from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session


def test_import_rejects_an_unsupported_quantity_unit() -> None:
    from app.nutrition.food_catalogue import FoodImportValidationError, normalize_food_import

    with pytest.raises(FoodImportValidationError, match="Unsupported quantity unit"):
        normalize_food_import(
            {
                "slug": "test-food",
                "name_fa": "غذای تست",
                "name_en": "Test food",
                "quantity": "1",
                "quantity_unit": "cup",
                "nutrients": [],
            }
        )


def test_meal_totals_keep_missing_nutrients_unavailable() -> None:
    from app.nutrition.food_catalogue import FoodCompositionValue, calculate_meal_totals

    totals = calculate_meal_totals(
        [
            (
                Decimal("150"),
                [
                    FoodCompositionValue("energy_kcal", Decimal("120"), "kcal"),
                    FoodCompositionValue("protein_g", Decimal("8"), "g"),
                ],
            )
        ]
    )

    assert totals["energy_kcal"] == Decimal("180")
    assert totals["protein_g"] == Decimal("12")
    assert totals["sodium_mg"] is None


def test_main_meal_requires_a_substantial_main_food() -> None:
    from app.nutrition.food_catalogue import FoodRole, validate_meal_roles

    with pytest.raises(ValueError, match="main eligible"):
        validate_meal_roles("main_meal", [FoodRole.SNACK])


def test_verified_iranian_seed_foods_have_provenance_and_explicit_basis(db: Session) -> None:
    from app.nutrition.models import NutritionCatalogueFood

    foods = db.scalars(
        select(NutritionCatalogueFood).where(
            NutritionCatalogueFood.verification_status == "verified"
        )
    ).all()

    assert {food.slug for food in foods} >= {
        "basmati-rice",
        "chicken-breast",
        "plain-yogurt",
    }
    assert "cooked-basmati-rice" not in {food.slug for food in foods}
    assert "grilled-chicken-breast" not in {food.slug for food in foods}
    assert all(food.source_reference for food in foods)
    assert all(food.measurement_basis.value in {"raw", "dry", "as_purchased"} for food in foods)
    assert all(food.canonical_quantity == Decimal("100") for food in foods)
    assert all(food.canonical_unit == "g" for food in foods)


def test_base_catalogue_seed_contains_user_approved_iranian_ingredients(db: Session) -> None:
    from app.nutrition.food_catalogue import seed_base_iranian_food_catalogue
    from app.nutrition.models import NutritionCatalogueFood

    seed_base_iranian_food_catalogue(db)

    foods = db.scalars(select(NutritionCatalogueFood)).all()
    assert {food.slug for food in foods} >= {
        "chicken-breast",
        "beef",
        "lentils",
        "basmati-rice",
        "tomato",
        "apple",
        "olive-oil",
    }
    approved = [food for food in foods if food.slug in {"chicken-breast", "beef", "lentils"}]
    assert all(food.verification_status.value == "verified" for food in approved)


def test_approved_catalogue_keeps_identity_aliases_and_composition_separate(db: Session) -> None:
    from app.nutrition.food_catalogue import seed_base_iranian_food_catalogue
    from app.nutrition.models import (
        NutritionCatalogueFood,
        NutritionCatalogueFoodAlias,
        NutritionFoodComposition,
    )

    seed_base_iranian_food_catalogue(db)

    chicken = db.scalar(
        select(NutritionCatalogueFood).where(NutritionCatalogueFood.slug == "chicken-breast")
    )
    assert chicken is not None
    assert chicken.measurement_basis.value == "raw"
    assert chicken.source_food_id == "171077"
    assert (
        db.scalar(
            select(NutritionCatalogueFoodAlias).where(
                NutritionCatalogueFoodAlias.food_id == chicken.id,
                NutritionCatalogueFoodAlias.normalized_alias == "فیله مرغ",
            )
        )
        is not None
    )
    compositions = db.scalars(
        select(NutritionFoodComposition).where(NutritionFoodComposition.food_id == chicken.id)
    ).all()
    values = {row.nutrient_code: row.value_per_100g for row in compositions}
    assert values["energy_kcal"] == Decimal("120")
    assert values["protein_g"] == Decimal("22.5")
    assert "added_sugars_g" not in values


def test_approved_catalogue_has_all_65_identities_and_only_sourced_rows_are_verified(
    db: Session,
) -> None:
    from app.nutrition.food_catalogue import seed_base_iranian_food_catalogue
    from app.nutrition.models import NutritionCatalogueFood

    seed_base_iranian_food_catalogue(db)

    foods = db.scalars(select(NutritionCatalogueFood)).all()
    current = [food for food in foods if food.verification_status.value != "retired"]
    assert len(current) == 65
    statuses = {food.slug: food.verification_status.value for food in current}
    assert statuses["sangak-bread"] == "draft"
    assert statuses["barbari-bread"] == "draft"
    assert statuses["lavash-bread"] == "draft"
    assert statuses["taftoon-bread"] == "draft"
    assert statuses["chicken-breast"] == "verified"


def test_prepared_meals_remain_a_distinct_table() -> None:
    from app.nutrition.models import NutritionCatalogueFood, NutritionCatalogueMeal

    assert NutritionCatalogueFood.__tablename__ == "nutrition_catalogue_foods"
    assert NutritionCatalogueMeal.__tablename__ == "nutrition_catalogue_meals"
