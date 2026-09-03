"""Pure deterministic comparison of fully evaluated nutrition candidates."""

from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from app.nutrition.planner_engine import GenerationOutcome, NutrientComparison, PlannerResult
from app.nutrition.program_selection import ProgramCandidate

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

    def sort_key(self) -> tuple[object, ...]:
        return (
            self.core_nutrition_max_deviation,
            self.core_nutrition_total_deviation,
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
) -> CandidateEvaluation:
    quality = (
        _candidate_quality(
            proposal,
            result,
            weekly_budget_irr=weekly_budget_irr,
            stable_variant_key=stable_variant_key,
        )
        if result.outcome is GenerationOutcome.SUCCESS
        else None
    )
    return CandidateEvaluation(
        program_id=proposal.program.id,
        program_code=proposal.program.code,
        stable_variant_key=stable_variant_key,
        preconstruction_rank=proposal.preconstruction_rank,
        preferred_style=proposal.preferred_style,
        result=result,
        quality=quality,
    )


def select_best_candidate(
    evaluations: tuple[CandidateEvaluation, ...],
) -> CandidateSelection:
    first_valid = next(
        (
            evaluation
            for evaluation in evaluations
            if evaluation.result.outcome is GenerationOutcome.SUCCESS
            and evaluation.quality is not None
        ),
        None,
    )
    admitted = tuple(
        evaluation
        for evaluation in evaluations
        if evaluation.result.outcome is GenerationOutcome.SUCCESS and evaluation.quality is not None
    )
    selected = (
        min(
            admitted,
            key=lambda evaluation: (
                evaluation.quality.sort_key() if evaluation.quality is not None else ()
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
        if evaluation.result.outcome is GenerationOutcome.SUCCESS:
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
) -> CandidateQuality:
    comparisons = result.nutrient_comparisons or {}
    core_deviations = tuple(
        _normalized_core_deviation(comparisons.get(code), code) for code in CORE_NUTRIENTS
    )
    return CandidateQuality(
        core_nutrition_max_deviation=max(core_deviations, default=ONE),
        core_nutrition_total_deviation=sum(core_deviations, ZERO),
        micronutrient_gap_penalty=_micronutrient_gap_penalty(comparisons),
        diet_quality_penalty=ZERO,
        sports_nutrition_distribution_penalty=ZERO,
        budget_utilization_penalty=_budget_utilization(result.weekly_cost_irr, weekly_budget_irr),
        preference_and_feedback_penalty=ZERO,
        repetition_penalty=ZERO,
        warning_burden=len(result.warning_codes),
        repair_burden=len(result.repair_actions),
        substitution_burden=0,
        preferred_program_style_penalty=0 if proposal.preferred_style else 1,
        stable_program_code=proposal.program.code,
        stable_variant_key=stable_variant_key,
    )


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
            gap += Decimal("0.10")
        gaps.append(gap)
    if not gaps:
        return ZERO
    return max(gaps) + min(sum(gaps, ZERO), ONE)


def _budget_utilization(cost: Decimal, budget: Decimal) -> Decimal:
    if budget > ZERO:
        return cost / budget
    return ZERO if cost <= ZERO else ONE
