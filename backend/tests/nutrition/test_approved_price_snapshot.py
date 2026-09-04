from datetime import UTC, datetime
from decimal import Decimal

import pytest
from sqlalchemy import select


def _user(db, *, email: str, is_admin: bool):
    from app.auth.models import User

    user = User(email=email, password_hash="hash", is_admin=is_admin)
    db.add(user)
    db.flush()
    return user


def _seed_approved_catalogue(db) -> None:
    from app.nutrition.food_catalogue import seed_base_iranian_food_catalogue

    seed_base_iranian_food_catalogue(db, commit=False)


def test_snapshot_has_exact_approved_food_set_and_valid_values() -> None:
    from app.nutrition.approved_price_snapshot import (
        APPROVED_PRICE_SNAPSHOT,
        validate_approved_price_snapshot,
    )
    from app.nutrition.catalogue_seed_data import APPROVED_FOODS

    report = validate_approved_price_snapshot()

    assert len(APPROVED_PRICE_SNAPSHOT) == 72
    assert len({entry.slug for entry in APPROVED_PRICE_SNAPSHOT}) == 72
    assert {entry.slug for entry in APPROVED_PRICE_SNAPSHOT} == {
        food.slug for food in APPROVED_FOODS
    }
    assert report.is_valid is True
    assert report.missing_slugs == ()
    assert report.extra_slugs == ()
    assert report.duplicate_slugs == ()
    assert report.invalid_prices == ()
    assert report.invalid_units == ()
    assert report.missing_price_mass_conversions == ()
    assert all(
        isinstance(entry.reference_price_toman, Decimal) for entry in APPROVED_PRICE_SNAPSHOT
    )
    assert all(entry.reference_price_toman > Decimal("0") for entry in APPROVED_PRICE_SNAPSHOT)
    assert {entry.canonical_unit for entry in APPROVED_PRICE_SNAPSHOT} <= {
        "TOMAN_PER_KG",
        "TOMAN_PER_LITER",
        "TOMAN_PER_UNIT",
    }


def test_snapshot_contains_the_exact_non_kg_price_baselines() -> None:
    from app.nutrition.approved_price_snapshot import APPROVED_PRICE_SNAPSHOT

    entries = {
        entry.slug: (entry.reference_price_toman, entry.canonical_unit)
        for entry in APPROVED_PRICE_SNAPSHOT
    }

    assert entries["egg"] == (Decimal("21000"), "TOMAN_PER_UNIT")
    assert entries["sangak-bread"] == (Decimal("15500"), "TOMAN_PER_UNIT")
    assert entries["barbari-bread"] == (Decimal("10000"), "TOMAN_PER_UNIT")
    assert entries["lavash-bread"] == (Decimal("2700"), "TOMAN_PER_UNIT")
    assert entries["taftoon-bread"] == (Decimal("4500"), "TOMAN_PER_UNIT")
    assert entries["milk"] == (Decimal("120000"), "TOMAN_PER_LITER")
    assert entries["olive-oil"] == (Decimal("1400000"), "TOMAN_PER_LITER")
    assert entries["vegetable-oil"] == (Decimal("410000"), "TOMAN_PER_LITER")


def test_apply_creates_one_manual_override_for_each_verified_food(db) -> None:
    from app.nutrition.approved_price_snapshot import apply_approved_price_snapshot
    from app.nutrition.models import NutritionFoodPriceOverride

    _seed_approved_catalogue(db)
    _user(db, email="snapshot-admin@example.com", is_admin=True)

    result = apply_approved_price_snapshot(db, admin_email="snapshot-admin@example.com")

    assert result.created_count == 72
    assert result.replaced_count == 0
    assert result.skipped_count == 0
    overrides = db.scalars(select(NutritionFoodPriceOverride)).all()
    assert len(overrides) == 72
    assert sum(override.active for override in overrides) == 72


