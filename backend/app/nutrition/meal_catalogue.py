from __future__ import annotations

from decimal import Decimal
from uuid import NAMESPACE_URL, UUID, uuid5

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.nutrition.enums import FoodVerificationStatus, MealCalculationMode, MealCategory
from app.nutrition.food_catalogue import FoodCompositionValue, calculate_meal_totals
from app.nutrition.meal_catalogue_seed_data import PREPARED_RECIPE_SEEDS, SEED_MEALS
from app.nutrition.models import (
    NutritionCatalogueFood,
    NutritionCatalogueMeal,
    NutritionCatalogueMealItem,
    NutritionPreparedRecipe,
    NutritionPreparedRecipeDataGap,
    NutritionPreparedRecipeIngredient,
    NutritionPreparedRecipeRatio,
    NutritionPreparedRecipeRevision,
    NutritionProgramSlot,
    NutritionWeeklyPlanMeal,
)
from app.nutrition.prepared_recipe import (
    CALCULATION_VERSION,
    PreparedRecipeDefinition,
    PreparedRecipeFood,
    PreparedRecipeIngredient,
    PreparedRecipeRatio,
    PreparedRecipeYield,
    calculate_prepared_recipe,
    validate_prepared_recipe,
)
from app.nutrition.price_overrides import effective_prices
from app.nutrition.schemas import (
    CatalogueMealItemResponse,
    CatalogueMealResponse,
    CatalogueMealWrite,
    PreparedRecipeIngredientResponse,
    PreparedRecipePreviewResponse,
    PreparedRecipeRatioResponse,
    PreparedRecipeResponse,
    PreparedRecipeWrite,
    PreparedRecipeYieldResponse,
    SharedCatalogueMealResponse,
)

CATEGORY_ORDER = tuple(MealCategory)


class MealReferencedError(Exception):
    pass


def list_catalogue_meals(
    db: Session,
    category: MealCategory | None = None,
    verification_status: FoodVerificationStatus | None = None,
) -> list[NutritionCatalogueMeal]:
    query = (
        select(NutritionCatalogueMeal)
        .options(
            selectinload(NutritionCatalogueMeal.items)
            .selectinload(NutritionCatalogueMealItem.food)
            .selectinload(NutritionCatalogueFood.compositions),
            selectinload(NutritionCatalogueMeal.prepared_recipe)
            .selectinload(NutritionPreparedRecipe.revisions)
            .selectinload(NutritionPreparedRecipeRevision.ingredients)
            .selectinload(NutritionPreparedRecipeIngredient.food)
            .selectinload(NutritionCatalogueFood.compositions),
            selectinload(NutritionCatalogueMeal.prepared_recipe)
            .selectinload(NutritionPreparedRecipe.revisions)
            .selectinload(NutritionPreparedRecipeRevision.ratios),
            selectinload(NutritionCatalogueMeal.prepared_recipe)
            .selectinload(NutritionPreparedRecipe.revisions)
            .selectinload(NutritionPreparedRecipeRevision.data_gaps),
        )
        .order_by(NutritionCatalogueMeal.category, NutritionCatalogueMeal.code)
    )
    if category is not None:
        query = query.where(NutritionCatalogueMeal.category == category)
    if verification_status is not None:
        query = query.where(NutritionCatalogueMeal.verification_status == verification_status)
    return list(db.scalars(query).unique())


def get_catalogue_meal(db: Session, meal_id: UUID) -> NutritionCatalogueMeal | None:
    return db.scalar(
        select(NutritionCatalogueMeal)
        .where(NutritionCatalogueMeal.id == meal_id)
        .options(
            selectinload(NutritionCatalogueMeal.items)
            .selectinload(NutritionCatalogueMealItem.food)
            .selectinload(NutritionCatalogueFood.compositions),
            selectinload(NutritionCatalogueMeal.prepared_recipe)
            .selectinload(NutritionPreparedRecipe.revisions)
            .selectinload(NutritionPreparedRecipeRevision.ingredients)
            .selectinload(NutritionPreparedRecipeIngredient.food)
            .selectinload(NutritionCatalogueFood.compositions),
            selectinload(NutritionCatalogueMeal.prepared_recipe)
            .selectinload(NutritionPreparedRecipe.revisions)
            .selectinload(NutritionPreparedRecipeRevision.ratios),
            selectinload(NutritionCatalogueMeal.prepared_recipe)
            .selectinload(NutritionPreparedRecipe.revisions)
            .selectinload(NutritionPreparedRecipeRevision.data_gaps),
        )
    )


