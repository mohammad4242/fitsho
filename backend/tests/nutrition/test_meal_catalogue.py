from decimal import Decimal
from uuid import UUID

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth.models import User
from app.config import Settings

ORIGIN = {"Origin": "http://localhost:5173"}
PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32


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
    from app.nutrition.enums import FoodVerificationStatus, MealCalculationMode, MealCategory
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
    assert {
        meal.code for meal in seeded if meal.calculation_mode is MealCalculationMode.PREPARED_RECIPE
    } == {"LU07", "LU08", "LU11"}
    assert all(
        meal.calculation_mode is MealCalculationMode.SIMPLE
        for meal in seeded
        if meal.code not in {"LU07", "LU08", "LU11"}
    )
    expected_prepared_recipe_yields = {
        "LU07": (Decimal("315"), Decimal("456.75"), Decimal("1.45")),
        "LU08": (Decimal("335"), Decimal("485.75"), Decimal("1.45")),
        "LU11": (Decimal("370"), Decimal("740"), Decimal("2.00")),
    }
    for code, (
        reference_input,
        cooked_yield,
        yield_factor,
    ) in expected_prepared_recipe_yields.items():
        meal = next(item for item in seeded if item.code == code)
        assert meal.prepared_recipe is not None
        revision = meal.prepared_recipe.revisions[-1]
        assert revision.verification_status is FoodVerificationStatus.DRAFT
        assert revision.reference_input_grams == reference_input
        assert revision.final_cooked_yield_grams == cooked_yield
        assert revision.final_cooked_yield_grams / revision.reference_input_grams == yield_factor
        assert revision.ratios
        assert revision.data_gaps
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
    ghormeh = next(meal for meal in seeded if meal.code == "LU07")
    assert {item.food.slug for item in ghormeh.items} == {"basmati-rice"}
    assert "ground-beef" not in {
        ingredient.food.slug for ingredient in ghormeh.prepared_recipe.revisions[-1].ingredients
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
    assert breakfast["image_url"] is None
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


def test_admin_uploads_and_replaces_meal_catalogue_image(
    client: TestClient,
    db: Session,
    test_settings: Settings,
) -> None:
    from app.nutrition.food_catalogue import seed_base_iranian_food_catalogue
    from app.nutrition.meal_catalogue import seed_meal_catalogue
    from app.nutrition.models import NutritionCatalogueMeal

    seed_base_iranian_food_catalogue(db)
    _add_required_imported_foods(db)
    seed_meal_catalogue(db)
    _register_admin(client, db)
    meal = db.scalar(select(NutritionCatalogueMeal).where(NutritionCatalogueMeal.code == "LU01"))
    assert meal is not None

    first = client.post(
        f"/api/v1/nutrition/admin/meals/{meal.id}/image",
        headers=ORIGIN,
        files={"file": ("meal.png", PNG_BYTES, "image/png")},
    )

    assert first.status_code == 200
    first_url = first.json()["image_url"]
    assert first_url.startswith("/media/meal-catalogue/")
    first_path = test_settings.media_root / first_url.removeprefix("/media/")
    assert first_path.read_bytes() == PNG_BYTES

    second = client.post(
        f"/api/v1/nutrition/admin/meals/{meal.id}/image",
        headers=ORIGIN,
        files={"file": ("replacement.png", PNG_BYTES + b"replacement", "image/png")},
    )

    assert second.status_code == 200
    assert second.json()["image_url"] != first_url
    assert not first_path.exists()
    listed = client.get("/api/v1/nutrition/admin/meals?category=lunch").json()["items"]
    saved_meal = next(item for item in listed if item["id"] == str(meal.id))
    assert saved_meal["image_url"] == second.json()["image_url"]


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


def _prepared_recipe_payload(*, egg_id: str, tomato_id: str, bread_id: str) -> dict[str, object]:
    return {
        "code": "CUS02",
        "name_fa": "خوراک پخته آزمایشی با نان",
        "name_en": "Test prepared dish with bread",
        "category": "lunch",
        "verification_status": "draft",
        "calculation_mode": "prepared_recipe",
        "items": [
            {
                "food_id": bread_id,
                "reference_grams": 60,
                "min_grams": 30,
                "max_grams": 120,
                "is_required": True,
                "functional_role": "carbohydrate",
            }
        ],
        "prepared_recipe": {
            "verification_status": "draft",
            "source_name": "Measured test kitchen batch",
            "source_reference": "https://example.test/recipe-batch-1",
            "notes": "Test-only measured batch",
            "cooked_yield": {
                "method": "proportional_reference_batch",
                "final_cooked_yield_grams": 300,
                "source_name": "Measured test kitchen batch",
                "source_reference": "https://example.test/recipe-batch-1",
                "notes": "Final mass measured after cooking",
            },
            "ingredients": [
                {
                    "food_id": egg_id,
                    "reference_grams": 100,
                    "min_grams": 80,
                    "max_grams": 120,
                    "is_required": True,
                },
                {
                    "food_id": tomato_id,
                    "reference_grams": 50,
                    "min_grams": 40,
                    "max_grams": 60,
                    "is_required": True,
                },
            ],
            "ratios": [
                {
                    "numerator_food_id": egg_id,
                    "denominator_food_id": tomato_id,
                    "min_ratio": 1.5,
                    "max_ratio": 2.5,
                }
            ],
            "data_gaps": [],
        },
    }


def test_admin_switches_modes_and_creates_immutable_recipe_revisions(
    client: TestClient,
    db: Session,
) -> None:
    from app.nutrition.food_catalogue import seed_base_iranian_food_catalogue
    from app.nutrition.models import (
        NutritionCatalogueFood,
        NutritionPreparedRecipeRevision,
    )

    seed_base_iranian_food_catalogue(db)
    _register_admin(client, db)
    foods = {
        food.slug: food
        for food in db.scalars(
            select(NutritionCatalogueFood).where(
                NutritionCatalogueFood.slug.in_(("egg", "tomato", "sangak-bread"))
            )
        )
    }
    payload = _prepared_recipe_payload(
        egg_id=str(foods["egg"].id),
        tomato_id=str(foods["tomato"].id),
        bread_id=str(foods["sangak-bread"].id),
    )

    created = client.post("/api/v1/nutrition/admin/meals", headers=ORIGIN, json=payload)

    assert created.status_code == 201, created.json()
    body = created.json()
    assert body["calculation_mode"] == "prepared_recipe"
    assert body["prepared_recipe"]["version"] == 1
    assert body["prepared_recipe"]["calculation_version"] == "prepared-recipe-v1"
    assert body["prepared_recipe"]["preview"]["nutrients_per_100g"]["energy_kcal"] > 0
    assert body["prepared_recipe"]["preview"]["final_cooked_yield_grams"] == 300

    changed_payload = {
        **payload,
        "prepared_recipe": {
            **payload["prepared_recipe"],  # type: ignore[dict-item]
            "ingredients": [
                {
                    **payload["prepared_recipe"]["ingredients"][0],  # type: ignore[index]
                    "reference_grams": 110,
                    "max_grams": 130,
                },
                payload["prepared_recipe"]["ingredients"][1],  # type: ignore[index]
            ],
        },
    }
    updated = client.put(
        f"/api/v1/nutrition/admin/meals/{body['id']}", headers=ORIGIN, json=changed_payload
    )

    assert updated.status_code == 200, updated.json()
    assert updated.json()["prepared_recipe"]["version"] == 2
    from app.nutrition.models import NutritionPreparedRecipe

    assert (
        db.scalar(
            select(func.count())
            .select_from(NutritionPreparedRecipeRevision)
            .join(
                NutritionPreparedRecipe,
                NutritionPreparedRecipeRevision.recipe_id == NutritionPreparedRecipe.id,
            )
            .where(NutritionPreparedRecipe.meal_id == UUID(body["id"]))
        )
        == 2
    )

    simple_payload = {
        key: value
        for key, value in payload.items()
        if key not in {"prepared_recipe", "calculation_mode"}
    }
    simple_payload["calculation_mode"] = "simple"
    switched_back = client.put(
        f"/api/v1/nutrition/admin/meals/{body['id']}", headers=ORIGIN, json=simple_payload
    )

    assert switched_back.status_code == 200, switched_back.json()
    assert switched_back.json()["calculation_mode"] == "simple"
    assert switched_back.json()["prepared_recipe"] is None
    assert (
        db.scalar(
            select(func.count())
            .select_from(NutritionPreparedRecipeRevision)
            .join(
                NutritionPreparedRecipe,
                NutritionPreparedRecipeRevision.recipe_id == NutritionPreparedRecipe.id,
            )
            .where(NutritionPreparedRecipe.meal_id == UUID(body["id"]))
        )
        == 2
    )


def test_recipe_data_gap_is_visible_and_prevents_verification(
    client: TestClient,
    db: Session,
) -> None:
    from app.nutrition.food_catalogue import seed_base_iranian_food_catalogue
    from app.nutrition.models import NutritionCatalogueFood

    seed_base_iranian_food_catalogue(db)
    _register_admin(client, db)
    foods = {
        food.slug: food
        for food in db.scalars(
            select(NutritionCatalogueFood).where(
                NutritionCatalogueFood.slug.in_(("egg", "tomato", "sangak-bread"))
            )
        )
    }
    payload = _prepared_recipe_payload(
        egg_id=str(foods["egg"].id),
        tomato_id=str(foods["tomato"].id),
        bread_id=str(foods["sangak-bread"].id),
    )
    payload["prepared_recipe"]["data_gaps"] = [  # type: ignore[index]
        {
            "ingredient_name_fa": "پیاز",
            "ingredient_name_en": "Onion",
            "message_fa": "پیاز در کاتالوگ مواد غذایی وجود ندارد",
            "message_en": "Onion does not exist in Food Catalogue",
        }
    ]

    draft = client.post("/api/v1/nutrition/admin/meals", headers=ORIGIN, json=payload)

    assert draft.status_code == 201, draft.json()
    assert draft.json()["prepared_recipe"]["data_gaps"][0]["message_fa"] == (
        "پیاز در کاتالوگ مواد غذایی وجود ندارد"
    )
    verified_payload = {
        **payload,
        "verification_status": "verified",
        "prepared_recipe": {
            **payload["prepared_recipe"],  # type: ignore[dict-item]
            "verification_status": "verified",
        },
    }
    rejected = client.put(
        f"/api/v1/nutrition/admin/meals/{draft.json()['id']}",
        headers=ORIGIN,
        json=verified_payload,
    )

    assert rejected.status_code == 422
    assert "data gaps" in rejected.json()["detail"]


def _register_member(
    client: TestClient,
    db: Session,
    email: str = "meal-member@example.com",
    is_admin: bool = False,
) -> User:
    response = client.post(
        "/api/v1/auth/register",
        headers=ORIGIN,
        json={"email": email, "password": "long password"},
    )
    assert response.status_code == 201
    user = db.scalar(select(User).where(User.email == email))
    assert user is not None
    user.is_admin = is_admin
    db.commit()
    return user


def test_member_meal_catalogue_requires_authentication(client: TestClient) -> None:
    response = client.get("/api/v1/nutrition/meal-catalogue")
    assert response.status_code == 401


def test_member_meal_catalogue_normal_member_access(client: TestClient, db: Session) -> None:
    from app.nutrition.food_catalogue import seed_base_iranian_food_catalogue
    from app.nutrition.meal_catalogue import seed_meal_catalogue
    from app.profile.enums import ProductMode
    from app.profile.models import UserProfile

    seed_base_iranian_food_catalogue(db)
    _add_required_imported_foods(db)
    seed_meal_catalogue(db)

    user = _register_member(client, db, email="training-only@example.com")
    db.add(UserProfile(user_id=user.id, product_mode=ProductMode.TRAINING))
    db.commit()

    response = client.get("/api/v1/nutrition/meal-catalogue")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "categories" in data
    assert len(data["items"]) > 0
    assert "breakfast" in data["categories"]


def test_member_meal_catalogue_category_filtering(client: TestClient, db: Session) -> None:
    from app.nutrition.food_catalogue import seed_base_iranian_food_catalogue
    from app.nutrition.meal_catalogue import seed_meal_catalogue

    seed_base_iranian_food_catalogue(db)
    _add_required_imported_foods(db)
    seed_meal_catalogue(db)
    _register_member(client, db, email="category-filter@example.com")

    response = client.get("/api/v1/nutrition/meal-catalogue?category=breakfast")
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) > 0
    assert all(item["category"] == "breakfast" for item in data["items"])


