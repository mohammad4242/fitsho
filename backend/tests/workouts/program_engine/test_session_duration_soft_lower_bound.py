from dataclasses import replace

import pytest

from app.workouts.program_engine.constraint_classification import (
    ConstraintClass,
    classify_constraint,
)
from app.workouts.program_engine.duration_policy import (
    calculate_main_training_minutes,
    get_session_duration_policy,
    get_session_exercise_count_policy,
    is_main_training_exercise,
)
from app.workouts.program_engine.engine import generate_program
from app.workouts.program_engine.final_gate import evaluate_final_program
from app.workouts.program_engine.normalization import normalize_request
from app.workouts.program_engine.rulesets.resistance_training_v1 import RULESET
from app.workouts.program_engine.schemas import ValidationReport
from app.workouts.program_engine.session_duration import repair_session_durations
from app.workouts.program_engine.supplemental_policy import main_exercise_count
from app.workouts.program_engine.validation import validate_program
from tests.workouts.program_engine.golden_fixtures import full_catalog, request


def _under_target_day(day):
    exercises = tuple(
        replace(item, estimated_minutes=1)
        if is_main_training_exercise(item)
        else item
        for item in day.exercises
    )
    cardio_minutes = day.cardio.duration_minutes if day.cardio is not None else 0
    return replace(
        day,
        exercises=exercises,
        estimated_duration_minutes=(
            RULESET.general_warmup_minutes
            + sum(item.estimated_minutes for item in exercises)
            + cardio_minutes
        ),
    )


def _over_target_day(day, maximum_minutes: int):
    main = tuple(item for item in day.exercises if is_main_training_exercise(item))
    exercises = tuple(
        replace(item, estimated_minutes=0) for item in day.exercises
    )
    first_main_index = next(
        index for index, item in enumerate(day.exercises) if is_main_training_exercise(item)
    )
    exercises = list(exercises)
    exercises[first_main_index] = replace(main[0], estimated_minutes=maximum_minutes + 1)
    exercises = tuple(exercises)
    cardio_minutes = day.cardio.duration_minutes if day.cardio is not None else 0
    return replace(
        day,
        exercises=exercises,
        estimated_duration_minutes=(
            RULESET.general_warmup_minutes
            + sum(item.estimated_minutes for item in exercises)
            + cardio_minutes
        ),
    )


def _generated_program(duration: int):
    source = request(
        session_duration_minutes=duration,
        available_training_days=2 if duration == 30 else 1,
    )
    result = generate_program(source, full_catalog(), RULESET, reference_templates=())
    assert result.program is not None, result.errors
    return source, result.program


@pytest.mark.parametrize("duration", [30, 45, 60, 75, 90])
def test_under_preferred_minimum_is_a_warning_and_does_not_add_work(duration: int) -> None:
    source, program = _generated_program(duration)
    day = _under_target_day(program.weekly_schedule[0])
    policy = get_session_duration_policy(duration)
    count_policy = get_session_exercise_count_policy(duration, RULESET)
    assert calculate_main_training_minutes(day) < policy.minimum_minutes
    assert main_exercise_count(day.exercises) >= count_policy.minimum_main_exercises
    original_shape = tuple(
        (item.exercise_id, item.sets, item.estimated_minutes) for item in day.exercises
    )

    normalized = normalize_request(source, RULESET)
    repaired = repair_session_durations(
        (day,), normalized, full_catalog(), RULESET
    )
    repaired_day = repaired.days[0]
    assert tuple(
        (item.exercise_id, item.sets, item.estimated_minutes)
        for item in repaired_day.exercises
    ) == original_shape
    assert "SESSION_DURATION_UNDER_TARGET" in repaired.reasons
    assert "SESSION_DURATION_TARGET_UNSATISFIED" not in repaired.reasons

    altered = replace(
        program,
        weekly_schedule=(day, *program.weekly_schedule[1:]),
    )
    report = validate_program(altered, source, RULESET)
    assert report.is_valid
    assert "SESSION_DURATION_UNDER_TARGET" in report.warnings
    assert "SESSION_DURATION_UNDER_TARGET" not in report.errors
    assert "SESSION_DURATION_TARGET_UNSATISFIED" not in report.errors

    decision = evaluate_final_program(altered, source, report, RULESET)
    assert decision.status.value in {"accepted", "accepted_with_constraints"}
    assert "SESSION_DURATION_UNDER_TARGET" not in decision.reason_codes
    assert "SESSION_DURATION_CONSTRAINT_UNEXPLAINED" not in decision.reason_codes
    assert decision.metrics["checks"]["duration"]["messages_fa"] == (
        f"برنامه اصولی با توجه به سطح و شرایط شما در "
        f"{calculate_main_training_minutes(day)} دقیقه ساخته شد."
    ,)