def create_catalogue_meal(db: Session, payload: CatalogueMealWrite) -> NutritionCatalogueMeal:
    if db.scalar(
        select(NutritionCatalogueMeal.id).where(NutritionCatalogueMeal.code == payload.code)
    ):
        raise ValueError("Meal code already exists")
    meal = NutritionCatalogueMeal(code=payload.code)
    return _save_catalogue_meal(db, meal, payload)


def update_catalogue_meal(
    db: Session, meal_id: UUID, payload: CatalogueMealWrite
) -> NutritionCatalogueMeal | None:
    meal = db.get(NutritionCatalogueMeal, meal_id)
    if meal is None:
        return None
    if meal.code != payload.code:
        raise ValueError("Meal code cannot be changed")
    meal.items.clear()
    db.flush()
    return _save_catalogue_meal(db, meal, payload)


def delete_catalogue_meal(db: Session, meal_id: UUID) -> str | None:
    meal = db.scalar(
        select(NutritionCatalogueMeal).where(NutritionCatalogueMeal.id == meal_id).with_for_update()
    )
    if meal is None:
        return None

    program_slot_refs = (
        db.scalar(
            select(func.count())
            .select_from(NutritionProgramSlot)
            .where(NutritionProgramSlot.meal_id == meal_id)
        )
        or 0
    )
    weekly_plan_refs = (
        db.scalar(
            select(func.count())
            .select_from(NutritionWeeklyPlanMeal)
            .where(NutritionWeeklyPlanMeal.catalogue_meal_id == meal_id)
        )
        or 0
    )
    if program_slot_refs > 0 or weekly_plan_refs > 0:
        raise MealReferencedError(
            "Meal is referenced by existing nutrition programs or weekly plans "
            "and cannot be deleted."
        )

    image_path = meal.image_path
    db.delete(meal)
    db.commit()
    return image_path


def _save_catalogue_meal(
    db: Session, meal: NutritionCatalogueMeal, payload: CatalogueMealWrite
) -> NutritionCatalogueMeal:
    recipe_payload = payload.prepared_recipe
    requested_food_ids = {item.food_id for item in payload.items}
    if recipe_payload is not None:
        requested_food_ids.update(item.food_id for item in recipe_payload.ingredients)
    foods = {
        food.id: food
        for food in db.scalars(
            select(NutritionCatalogueFood).where(NutritionCatalogueFood.id.in_(requested_food_ids))
        )
    }
    if len(foods) != len(requested_food_ids):
        raise ValueError("Every meal food must exist")
    if payload.verification_status == FoodVerificationStatus.VERIFIED.value and any(
        foods[item.food_id].verification_status is not FoodVerificationStatus.VERIFIED
        for item in payload.items
    ):
        raise ValueError("Verified meals may only use verified foods")
    if payload.calculation_mode is MealCalculationMode.PREPARED_RECIPE:
        if recipe_payload is None:
            raise ValueError("Prepared Recipe meals require a valid recipe")
        definition = _definition_from_payload(recipe_payload)
        validate_prepared_recipe(definition, set(foods))
        if recipe_payload.verification_status == FoodVerificationStatus.VERIFIED.value:
            if recipe_payload.data_gaps:
                raise ValueError("Verified Prepared Recipes cannot contain data gaps")
            if any(
                item.is_required
                and foods[item.food_id].verification_status is not FoodVerificationStatus.VERIFIED
                for item in recipe_payload.ingredients
            ):
                raise ValueError("Verified Prepared Recipes require verified required foods")
    meal.name_fa = payload.name_fa
    meal.name_en = payload.name_en
    meal.category = payload.category
    meal.verification_status = FoodVerificationStatus(payload.verification_status)
    meal.calculation_mode = payload.calculation_mode
    meal.items = [
        NutritionCatalogueMealItem(
            food_id=item.food_id,
            reference_grams=item.reference_grams,
            min_grams=item.min_grams,
            max_grams=item.max_grams,
            is_required=item.is_required,
            functional_role=item.functional_role,
        )
        for item in payload.items
    ]
    db.add(meal)
    db.flush()
    if recipe_payload is not None:
        _append_recipe_revision(db, meal, recipe_payload)
    db.commit()
    saved = get_catalogue_meal(db, meal.id)
    if saved is None:
        raise ValueError("Meal was not found after saving")
    return saved