def test_draft_meal_excluded_from_member_and_safe_response_schema(
    client: TestClient, db: Session
) -> None:
    from app.nutrition.enums import FoodVerificationStatus, MealCategory
    from app.nutrition.food_catalogue import seed_base_iranian_food_catalogue
    from app.nutrition.meal_catalogue import seed_meal_catalogue
    from app.nutrition.models import NutritionCatalogueMeal

    seed_base_iranian_food_catalogue(db)
    _add_required_imported_foods(db)
    seed_meal_catalogue(db)

    draft_meal = NutritionCatalogueMeal(
        code="DRAFT01",
        name_fa="وعده پیش‌نویس اختصاصی",
        name_en="Draft Only Meal",
        category=MealCategory.BREAKFAST,
        verification_status=FoodVerificationStatus.DRAFT,
    )
    db.add(draft_meal)
    db.commit()

    _register_member(client, db, email="member-safe@example.com")
    member_resp = client.get("/api/v1/nutrition/meal-catalogue?category=breakfast")
    assert member_resp.status_code == 200
    member_data = member_resp.json()
    member_item_ids = {item["id"] for item in member_data["items"]}

    # Draft meal must NOT be returned to normal members
    assert str(draft_meal.id) not in member_item_ids

    # Verify member response item schema contains only safe public fields
    forbidden_fields = {
        "code",
        "verification_status",
        "calculation_mode",
        "items",
        "min_grams",
        "max_grams",
        "is_required",
        "functional_role",
        "prepared_recipe",
        "totals",
        "price",
        "prices",
        "estimated_cost_irr_per_100g",
        "price_reference_ids",
    }
    for item in member_data["items"]:
        assert set(item.keys()) == {"id", "name_fa", "name_en", "image_url", "category"}
        for field in forbidden_fields:
            assert field not in item

    # Verify admin can still view and manage the draft meal
    admin_client = TestClient(client.app, cookies=None)
    _register_admin(admin_client, db)
    admin_resp = admin_client.get("/api/v1/nutrition/admin/meals?category=breakfast")
    assert admin_resp.status_code == 200
    admin_data = admin_resp.json()
    admin_item_ids = {item["id"] for item in admin_data["items"]}
    assert str(draft_meal.id) in admin_item_ids


def test_admin_meals_still_denies_normal_member(client: TestClient, db: Session) -> None:
    _register_member(client, db, email="non-admin@example.com")
    resp_get = client.get("/api/v1/nutrition/admin/meals")
    assert resp_get.status_code == 403

    resp_post = client.post("/api/v1/nutrition/admin/meals", headers=ORIGIN, json={})
    assert resp_post.status_code == 403

