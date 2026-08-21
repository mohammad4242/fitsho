from dataclasses import replace

import pytest

from app.workouts.program_engine.duration_policy import get_session_duration_policy
from app.workouts.program_engine.eligibility import filter_eligible_exercises
from app.workouts.program_engine.engine import generate_program
from app.workouts.program_engine.normalization import normalize_request
from app.workouts.program_engine.prescription import estimate_exercise_minutes
from app.workouts.program_engine.rulesets.resistance_training_v1 import RULESET
from app.workouts.program_engine.session_duration import repair_session_durations
from app.workouts.program_engine.validation import validate_program
from tests.workouts.program_engine.golden_fixtures import full_catalog, request


@pytest.mark.parametrize(
    ("requested", "minimum", "maximum"),
    [(30, 20, 40), (45, 35, 55), (60, 50, 70), (75, 65, 85), (90, 80, 100), (120, 110, 130)],
)
def test_session_duration_policy_has_exact_product_bounds(
    requested: int, minimum: int, maximum: int
) -> None:
    policy = get_session_duration_policy(requested, RULESET)

    assert (policy.minimum_minutes, policy.maximum_minutes) == (minimum, maximum)


@pytest.mark.parametrize("requested", [30, 45, 60, 75, 90])
def test_generate_program_keeps_every_session_inside_duration_target(requested: int) -> None:
    source = request(session_duration_minutes=requested, available_training_days=1)

    result = generate_program(source, full_catalog(), RULESET)

    assert result.is_success, result.errors
    assert result.program is not None
    policy = get_session_duration_policy(requested, RULESET)
    assert all(
        policy.minimum_minutes <= day.estimated_duration_minutes <= policy.maximum_minutes
        for day in result.program.weekly_schedule
    )


def test_underfilled_session_is_repaired_with_real_estimates() -> None:
    source = request(session_duration_minutes=90, available_training_days=1)
    normalized = normalize_request(source, RULESET)
    eligibility = filter_eligible_exercises(normalized, full_catalog())
    result = generate_program(source, full_catalog(), RULESET)

    assert result.program is not None
    original = result.program.weekly_schedule[0]
    reduced_exercises = tuple(
        replace(
            item,
            sets=RULESET.minimum_working_sets,
            estimated_minutes=estimate_exercise_minutes(
                RULESET.minimum_working_sets,
                item.rest_seconds,
                item.warmup_sets,
                RULESET,
            ),
        )
        for item in original.exercises
    )
    underfilled = replace(
        original,
        exercises=reduced_exercises,
        estimated_duration_minutes=RULESET.general_warmup_minutes
        + sum(item.estimated_minutes for item in reduced_exercises),
    )
    assert underfilled.estimated_duration_minutes < 80

    repaired, reasons = repair_session_durations(
        (underfilled,),
        normalized,
        eligibility.eligible,
        RULESET,
    )

    assert repaired[0].estimated_duration_minutes >= 80
    assert "SESSION_DURATION_REPAIR_APPLIED" in reasons


def test_overfilled_session_is_repaired_without_fake_duration() -> None:
    source = request(session_duration_minutes=45, available_training_days=1)
    normalized = normalize_request(source, RULESET)
    eligibility = filter_eligible_exercises(normalized, full_catalog())
    result = generate_program(source, full_catalog(), RULESET)

    assert result.program is not None
    day = result.program.weekly_schedule[0]
    exercises = tuple(
        replace(
            item,
            sets=RULESET.max_working_sets_for_exercise(
                training_status=normalized.training_status,
                goal=source.primary_goal,
                exercise_type=item.exercise_type,
                is_priority=False,
                weekly_exposure_count=1,
            ),
            estimated_minutes=estimate_exercise_minutes(
                RULESET.max_working_sets_for_exercise(
                    training_status=normalized.training_status,
                    goal=source.primary_goal,
                    exercise_type=item.exercise_type,
                    is_priority=False,
                    weekly_exposure_count=1,
                ),
                item.rest_seconds,
                item.warmup_sets,
                RULESET,
            ),
        )
        for item in day.exercises
    )
    overfilled = replace(
        day,
        exercises=exercises,
        estimated_duration_minutes=RULESET.general_warmup_minutes
        + sum(item.estimated_minutes for item in exercises),
    )
    assert overfilled.estimated_duration_minutes > 40

    repaired, reasons = repair_session_durations(
        (overfilled,),
        normalized,
        eligibility.eligible,
        RULESET,
    )

    assert repaired[0].estimated_duration_minutes <= 55
    assert repaired[0].estimated_duration_minutes >= 35
    assert "SESSION_DURATION_REPAIR_APPLIED" in reasons


def test_unsupported_target_fails_explicitly_instead_of_returning_short_session() -> None:
    result = generate_program(
        request(session_duration_minutes=180, available_training_days=1),
        full_catalog(),
        RULESET,
    )

    assert not result.is_success
    assert "SESSION_DURATION_UNDER_TARGET" in result.errors


def test_final_validator_rejects_underfilled_session() -> None:
    source = request(session_duration_minutes=45, available_training_days=1)
    result = generate_program(source, full_catalog(), RULESET)

    assert result.program is not None
    day = result.program.weekly_schedule[0]
    invalid = replace(
        result.program,
        weekly_schedule=(replace(day, estimated_duration_minutes=15),),
    )

    report = validate_program(invalid, source, RULESET)

    assert "SESSION_DURATION_UNDER_TARGET" in report.errors
    assert "SESSION_DURATION_TARGET_UNSATISFIED" in report.errors
