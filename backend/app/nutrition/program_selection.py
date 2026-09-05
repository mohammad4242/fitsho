"""Deterministic Nutrition Program proposal ordering from profile signals."""

from collections.abc import Iterable
from dataclasses import dataclass
from decimal import Decimal
from typing import NamedTuple
from uuid import UUID

from app.nutrition.enums import NutritionOptimizationMode
from app.nutrition.models import NutritionProgram
from app.nutrition.nutrition_request import NormalizedNutritionRequest
from app.nutrition.planner_policy import PROGRAM_SELECTION_POLICY_VERSION
from app.nutrition.program_costing import ProgramCostEstimate
from app.nutrition.program_eligibility import (
    ProgramEligibilityResult,
    ProgramHardRejection,
    check_program_eligibility,
)
from app.nutrition.program_scoring import (
    ProgramScore,
    ProgramScoringResult,
    score_program,
)


class ProgramSelectionContext(NamedTuple):
    fitness_goal: str
    trains: bool
    exercise_type: str | None
    plan_style: str
    budget_style: str
    cooking_skill: str
    maximum_cooking_time_minutes: int
    meal_preparation_preference: str
    preferred_variety: str


@dataclass(frozen=True, init=False)
class ProgramCandidate:
    program: NutritionProgram
    score: ProgramScoringResult
    preconstruction_rank: int

    def __init__(
        self,
        program: NutritionProgram,
        score: ProgramScoringResult | None = None,
        preconstruction_rank: int = 0,
        *,
        preferred_style: bool | None = None,
    ) -> None:
        object.__setattr__(self, "program", program)
        object.__setattr__(self, "preconstruction_rank", preconstruction_rank)
        if score is None:
            pref = bool(preferred_style)
            score = ProgramScoringResult(
                score=ProgramScore(
                    budget_score=0,
                    goal_score=0,
                    training_score=0,
                    meal_structure_score=0,
                    preference_score=100 if pref else 0,
                    total=100 if pref else 0,
                ),
                reason_codes=("PREFERRED_DIET_STYLE",) if pref else (),
            )
        object.__setattr__(self, "score", score)

    @property
    def preferred_style(self) -> bool:
        return "PREFERRED_DIET_STYLE" in self.score.reason_codes


@dataclass(frozen=True)
class ProgramSelectionResult:
    programs_considered: int
    hard_rejections: tuple[ProgramHardRejection, ...]
    candidates: tuple[ProgramCandidate, ...]
    policy_version: str
    cost_estimates: tuple[ProgramCostEstimate, ...] = ()

    def decision_trace(
        self,
        *,
        programs_constructed: int | None = None,
        fallback_batches_used: int | None = None,
    ) -> dict[str, object]:
        return {
            "policy_version": self.policy_version,
            "programs_considered": self.programs_considered,
            "programs_hard_rejected": len(self.hard_rejections),
            "programs_constructed": (
                programs_constructed if programs_constructed is not None else len(self.candidates)
            ),
            "fallback_batches_used": (
                fallback_batches_used if fallback_batches_used is not None else 0
            ),
            "hard_rejections": [
                {"program_code": r.program_code, "reason_codes": list(r.reason_codes)}
                for r in self.hard_rejections
            ],
            "program_cost_estimates": [
                {
                    "program_code": est.program_code,
                    "estimated_monthly_cost_irr": str(est.estimated_monthly_cost_irr),
                    "minimum_adapted_monthly_cost_irr": (
                        str(est.minimum_adapted_monthly_cost_irr)
                        if est.minimum_adapted_monthly_cost_irr is not None
                        else None
                    ),
                    "effective_budget_tier": est.effective_budget_tier,
                    "price_coverage_complete": est.price_coverage_complete,
                    "estimate_confidence": est.estimate_confidence,
                    "reason_codes": list(est.reason_codes),
                }
                for est in self.cost_estimates
            ],
            "candidates": [
                {
                    "program_code": c.program.code,
                    "preconstruction_rank": c.preconstruction_rank,
                    "score": c.score.score.total,
                    "reason_codes": list(c.score.reason_codes),
                }
                for c in self.candidates
            ],
        }


