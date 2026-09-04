"""Pure deterministic comparison of fully evaluated nutrition candidates."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID

from app.nutrition.enums import NutritionOptimizationMode
from app.nutrition.preference_snapshot import PreferenceSnapshot
from app.nutrition.program_selection import ProgramCandidate

if TYPE_CHECKING:
    from app.nutrition.planner_engine import NutrientComparison, PlannerResult

ZERO = Decimal("0")
ONE = Decimal("1")
CORE_NUTRIENTS = ("goal_calories", "protein", "carbohydrate", "total_fat")


@dataclass(frozen=True)
class CandidateQuality:
    core_nutrition_max_deviation: Decimal
    core_nutrition_total_deviation: Decimal
    micronutrient_gap_penalty: Decimal
    diet_quality_penalty: Decimal
    sports_nutrition_distribution_penalty: Decimal
    budget_utilization_penalty: Decimal
    preference_and_feedback_penalty: Decimal
    repetition_penalty: Decimal
    warning_burden: int
    repair_burden: int
    substitution_burden: int
    preferred_program_style_penalty: int
    stable_program_code: str
    stable_variant_key: tuple[str, ...]
    goal_target_penalty: Decimal = ZERO
    cost_irr: Decimal = ZERO

    def sort_key(
        self, mode: NutritionOptimizationMode = NutritionOptimizationMode.BUDGET_CONSTRAINED
    ) -> tuple[object, ...]:
        if mode == NutritionOptimizationMode.IDEAL_REFERENCE:
            return (
                self.core_nutrition_max_deviation,
                self.core_nutrition_total_deviation,
                self.goal_target_penalty,
                self.micronutrient_gap_penalty,
                self.diet_quality_penalty,
                self.sports_nutrition_distribution_penalty,
                self.preference_and_feedback_penalty,
                self.repetition_penalty,
                self.warning_burden,
                self.repair_burden,
                self.substitution_burden,
                self.preferred_program_style_penalty,
                self.cost_irr,
                self.stable_program_code,
                self.stable_variant_key,
            )
        return (
            self.core_nutrition_max_deviation,
            self.core_nutrition_total_deviation,
            self.goal_target_penalty,
            self.micronutrient_gap_penalty,
            self.diet_quality_penalty,
            self.sports_nutrition_distribution_penalty,
            self.budget_utilization_penalty,
            self.preference_and_feedback_penalty,
            self.repetition_penalty,
            self.warning_burden,
            self.repair_burden,
            self.substitution_burden,
            self.preferred_program_style_penalty,
            self.stable_program_code,
            self.stable_variant_key,
        )


@dataclass(frozen=True)
class CandidateEvaluation:
    program_id: UUID | None
    program_code: str
    stable_variant_key: tuple[str, ...]
    preconstruction_rank: int
    preferred_style: bool
    result: PlannerResult
    quality: CandidateQuality | None


@dataclass(frozen=True)
class CandidateSelection:
    selected: CandidateEvaluation | None
    first_valid: CandidateEvaluation | None
    evaluations: tuple[CandidateEvaluation, ...]


def evaluate_candidate(
    proposal: ProgramCandidate,
    result: PlannerResult,
    *,
    weekly_budget_irr: Decimal,
    stable_variant_key: tuple[str, ...] = ("base",),
    preference_snapshot: PreferenceSnapshot | None = None,
) -> CandidateEvaluation:
    effective_variant_key = _effective_variant_key(result, stable_variant_key)
    quality = (
        _quality_for_result(
            result,
            weekly_budget_irr=weekly_budget_irr,
            preferred_style=proposal.preferred_style,
            stable_program_code=proposal.program.code,
            stable_variant_key=effective_variant_key,
            preference_snapshot=preference_snapshot,
        )
        if _is_success(result)
        else None
    )
    return CandidateEvaluation(
        program_id=proposal.program.id,
        program_code=proposal.program.code,
        stable_variant_key=effective_variant_key,
        preconstruction_rank=proposal.preconstruction_rank,
        preferred_style=proposal.preferred_style,
        result=result,
        quality=quality,
    )


def select_best_candidate(
    evaluations: tuple[CandidateEvaluation, ...],
    mode: NutritionOptimizationMode = NutritionOptimizationMode.BUDGET_CONSTRAINED,
) -> CandidateSelection:
    first_valid = next(
        (
            evaluation
            for evaluation in evaluations
            if _is_success(evaluation.result) and evaluation.quality is not None
        ),
        None,
    )
    admitted = tuple(
        evaluation
        for evaluation in evaluations
        if _is_success(evaluation.result) and evaluation.quality is not None
    )
    selected = (
        min(
            admitted,
            key=lambda evaluation: (
                evaluation.quality.sort_key(mode) if evaluation.quality is not None else ()
            ),
        )
        if admitted
        else None
    )
    return CandidateSelection(
        selected=selected,
        first_valid=first_valid,
        evaluations=evaluations,
    )


def failure_reason_counts(
    evaluations: tuple[CandidateEvaluation, ...],
) -> dict[str, int]:
    counts: dict[str, int] = {}
    for evaluation in evaluations:
        if _is_success(evaluation.result):
            continue
        for reason in evaluation.result.reason_codes:
            counts[reason] = counts.get(reason, 0) + 1
    return dict(sorted(counts.items()))


def _candidate_quality(
    proposal: ProgramCandidate,
    result: PlannerResult,
    *,
    weekly_budget_irr: Decimal,
    stable_variant_key: tuple[str, ...],
    preference_snapshot: PreferenceSnapshot | None = None,
) -> CandidateQuality:
    return _quality_for_result(
        result,
        weekly_budget_irr=weekly_budget_irr,
        preferred_style=proposal.preferred_style,
        stable_program_code=proposal.program.code,
        stable_variant_key=stable_variant_key,
        preference_snapshot=preference_snapshot,
    )


def quality_for_result(
    result: PlannerResult,
    *,
    weekly_budget_irr: Decimal,
    stable_variant_key: tuple[str, ...] = ("base",),
    preference_snapshot: PreferenceSnapshot | None = None,
) -> CandidateQuality:
    """Score a fully validated result for comparing variants of one program."""

    return _quality_for_result(
        result,
        weekly_budget_irr=weekly_budget_irr,
        preferred_style=True,
        stable_program_code="",
        stable_variant_key=stable_variant_key,
        preference_snapshot=preference_snapshot,
    )


def _quality_for_result(
    result: PlannerResult,
    *,
    weekly_budget_irr: Decimal,
    preferred_style: bool,
    stable_program_code: str,
    stable_variant_key: tuple[str, ...],
    preference_snapshot: PreferenceSnapshot | None,
) -> CandidateQuality:
    comparisons = result.nutrient_comparisons or {}
    core_deviations = tuple(
        _normalized_core_deviation(comparisons.get(code), code) for code in CORE_NUTRIENTS
    )
    return CandidateQuality(
        core_nutrition_max_deviation=max(core_deviations, default=ONE),
        core_nutrition_total_deviation=sum(core_deviations, ZERO),
        micronutrient_gap_penalty=_micronutrient_gap_penalty(comparisons),
        diet_quality_penalty=_diet_quality_penalty(comparisons),
        sports_nutrition_distribution_penalty=ZERO,
        budget_utilization_penalty=_budget_utilization(result.weekly_cost_irr, weekly_budget_irr),
        preference_and_feedback_penalty=_preference_penalty(result, preference_snapshot),
        repetition_penalty=_repetition_penalty(result),
        warning_burden=len(result.warning_codes),
        repair_burden=(
            len(result.repair_actions)
            + len(result.portion_adjustment_actions)
            + len(result.budget_repair_actions)
        ),
        substitution_burden=len(result.substitution_actions),
        preferred_program_style_penalty=0 if preferred_style else 1,
        stable_program_code=stable_program_code,
        stable_variant_key=stable_variant_key,
        cost_irr=result.weekly_cost_irr,
    )


def _effective_variant_key(
    result: PlannerResult,
    stable_variant_key: tuple[str, ...],
) -> tuple[str, ...]:
    if stable_variant_key != ("base",) or not result.substitution_actions:
        return stable_variant_key
    return tuple(
        f"{action.day_index:02d}:{action.role}:{action.slot_index:02d}:"
        f"{action.replacement_template_id}"
        for action in result.substitution_actions
    )


def _is_success(result: PlannerResult) -> bool:
    return result.outcome.value == "success"


def _normalized_core_deviation(
    comparison: NutrientComparison | None,
    code: str,
) -> Decimal:
    if comparison is None or comparison.preferred is None or comparison.preferred <= ZERO:
        return ONE
    if code == "protein":
        difference = max(comparison.preferred - comparison.planned, ZERO)
    else:
        difference = abs(comparison.planned - comparison.preferred)
    return difference / comparison.preferred


def _micronutrient_gap_penalty(comparisons: dict[str, NutrientComparison]) -> Decimal:
    gaps: list[Decimal] = []
    for code, comparison in comparisons.items():
        if code in CORE_NUTRIENTS:
            continue
        if comparison.preferred is None or comparison.preferred <= ZERO:
            continue
        gap = max(comparison.preferred - comparison.planned, ZERO) / comparison.preferred
        if comparison.data_confidence != "high":
            gap += Decimal("0.25")
        gaps.append(gap)
    if not gaps:
        return ZERO
    return max(gaps) + min(sum(gaps, ZERO), ONE)


def _diet_quality_penalty(comparisons: dict[str, NutrientComparison]) -> Decimal:
    penalty = ZERO
    for code, comparison in comparisons.items():
        if comparison.preferred is None or comparison.preferred <= ZERO:
            continue
        if code == "fibre":
            penalty += max(comparison.preferred - comparison.planned, ZERO) / comparison.preferred
        elif code in {"free_sugar", "added_sugar", "saturated_fat", "trans_fat", "sodium"}:
            penalty += max(comparison.planned - comparison.preferred, ZERO) / comparison.preferred
    return penalty


def _preference_penalty(
    result: PlannerResult,
    snapshot: PreferenceSnapshot | None,
) -> Decimal:
    if snapshot is None:
        return ZERO
    counts: dict[str, int] = {}
    for day in result.days:
        for meal in day.meals:
            if meal.template_id is not None:
                counts[meal.template_id] = counts.get(meal.template_id, 0) + 1
    penalty = ZERO
    for meal_id, count in counts.items():
        if meal_id in snapshot.disliked_meal_ids:
            penalty += Decimal("2") * count
        if meal_id in snapshot.liked_meal_ids:
            penalty -= Decimal("0.5") * count
        if meal_id in snapshot.prefer_more_often_meal_ids:
            penalty -= Decimal("1") * count
    if snapshot.data_sufficient:
        adherence = dict(snapshot.historical_meal_adherence)
        penalty += sum(
            (
                (ONE - adherence[meal_id]) * Decimal("0.5") * count
                for meal_id, count in counts.items()
                if meal_id in adherence
            ),
            ZERO,
        )
    return penalty


def _repetition_penalty(result: PlannerResult) -> Decimal:
    counts: dict[str, int] = {}
    for day in result.days:
        for meal in day.meals:
            if meal.template_id is not None:
                counts[meal.template_id] = counts.get(meal.template_id, 0) + 1
    return sum(
        (Decimal(count - 1) ** 2 for count in counts.values() if count > 1),
        ZERO,
    )


def _budget_utilization(cost: Decimal, budget: Decimal) -> Decimal:
    if budget > ZERO and budget != Decimal("Infinity"):
        return cost / budget
    return ZERO if cost <= ZERO else ONE
