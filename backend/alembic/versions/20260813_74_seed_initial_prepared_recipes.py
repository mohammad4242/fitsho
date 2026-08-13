"""seed initial draft Prepared Recipes"""

import json
from collections.abc import Sequence
from datetime import date
from decimal import Decimal
from uuid import NAMESPACE_URL, uuid5

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert

from alembic import op

revision: str = "20260813_74"
down_revision: str | Sequence[str] | None = "20260813_73"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_FOOD_SLUG = "beef-chuck-stew-meat"
_NUTRIENT_UNITS = {
    "energy_kcal": "kcal",
    "protein_g": "g",
    "carbohydrate_g": "g",
    "total_fat_g": "g",
    "fibre_g": "g",
    "saturated_fat_g": "g",
    "sodium_mg": "mg",
    "calcium_mg": "mg",
    "potassium_mg": "mg",
    "magnesium_mg": "mg",
    "iron_mg": "mg",
    "zinc_mg": "mg",
    "copper_mg": "mg",
}
_FOOD_VALUES = {
    "energy_kcal": "231.71",
    "protein_g": "18.40",
    "carbohydrate_g": "0",
    "total_fat_g": "17.80",
    "fibre_g": "0",
    "saturated_fat_g": "6.34",
    "sodium_mg": "48.4",
    "calcium_mg": "4.58",
    "potassium_mg": "281",
    "magnesium_mg": "17",
    "iron_mg": "2.06",
    "zinc_mg": "5.39",
    "copper_mg": "0.054",
}
_RECIPES: dict[str, dict[str, object]] = {
    "LU07": {
        "name_fa": "قورمه‌سبزی",
        "name_en": "Ghormeh sabzi",
        "final_cooked_yield_grams": "400",
        "ingredients": (
            ("beef-chuck-stew-meat", "120", "80", "200", True),
            ("red-kidney-beans", "40", "25", "70", True),
            ("mixed-herbs", "120", "70", "200", True),
            ("onion", "30", "15", "60", True),
            ("vegetable-oil", "5", "2", "10", False),
        ),
        "ratios": (("beef-chuck-stew-meat", "red-kidney-beans", "1.5", "5"),),
        "gap_fa": "وزن نهایی پخته و ترکیب دقیق سبزی قورمه تخمینی است و منبع اندازه‌گیری‌شده ندارد",
        "gap_en": (
            "Final cooked yield and the exact Ghormeh herb blend are estimates "
            "without a measured source"
        ),
    },
    "LU08": {
        "name_fa": "قیمه",
        "name_en": "Gheimeh",
        "final_cooked_yield_grams": "425",
        "ingredients": (
            ("beef-chuck-stew-meat", "120", "80", "200", True),
            ("split-peas", "45", "25", "75", True),
            ("tomato-paste", "35", "15", "65", True),
            ("potato", "100", "50", "180", False),
            ("onion", "30", "15", "60", True),
            ("vegetable-oil", "5", "2", "10", False),
        ),
        "ratios": (("beef-chuck-stew-meat", "split-peas", "1.5", "4"),),
        "gap_fa": "وزن نهایی پخته تخمینی است و منبع اندازه‌گیری‌شده ندارد",
        "gap_en": "Final cooked yield is an estimate without a measured source",
    },
    "LU11": {
        "name_fa": "آبگوشت",
        "name_en": "Abgoosht",
        "final_cooked_yield_grams": "520",
        "ingredients": (
            ("lamb", "120", "80", "200", True),
            ("chickpeas", "35", "20", "60", True),
            ("white-beans", "35", "20", "60", True),
            ("potato", "120", "70", "220", True),
            ("tomato-paste", "30", "15", "60", True),
            ("onion", "30", "15", "60", True),
        ),
        "ratios": (
            ("lamb", "chickpeas", "2", "6"),
            ("chickpeas", "white-beans", "0.5", "2"),
        ),
        "gap_fa": "وزن نهایی پخته و مقدار آب باقی‌مانده تخمینی است و منبع اندازه‌گیری‌شده ندارد",
        "gap_en": "Final cooked yield and retained broth are estimates without a measured source",
    },
}


def upgrade() -> None:
    connection = op.get_bind()
    _seed_stew_beef(connection)
    for code, recipe_seed in _RECIPES.items():
        _seed_recipe(connection, code, recipe_seed)


def downgrade() -> None:
    connection = op.get_bind()
    recipes = _table("nutrition_prepared_recipes", "id", "meal_id")
    meals = _table("nutrition_catalogue_meals", "id", "code", "calculation_mode")
    recipe_ids = [
        uuid5(NAMESPACE_URL, f"fitsho:nutrition:prepared-recipe:{code}") for code in _RECIPES
    ]
    connection.execute(recipes.delete().where(recipes.c.id.in_(recipe_ids)))
    connection.execute(
        meals.update().where(meals.c.code.in_(tuple(_RECIPES))).values(calculation_mode="simple")
    )


