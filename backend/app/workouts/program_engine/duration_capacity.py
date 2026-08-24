from dataclasses import dataclass
from enum import StrEnum

from app.exercises.enums import ExerciseLabel, ExerciseType
from app.workouts.program_engine.duration_policy import get_session_duration_policy
from app.workouts.program_engine.enums import Goal
from app.workouts.program_engine.prescription import (
    estimate_exercise_minutes,
    prescription_for,
)
from app.workouts.program_engine.rulesets.resistance_training_v1 import ProgramRuleset
from app.workouts.program_engine.schemas import ExerciseCandidate, NormalizedProgramRequest
from app.workouts.program_engine.strength_programming import classify_strength_role


class CapacityFeasibility(StrEnum):
    COMFORTABLY_FEASIBLE = "comfortably_feasible"
    FEASIBLE_BUT_TIGHT = "feasible_but_tight"
    PROVABLY_INFEASIBLE = "provably_infeasible"


@dataclass(frozen=True)
class PlannedWorkCost:
    minutes: int
    working_sets: int
    exercise_count: int = 1

    def __post_init__(self) -> None:
        if self.minutes < 0 or self.working_sets < 0 or self.exercise_count < 0:
            raise ValueError("planned work cost values must be non-negative")


@dataclass(frozen=True)
class CandidateWorkCost(PlannedWorkCost):
    rest_seconds: int = 0
    warmup_sets: int = 0


@dataclass(frozen=True)
class SessionCapacity:
    requested_workout_minutes: int
    target_total_minutes: int
    minimum_workout_minutes: int
    maximum_workout_minutes: int
    resistance_work_budget_minutes: int
    minimum_resistance_work_minutes: int
    maximum_resistance_work_minutes: int
    expected_exercise_count_capacity: int
    expected_working_set_capacity: int
    representative_exercise_minutes: int


@dataclass(frozen=True)
class SessionCapacityAssessment:
    capacity: SessionCapacity
    status: CapacityFeasibility
    required_work_cost_minutes: int
    complete_work_cost_minutes: int
    required_working_sets: int
    complete_working_sets: int
    required_exercise_count: int
    complete_exercise_count: int
    optional_capacity_minutes: int
    optional_work_likely_trimmed: int
    reason_codes: tuple[str, ...]


def estimate_candidate_cost(
    request: NormalizedProgramRequest,
    candidate: ExerciseCandidate,
    ruleset: ProgramRuleset,
    *,
    sets: int | None = None,
    is_first_compound: bool = False,
) -> CandidateWorkCost:
    strength_role = (
        classify_strength_role(candidate, request, ruleset).role
        if request.primary_goal is Goal.STRENGTH
        else None
    )
    prescription = prescription_for(
        request.primary_goal,
        candidate.exercise_type,
        request.training_status,
        ruleset,
        prescription_mode=candidate.prescription_mode,
        duration_min_seconds=candidate.duration_min_seconds,
        duration_max_seconds=candidate.duration_max_seconds,
        strength_role=strength_role,
        fatigue_cost=candidate.fatigue_cost,
    )
    is_priority = candidate.primary_muscle in request.source.priority_muscles
    working_set_cap = ruleset.max_working_sets_for_exercise(
        training_status=request.training_status,
        goal=request.primary_goal,
        exercise_type=candidate.exercise_type,
        is_priority=is_priority,
        weekly_exposure_count=1,
        is_primary_strength=(
            request.primary_goal is Goal.STRENGTH
            and strength_role is not None
            and strength_role.value == "primary_strength"
        ),
    )
    working_sets = min(
        max(ruleset.minimum_working_sets, sets or ruleset.minimum_working_sets),
        working_set_cap,
    )
    warmup_sets = 0
    if is_first_compound and candidate.exercise_type is ExerciseType.COMPOUND:
        warmup_sets = (
            ruleset.strength_compound_warmup_sets
            if request.primary_goal is Goal.STRENGTH
            else ruleset.first_compound_warmup_sets
        )
    return CandidateWorkCost(
        minutes=estimate_exercise_minutes(
            working_sets,
            prescription.rest_seconds,
            warmup_sets,
            ruleset,
        ),
        working_sets=working_sets,
        rest_seconds=prescription.rest_seconds,
        warmup_sets=warmup_sets,
    )


def build_session_capacity(
    request: NormalizedProgramRequest,
    candidates: tuple[ExerciseCandidate, ...],
    ruleset: ProgramRuleset,
) -> SessionCapacity:
    """Build session capacity where `resistance_work_budget_minutes` equals the
    full ``session_duration_minutes``.  Cardio is scheduled *outside* and after
    the resistance block; it does NOT reduce the resistance budget."""
    duration_policy = get_session_duration_policy(request.source.session_duration_minutes)
    # Resistance budget = full requested minutes.  Cardio is additive.
    resistance_budget = duration_policy.requested_minutes
    minimum_resistance = duration_policy.minimum_minutes
    maximum_resistance = duration_policy.maximum_minutes
    representative = _representative_candidate(request, candidates, ruleset)
    if representative is None:
        exercise_capacity = 0
        working_set_capacity = 0
        representative_minutes = 0
        first_cost = None
        later_cost = None
    else:
        first_cost = estimate_candidate_cost(
            request,
            representative,
            ruleset,
            is_first_compound=True,
        )
        later_cost = estimate_candidate_cost(request, representative, ruleset)
        exercise_capacity = _exercise_capacity(
            resistance_budget,
            first_cost.minutes,
            later_cost.minutes,
            ruleset.max_exercises_per_session,
        )
        working_set_capacity = _working_set_capacity(
            request,
            representative,
            ruleset,
            resistance_budget,
            exercise_capacity,
            first_cost,
            later_cost,
        )
        representative_minutes = later_cost.minutes
    # Unreserved fields now equal the main fields (they're the same —
    # no cardio deduction), kept for backward API compatibility.
    return SessionCapacity(
        requested_workout_minutes=duration_policy.requested_minutes,
        target_total_minutes=duration_policy.requested_minutes + ruleset.general_warmup_minutes,
        minimum_workout_minutes=duration_policy.minimum_minutes,
        maximum_workout_minutes=duration_policy.maximum_minutes,
        resistance_work_budget_minutes=resistance_budget,
        minimum_resistance_work_minutes=minimum_resistance,
        maximum_resistance_work_minutes=maximum_resistance,
        expected_exercise_count_capacity=exercise_capacity,
        expected_working_set_capacity=working_set_capacity,
        representative_exercise_minutes=representative_minutes,
    )


