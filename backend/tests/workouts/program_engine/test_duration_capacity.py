from importlib import import_module

from app.exercises.enums import MuscleGroup
from app.workouts.program_engine.cardio import planned_cardio_day_indexes
from app.workouts.program_engine.duration_policy import get_session_duration_policy
from app.workouts.program_engine.engine import generate_program
from app.workouts.program_engine.enums import Goal
from app.workouts.program_engine.normalization import normalize_request
from app.workouts.program_engine.rulesets.resistance_training_v1 import RULESET
from app.workouts.program_engine.split_selector import (
    rank_availability_aware_fallbacks,
    rank_split_candidates,
)
from app.workouts.program_engine.volume_planner import plan_weekly_volume
from tests.workouts.program_engine.golden_fixtures import full_catalog, request


def _module():
    return import_module("app.workouts.program_engine.duration_capacity")


def _normalized(goal: Goal, duration: int):
    return normalize_request(
        request(
            primary_goal=goal,
            session_duration_minutes=duration,
            available_training_days=3,
            training_experience="intermediate",
            training_age_months=30,
        ),
        RULESET,
    )


def test_cardio_reserve_avoids_explicit_priority_day_when_an_alternative_exists() -> None:
    indexes = planned_cardio_day_indexes(
        ("chest_triceps", "back_biceps", "legs"),
        1,
        priority_muscles=frozenset({MuscleGroup.CHEST}),
    )

    assert indexes == frozenset({1})


def test_capacity_preserves_workout_warmup_and_cardio_semantics() -> None:
    module = _module()
    capacity = module.build_session_capacity(
        _normalized(Goal.FAT_LOSS, 45),
        tuple(full_catalog()),
        RULESET,
    )

    assert capacity.requested_workout_minutes == 45
    assert capacity.target_total_minutes == 45 + RULESET.general_warmup_minutes
    # Phase 11.9: resistance budget = full session_duration_minutes (cardio is additive, not deducted)
    assert capacity.resistance_work_budget_minutes == 45
    assert capacity.minimum_resistance_work_minutes == 45 - 10  # tolerance-based min
    assert capacity.maximum_resistance_work_minutes == 45 + 10  # tolerance-based max


def test_candidate_cost_reuses_goal_specific_prescription_and_warmup() -> None:
    module = _module()
    candidate = next(item for item in full_catalog() if item.name == "Dumbbell Press")

    strength = module.estimate_candidate_cost(
        _normalized(Goal.STRENGTH, 30),
        candidate,
        RULESET,
        sets=3,
        is_first_compound=True,
    )
    hypertrophy = module.estimate_candidate_cost(
        _normalized(Goal.HYPERTROPHY, 30),
        candidate,
        RULESET,
        sets=3,
        is_first_compound=True,
    )
    endurance = module.estimate_candidate_cost(
        _normalized(Goal.MUSCULAR_ENDURANCE, 30),
        candidate,
        RULESET,
        sets=3,
        is_first_compound=True,
    )

    assert strength.minutes > hypertrophy.minutes > endurance.minutes
    assert strength.rest_seconds == RULESET.prescription_rules["strength_compound"].rest_seconds
    assert (
        hypertrophy.rest_seconds == RULESET.prescription_rules["hypertrophy_compound"].rest_seconds
    )
    assert endurance.rest_seconds == RULESET.prescription_rules["muscular_endurance"].rest_seconds
    assert strength.warmup_sets == RULESET.strength_compound_warmup_sets
    assert hypertrophy.warmup_sets == RULESET.first_compound_warmup_sets


def test_expected_exercise_and_set_capacity_changes_with_goal_and_time() -> None:
    module = _module()
    catalog = tuple(full_catalog())

    strength_30 = module.build_session_capacity(
        _normalized(Goal.STRENGTH, 30),
        catalog,
        RULESET,
    )
    hypertrophy_30 = module.build_session_capacity(
        _normalized(Goal.HYPERTROPHY, 30),
        catalog,
        RULESET,
    )
    hypertrophy_60 = module.build_session_capacity(
        _normalized(Goal.HYPERTROPHY, 60),
        catalog,
        RULESET,
    )

    assert (
        strength_30.expected_exercise_count_capacity
        <= hypertrophy_30.expected_exercise_count_capacity
    )
    assert strength_30.expected_working_set_capacity <= hypertrophy_30.expected_working_set_capacity
    assert (
        hypertrophy_60.expected_exercise_count_capacity
        > hypertrophy_30.expected_exercise_count_capacity
    )
    assert (
        hypertrophy_60.expected_working_set_capacity > hypertrophy_30.expected_working_set_capacity
    )


