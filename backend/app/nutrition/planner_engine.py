from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, replace
from decimal import ROUND_HALF_UP, Decimal
from enum import StrEnum

from app.nutrition.budget_optimizer import BudgetRepairAction, optimize_weekly_budget
from app.nutrition.candidate_selection import quality_for_result
from app.nutrition.exceptions import ScheduledTemplateUnavailableError
from app.nutrition.food_constraints import (
    ConstraintSeverity,
    NormalizedFoodConstraint,
    evaluate_food_constraints,
)
from app.nutrition.planner_policy import DEFAULT_POLICY, PlannerPolicy
from app.nutrition.portion_solver import (
    PortionAdjustmentAction,
    PortionVariable,
    solve_portions,
)
from app.nutrition.preference_snapshot import PreferenceSnapshot
from app.nutrition.prepared_recipe import (
    PreparedRecipeCalculation,
    PreparedRecipeDefinition,
    PreparedRecipeFood,
    calculate_prepared_recipe,
)
from app.nutrition.template_substitution import (
    NoCompatibleTemplateSubstituteError,
    PartialWeekVariant,
    SubstitutionAction,
    SubstitutionContext,
    rank_template_substitutes,
    substitution_rejection_diagnostics,
    template_reference_metrics,
)

ZERO = Decimal("0")
ONE = Decimal("1")
HUNDRED = Decimal("100")
TARGET_NUTRIENT_CODES = {
    "goal_calories": "energy_kcal",
    "protein": "protein_g",
    "carbohydrate": "carbohydrate_g",
    "total_fat": "total_fat_g",
    "fibre": "fibre_g",
    "free_sugar": "free_sugar_g",
    "added_sugar": "added_sugar_g",
    "saturated_fat": "saturated_fat_g",
    "trans_fat": "trans_fat_g",
    "sodium": "sodium_mg",
}


class GenerationOutcome(StrEnum):
    SUCCESS = "success"
    FAILED = "failed"
    SAFETY_BLOCKED = "safety_blocked"
    INFEASIBLE = "infeasible"
    TARGET_INFEASIBLE = "target_infeasible"
    LIVE_PRICE_UNAVAILABLE = "live_price_unavailable"


@dataclass(frozen=True)
class PlannerFood:
    food_id: str
    slug: str
    name_fa: str
    name_en: str
    roles: tuple[str, ...]
    nutrients_per_100g: dict[str, Decimal]
    price_irr_per_gram: Decimal
    price_reference_id: str
    dietary_patterns: tuple[str, ...] = ("omnivore", "vegetarian", "vegan")
    allergen_tags: tuple[str, ...] = ()
    allergen_metadata_verified: bool = False


@dataclass(frozen=True)
class PlannerMealIngredient:
    food_id: str
    reference_grams: Decimal
    min_grams: Decimal
    max_grams: Decimal
    is_required: bool
    functional_role: str | None


@dataclass(frozen=True)
class PlannerMealTemplate:
    meal_id: str
    name_fa: str
    name_en: str
    category: str
    items: tuple[PlannerMealIngredient, ...]
    prepared_recipe: PlannerPreparedRecipe | None = None
    verification_status: str = "verified"


@dataclass(frozen=True)
class PlannerPreparedRecipe:
    revision_id: str
    name_fa: str
    name_en: str
    definition: PreparedRecipeDefinition
    verification_status: str = "draft"
    provenance: dict[str, object] | None = None
    data_gaps: tuple[dict[str, str], ...] = ()


@dataclass(frozen=True)
class EligibleMealTemplate:
    template: PlannerMealTemplate
    items: tuple[tuple[PlannerMealIngredient, PlannerFood], ...]
    prepared_recipe_foods: tuple[tuple[str, PlannerFood], ...] = ()


@dataclass(frozen=True)
class PlannerInput:
    daily_targets: dict[str, Decimal]
    micronutrient_targets: dict[str, Decimal]
    micronutrient_upper_limits: dict[str, Decimal]
    daily_minimums: dict[str, Decimal]
    daily_maximums: dict[str, Decimal]
    main_meals_per_day: int
    snacks_per_day: int
    weekly_budget_irr: int
    budget_mode: str
    excluded_terms: tuple[str, ...]
    liked_food_ids: tuple[str, ...]
    disliked_food_ids: tuple[str, ...]
    dietary_pattern: str
    maximum_meal_repetition_per_week: int
    template_schedule: tuple[tuple[tuple[str, str | None, str], ...], ...] | None = None
    preference_snapshot: PreferenceSnapshot | None = None
    food_constraints: tuple[NormalizedFoodConstraint, ...] = ()


@dataclass(frozen=True)
class PlannedFood:
    food_id: str | None
    slug: str
    name_fa: str
    name_en: str
    roles: tuple[str, ...]
    grams: Decimal
    cost_irr: Decimal
    nutrients: tuple[tuple[str, Decimal], ...]
    price_reference_id: str
    min_grams: Decimal
    max_grams: Decimal
    functional_role: str | None
    item_kind: str = "food"
    recipe_snapshot: dict[str, object] | None = None


@dataclass(frozen=True)
class PlannedMeal:
    role: str
    slot_index: int
    template_id: str | None
    template_category: str
    foods: tuple[PlannedFood, ...]
    cost_irr: Decimal
    nutrients: tuple[tuple[str, Decimal], ...]


@dataclass(frozen=True)
class PlannedDay:
    day_index: int
    meals: tuple[PlannedMeal, ...]
    cost_irr: Decimal
    nutrients: tuple[tuple[str, Decimal], ...]


@dataclass(frozen=True)
class NutrientComparison:
    preferred: Decimal | None
    minimum_or_maximum: Decimal | None
    planned: Decimal
    difference_from_preferred: Decimal | None
    difference_from_limit: Decimal | None
    status: str
    reason_codes: tuple[str, ...] = ()
    data_confidence: str = "high"


@dataclass(frozen=True)
class RepairAction:
    nutrient_code: str
    food_slug: str
    grams_added: Decimal
    day_index: int
    reason_code: str = "MICRONUTRIENT_REPAIR_APPLIED"


@dataclass(frozen=True)
class PlannerResult:
    outcome: GenerationOutcome
    reason_codes: tuple[str, ...]
    days: tuple[PlannedDay, ...] = ()
    weekly_cost_irr: Decimal = ZERO
    budget_status: str = "unavailable"
    nutrient_comparisons: dict[str, NutrientComparison] | None = None
    repair_actions: tuple[RepairAction, ...] = ()
    warning_codes: tuple[str, ...] = ()
    substitution_actions: tuple[SubstitutionAction, ...] = ()
    substitution_diagnostics: tuple[dict[str, str], ...] = ()
    budget_repair_actions: tuple[BudgetRepairAction, ...] = ()
    budget_diagnostics: dict[str, str] | None = None
    portion_adjustment_actions: tuple[PortionAdjustmentAction, ...] = ()

    def __post_init__(self) -> None:
        if self.nutrient_comparisons is None:
            object.__setattr__(self, "nutrient_comparisons", {})
        if self.budget_diagnostics is None:
            object.__setattr__(self, "budget_diagnostics", {})


@dataclass(frozen=True)
class _ScheduledWeekVariant:
    days: tuple[PlannedDay, ...]
    substitutions: tuple[SubstitutionAction, ...]
    stable_variant_key: tuple[str, ...]


@dataclass(frozen=True)
class _EvaluatedVariant:
    result: PlannerResult
    stable_variant_key: tuple[str, ...]


