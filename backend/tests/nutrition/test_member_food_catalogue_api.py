from datetime import UTC, datetime
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.models import User
from app.profile.enums import ProductMode
from app.profile.models import UserProfile

ORIGIN = {"Origin": "http://localhost:5173"}


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
