from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload


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
        "ground-beef",
        "beef-chuck-stew-meat",
        "lentils",
        "basmati-rice",
        "tomato",
        "apple",
        "olive-oil",
    }
    approved = [food for food in foods if food.slug in {"chicken-breast", "ground-beef", "lentils"}]
    assert all(food.verification_status.value == "verified" for food in approved)


def test_base_seed_contains_exact_requested_source_backed_foods(db: Session) -> None:
    from app.nutrition.food_catalogue import seed_base_iranian_food_catalogue
    from app.nutrition.models import NutritionCatalogueFood

    first = seed_base_iranian_food_catalogue(db, commit=False)
    second = seed_base_iranian_food_catalogue(db, commit=False)

    requested = {
        food.slug: food
        for food in db.scalars(
            select(NutritionCatalogueFood).where(
                NutritionCatalogueFood.slug.in_(
                    {
                        "beef-chuck-stew-meat",
                        "creamy-peanut-butter",
                        "tomato-paste",
                        "green-beans",
                        "barberries",
                        "wheat-flour",
                        "mozzarella",
                        "ground-beef",
                    }
                )
            )
        )
    }
    assert len(first) == len(second) == 72
    assert set(requested) == {
        "creamy-peanut-butter",
        "tomato-paste",
        "green-beans",
        "barberries",
        "wheat-flour",
        "mozzarella",
        "ground-beef",
        "beef-chuck-stew-meat",
    }
    assert all(food.verification_status.value == "verified" for food in requested.values())
    assert {food.source_food_id for food in requested.values()} == {
        "2262072",
        "2685580",
        "2346400",
        "0945",
        "790018",
        "170846",
        "174030",
        "2646174",
    }
    assert {food.slug: food.measurement_basis.value for food in requested.values()} == {
        "creamy-peanut-butter": "as_purchased",
        "tomato-paste": "as_purchased",
        "green-beans": "raw",
        "barberries": "dry",
        "wheat-flour": "dry",
        "mozzarella": "as_purchased",
        "ground-beef": "raw",
        "beef-chuck-stew-meat": "raw",
    }
    assert requested["ground-beef"].name_fa == "گوشت چرخ‌کرده گوساله (۱۰٪ چربی)"
    assert requested["ground-beef"].name_en == "Ground beef, 90% lean / 10% fat"
    assert requested["ground-beef"].dietary_patterns == ["omnivore"]
    assert requested["beef-chuck-stew-meat"].name_en == "Beef chuck stew meat"
    assert requested["beef-chuck-stew-meat"].source_food_id == "2646174"
    assert requested["beef-chuck-stew-meat"].dietary_patterns == ["omnivore"]
    assert requested["mozzarella"].dietary_patterns == ["omnivore", "vegetarian"]
    assert requested["mozzarella"].aliases
    assert {alias.alias for alias in requested["mozzarella"].aliases} >= {
        "پنیر موزارلا",
        "پنیر پیتزا",
    }
    assert (
        db.scalar(select(NutritionCatalogueFood).where(NutritionCatalogueFood.slug == "beef"))
        is None
    )


def test_requested_foods_have_complete_primaries_and_composition_provenance(
    db: Session,
) -> None:
    from app.nutrition.food_catalogue import (
        REQUIRED_PRIMARY_NUTRIENTS,
        seed_base_iranian_food_catalogue,
    )
    from app.nutrition.models import NutritionCatalogueFood

    seed_base_iranian_food_catalogue(db)
    slugs = {
        "creamy-peanut-butter",
        "tomato-paste",
        "green-beans",
        "barberries",
        "wheat-flour",
        "mozzarella",
        "ground-beef",
    }
    foods = db.scalars(
        select(NutritionCatalogueFood).where(NutritionCatalogueFood.slug.in_(slugs))
    ).all()

    assert len(foods) == 7
    for food in foods:
        codes = {composition.nutrient_code for composition in food.compositions}
        assert codes >= REQUIRED_PRIMARY_NUTRIENTS
        assert food.verification_status.value == "verified"
        assert food.source_name
        assert food.source_reference.startswith("https://")
        assert food.data_version
        assert food.source_access_date is not None
        assert all(composition.source_name for composition in food.compositions)
        assert all(
            composition.source_reference.startswith("https://") for composition in food.compositions
        )
        assert all(
            composition.source_food_id == food.source_food_id for composition in food.compositions
        )
        assert all(composition.data_version for composition in food.compositions)
        assert all(composition.source_access_date is not None for composition in food.compositions)
        assert all(composition.confidence.value == "high" for composition in food.compositions)