def plan_week(
    inputs: PlannerInput,
    foods: tuple[PlannerFood, ...],
    meal_templates: tuple[PlannerMealTemplate, ...],
    policy: PlannerPolicy = DEFAULT_POLICY,
    *,
    optimization_cache: dict[tuple[object, ...], PlannedFood] | None = None,
) -> PlannerResult:
    _validate_inputs(inputs)
    optimization_cache = optimization_cache if optimization_cache is not None else {}
    eligible = tuple(
        sorted(
            (
                food
                for food in foods
                if food.price_irr_per_gram > ZERO
                and _has_mandatory_nutrients(food)
                and not _is_food_blocked(food, inputs)
                and inputs.dietary_pattern in food.dietary_patterns
            ),
            key=lambda item: item.slug,
        )
    )
    eligible_templates = _eligible_templates(inputs, eligible, meal_templates)
    main_templates = _rank_templates(
        inputs,
        tuple(item for item in eligible_templates if item.template.category != "snack"),
        policy,
    )
    snack_templates = _rank_templates(
        inputs,
        tuple(item for item in eligible_templates if item.template.category == "snack"),
        policy,
    )
    if not main_templates or (inputs.snacks_per_day and not snack_templates):
        if inputs.preference_snapshot is not None and inputs.preference_snapshot.excluded_meal_ids:
            excluded = set(inputs.preference_snapshot.excluded_meal_ids)
            if any(template.meal_id in excluded for template in meal_templates):
                return _failure(
                    GenerationOutcome.INFEASIBLE,
                    "PREFERENCE_EXCLUSION_NO_FEASIBLE_PLAN",
                )
        return _failure(GenerationOutcome.LIVE_PRICE_UNAVAILABLE, "INSUFFICIENT_PRICE_COVERAGE")

    weekly_budget_cap = _weekly_budget_cap(inputs, policy)
    variants: tuple[_ScheduledWeekVariant, ...]
    try:
        if inputs.template_schedule is None:
            days = _build_days(
                inputs,
                main_templates,
                snack_templates,
                policy,
                maximum_recipe_cost_irr=weekly_budget_cap,
                optimization_cache=optimization_cache,
            )
            variants = (_ScheduledWeekVariant(days, (), ("base",)),)
        else:
            variants = _build_scheduled_day_variants(
                inputs,
                main_templates,
                snack_templates,
                meal_templates,
                policy,
                maximum_recipe_cost_irr=weekly_budget_cap,
                optimization_cache=optimization_cache,
                all_foods_by_id={food.food_id: food for food in foods},
            )
    except NoCompatibleTemplateSubstituteError as error:
        if inputs.preference_snapshot is not None and inputs.preference_snapshot.excluded_meal_ids:
            if error.requested_template_id in set(inputs.preference_snapshot.excluded_meal_ids):
                return _failure(
                    GenerationOutcome.INFEASIBLE,
                    "PREFERENCE_EXCLUSION_NO_FEASIBLE_PLAN",
                )
        return PlannerResult(
            outcome=GenerationOutcome.INFEASIBLE,
            reason_codes=("NO_COMPATIBLE_TEMPLATE_SUBSTITUTE",),
            substitution_diagnostics=error.diagnostics,
        )
    except ScheduledTemplateUnavailableError as error:
        if inputs.preference_snapshot is not None and error.meal_id in set(
            inputs.preference_snapshot.excluded_meal_ids
        ):
            return _failure(GenerationOutcome.INFEASIBLE, "PREFERENCE_EXCLUSION_NO_FEASIBLE_PLAN")
        return _failure(GenerationOutcome.INFEASIBLE, "SCHEDULED_TEMPLATE_UNAVAILABLE")

    foods_by_id = {food.food_id: food for food in eligible}
    evaluated = tuple(
        _EvaluatedVariant(
            result=_evaluate_built_days(
                inputs,
                variant.days,
                eligible_templates,
                foods_by_id,
                policy,
                substitution_actions=variant.substitutions,
                optimization_cache=optimization_cache,
            ),
            stable_variant_key=variant.stable_variant_key,
        )
        for variant in variants[: policy.maximum_candidate_rebuild_attempts]
    )
    successful = tuple(
        variant for variant in evaluated if variant.result.outcome is GenerationOutcome.SUCCESS
    )
    if successful:
        return min(
            successful,
            key=lambda variant: quality_for_result(
                variant.result,
                weekly_budget_irr=Decimal(inputs.weekly_budget_irr),
                stable_variant_key=variant.stable_variant_key,
                preference_snapshot=inputs.preference_snapshot,
            ).sort_key(),
        ).result
    return min(evaluated, key=_failure_variant_key).result


def _evaluate_built_days(
    inputs: PlannerInput,
    days: tuple[PlannedDay, ...],
    eligible_templates: tuple[EligibleMealTemplate, ...],
    foods_by_id: dict[str, PlannerFood],
    policy: PlannerPolicy,
    *,
    substitution_actions: tuple[SubstitutionAction, ...],
    optimization_cache: dict[tuple[object, ...], PlannedFood],
) -> PlannerResult:
    days, repairs = _repair_micronutrients(days, inputs, foods_by_id, policy)

    def build_budget_meal(
        candidate: EligibleMealTemplate,
        role: str,
        slot_index: int,
        target_kcal: Decimal,
        maximum_cost_irr: Decimal,
    ) -> PlannedMeal:
        return _meal_from_template(
            role,
            slot_index,
            candidate,
            target_kcal,
            maximum_recipe_cost_irr=maximum_cost_irr,
            optimization_cache=optimization_cache,
        )

    portion_actions: list[PortionAdjustmentAction] = []
    portion_reasons: tuple[str, ...] = ()
    budget_result = None
    validation: tuple[str, ...] = ()
    upper_limit_exceeded = False
    for _ in range(policy.maximum_combined_repair_passes):
        days, actions, portion_reasons = _repair_portions(days, inputs, foods_by_id, policy)
        portion_actions.extend(actions)
        budget_result = optimize_weekly_budget(
            days=days,
            inputs=inputs,
            eligible_templates=eligible_templates,
            policy=policy,
            meal_builder=build_budget_meal,
        )
        days = budget_result.days
        days, actions, post_portion_reasons = _repair_portions(days, inputs, foods_by_id, policy)
        portion_actions.extend(actions)
        portion_reasons = tuple(dict.fromkeys((*portion_reasons, *post_portion_reasons)))
        weekly_totals = _sum_nutrients(day.nutrients for day in days)
        daily_average = {code: value / Decimal("7") for code, value in weekly_totals.items()}
        validation = _validate_nutritional_feasibility(inputs, daily_average, policy)
        upper_limit_exceeded = _upper_limit_exceeded(inputs, daily_average)
        allowance = Decimal(inputs.weekly_budget_irr)
        budget_cap = allowance * (
            Decimal("1")
            if inputs.budget_mode == "strict"
            else Decimal("1") + policy.flexible_budget_overage_cap
        )
        budget_valid = (
            budget_result.failure_code is None and budget_result.final_cost_irr <= budget_cap
        )
        if not validation and not upper_limit_exceeded and budget_valid:
            break

    assert budget_result is not None
    weekly_totals = _sum_nutrients(day.nutrients for day in days)
    daily_average = {code: value / Decimal("7") for code, value in weekly_totals.items()}
    data_completeness = _nutrient_data_completeness(days, inputs)
    comparisons = _comparisons(inputs, daily_average, data_completeness, policy)
    if upper_limit_exceeded or validation:
        return PlannerResult(
            outcome=(
                GenerationOutcome.INFEASIBLE
                if upper_limit_exceeded
                else GenerationOutcome.TARGET_INFEASIBLE
            ),
            reason_codes=(
                ("NUTRIENT_UPPER_LIMIT_EXCEEDED",)
                if upper_limit_exceeded
                else portion_reasons or validation
            ),
            nutrient_comparisons=comparisons,
            repair_actions=repairs,
            substitution_actions=substitution_actions,
            budget_repair_actions=budget_result.repair_actions,
            budget_diagnostics=budget_result.diagnostics,
            portion_adjustment_actions=tuple(portion_actions),
        )
    cost = budget_result.final_cost_irr
    if budget_result.failure_code is not None:
        return PlannerResult(
            outcome=GenerationOutcome.INFEASIBLE,
            reason_codes=(budget_result.failure_code,),
            weekly_cost_irr=cost,
            budget_status="over_budget",
            nutrient_comparisons=comparisons,
            repair_actions=repairs,
            substitution_actions=substitution_actions,
            budget_repair_actions=budget_result.repair_actions,
            budget_diagnostics=budget_result.diagnostics,
            portion_adjustment_actions=tuple(portion_actions),
        )
    allowance = Decimal(inputs.weekly_budget_irr)
    if inputs.budget_mode == "strict" and cost > allowance:
        return PlannerResult(
            outcome=GenerationOutcome.INFEASIBLE,
            reason_codes=("STRICT_BUDGET_EXCEEDED",),
            weekly_cost_irr=cost,
            budget_status="over_budget",
            nutrient_comparisons=comparisons,
            repair_actions=repairs,
            substitution_actions=substitution_actions,
            budget_repair_actions=budget_result.repair_actions,
            budget_diagnostics=budget_result.diagnostics,
            portion_adjustment_actions=tuple(portion_actions),
        )
    if inputs.budget_mode == "flexible" and cost > allowance * (
        Decimal("1") + policy.flexible_budget_overage_cap
    ):
        return PlannerResult(
            outcome=GenerationOutcome.INFEASIBLE,
            reason_codes=("FLEXIBLE_BUDGET_CAP_EXCEEDED",),
            weekly_cost_irr=cost,
            budget_status="over_budget",
            nutrient_comparisons=comparisons,
            repair_actions=repairs,
            substitution_actions=substitution_actions,
            budget_repair_actions=budget_result.repair_actions,
            budget_diagnostics=budget_result.diagnostics,
            portion_adjustment_actions=tuple(portion_actions),
        )
    budget_status = "flexible_overage" if cost > allowance else "within_budget"
    warning_codes = _warning_codes(
        inputs,
        daily_average,
        budget_status,
        data_completeness,
        days,
    )
    return PlannerResult(
        outcome=GenerationOutcome.SUCCESS,
        reason_codes=("SAFE_FEASIBLE_DRAFT_GENERATED",),
        days=days,
        weekly_cost_irr=cost,
        budget_status=budget_status,
        nutrient_comparisons=comparisons,
        repair_actions=repairs,
        warning_codes=warning_codes,
        substitution_actions=substitution_actions,
        budget_repair_actions=budget_result.repair_actions,
        budget_diagnostics=budget_result.diagnostics,
        portion_adjustment_actions=tuple(portion_actions),
    )