def test_apply_preserves_automatic_reference_and_price_history(db) -> None:
    from app.nutrition.approved_price_snapshot import apply_approved_price_snapshot
    from app.nutrition.enums import EstimateConfidence, PriceReferenceStatus
    from app.nutrition.models import (
        NutritionCatalogueFood,
        NutritionFoodPriceHistory,
        NutritionFoodPriceReference,
    )

    _seed_approved_catalogue(db)
    admin = _user(db, email="snapshot-preserve-admin@example.com", is_admin=True)
    food = db.scalar(select(NutritionCatalogueFood).where(NutritionCatalogueFood.slug == "egg"))
    assert food is not None
    now = datetime(2026, 9, 2, 12, tzinfo=UTC)
    reference = NutritionFoodPriceReference(
        food_id=food.id,
        canonical_unit="TOMAN_PER_UNIT",
        reference_price_toman=Decimal("19000"),
        sample_count=3,
        confidence=EstimateConfidence.HIGH,
        status=PriceReferenceStatus.ACCEPTED,
        calculated_at=now,
        accepted_at=now,
    )
    history = NutritionFoodPriceHistory(
        food_id=food.id,
        canonical_unit="TOMAN_PER_UNIT",
        reference_price_toman=Decimal("19000"),
        sample_count=3,
        confidence=EstimateConfidence.HIGH,
        accepted_at=now,
        source_quote_ids=["quote-1"],
    )
    db.add_all([reference, history])
    db.flush()

    apply_approved_price_snapshot(db, admin_email=admin.email)

    assert db.get(NutritionFoodPriceReference, food.id) is reference
    assert reference.reference_price_toman == Decimal("19000")
    assert db.get(NutritionFoodPriceHistory, history.id) is history
    assert history.source_quote_ids == ["quote-1"]


def test_apply_replaces_previous_override_without_deleting_it(db) -> None:
    from app.nutrition.approved_price_snapshot import apply_approved_price_snapshot
    from app.nutrition.models import NutritionCatalogueFood, NutritionFoodPriceOverride

    _seed_approved_catalogue(db)
    admin = _user(db, email="snapshot-replace-admin@example.com", is_admin=True)
    food = db.scalar(select(NutritionCatalogueFood).where(NutritionCatalogueFood.slug == "egg"))
    assert food is not None
    previous = NutritionFoodPriceOverride(
        food_id=food.id,
        reference_price_toman=Decimal("18000"),
        canonical_unit="TOMAN_PER_UNIT",
        reason="قیمت قبلی دستی",
        created_by_user_id=admin.id,
        created_at=datetime(2026, 9, 1, 12, tzinfo=UTC),
        active=True,
    )
    db.add(previous)
    db.flush()
    previous_id = previous.id

    result = apply_approved_price_snapshot(db, admin_email=admin.email)

    db.expire_all()
    old = db.get(NutritionFoodPriceOverride, previous_id)
    active = db.scalar(
        select(NutritionFoodPriceOverride).where(
            NutritionFoodPriceOverride.food_id == food.id,
            NutritionFoodPriceOverride.active.is_(True),
        )
    )
    assert result.replaced_count == 1
    assert old is not None
    assert old.active is False
    assert old.expired_at is not None
    assert active is not None
    assert active.id != previous_id
    assert active.reference_price_toman == Decimal("21000")


def test_apply_is_idempotent_for_same_snapshot_version(db) -> None:
    from app.nutrition.approved_price_snapshot import apply_approved_price_snapshot
    from app.nutrition.models import NutritionFoodPriceOverride

    _seed_approved_catalogue(db)
    admin = _user(db, email="snapshot-idempotent-admin@example.com", is_admin=True)

    first = apply_approved_price_snapshot(db, admin_email=admin.email)
    before = db.scalars(select(NutritionFoodPriceOverride)).all()
    second = apply_approved_price_snapshot(db, admin_email=admin.email)
    after = db.scalars(select(NutritionFoodPriceOverride)).all()

    assert first.created_count == 72
    assert second.created_count == 0
    assert second.replaced_count == 0
    assert second.skipped_count == 72
    assert len(after) == len(before) == 72
    assert sum(item.active for item in after) == 72


def test_apply_missing_catalogue_food_fails_before_any_partial_override(db) -> None:
    from app.nutrition.approved_price_snapshot import (
        ApprovedPriceSnapshotCatalogueMismatchError,
        apply_approved_price_snapshot,
    )
    from app.nutrition.enums import FoodVerificationStatus
    from app.nutrition.models import NutritionCatalogueFood, NutritionFoodPriceOverride

    _seed_approved_catalogue(db)
    admin = _user(db, email="snapshot-missing-admin@example.com", is_admin=True)
    food = db.scalar(select(NutritionCatalogueFood).where(NutritionCatalogueFood.slug == "melon"))
    assert food is not None
    food.verification_status = FoodVerificationStatus.DRAFT
    db.flush()

    with pytest.raises(ApprovedPriceSnapshotCatalogueMismatchError, match="melon"):
        apply_approved_price_snapshot(db, admin_email=admin.email)

    assert db.scalars(select(NutritionFoodPriceOverride)).all() == []


