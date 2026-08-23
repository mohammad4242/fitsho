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
from app.workouts.program_engine.volume_planner import plan_weekly_volume
from tests.workouts.program_engine.golden_fixtures import full_catalog, request


@pytest.mark.parametrize(
    ("requested", "minimum", "maximum"),
    [(30, 20, 40), (45, 35, 55), (60, 50, 70), (75, 65, 85), (90, 80, 100), (120, 110, 130)],
)
def test_session_duration_policy_has_exact_product_bounds(
    requested: int, minimum: int, maximum: int
) -> None:
    policy = get_session_duration_policy(requested)

    assert (policy.minimum_minutes, policy.maximum_minutes) == (minimum, maximum)


def test_general_warmup_is_outside_the_requested_workout_duration() -> None:
    source = request(session_duration_minutes=60, available_training_days=1)
    result = generate_program(source, full_catalog(), RULESET)
    assert result.program is not None, result.errors
    day = result.program.weekly_schedule[0]
    normal_upper_total = source.session_duration_minutes + 10 + RULESET.general_warmup_minutes
    program = replace(
        result.program,
        weekly_schedule=(replace(day, estimated_duration_minutes=normal_upper_total),),
    )

    report = validate_program(program, source, RULESET)

    assert "SESSION_DURATION_EXCEEDED" not in report.errors
    assert "SESSION_DURATION_OVER_TARGET" not in report.errors


def test_high_quality_fifty_two_minute_workout_satisfies_sixty_minute_request() -> None:
    source = request(session_duration_minutes=60, available_training_days=1)
    result = generate_program(source, full_catalog(), RULESET)
    assert result.program is not None, result.errors
    day = result.program.weekly_schedule[0]
    program = replace(
        result.program,
        weekly_schedule=(
            replace(day, estimated_duration_minutes=52 + RULESET.general_warmup_minutes),
        ),
    )

    report = validate_program(program, source, RULESET)

    assert "SESSION_DURATION_UNDER_TARGET" not in report.errors
    assert "SESSION_DURATION_TARGET_UNSATISFIED" not in report.errors


def test_useful_workload_limit_does_not_force_artificial_rest() -> None:
    source = request(
        session_duration_minutes=75,
        available_training_days=3,
        training_experience="beginner",
        training_age_months=3,
        primary_goal="muscle_gain",
        priority_muscles=["chest", "back"],
    )

    result = generate_program(source, full_catalog(), RULESET, reference_templates=())

    assert result.program is not None, result.errors
    assert "SESSION_DURATION_CONSTRAINED_BY_USEFUL_WORKLOAD" in result.program.warnings
    assert all(
        "SESSION_DURATION_REPAIR_EXTENDED_REST" not in exercise.reason_codes
        for day in result.program.weekly_schedule
        for exercise in day.exercises
    )


def test_optional_template_work_is_removed_before_core_for_duration() -> None:
    source = request(session_duration_minutes=60, available_training_days=1)
    normalized = normalize_request(source, RULESET)
    test_ruleset = replace(RULESET, minimum_exercises_per_session=2)
    result = generate_program(source, full_catalog(), RULESET)
    assert result.program is not None, result.errors
    day = result.program.weekly_schedule[0]
    base = day.exercises[:3]
    assert len(base) == 3
    exercises = tuple(
        replace(
            item,
            sets=RULESET.minimum_working_sets,
            rest_seconds=RULESET.minimum_rest_seconds,
            estimated_minutes=30,
            reason_codes=(
                "TEMPLATE_ADAPTATION_PRIORITY:optional"
                if index == len(base) - 1
                else "TEMPLATE_ADAPTATION_PRIORITY:core",
            ),
        )
        for index, item in enumerate(base)
    )
    overfilled = replace(
        day,
        focus="template_reference_1",
        exercises=exercises,
        cardio=None,
        estimated_duration_minutes=RULESET.general_warmup_minutes
        + sum(item.estimated_minutes for item in exercises),
    )

    repaired, _ = repair_session_durations((overfilled,), normalized, (), test_ruleset)

    assert exercises[-1].exercise_id not in {item.exercise_id for item in repaired[0].exercises}
    assert {item.exercise_id for item in exercises[:-1]}.issubset(
        {item.exercise_id for item in repaired[0].exercises}
    )


def test_core_preservation_can_extend_workout_to_plus_twenty_with_reason() -> None:
    source = request(session_duration_minutes=60, available_training_days=1)
    normalized = normalize_request(source, RULESET)
    result = generate_program(source, full_catalog(), RULESET)
    assert result.program is not None, result.errors
    day = result.program.weekly_schedule[0]
    base = day.exercises[: RULESET.minimum_exercises_per_session]
    exercises = tuple(
        replace(
            item,
            sets=RULESET.minimum_working_sets,
            rest_seconds=RULESET.minimum_rest_seconds,
            estimated_minutes=15,
            reason_codes=("TEMPLATE_ADAPTATION_PRIORITY:core",),
        )
        for item in base
    )
    overfilled = replace(
        day,
        focus="template_reference_1",
        exercises=exercises,
        cardio=None,
        estimated_duration_minutes=RULESET.general_warmup_minutes
        + sum(item.estimated_minutes for item in exercises),
    )

    repaired, reasons = repair_session_durations((overfilled,), normalized, (), RULESET)

    assert repaired[0].exercises == exercises
    assert repaired[0].estimated_duration_minutes == 80
    assert "SESSION_DURATION_EXTENDED_TO_PRESERVE_CORE" in reasons