def _failure_variant_key(variant: _EvaluatedVariant) -> tuple[object, ...]:
    outcome_priority = {
        GenerationOutcome.TARGET_INFEASIBLE: 0,
        GenerationOutcome.INFEASIBLE: 1,
        GenerationOutcome.LIVE_PRICE_UNAVAILABLE: 2,
        GenerationOutcome.FAILED: 3,
    }
    return (
        outcome_priority.get(variant.result.outcome, 4),
        variant.result.reason_codes,
        len(variant.result.substitution_actions),
        variant.stable_variant_key,
    )


def _validate_inputs(inputs: PlannerInput) -> None:
    if inputs.main_meals_per_day not in {2, 3, 4}:
        raise ValueError("Main meal slots must be between 2 and 4")
    if inputs.snacks_per_day not in {0, 1, 2, 3}:
        raise ValueError("Snack slots must be between 0 and 3")
    if inputs.weekly_budget_irr < 0 or inputs.budget_mode not in {"strict", "flexible"}:
        raise ValueError("Invalid budget input")
    if inputs.dietary_pattern not in {"omnivore", "vegetarian", "vegan"}:
        raise ValueError("Invalid dietary pattern")
    if inputs.maximum_meal_repetition_per_week < 1:
        raise ValueError("Maximum meal repetition must be positive")


def _weekly_budget_cap(inputs: PlannerInput, policy: PlannerPolicy) -> Decimal:
    allowance = Decimal(inputs.weekly_budget_irr)
    if inputs.budget_mode == "strict":
        return allowance
    return allowance * (Decimal("1") + policy.flexible_budget_overage_cap)


def _has_mandatory_nutrients(food: PlannerFood) -> bool:
    return (
        all(
            food.nutrients_per_100g.get(code, ZERO) >= ZERO and code in food.nutrients_per_100g
            for code in ("energy_kcal", "protein_g", "carbohydrate_g", "total_fat_g")
        )
        and food.nutrients_per_100g["energy_kcal"] > ZERO
    )


def _excluded(food: PlannerFood, excluded_terms: tuple[str, ...]) -> bool:
    haystack = f"{food.slug} {food.name_fa}".casefold()
    return any(term.strip().casefold() in haystack for term in excluded_terms if term.strip())


def _is_food_blocked(food: PlannerFood, inputs: PlannerInput) -> bool:
    if _excluded(food, inputs.excluded_terms):
        return True
    if inputs.food_constraints:
        decision = evaluate_food_constraints(
            constraints=inputs.food_constraints,
            slug=food.slug,
            name_fa=food.name_fa,
            name_en=food.name_en,
            allergen_tags=food.allergen_tags,
            allergen_metadata_verified=food.allergen_metadata_verified,
        )
        if decision.is_hard_blocked:
            return True
    return False


def _rank_candidates(
    inputs: PlannerInput,
    foods: tuple[PlannerFood, ...],
    policy: PlannerPolicy,
) -> tuple[PlannerFood, ...]:
    def score(food: PlannerFood) -> tuple[Decimal, str]:
        energy = food.nutrients_per_100g["energy_kcal"]
        micronutrient_adequacy = sum(
            (
                min(food.nutrients_per_100g.get(code, ZERO) / target, Decimal("1"))
                for code, target in inputs.micronutrient_targets.items()
                if target > ZERO
            ),
            ZERO,
        )
        preference = (Decimal("1") if food.food_id in inputs.liked_food_ids else ZERO) - (
            Decimal("1") if food.food_id in inputs.disliked_food_ids else ZERO
        )
        if inputs.food_constraints:
            decision = evaluate_food_constraints(
                constraints=inputs.food_constraints,
                slug=food.slug,
                name_fa=food.name_fa,
                name_en=food.name_en,
                allergen_tags=food.allergen_tags,
                allergen_metadata_verified=food.allergen_metadata_verified,
            )
            if decision.penalty > ZERO:
                preference -= decision.penalty
        cost_per_kcal = food.price_irr_per_gram * HUNDRED / energy
        value = (
            micronutrient_adequacy * policy.micronutrient_score_weight
            + preference * policy.preference_score_weight
            - cost_per_kcal * policy.cost_score_weight / Decimal("10000")
        )
        return (-value, food.slug)

    return tuple(sorted(foods, key=score))


def _eligible_templates(
    inputs: PlannerInput,
    foods: tuple[PlannerFood, ...],
    templates: tuple[PlannerMealTemplate, ...],
) -> tuple[EligibleMealTemplate, ...]:
    foods_by_id = {food.food_id: food for food in foods}
    eligible: list[EligibleMealTemplate] = []
    for template in sorted(templates, key=lambda item: (item.category, item.meal_id)):
        if template.verification_status != "verified":
            continue
        if (
            inputs.preference_snapshot is not None
            and template.meal_id in inputs.preference_snapshot.excluded_meal_ids
        ):
            continue
        items: list[tuple[PlannerMealIngredient, PlannerFood]] = []
        missing_required = False
        for item in template.items:
            if not _valid_portion_bounds(
                item.min_grams,
                item.reference_grams,
                item.max_grams,
                item.is_required,
            ):
                missing_required = True
                break
            food = foods_by_id.get(item.food_id)
            if food is None:
                if item.is_required:
                    missing_required = True
                    break
                continue
            items.append((item, food))
        recipe_foods: list[tuple[str, PlannerFood]] = []
        if template.prepared_recipe is not None:
            for ingredient in template.prepared_recipe.definition.ingredients:
                food = foods_by_id.get(str(ingredient.food_id))
                if food is None:
                    missing_required = True
                    break
                recipe_foods.append((str(ingredient.food_id), food))
            if not missing_required and template.prepared_recipe is not None:
                try:
                    calculate_prepared_recipe(
                        template.prepared_recipe.definition,
                        {
                            food_id: PreparedRecipeFood(
                                food_id=food_id,
                                nutrients_per_100g=food.nutrients_per_100g,
                                price_irr_per_gram=food.price_irr_per_gram,
                                price_reference_id=food.price_reference_id,
                            )
                            for food_id, food in recipe_foods
                        },
                    )
                except ValueError:
                    missing_required = True
        if not missing_required and (items or recipe_foods):
            eligible.append(
                EligibleMealTemplate(
                    template=template,
                    items=tuple(items),
                    prepared_recipe_foods=tuple(recipe_foods),
                )
            )
    return tuple(eligible)


def _valid_portion_bounds(
    minimum: Decimal,
    reference: Decimal,
    maximum: Decimal,
    is_required: bool,
) -> bool:
    if not all(value.is_finite() for value in (minimum, reference, maximum)):
        return False
    if minimum < ZERO or maximum <= ZERO or not minimum <= reference <= maximum:
        return False
    return not is_required or min(minimum, reference, maximum) > ZERO


def _rank_templates(
    inputs: PlannerInput,
    templates: tuple[EligibleMealTemplate, ...],
    policy: PlannerPolicy,
) -> tuple[EligibleMealTemplate, ...]:
    def score(candidate: EligibleMealTemplate) -> tuple[Decimal, str]:
        nutrients: dict[str, Decimal] = {}
        cost = ZERO
        preference = ZERO
        for item, food in candidate.items:
            for code, value in food.nutrients_per_100g.items():
                nutrients[code] = nutrients.get(code, ZERO) + value * item.reference_grams / HUNDRED
            cost += food.price_irr_per_gram * item.reference_grams
            preference += (Decimal("1") if food.food_id in inputs.liked_food_ids else ZERO) - (
                Decimal("1") if food.food_id in inputs.disliked_food_ids else ZERO
            )
        if candidate.template.prepared_recipe is not None:
            calculation = calculate_prepared_recipe(
                candidate.template.prepared_recipe.definition,
                {
                    food_id: PreparedRecipeFood(
                        food_id=food_id,
                        nutrients_per_100g=food.nutrients_per_100g,
                        price_irr_per_gram=food.price_irr_per_gram,
                        price_reference_id=food.price_reference_id,
                    )
                    for food_id, food in candidate.prepared_recipe_foods
                },
            )
            for code, value in calculation.total_nutrients:
                nutrients[code] = nutrients.get(code, ZERO) + value
            cost += calculation.total_cost_irr
        micronutrient_adequacy = sum(
            (
                min(nutrients.get(code, ZERO) / target, Decimal("1"))
                for code, target in inputs.micronutrient_targets.items()
                if target > ZERO
            ),
            ZERO,
        )
        energy = max(nutrients.get("energy_kcal", ZERO), Decimal("1"))
        value = (
            micronutrient_adequacy * policy.micronutrient_score_weight
            + preference * policy.preference_score_weight
            - (cost / energy) * policy.cost_score_weight / Decimal("10000")
        )
        return -value, candidate.template.meal_id

    return tuple(sorted(templates, key=score))