def _definition_from_payload(payload: object) -> PreparedRecipeDefinition:
    if not isinstance(payload, PreparedRecipeWrite):
        raise ValueError("Invalid Prepared Recipe payload")
    return PreparedRecipeDefinition(
        calculation_version=CALCULATION_VERSION,
        ingredients=tuple(
            PreparedRecipeIngredient(
                food_id=item.food_id,
                reference_grams=item.reference_grams,
                min_grams=item.min_grams,
                max_grams=item.max_grams,
                is_required=item.is_required,
            )
            for item in payload.ingredients
        ),
        ratios=tuple(
            PreparedRecipeRatio(
                numerator_food_id=item.numerator_food_id,
                denominator_food_id=item.denominator_food_id,
                min_ratio=item.min_ratio,
                max_ratio=item.max_ratio,
            )
            for item in payload.ratios
        ),
        cooked_yield=PreparedRecipeYield(
            method=payload.cooked_yield.method,
            reference_input_grams=sum(
                (item.reference_grams for item in payload.ingredients), Decimal("0")
            ),
            final_cooked_yield_grams=payload.cooked_yield.final_cooked_yield_grams,
        ),
    )


def _append_recipe_revision(db: Session, meal: NutritionCatalogueMeal, payload: object) -> None:
    if not isinstance(payload, PreparedRecipeWrite):
        raise ValueError("Invalid Prepared Recipe payload")
    recipe = db.scalar(
        select(NutritionPreparedRecipe).where(NutritionPreparedRecipe.meal_id == meal.id)
    )
    if recipe is None:
        recipe = NutritionPreparedRecipe(meal_id=meal.id)
        db.add(recipe)
        db.flush()
    latest_version = db.scalar(
        select(func.max(NutritionPreparedRecipeRevision.version)).where(
            NutritionPreparedRecipeRevision.recipe_id == recipe.id
        )
    )
    definition = _definition_from_payload(payload)
    revision = NutritionPreparedRecipeRevision(
        recipe_id=recipe.id,
        version=(latest_version or 0) + 1,
        verification_status=FoodVerificationStatus(payload.verification_status),
        calculation_version=CALCULATION_VERSION,
        source_name=payload.source_name,
        source_reference=payload.source_reference,
        notes=payload.notes,
        yield_method=payload.cooked_yield.method,
        reference_input_grams=definition.cooked_yield.reference_input_grams,
        final_cooked_yield_grams=payload.cooked_yield.final_cooked_yield_grams,
        yield_source_name=payload.cooked_yield.source_name,
        yield_source_reference=payload.cooked_yield.source_reference,
        yield_notes=payload.cooked_yield.notes,
        ingredients=[
            NutritionPreparedRecipeIngredient(
                food_id=item.food_id,
                reference_grams=item.reference_grams,
                min_grams=item.min_grams,
                max_grams=item.max_grams,
                is_required=item.is_required,
            )
            for item in payload.ingredients
        ],
        ratios=[
            NutritionPreparedRecipeRatio(
                numerator_food_id=item.numerator_food_id,
                denominator_food_id=item.denominator_food_id,
                min_ratio=item.min_ratio,
                max_ratio=item.max_ratio,
            )
            for item in payload.ratios
        ],
        data_gaps=[
            NutritionPreparedRecipeDataGap(**item.model_dump()) for item in payload.data_gaps
        ],
    )
    db.add(revision)
    db.flush()


def preview_prepared_recipe(
    db: Session, payload: PreparedRecipeWrite
) -> PreparedRecipePreviewResponse:
    definition = _definition_from_payload(payload)
    food_ids = [item.food_id for item in payload.ingredients]
    foods = db.scalars(
        select(NutritionCatalogueFood)
        .where(NutritionCatalogueFood.id.in_(food_ids))
        .options(selectinload(NutritionCatalogueFood.compositions))
    ).all()
    if len(foods) != len(food_ids):
        raise ValueError("Prepared Recipe ingredient does not exist in Food Catalogue")
    prices = effective_prices(db, food_ids)
    all_prices_available = len(prices) == len(food_ids)
    calculation_foods: dict[UUID, PreparedRecipeFood] = {}
    for food in foods:
        price = prices.get(food.id)
        price_per_gram = Decimal("0")
        reference_id = "unavailable"
        if price is not None and price.canonical_unit == "TOMAN_PER_KG":
            price_per_gram = price.reference_price_toman * Decimal("10") / Decimal("1000")
            reference_id = price.reference_id
        else:
            all_prices_available = False
        calculation_foods[food.id] = PreparedRecipeFood(
            food_id=food.id,
            nutrients_per_100g={
                composition.nutrient_code: composition.value_per_100g
                for composition in food.compositions
            },
            price_irr_per_gram=price_per_gram,
            price_reference_id=reference_id,
        )
    calculation = calculate_prepared_recipe(definition, calculation_foods)
    return PreparedRecipePreviewResponse(
        final_cooked_yield_grams=float(calculation.final_cooked_yield_grams),
        nutrients_per_100g={
            code: float(value) for code, value in calculation.nutrients_per_100g.items()
        },
        estimated_cost_irr_per_100g=(
            float(calculation.cost_irr_per_100g) if all_prices_available else None
        ),
        price_reference_ids=(list(calculation.price_reference_ids) if all_prices_available else []),
    )