def test_assessment_trims_optional_work_but_rejects_impossible_required_work() -> None:
    module = _module()
    capacity = module.build_session_capacity(
        _normalized(Goal.HYPERTROPHY, 30),
        tuple(full_catalog()),
        RULESET,
    )

    tight = module.assess_session_capacity(
        capacity,
        required_work=(module.PlannedWorkCost(minutes=12, working_sets=3),) * 2,
        optional_work=(module.PlannedWorkCost(minutes=12, working_sets=3),) * 2,
    )
    impossible = module.assess_session_capacity(
        capacity,
        required_work=(module.PlannedWorkCost(minutes=21, working_sets=3),) * 2,
        optional_work=(),
    )

    assert tight.status is module.CapacityFeasibility.FEASIBLE_BUT_TIGHT
    assert tight.required_work_cost_minutes == 24
    assert tight.optional_capacity_minutes == 6
    assert tight.optional_work_likely_trimmed == 2
    assert "OPTIONAL_WORK_EXCEEDS_DURATION_CAPACITY" in tight.reason_codes
    assert impossible.status is module.CapacityFeasibility.PROVABLY_INFEASIBLE
    assert "REQUIRED_WORK_EXCEEDS_DURATION_CAPACITY" in impossible.reason_codes


def test_engine_plans_cardio_reserve_before_template_or_split_selection() -> None:
    source = request(
        primary_goal=Goal.FAT_LOSS,
        session_duration_minutes=30,
        available_training_days=3,
        training_experience="intermediate",
        training_age_months=30,
    )

    result = generate_program(source, full_catalog(), RULESET, reference_templates=())

    assert result.program is not None, result.errors
    capacity_trace = next(
        item for item in result.program.decision_trace if item.get("stage") == "duration_capacity"
    )
    assert capacity_trace["requested_workout_minutes"] == 30
    # Phase 11.9: cardio does NOT reduce resistance budget
    assert capacity_trace["resistance_work_budget_minutes"] == 30


def test_normal_split_ranking_uses_capacity_and_is_candidate_order_independent() -> None:
    normalized = _normalized(Goal.STRENGTH, 30)
    catalog = tuple(full_catalog())
    capacity = _module().build_session_capacity(
        normalized,
        catalog,
        RULESET,
    )

    first = rank_split_candidates(
        normalized,
        RULESET,
        exercises=catalog,
        session_capacity=capacity,
    )
    second = rank_split_candidates(
        normalized,
        RULESET,
        exercises=tuple(reversed(catalog)),
        session_capacity=capacity,
    )

    assert first == second
    assert any(reason.startswith("SPLIT_DURATION_CAPACITY_") for reason in first[0].reason_codes)


def test_dynamic_fallback_uses_capacity_and_is_candidate_order_independent() -> None:
    normalized = _normalized(Goal.HYPERTROPHY, 30)
    catalog = tuple(full_catalog())
    capacity = _module().build_session_capacity(
        normalized,
        catalog,
        RULESET,
    )
    weekdays = RULESET.default_weekdays[normalized.resistance_training_days]

    first = rank_availability_aware_fallbacks(
        normalized,
        catalog,
        RULESET,
        weekdays=weekdays,
        session_capacity=capacity,
    )
    second = rank_availability_aware_fallbacks(
        normalized,
        tuple(reversed(catalog)),
        RULESET,
        weekdays=weekdays,
        session_capacity=capacity,
    )

    assert first == second
    assert first
    assert "DYNAMIC_LAYOUT_DURATION_CAPACITY_SCREENED" in first[0].reason_codes


