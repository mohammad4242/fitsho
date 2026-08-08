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
    liked_terms: tuple[str, ...]
    disliked_terms: tuple[str, ...]
    dietary_pattern: str
    maximum_meal_repetition_per_week: int


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


@dataclass(frozen=True)
class PlannedMeal:
    role: str
    slot_index: int
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
    proteins = _rank_candidates(
        inputs, tuple(food for food in eligible if "main_protein" in food.roles), policy
    )
    staples = _rank_candidates(
        inputs, tuple(food for food in eligible if "main_staple" in food.roles), policy
    )
    snacks = _rank_candidates(
        inputs,
        tuple(
            food
            for food in eligible
            if "snack" in food.roles
            and "main_protein" not in food.roles
            and "main_staple" not in food.roles
        ),
        policy,
    )
    flexible = _rank_candidates(
        inputs, tuple(food for food in eligible if "flexible" in food.roles), policy
    )
    if (
        len(proteins) < policy.minimum_main_protein_candidates
        or len(staples) < policy.minimum_main_staple_candidates
        or (inputs.snacks_per_day and len(snacks) < policy.minimum_snack_candidates)
    ):
        return _failure(GenerationOutcome.LIVE_PRICE_UNAVAILABLE, "INSUFFICIENT_PRICE_COVERAGE")

    days = _build_days(inputs, proteins, staples, snacks, flexible, policy)
    days, repairs = _repair_micronutrients(days, inputs, flexible, policy)
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
        name = f"{food.slug} {food.name_fa}".casefold()
        preference = sum(
            (Decimal("1") for term in inputs.liked_terms if term.casefold() in name),
            ZERO,
        ) - sum(
            (Decimal("1") for term in inputs.disliked_terms if term.casefold() in name),
            ZERO,
        )
        cost_per_kcal = food.price_irr_per_gram * HUNDRED / energy
        value = (
            micronutrient_adequacy * policy.micronutrient_score_weight
            + preference * policy.preference_score_weight
            - cost_per_kcal * policy.cost_score_weight / Decimal("10000")
        )
        return (-value, food.slug)

    return tuple(sorted(foods, key=score))


def _build_days(
    inputs: PlannerInput,
    proteins: tuple[PlannerFood, ...],
    staples: tuple[PlannerFood, ...],
    snacks: tuple[PlannerFood, ...],
    flexible: tuple[PlannerFood, ...],
    policy: PlannerPolicy,
) -> tuple[PlannedDay, ...]:
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
    fat_candidates = tuple(
        food for food in flexible if food.nutrients_per_100g.get("total_fat_g", ZERO) > 20
    )
    days: list[PlannedDay] = []
    for day_index in range(7):
        meals: list[PlannedMeal] = []
        for slot_index in range(inputs.main_meals_per_day):
            sequence = day_index * inputs.main_meals_per_day + slot_index
            protein = proteins[sequence % len(proteins)]
            staple = staples[sequence % len(staples)]
            fat = fat_candidates[sequence % len(fat_candidates)] if fat_candidates else None
            protein_share = policy.protein_energy_share
            fat_share = Decimal("0.15") if fat else ZERO
            staple_share = Decimal("1") - protein_share - fat_share
            items = [
                _portion(
                    protein, main_slot_kcal * protein_share, policy.maximum_main_food_portion_g
                ),
                _portion(staple, main_slot_kcal * staple_share, policy.maximum_main_food_portion_g),
            ]
            if fat is not None:
                items.append(
                    _portion(fat, main_slot_kcal * fat_share, policy.maximum_main_food_portion_g)
                )
            meals.append(_meal("main_meal", slot_index, tuple(items)))
        for slot_index in range(inputs.snacks_per_day):
            snack = snacks[(day_index * max(inputs.snacks_per_day, 1) + slot_index) % len(snacks)]
            meals.append(
                _meal(
                    "snack",
                    slot_index,
                    (_portion(snack, snack_slot_kcal, policy.maximum_snack_portion_g),),
                )
            )
        days.append(_day(day_index, tuple(meals)))
    return tuple(days)


def _portion(food: PlannerFood, target_kcal: Decimal, maximum_g: Decimal) -> PlannedFood:
    energy = food.nutrients_per_100g["energy_kcal"]
    grams = (target_kcal * HUNDRED / energy).quantize(Decimal("0.1"), ROUND_HALF_UP)
    grams = max(DEFAULT_POLICY.minimum_portion_g, min(grams, maximum_g))
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
    )


def _meal(role: str, slot_index: int, foods: tuple[PlannedFood, ...]) -> PlannedMeal:
    nutrients = _sum_nutrients(food.nutrients for food in foods)
    return PlannedMeal(
        role=role,
        slot_index=slot_index,
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
    flexible: tuple[PlannerFood, ...],
    policy: PlannerPolicy,
) -> tuple[tuple[PlannedDay, ...], tuple[RepairAction, ...]]:
    mutable_days = list(days)
    actions: list[RepairAction] = []
    for nutrient_code, target in sorted(inputs.micronutrient_targets.items()):
        weekly = _sum_nutrients(day.nutrients for day in mutable_days).get(nutrient_code, ZERO)
        if weekly >= target * Decimal("7"):
            continue
        candidates = [
            food for food in flexible if food.nutrients_per_100g.get(nutrient_code, ZERO) > ZERO
        ]
        if not candidates:
            continue
        candidates.sort(
            key=lambda food: (
                -(food.nutrients_per_100g[nutrient_code] / food.nutrients_per_100g["energy_kcal"]),
                food.slug,
            )
        )
        selected = candidates[0]
        for day_index in range(min(policy.maximum_repair_iterations, len(mutable_days))):
            day = mutable_days[day_index]
            target_meal_index = next(
                index for index, meal in enumerate(day.meals) if meal.role == "main_meal"
            )
            meal = day.meals[target_meal_index]
            addition = _portion_for_grams(selected, policy.repair_portion_g)
            repaired_meal = _meal(meal.role, meal.slot_index, (*meal.foods, addition))
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
            actions.append(
                RepairAction(nutrient_code, selected.slug, policy.repair_portion_g, day_index)
            )
            weekly += selected.nutrients_per_100g[nutrient_code] * policy.repair_portion_g / HUNDRED
            if weekly >= target * Decimal("7"):
                break
        if len(actions) >= policy.maximum_repair_iterations:
            break
    return tuple(mutable_days), tuple(actions)


def _portion_for_grams(food: PlannerFood, grams: Decimal) -> PlannedFood:
    energy = food.nutrients_per_100g["energy_kcal"]
    return _portion(food, energy * grams / HUNDRED, grams)


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