def _build_days(
    inputs: PlannerInput,
    main_templates: tuple[EligibleMealTemplate, ...],
    snack_templates: tuple[EligibleMealTemplate, ...],
    policy: PlannerPolicy,
    *,
    maximum_recipe_cost_irr: Decimal,
    optimization_cache: dict[tuple[object, ...], PlannedFood],
) -> tuple[PlannedDay, ...]:
    if inputs.template_schedule is not None:
        return _build_scheduled_days(
            inputs,
            (*main_templates, *snack_templates),
            policy,
            maximum_recipe_cost_irr=maximum_recipe_cost_irr,
            optimization_cache=optimization_cache,
        )
    daily_kcal = inputs.daily_targets["goal_calories"]
    snack_total_share = policy.snack_energy_share if inputs.snacks_per_day else ZERO
    main_slot_kcal = (
        daily_kcal * (Decimal("1") - snack_total_share) / Decimal(inputs.main_meals_per_day)
    )
    snack_slot_kcal = (
        daily_kcal * snack_total_share / Decimal(inputs.snacks_per_day)
        if inputs.snacks_per_day
        else ZERO
    )
    days: list[PlannedDay] = []
    for day_index in range(7):
        meals: list[PlannedMeal] = []
        for slot_index in range(inputs.main_meals_per_day):
            sequence = day_index * inputs.main_meals_per_day + slot_index
            template = main_templates[sequence % len(main_templates)]
            meals.append(
                _meal_from_template(
                    "main_meal",
                    slot_index,
                    template,
                    main_slot_kcal,
                    maximum_recipe_cost_irr=maximum_recipe_cost_irr,
                    optimization_cache=optimization_cache,
                )
            )
        for slot_index in range(inputs.snacks_per_day):
            sequence = day_index * max(inputs.snacks_per_day, 1) + slot_index
            template = snack_templates[sequence % len(snack_templates)]
            meals.append(
                _meal_from_template(
                    "snack",
                    slot_index,
                    template,
                    snack_slot_kcal,
                    maximum_recipe_cost_irr=maximum_recipe_cost_irr,
                    optimization_cache=optimization_cache,
                )
            )
        days.append(_day(day_index, tuple(meals)))
    return tuple(days)


def _determine_substitution_reason(
    requested: PlannerMealTemplate | None,
    all_foods_by_id: dict[str, PlannerFood],
    constraints: tuple[NormalizedFoodConstraint, ...],
) -> str:
    if requested is None:
        return "SCHEDULED_TEMPLATE_UNAVAILABLE"
    if constraints:
        for item in requested.items:
            food = all_foods_by_id.get(item.food_id)
            if food is not None:
                for constraint in constraints:
                    if constraint.severity == ConstraintSeverity.HARD:
                        decision = evaluate_food_constraints(
                            constraints=(constraint,),
                            slug=food.slug,
                            name_fa=food.name_fa,
                            name_en=food.name_en,
                            allergen_tags=food.allergen_tags,
                            allergen_metadata_verified=food.allergen_metadata_verified,
                        )
                        if decision.is_hard_blocked:
                            if constraint.source == "allergy":
                                return "MEAL_SUBSTITUTED_FOR_ALLERGY"
                            if constraint.source == "intolerance":
                                return "MEAL_SUBSTITUTED_FOR_INTOLERANCE"
                            return "MEAL_SUBSTITUTED_FOR_HARD_EXCLUSION"
        if requested.prepared_recipe is not None:
            for ingredient in requested.prepared_recipe.definition.ingredients:
                recipe_food = all_foods_by_id.get(str(ingredient.food_id))
                if recipe_food is not None:
                    for constraint in constraints:
                        if constraint.severity == ConstraintSeverity.HARD:
                            decision = evaluate_food_constraints(
                                constraints=(constraint,),
                                slug=recipe_food.slug,
                                name_fa=recipe_food.name_fa,
                                name_en=recipe_food.name_en,
                                allergen_tags=recipe_food.allergen_tags,
                                allergen_metadata_verified=recipe_food.allergen_metadata_verified,
                            )
                            if decision.is_hard_blocked:
                                if constraint.source == "allergy":
                                    return "MEAL_SUBSTITUTED_FOR_ALLERGY"
                                if constraint.source == "intolerance":
                                    return "MEAL_SUBSTITUTED_FOR_INTOLERANCE"
                                return "MEAL_SUBSTITUTED_FOR_HARD_EXCLUSION"
    return "SCHEDULED_TEMPLATE_UNAVAILABLE"


def _build_scheduled_days(
    inputs: PlannerInput,
    templates: tuple[EligibleMealTemplate, ...],
    policy: PlannerPolicy,
    *,
    maximum_recipe_cost_irr: Decimal,
    optimization_cache: dict[tuple[object, ...], PlannedFood],
) -> tuple[PlannedDay, ...]:
    raw_templates = tuple(candidate.template for candidate in templates)
    all_foods = {food.food_id: food for template in templates for _item, food in template.items}
    variants = _build_scheduled_day_variants(
        inputs,
        templates,
        templates,
        raw_templates,
        policy,
        maximum_recipe_cost_irr=maximum_recipe_cost_irr,
        optimization_cache=optimization_cache,
        all_foods_by_id=all_foods,
    )
    return variants[0].days


