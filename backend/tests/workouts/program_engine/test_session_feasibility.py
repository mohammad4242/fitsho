from dataclasses import replace
from types import SimpleNamespace
from uuid import uuid4

from app.exercises.enums import ExerciseLabel, ExerciseType, MuscleGroup
from app.workouts.program_engine.engine import generate_program
from app.workouts.program_engine.final_gate import evaluate_final_program
from app.workouts.program_engine.rulesets.resistance_training_v1 import RULESET
from app.workouts.program_engine.schemas import ValidationReport
from app.workouts.program_engine.session_duration import SessionDurationRepairEvidence
from app.workouts.program_engine.session_feasibility import (
    SESSION_COUNT_CONSTRAINED_REASON,
    SessionCountStatus,
    SessionFeasibilityEvidence,
    absolute_minimum_main_exercise_count,
    assess_session_count,
)
from app.workouts.program_engine.supplemental_policy import is_main_resistance_exercise
from tests.workouts.program_engine.golden_fixtures import full_catalog, request


def _exercise(
    exercise_type: ExerciseType,
    primary_muscle: MuscleGroup,
    *,
    labels: frozenset[ExerciseLabel] = frozenset(),
):
    return SimpleNamespace(
        exercise_id=uuid4(),
        exercise_type=exercise_type,
        primary_muscle=primary_muscle,
        labels=labels,
    )


def _day(*exercises):
    return SimpleNamespace(day_index=1, exercises=tuple(exercises))


def _complete_evidence(day, *, feasible_candidate_count: int = 0):
    return SessionFeasibilityEvidence.from_day(
        day,
        requested_minutes=60,
        ruleset=RULESET,
        candidate_pool_count=3,
        classified_candidate_count=3,
        feasible_candidate_count=feasible_candidate_count,
        rejection_reason_counts={"CANDIDATE_WEEKLY_HARD_VOLUME_LIMIT": 3},
        search_exhausted=True,
        candidate_pool_complete=True,
    )


def test_underpreferred_count_without_evidence_is_unproven_and_rejected() -> None:
    day = _day(*(_exercise(ExerciseType.COMPOUND, MuscleGroup.CHEST) for _ in range(4)))

    assessment = assess_session_count(day, requested_minutes=60, ruleset=RULESET)

    assert assessment.status is SessionCountStatus.UNPROVEN
    assert not assessment.evidence_complete
    assert assessment.reason_codes == ("SESSION_EXERCISE_COUNT_OUT_OF_RANGE",)


def test_complete_evidence_accepts_only_a_constrained_underfilled_count() -> None:
    day = _day(*(_exercise(ExerciseType.COMPOUND, MuscleGroup.CHEST) for _ in range(4)))
    evidence = _complete_evidence(day)

    assessment = assess_session_count(
        day,
        requested_minutes=60,
        ruleset=RULESET,
        evidence=evidence,
    )

    assert assessment.status is SessionCountStatus.CONSTRAINED
    assert assessment.evidence_complete
    assert assessment.reason_codes == (SESSION_COUNT_CONSTRAINED_REASON,)


def test_one_safe_useful_non_redundant_candidate_invalidates_constrained_evidence() -> None:
    day = _day(*(_exercise(ExerciseType.COMPOUND, MuscleGroup.CHEST) for _ in range(4)))
    evidence = _complete_evidence(day, feasible_candidate_count=1)

    assessment = assess_session_count(
        day,
        requested_minutes=60,
        ruleset=RULESET,
        evidence=evidence,
    )

    assert assessment.status is SessionCountStatus.UNPROVEN
    assert not assessment.evidence_complete
    assert assessment.reason_codes == ("SESSION_EXERCISE_COUNT_OUT_OF_RANGE",)


def test_incomplete_candidate_search_cannot_explain_underfilled_count() -> None:
    day = _day(*(_exercise(ExerciseType.COMPOUND, MuscleGroup.CHEST) for _ in range(4)))
    evidence = SessionFeasibilityEvidence.from_day(
        day,
        requested_minutes=60,
        ruleset=RULESET,
        candidate_pool_count=3,
        classified_candidate_count=3,
        feasible_candidate_count=0,
        rejection_reason_counts={"CANDIDATE_WEEKLY_HARD_VOLUME_LIMIT": 3},
        search_exhausted=False,
        candidate_pool_complete=True,
    )

    assessment = assess_session_count(
        day,
        requested_minutes=60,
        ruleset=RULESET,
        evidence=evidence,
    )

    assert assessment.status is SessionCountStatus.UNPROVEN
    assert not assessment.evidence_complete


