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


def test_portion_scaling_keeps_the_canonical_100g_values_immutable() -> None:
    from app.nutrition.food_catalogue import scale_nutrient_value_for_grams

    assert scale_nutrient_value_for_grams(Decimal("12.56"), Decimal("50")) == Decimal("6.28")


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


def test_approved_catalogue_has_all_65_identities_and_source_backed_breads_are_verified(
    db: Session,
) -> None:
    from app.nutrition.food_catalogue import seed_base_iranian_food_catalogue
    from app.nutrition.models import NutritionCatalogueFood

    seed_base_iranian_food_catalogue(db)

    foods = db.scalars(select(NutritionCatalogueFood)).all()
    current = [food for food in foods if food.verification_status.value != "retired"]
    assert len(current) == 65
    statuses = {food.slug: food.verification_status.value for food in current}
    assert statuses["sangak-bread"] == "verified"
    assert statuses["barbari-bread"] == "verified"
    assert statuses["lavash-bread"] == "verified"
    assert statuses["taftoon-bread"] == "verified"
    assert statuses["chicken-breast"] == "verified"


def test_iranian_breads_have_literal_source_backed_nutrients_and_palm_portions(
    db: Session,
) -> None:
    from app.nutrition.food_catalogue import seed_base_iranian_food_catalogue
    from app.nutrition.models import NutritionCatalogueFood

    seed_base_iranian_food_catalogue(db)

    expected = {
        "sangak-bread": {
            "energy_kcal": Decimal("258"),
            "protein_g": Decimal("7.7"),
            "carbohydrate_g": Decimal("57.4"),
            "total_fat_g": Decimal("0.7"),
            "fibre_g": Decimal("4.1"),
            "total_sugars_g": Decimal("1.5"),
            "potassium_mg": Decimal("110"),
            "zinc_mg": Decimal("1.66"),
            "copper_mg": Decimal("0.3445"),
            "calcium_mg": Decimal("80.05"),
        },
        "barbari-bread": {
            "energy_kcal": Decimal("272"),
            "protein_g": Decimal("8.4"),
            "carbohydrate_g": Decimal("59.5"),
            "total_fat_g": Decimal("0.6"),
            "fibre_g": Decimal("2.2"),
            "total_sugars_g": Decimal("0.8"),
            "potassium_mg": Decimal("112"),
            "zinc_mg": Decimal("0.884"),
            "copper_mg": Decimal("0.218"),
        },
        "taftoon-bread": {
            "energy_kcal": Decimal("279"),
            "protein_g": Decimal("8.1"),
            "carbohydrate_g": Decimal("61.1"),
            "total_fat_g": Decimal("0.7"),
            "fibre_g": Decimal("2.2"),
            "total_sugars_g": Decimal("0.8"),
            "potassium_mg": Decimal("106"),
            "zinc_mg": Decimal("1.35"),
            "copper_mg": Decimal("0.289"),
        },
        "lavash-bread": {
            "energy_kcal": Decimal("291"),
            "protein_g": Decimal("8.8"),
            "carbohydrate_g": Decimal("63.4"),
            "total_fat_g": Decimal("0.8"),
            "fibre_g": Decimal("2.4"),
            "total_sugars_g": Decimal("0.8"),
            "potassium_mg": Decimal("103"),
            "zinc_mg": Decimal("0.561"),
            "copper_mg": Decimal("0.2805"),
        },
    }
    palm_grams = {
        "sangak-bread": Decimal("30"),
        "barbari-bread": Decimal("30"),
        "taftoon-bread": Decimal("30"),
        "lavash-bread": Decimal("7.5"),
    }

    foods = db.scalars(
        select(NutritionCatalogueFood).where(NutritionCatalogueFood.slug.in_(expected))
    ).all()
    assert len(foods) == 4
    for food in foods:
        values = {row.nutrient_code: row.value_per_100g for row in food.compositions}
        assert values == expected[food.slug]
        assert all(row.source_reference.startswith("https://doi.org/") for row in food.compositions)
        assert "iron_mg" not in values
        assert len(food.portions) == 1
        assert food.portions[0].code == "palm"
        assert food.portions[0].grams == palm_grams[food.slug]
        assert food.portions[0].is_default is True


def test_prepared_meals_remain_a_distinct_table() -> None:
    from app.nutrition.models import NutritionCatalogueFood, NutritionCatalogueMeal

    assert NutritionCatalogueFood.__tablename__ == "nutrition_catalogue_foods"
    assert NutritionCatalogueMeal.__tablename__ == "nutrition_catalogue_meals"


def test_seeded_egg_has_a_default_documented_portion(db: Session) -> None:
    from app.nutrition.models import NutritionCatalogueFood

    egg = db.scalar(select(NutritionCatalogueFood).where(NutritionCatalogueFood.slug == "egg"))

    assert egg is not None
    assert len(egg.portions) == 1
    portion = egg.portions[0]
    assert portion.code == "piece"
    assert portion.grams == Decimal("50")
    assert portion.is_default is True
    assert portion.source_reference
