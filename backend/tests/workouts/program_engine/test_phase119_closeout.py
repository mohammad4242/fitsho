import pytest

from app.workouts.program_engine.duration_capacity import build_session_capacity
from app.workouts.program_engine.duration_policy import (
    get_session_duration_policy,
    validate_session_duration,
)
from app.workouts.program_engine.enums import Goal
from app.workouts.program_engine.normalization import normalize_request
from app.workouts.program_engine.rulesets.resistance_training_v1 import ProgramRuleset
from tests.workouts.program_engine.golden_fixtures import full_catalog, request

RULESET = ProgramRuleset()


def _normalized(goal, duration):
    return normalize_request(request(primary_goal=goal, session_duration_minutes=duration), RULESET)


def test_phase119_official_durations_accepted():
    for duration in [30, 45, 60, 75, 90, 120]:
        assert validate_session_duration(duration) == duration


def test_phase119_unofficial_durations_rejected():
    for duration in [20, 40, 50, 70, 100, 150]:
        with pytest.raises(ValueError):
            validate_session_duration(duration)


def test_phase119_capacity_resistance_budget_ignores_cardio():
    capacity = build_session_capacity(
        _normalized(Goal.FAT_LOSS, 45), tuple(full_catalog()), RULESET
    )
    assert capacity.resistance_work_budget_minutes == 45


def test_phase119_short_session_exercise_floor():
    capacity = build_session_capacity(
        _normalized(Goal.FAT_LOSS, 30), tuple(full_catalog()), RULESET
    )
    assert capacity.expected_exercise_count_capacity >= 3


def test_phase119_long_session_exercise_floor():
    capacity = build_session_capacity(
        _normalized(Goal.FAT_LOSS, 60), tuple(full_catalog()), RULESET
    )
    assert capacity.expected_exercise_count_capacity >= 5


def test_phase119_cardio_additive_semantics():
    from app.workouts.program_engine.cardio import add_cardio
    from app.workouts.program_engine.schemas import WorkoutDay

    source = request(primary_goal=Goal.FAT_LOSS, session_duration_minutes=45)
    normalized = normalize_request(source, RULESET)
    day = WorkoutDay(
        day_index=1, weekday=0, title="", focus="chest", exercises=(), estimated_duration_minutes=45
    )

    # Available cardio should be 10 because duration_policy.maximum_total_minutes(5) = 45+10+5 = 60
    # 60 - 45 = 15, min(10, 15) = 10
    days = add_cardio(normalized, (day,), tuple(full_catalog()), RULESET)
    assert days[0].cardio is not None
    assert days[0].cardio.duration_minutes == 10
    assert days[0].estimated_duration_minutes == 55  # 45 + 10


def test_phase119_underfill_repair_no_rest_extension():
    from app.workouts.program_engine.schemas import WorkoutDay
    from app.workouts.program_engine.session_duration import _repair_underfill

    source = request(primary_goal=Goal.FAT_LOSS, session_duration_minutes=90)
    normalized = normalize_request(source, RULESET)
    day = WorkoutDay(
        day_index=1, weekday=0, title="", focus="chest", exercises=(), estimated_duration_minutes=20
    )

    repaired = _repair_underfill(
        day,
        normalized,
        tuple(full_catalog()),
        get_session_duration_policy(90),
        RULESET,
        other_days=(),
        volume=None,
        prefer_acceptable_volume_for_minimum_fill=False,
        minimum_exercises=5,
    )

    assert len(repaired.exercises) >= 5
    # Ensure no rest extension reason code
    for ex in repaired.exercises:
        assert "REST_EXTENDED_FOR_SAFE_DURATION_TARGET" not in ex.reason_codes


@pytest.mark.parametrize("duration", [30, 45, 60, 75, 90, 120])
def test_phase119_budget_semantics_overrun_only(duration):
    from app.workouts.program_engine.engine import generate_program

    source = request(primary_goal=Goal.HYPERTROPHY, session_duration_minutes=duration)
    res = generate_program(source, full_catalog(), RULESET)
    assert res.is_success

    metrics = res.program.aggregate_metrics.get("coach_quality", {})
    duration_fit = metrics.get("duration_fit")
    assert isinstance(duration_fit, dict)
    assert {"satisfied", "total", "percentage"}.issubset(duration_fit)


@pytest.mark.parametrize("goal", [Goal.HYPERTROPHY, Goal.STRENGTH, Goal.FAT_LOSS])
@pytest.mark.parametrize("duration", [30, 45, 60, 75, 90, 120])
def test_phase119_full_matrix_semantics(goal, duration):
    from app.workouts.program_engine.engine import generate_program

    source = request(primary_goal=goal, session_duration_minutes=duration)
    res = generate_program(source, full_catalog(), RULESET)

    # 1. Program valid
    assert res.program.validation_report.is_valid

    # 2. No overrun
    policy = get_session_duration_policy(duration)
    assert all(
        (
            day.estimated_duration_minutes
            - RULESET.general_warmup_minutes
            - (day.cardio.duration_minutes if getattr(day, "cardio", None) else 0)
        )
        <= policy.maximum_minutes
        for day in res.program.weekly_schedule
    )

    # 3. Correct exercise count floor
    effective_floor = 3 if duration <= 30 else RULESET.minimum_exercises_per_session
    assert all(len(day.exercises) >= effective_floor for day in res.program.weekly_schedule)


