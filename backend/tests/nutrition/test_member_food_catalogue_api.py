from datetime import UTC, datetime
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.auth.models import User
from app.config import Settings
from app.profile.enums import ProductMode
from app.profile.models import UserProfile

ORIGIN = {"Origin": "http://localhost:5173"}
PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32


def _register_with_mode(
    client: TestClient,
    db: Session,
    *,
    email: str,
    mode: ProductMode,
    admin: bool = False,
) -> User:
    response = client.post(
        "/api/v1/auth/register",
        headers=ORIGIN,
        json={"email": email, "password": "long password"},
    )
    assert response.status_code == 201
    user = db.scalar(select(User).where(User.email == email))
    assert user is not None
    user.is_admin = admin
    db.add(UserProfile(user_id=user.id, product_mode=mode))
    db.commit()
    return user


def test_training_member_cannot_read_food_catalogue(client: TestClient, db: Session) -> None:
    _register_with_mode(
        client,
        db,
        email="training-catalogue@example.com",
        mode=ProductMode.TRAINING,
    )

    response = client.get("/api/v1/nutrition/food-catalogue")

    assert response.status_code == 403


def test_nutrition_member_sees_macros_search_and_no_price_data(
    client: TestClient, db: Session
) -> None:
    _register_with_mode(
        client,
        db,
        email="nutrition-catalogue@example.com",
        mode=ProductMode.NUTRITION,
    )

    response = client.get(
        "/api/v1/nutrition/food-catalogue",
        params={"q": "سینه مرغ", "category": "poultry", "page": 1, "page_size": 12},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["page"] == 1
    assert payload["page_size"] == 12
    assert payload["total"] == 1
    assert "poultry" in payload["categories"]
    item = payload["items"][0]
    assert item["slug"] == "chicken-breast"
    assert set(item["macros"]) == {
        "energy_kcal",
        "protein_g",
        "carbohydrate_g",
        "total_fat_g",
        "fibre_g",
    }
    assert item["nutrient_basis"] == {"quantity": "100.0000", "unit": "g"}
    assert item["image_url"] is None
    assert "price" not in item
    assert any(nutrient["nutrient_code"] == "iron_mg" for nutrient in item["nutrients"])


def test_member_never_receives_an_accepted_catalogue_price(client: TestClient, db: Session) -> None:
    from app.nutrition.enums import EstimateConfidence, PriceReferenceStatus
    from app.nutrition.models import NutritionCatalogueFood, NutritionFoodPriceReference

    _register_with_mode(
        client,
        db,
        email="both-catalogue@example.com",
        mode=ProductMode.BOTH,
    )
    rice = db.scalar(
        select(NutritionCatalogueFood).where(NutritionCatalogueFood.slug == "basmati-rice")
    )
    assert rice is not None
    now = datetime.now(UTC)
    reference = db.get(NutritionFoodPriceReference, rice.id)
    if reference is None:
        reference = NutritionFoodPriceReference(
            food_id=rice.id,
            canonical_unit="TOMAN_PER_KG",
            reference_price_toman=Decimal("590000"),
            sample_count=3,
            confidence=EstimateConfidence.HIGH,
            status=PriceReferenceStatus.ACCEPTED,
            calculated_at=now,
            accepted_at=now,
        )
        db.add(reference)
    else:
        reference.reference_price_toman = Decimal("590000")
        reference.status = PriceReferenceStatus.ACCEPTED
        reference.calculated_at = now
        reference.accepted_at = now
    db.commit()

    response = client.get("/api/v1/nutrition/food-catalogue?q=Rice")

    assert response.status_code == 200
    item = next(row for row in response.json()["items"] if row["slug"] == "basmati-rice")
    assert "price" not in item


def test_admin_reads_catalogue_with_price_data(client: TestClient, db: Session) -> None:
    from app.nutrition.enums import EstimateConfidence, PriceReferenceStatus
    from app.nutrition.models import NutritionCatalogueFood, NutritionFoodPriceReference

    _register_with_mode(
        client,
        db,
        email="admin-catalogue-read@example.com",
        mode=ProductMode.NUTRITION,
        admin=True,
    )
    rice = db.scalar(
        select(NutritionCatalogueFood).where(NutritionCatalogueFood.slug == "basmati-rice")
    )
    assert rice is not None
    now = datetime.now(UTC)
    db.merge(
        NutritionFoodPriceReference(
            food_id=rice.id,
            canonical_unit="TOMAN_PER_KG",
            reference_price_toman=Decimal("590000"),
            sample_count=3,
            confidence=EstimateConfidence.HIGH,
            status=PriceReferenceStatus.ACCEPTED,
            calculated_at=now,
            accepted_at=now,
        )
    )
    db.commit()

    response = client.get("/api/v1/nutrition/admin/food-catalogue?q=Rice")

    assert response.status_code == 200
    item = next(row for row in response.json()["items"] if row["slug"] == "basmati-rice")
    assert item["price"]["status"] == "accepted"
    assert item["image_url"] is None


def test_admin_uploads_and_replaces_food_image_without_exposing_price_to_member(
    client: TestClient,
    db: Session,
    test_settings: Settings,
) -> None:
    _register_with_mode(
        client,
        db,
        email="admin-catalogue-image@example.com",
        mode=ProductMode.NUTRITION,
        admin=True,
    )

    first = client.post(
        "/api/v1/nutrition/admin/foods/chicken-breast/image",
        headers=ORIGIN,
        files={"file": ("chicken.png", PNG_BYTES, "image/png")},
    )

    assert first.status_code == 200
    first_url = first.json()["image_url"]
    assert first_url.startswith("/media/food-catalogue/")
    first_path = test_settings.media_root / first_url.removeprefix("/media/")
    assert first_path.read_bytes() == PNG_BYTES

    second = client.post(
        "/api/v1/nutrition/admin/foods/chicken-breast/image",
        headers=ORIGIN,
        files={"file": ("replacement.png", PNG_BYTES + b"replacement", "image/png")},
    )

    assert second.status_code == 200
    assert second.json()["image_url"] != first_url
    assert not first_path.exists()
    member_items = client.get("/api/v1/nutrition/food-catalogue?q=chicken").json()["items"]
    member = next(item for item in member_items if item["slug"] == "chicken-breast")
    assert member["image_url"] == second.json()["image_url"]
    assert "price" not in member


def test_food_image_upload_requires_admin_and_trusted_origin(
    client: TestClient, db: Session
) -> None:
    _register_with_mode(
        client,
        db,
        email="member-catalogue-image@example.com",
        mode=ProductMode.NUTRITION,
    )

    forbidden = client.post(
        "/api/v1/nutrition/admin/foods/chicken-breast/image",
        headers=ORIGIN,
        files={"file": ("chicken.png", PNG_BYTES, "image/png")},
    )
    assert forbidden.status_code == 403


def test_food_image_upload_rejects_invalid_image_and_missing_food(
    client: TestClient, db: Session
) -> None:
    _register_with_mode(
        client,
        db,
        email="admin-invalid-catalogue-image@example.com",
        mode=ProductMode.NUTRITION,
        admin=True,
    )

    invalid = client.post(
        "/api/v1/nutrition/admin/foods/chicken-breast/image",
        headers=ORIGIN,
        files={"file": ("chicken.png", b"not-an-image", "image/png")},
    )
    missing = client.post(
        "/api/v1/nutrition/admin/foods/not-a-food/image",
        headers=ORIGIN,
        files={"file": ("chicken.png", PNG_BYTES, "image/png")},
    )
    no_origin = client.post(
        "/api/v1/nutrition/admin/foods/chicken-breast/image",
        files={"file": ("chicken.png", PNG_BYTES, "image/png")},
    )

    assert invalid.status_code == 422
    assert missing.status_code == 404
    assert no_origin.status_code == 403


def test_only_admin_can_create_audited_price_override(client: TestClient, db: Session) -> None:
    from app.nutrition.models import NutritionFoodPriceOverride

    admin = _register_with_mode(
        client,
        db,
        email="catalogue-admin@example.com",
        mode=ProductMode.NUTRITION,
        admin=True,
    )

    response = client.post(
        "/api/v1/nutrition/admin/foods/basmati-rice/price-override",
        headers=ORIGIN,
        json={
            "reference_price_toman": "610000",
            "canonical_unit": "TOMAN_PER_KG",
            "reason": "اصلاح قیمت هفتگی بازار تهران",
        },
    )

    assert response.status_code == 201
    assert response.json()["source"] == "manual_override"
    override = db.scalar(
        select(NutritionFoodPriceOverride).where(NutritionFoodPriceOverride.active.is_(True))
    )
    assert override is not None
    assert override.created_by_user_id == admin.id
    assert override.reason == "اصلاح قیمت هفتگی بازار تهران"

    response_without_origin = client.post(
        "/api/v1/nutrition/admin/foods/basmati-rice/price-override",
        json={
            "reference_price_toman": "620000",
            "canonical_unit": "TOMAN_PER_KG",
            "reason": "اصلاح مجدد قیمت بازار تهران",
        },
    )
    assert response_without_origin.status_code == 403


def test_admin_can_retire_catalogue_food_and_repeat_idempotently(
    client: TestClient, db: Session
) -> None:
    from app.nutrition.enums import FoodVerificationStatus
    from app.nutrition.models import NutritionCatalogueFood

    _register_with_mode(
        client,
        db,
        email="admin-catalogue-retire@example.com",
        mode=ProductMode.NUTRITION,
        admin=True,
    )

    response = client.delete(
        "/api/v1/nutrition/admin/foods/chicken-breast",
        headers=ORIGIN,
    )

    assert response.status_code == 204
    assert response.content == b""
    food = db.scalar(
        select(NutritionCatalogueFood).where(NutritionCatalogueFood.slug == "chicken-breast")
    )
    assert food is not None
    assert food.verification_status is FoodVerificationStatus.RETIRED

    repeated = client.delete(
        "/api/v1/nutrition/admin/foods/chicken-breast",
        headers=ORIGIN,
    )

    assert repeated.status_code == 204
    assert db.get(NutritionCatalogueFood, food.id) is not None


def test_retired_food_disappears_from_admin_catalogue(client: TestClient, db: Session) -> None:
    _register_with_mode(
        client,
        db,
        email="admin-catalogue-retire-list@example.com",
        mode=ProductMode.NUTRITION,
        admin=True,
    )

    assert (
        client.delete(
            "/api/v1/nutrition/admin/foods/chicken-breast",
            headers=ORIGIN,
        ).status_code
        == 204
    )

    response = client.get("/api/v1/nutrition/admin/food-catalogue", params={"q": "chicken"})

    assert response.status_code == 200
    assert all(item["slug"] != "chicken-breast" for item in response.json()["items"])


def test_retired_food_disappears_from_member_catalogue(client: TestClient, db: Session) -> None:
    _register_with_mode(
        client,
        db,
        email="admin-catalogue-retire-member-list@example.com",
        mode=ProductMode.NUTRITION,
        admin=True,
    )
    assert (
        client.delete(
            "/api/v1/nutrition/admin/foods/chicken-breast",
            headers=ORIGIN,
        ).status_code
        == 204
    )
    _register_with_mode(
        client,
        db,
        email="member-catalogue-after-retire@example.com",
        mode=ProductMode.NUTRITION,
    )

    response = client.get("/api/v1/nutrition/food-catalogue", params={"q": "chicken"})

    assert response.status_code == 200
    assert all(item["slug"] != "chicken-breast" for item in response.json()["items"])


def test_non_admin_cannot_retire_catalogue_food(client: TestClient, db: Session) -> None:
    _register_with_mode(
        client,
        db,
        email="member-catalogue-retire-forbidden@example.com",
        mode=ProductMode.NUTRITION,
    )

    response = client.delete(
        "/api/v1/nutrition/admin/foods/chicken-breast",
        headers=ORIGIN,
    )

    assert response.status_code == 403


def test_catalogue_retirement_requires_trusted_origin(client: TestClient, db: Session) -> None:
    _register_with_mode(
        client,
        db,
        email="admin-catalogue-retire-origin@example.com",
        mode=ProductMode.NUTRITION,
        admin=True,
    )

    response = client.delete("/api/v1/nutrition/admin/foods/chicken-breast")

    assert response.status_code == 403


def test_catalogue_retirement_returns_not_found_for_unknown_slug(
    client: TestClient, db: Session
) -> None:
    _register_with_mode(
        client,
        db,
        email="admin-catalogue-retire-missing@example.com",
        mode=ProductMode.NUTRITION,
        admin=True,
    )

    response = client.delete(
        "/api/v1/nutrition/admin/foods/not-a-real-food",
        headers=ORIGIN,
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Food not found"


def test_catalogue_retirement_preserves_children_price_history_and_meal_reference(
    client: TestClient, db: Session
) -> None:
    from app.nutrition.enums import (
        EstimateConfidence,
        FoodVerificationStatus,
        MealCategory,
        PriceReferenceStatus,
    )
    from app.nutrition.models import (
        NutritionCatalogueFood,
        NutritionCatalogueMeal,
        NutritionCatalogueMealItem,
        NutritionFoodPriceHistory,
        NutritionFoodPriceReference,
    )
    from app.nutrition.plan_service import _planner_foods

    _register_with_mode(
        client,
        db,
        email="admin-catalogue-retire-preserve@example.com",
        mode=ProductMode.NUTRITION,
        admin=True,
    )
    food = db.scalar(
        select(NutritionCatalogueFood)
        .where(NutritionCatalogueFood.slug == "chicken-breast")
        .options(
            selectinload(NutritionCatalogueFood.aliases),
            selectinload(NutritionCatalogueFood.compositions),
            selectinload(NutritionCatalogueFood.portions),
        )
    )
    assert food is not None
    alias_ids = {alias.id for alias in food.aliases}
    composition_ids = {composition.id for composition in food.compositions}
    portion_ids = {portion.id for portion in food.portions}

    meal = NutritionCatalogueMeal(
        code="retire-preserve",
        name_fa="وعده تست حفظ سابقه",
        name_en="Retirement preservation meal",
        category=MealCategory.LUNCH,
        verification_status=FoodVerificationStatus.DRAFT,
    )
    db.add(meal)
    db.flush()
    meal_item = NutritionCatalogueMealItem(
        meal_id=meal.id,
        food_id=food.id,
        reference_grams=Decimal("100"),
        min_grams=Decimal("80"),
        max_grams=Decimal("120"),
    )
    db.add(meal_item)
    db.flush()
    meal_item_count_before = db.scalar(
        select(func.count())
        .select_from(NutritionCatalogueMealItem)
        .where(NutritionCatalogueMealItem.food_id == food.id)
    )
    now = datetime.now(UTC)
    reference = NutritionFoodPriceReference(
        food_id=food.id,
        canonical_unit="TOMAN_PER_KG",
        reference_price_toman=Decimal("590000"),
        sample_count=3,
        confidence=EstimateConfidence.HIGH,
        status=PriceReferenceStatus.ACCEPTED,
        calculated_at=now,
        accepted_at=now,
    )
    history = NutritionFoodPriceHistory(
        food_id=food.id,
        canonical_unit="TOMAN_PER_KG",
        reference_price_toman=Decimal("590000"),
        sample_count=3,
        confidence=EstimateConfidence.HIGH,
        accepted_at=now,
        source_quote_ids=[],
        accepted_quote_ids=[],
        rejected_quote_ids=[],
    )
    db.add_all([reference, history])
    db.commit()

    response = client.delete(
        "/api/v1/nutrition/admin/foods/chicken-breast",
        headers=ORIGIN,
    )

    assert response.status_code == 204
    preserved = db.scalar(
        select(NutritionCatalogueFood)
        .where(NutritionCatalogueFood.slug == "chicken-breast")
        .options(
            selectinload(NutritionCatalogueFood.aliases),
            selectinload(NutritionCatalogueFood.compositions),
            selectinload(NutritionCatalogueFood.portions),
        )
    )
    assert preserved is not None
    assert preserved.verification_status is FoodVerificationStatus.RETIRED
    assert {alias.id for alias in preserved.aliases} == alias_ids
    assert {composition.id for composition in preserved.compositions} == composition_ids
    assert {portion.id for portion in preserved.portions} == portion_ids
    assert db.get(NutritionCatalogueMealItem, meal_item.id) is not None
    assert db.get(NutritionFoodPriceReference, food.id) is not None
    assert db.get(NutritionFoodPriceHistory, history.id) is not None
    planner_foods, _, _ = _planner_foods(db)
    assert all(candidate.slug != "chicken-breast" for candidate in planner_foods)

    meal_item_count = db.scalar(
        select(func.count())
        .select_from(NutritionCatalogueMealItem)
        .where(NutritionCatalogueMealItem.food_id == food.id)
    )
    assert meal_item_count == meal_item_count_before