def _build_scheduled_day_variants(
    inputs: PlannerInput,
    main_templates: tuple[EligibleMealTemplate, ...],
    snack_templates: tuple[EligibleMealTemplate, ...],
    all_templates: tuple[PlannerMealTemplate, ...],
    policy: PlannerPolicy,
    *,
    maximum_recipe_cost_irr: Decimal,
    optimization_cache: dict[tuple[object, ...], PlannedFood],
    all_foods_by_id: dict[str, PlannerFood] | None = None,
) -> tuple[_ScheduledWeekVariant, ...]:
    all_foods = all_foods_by_id if all_foods_by_id is not None else {}
    if len(inputs.template_schedule or ()) != 7:
        raise ValueError("Template schedule must contain exactly seven days")
    eligible_templates = tuple(
        sorted(
            {
                candidate.template.meal_id: candidate
                for candidate in (*main_templates, *snack_templates)
            }.values(),
            key=lambda candidate: candidate.template.meal_id,
        )
    )
    by_id = {candidate.template.meal_id: candidate for candidate in eligible_templates}
    requested_by_id = {template.meal_id: template for template in all_templates}
    schedule = inputs.template_schedule or ()
    pending_slots = _pending_schedule_slots(schedule)
    initial_usage = _scheduled_template_usage(schedule, by_id)
    empty_days = tuple(() for _ in schedule)
    states: tuple[PartialWeekVariant, ...] = (
        PartialWeekVariant(
            days_built=empty_days,
            pending_slots=pending_slots,
            substitutions=(),
            partial_quality_lower_bound=(),
            stable_variant_key=("base",),
            usage=tuple(sorted(initial_usage.items())),
        ),
    )
    while states and states[0].pending_slots:
        day_index, slot_index, role, requested_id, category = states[0].pending_slots[0]
        next_states: list[PartialWeekVariant] = []
        first_failure: NoCompatibleTemplateSubstituteError | None = None
        for state in states:
            usage = dict(state.usage)
            if requested_id is None:
                selected_days = [list(day) for day in state.days_built]
                selected_days[day_index].append(None)
                next_states.append(
                    PartialWeekVariant(
                        days_built=tuple(tuple(day) for day in selected_days),
                        pending_slots=state.pending_slots[1:],
                        substitutions=state.substitutions,
                        partial_quality_lower_bound=state.partial_quality_lower_bound,
                        stable_variant_key=state.stable_variant_key,
                        usage=state.usage,
                    )
                )
                continue
            requested_candidate = by_id.get(requested_id or "")
            original_available = (
                requested_candidate is not None
                and requested_candidate.template.category == category
            )
            options: tuple[EligibleMealTemplate, ...]
            if original_available:
                assert requested_candidate is not None
                options = (requested_candidate,)
            else:
                requested = requested_by_id.get(requested_id) or PlannerMealTemplate(
                    meal_id=requested_id,
                    name_fa=requested_id,
                    name_en=requested_id,
                    category=category,
                    items=(),
                )
                real_slots = [item for item in schedule[day_index] if item[1] is not None]
                snack_count = sum(item[0] == "snack" for item in real_slots)
                main_count = len(real_slots) - snack_count
                snack_share = policy.snack_energy_share if snack_count else ZERO
                target_kcal = (
                    inputs.daily_targets["goal_calories"] * snack_share / snack_count
                    if role == "snack" and snack_count
                    else inputs.daily_targets["goal_calories"]
                    * (Decimal("1") - snack_share)
                    / main_count
                )
                target_protein = inputs.daily_targets.get("protein", ZERO)
                target_protein = (
                    target_protein * snack_share / snack_count
                    if role == "snack" and snack_count
                    else target_protein * (Decimal("1") - snack_share) / main_count
                )
                context = SubstitutionContext(
                    slot_category=category,
                    target_kcal=target_kcal,
                    target_protein=target_protein,
                    template_usage=tuple(sorted(usage.items())),
                    maximum_repetition=inputs.maximum_meal_repetition_per_week,
                    liked_food_ids=inputs.liked_food_ids,
                    disliked_food_ids=inputs.disliked_food_ids,
                    day_index=day_index,
                    role=role,
                    slot_index=slot_index,
                    dietary_pattern=inputs.dietary_pattern,
                    excluded_terms=inputs.excluded_terms,
                    food_constraints=inputs.food_constraints,
                )
                options = rank_template_substitutes(
                    requested,
                    eligible_templates,
                    context,
                )[
                    : min(
                        policy.maximum_substitutes_per_slot,
                        policy.maximum_template_substitution_attempts_per_slot,
                    )
                ]
                if not options:
                    first_failure = first_failure or NoCompatibleTemplateSubstituteError(
                        day_index=day_index,
                        role=role,
                        slot_index=slot_index,
                        requested_template_id=requested_id,
                        category=category,
                        diagnostics=substitution_rejection_diagnostics(
                            requested,
                            eligible_templates,
                            context,
                        ),
                    )
                    continue
            for candidate in options:
                selected_days = [list(day) for day in state.days_built]
                selected_days[day_index].append(candidate.template.meal_id)
                action = None
                if not original_available:
                    reason = _determine_substitution_reason(
                        requested=requested_by_id.get(requested_id or ""),
                        all_foods_by_id=all_foods,
                        constraints=inputs.food_constraints,
                    )
                    action = SubstitutionAction(
                        day_index=day_index,
                        role=role,
                        slot_index=slot_index,
                        requested_template_id=requested_id or "",
                        replacement_template_id=candidate.template.meal_id,
                        reason_code=reason,
                    )
                substitutions = state.substitutions + ((action,) if action else ())
                _candidate_energy, _candidate_protein, candidate_cost = template_reference_metrics(
                    candidate
                )
                real_slots = [item for item in schedule[day_index] if item[1] is not None]
                snack_count = sum(item[0] == "snack" for item in real_slots)
                main_count = len(real_slots) - snack_count
                snack_share = policy.snack_energy_share if snack_count else ZERO
                target_kcal = (
                    inputs.daily_targets["goal_calories"] * snack_share / snack_count
                    if role == "snack" and snack_count
                    else inputs.daily_targets["goal_calories"]
                    * (Decimal("1") - snack_share)
                    / main_count
                )
                target_protein = inputs.daily_targets.get("protein", ZERO)
                target_protein = (
                    target_protein * snack_share / snack_count
                    if role == "snack" and snack_count
                    else target_protein * (Decimal("1") - snack_share) / main_count
                )
                energy_lower_bound, protein_lower_bound = _template_slot_lower_bound(
                    candidate,
                    target_kcal,
                    target_protein,
                )
                lower_bound = state.partial_quality_lower_bound + (
                    energy_lower_bound,
                    protein_lower_bound,
                    Decimal(len(substitutions)),
                    candidate_cost,
                )
                stable_key = state.stable_variant_key
                if action is not None:
                    if stable_key == ("base",):
                        stable_key = ()
                    stable_key += (
                        f"{day_index:02d}:{role}:{slot_index:02d}:{candidate.template.meal_id}",
                    )
                next_states.append(
                    PartialWeekVariant(
                        days_built=tuple(tuple(day) for day in selected_days),
                        pending_slots=state.pending_slots[1:],
                        substitutions=substitutions,
                        partial_quality_lower_bound=lower_bound,
                        stable_variant_key=stable_key,
                        usage=tuple(
                            sorted(
                                {
                                    **usage,
                                    candidate.template.meal_id: usage.get(
                                        candidate.template.meal_id, 0
                                    )
                                    + (0 if original_available else 1),
                                }.items()
                            )
                        ),
                    )
                )
        if not next_states:
            if first_failure is not None:
                raise first_failure
            break
        states = tuple(
            sorted(
                next_states,
                key=lambda state: (
                    state.partial_quality_lower_bound,
                    state.stable_variant_key,
                ),
            )[: policy.maximum_partial_variants_per_program]
        )

    max_variants = min(
        policy.maximum_full_variants_per_program,
        policy.maximum_candidate_rebuild_attempts,
    )
    variants: list[_ScheduledWeekVariant] = []
    meal_cache: dict[tuple[str, str, Decimal], PlannedMeal] = {}
    for state in states[:max_variants]:
        variants.append(
            _ScheduledWeekVariant(
                days=_materialize_scheduled_days(
                    inputs,
                    state.days_built,
                    by_id,
                    policy,
                    maximum_recipe_cost_irr=maximum_recipe_cost_irr,
                    meal_cache=meal_cache,
                    optimization_cache=optimization_cache,
                ),
                substitutions=state.substitutions,
                stable_variant_key=(state.stable_variant_key or ("base",)),
            )
        )
    return tuple(variants)


def _template_slot_lower_bound(
    candidate: EligibleMealTemplate,
    target_kcal: Decimal,
    target_protein: Decimal,
) -> tuple[Decimal, Decimal]:
    minimum_energy = ZERO
    maximum_energy = ZERO
    minimum_protein = ZERO
    maximum_protein = ZERO
    for item, food in candidate.items:
        energy = food.nutrients_per_100g.get("energy_kcal", ZERO) / HUNDRED
        protein = food.nutrients_per_100g.get("protein_g", ZERO) / HUNDRED
        minimum_energy += energy * item.min_grams
        maximum_energy += energy * item.max_grams
        minimum_protein += protein * item.min_grams
        maximum_protein += protein * item.max_grams

    def gap(target: Decimal, minimum: Decimal, maximum: Decimal) -> Decimal:
        if target <= minimum:
            return (minimum - target) / max(target, ONE)
        if target >= maximum:
            return (target - maximum) / max(target, ONE)
        return ZERO

    return (
        gap(target_kcal, minimum_energy, maximum_energy),
        gap(target_protein, minimum_protein, maximum_protein),
    )


def _pending_schedule_slots(
    schedule: tuple[tuple[tuple[str, str | None, str], ...], ...],
) -> tuple[tuple[int, int, str, str | None, str], ...]:
    pending: list[tuple[int, int, str, str | None, str]] = []
    for day_index, day in enumerate(schedule):
        role_indexes: dict[str, int] = {}
        for role, template_id, category in day:
            slot_index = role_indexes.get(role, 0)
            role_indexes[role] = slot_index + 1
            pending.append((day_index, slot_index, role, template_id, category))
    return tuple(pending)


def _scheduled_template_usage(
    schedule: tuple[tuple[tuple[str, str | None, str], ...], ...],
    eligible_by_id: dict[str, EligibleMealTemplate],
) -> dict[str, int]:
    usage: dict[str, int] = {}
    for day in schedule:
        for _role, template_id, category in day:
            candidate = eligible_by_id.get(template_id or "")
            if candidate is not None and candidate.template.category == category:
                usage[template_id or ""] = usage.get(template_id or "", 0) + 1
    return usage