def test_requested_foods_keep_unavailable_micronutrients_absent(db: Session) -> None:
    from app.nutrition.food_catalogue import seed_base_iranian_food_catalogue
    from app.nutrition.models import NutritionCatalogueFood

    seed_base_iranian_food_catalogue(db)
    barberries = db.scalar(
        select(NutritionCatalogueFood).where(NutritionCatalogueFood.slug == "barberries")
    )
    peanut_butter = db.scalar(
        select(NutritionCatalogueFood).where(NutritionCatalogueFood.slug == "creamy-peanut-butter")
    )

    assert barberries is not None
    assert peanut_butter is not None
    barberry_values = {
        composition.nutrient_code: composition.value_per_100g
        for composition in barberries.compositions
    }
    peanut_values = {
        composition.nutrient_code: composition.value_per_100g
        for composition in peanut_butter.compositions
    }
    assert barberry_values == {
        "energy_kcal": Decimal("334"),
        "protein_g": Decimal("4.2"),
        "carbohydrate_g": Decimal("80.6"),
        "total_fat_g": Decimal("2"),
        "fibre_g": Decimal("11.5"),
        "total_sugars_g": Decimal("48.2"),
        "saturated_fat_g": Decimal("0.48"),
        "sodium_mg": Decimal("12"),
    }
    assert "total_sugars_g" not in peanut_values


def test_seed_keeps_food_draft_when_a_required_primary_is_unavailable(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.nutrition import food_catalogue
    from app.nutrition.catalogue_seed_data import FoodCompositionSeed, composition_seeds_for
    from app.nutrition.models import NutritionCatalogueFood

    def without_fibre(slug: str) -> tuple[FoodCompositionSeed, ...]:
        compositions = composition_seeds_for(slug)
        if slug == "barberries":
            return tuple(row for row in compositions if row.nutrient_code != "fibre_g")
        return compositions

    monkeypatch.setattr(food_catalogue, "composition_seeds_for", without_fibre)
    food_catalogue.seed_base_iranian_food_catalogue(db)

    barberries = db.scalar(
        select(NutritionCatalogueFood).where(NutritionCatalogueFood.slug == "barberries")
    )
    assert barberries is not None
    assert barberries.verification_status.value == "draft"


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


def test_approved_catalogue_has_all_72_identities_and_source_backed_breads_are_verified(
    db: Session,
) -> None:
    from app.nutrition.food_catalogue import seed_base_iranian_food_catalogue
    from app.nutrition.models import NutritionCatalogueFood

    seed_base_iranian_food_catalogue(db)

    foods = db.scalars(select(NutritionCatalogueFood)).all()
    current = [food for food in foods if food.verification_status.value != "retired"]
    assert len(current) == 72
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


def test_base_catalogue_seed_does_not_resurrect_retired_food(db: Session) -> None:
    from app.nutrition.enums import FoodVerificationStatus
    from app.nutrition.food_catalogue import seed_base_iranian_food_catalogue
    from app.nutrition.models import NutritionCatalogueFood

    food = db.scalar(
        select(NutritionCatalogueFood)
        .where(NutritionCatalogueFood.slug == "chicken-breast")
        .options(
            selectinload(NutritionCatalogueFood.roles),
            selectinload(NutritionCatalogueFood.aliases),
            selectinload(NutritionCatalogueFood.compositions),
            selectinload(NutritionCatalogueFood.portions),
        )
    )
    assert food is not None
    original_id = food.id
    original_role_ids = {(role.food_id, role.role) for role in food.roles}
    original_alias_ids = {alias.id for alias in food.aliases}
    original_composition_ids = {composition.id for composition in food.compositions}
    original_portion_ids = {portion.id for portion in food.portions}

    food.verification_status = FoodVerificationStatus.RETIRED
    db.commit()

    seeded = seed_base_iranian_food_catalogue(db)
    db.expire_all()
    preserved = db.scalar(
        select(NutritionCatalogueFood)
        .where(NutritionCatalogueFood.slug == "chicken-breast")
        .options(
            selectinload(NutritionCatalogueFood.roles),
            selectinload(NutritionCatalogueFood.aliases),
            selectinload(NutritionCatalogueFood.compositions),
            selectinload(NutritionCatalogueFood.portions),
        )
    )

    assert len(seeded) == 72
    assert preserved is not None
    assert preserved.id == original_id
    assert preserved.verification_status is FoodVerificationStatus.RETIRED
    assert {(role.food_id, role.role) for role in preserved.roles} == original_role_ids
    assert {alias.id for alias in preserved.aliases} == original_alias_ids
    assert {composition.id for composition in preserved.compositions} == original_composition_ids
    assert {portion.id for portion in preserved.portions} == original_portion_ids