def meal_summary_response(meal: NutritionCatalogueMeal) -> SharedCatalogueMealResponse:
    return SharedCatalogueMealResponse(
        id=meal.id,
        code=meal.code,
        name_fa=meal.name_fa,
        name_en=meal.name_en,
        image_url=meal.image_path,
        category=meal.category,
        verification_status=meal.verification_status.value,
        calculation_mode=meal.calculation_mode,
        items=[
            CatalogueMealItemResponse(
                food_id=item.food_id,
                food_slug=item.food.slug,
                food_name_fa=item.food.name_fa,
                food_name_en=item.food.name_en,
                reference_grams=float(item.reference_grams),
                min_grams=float(item.min_grams),
                max_grams=float(item.max_grams),
                is_required=item.is_required,
                functional_role=item.functional_role,
            )
            for item in meal.items
        ],
    )


def meal_response(meal: NutritionCatalogueMeal, db: Session | None = None) -> CatalogueMealResponse:
    total_items = [
        (
            item.reference_grams,
            [
                FoodCompositionValue(row.nutrient_code, row.value_per_100g, row.unit)
                for row in item.food.compositions
            ],
        )
        for item in meal.items
    ]
    prepared_response = _prepared_recipe_response(meal, db)
    if prepared_response is not None:
        total_items.append(
            (
                Decimal(str(prepared_response.preview.final_cooked_yield_grams)),
                [
                    FoodCompositionValue(code, Decimal(str(value)), "")
                    for code, value in prepared_response.preview.nutrients_per_100g.items()
                ],
            )
        )
    totals = calculate_meal_totals(total_items)
    return CatalogueMealResponse(
        id=meal.id,
        code=meal.code,
        name_fa=meal.name_fa,
        name_en=meal.name_en,
        image_url=meal.image_path,
        category=meal.category,
        verification_status=meal.verification_status.value,
        calculation_mode=meal.calculation_mode,
        items=[
            CatalogueMealItemResponse(
                food_id=item.food_id,
                food_slug=item.food.slug,
                food_name_fa=item.food.name_fa,
                food_name_en=item.food.name_en,
                reference_grams=float(item.reference_grams),
                min_grams=float(item.min_grams),
                max_grams=float(item.max_grams),
                is_required=item.is_required,
                functional_role=item.functional_role,
            )
            for item in meal.items
        ],
        prepared_recipe=prepared_response,
        totals={key: float(value) if value is not None else None for key, value in totals.items()},
    )