def assess_session_capacity(
    capacity: SessionCapacity,
    *,
    required_work: tuple[PlannedWorkCost, ...],
    optional_work: tuple[PlannedWorkCost, ...],
) -> SessionCapacityAssessment:
    required_minutes = sum(item.minutes for item in required_work)
    optional_minutes = sum(item.minutes for item in optional_work)
    complete_minutes = required_minutes + optional_minutes
    optional_capacity = max(0, capacity.resistance_work_budget_minutes - required_minutes)
    optional_fitted = 0
    used_optional_minutes = 0
    for item in optional_work:
        if used_optional_minutes + item.minutes > optional_capacity:
            continue
        used_optional_minutes += item.minutes
        optional_fitted += 1
    optional_trimmed = len(optional_work) - optional_fitted
    if required_minutes > capacity.maximum_resistance_work_minutes:
        status = CapacityFeasibility.PROVABLY_INFEASIBLE
        reasons = ("REQUIRED_WORK_EXCEEDS_DURATION_CAPACITY",)
    elif complete_minutes > capacity.resistance_work_budget_minutes:
        status = CapacityFeasibility.FEASIBLE_BUT_TIGHT
        reasons = ("OPTIONAL_WORK_EXCEEDS_DURATION_CAPACITY",)
    else:
        status = CapacityFeasibility.COMFORTABLY_FEASIBLE
        reasons = ("SESSION_WORK_FITS_DURATION_CAPACITY",)
    return SessionCapacityAssessment(
        capacity=capacity,
        status=status,
        required_work_cost_minutes=required_minutes,
        complete_work_cost_minutes=complete_minutes,
        required_working_sets=sum(item.working_sets for item in required_work),
        complete_working_sets=sum(item.working_sets for item in (*required_work, *optional_work)),
        required_exercise_count=sum(item.exercise_count for item in required_work),
        complete_exercise_count=sum(
            item.exercise_count for item in (*required_work, *optional_work)
        ),
        optional_capacity_minutes=optional_capacity,
        optional_work_likely_trimmed=optional_trimmed,
        reason_codes=reasons,
    )


def _representative_candidate(
    request: NormalizedProgramRequest,
    candidates: tuple[ExerciseCandidate, ...],
    ruleset: ProgramRuleset,
) -> ExerciseCandidate | None:
    resistance_candidates = tuple(
        candidate
        for candidate in candidates
        if candidate.exercise_type
        in {ExerciseType.COMPOUND, ExerciseType.ISOLATION, ExerciseType.CORE}
        and ExerciseLabel.CARDIO not in candidate.labels
    )
    compounds = tuple(
        candidate
        for candidate in resistance_candidates
        if candidate.exercise_type is ExerciseType.COMPOUND
    )
    pool = compounds or resistance_candidates
    if not pool:
        return None
    ranked = sorted(
        pool,
        key=lambda candidate: (
            estimate_candidate_cost(request, candidate, ruleset).minutes,
            str(candidate.id),
        ),
    )
    return ranked[len(ranked) // 2]


def _exercise_capacity(
    resistance_budget: int,
    first_exercise_minutes: int,
    later_exercise_minutes: int,
    maximum_exercises: int,
) -> int:
    if resistance_budget < first_exercise_minutes:
        return 0
    remaining = resistance_budget - first_exercise_minutes
    return min(maximum_exercises, 1 + remaining // max(1, later_exercise_minutes))


def _working_set_capacity(
    request: NormalizedProgramRequest,
    representative: ExerciseCandidate,
    ruleset: ProgramRuleset,
    resistance_budget: int,
    exercise_capacity: int,
    first_cost: CandidateWorkCost,
    later_cost: CandidateWorkCost,
) -> int:
    if exercise_capacity == 0:
        return 0
    base_minutes = first_cost.minutes + (exercise_capacity - 1) * later_cost.minutes
    base_sets = exercise_capacity * later_cost.working_sets
    extra_cost = estimate_candidate_cost(
        request,
        representative,
        ruleset,
        sets=later_cost.working_sets + 1,
    )
    marginal_minutes = max(1, extra_cost.minutes - later_cost.minutes)
    per_exercise_headroom = max(0, extra_cost.working_sets - later_cost.working_sets)
    extra_sets = min(
        max(0, resistance_budget - base_minutes) // marginal_minutes,
        exercise_capacity * per_exercise_headroom,
    )
    return base_sets + extra_sets
