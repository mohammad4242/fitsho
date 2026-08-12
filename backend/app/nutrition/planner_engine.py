from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from enum import StrEnum

from app.nutrition.planner_policy import DEFAULT_POLICY, PlannerPolicy

ZERO = Decimal("0")
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


@dataclass(frozen=True)
class EligibleMealTemplate:
    template: PlannerMealTemplate
    items: tuple[tuple[PlannerMealIngredient, PlannerFood], ...]


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


@dataclass(frozen=True)
class PlannedFood:
    food_id: str
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

    def __post_init__(self) -> None:
        if self.nutrient_comparisons is None:
            object.__setattr__(self, "nutrient_comparisons", {})


def plan_week(
    inputs: PlannerInput,
    foods: tuple[PlannerFood, ...],
    meal_templates: tuple[PlannerMealTemplate, ...],
    policy: PlannerPolicy = DEFAULT_POLICY,
) -> PlannerResult:
    _validate_inputs(inputs)
    eligible = tuple(
        sorted(
            (
                food
                for food in foods
                if food.price_irr_per_gram > ZERO
                and _has_mandatory_nutrients(food)
                and not _excluded(food, inputs.excluded_terms)
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
        return _failure(GenerationOutcome.LIVE_PRICE_UNAVAILABLE, "INSUFFICIENT_PRICE_COVERAGE")

    days = _build_days(inputs, main_templates, snack_templates, policy)
    foods_by_id = {food.food_id: food for food in eligible}
    days, repairs = _repair_micronutrients(days, inputs, foods_by_id, policy)
    weekly_totals = _sum_nutrients(day.nutrients for day in days)
    daily_average = {code: value / Decimal("7") for code, value in weekly_totals.items()}
    data_completeness = _nutrient_data_completeness(days, inputs)
    comparisons = _comparisons(inputs, daily_average, data_completeness, policy)
    if _upper_limit_exceeded(inputs, daily_average):
        return PlannerResult(
            outcome=GenerationOutcome.INFEASIBLE,
            reason_codes=("NUTRIENT_UPPER_LIMIT_EXCEEDED",),
            nutrient_comparisons=comparisons,
            repair_actions=repairs,
        )

    validation = _validate_nutritional_feasibility(inputs, daily_average, policy)
    if validation:
        return PlannerResult(
            outcome=GenerationOutcome.TARGET_INFEASIBLE,
            reason_codes=validation,
            nutrient_comparisons=comparisons,
            repair_actions=repairs,
        )

    cost = sum((day.cost_irr for day in days), ZERO).quantize(Decimal("1"))
    allowance = Decimal(inputs.weekly_budget_irr)
    if inputs.budget_mode == "strict" and cost > allowance:
        return PlannerResult(
            outcome=GenerationOutcome.INFEASIBLE,
            reason_codes=("STRICT_BUDGET_EXCEEDED",),
            weekly_cost_irr=cost,
            budget_status="over_budget",
            nutrient_comparisons=comparisons,
            repair_actions=repairs,
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
        items: list[tuple[PlannerMealIngredient, PlannerFood]] = []
        missing_required = False
        for item in template.items:
            food = foods_by_id.get(item.food_id)
            if food is None:
                if item.is_required:
                    missing_required = True
                    break
                continue
            items.append((item, food))
        if not missing_required and items:
            eligible.append(EligibleMealTemplate(template=template, items=tuple(items)))
    return tuple(eligible)


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
) -> tuple[PlannedDay, ...]:
    if inputs.template_schedule is not None:
        return _build_scheduled_days(inputs, (*main_templates, *snack_templates), policy)
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
            meals.append(_meal_from_template("main_meal", slot_index, template, main_slot_kcal))
        for slot_index in range(inputs.snacks_per_day):
            sequence = day_index * max(inputs.snacks_per_day, 1) + slot_index
            template = snack_templates[sequence % len(snack_templates)]
            meals.append(_meal_from_template("snack", slot_index, template, snack_slot_kcal))
        days.append(_day(day_index, tuple(meals)))
    return tuple(days)


def _build_scheduled_days(
    inputs: PlannerInput,
    templates: tuple[EligibleMealTemplate, ...],
    policy: PlannerPolicy,
) -> tuple[PlannedDay, ...]:
    if len(inputs.template_schedule or ()) != 7:
        raise ValueError("Template schedule must contain exactly seven days")
    by_id = {candidate.template.meal_id: candidate for candidate in templates}
    days: list[PlannedDay] = []
    for day_index, schedule in enumerate(inputs.template_schedule or ()):
        real_slots = [slot for slot in schedule if slot[1] is not None]
        snack_count = sum(role == "snack" for role, _, _ in real_slots)
        main_count = len(real_slots) - snack_count
        snack_share = policy.snack_energy_share if snack_count else ZERO
        main_kcal = (
            inputs.daily_targets["goal_calories"] * (Decimal("1") - snack_share) / main_count
        )
        snack_kcal = (
            inputs.daily_targets["goal_calories"] * snack_share / snack_count
            if snack_count
            else ZERO
        )
        meals: list[PlannedMeal] = []
        role_indexes: dict[str, int] = {}
        for role, template_id, category in schedule:
            slot_index = role_indexes.get(role, 0)
            role_indexes[role] = slot_index + 1
            if template_id is None:
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
            candidate = by_id.get(template_id)
            if candidate is None:
                raise ValueError(f"Scheduled Meal Catalogue template is unavailable: {template_id}")
            target = snack_kcal if role == "snack" else main_kcal
            meals.append(_meal_from_template(role, slot_index, candidate, target))
        days.append(_day(day_index, tuple(meals)))
    return tuple(days)


def _meal_from_template(
    role: str,
    slot_index: int,
    candidate: EligibleMealTemplate,
    target_kcal: Decimal,
) -> PlannedMeal:
    reference_kcal = sum(
        (
            food.nutrients_per_100g["energy_kcal"] * item.reference_grams / HUNDRED
            for item, food in candidate.items
        ),
        ZERO,
    )
    scale = target_kcal / reference_kcal if reference_kcal > ZERO else Decimal("1")
    foods = tuple(
        _portion_for_template_item(food, item, item.reference_grams * scale)
        for item, food in candidate.items
    )
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
            (day_index, meal_index, food)
            for day_index, day in enumerate(mutable_days)
            for meal_index, meal in enumerate(day.meals)
            for food in meal.foods
            if food.grams < food.max_grams
            and foods_by_id[food.food_id].nutrients_per_100g.get(nutrient_code, ZERO) > ZERO
        ]
        if not candidates:
            continue
        candidates.sort(
            key=lambda candidate: (
                -(
                    foods_by_id[candidate[2].food_id].nutrients_per_100g[nutrient_code]
                    / foods_by_id[candidate[2].food_id].nutrients_per_100g["energy_kcal"]
                ),
                candidate[2].slug,
                candidate[0],
                candidate[1],
            )
        )
        for day_index, target_meal_index, selected in candidates[
            : policy.maximum_repair_iterations
        ]:
            day = mutable_days[day_index]
            meal = day.meals[target_meal_index]
            source = foods_by_id[selected.food_id]
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


def _resize_planned_food(planned: PlannedFood, source: PlannerFood, grams: Decimal) -> PlannedFood:
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