def test_apply_rejects_non_admin_user_without_mutation(db) -> None:
    from app.nutrition.approved_price_snapshot import (
        ApprovedPriceSnapshotAdminError,
        apply_approved_price_snapshot,
    )
    from app.nutrition.models import NutritionFoodPriceOverride

    _seed_approved_catalogue(db)
    member = _user(db, email="snapshot-member@example.com", is_admin=False)

    with pytest.raises(ApprovedPriceSnapshotAdminError, match="admin"):
        apply_approved_price_snapshot(db, admin_email=member.email)

    assert db.scalars(select(NutritionFoodPriceOverride)).all() == []


def test_apply_resolves_exactly_one_admin_when_email_is_omitted(db) -> None:
    from app.nutrition.approved_price_snapshot import apply_approved_price_snapshot

    _seed_approved_catalogue(db)
    _user(db, email="only-snapshot-admin@example.com", is_admin=True)

    result = apply_approved_price_snapshot(db)

    assert result.created_count == 72


def test_after_apply_all_snapshot_foods_have_effective_prices(db) -> None:
    from app.nutrition.approved_price_snapshot import (
        APPROVED_PRICE_SNAPSHOT,
        apply_approved_price_snapshot,
    )
    from app.nutrition.models import NutritionCatalogueFood
    from app.nutrition.price_overrides import effective_prices

    _seed_approved_catalogue(db)
    admin = _user(db, email="snapshot-effective-admin@example.com", is_admin=True)
    apply_approved_price_snapshot(db, admin_email=admin.email)
    foods = db.scalars(
        select(NutritionCatalogueFood).where(
            NutritionCatalogueFood.slug.in_([entry.slug for entry in APPROVED_PRICE_SNAPSHOT])
        )
    ).all()

    effective = effective_prices(db, [food.id for food in foods])

    assert len(foods) == 72
    assert len(effective) == 72
    assert all(item.source == "manual_override" for item in effective.values())


def test_applied_snapshot_keeps_non_kg_units_and_planner_mass_audit(db) -> None:
    from app.nutrition.approved_price_snapshot import apply_approved_price_snapshot
    from app.nutrition.plan_service import _planner_foods

    _seed_approved_catalogue(db)
    admin = _user(db, email="snapshot-planner-admin@example.com", is_admin=True)
    apply_approved_price_snapshot(db, admin_email=admin.email)

    candidates, price_snapshot, _manifest = _planner_foods(db)
    candidates_by_slug = {candidate.slug: candidate for candidate in candidates}
    snapshots_by_slug = {
        item["slug"]: item
        for item in price_snapshot["references"]
        if isinstance(item, dict) and "slug" in item
    }

    expected = {
        "egg": (Decimal("4200"), "TOMAN_PER_UNIT", "50"),
        "sangak-bread": (
            Decimal("15500") * Decimal("10") / Decimal("600"),
            "TOMAN_PER_UNIT",
            "600",
        ),
        "barbari-bread": (
            Decimal("10000") * Decimal("10") / Decimal("550"),
            "TOMAN_PER_UNIT",
            "550",
        ),
        "lavash-bread": (
            Decimal("2700") * Decimal("10") / Decimal("130"),
            "TOMAN_PER_UNIT",
            "130",
        ),
        "taftoon-bread": (
            Decimal("4500") * Decimal("10") / Decimal("320"),
            "TOMAN_PER_UNIT",
            "320",
        ),
        "milk": (
            Decimal("120000") * Decimal("10") / Decimal("1030"),
            "TOMAN_PER_LITER",
            "1030",
        ),
        "olive-oil": (
            Decimal("1400000") * Decimal("10") / Decimal("913"),
            "TOMAN_PER_LITER",
            "913",
        ),
        "vegetable-oil": (
            Decimal("410000") * Decimal("10") / Decimal("920"),
            "TOMAN_PER_LITER",
            "920",
        ),
    }
    assert set(expected) <= candidates_by_slug.keys()
    for slug, (price, unit, grams) in expected.items():
        assert candidates_by_slug[slug].price_irr_per_gram == price
        assert snapshots_by_slug[slug]["canonical_unit"] == unit
        assert snapshots_by_slug[slug]["grams_per_price_unit"] == grams
        assert (
            snapshots_by_slug[slug]["price_mass_conversion_version"] == "price-mass-equivalent-v1"
        )
