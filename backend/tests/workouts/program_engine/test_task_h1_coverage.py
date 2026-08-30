from dataclasses import replace

from app.exercises.enums import Equipment, MovementPattern, MuscleGroup
from app.workouts.program_engine.engine import generate_program
from app.workouts.program_engine.rulesets.resistance_training_v1 import RULESET
from app.workouts.program_engine.weekly_coverage import (
    assess_weekly_coverage,
    build_coverage_availability_evidence,
)
from tests.workouts.program_engine.golden_fixtures import full_catalog, request


def _run_batch2_profile_6(monkeypatch):
    import scripts.generate_e2e_report_batch2 as batch2

    captured = []
    original_generate = batch2.generate_program

    def capture_generate(*args, **kwargs):
        result = original_generate(*args, **kwargs)
        captured.append((args[0], result))
        return result

    monkeypatch.setattr(batch2, "generate_program", capture_generate)
    monkeypatch.setattr(
        batch2,
        "TEST_PROFILES_BATCH2",
        [
            dict(profile, session_duration_minutes=30)
            for profile in batch2.TEST_PROFILES_BATCH2
            if profile["num"] == 6
        ],
    )
    results = batch2.run_batch2_profiles()

    assert len(results) == 1
    assert len(captured) == 1
    return results[0], captured[0]


def test_batch2_profile_6_uses_legacy_pull_up_bar_default(monkeypatch) -> None:
    (profile, response), (source, generation) = _run_batch2_profile_6(monkeypatch)

    assert profile["num"] == 6
    assert response["success"] is True
    assert generation.program is not None
    assert Equipment.PULL_UP_BAR in source.available_equipment


def test_full_body_coverage_reports_satisfied_for_actual_exercises() -> None:
    result = generate_program(
        request(available_training_days=1, session_duration_minutes=60),
        full_catalog(),
        RULESET,
    )

    assert result.program is not None, result.errors
    coverage = result.program.aggregate_metrics["weekly_coverage"]
    assert coverage["status"] == "satisfied"
    assert coverage["claimed_full_body"] is True
    assert coverage["claimed_balanced"] is True
    assert coverage["fully_balanced"] is True
    assert coverage["missing_patterns"] == ()
    assert coverage["missing_major_muscles"] == ()


def test_full_body_coverage_distinguishes_missing_available_work() -> None:
    result = generate_program(
        request(available_training_days=1, session_duration_minutes=60),
        full_catalog(),
        RULESET,
    )

    assert result.program is not None, result.errors
    days = tuple(
        replace(
            day,
            exercises=tuple(
                item
                for item in day.exercises
                if item.primary_muscle is not MuscleGroup.BACK
                and item.movement_pattern
                not in {MovementPattern.HORIZONTAL_PULL, MovementPattern.VERTICAL_PULL}
            ),
        )
        for day in result.program.weekly_schedule
    )
    coverage = assess_weekly_coverage(days, {}, ruleset=RULESET).metrics

    assert coverage["status"] == "unsatisfied"
    assert coverage["claimed_full_body"] is True
    assert coverage["claimed_balanced"] is False
    assert coverage["fully_balanced"] is False
    assert coverage["missing_patterns"] == ("pull",)
    assert coverage["unavailable_patterns"] == ()
    assert coverage["missing_major_muscles"] == ("back",)
    assert coverage["unavailable_major_muscles"] == ()
    assert "FULL_BODY_PATTERN_MISSING:pull" in coverage["reason_codes"]
    assert "FULL_BODY_COVERAGE_MISSING:back" in coverage["reason_codes"]


def test_full_body_coverage_does_not_expand_unavailable_quads_or_hamstrings_to_glutes() -> None:
    result = generate_program(
        request(available_training_days=1, session_duration_minutes=60),
        full_catalog(),
        RULESET,
    )

    assert result.program is not None, result.errors
    days = tuple(
        replace(
            day,
            exercises=tuple(
                item
                for item in day.exercises
                if item.movement_pattern
                in {MovementPattern.HORIZONTAL_PUSH, MovementPattern.HORIZONTAL_PULL}
            ),
        )
        for day in result.program.weekly_schedule
    )
    coverage = assess_weekly_coverage(
        days,
        {
            "unavailable_muscle_coverage": ("quadriceps", "hamstrings"),
            "relaxed_required_pattern_groups": (
                ("squat", "lunge", "knee_extension"),
                ("hip_hinge", "hip_extension"),
            ),
        },
        ruleset=RULESET,
    ).metrics

    assert coverage["status"] == "unsatisfied"
    assert coverage["unavailable_patterns"] == ()
    assert coverage["unavailable_major_muscles"] == ()
    assert "glutes" in coverage["missing_major_muscles"]
    assert "FULL_BODY_COVERAGE_MISSING:glutes" in coverage["reason_codes"]


def test_shoulder_abduction_candidate_prevents_false_unavailable_shoulders() -> None:
    result = generate_program(
        request(available_training_days=1, session_duration_minutes=60),
        full_catalog(),
        RULESET,
    )

    assert result.program is not None, result.errors
    lateral_raise = next(
        candidate
        for candidate in full_catalog()
        if candidate.movement_pattern is MovementPattern.SHOULDER_ABDUCTION
    )
    days = tuple(
        replace(
            day,
            exercises=tuple(
                item
                for item in day.exercises
                if item.primary_muscle is not MuscleGroup.SHOULDERS
                and MuscleGroup.SHOULDERS not in item.secondary_muscles
            ),
        )
        for day in result.program.weekly_schedule
    )
    coverage = assess_weekly_coverage(
        days,
        {},
        ruleset=RULESET,
        availability_evidence=build_coverage_availability_evidence((lateral_raise,), ()),
    ).metrics

    assert coverage["status"] == "unsatisfied"
    assert coverage["missing_major_muscles"] == ("shoulders",)
    assert coverage["unavailable_major_muscles"] == ()
    assert (
        coverage["availability_evidence"]["muscles"]["shoulders"]["eligible_candidate_count"] == 1
    )