def select_program_candidates(
    programs: Iterable[NutritionProgram],
    request: NormalizedNutritionRequest,
    *,
    cost_estimates: dict[str, ProgramCostEstimate] | None = None,
    policy_version: str = PROGRAM_SELECTION_POLICY_VERSION,
    mode: NutritionOptimizationMode = NutritionOptimizationMode.BUDGET_CONSTRAINED,
) -> ProgramSelectionResult:
    """Evaluate and rank nutrition programs using eligibility and deterministic scoring."""
    programs_list = list(programs)
    programs_considered = len(programs_list)
    hard_rejections: list[ProgramHardRejection] = []
    eligible_programs: list[tuple[NutritionProgram, ProgramCostEstimate | None]] = []

    for program in programs_list:
        estimate = cost_estimates.get(program.code) if cost_estimates else None
        eligibility: ProgramEligibilityResult = check_program_eligibility(
            program, request, cost_estimate=estimate
        )
        if not eligibility.eligible:
            hard_rejections.append(
                ProgramHardRejection(
                    program_code=program.code,
                    reason_codes=eligibility.reason_codes,
                )
            )
        else:
            eligible_programs.append((program, estimate))

    scored: list[tuple[NutritionProgram, ProgramScoringResult]] = [
        (program, score_program(program, request, cost_estimate=estimate, mode=mode))
        for program, estimate in eligible_programs
    ]

    ordered = sorted(
        scored,
        key=lambda item: (
            -item[1].score.total,
            item[0].code,
            str(item[0].id) if item[0].id is not None else "",
            item[0].slug,
        ),
    )

    candidates = tuple(
        ProgramCandidate(
            program=program,
            score=scoring_result,
            preconstruction_rank=index,
        )
        for index, (program, scoring_result) in enumerate(ordered)
    )

    recorded_estimates: tuple[ProgramCostEstimate, ...] = ()
    if cost_estimates:
        recorded_estimates = tuple(cost_estimates.values())

    return ProgramSelectionResult(
        programs_considered=programs_considered,
        hard_rejections=tuple(hard_rejections),
        candidates=candidates,
        policy_version=policy_version,
        cost_estimates=recorded_estimates,
    )


def rank_base_programs(
    programs: Iterable[NutritionProgram],
    request: NormalizedNutritionRequest,
    *,
    cost_estimates: dict[str, ProgramCostEstimate] | None = None,
    policy_version: str = PROGRAM_SELECTION_POLICY_VERSION,
) -> ProgramSelectionResult:
    """Unified base program proposal ordering combining budget, goal, preference,
    training, and meal structure."""
    return select_program_candidates(
        programs,
        request,
        cost_estimates=cost_estimates,
        policy_version=policy_version,
        mode=NutritionOptimizationMode.BUDGET_CONSTRAINED,
    )


def rank_for_budget(
    programs: Iterable[NutritionProgram],
    request: NormalizedNutritionRequest,
    *,
    cost_estimates: dict[str, ProgramCostEstimate] | None = None,
    policy_version: str = PROGRAM_SELECTION_POLICY_VERSION,
) -> ProgramSelectionResult:
    return rank_base_programs(
        programs,
        request,
        cost_estimates=cost_estimates,
        policy_version=policy_version,
    )


def rank_for_ideal(
    programs: Iterable[NutritionProgram],
    request: NormalizedNutritionRequest,
    *,
    cost_estimates: dict[str, ProgramCostEstimate] | None = None,
    policy_version: str = PROGRAM_SELECTION_POLICY_VERSION,
) -> ProgramSelectionResult:
    return select_program_candidates(
        programs,
        request,
        cost_estimates=cost_estimates,
        policy_version=policy_version,
        mode=NutritionOptimizationMode.IDEAL_REFERENCE,
    )


def _context_to_request(context: ProgramSelectionContext) -> NormalizedNutritionRequest:
    return NormalizedNutritionRequest(
        user_id="compatibility",
        fitness_goal=context.fitness_goal,
        body_weight_kg=Decimal("70.0"),
        protein_calculation_weight_kg=Decimal("70.0"),
        tdee_kcal=Decimal("2000.0"),
        monthly_budget_irr=150_000_000,
        weekly_budget_irr=34_615_384,
        budget_style=context.budget_style,
        trains=context.trains,
        exercise_type=context.exercise_type,
        training_days_per_week=None,
        training_minutes_per_session=None,
        training_intensity=None,
        training_experience=None,
        main_meal_slots=3,
        snack_slots=1,
        dietary_pattern="omnivore",
        maximum_meal_repetition_per_week=2,
        preferred_variety=context.preferred_variety,
        requested_weight_change_kg_per_week=None,
        plan_style=context.plan_style,
        cooking_skill=context.cooking_skill,
        maximum_cooking_time_minutes=context.maximum_cooking_time_minutes,
        meal_preparation_preference=context.meal_preparation_preference,
    )


def enumerate_program_candidates(
    programs: Iterable[NutritionProgram],
    context: ProgramSelectionContext,
) -> tuple[ProgramCandidate, ...]:
    """Return every active program in a stable, style-preferred order."""
    request = _context_to_request(context)
    result = select_program_candidates(programs, request)
    return result.candidates


def select_program(
    programs: Iterable[NutritionProgram],
    context: ProgramSelectionContext,
    user_id: UUID | None = None,
) -> NutritionProgram:
    """Compatibility wrapper returning the first proposal."""
    del user_id
    candidates = enumerate_program_candidates(programs, context)
    if not candidates:
        raise ValueError("No active Nutrition Program is available")
    return candidates[0].program