@pytest.mark.parametrize("duration", [30, 45, 60, 75, 90])
def test_under_preferred_minimum_with_too_few_main_exercises_remains_hard(
    duration: int,
) -> None:
    source, program = _generated_program(duration)
    day = _under_target_day(program.weekly_schedule[0])
    count_policy = get_session_exercise_count_policy(duration, RULESET)
    main = tuple(item for item in day.exercises if is_main_training_exercise(item))
    assert len(main) >= count_policy.minimum_main_exercises
    kept_main = main[: count_policy.minimum_main_exercises - 1]
    non_main = tuple(item for item in day.exercises if not is_main_training_exercise(item))
    shortened = replace(
        day,
        exercises=(*kept_main, *non_main),
        estimated_duration_minutes=RULESET.general_warmup_minutes
        + sum(item.estimated_minutes for item in (*kept_main, *non_main))
        + (day.cardio.duration_minutes if day.cardio is not None else 0),
    )

    report = validate_program(replace(program, weekly_schedule=(shortened,)), source, RULESET)

    assert "SESSION_EXERCISE_COUNT_OUT_OF_RANGE" in report.errors
    assert "SESSION_DURATION_UNDER_TARGET" in report.warnings
    assert "SESSION_DURATION_UNDER_TARGET" not in report.errors
    decision = evaluate_final_program(
        replace(program, weekly_schedule=(shortened,)), source, report, RULESET
    )
    assert decision.status.value == "rejected"
    assert "SESSION_EXERCISE_COUNT_OUT_OF_RANGE" in decision.reason_codes


@pytest.mark.parametrize("duration", [30, 45, 60, 75, 90])
def test_over_maximum_remains_hard(duration: int) -> None:
    source, program = _generated_program(duration)
    policy = get_session_duration_policy(duration)
    day = _over_target_day(program.weekly_schedule[0], policy.maximum_minutes)
    altered = replace(program, weekly_schedule=(day,))

    report = validate_program(altered, source, RULESET)

    assert "SESSION_DURATION_EXCEEDED" in report.errors
    assert "SESSION_DURATION_OVER_TARGET" in report.errors
    assert "SESSION_DURATION_TARGET_UNSATISFIED" in report.errors
    decision = evaluate_final_program(altered, source, report, RULESET)
    assert decision.status.value == "rejected"
    assert "SESSION_DURATION_OVER_TARGET" in decision.reason_codes


@pytest.mark.parametrize("duration", [30, 45, 60, 75, 90])
def test_preferred_range_is_satisfied_without_under_warning(duration: int) -> None:
    source, program = _generated_program(duration)
    policy = get_session_duration_policy(duration)
    day = program.weekly_schedule[0]
    assert policy.minimum_minutes <= calculate_main_training_minutes(day)

    report = validate_program(program, source, RULESET)

    assert "SESSION_DURATION_UNDER_TARGET" not in report.warnings
    assert "SESSION_DURATION_UNDER_TARGET" not in report.errors


def test_duration_policy_exposes_soft_lower_and_hard_upper_semantics() -> None:
    policy = get_session_duration_policy(60)

    assert policy.below_preferred_minimum(49)
    assert not policy.below_preferred_minimum(50)
    assert policy.exceeds_hard_maximum(71)
    assert not policy.exceeds_hard_maximum(70)
    assert not policy.within_preferred_range(49)
    assert policy.within_preferred_range(60)


def test_under_target_is_soft_even_after_repair_exhaustion() -> None:
    assert (
        classify_constraint("SESSION_DURATION_UNDER_TARGET", repair_exhausted=True)
        is ConstraintClass.SOFT
    )
    assert (
        classify_constraint("SESSION_DURATION_EXCEEDED", repair_exhausted=True)
        is ConstraintClass.HARD
    )
    assert (
        classify_constraint("SESSION_DURATION_OVER_TARGET", repair_exhausted=True)
        is ConstraintClass.HARD
    )


def test_final_gate_ignores_legacy_under_target_error_as_a_soft_duration_code() -> None:
    source, program = _generated_program(60)
    report = ValidationReport(
        errors=("SESSION_DURATION_UNDER_TARGET",),
        warnings=(),
        assumptions=program.assumptions,
        metrics=program.aggregate_metrics,
        decision_trace=program.decision_trace,
    )

    decision = evaluate_final_program(program, source, report, RULESET)

    assert decision.status.value in {"accepted", "accepted_with_constraints"}
    assert "SESSION_DURATION_UNDER_TARGET" not in decision.reason_codes