def _prepared_recipe_response(
    meal: NutritionCatalogueMeal, db: Session | None
) -> PreparedRecipeResponse | None:
    if meal.calculation_mode is not MealCalculationMode.PREPARED_RECIPE:
        return None
    recipe = meal.prepared_recipe
    if recipe is None or not recipe.revisions:
        raise ValueError("Prepared Recipe meal has no valid recipe revision")
    revision = recipe.revisions[-1]
    definition = PreparedRecipeDefinition(
        calculation_version=revision.calculation_version,
        ingredients=tuple(
            PreparedRecipeIngredient(
                food_id=item.food_id,
                reference_grams=item.reference_grams,
                min_grams=item.min_grams,
                max_grams=item.max_grams,
                is_required=item.is_required,
            )
            for item in revision.ingredients
        ),
        ratios=tuple(
            PreparedRecipeRatio(
                numerator_food_id=item.numerator_food_id,
                denominator_food_id=item.denominator_food_id,
                min_ratio=item.min_ratio,
                max_ratio=item.max_ratio,
            )
            for item in revision.ratios
        ),
        cooked_yield=PreparedRecipeYield(
            method=revision.yield_method,
            reference_input_grams=revision.reference_input_grams,
            final_cooked_yield_grams=revision.final_cooked_yield_grams,
        ),
    )
    prices = effective_prices(db, [item.food_id for item in revision.ingredients]) if db else {}
    all_prices_available = len(prices) == len(revision.ingredients)
    calculation_foods: dict[UUID, PreparedRecipeFood] = {}
    for item in revision.ingredients:
        price = prices.get(item.food_id)
        price_per_gram = Decimal("0")
        reference_id = "unavailable"
        if price is not None and price.canonical_unit == "TOMAN_PER_KG":
            price_per_gram = price.reference_price_toman * Decimal("10") / Decimal("1000")
            reference_id = price.reference_id
        else:
            all_prices_available = False
        calculation_foods[item.food_id] = PreparedRecipeFood(
            food_id=item.food_id,
            nutrients_per_100g={
                composition.nutrient_code: composition.value_per_100g
                for composition in item.food.compositions
            },
            price_irr_per_gram=price_per_gram,
            price_reference_id=reference_id,
        )
    calculation = calculate_prepared_recipe(definition, calculation_foods)
    return PreparedRecipeResponse(
        id=revision.id,
        version=revision.version,
        verification_status=revision.verification_status.value,
        calculation_version=revision.calculation_version,
        source_name=revision.source_name,
        source_reference=revision.source_reference,
        notes=revision.notes,
        cooked_yield=PreparedRecipeYieldResponse(
            method=revision.yield_method,
            reference_input_grams=float(revision.reference_input_grams),
            final_cooked_yield_grams=float(revision.final_cooked_yield_grams),
            source_name=revision.yield_source_name,
            source_reference=revision.yield_source_reference,
            notes=revision.yield_notes,
        ),
        ingredients=[
            PreparedRecipeIngredientResponse(
                food_id=item.food_id,
                food_slug=item.food.slug,
                food_name_fa=item.food.name_fa,
                food_name_en=item.food.name_en,
                reference_grams=float(item.reference_grams),
                min_grams=float(item.min_grams),
                max_grams=float(item.max_grams),
                is_required=item.is_required,
            )
            for item in revision.ingredients
        ],
        ratios=[
            PreparedRecipeRatioResponse(
                numerator_food_id=item.numerator_food_id,
                denominator_food_id=item.denominator_food_id,
                min_ratio=float(item.min_ratio),
                max_ratio=float(item.max_ratio),
            )
            for item in revision.ratios
        ],
        data_gaps=[
            {
                "ingredient_name_fa": item.ingredient_name_fa,
                "ingredient_name_en": item.ingredient_name_en,
                "message_fa": item.message_fa,
                "message_en": item.message_en,
            }
            for item in revision.data_gaps
        ],
        preview=PreparedRecipePreviewResponse(
            final_cooked_yield_grams=float(calculation.final_cooked_yield_grams),
            nutrients_per_100g={
                code: float(value) for code, value in calculation.nutrients_per_100g.items()
            },
            estimated_cost_irr_per_100g=(
                float(calculation.cost_irr_per_100g) if all_prices_available else None
            ),
            price_reference_ids=(
                list(calculation.price_reference_ids) if all_prices_available else []
            ),
        ),
    )