def _seed_stew_beef(connection: sa.Connection) -> None:
    foods = _table(
        "nutrition_catalogue_foods",
        "id",
        "slug",
        "name_fa",
        "name_en",
        "verification_status",
        "source_name",
        "source_reference",
        "source_food_id",
        "category",
        "measurement_basis",
        "canonical_quantity",
        "canonical_unit",
        "edible_portion",
        "data_version",
        "source_access_date",
        "dietary_patterns",
    )
    food_id = uuid5(NAMESPACE_URL, f"fitsho:nutrition:food:{_FOOD_SLUG}")
    connection.execute(
        insert(foods)
        .values(
            id=food_id,
            slug=_FOOD_SLUG,
            name_fa="گوشت خورشتی گوساله (سردست)",
            name_en="Beef chuck stew meat",
            verification_status="verified",
            source_name="USDA FoodData Central Foundation Foods",
            source_reference="https://fdc.nal.usda.gov/food-details/2646174/nutrients",
            source_food_id="2646174",
            category="red_meat",
            measurement_basis="raw",
            canonical_quantity=100,
            canonical_unit="g",
            edible_portion=1,
            data_version="fdc-2646174-published-2023-10-12",
            source_access_date=date(2026, 8, 13),
            dietary_patterns=json.dumps(["omnivore"]),
        )
        .on_conflict_do_nothing(index_elements=[foods.c.slug])
    )
    stored_id = connection.scalar(sa.select(foods.c.id).where(foods.c.slug == _FOOD_SLUG))
    assert stored_id is not None
    roles = _table("nutrition_catalogue_food_roles", "food_id", "role")
    connection.execute(
        insert(roles).values(food_id=stored_id, role="main_protein").on_conflict_do_nothing()
    )
    aliases = _table(
        "nutrition_catalogue_food_aliases",
        "id",
        "food_id",
        "alias",
        "normalized_alias",
        "language",
    )
    for alias in (
        "گوشت خورشتی گوساله (سردست)",
        "گوشت خورشتی گوساله",
        "گوشت تکه‌ای گوساله",
        "Beef chuck stew meat",
        "Beef chuck roast",
    ):
        normalized = _normalize(alias)
        connection.execute(
            insert(aliases)
            .values(
                id=uuid5(NAMESPACE_URL, f"fitsho:nutrition:food:{_FOOD_SLUG}:alias:{normalized}"),
                food_id=stored_id,
                alias=alias,
                normalized_alias=normalized,
                language="fa" if any("\u0600" <= char <= "\u06ff" for char in alias) else "en",
            )
            .on_conflict_do_nothing()
        )
    compositions = _table(
        "nutrition_food_compositions",
        "id",
        "food_id",
        "nutrient_code",
        "value_per_100g",
        "unit",
        "unit_form",
        "source_name",
        "source_reference",
        "source_food_id",
        "data_version",
        "source_access_date",
        "confidence",
    )
    for code, value in _FOOD_VALUES.items():
        connection.execute(
            insert(compositions)
            .values(
                id=uuid5(NAMESPACE_URL, f"fitsho:nutrition:food:{_FOOD_SLUG}:nutrient:{code}"),
                food_id=stored_id,
                nutrient_code=code,
                value_per_100g=Decimal(value),
                unit=_NUTRIENT_UNITS[code],
                unit_form="nutrient_mass",
                source_name="USDA FoodData Central Foundation Foods",
                source_reference="https://fdc.nal.usda.gov/food-details/2646174/nutrients",
                source_food_id="2646174",
                data_version="fdc-2646174-published-2023-10-12",
                source_access_date=date(2026, 8, 13),
                confidence="high",
            )
            .on_conflict_do_nothing()
        )


