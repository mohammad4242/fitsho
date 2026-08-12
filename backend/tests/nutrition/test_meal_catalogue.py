from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import func, select
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


def _add_required_imported_foods(db: Session) -> None:
    from app.nutrition.enums import FoodMeasurementBasis, FoodVerificationStatus
    from app.nutrition.models import NutritionCatalogueFood

    for slug, name_fa, name_en, category in (
        ("creamy-peanut-butter", "کره بادام‌زمینی", "Creamy peanut butter", "nuts_seeds"),
        ("wheat-flour", "آرد گندم", "Wheat flour", "grains"),
        ("green-beans", "لوبیا سبز", "Green beans", "vegetable"),
        ("tomato-paste", "رب گوجه‌فرنگی", "Tomato paste", "vegetable"),
    ):
        if db.scalar(select(NutritionCatalogueFood.id).where(NutritionCatalogueFood.slug == slug)):
            continue
        db.add(
            NutritionCatalogueFood(
                slug=slug,
                name_fa=name_fa,
                name_en=name_en,
                verification_status=FoodVerificationStatus.VERIFIED,
                source_name="USDA FoodData Central Foundation Foods",
                source_reference="https://fdc.nal.usda.gov/",
                category=category,
                measurement_basis=FoodMeasurementBasis.AS_PURCHASED,
                canonical_quantity=Decimal("100"),
                canonical_unit="g",
                edible_portion=Decimal("1"),
                data_version="foundation-test-fixture",
                dietary_patterns=["omnivore", "vegetarian", "vegan"],
            )
        )
    db.commit()


def test_seed_creates_exact_complete_bounded_meal_catalogue_idempotently(db: Session) -> None:
    from app.nutrition.enums import FoodVerificationStatus, MealCategory
    from app.nutrition.food_catalogue import seed_base_iranian_food_catalogue
    from app.nutrition.meal_catalogue import seed_meal_catalogue
    from app.nutrition.models import NutritionCatalogueMeal

    seed_base_iranian_food_catalogue(db)
    _add_required_imported_foods(db)
    custom = NutritionCatalogueMeal(
        code="CUSTOM01",
        name_fa="وعده سفارشی حفظ‌شونده",
        name_en="Preserved custom meal",
        category=MealCategory.SNACK,
        verification_status=FoodVerificationStatus.DRAFT,
    )
    db.add(custom)
    db.commit()
    first = seed_meal_catalogue(db)
    second = seed_meal_catalogue(db)

    expected_codes = {
        *(f"BF{number:02}" for number in range(1, 9)),
        *(f"LU{number:02}" for number in range(1, 14)),
        *(f"DN{number:02}" for number in range(1, 9)),
        *(f"SN{number:02}" for number in range(1, 9)),
        "PW01",
    }
    seeded = [meal for meal in second if meal.code in expected_codes]

    assert len(first) == 39
    assert len(second) == 39
    assert len(seeded) == 38
    assert {meal.code for meal in seeded} == expected_codes
    assert db.scalar(select(func.count()).select_from(NutritionCatalogueMeal)) == 39
    assert {
        category: sum(meal.category.value == category for meal in seeded)
        for category in ("breakfast", "lunch", "dinner", "snack", "post_workout")
    } == {
        "breakfast": 8,
        "lunch": 13,
        "dinner": 8,
        "snack": 8,
        "post_workout": 1,
    }
    assert all(meal.verification_status.value == "verified" for meal in seeded)
    assert all(meal.items for meal in seeded)
    assert all(item.food_id is not None for meal in seeded for item in meal.items)
    assert all(item.functional_role is not None for meal in seeded for item in meal.items)
    assert all(
        item.min_grams <= item.reference_grams <= item.max_grams
        for meal in seeded
        for item in meal.items
    )
    peanuts = next(meal for meal in seeded if meal.code == "SN01")
    assert peanuts.items[0].reference_grams == Decimal("50")
    assert peanuts.items[0].min_grams <= Decimal("50") <= peanuts.items[0].max_grams
    post_workout = next(meal for meal in seeded if meal.code == "PW01")
    assert {item.food.slug for item in post_workout.items} == {"egg", "potato"}
    assert all(
        item.food.slug == "sangak-bread"
        for meal in seeded
        for item in meal.items
        if item.food.category == "bread"
    )
    assert {
        meal.code for meal in seeded if any(item.food.category == "bread" for item in meal.items)
    } == {
        "BF01",
        "BF02",
        "BF03",
        "BF04",
        "BF05",
        "BF06",
        "BF07",
        "LU11",
        "DN02",
        "DN05",
        "DN06",
        "DN07",
        "SN02",
        "SN07",
    }


def test_admin_lists_and_updates_meals_with_bounded_ingredients(
    client: TestClient,
    db: Session,
) -> None:
    from app.nutrition.food_catalogue import seed_base_iranian_food_catalogue
    from app.nutrition.meal_catalogue import seed_meal_catalogue
    from app.nutrition.models import NutritionCatalogueFood

    seed_base_iranian_food_catalogue(db)
    _add_required_imported_foods(db)
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
    assert len(listed.json()["items"]) == 8
    breakfast = next(item for item in listed.json()["items"] if item["code"] == "BF02")
    meal_id = breakfast["id"]

    updated = client.put(
        f"/api/v1/nutrition/admin/meals/{meal_id}",
        headers=ORIGIN,
        json={
            "code": "BF02",
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
            "code": "BF99",
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


def test_admin_rejects_duplicate_or_changed_meal_codes(
    client: TestClient,
    db: Session,
) -> None:
    from app.nutrition.food_catalogue import seed_base_iranian_food_catalogue
    from app.nutrition.meal_catalogue import seed_meal_catalogue
    from app.nutrition.models import NutritionCatalogueFood

    seed_base_iranian_food_catalogue(db)
    _add_required_imported_foods(db)
    seed_meal_catalogue(db)
    _register_admin(client, db)
    egg = db.scalar(select(NutritionCatalogueFood).where(NutritionCatalogueFood.slug == "egg"))
    assert egg is not None
    payload = {
        "code": "CUS01",
        "name_fa": "وعده سفارشی",
        "name_en": "Custom meal",
        "category": "snack",
        "verification_status": "verified",
        "items": [
            {
                "food_id": str(egg.id),
                "reference_grams": 50,
                "min_grams": 50,
                "max_grams": 100,
                "is_required": True,
                "functional_role": "protein",
            }
        ],
    }

    created = client.post("/api/v1/nutrition/admin/meals", headers=ORIGIN, json=payload)

    assert created.status_code == 201, created.json()
    assert created.json()["code"] == "CUS01"
    duplicate = client.post("/api/v1/nutrition/admin/meals", headers=ORIGIN, json=payload)
    assert duplicate.status_code == 422
    changed = client.put(
        f"/api/v1/nutrition/admin/meals/{created.json()['id']}",
        headers=ORIGIN,
        json={**payload, "code": "CUS02"},
    )
    assert changed.status_code == 422


def test_meal_catalogue_requires_admin_access(client: TestClient) -> None:
    assert client.get("/api/v1/nutrition/admin/meals").status_code == 401