def test_core_preservation_extension_is_a_valid_user_facing_warning() -> None:
    source = request(session_duration_minutes=60, available_training_days=1)
    result = generate_program(source, full_catalog(), RULESET)
    assert result.program is not None, result.errors
    day = replace(
        result.program.weekly_schedule[0],
        estimated_duration_minutes=80,
    )
    trace = result.program.decision_trace + (
        {
            "stage": "session_duration",
            "reason_codes": ("SESSION_DURATION_EXTENDED_TO_PRESERVE_CORE",),
        },
    )
    program = replace(result.program, weekly_schedule=(day,), decision_trace=trace)

    report = validate_program(program, source, RULESET)

    assert "SESSION_DURATION_EXTENDED_TO_PRESERVE_CORE" in report.warnings
    assert "SESSION_DURATION_EXCEEDED" not in report.errors


def test_core_preservation_cannot_extend_beyond_plus_twenty() -> None:
    source = request(session_duration_minutes=60, available_training_days=1)
    result = generate_program(source, full_catalog(), RULESET)
    assert result.program is not None, result.errors
    day = replace(
        result.program.weekly_schedule[0],
        estimated_duration_minutes=86,
    )
    trace = result.program.decision_trace + (
        {
            "stage": "session_duration",
            "reason_codes": ("SESSION_DURATION_EXTENDED_TO_PRESERVE_CORE",),
        },
    )
    program = replace(result.program, weekly_schedule=(day,), decision_trace=trace)

    report = validate_program(program, source, RULESET)

    assert "SESSION_DURATION_EXCEEDED" in report.errors


@pytest.mark.parametrize("requested", [30, 45, 60, 75, 90])
def test_generate_program_keeps_every_session_inside_duration_target(requested: int) -> None:
    source = request(session_duration_minutes=requested, available_training_days=1)

    result = generate_program(source, full_catalog(), RULESET)

    assert result.is_success, result.errors
    assert result.program is not None
    policy = get_session_duration_policy(requested)
    assert all(
        policy.contains_total(day.estimated_duration_minutes, RULESET.general_warmup_minutes)
        for day in result.program.weekly_schedule
    )


def test_advanced_strength_program_supports_120_minute_session_policy() -> None:
    source = request(
        session_duration_minutes=120,
        available_training_days=1,
        primary_goal="strength",
        training_experience="advanced",
        training_age_months=72,
    )

    result = generate_program(source, full_catalog(), RULESET)

    assert result.is_success, result.errors
    assert result.program is not None
    policy = get_session_duration_policy(120)
    assert policy.contains_total(
        result.program.weekly_schedule[0].estimated_duration_minutes,
        RULESET.general_warmup_minutes,
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
    assert underfilled.estimated_duration_minutes < 80 + RULESET.general_warmup_minutes

    repaired, reasons = repair_session_durations(
        (underfilled,),
        normalized,
        eligibility.eligible,
        RULESET,
    )

    assert repaired[0].estimated_duration_minutes >= 80 + RULESET.general_warmup_minutes
    assert "SESSION_DURATION_REPAIR_APPLIED" in reasons


def test_duration_repair_cannot_add_hidden_or_per_session_volume() -> None:
    source = request(session_duration_minutes=60, available_training_days=1)
    normalized = normalize_request(source, RULESET)
    result = generate_program(source, full_catalog(), RULESET)
    assert result.program is not None
    chest = next(
        item
        for item in result.program.weekly_schedule[0].exercises
        if item.primary_muscle is not None and item.primary_muscle.value == "chest"
    )
    exercises = (replace(chest, sets=3), replace(chest, exercise_id=full_catalog()[1].id, sets=3))
    day = replace(
        result.program.weekly_schedule[0],
        exercises=exercises,
        estimated_duration_minutes=RULESET.general_warmup_minutes
        + sum(item.estimated_minutes for item in exercises),
    )
    volume = plan_weekly_volume(normalized, result.program.split, RULESET)
    chest_candidates = tuple(
        item for item in full_catalog() if item.primary_muscle is chest.primary_muscle
    )

    repaired, _ = repair_session_durations(
        (day,),
        normalized,
        chest_candidates,
        RULESET,
        volume=volume,
    )

    repaired_chest = tuple(
        item for item in repaired[0].exercises if item.primary_muscle is chest.primary_muscle
    )
    assert sum(item.sets for item in repaired_chest) <= RULESET.max_sets_per_muscle_per_session
    assert all(item.counts_toward_volume for item in repaired[0].exercises)


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

    assert repaired[0].estimated_duration_minutes <= 55 + RULESET.general_warmup_minutes
    assert repaired[0].estimated_duration_minutes >= 35 + RULESET.general_warmup_minutes
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
