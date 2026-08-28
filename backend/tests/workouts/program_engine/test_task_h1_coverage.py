from dataclasses import replace

from app.exercises.enums import MovementPattern, MuscleGroup
from app.workouts.program_engine.engine import generate_program
from app.workouts.program_engine.equipment import effective_required_equipment
from app.workouts.program_engine.rulesets.resistance_training_v1 import RULESET
from app.workouts.program_engine.safety import effective_caution_tags
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
        [profile for profile in batch2.TEST_PROFILES_BATCH2 if profile["num"] == 6],
    )
    results = batch2.run_batch2_profiles()

    assert len(results) == 1
    assert len(captured) == 1
    return results[0], captured[0]


def test_batch2_profile_6_reports_unavailable_pull_without_balanced_claim(monkeypatch) -> None:
    (profile, response), (source, generation) = _run_batch2_profile_6(monkeypatch)

    assert response["success"] is True
    plan = response["plan"]
    program = generation.program
    assert plan is not None
    assert program is not None, generation.errors
    assert profile["num"] == 6
    assert len(program.weekly_schedule) == 2

    actual_patterns = {
        item.movement_pattern for day in program.weekly_schedule for item in day.exercises
    }
    assert {
        MovementPattern.HORIZONTAL_PUSH,
        MovementPattern.SQUAT,
        MovementPattern.HIP_EXTENSION,
    }.issubset(actual_patterns)
    assert not actual_patterns.intersection(
        {MovementPattern.HORIZONTAL_PULL, MovementPattern.VERTICAL_PULL}
    )
    actual_muscles = {
        muscle
        for day in program.weekly_schedule
        for item in day.exercises
        for muscle in (item.primary_muscle, *item.secondary_muscles)
        if muscle is not None
    }
    assert {
        MuscleGroup.CHEST,
        MuscleGroup.SHOULDERS,
        MuscleGroup.QUADRICEPS,
        MuscleGroup.HAMSTRINGS,
        MuscleGroup.GLUTES,
    }.issubset(actual_muscles)
    assert MuscleGroup.BACK not in actual_muscles

    coverage = program.aggregate_metrics["weekly_coverage"]
    assert coverage["status"] == "constrained"
    assert coverage["covered_patterns"] == ("push", "knee", "hinge")
    assert coverage["missing_patterns"] == ("pull",)
    assert coverage["missing_major_muscles"] == ("back",)
    assert coverage["unavailable_patterns"] == ("pull",)
    assert coverage["unavailable_major_muscles"] == ("back",)
    assert "FULL_BODY_PATTERN_UNAVAILABLE:pull" in coverage["reason_codes"]
    assert "FULL_BODY_COVERAGE_UNAVAILABLE:back" in coverage["reason_codes"]
    pull_evidence = coverage["availability_evidence"]["patterns"]["pull"]
    back_evidence = coverage["availability_evidence"]["muscles"]["back"]
    assert pull_evidence["candidate_count"] == pull_evidence["rejected_candidate_count"]
    assert pull_evidence["eligible_candidate_count"] == 0
    assert "EXERCISE_REJECTED_MISSING_EQUIPMENT" in pull_evidence["rejection_reason_codes"]
    assert back_evidence["candidate_count"] == back_evidence["rejected_candidate_count"]
    assert back_evidence["eligible_candidate_count"] == 0
    assert "EXERCISE_REJECTED_MISSING_EQUIPMENT" in back_evidence["rejection_reason_codes"]
    assert pull_evidence["unavailable"] is True
    assert back_evidence["unavailable"] is True
    assert coverage["fully_balanced"] is False
    assert coverage["claimed_balanced"] is False
    assert program.aggregate_metrics["coach_quality"]["coverage_fit"] == "constrained"
    response_coverage = plan.aggregate_metrics["weekly_coverage"]
    assert response_coverage["status"] == "constrained"
    assert response_coverage["missing_patterns"] == ["pull"]
    assert response_coverage["unavailable_major_muscles"] == ["back"]
    assert not any(
        item.primary_muscle is MuscleGroup.BACK
        for day in program.weekly_schedule
        for item in day.exercises
    )
    assert all(
        item.is_active
        and item.is_programmable
        and not item.needs_review
        and item.counts_toward_volume
        and effective_required_equipment(item.equipment, item.movement_pattern).issubset(
            source.available_equipment
        )
        and not effective_caution_tags(item).intersection(source.blocked_caution_tags)
        for day in program.weekly_schedule
        for item in day.exercises
    )


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