def _seed_recipe(connection: sa.Connection, code: str, seed: dict[str, object]) -> None:
    meals = _table(
        "nutrition_catalogue_meals", "id", "code", "calculation_mode", "verification_status"
    )
    foods = _table("nutrition_catalogue_foods", "id", "slug")
    meal_items = _table("nutrition_catalogue_meal_items", "meal_id", "food_id")
    recipes = _table("nutrition_prepared_recipes", "id", "meal_id")
    meal_id = connection.scalar(sa.select(meals.c.id).where(meals.c.code == code))
    if meal_id is None:
        return
    if connection.scalar(sa.select(recipes.c.id).where(recipes.c.meal_id == meal_id)) is not None:
        return
    ingredient_seeds = seed["ingredients"]
    ratio_seeds = seed["ratios"]
    assert isinstance(ingredient_seeds, tuple)
    assert isinstance(ratio_seeds, tuple)
    food_ids = {
        slug: connection.scalar(sa.select(foods.c.id).where(foods.c.slug == slug))
        for slug, *_ in ingredient_seeds
    }
    if any(food_id is None for food_id in food_ids.values()):
        missing = [slug for slug, food_id in food_ids.items() if food_id is None]
        raise RuntimeError(f"Prepared Recipe seed foods are missing: {', '.join(missing)}")
    side_slugs = {
        "LU07": ("basmati-rice",),
        "LU08": ("basmati-rice",),
        "LU11": ("sangak-bread", "mixed-herbs"),
    }[code]
    side_ids = tuple(
        connection.scalar(sa.select(foods.c.id).where(foods.c.slug == slug)) for slug in side_slugs
    )
    connection.execute(
        meal_items.delete().where(
            meal_items.c.meal_id == meal_id,
            meal_items.c.food_id.not_in(side_ids),
        )
    )
    connection.execute(
        meals.update()
        .where(meals.c.id == meal_id)
        .values(calculation_mode="prepared_recipe", verification_status="verified")
    )
    recipe_id = uuid5(NAMESPACE_URL, f"fitsho:nutrition:prepared-recipe:{code}")
    revision_id = uuid5(NAMESPACE_URL, f"fitsho:nutrition:prepared-recipe:{code}:v1")
    connection.execute(recipes.insert().values(id=recipe_id, meal_id=meal_id))
    revisions = _table(
        "nutrition_prepared_recipe_revisions",
        "id",
        "recipe_id",
        "version",
        "verification_status",
        "calculation_version",
        "source_name",
        "source_reference",
        "notes",
        "yield_method",
        "reference_input_grams",
        "final_cooked_yield_grams",
        "yield_source_name",
        "yield_source_reference",
        "yield_notes",
    )
    reference_input = sum(
        (Decimal(reference) for _, reference, *_ in ingredient_seeds), Decimal("0")
    )
    connection.execute(
        revisions.insert().values(
            id=revision_id,
            recipe_id=recipe_id,
            version=1,
            verification_status="draft",
            calculation_version="prepared-recipe-v1",
            source_name="Fitsho initial recipe estimate",
            source_reference="admin://nutrition/prepared-recipes/initial-estimate",
            notes="Ingredient bounds are editable; seasonings are intentionally excluded.",
            yield_method="proportional_reference_batch",
            reference_input_grams=reference_input,
            final_cooked_yield_grams=Decimal(str(seed["final_cooked_yield_grams"])),
            yield_source_name="Fitsho approximate retained-water model",
            yield_source_reference="admin://nutrition/prepared-recipes/estimated-yield",
            yield_notes="Approximate cooked mass; replace with a measured kitchen batch.",
        )
    )
    ingredients = _table(
        "nutrition_prepared_recipe_ingredients",
        "id",
        "revision_id",
        "food_id",
        "reference_grams",
        "min_grams",
        "max_grams",
        "is_required",
    )
    connection.execute(
        ingredients.insert(),
        [
            {
                "id": uuid5(NAMESPACE_URL, f"fitsho:nutrition:prepared-recipe:{code}:v1:{slug}"),
                "revision_id": revision_id,
                "food_id": food_ids[slug],
                "reference_grams": Decimal(reference),
                "min_grams": Decimal(minimum),
                "max_grams": Decimal(maximum),
                "is_required": required,
            }
            for slug, reference, minimum, maximum, required in ingredient_seeds
        ],
    )
    ratios = _table(
        "nutrition_prepared_recipe_ratios",
        "id",
        "revision_id",
        "numerator_food_id",
        "denominator_food_id",
        "min_ratio",
        "max_ratio",
    )
    connection.execute(
        ratios.insert(),
        [
            {
                "id": uuid5(
                    NAMESPACE_URL,
                    f"fitsho:nutrition:prepared-recipe:{code}:v1:ratio:{numerator}:{denominator}",
                ),
                "revision_id": revision_id,
                "numerator_food_id": food_ids[numerator],
                "denominator_food_id": food_ids[denominator],
                "min_ratio": Decimal(minimum),
                "max_ratio": Decimal(maximum),
            }
            for numerator, denominator, minimum, maximum in ratio_seeds
        ],
    )
    gaps = _table(
        "nutrition_prepared_recipe_data_gaps",
        "id",
        "revision_id",
        "ingredient_name_fa",
        "ingredient_name_en",
        "message_fa",
        "message_en",
    )
    connection.execute(
        gaps.insert().values(
            id=uuid5(NAMESPACE_URL, f"fitsho:nutrition:prepared-recipe:{code}:v1:yield-gap"),
            revision_id=revision_id,
            ingredient_name_fa=str(seed["name_fa"]),
            ingredient_name_en=str(seed["name_en"]),
            message_fa=str(seed["gap_fa"]),
            message_en=str(seed["gap_en"]),
        )
    )


def _table(name: str, *columns: str) -> sa.TableClause:
    return sa.table(name, *(sa.column(column) for column in columns))


def _normalize(value: str) -> str:
    return " ".join(value.strip().casefold().replace("ي", "ی").replace("ك", "ک").split())
