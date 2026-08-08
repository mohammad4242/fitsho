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


def test_verified_iranian_seed_foods_have_provenance(db: Session) -> None:
    from app.nutrition.models import NutritionCatalogueFood

    foods = db.scalars(
        select(NutritionCatalogueFood).where(
            NutritionCatalogueFood.verification_status == "verified"
        )
    ).all()

    assert {food.slug for food in foods} >= {
        "cooked-basmati-rice",
        "grilled-chicken-breast",
        "plain-yogurt",
    }
    assert all(food.source_reference for food in foods)
