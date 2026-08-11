from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.models import User

ORIGIN = {"Origin": "http://localhost:5173"}


def _register_admin(client: TestClient, db: Session) -> None:
    response = client.post(
        "/api/v1/auth/register",
        headers=ORIGIN,
        json={"email": "meal-admin@example.com", "password": "long password"},
    )
    assert response.status_code == 201
    user = db.scalar(select(User).where(User.email == "meal-admin@example.com"))
    assert user is not None
    user.is_admin = True
    db.commit()


def test_seed_creates_one_existing_food_linked_meal_for_every_category(db: Session) -> None:
    from app.nutrition.food_catalogue import seed_base_iranian_food_catalogue
    from app.nutrition.meal_catalogue import seed_meal_catalogue

    seed_base_iranian_food_catalogue(db)
    meals = seed_meal_catalogue(db)

    assert {meal.category.value for meal in meals} == {
        "breakfast",
        "lunch",
        "post_workout",
        "snack",
        "dinner",
    }
    assert all(meal.items for meal in meals)
    assert all(item.food_id is not None for meal in meals for item in meal.items)
    peanuts = next(meal for meal in meals if meal.category.value == "snack")
    assert peanuts.items[0].reference_grams == Decimal("50")
    assert peanuts.items[0].min_grams <= Decimal("50") <= peanuts.items[0].max_grams


def test_admin_lists_and_updates_meals_with_bounded_ingredients(
    client: TestClient,
    db: Session,
) -> None:
    from app.nutrition.food_catalogue import seed_base_iranian_food_catalogue
    from app.nutrition.meal_catalogue import seed_meal_catalogue
    from app.nutrition.models import NutritionCatalogueFood

    seed_base_iranian_food_catalogue(db)
    seed_meal_catalogue(db)
    _register_admin(client, db)
    egg = db.scalar(select(NutritionCatalogueFood).where(NutritionCatalogueFood.slug == "egg"))
    tomato = db.scalar(
        select(NutritionCatalogueFood).where(NutritionCatalogueFood.slug == "tomato")
    )
    assert egg is not None and tomato is not None

    listed = client.get("/api/v1/nutrition/admin/meals?category=breakfast")

    assert listed.status_code == 200
    assert listed.json()["categories"] == [
        "breakfast",
        "lunch",
        "post_workout",
        "snack",
        "dinner",
    ]
    assert len(listed.json()["items"]) == 1
    meal_id = listed.json()["items"][0]["id"]

    updated = client.put(
        f"/api/v1/nutrition/admin/meals/{meal_id}",
        headers=ORIGIN,
        json={
            "name_fa": "املت تخم‌مرغ و گوجه",
            "name_en": "Egg and tomato breakfast",
            "category": "breakfast",
            "verification_status": "verified",
            "items": [
                {
                    "food_id": str(egg.id),
                    "reference_grams": 100,
                    "min_grams": 50,
                    "max_grams": 150,
                    "is_required": True,
                    "functional_role": "protein",
                },
                {
                    "food_id": str(tomato.id),
                    "reference_grams": 60,
                    "min_grams": 30,
                    "max_grams": 120,
                    "is_required": False,
                    "functional_role": "micronutrient_source",
                },
            ],
        },
    )

    assert updated.status_code == 200
    body = updated.json()
    assert body["name_fa"] == "املت تخم‌مرغ و گوجه"
    assert body["category"] == "breakfast"
    assert body["items"][1]["is_required"] is False
    assert body["items"][1]["max_grams"] == 120


def test_admin_rejects_verified_meal_with_draft_food_or_invalid_bounds(
    client: TestClient,
    db: Session,
) -> None:
    from app.nutrition.food_catalogue import seed_base_iranian_food_catalogue
    from app.nutrition.models import NutritionCatalogueFood

    seed_base_iranian_food_catalogue(db)
    _register_admin(client, db)
    bread = db.scalar(
        select(NutritionCatalogueFood).where(NutritionCatalogueFood.slug == "sangak-bread")
    )
    assert bread is not None

    response = client.post(
        "/api/v1/nutrition/admin/meals",
        headers=ORIGIN,
        json={
            "name_fa": "صبحانه نامعتبر",
            "name_en": "Invalid breakfast",
            "category": "breakfast",
            "verification_status": "verified",
            "items": [
                {
                    "food_id": str(bread.id),
                    "reference_grams": 50,
                    "min_grams": 80,
                    "max_grams": 40,
                    "is_required": True,
                    "functional_role": "carbohydrate",
                }
            ],
        },
    )

    assert response.status_code == 422


def test_meal_catalogue_requires_admin_access(client: TestClient) -> None:
    assert client.get("/api/v1/nutrition/admin/meals").status_code == 401