def test_phase119_cardio_ordering_and_coach_quality_fit():
    from app.workouts.program_engine.engine import generate_program

    # Generate a program that might have cardio
    source = request(
        primary_goal=Goal.FAT_LOSS,
        session_duration_minutes=60,
        available_training_days=3,
        training_experience="beginner",
    )
    res = generate_program(source, full_catalog(), RULESET)
    assert res.is_success

    # Check that cardio is present
    has_cardio = any(day.cardio is not None for day in res.program.weekly_schedule)
    assert has_cardio

    # Check that coach_quality duration_fit is identical to engine's budget fit semantics
    engine_metrics = res.program.aggregate_metrics.get("coach_quality", {})
    budget_fit = engine_metrics["duration_fit"]["percentage"] == 100.0

    from app.workouts.program_engine.coach_quality import build_coach_quality_metrics

    cq = build_coach_quality_metrics(res.program, source, res.program.validation_report, RULESET)

    # If the engine says it fits the strict budget, the coach quality metric must be 100% satisfied
    if budget_fit:
        assert cq["duration_fit"]["percentage"] == 100.0
    else:
        # Otherwise, the days that exceeded 60 won't be counted
        assert cq["duration_fit"]["percentage"] < 100.0

    # Cardio must not affect the duration_fit
    # If we artificially strip cardio, coach quality duration fit should be identical
    from dataclasses import replace

    days_no_cardio = tuple(replace(day, cardio=None) for day in res.program.weekly_schedule)
    program_no_cardio = replace(res.program, weekly_schedule=days_no_cardio)
    cq_no_cardio = build_coach_quality_metrics(
        program_no_cardio, source, res.program.validation_report, RULESET
    )

    assert cq["duration_fit"] == cq_no_cardio["duration_fit"]


def test_phase119_coach_quality_strict_semantics():
    from dataclasses import replace

    from app.workouts.program_engine.coach_quality import _duration_fit

    # Mock a program
    source = request(session_duration_minutes=60)
    from app.workouts.program_engine.engine import generate_program

    res = generate_program(source, full_catalog(), RULESET)
    program = res.program

    # 60 requested / 68 resistance = not fit
    day_over = replace(
        program.weekly_schedule[0],
        estimated_duration_minutes=68 + RULESET.general_warmup_minutes,
        cardio=None,
    )
    program_over = replace(program, weekly_schedule=(day_over,))
    cq_over = _duration_fit(program_over, source, program.validation_report, RULESET)
    assert cq_over["percentage"] == 0.0

    # 60 requested / 50 complete resistance = fit
    day_under = replace(
        program.weekly_schedule[0],
        estimated_duration_minutes=50 + RULESET.general_warmup_minutes,
        cardio=None,
    )
    program_under = replace(program, weekly_schedule=(day_under,))
    cq_under = _duration_fit(program_under, source, program.validation_report, RULESET)
    assert cq_under["percentage"] == 100.0


def test_phase119_cardio_additive():
    from app.workouts.program_engine.engine import generate_program

    # A long session (120 mins) that would normally squeeze cardio out if they were coupled
    source = request(
        primary_goal=Goal.FAT_LOSS,
        session_duration_minutes=120,
        available_training_days=3,
        training_experience="beginner",
    )
    res = generate_program(source, full_catalog(), RULESET)
    assert res.is_success

    # Check that cardio is present and uses EXACTLY the configured start minutes
    days_with_cardio = [d for d in res.program.weekly_schedule if d.cardio is not None]
    assert days_with_cardio, "Expected cardio to be prescribed"
    for day in days_with_cardio:
        assert day.cardio.duration_minutes == RULESET.cardio_start_minutes


def test_phase119_underfill_does_not_inflate_sets():
    import uuid

    from app.exercises.enums import ExerciseType, MuscleGroup
    from app.workouts.program_engine.duration_policy import get_session_duration_policy
    from app.workouts.program_engine.normalization import normalize_request
    from app.workouts.program_engine.schemas import ProgrammedExercise, WorkoutDay
    from app.workouts.program_engine.session_duration import _repair_underfill

    raw_source = request(session_duration_minutes=60)
    source = normalize_request(raw_source, RULESET)

    day = WorkoutDay(
        day_index=0,
        weekday=0,
        title="Test",
        focus="upper",
        estimated_duration_minutes=10,
        exercises=(
            ProgrammedExercise(
                exercise_id=uuid.uuid4(),
                exercise_name="Mock",
                order=1,
                sets=3,
                rep_min=8,
                rep_max=12,
                target_rir=2,
                rest_seconds=60,
                estimated_minutes=10,
                exercise_type=ExerciseType.COMPOUND,
                primary_muscle=MuscleGroup.CHEST,
                counts_toward_volume=True,
                reason_codes=(),
            ),
        ),
        cardio=None,
    )

    policy = get_session_duration_policy(60)
    repaired_day = _repair_underfill(
        day,
        source,
        candidates=(),
        policy=policy,
        ruleset=RULESET,
        other_days=(),
        volume=None,
        prefer_acceptable_volume_for_minimum_fill=False,
        minimum_exercises=5,
    )

    assert len(repaired_day.exercises) == 1
    assert repaired_day.exercises[0].sets == 3