def seed_meal_catalogue(db: Session, *, commit: bool = True) -> list[NutritionCatalogueMeal]:
    foods = {food.slug: food for food in db.scalars(select(NutritionCatalogueFood))}
    seed_codes = [str(seed["code"]) for seed in SEED_MEALS]
    existing_by_code = {
        meal.code: meal
        for meal in db.scalars(
            select(NutritionCatalogueMeal).where(NutritionCatalogueMeal.code.in_(seed_codes))
        )
    }
    seeded: list[NutritionCatalogueMeal] = []
    for seed in SEED_MEALS:
        category = seed["category"]
        assert isinstance(category, MealCategory)
        code = str(seed["code"])
        meal = existing_by_code.get(code)
        if meal is None:
            meal = NutritionCatalogueMeal(
                id=uuid5(NAMESPACE_URL, f"fitsho:nutrition:meal:{code}"), code=code
            )
            db.add(meal)
        else:
            meal.items.clear()
            db.flush()
        item_seeds = seed["items"]
        assert isinstance(item_seeds, tuple)
        missing = [slug for slug, *_ in item_seeds if slug not in foods]
        if missing:
            raise ValueError(f"Meal seed foods are missing: {', '.join(missing)}")
        meal.name_fa = str(seed["name_fa"])
        meal.name_en = str(seed["name_en"])
        meal.code = code
        meal.category = category
        meal.verification_status = (
            FoodVerificationStatus.VERIFIED
            if all(
                foods[slug].verification_status is FoodVerificationStatus.VERIFIED
                for slug, *_ in item_seeds
            )
            else FoodVerificationStatus.DRAFT
        )
        recipe_seed = PREPARED_RECIPE_SEEDS.get(code)
        meal.calculation_mode = (
            MealCalculationMode.PREPARED_RECIPE
            if recipe_seed is not None
            else MealCalculationMode.SIMPLE
        )
        meal.items = [
            NutritionCatalogueMealItem(
                id=uuid5(NAMESPACE_URL, f"fitsho:nutrition:meal:{code}:{slug}"),
                food_id=foods[slug].id,
                reference_grams=Decimal(reference),
                min_grams=Decimal(minimum),
                max_grams=Decimal(maximum),
                is_required=required,
                functional_role=role,
            )
            for slug, reference, minimum, maximum, required, role in item_seeds
        ]
        if recipe_seed is not None:
            _seed_initial_prepared_recipe(db, meal, recipe_seed, foods)
        seeded.append(meal)
    if commit:
        db.commit()
    else:
        db.flush()
    return list_catalogue_meals(db)


def _seed_initial_prepared_recipe(
    db: Session,
    meal: NutritionCatalogueMeal,
    seed: dict[str, object],
    foods: dict[str, NutritionCatalogueFood],
) -> None:
    existing_recipe_id = db.scalar(
        select(NutritionPreparedRecipe.id).where(NutritionPreparedRecipe.meal_id == meal.id)
    )
    if existing_recipe_id:
        return
    ingredient_seeds = seed["ingredients"]
    ratio_seeds = seed["ratios"]
    assert isinstance(ingredient_seeds, tuple)
    assert isinstance(ratio_seeds, tuple)
    missing = [slug for slug, *_ in ingredient_seeds if slug not in foods]
    if missing:
        raise ValueError(f"Prepared Recipe seed foods are missing: {', '.join(missing)}")
    recipe = NutritionPreparedRecipe(
        id=uuid5(NAMESPACE_URL, f"fitsho:nutrition:prepared-recipe:{meal.code}"),
        meal_id=meal.id,
    )
    db.add(recipe)
    db.flush()
    reference_input = sum(
        (Decimal(reference) for _, reference, *_ in ingredient_seeds), Decimal("0")
    )
    revision = NutritionPreparedRecipeRevision(
        id=uuid5(NAMESPACE_URL, f"fitsho:nutrition:prepared-recipe:{meal.code}:v1"),
        recipe_id=recipe.id,
        version=1,
        verification_status=FoodVerificationStatus.DRAFT,
        calculation_version=CALCULATION_VERSION,
        source_name="Fitsho initial recipe estimate",
        source_reference="admin://nutrition/prepared-recipes/initial-estimate",
        notes="Ingredient bounds are editable; seasonings are intentionally excluded.",
        yield_method="proportional_reference_batch",
        reference_input_grams=reference_input,
        final_cooked_yield_grams=Decimal(str(seed["final_cooked_yield_grams"])),
        yield_source_name="Fitsho approximate retained-water model",
        yield_source_reference="admin://nutrition/prepared-recipes/estimated-yield",
        yield_notes="Approximate cooked mass; replace with a measured kitchen batch.",
        ingredients=[
            NutritionPreparedRecipeIngredient(
                food_id=foods[slug].id,
                reference_grams=Decimal(reference),
                min_grams=Decimal(minimum),
                max_grams=Decimal(maximum),
                is_required=required,
            )
            for slug, reference, minimum, maximum, required in ingredient_seeds
        ],
        ratios=[
            NutritionPreparedRecipeRatio(
                numerator_food_id=foods[numerator].id,
                denominator_food_id=foods[denominator].id,
                min_ratio=Decimal(minimum),
                max_ratio=Decimal(maximum),
            )
            for numerator, denominator, minimum, maximum in ratio_seeds
        ],
        data_gaps=[
            NutritionPreparedRecipeDataGap(
                ingredient_name_fa=str(seed["name_fa"]),
                ingredient_name_en=str(seed["name_en"]),
                message_fa=str(seed["gap_fa"]),
                message_en=str(seed["gap_en"]),
            )
        ],
    )
    db.add(revision)
    db.flush()
