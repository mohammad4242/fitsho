from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

ZERO = Decimal("0")
ONE = Decimal("1")

_TARGET_REASON_CODES = {
    "energy_kcal": "CALORIE_TARGET_UNREACHABLE_WITH_PORTION_BOUNDS",
    "protein_g": "PROTEIN_TARGET_UNREACHABLE_WITH_PORTION_BOUNDS",
    "carbohydrate_g": "CARBOHYDRATE_TARGET_UNREACHABLE_WITH_PORTION_BOUNDS",
    "total_fat_g": "FAT_TARGET_UNREACHABLE_WITH_PORTION_BOUNDS",
}


@dataclass(frozen=True)
class PortionVariable:
    key: str
    day_index: int
    role: str
    slot_index: int
    food_id: str | None
    grams: Decimal
    reference_grams: Decimal
    min_grams: Decimal
    max_grams: Decimal
    nutrients_per_gram: tuple[tuple[str, Decimal], ...]
    cost_per_gram: Decimal


@dataclass(frozen=True)
class PortionAdjustmentAction:
    day_index: int
    role: str
    slot_index: int
    food_id: str | None
    before_grams: Decimal
    after_grams: Decimal
    reason_code: str = "PORTION_SOLVER_APPLIED"


@dataclass(frozen=True)
class PortionSolverResult:
    grams_by_key: tuple[tuple[str, Decimal], ...]
    final_totals: dict[str, Decimal]
    actions: tuple[PortionAdjustmentAction, ...]
    reason_codes: tuple[str, ...]
    initial_score: tuple[Decimal, ...]
    final_score: tuple[Decimal, ...]


def solve_portions(
    *,
    variables: tuple[PortionVariable, ...],
    initial_totals: dict[str, Decimal],
    targets: dict[str, Decimal],
    minimums: dict[str, Decimal],
    maximums: dict[str, Decimal],
    upper_limits: dict[str, Decimal],
    increment_g: Decimal,
    maximum_iterations: int,
    target_tolerance_ratio: Decimal = Decimal("0.20"),
) -> PortionSolverResult:
    if not increment_g.is_finite() or increment_g <= ZERO:
        raise ValueError("Portion solver increment must be finite and positive")
    if maximum_iterations < 0:
        raise ValueError("Portion solver iteration limit must not be negative")

    ordered = tuple(sorted(variables, key=lambda variable: variable.key))
    current = {variable.key: _quantize(variable.grams, increment_g) for variable in ordered}
    initial = {variable.key: variable.grams for variable in ordered}
    base_totals = dict(initial_totals)
    for variable in ordered:
        for code, nutrient_per_gram in variable.nutrients_per_gram:
            base_totals[code] = base_totals.get(code, ZERO) - nutrient_per_gram * variable.grams

    initial_totals_exact = _totals(base_totals, ordered, initial)
    initial_score = _score(
        initial_totals_exact,
        current,
        ordered,
        targets,
        minimums,
        maximums,
        upper_limits,
    )
    current_score = initial_score
    actions: list[PortionAdjustmentAction] = []

    for _ in range(maximum_iterations):
        best: tuple[tuple[Decimal, ...], str, Decimal, dict[str, Decimal]] | None = None
        for variable in ordered:
            before = current[variable.key]
            for direction in (-ONE, ONE):
                requested = before + direction * increment_g
                if requested < variable.min_grams or requested > variable.max_grams:
                    continue
                after = _quantize(requested, increment_g)
                after = max(variable.min_grams, min(after, variable.max_grams))
                if after == before:
                    continue
                candidate = dict(current)
                candidate[variable.key] = after
                candidate_totals = _totals(base_totals, ordered, candidate)
                candidate_score = _score(
                    candidate_totals,
                    candidate,
                    ordered,
                    targets,
                    minimums,
                    maximums,
                    upper_limits,
                )
                candidate_key = (candidate_score, variable.key, after, candidate_totals)
                if best is None or candidate_key[:3] < best[:3]:
                    best = candidate_key
        if best is None or best[0] >= current_score:
            break
        _, key, after, _ = best
        before = current[key]
        current[key] = after
        variable = next(variable for variable in ordered if variable.key == key)
        actions.append(
            PortionAdjustmentAction(
                day_index=variable.day_index,
                role=variable.role,
                slot_index=variable.slot_index,
                food_id=variable.food_id,
                before_grams=before,
                after_grams=after,
            )
        )
        current_score = best[0]

    final_totals = _totals(base_totals, ordered, current)
    reason_codes = _reason_codes(
        final_totals,
        targets,
        minimums,
        maximums,
        upper_limits,
        target_tolerance_ratio,
    )
    return PortionSolverResult(
        grams_by_key=tuple(sorted(current.items())),
        final_totals=final_totals,
        actions=tuple(actions),
        reason_codes=reason_codes,
        initial_score=initial_score,
        final_score=current_score,
    )