def _materialize_scheduled_days(
    inputs: PlannerInput,
    selected_template_ids: tuple[tuple[str | None, ...], ...],
    by_id: dict[str, EligibleMealTemplate],
    policy: PlannerPolicy,
    *,
    maximum_recipe_cost_irr: Decimal,
    meal_cache: dict[tuple[str, str, Decimal], PlannedMeal] | None = None,
    optimization_cache: dict[tuple[object, ...], PlannedFood],
) -> tuple[PlannedDay, ...]:
    meal_cache = meal_cache if meal_cache is not None else {}
    days: list[PlannedDay] = []
    for day_index, schedule in enumerate(inputs.template_schedule or ()):
        real_slots = [slot for slot in schedule if slot[1] is not None]
        snack_count = sum(role == "snack" for role, _, _ in real_slots)
        main_count = len(real_slots) - snack_count
        snack_share = policy.snack_energy_share if snack_count else ZERO
        main_kcal = (
            inputs.daily_targets["goal_calories"] * (Decimal("1") - snack_share) / main_count
            if main_count
            else ZERO
        )
        snack_kcal = (
            inputs.daily_targets["goal_calories"] * snack_share / snack_count
            if snack_count
            else ZERO
        )
        meals: list[PlannedMeal] = []
        role_indexes: dict[str, int] = {}
        for physical_slot_index, (role, _requested_id, category) in enumerate(schedule):
            slot_index = role_indexes.get(role, 0)
            role_indexes[role] = slot_index + 1
            selected_id = selected_template_ids[day_index][physical_slot_index]
            if selected_id is None:
                meals.append(
                    PlannedMeal(
                        role=role,
                        slot_index=slot_index,
                        template_id=None,
                        template_category=category,
                        foods=(),
                        cost_irr=ZERO,
                        nutrients=(),
                    )
                )
                continue
            candidate = by_id.get(selected_id)
            if candidate is None:
                raise ScheduledTemplateUnavailableError(selected_id, category)
            target = snack_kcal if role == "snack" else main_kcal
            cache_key = (candidate.template.meal_id, role, target)
            cached_meal = meal_cache.get(cache_key)
            if cached_meal is None:
                cached_meal = _meal_from_template(
                    role,
                    slot_index,
                    candidate,
                    target,
                    maximum_recipe_cost_irr=maximum_recipe_cost_irr,
                    optimization_cache=optimization_cache,
                )
                meal_cache[cache_key] = cached_meal
            meals.append(replace(cached_meal, slot_index=slot_index))
        days.append(_day(day_index, tuple(meals)))
    return tuple(days)


def _meal_from_template(
    role: str,
    slot_index: int,
    candidate: EligibleMealTemplate,
    target_kcal: Decimal,
    *,
    maximum_recipe_cost_irr: Decimal,
    optimization_cache: dict[tuple[object, ...], PlannedFood],
) -> PlannedMeal:
    simple_reference_kcal = sum(
        (
            food.nutrients_per_100g["energy_kcal"] * item.reference_grams / HUNDRED
            for item, food in candidate.items
        ),
        ZERO,
    )
    recipe_reference_kcal = ZERO
    if candidate.template.prepared_recipe is not None:
        recipe_reference = calculate_prepared_recipe(
            candidate.template.prepared_recipe.definition,
            {
                food_id: PreparedRecipeFood(
                    food_id=food_id,
                    nutrients_per_100g=food.nutrients_per_100g,
                    price_irr_per_gram=food.price_irr_per_gram,
                    price_reference_id=food.price_reference_id,
                )
                for food_id, food in candidate.prepared_recipe_foods
            },
        )
        recipe_reference_kcal = dict(recipe_reference.total_nutrients).get("energy_kcal", ZERO)
    reference_kcal = simple_reference_kcal + recipe_reference_kcal
    scale = target_kcal / reference_kcal if reference_kcal > ZERO else Decimal("1")
    planned_foods = list(
        _portion_for_template_item(food, item, item.reference_grams * scale)
        for item, food in candidate.items
    )
    if candidate.template.prepared_recipe is not None:
        target_recipe_kcal = max(target_kcal - simple_reference_kcal * scale, ZERO)
        target_recipe_protein = target_recipe_kcal * Decimal("0.20") / Decimal("4")
        planned_foods.insert(
            0,
            _cached_optimize_prepared_recipe(
                candidate.template.prepared_recipe,
                dict(candidate.prepared_recipe_foods),
                target_kcal=target_recipe_kcal,
                target_protein=target_recipe_protein,
                maximum_cost_irr=maximum_recipe_cost_irr,
                optimization_cache=optimization_cache,
            ),
        )
    foods = tuple(planned_foods)
    return _meal(
        role,
        slot_index,
        foods,
        template_id=candidate.template.meal_id,
        template_category=candidate.template.category,
    )


def _portion_for_template_item(
    food: PlannerFood,
    item: PlannerMealIngredient,
    requested_grams: Decimal,
) -> PlannedFood:
    grams = requested_grams.quantize(Decimal("0.1"), ROUND_HALF_UP)
    grams = max(item.min_grams, min(grams, item.max_grams))
    nutrients = tuple(
        sorted(
            (code, (value * grams / HUNDRED).quantize(Decimal("0.0001")))
            for code, value in food.nutrients_per_100g.items()
        )
    )
    return PlannedFood(
        food_id=food.food_id,
        slug=food.slug,
        name_fa=food.name_fa,
        name_en=food.name_en,
        roles=food.roles,
        grams=grams,
        cost_irr=(food.price_irr_per_gram * grams).quantize(Decimal("1")),
        nutrients=nutrients,
        price_reference_id=food.price_reference_id,
        min_grams=item.min_grams,
        max_grams=item.max_grams,
        functional_role=item.functional_role,
    )


def optimize_prepared_recipe(
    recipe: PlannerPreparedRecipe,
    foods: dict[str, PlannerFood],
    *,
    target_kcal: Decimal,
    target_protein: Decimal,
    maximum_cost_irr: Decimal,
) -> PlannedFood:
    """Select a deterministic bounded recipe variant using the shared calculator."""

    if not maximum_cost_irr.is_finite() or maximum_cost_irr < ZERO:
        raise ValueError("Prepared Recipe maximum cost must be finite and non-negative")

    definition = recipe.definition
    calculation_foods = {
        food_id: PreparedRecipeFood(
            food_id=food_id,
            nutrients_per_100g=food.nutrients_per_100g,
            price_irr_per_gram=food.price_irr_per_gram,
            price_reference_id=food.price_reference_id,
        )
        for food_id, food in foods.items()
    }
    quantities = {
        ingredient.food_id: ingredient.reference_grams for ingredient in definition.ingredients
    }
    candidates: list[tuple[Decimal, Decimal, tuple[Decimal, ...], PreparedRecipeCalculation]] = []
    levels = (Decimal("0"), Decimal("0.25"), Decimal("0.5"), Decimal("0.75"), Decimal("1"))

    def search(index: int) -> None:
        if index == len(definition.ingredients):
            try:
                calculation = calculate_prepared_recipe(
                    definition, calculation_foods, quantities=quantities
                )
            except ValueError:
                return
            protein = dict(calculation.total_nutrients).get("protein_g", ZERO)
            energy = dict(calculation.total_nutrients).get("energy_kcal", ZERO)
            protein_gap = max(target_protein - protein, ZERO)
            kcal_gap = abs(target_kcal - energy)
            budget_penalty = max(calculation.total_cost_irr - maximum_cost_irr, ZERO)
            selected = tuple(
                quantities[ingredient.food_id] for ingredient in definition.ingredients
            )
            candidates.append(
                (
                    budget_penalty * Decimal("1000") + protein_gap * Decimal("100") + kcal_gap,
                    calculation.total_cost_irr,
                    selected,
                    calculation,
                )
            )
            return
        ingredient = definition.ingredients[index]
        span = ingredient.max_grams - ingredient.min_grams
        values = {ingredient.min_grams + span * level for level in levels}
        values.add(ingredient.reference_grams)
        for grams in sorted(values):
            quantities[ingredient.food_id] = grams
            search(index + 1)

    search(0)
    if not candidates:
        raise ValueError("Prepared Recipe constraints are infeasible")
    _, _, _, selected_calculation = min(candidates, key=lambda item: item[:3])
    calculation = selected_calculation
    selected_grams = {
        str(food_id): str(grams) for food_id, grams in calculation.selected_ingredient_grams
    }
    nutrients = tuple(sorted(calculation.total_nutrients))
    return PlannedFood(
        food_id=None,
        slug=f"prepared-{recipe.name_en.casefold().replace(' ', '-')}",
        name_fa=recipe.name_fa,
        name_en=recipe.name_en,
        roles=("prepared_recipe",),
        grams=calculation.final_cooked_yield_grams.quantize(Decimal("0.1"), ROUND_HALF_UP),
        cost_irr=calculation.total_cost_irr.quantize(Decimal("1")),
        nutrients=nutrients,
        price_reference_id="prepared-recipe",
        min_grams=ZERO,
        max_grams=calculation.final_cooked_yield_grams,
        functional_role=None,
        item_kind="prepared_recipe",
        recipe_snapshot={
            "revision_id": recipe.revision_id,
            "calculation_version": calculation.calculation_version,
            "verification_status": recipe.verification_status,
            "provenance": recipe.provenance,
            "data_gaps": list(recipe.data_gaps),
            "selected_ingredient_grams": selected_grams,
            "ingredients": [
                {
                    "food_id": food_id,
                    "slug": foods[food_id].slug,
                    "name_fa": foods[food_id].name_fa,
                    "name_en": foods[food_id].name_en,
                    "grams": selected_grams[food_id],
                    "cost_irr": str(
                        foods[food_id].price_irr_per_gram * Decimal(selected_grams[food_id])
                    ),
                    "nutrients": {
                        code: str(value * Decimal(selected_grams[food_id]) / HUNDRED)
                        for code, value in foods[food_id].nutrients_per_100g.items()
                    },
                    "price_reference_id": foods[food_id].price_reference_id,
                }
                for food_id in sorted(foods)
            ],
            "final_cooked_yield_grams": str(calculation.final_cooked_yield_grams),
            "nutrients_per_100g": {
                code: str(value) for code, value in calculation.nutrients_per_100g.items()
            },
            "total_cost_irr": str(calculation.total_cost_irr),
            "cost_irr_per_100g": str(calculation.cost_irr_per_100g),
            "price_reference_ids": list(calculation.price_reference_ids),
        },
    )


