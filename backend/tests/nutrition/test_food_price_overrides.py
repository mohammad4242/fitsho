from datetime import UTC, datetime
from decimal import Decimal


def test_active_override_precedes_accepted_automatic_reference(db) -> None:
    from app.auth.models import User
    from app.nutrition.enums import (
        EstimateConfidence,
        FoodVerificationStatus,
        PriceReferenceStatus,
    )
    from app.nutrition.models import (
        NutritionCatalogueFood,
        NutritionFoodPriceOverride,
        NutritionFoodPriceReference,
    )
    from app.nutrition.price_overrides import effective_prices

    now = datetime(2026, 8, 9, 12, tzinfo=UTC)
    admin = User(email="price-admin@example.com", password_hash="hash", is_admin=True)
    food = NutritionCatalogueFood(
        slug="override-rice",
        name_fa="برنج",
        name_en="Rice",
        verification_status=FoodVerificationStatus.VERIFIED,
        source_name="test",
        source_reference="https://example.test/rice",
    )
    db.add_all([admin, food])
    db.flush()
    db.add(
        NutritionFoodPriceReference(
            food_id=food.id,
            canonical_unit="TOMAN_PER_KG",
            reference_price_toman=Decimal("500000"),
            sample_count=3,
            confidence=EstimateConfidence.HIGH,
            status=PriceReferenceStatus.ACCEPTED,
            calculated_at=now,
            accepted_at=now,
        )
    )
    override = NutritionFoodPriceOverride(
        food_id=food.id,
        reference_price_toman=Decimal("450000"),
        canonical_unit="TOMAN_PER_KG",
        reason="اصلاح موقت قیمت بازار تهران",
        created_by_user_id=admin.id,
        created_at=now,
        active=True,
    )
    db.add(override)
    db.flush()

    effective = effective_prices(db, [food.id], now=now)[food.id]

    assert effective.source == "manual_override"
    assert effective.reference_price_toman == Decimal("450000")
    assert effective.reference_id == str(override.id)


def test_expiry_preserves_override_audit_record(db) -> None:
    from app.auth.models import User
    from app.nutrition.enums import (
        FoodVerificationStatus,
        PriceUpdateRunStatus,
        PriceUpdateTriggerKind,
    )
    from app.nutrition.models import (
        NutritionCatalogueFood,
        NutritionFoodPriceOverride,
        NutritionFoodPriceUpdateRun,
    )
    from app.nutrition.price_overrides import expire_active_overrides

    now = datetime(2026, 8, 9, 12, tzinfo=UTC)
    admin = User(email="expiry-admin@example.com", password_hash="hash", is_admin=True)
    food = NutritionCatalogueFood(
        slug="expiry-rice",
        name_fa="برنج",
        name_en="Rice",
        verification_status=FoodVerificationStatus.VERIFIED,
        source_name="test",
        source_reference="https://example.test/rice",
    )
    db.add_all([admin, food])
    db.flush()
    override = NutritionFoodPriceOverride(
        food_id=food.id,
        reference_price_toman=Decimal("450000"),
        canonical_unit="TOMAN_PER_KG",
        reason="اصلاح موقت قیمت بازار تهران",
        created_by_user_id=admin.id,
        created_at=now,
        active=True,
    )
    run = NutritionFoodPriceUpdateRun(
        scheduled_for=now,
        started_at=now,
        finished_at=now,
        status=PriceUpdateRunStatus.COMPLETED,
        trigger_kind=PriceUpdateTriggerKind.SCHEDULED,
        policy_version="public-price-v3",
    )
    db.add_all([override, run])
    db.flush()

    expired = expire_active_overrides(db, run=run, expired_at=now)
    db.flush()

    assert expired == 1
    assert override.active is False
    assert override.expired_at == now
    assert override.expired_by_run_id == run.id
    assert override.reference_price_toman == Decimal("450000")
    assert override.reason == "اصلاح موقت قیمت بازار تهران"


def test_planner_uses_active_override_without_mutating_automatic_reference(db) -> None:
    from sqlalchemy import select

    from app.auth.models import User
    from app.nutrition.models import NutritionCatalogueFood, NutritionFoodPriceOverride
    from app.nutrition.plan_service import _planner_foods

    now = datetime.now(UTC)
    admin = User(email="planner-price-admin@example.com", password_hash="hash", is_admin=True)
    rice = db.scalar(
        select(NutritionCatalogueFood).where(NutritionCatalogueFood.slug == "basmati-rice")
    )
    assert rice is not None
    db.add(admin)
    db.flush()
    override = NutritionFoodPriceOverride(
        food_id=rice.id,
        reference_price_toman=Decimal("600000"),
        canonical_unit="TOMAN_PER_KG",
        reason="قیمت معتبر موقت برای برنامه غذایی",
        created_by_user_id=admin.id,
        created_at=now,
        active=True,
    )
    db.add(override)
    db.flush()

    candidates, snapshot, _manifest = _planner_foods(db)

    candidate = next(item for item in candidates if item.slug == "basmati-rice")
    reference = next(item for item in snapshot["references"] if item["food_id"] == str(rice.id))
    assert candidate.price_irr_per_gram == Decimal("6000")
    assert reference["source"] == "manual_override"
    assert reference["reference_id"] == str(override.id)
