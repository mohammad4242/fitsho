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
        _normalized(Goal.FAT_LOSS, 45), tuple(full_catalog()), RULESET, cardio_reserve_minutes=10
    )
    assert capacity.resistance_work_budget_minutes == 45

def test_phase119_short_session_exercise_floor():
    capacity = build_session_capacity(
        _normalized(Goal.FAT_LOSS, 30), tuple(full_catalog()), RULESET, cardio_reserve_minutes=10
    )
    assert capacity.expected_exercise_count_capacity >= 3

def test_phase119_long_session_exercise_floor():
    capacity = build_session_capacity(
        _normalized(Goal.FAT_LOSS, 60), tuple(full_catalog()), RULESET, cardio_reserve_minutes=10
    )
    assert capacity.expected_exercise_count_capacity >= 5


def test_phase119_cardio_additive_semantics():
    from app.workouts.program_engine.cardio import add_cardio
    from app.workouts.program_engine.schemas import WorkoutDay
    
    source = request(primary_goal=Goal.FAT_LOSS, session_duration_minutes=45)
    normalized = normalize_request(source, RULESET)
    day = WorkoutDay(day_index=1, weekday=0, title="", focus="chest", exercises=(), estimated_duration_minutes=45)

    # Available cardio should be 10 because duration_policy.maximum_total_minutes(5) = 45+10+5 = 60
    # 60 - 45 = 15, min(10, 15) = 10
    days = add_cardio(normalized, (day,), tuple(full_catalog()), RULESET)
    assert days[0].cardio is not None
    assert days[0].cardio.duration_minutes == 10
    assert days[0].estimated_duration_minutes == 55 # 45 + 10

def test_phase119_underfill_repair_no_rest_extension():
    from app.workouts.program_engine.schemas import WorkoutDay
    from app.workouts.program_engine.session_duration import _repair_underfill
    
    source = request(primary_goal=Goal.FAT_LOSS, session_duration_minutes=90)
    normalized = normalize_request(source, RULESET)
    day = WorkoutDay(day_index=1, weekday=0, title="", focus="chest", exercises=(), estimated_duration_minutes=20)
    
    repaired = _repair_underfill(
        day, normalized, tuple(full_catalog()), get_session_duration_policy(90), RULESET,
        other_days=(), volume=None, prefer_acceptable_volume_for_minimum_fill=False,
        minimum_exercises=5
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
    assert "resistance_time_budget_fit" in metrics
    assert "resistance_time_utilization" in metrics
    assert "resistance_time_overrun_minutes" in metrics
    assert "duration_constrained_quality" in metrics
    assert "late_duration_repair_class" in metrics
    
    assert metrics["resistance_time_budget_fit"] is True


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
        day.estimated_duration_minutes - RULESET.general_warmup_minutes <= policy.maximum_minutes
        for day in res.program.weekly_schedule
    )
    
    # 3. Correct exercise count floor
    effective_floor = 3 if duration <= 30 else RULESET.minimum_exercises_per_session
    assert all(
        len(day.exercises) >= effective_floor
        for day in res.program.weekly_schedule
    )