def _meal(
    role: str,
    slot_index: int,
    foods: tuple[PlannedFood, ...],
    *,
    template_id: str | None,
    template_category: str,
) -> PlannedMeal:
    nutrients = _sum_nutrients(food.nutrients for food in foods)
    return PlannedMeal(
        role=role,
        slot_index=slot_index,
        template_id=template_id,
        template_category=template_category,
        foods=foods,
        cost_irr=sum((food.cost_irr for food in foods), ZERO),
        nutrients=tuple(sorted(nutrients.items())),
    )


def _day(day_index: int, meals: tuple[PlannedMeal, ...]) -> PlannedDay:
    nutrients = _sum_nutrients(meal.nutrients for meal in meals)
    return PlannedDay(
        day_index=day_index,
        meals=meals,
        cost_irr=sum((meal.cost_irr for meal in meals), ZERO),
        nutrients=tuple(sorted(nutrients.items())),
    )


def _cached_optimize_prepared_recipe(
    recipe: PlannerPreparedRecipe,
    foods: dict[str, PlannerFood],
    *,
    target_kcal: Decimal,
    target_protein: Decimal,
    maximum_cost_irr: Decimal,
    optimization_cache: dict[tuple[object, ...], PlannedFood],
) -> PlannedFood:
    food_key = tuple(
        (
            food_id,
            food.price_irr_per_gram,
            food.price_reference_id,
            tuple(sorted(food.nutrients_per_100g.items())),
        )
        for food_id, food in sorted(foods.items())
    )
    key = (
        recipe.revision_id,
        recipe.definition,
        food_key,
        target_kcal,
        target_protein,
        maximum_cost_irr,
    )
    cached = optimization_cache.get(key)
    if cached is not None:
        return cached
    result = optimize_prepared_recipe(
        recipe,
        foods,
        target_kcal=target_kcal,
        target_protein=target_protein,
        maximum_cost_irr=maximum_cost_irr,
    )
    optimization_cache[key] = result
    return result


def _repair_micronutrients(
    days: tuple[PlannedDay, ...],
    inputs: PlannerInput,
    foods_by_id: dict[str, PlannerFood],
    policy: PlannerPolicy,
) -> tuple[tuple[PlannedDay, ...], tuple[RepairAction, ...]]:
    mutable_days = list(days)
    actions: list[RepairAction] = []
    for nutrient_code, target in sorted(inputs.micronutrient_targets.items()):
        weekly = _sum_nutrients(day.nutrients for day in mutable_days).get(nutrient_code, ZERO)
        if weekly >= target * Decimal("7"):
            continue
        candidates = [
            (day_index, meal_index, food.food_id, food)
            for day_index, day in enumerate(mutable_days)
            for meal_index, meal in enumerate(day.meals)
            for food in meal.foods
            if food.food_id is not None
            and food.grams < food.max_grams
            and foods_by_id[food.food_id].nutrients_per_100g.get(nutrient_code, ZERO) > ZERO
        ]
        if not candidates:
            continue
        candidates.sort(
            key=lambda candidate: (
                -(
                    foods_by_id[candidate[2]].nutrients_per_100g[nutrient_code]
                    / foods_by_id[candidate[2]].nutrients_per_100g["energy_kcal"]
                ),
                candidate[3].slug,
                candidate[0],
                candidate[1],
            )
        )
        for day_index, target_meal_index, selected_food_id, selected in candidates[
            : policy.maximum_repair_iterations
        ]:
            day = mutable_days[day_index]
            meal = day.meals[target_meal_index]
            source = foods_by_id[selected_food_id]
            added_grams = min(policy.repair_portion_g, selected.max_grams - selected.grams)
            resized = _resize_planned_food(selected, source, selected.grams + added_grams)
            repaired_meal = _meal(
                meal.role,
                meal.slot_index,
                tuple(resized if food.food_id == selected.food_id else food for food in meal.foods),
                template_id=meal.template_id,
                template_category=meal.template_category,
            )
            repaired_meals = list(day.meals)
            repaired_meals[target_meal_index] = repaired_meal
            candidate_days = list(mutable_days)
            candidate_days[day_index] = _day(day.day_index, tuple(repaired_meals))
            candidate_totals = _sum_nutrients(item.nutrients for item in candidate_days)
            candidate_average = {
                code: value / Decimal("7") for code, value in candidate_totals.items()
            }
            candidate_cost = sum((item.cost_irr for item in candidate_days), ZERO)
            budget_cap = Decimal(inputs.weekly_budget_irr) * (
                Decimal("1")
                if inputs.budget_mode == "strict"
                else Decimal("1") + policy.flexible_budget_overage_cap
            )
            if (
                _upper_limit_exceeded(inputs, candidate_average)
                or _validate_nutritional_feasibility(inputs, candidate_average, policy)
                or candidate_cost > budget_cap
            ):
                continue
            mutable_days = candidate_days
            actions.append(RepairAction(nutrient_code, selected.slug, added_grams, day_index))
            weekly += source.nutrients_per_100g[nutrient_code] * added_grams / HUNDRED
            if weekly >= target * Decimal("7"):
                break
        if len(actions) >= policy.maximum_repair_iterations:
            break
    return tuple(mutable_days), tuple(actions)


def _repair_portions(
    days: tuple[PlannedDay, ...],
    inputs: PlannerInput,
    foods_by_id: dict[str, PlannerFood],
    policy: PlannerPolicy,
) -> tuple[tuple[PlannedDay, ...], tuple[PortionAdjustmentAction, ...], tuple[str, ...]]:
    target_values = {
        TARGET_NUTRIENT_CODES.get(code, code): value
        for code, value in inputs.daily_targets.items()
        if TARGET_NUTRIENT_CODES.get(code, code)
        in {"energy_kcal", "protein_g", "carbohydrate_g", "total_fat_g", "fibre_g"}
    }
    minimum_values = {
        TARGET_NUTRIENT_CODES.get(code, code): value
        for code, value in inputs.daily_minimums.items()
    }
    maximum_values = {
        TARGET_NUTRIENT_CODES.get(code, code): value
        for code, value in inputs.daily_maximums.items()
    }
    upper_limits = dict(inputs.micronutrient_upper_limits)
    repaired_days = list(days)
    actions: list[PortionAdjustmentAction] = []
    reasons: list[str] = []

    for day_index, day in enumerate(days):
        variables: list[PortionVariable] = []
        locations: dict[str, tuple[int, int, PlannerFood]] = {}
        for meal_index, meal in enumerate(day.meals):
            for food_index, planned in enumerate(meal.foods):
                if planned.food_id is None:
                    continue
                source = foods_by_id.get(planned.food_id)
                if source is None:
                    continue
                key = f"{day_index}:{meal.role}:{meal.slot_index}:{food_index}:{planned.food_id}"
                variables.append(
                    PortionVariable(
                        key=key,
                        day_index=day_index,
                        role=meal.role,
                        slot_index=meal.slot_index,
                        food_id=planned.food_id,
                        grams=planned.grams,
                        reference_grams=planned.grams,
                        min_grams=planned.min_grams,
                        max_grams=planned.max_grams,
                        nutrients_per_gram=tuple(
                            sorted(
                                (code, value / HUNDRED)
                                for code, value in source.nutrients_per_100g.items()
                            )
                        ),
                        cost_per_gram=source.price_irr_per_gram,
                    )
                )
                locations[key] = (meal_index, food_index, source)
        if not variables:
            continue
        solver_result = solve_portions(
            variables=tuple(variables),
            initial_totals=dict(day.nutrients),
            targets=target_values,
            minimums=minimum_values,
            maximums=maximum_values,
            upper_limits=upper_limits,
            increment_g=policy.portion_adjustment_increment_g,
            maximum_iterations=policy.maximum_portion_solver_iterations,
            target_tolerance_ratio=policy.calorie_tolerance_ratio,
        )
        replacements = dict(solver_result.grams_by_key)
        meals = list(day.meals)
        for key, grams in replacements.items():
            meal_index, food_index, source = locations[key]
            planned = meals[meal_index].foods[food_index]
            if grams == planned.grams:
                continue
            resized = _resize_planned_food(planned, source, grams)
            meal_foods = list(meals[meal_index].foods)
            meal_foods[food_index] = resized
            meals[meal_index] = _meal(
                meals[meal_index].role,
                meals[meal_index].slot_index,
                tuple(meal_foods),
                template_id=meals[meal_index].template_id,
                template_category=meals[meal_index].template_category,
            )
        repaired_days[day_index] = _day(day.day_index, tuple(meals))
        actions.extend(solver_result.actions)
        reasons.extend(solver_result.reason_codes)

    return tuple(repaired_days), tuple(actions), tuple(dict.fromkeys(sorted(reasons)))


