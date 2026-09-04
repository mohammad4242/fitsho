"""Pure deterministic budget repair for already validated planner objects."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING, Protocol

from app.nutrition.planner_policy import PlannerPolicy

if TYPE_CHECKING:
    from app.nutrition.planner_engine import (
        EligibleMealTemplate,
        PlannedDay,
        PlannedFood,
        PlannedMeal,
        PlannerFood,
        PlannerInput,
    )

ZERO = Decimal("0")
HUNDRED = Decimal("100")
BUDGET_OPTIMIZER_VERSION = "deterministic-budget-optimizer-v1"
BUDGET_FEASIBILITY_SOLVER_VERSION = "bounded-template-feasibility-v1"

MealBuilder = Callable[
    ["EligibleMealTemplate", str, int, Decimal, Decimal],
    "PlannedMeal",
]


@dataclass(frozen=True)
class BudgetRepairAction:
    day_index: int
    role: str
    slot_index: int
    action_type: str
    before_cost_irr: Decimal
    after_cost_irr: Decimal
    saved_irr: Decimal
    reason_code: str


@dataclass(frozen=True)
class BudgetFeasibilityResult:
    feasible: bool
    minimum_feasible_weekly_cost_irr: Decimal | None
    search_exhaustive: bool
    solver_version: str = BUDGET_FEASIBILITY_SOLVER_VERSION


@dataclass(frozen=True)
class BudgetOptimizationResult:
    days: tuple[PlannedDay, ...]
    repair_actions: tuple[BudgetRepairAction, ...]
    final_cost_irr: Decimal
    failure_code: str | None = None
    diagnostics: dict[str, str] | None = None
    minimum_feasible_weekly_cost_irr: Decimal | None = None
    search_exhaustive: bool = False

    def __post_init__(self) -> None:
        if self.diagnostics is None:
            object.__setattr__(self, "diagnostics", {})

    @property
    def repaired_days(self) -> tuple[PlannedDay, ...]:
        return self.days


class BudgetFeasibilitySolver(Protocol):
    def solve(
        self,
        *,
        inputs: PlannerInput,
        variants: tuple[object, ...],
        policy: PlannerPolicy,
    ) -> BudgetFeasibilityResult: ...


@dataclass(frozen=True)
class _BudgetMove:
    days: tuple[PlannedDay, ...]
    action: BudgetRepairAction
    final_cost_irr: Decimal
    nutrition_penalty: Decimal
    repetition_penalty: int
    preference_penalty: int
    stable_action_id: str


@dataclass(frozen=True)
class _SearchState:
    days: tuple[PlannedDay, ...]
    stable_key: tuple[str, ...]


@dataclass(frozen=True)
class _SearchResult:
    days: tuple[PlannedDay, ...] | None
    feasibility: BudgetFeasibilityResult
    stable_key: tuple[str, ...] = ()


def optimize_weekly_budget(
    *,
    days: tuple[PlannedDay, ...],
    inputs: PlannerInput,
    eligible_templates: tuple[EligibleMealTemplate, ...],
    policy: PlannerPolicy,
    meal_builder: MealBuilder | None = None,
) -> BudgetOptimizationResult:
    """Apply bounded safe repairs, then search the minimum-cost feasible variants."""

    current_cost = _weekly_cost(days)
    budget_cap = _budget_cap(inputs, policy)
    base_diagnostics = {
        "budget_optimizer_version": BUDGET_OPTIMIZER_VERSION,
        "user_weekly_budget_irr": str(inputs.weekly_budget_irr),
        "budget_cap_irr": str(budget_cap),
    }
    if current_cost <= budget_cap:
        return BudgetOptimizationResult(
            days=days,
            repair_actions=(),
            final_cost_irr=current_cost,
            diagnostics={
                **base_diagnostics,
                "final_weekly_cost_irr": str(current_cost),
                "budget_gap_irr": str(current_cost - budget_cap),
            },
        )

    builder = meal_builder or _default_meal_builder
    mutable_days = days
    actions: list[BudgetRepairAction] = []
    for _ in range(policy.maximum_budget_repair_iterations):
        current_cost = _weekly_cost(mutable_days)
        if current_cost <= budget_cap:
            break
        moves = _generate_moves(
            mutable_days,
            inputs,
            eligible_templates,
            policy,
            budget_cap=budget_cap,
            meal_builder=builder,
        )
        if not moves:
            break
        selected = min(
            moves,
            key=lambda move: (
                0 if move.final_cost_irr <= budget_cap else 1,
                move.nutrition_penalty,
                -move.action.saved_irr,
                move.repetition_penalty,
                move.preference_penalty,
                move.stable_action_id,
            ),
        )
        if selected.final_cost_irr >= current_cost:
            break
        mutable_days = selected.days
        actions.append(selected.action)

    final_cost = _weekly_cost(mutable_days)
    if final_cost <= budget_cap:
        return BudgetOptimizationResult(
            days=mutable_days,
            repair_actions=tuple(actions),
            final_cost_irr=final_cost,
            minimum_feasible_weekly_cost_irr=final_cost,
            search_exhaustive=False,
            diagnostics={
                **base_diagnostics,
                "final_weekly_cost_irr": str(final_cost),
                "budget_gap_irr": str(final_cost - budget_cap),
                "feasibility_solver_version": "not_required",
                "feasibility_search_exhaustive": "false",
            },
        )

    search = _minimum_cost_feasibility_search(
        mutable_days,
        inputs,
        eligible_templates,
        policy,
        budget_cap=budget_cap,
        meal_builder=builder,
    )
    minimum_cost = search.feasibility.minimum_feasible_weekly_cost_irr
    if search.days is not None and minimum_cost is not None and minimum_cost <= budget_cap:
        fallback_actions = _actions_between(mutable_days, search.days)
        return BudgetOptimizationResult(
            days=search.days,
            repair_actions=tuple(actions) + fallback_actions,
            final_cost_irr=minimum_cost,
            minimum_feasible_weekly_cost_irr=minimum_cost,
            search_exhaustive=search.feasibility.search_exhaustive,
            diagnostics={
                **base_diagnostics,
                "final_weekly_cost_irr": str(minimum_cost),
                "minimum_feasible_weekly_cost_irr": str(minimum_cost),
                "budget_gap_irr": str(minimum_cost - budget_cap),
                "feasibility_solver_version": search.feasibility.solver_version,
                "feasibility_search_exhaustive": str(search.feasibility.search_exhaustive).lower(),
            },
        )

    final_cost = minimum_cost if minimum_cost is not None else _weekly_cost(mutable_days)
    failure_code = (
        "STRICT_BUDGET_NO_FEASIBLE_REPAIR"
        if inputs.budget_mode == "strict"
        else "FLEXIBLE_BUDGET_NO_FEASIBLE_REPAIR"
    )
    if minimum_cost is None:
        failure_code = "INSUFFICIENT_LOW_COST_TEMPLATE_COVERAGE"
    return BudgetOptimizationResult(
        days=search.days or mutable_days,
        repair_actions=tuple(actions)
        + (_actions_between(mutable_days, search.days) if search.days is not None else ()),
        final_cost_irr=final_cost,
        failure_code=failure_code,
        minimum_feasible_weekly_cost_irr=minimum_cost,
        search_exhaustive=search.feasibility.search_exhaustive,
        diagnostics={
            **base_diagnostics,
            "final_weekly_cost_irr": str(final_cost),
            "minimum_feasible_weekly_cost_irr": (
                str(minimum_cost) if minimum_cost is not None else ""
            ),
            "budget_gap_irr": str(final_cost - budget_cap),
            "feasibility_solver_version": search.feasibility.solver_version,
            "feasibility_search_exhaustive": str(search.feasibility.search_exhaustive).lower(),
        },
    )


def _generate_moves(
    days: tuple[PlannedDay, ...],
    inputs: PlannerInput,
    eligible_templates: tuple[EligibleMealTemplate, ...],
    policy: PlannerPolicy,
    *,
    budget_cap: Decimal,
    meal_builder: MealBuilder,
) -> tuple[_BudgetMove, ...]:
    from app.nutrition.planner_engine import _resize_planned_food

    templates_by_id = {candidate.template.meal_id: candidate for candidate in eligible_templates}
    foods_by_id = {
        food.food_id: food for candidate in eligible_templates for _item, food in candidate.items
    }
    for candidate in eligible_templates:
        foods_by_id.update({food_id: food for food_id, food in candidate.prepared_recipe_foods})
    moves: list[_BudgetMove] = []
    prepared_specs: list[tuple[int, int, PlannedMeal, EligibleMealTemplate, Decimal, Decimal]] = []
    prepared_variant_cache: dict[tuple[object, ...], PlannedMeal | None] = {}
    current_weekly_cost = _weekly_cost(days)
    budget_overage = max(current_weekly_cost - budget_cap, ZERO)
    prepared_recipe_slots = sum(
        1
        for day in days
        for meal in day.meals
        if meal.template_id is not None
        and meal.template_id in templates_by_id
        and templates_by_id[meal.template_id].template.prepared_recipe is not None
    )
    prepared_recipe_slots = max(prepared_recipe_slots, 1)
    for day_index, day in enumerate(days):
        for meal_index, meal in enumerate(day.meals):
            if meal.template_id is None or not meal.foods:
                continue
            current_template = templates_by_id.get(meal.template_id)
            target_kcal = _meal_target_kcal(inputs, day_index, meal)
            current_energy = dict(meal.nutrients).get("energy_kcal", ZERO)
            if current_energy > ZERO:
                target_kcal = current_energy

            for candidate in eligible_templates:
                if candidate.template.meal_id == meal.template_id:
                    continue
                if candidate.template.category != meal.template_category:
                    continue
                if not _template_is_safe(candidate, inputs):
                    continue
                if _template_reference_cost(candidate) >= meal.cost_irr:
                    continue
                try:
                    replacement = meal_builder(
                        candidate,
                        meal.role,
                        meal.slot_index,
                        target_kcal,
                        budget_cap,
                    )
                except ValueError:
                    continue
                if replacement.cost_irr >= meal.cost_irr:
                    continue
                candidate_days = _replace_meal(days, day_index, meal_index, replacement)
                if not _valid_repair_days(candidate_days, days, inputs, policy):
                    continue
                moves.append(
                    _make_move(
                        candidate_days,
                        inputs,
                        meal,
                        replacement,
                        day_index=day_index,
                        action_type="replace_template",
                        reason_code="BUDGET_CHEAPER_COMPATIBLE_TEMPLATE",
                        stable_action_id=f"template:{candidate.template.meal_id}:{day_index}:{meal_index}",
                    )
                )

            if (
                current_template is not None
                and current_template.template.prepared_recipe is not None
            ):
                per_slot_overage = budget_overage / Decimal(prepared_recipe_slots)
                prepared_specs.append(
                    (
                        day_index,
                        meal_index,
                        meal,
                        current_template,
                        target_kcal,
                        per_slot_overage,
                    )
                )

            if current_template is None:
                continue
            optional_food_ids = {
                item.food_id for item, _food in current_template.items if not item.is_required
            }
            for food_index, planned_food in enumerate(meal.foods):
                if planned_food.food_id is None:
                    continue
                source = foods_by_id.get(planned_food.food_id)
                if source is None or not _food_is_safe(source, inputs):
                    continue
                if planned_food.grams <= planned_food.min_grams:
                    continue
                new_grams = max(
                    planned_food.min_grams,
                    planned_food.grams - policy.repair_portion_g,
                )
                if new_grams >= planned_food.grams:
                    continue
                resized = _resize_planned_food(planned_food, source, new_grams)
                resized_foods = list(meal.foods)
                resized_foods[food_index] = resized
                replacement = _rebuild_meal(meal, tuple(resized_foods))
                candidate_days = _replace_meal(days, day_index, meal_index, replacement)
                if not _valid_repair_days(candidate_days, days, inputs, policy):
                    continue
                optional = planned_food.food_id in optional_food_ids
                moves.append(
                    _make_move(
                        candidate_days,
                        inputs,
                        meal,
                        replacement,
                        day_index=day_index,
                        action_type=(
                            "reduce_optional_ingredient" if optional else "rescale_food_portion"
                        ),
                        reason_code=(
                            "BUDGET_OPTIONAL_INGREDIENT_REDUCED"
                            if optional
                            else "BUDGET_SAFE_PORTION_RESCALED"
                        ),
                        stable_action_id=f"portion:{day_index}:{meal_index}:{food_index}",
                    )
                )
    if moves:
        return tuple(moves)

    for (
        day_index,
        meal_index,
        meal,
        current_template,
        target_kcal,
        per_slot_overage,
    ) in prepared_specs:
        for fraction in (Decimal("1"), Decimal("0.5")):
            maximum_recipe_cost = max(
                meal.cost_irr - per_slot_overage * fraction,
                ZERO,
            )
            cache_key = (
                current_template.template.meal_id,
                meal.role,
                meal.slot_index,
                target_kcal,
                maximum_recipe_cost,
            )
            if cache_key not in prepared_variant_cache:
                try:
                    prepared_variant_cache[cache_key] = meal_builder(
                        current_template,
                        meal.role,
                        meal.slot_index,
                        target_kcal,
                        maximum_recipe_cost,
                    )
                except ValueError:
                    prepared_variant_cache[cache_key] = None
            prepared_replacement = prepared_variant_cache[cache_key]
            if prepared_replacement is None or prepared_replacement.cost_irr >= meal.cost_irr:
                continue
            candidate_days = _replace_meal(days, day_index, meal_index, prepared_replacement)
            if _valid_repair_days(candidate_days, days, inputs, policy):
                moves.append(
                    _make_move(
                        candidate_days,
                        inputs,
                        meal,
                        prepared_replacement,
                        day_index=day_index,
                        action_type="prepared_recipe_variant",
                        reason_code="BUDGET_CHEAPER_PREPARED_RECIPE_VARIANT",
                        stable_action_id=(
                            f"prepared:{meal.template_id}:{day_index}:{meal_index}:{fraction}"
                        ),
                    )
                )
    return tuple(moves)


def _minimum_cost_feasibility_search(
    days: tuple[PlannedDay, ...],
    inputs: PlannerInput,
    eligible_templates: tuple[EligibleMealTemplate, ...],
    policy: PlannerPolicy,
    *,
    budget_cap: Decimal,
    meal_builder: MealBuilder,
) -> _SearchResult:
    templates_by_category: dict[str, list[EligibleMealTemplate]] = {}
    for candidate in eligible_templates:
        if _template_is_safe(candidate, inputs):
            templates_by_category.setdefault(candidate.template.category, []).append(candidate)

    states: tuple[_SearchState, ...] = (_SearchState(days, ()),)
    truncated = False
    slots = [
        (day_index, meal_index, meal)
        for day_index, day in enumerate(days)
        for meal_index, meal in enumerate(day.meals)
        if meal.template_id is not None and meal.foods
    ]
    slot_options: list[tuple[int, int, tuple[tuple[str, PlannedMeal], ...]]] = []
    for day_index, meal_index, initial_meal in slots:
        candidates = list(templates_by_category.get(initial_meal.template_category, ()))
        candidates.sort(
            key=lambda candidate: (
                _template_reference_cost(candidate),
                candidate.template.meal_id,
            )
        )
        current_candidate = next(
            (
                candidate
                for candidate in candidates
                if candidate.template.meal_id == initial_meal.template_id
            ),
            None,
        )
        if len(candidates) > policy.maximum_budget_alternatives_per_slot:
            truncated = True
            candidates = candidates[: policy.maximum_budget_alternatives_per_slot]
            if current_candidate is not None and current_candidate not in candidates:
                candidates[-1] = current_candidate
        target_kcal = _meal_target_kcal(inputs, day_index, initial_meal)
        current_energy = dict(initial_meal.nutrients).get("energy_kcal", ZERO)
        if current_energy > ZERO:
            target_kcal = current_energy
        options: list[tuple[str, PlannedMeal]] = []
        for candidate in candidates:
            if candidate.template.meal_id == initial_meal.template_id:
                replacement = initial_meal
            else:
                try:
                    replacement = meal_builder(
                        candidate,
                        initial_meal.role,
                        initial_meal.slot_index,
                        target_kcal,
                        budget_cap,
                    )
                except ValueError:
                    continue
            options.append((candidate.template.meal_id, replacement))
        if options:
            slot_options.append((day_index, meal_index, tuple(options)))

    for day_index, meal_index, slot_variants in slot_options:
        next_states: list[_SearchState] = []
        for state in states:
            for template_id, replacement in slot_variants:
                candidate_days = _replace_meal(state.days, day_index, meal_index, replacement)
                next_states.append(
                    _SearchState(
                        candidate_days,
                        state.stable_key + (f"{day_index}:{meal_index}:{template_id}",),
                    )
                )
        if len(next_states) > policy.maximum_budget_feasibility_variants:
            truncated = True
        states = tuple(
            sorted(
                _deduplicate_states(next_states),
                key=lambda state: (
                    _weekly_cost(state.days),
                    _nutrition_penalty(state.days, inputs),
                    state.stable_key,
                ),
            )[: policy.maximum_budget_feasibility_variants]
        )
        if not states:
            break

    feasible_states = tuple(
        state for state in states if _valid_candidate_days(state.days, inputs, policy)
    )
    selected = min(
        feasible_states,
        key=lambda state: (_weekly_cost(state.days), state.stable_key),
        default=None,
    )
    minimum_cost = _weekly_cost(selected.days) if selected is not None else None
    feasibility = BudgetFeasibilityResult(
        feasible=minimum_cost is not None and minimum_cost <= budget_cap,
        minimum_feasible_weekly_cost_irr=minimum_cost,
        search_exhaustive=not truncated and not _has_resizable_foods(days),
    )
    return _SearchResult(
        days=selected.days if selected is not None else None,
        feasibility=feasibility,
        stable_key=selected.stable_key if selected is not None else (),
    )


def _deduplicate_states(states: list[_SearchState]) -> tuple[_SearchState, ...]:
    unique: dict[tuple[object, ...], _SearchState] = {}
    for state in states:
        identity = tuple(meal.template_id for day in state.days for meal in day.meals)
        previous = unique.get(identity)
        if previous is None or state.stable_key < previous.stable_key:
            unique[identity] = state
    return tuple(unique.values())


def _make_move(
    days: tuple[PlannedDay, ...],
    inputs: PlannerInput,
    before: PlannedMeal,
    after: PlannedMeal,
    *,
    day_index: int,
    action_type: str,
    reason_code: str,
    stable_action_id: str,
) -> _BudgetMove:
    saved = before.cost_irr - after.cost_irr
    action = BudgetRepairAction(
        day_index=day_index,
        role=before.role,
        slot_index=before.slot_index,
        action_type=action_type,
        before_cost_irr=before.cost_irr,
        after_cost_irr=after.cost_irr,
        saved_irr=saved,
        reason_code=reason_code,
    )
    return _BudgetMove(
        days=days,
        action=action,
        final_cost_irr=_weekly_cost(days),
        nutrition_penalty=_nutrition_penalty(days, inputs),
        repetition_penalty=_repetition_penalty(days, inputs),
        preference_penalty=_preference_penalty(days, inputs),
        stable_action_id=stable_action_id,
    )


def _actions_between(
    before: tuple[PlannedDay, ...],
    after: tuple[PlannedDay, ...] | None,
) -> tuple[BudgetRepairAction, ...]:
    if after is None:
        return ()
    actions: list[BudgetRepairAction] = []
    for day_before, day_after in zip(before, after, strict=True):
        for meal_before, meal_after in zip(day_before.meals, day_after.meals, strict=True):
            if meal_before == meal_after or meal_before.cost_irr <= meal_after.cost_irr:
                continue
            action_type = (
                "replace_template"
                if meal_before.template_id != meal_after.template_id
                else "rescale_food_portion"
            )
            actions.append(
                BudgetRepairAction(
                    day_index=day_before.day_index,
                    role=meal_before.role,
                    slot_index=meal_before.slot_index,
                    action_type=action_type,
                    before_cost_irr=meal_before.cost_irr,
                    after_cost_irr=meal_after.cost_irr,
                    saved_irr=meal_before.cost_irr - meal_after.cost_irr,
                    reason_code="BUDGET_MINIMUM_COST_FEASIBILITY_REPAIR",
                )
            )
    return tuple(actions)


def _valid_candidate_days(
    days: tuple[PlannedDay, ...],
    inputs: PlannerInput,
    policy: PlannerPolicy,
    *,
    enforce_repetition: bool = True,
) -> bool:
    from app.nutrition.planner_engine import (
        _sum_nutrients,
        _upper_limit_exceeded,
        _validate_nutritional_feasibility,
    )

    if enforce_repetition and _repetition_penalty(days, inputs) > 0:
        return False
    totals = _sum_nutrients(day.nutrients for day in days)
    daily_average = {code: value / Decimal("7") for code, value in totals.items()}
    return not _upper_limit_exceeded(
        inputs, daily_average
    ) and not _validate_nutritional_feasibility(inputs, daily_average, policy)


def _valid_repair_days(
    candidate: tuple[PlannedDay, ...],
    current: tuple[PlannedDay, ...],
    inputs: PlannerInput,
    policy: PlannerPolicy,
) -> bool:
    return _repetition_penalty(candidate, inputs) <= _repetition_penalty(
        current, inputs
    ) and _valid_candidate_days(candidate, inputs, policy, enforce_repetition=False)


def _has_resizable_foods(days: tuple[PlannedDay, ...]) -> bool:
    return any(
        food.food_id is not None and food.grams > food.min_grams
        for day in days
        for meal in day.meals
        for food in meal.foods
    )


def _replace_meal(
    days: tuple[PlannedDay, ...],
    day_index: int,
    meal_index: int,
    replacement: PlannedMeal,
) -> tuple[PlannedDay, ...]:
    from app.nutrition.planner_engine import _day

    mutable_days = list(days)
    day = mutable_days[day_index]
    meals = list(day.meals)
    meals[meal_index] = replacement
    mutable_days[day_index] = _day(day.day_index, tuple(meals))
    return tuple(mutable_days)


def _rebuild_meal(meal: PlannedMeal, foods: tuple[PlannedFood, ...]) -> PlannedMeal:
    from app.nutrition.planner_engine import _meal

    return _meal(
        meal.role,
        meal.slot_index,
        foods,
        template_id=meal.template_id,
        template_category=meal.template_category,
    )


def _default_meal_builder(
    candidate: EligibleMealTemplate,
    role: str,
    slot_index: int,
    target_kcal: Decimal,
    maximum_cost_irr: Decimal,
) -> PlannedMeal:
    from app.nutrition.planner_engine import _meal_from_template

    return _meal_from_template(
        role,
        slot_index,
        candidate,
        target_kcal,
        maximum_recipe_cost_irr=maximum_cost_irr,
        optimization_cache={},
    )


def _budget_cap(inputs: PlannerInput, policy: PlannerPolicy) -> Decimal:
    allowance = Decimal(inputs.weekly_budget_irr)
    if inputs.budget_mode == "strict":
        return allowance
    return allowance * (Decimal("1") + policy.flexible_budget_overage_cap)


def _weekly_cost(days: tuple[PlannedDay, ...]) -> Decimal:
    return sum((day.cost_irr for day in days), ZERO).quantize(Decimal("1"))


def _meal_target_kcal(inputs: PlannerInput, day_index: int, meal: PlannedMeal) -> Decimal:
    if inputs.template_schedule is not None:
        schedule = inputs.template_schedule[day_index]
        real_slots = [slot for slot in schedule if slot[1] is not None]
        snack_count = sum(role == "snack" for role, _template_id, _category in real_slots)
        main_count = len(real_slots) - snack_count
        snack_share = Decimal("0.15") if snack_count else ZERO
        if meal.role == "snack" and snack_count:
            return inputs.daily_targets["goal_calories"] * snack_share / snack_count
        if main_count:
            return inputs.daily_targets["goal_calories"] * (Decimal("1") - snack_share) / main_count
    if meal.role == "snack" and inputs.snacks_per_day:
        return inputs.daily_targets["goal_calories"] * Decimal("0.15") / inputs.snacks_per_day
    return inputs.daily_targets["goal_calories"] / inputs.main_meals_per_day


def _template_reference_cost(candidate: EligibleMealTemplate) -> Decimal:
    cost = sum(
        (food.price_irr_per_gram * item.reference_grams for item, food in candidate.items),
        ZERO,
    )
    for food_id, food in candidate.prepared_recipe_foods:
        recipe = candidate.template.prepared_recipe
        if recipe is None:
            continue
        ingredient = next(
            ingredient
            for ingredient in recipe.definition.ingredients
            if str(ingredient.food_id) == food_id
        )
        cost += food.price_irr_per_gram * ingredient.reference_grams
    return cost


def _template_is_safe(candidate: EligibleMealTemplate, inputs: PlannerInput) -> bool:
    if candidate.template.verification_status != "verified":
        return False
    if any(not _food_is_safe(food, inputs) for _item, food in candidate.items):
        return False
    return all(_food_is_safe(food, inputs) for _food_id, food in candidate.prepared_recipe_foods)


def _food_is_safe(food: PlannerFood, inputs: PlannerInput) -> bool:
    if getattr(inputs, "food_constraints", ()):
        from app.nutrition.food_constraints import evaluate_food_constraints

        decision = evaluate_food_constraints(
            constraints=inputs.food_constraints,
            slug=food.slug,
            name_fa=food.name_fa,
            name_en=food.name_en,
            allergen_tags=getattr(food, "allergen_tags", ()),
            allergen_metadata_verified=getattr(food, "allergen_metadata_verified", False),
        )
        if decision.is_hard_blocked:
            return False

    return (
        food.price_irr_per_gram > ZERO
        and food.price_reference_id not in {"", "unavailable"}
        and inputs.dietary_pattern in food.dietary_patterns
        and not _excluded(food.slug, food.name_fa, inputs.excluded_terms)
        and all(
            code in food.nutrients_per_100g and food.nutrients_per_100g[code] >= ZERO
            for code in ("energy_kcal", "protein_g", "carbohydrate_g", "total_fat_g")
        )
        and food.nutrients_per_100g.get("energy_kcal", ZERO) > ZERO
    )


def _excluded(slug: str, name_fa: str, excluded_terms: tuple[str, ...]) -> bool:
    haystack = f"{slug} {name_fa}".casefold()
    return any(term.strip().casefold() in haystack for term in excluded_terms if term.strip())


def _nutrition_penalty(days: tuple[PlannedDay, ...], inputs: PlannerInput) -> Decimal:
    from app.nutrition.planner_engine import TARGET_NUTRIENT_CODES, _sum_nutrients

    totals = _sum_nutrients(day.nutrients for day in days)
    penalty = ZERO
    for code, target in inputs.daily_targets.items():
        if target <= ZERO:
            continue
        nutrient_code = TARGET_NUTRIENT_CODES.get(code, code)
        planned = totals.get(nutrient_code, ZERO) / Decimal("7")
        penalty += abs(planned - target) / target
    return penalty


def _repetition_penalty(days: tuple[PlannedDay, ...], inputs: PlannerInput) -> int:
    usage: dict[str, int] = {}
    for day in days:
        for meal in day.meals:
            if meal.template_id is not None:
                usage[meal.template_id] = usage.get(meal.template_id, 0) + 1
    return sum(max(count - inputs.maximum_meal_repetition_per_week, 0) for count in usage.values())


def _preference_penalty(days: tuple[PlannedDay, ...], inputs: PlannerInput) -> int:
    penalty = 0
    liked = set(inputs.liked_food_ids)
    disliked = set(inputs.disliked_food_ids)
    for day in days:
        for meal in day.meals:
            for food in meal.foods:
                if food.food_id in liked:
                    penalty -= 1
                if food.food_id in disliked:
                    penalty += 1
    return penalty