def test_engine_uses_duration_aware_split_ranking_without_changing_day_count() -> None:
    source = request(
        primary_goal=Goal.STRENGTH,
        session_duration_minutes=30,
        available_training_days=4,
        training_experience="intermediate",
        training_age_months=30,
    )

    result = generate_program(source, full_catalog(), RULESET, reference_templates=())

    assert result.program is not None, result.errors
    assert len(result.program.weekly_schedule) == source.available_training_days
    assert any(
        reason.startswith("SPLIT_DURATION_CAPACITY_")
        for reason in result.program.split.reason_codes
    )


def test_weekly_volume_targets_are_allocated_from_real_time_capacity() -> None:
    catalog = tuple(full_catalog())
    short_request = _normalized(Goal.HYPERTROPHY, 30)
    long_request = _normalized(Goal.HYPERTROPHY, 60)
    short_capacity = _module().build_session_capacity(
        short_request,
        catalog,
        RULESET,
    )
    long_capacity = _module().build_session_capacity(
        long_request,
        catalog,
        RULESET,
    )
    short_split = rank_split_candidates(
        short_request,
        RULESET,
        exercises=catalog,
        session_capacity=short_capacity,
    )[0]
    long_split = rank_split_candidates(
        long_request,
        RULESET,
        exercises=catalog,
        session_capacity=long_capacity,
    )[0]

    short_volume = plan_weekly_volume(
        short_request,
        short_split,
        RULESET,
        session_capacity=short_capacity,
    )
    long_volume = plan_weekly_volume(
        long_request,
        long_split,
        RULESET,
        session_capacity=long_capacity,
    )

    assert sum(item.target_sets for item in short_volume.targets) < sum(
        item.target_sets for item in long_volume.targets
    )
    assert "VOLUME_REDUCED_FOR_DURATION_CAPACITY" in short_volume.reason_codes
    assert any(
        "DURATION_CAPACITY_LIMITED_VOLUME" in item.constraint_reason_codes
        for item in short_volume.targets
    )


def test_thirty_minute_strength_program_uses_intentional_reduced_exercise_count() -> None:
    source = request(
        primary_goal=Goal.STRENGTH,
        session_duration_minutes=30,
        available_training_days=3,
        training_experience="intermediate",
        training_age_months=30,
    )

    result = generate_program(source, full_catalog(), RULESET, reference_templates=())

    assert result.program is not None, result.errors
    assert any(
        len(day.exercises) < RULESET.minimum_exercises_per_session
        for day in result.program.weekly_schedule
    )
    trace_reasons = {
        reason
        for entry in result.program.decision_trace
        for reason in entry.get("reason_codes", ())
    }
    assert "DURATION_PLANNED_REDUCED_EXERCISE_COUNT" in trace_reasons
    policy = get_session_duration_policy(source.session_duration_minutes)
    assert all(
        policy.contains_total(day.estimated_duration_minutes, RULESET.general_warmup_minutes)
        for day in result.program.weekly_schedule
    )
    primary = next(
        item
        for day in result.program.weekly_schedule
        for item in day.exercises
        if "STRENGTH_PRIMARY_COMPOUND" in item.reason_codes
    )
    assert (
        primary.rest_seconds >= RULESET.prescription_rules["strength_compound"].minimum_rest_seconds
    )
    assert primary.warmup_sets == RULESET.strength_compound_warmup_sets


def test_duration_trace_reports_planned_budget_and_late_repair_size() -> None:
    source = request(
        primary_goal=Goal.HYPERTROPHY,
        session_duration_minutes=60,
        available_training_days=3,
        training_experience="intermediate",
        training_age_months=30,
    )

    result = generate_program(source, full_catalog(), RULESET, reference_templates=())

    assert result.program is not None, result.errors
    trace = next(
        item for item in result.program.decision_trace if item.get("stage") == "session_duration"
    )
    # Phase 11.9: resistance budget = full session_duration_minutes (cardio is additive)
    assert trace["planned_resistance_work_budget_minutes"] == source.session_duration_minutes

    assert trace["planned_exercise_capacity"] >= RULESET.minimum_exercises_per_session
    assert trace["planned_set_capacity"] > 0
    assert len(trace["estimated_duration_before_late_repair"]) == 3
    assert len(trace["estimated_duration_after_late_repair"]) == 3
    assert trace["repair_classification"] in {"not_needed", "minor"}