def _resize_planned_food(planned: PlannedFood, source: PlannerFood, grams: Decimal) -> PlannedFood:
    if planned.food_id is None:
        raise ValueError("Prepared Recipe outputs cannot be resized as Food Catalogue items")
    item = PlannerMealIngredient(
        food_id=planned.food_id,
        reference_grams=planned.grams,
        min_grams=planned.min_grams,
        max_grams=planned.max_grams,
        is_required=True,
        functional_role=planned.functional_role,
    )
    return _portion_for_template_item(source, item, grams)


def _sum_nutrients(
    rows: Iterable[tuple[tuple[str, Decimal], ...]],
) -> dict[str, Decimal]:
    totals: dict[str, Decimal] = {}
    for row in rows:
        for code, value in row:
            totals[code] = totals.get(code, ZERO) + value
    return totals


def _comparisons(
    inputs: PlannerInput,
    daily_average: dict[str, Decimal],
    data_completeness: dict[str, Decimal],
    policy: PlannerPolicy,
) -> dict[str, NutrientComparison]:
    comparisons: dict[str, NutrientComparison] = {}
    metrics = {
        **inputs.daily_targets,
        **inputs.micronutrient_targets,
        **inputs.daily_maximums,
    }
    for code, preferred in metrics.items():
        nutrient_code = TARGET_NUTRIENT_CODES.get(code, code)
        planned = daily_average.get(nutrient_code, ZERO)
        minimum = inputs.daily_minimums.get(code)
        maximum = inputs.daily_maximums.get(code) or inputs.micronutrient_upper_limits.get(code)
        complete = data_completeness.get(nutrient_code, Decimal("1"))
        reasons: tuple[str, ...]
        if complete < policy.micronutrient_data_completeness_threshold:
            status = "data_incomplete"
            reasons = ("NUTRIENT_DATA_INCOMPLETE",)
            confidence = "low"
        elif maximum is not None and planned > maximum:
            status = "above_applicable_limit"
            reasons = ("ABOVE_APPLICABLE_LIMIT",)
            confidence = "high"
        elif minimum is not None and planned < minimum:
            status = "below_minimum"
            reasons = ("BELOW_MINIMUM",)
            confidence = "high"
        elif planned < preferred:
            status = (
                "below_preferred_but_acceptable"
                if minimum is not None
                else "below_reference_target"
            )
            reasons = ("DIETARY_REFERENCE_GAP",)
            confidence = "high"
        else:
            status = "within_target"
            reasons = ()
            confidence = "high"
        comparisons[code] = NutrientComparison(
            preferred=preferred,
            minimum_or_maximum=minimum if minimum is not None else maximum,
            planned=planned,
            difference_from_preferred=planned - preferred,
            difference_from_limit=(
                planned - maximum
                if maximum is not None
                else planned - minimum
                if minimum is not None
                else None
            ),
            status=status,
            reason_codes=reasons,
            data_confidence=confidence,
        )
    for code, maximum in inputs.micronutrient_upper_limits.items():
        if code not in comparisons:
            planned = daily_average.get(code, ZERO)
            comparisons[code] = NutrientComparison(
                preferred=None,
                minimum_or_maximum=maximum,
                planned=planned,
                difference_from_preferred=None,
                difference_from_limit=planned - maximum,
                status=("above_applicable_limit" if planned > maximum else "within_target"),
                reason_codes=("ABOVE_APPLICABLE_LIMIT",) if planned > maximum else (),
            )
    return comparisons


def _nutrient_data_completeness(
    days: tuple[PlannedDay, ...], inputs: PlannerInput
) -> dict[str, Decimal]:
    requested = {
        *inputs.micronutrient_targets,
        *inputs.micronutrient_upper_limits,
        *(TARGET_NUTRIENT_CODES.get(code, code) for code in inputs.daily_maximums),
    }
    total_energy = ZERO
    known_energy = {code: ZERO for code in requested}
    for day in days:
        for meal in day.meals:
            for food in meal.foods:
                nutrients = dict(food.nutrients)
                energy = nutrients.get("energy_kcal", ZERO)
                total_energy += energy
                for code in requested:
                    if code in nutrients:
                        known_energy[code] += energy
    if total_energy <= ZERO:
        return {code: ZERO for code in requested}
    return {code: value / total_energy for code, value in known_energy.items()}


def _validate_nutritional_feasibility(
    inputs: PlannerInput,
    daily_average: dict[str, Decimal],
    policy: PlannerPolicy,
) -> tuple[str, ...]:
    goal = inputs.daily_targets["goal_calories"]
    energy = daily_average.get("energy_kcal", ZERO)
    reasons: list[str] = []
    if goal > ZERO and abs(energy - goal) / goal > policy.calorie_tolerance_ratio:
        reasons.append("CALORIE_TARGET_OUTSIDE_TOLERANCE")
    if any(
        daily_average.get(TARGET_NUTRIENT_CODES.get(code, code), ZERO) < minimum
        for code, minimum in inputs.daily_minimums.items()
        if code in {"protein", "carbohydrate", "total_fat"}
    ):
        reasons.append("MACRONUTRIENT_FLOOR_NOT_MET")
    if any(
        daily_average.get(TARGET_NUTRIENT_CODES.get(code, code), ZERO)
        > maximum * (Decimal("1") + policy.macro_tolerance_ratio)
        for code, maximum in inputs.daily_maximums.items()
        if code in {"carbohydrate", "total_fat"}
    ):
        reasons.append("MACRONUTRIENT_MAXIMUM_EXCEEDED")
    return tuple(reasons)


def _upper_limit_exceeded(inputs: PlannerInput, daily_average: dict[str, Decimal]) -> bool:
    return any(
        daily_average.get(code, ZERO) > maximum
        for code, maximum in inputs.micronutrient_upper_limits.items()
    )


def _warning_codes(
    inputs: PlannerInput,
    daily_average: dict[str, Decimal],
    budget_status: str,
    data_completeness: dict[str, Decimal],
    days: tuple[PlannedDay, ...],
) -> tuple[str, ...]:
    warnings = [
        "MICRONUTRIENT_REFERENCE_GAP"
        for code, target in inputs.micronutrient_targets.items()
        if daily_average.get(code, ZERO) < target
    ]
    if budget_status == "flexible_overage":
        warnings.append("FLEXIBLE_BUDGET_OVERAGE")
    if any(
        value < DEFAULT_POLICY.micronutrient_data_completeness_threshold
        for value in data_completeness.values()
    ):
        warnings.append("NUTRIENT_DATA_INCOMPLETE")
    signatures = [
        tuple(food.slug for food in meal.foods)
        for day in days
        for meal in day.meals
        if meal.role == "main_meal"
    ]
    if any(
        signatures.count(signature) > inputs.maximum_meal_repetition_per_week
        for signature in set(signatures)
    ):
        warnings.append("REPETITION_LIMIT_RELAXED")
    return tuple(dict.fromkeys(warnings))


def _failure(outcome: GenerationOutcome, reason: str) -> PlannerResult:
    return PlannerResult(outcome=outcome, reason_codes=(reason,))