def _quantize(value: Decimal, increment: Decimal) -> Decimal:
    return (value / increment).to_integral_value(rounding=ROUND_HALF_UP) * increment


def _totals(
    base_totals: dict[str, Decimal],
    variables: tuple[PortionVariable, ...],
    grams_by_key: dict[str, Decimal],
) -> dict[str, Decimal]:
    totals = dict(base_totals)
    for variable in variables:
        grams = grams_by_key[variable.key]
        for code, nutrient_per_gram in variable.nutrients_per_gram:
            totals[code] = totals.get(code, ZERO) + nutrient_per_gram * grams
    return totals


def _score(
    totals: dict[str, Decimal],
    grams_by_key: dict[str, Decimal],
    variables: tuple[PortionVariable, ...],
    targets: dict[str, Decimal],
    minimums: dict[str, Decimal],
    maximums: dict[str, Decimal],
    upper_limits: dict[str, Decimal],
) -> tuple[Decimal, ...]:
    safety_excess = sum(
        (max(totals.get(code, ZERO) - limit, ZERO) for code, limit in upper_limits.items()),
        ZERO,
    )
    maximum_excess = sum(
        (max(totals.get(code, ZERO) - limit, ZERO) for code, limit in maximums.items()),
        ZERO,
    )
    minimum_deficit = sum(
        (max(limit - totals.get(code, ZERO), ZERO) for code, limit in minimums.items()),
        ZERO,
    )
    deviations = tuple(
        abs(totals.get(code, ZERO) - target) / max(target, ONE)
        for code, target in sorted(targets.items())
    )
    max_deviation = max(deviations, default=ZERO)
    total_deviation = sum(deviations, ZERO)
    fibre_deficit = max(minimums.get("fibre_g", ZERO) - totals.get("fibre_g", ZERO), ZERO)
    reference_distance = sum(
        (
            abs(grams_by_key[variable.key] - variable.reference_grams)
            / max(variable.reference_grams, ONE)
            for variable in variables
        ),
        ZERO,
    )
    cost_increase = sum(
        (
            max(grams_by_key[variable.key] - variable.grams, ZERO) * variable.cost_per_gram
            for variable in variables
        ),
        ZERO,
    )
    return (
        safety_excess,
        maximum_excess,
        minimum_deficit,
        max_deviation,
        total_deviation,
        fibre_deficit,
        reference_distance,
        cost_increase,
    )


def _reason_codes(
    totals: dict[str, Decimal],
    targets: dict[str, Decimal],
    minimums: dict[str, Decimal],
    maximums: dict[str, Decimal],
    upper_limits: dict[str, Decimal],
    tolerance_ratio: Decimal,
) -> tuple[str, ...]:
    if any(totals.get(code, ZERO) > limit for code, limit in upper_limits.items()):
        return ("NUTRIENT_UPPER_LIMIT_EXCEEDED",)
    bounded_reasons: list[str] = []
    for code, minimum in sorted(minimums.items()):
        if totals.get(code, ZERO) < minimum:
            reason = _TARGET_REASON_CODES.get(code)
            if reason is not None:
                bounded_reasons.append(reason)
    for code, maximum in sorted(maximums.items()):
        if totals.get(code, ZERO) > maximum:
            reason = _TARGET_REASON_CODES.get(code)
            if reason is not None:
                bounded_reasons.append(reason)
    if bounded_reasons:
        bounded_unique = tuple(dict.fromkeys(bounded_reasons))
        return (
            ("MULTI_MACRO_TARGET_UNREACHABLE_WITH_PORTION_BOUNDS",)
            if len(bounded_unique) > 1
            else bounded_unique
        )

    reasons: list[str] = []
    for code, target in sorted(targets.items()):
        if target > ZERO and abs(totals.get(code, ZERO) - target) / target > tolerance_ratio:
            reason = _TARGET_REASON_CODES.get(code)
            if reason is not None:
                reasons.append(reason)
    if len(set(reasons)) > 1:
        return ("MULTI_MACRO_TARGET_UNREACHABLE_WITH_PORTION_BOUNDS",)
    return tuple(dict.fromkeys(reasons))