def test_absolute_minimum_floor_is_three_for_45_and_four_for_60_minutes() -> None:
    assert absolute_minimum_main_exercise_count(45, RULESET) == 3
    assert absolute_minimum_main_exercise_count(60, RULESET) == 4


def test_complete_evidence_below_absolute_minimum_remains_hard() -> None:
    day = _day(*(_exercise(ExerciseType.COMPOUND, MuscleGroup.CHEST) for _ in range(3)))
    evidence = SessionFeasibilityEvidence.from_day(
        day,
        requested_minutes=60,
        ruleset=RULESET,
        candidate_pool_count=3,
        classified_candidate_count=3,
        feasible_candidate_count=0,
        rejection_reason_counts={"CANDIDATE_WEEKLY_HARD_VOLUME_LIMIT": 3},
        search_exhausted=True,
        candidate_pool_complete=True,
    )

    assessment = assess_session_count(
        day,
        requested_minutes=60,
        ruleset=RULESET,
        evidence=evidence,
    )

    assert evidence.absolute_minimum_main_exercises == 4
    assert assessment.status is SessionCountStatus.UNPROVEN
    assert assessment.reason_codes == ("SESSION_EXERCISE_COUNT_OUT_OF_RANGE",)


def test_required_slot_failure_invalidates_constrained_evidence() -> None:
    day = _day(*(_exercise(ExerciseType.COMPOUND, MuscleGroup.CHEST) for _ in range(4)))
    evidence = SessionFeasibilityEvidence.from_day(
        day,
        requested_minutes=60,
        ruleset=RULESET,
        candidate_pool_count=3,
        classified_candidate_count=3,
        feasible_candidate_count=0,
        rejection_reason_counts={"CANDIDATE_WEEKLY_HARD_VOLUME_LIMIT": 3},
        search_exhausted=True,
        candidate_pool_complete=True,
        required_slots_satisfied=False,
    )

    assessment = assess_session_count(
        day,
        requested_minutes=60,
        ruleset=RULESET,
        evidence=evidence,
    )

    assert assessment.status is SessionCountStatus.UNPROVEN
    assert not evidence.evidence_complete


def test_core_cardio_and_warmup_are_not_main_count() -> None:
    day = _day(
        *(_exercise(ExerciseType.COMPOUND, MuscleGroup.CHEST) for _ in range(4)),
        _exercise(ExerciseType.CORE, MuscleGroup.ABS),
        _exercise(
            ExerciseType.OTHER,
            MuscleGroup.CHEST,
            labels=frozenset({ExerciseLabel.CARDIO}),
        ),
    )
    evidence = _complete_evidence(day)

    assessment = assess_session_count(
        day,
        requested_minutes=60,
        ruleset=RULESET,
        evidence=evidence,
    )

    assert assessment.actual_main_exercises == 4
    assert is_main_resistance_exercise(day.exercises[4]) is False
    assert is_main_resistance_exercise(day.exercises[5]) is False


def test_final_gate_accepts_exactly_proven_constrained_count_with_warning() -> None:
    source = request(session_duration_minutes=60, available_training_days=1)
    result = generate_program(source, full_catalog(), RULESET)
    assert result.program is not None, result.errors
    base = result.program
    day = base.weekly_schedule[0]
    main = tuple(item for item in day.exercises if is_main_resistance_exercise(item))
    assert len(main) >= 4
    selected = set(item.exercise_id for item in main[:4])
    constrained_day = replace(
        day,
        exercises=tuple(
            item
            for item in day.exercises
            if not is_main_resistance_exercise(item) or item.exercise_id in selected
        ),
    )
    feasibility = _complete_evidence(constrained_day)
    duration_evidence = SessionDurationRepairEvidence.from_day(
        constrained_day,
        (SESSION_COUNT_CONSTRAINED_REASON,),
        feasibility=feasibility,
    )
    trace = tuple(
        {
            **entry,
            "per_session_evidence": (duration_evidence.as_trace(),),
        }
        if entry.get("stage") == "session_duration"
        else entry
        for entry in base.decision_trace
    )
    candidate = replace(base, weekly_schedule=(constrained_day,), decision_trace=trace)
    report = ValidationReport(
        errors=(),
        warnings=(SESSION_COUNT_CONSTRAINED_REASON,),
        assumptions=base.assumptions,
        metrics=candidate.aggregate_metrics,
        decision_trace=trace,
    )

    decision = evaluate_final_program(candidate, source, report, RULESET)

    assert decision.status is not None
    assert decision.status.value == "accepted_with_constraints"
    assert decision.metrics["checks"]["exercise_count"]["status"] == "constrained"
    assert SESSION_COUNT_CONSTRAINED_REASON in decision.constraint_reason_codes
