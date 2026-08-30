from dataclasses import replace
from uuid import uuid4

import pytest

from app.exercises.enums import MovementPattern, MuscleGroup
from app.workouts.program_engine.engine import generate_program
from app.workouts.program_engine.exercise_semantics import (
    ExerciseRoleSignature,
    near_equivalent_exercises,
)
from app.workouts.program_engine.normalization import normalize_request
from app.workouts.program_engine.rulesets.resistance_training_v1 import RULESET
from app.workouts.program_engine.schemas import (
    TemplateReference,
    TemplateReferenceDay,
    TemplateReferenceSlot,
)
from app.workouts.program_engine.template_sessions import (
    TemplateConstructionError,
    build_template_sessions,
)
from app.workouts.program_engine.validation import validate_program
from tests.workouts.program_engine.golden_fixtures import full_catalog, request


def test_validator_does_not_allow_template_or_repair_reason_to_bypass_semantics() -> None:
    source = request(available_training_days=1)
    result = generate_program(source, full_catalog(), RULESET)
    assert result.program is not None
    day = result.program.weekly_schedule[0]
    duplicate = replace(
        day.exercises[1],
        exercise_id=uuid4(),
        movement_pattern=day.exercises[2].movement_pattern,
        primary_muscle=day.exercises[2].primary_muscle,
        exercise_type=day.exercises[2].exercise_type,
        secondary_muscles=day.exercises[2].secondary_muscles,
        muscle_focus=day.exercises[2].muscle_focus,
        body_position=day.exercises[2].body_position,
        laterality=day.exercises[2].laterality,
        substitution_group=day.exercises[2].substitution_group,
        reason_codes=("DELIBERATE_REDUNDANCY_FOR_TEMPLATE_STRUCTURE",),
    )
    invalid = replace(
        result.program,
        weekly_schedule=(
            replace(day, exercises=(day.exercises[2], duplicate, *day.exercises[3:])),
        ),
    )

    report = validate_program(invalid, source, RULESET)

    assert "SEMANTIC_NEAR_DUPLICATE_EXERCISE" in report.errors


def test_template_core_duplicate_is_rejected_when_no_safe_complement_exists() -> None:
    source = request(available_training_days=1)
    normalized = normalize_request(source, RULESET)
    first = next(item for item in full_catalog() if item.movement_pattern is MovementPattern.SQUAT)
    second = replace(first, id=uuid4(), substitution_group="squat_dumbbell")
    slot_values = dict(
        target_muscles=(MuscleGroup.QUADRICEPS,),
        movement_pattern=MovementPattern.SQUAT,
        intensity_method="standard",
        adaptation_priority="core",
        superset_group=None,
        superset_exercise_id=None,
        superset_exercise_slug_hint=None,
        sets=3,
        rep_min=8,
        rep_max=12,
        target_rir=2,
        rest_seconds=90,
    )
    template = TemplateReference(
        slug="same-role-squat-template",
        days_per_week=1,
        supported_levels=("beginner",),
        focus_tags=("legs",),
        intensity_methods=("standard",),
        days=(
            TemplateReferenceDay(
                day_number=1,
                title="Legs",
                focus=(MuscleGroup.QUADRICEPS,),
                slots=(
                    TemplateReferenceSlot(
                        exercise_id=first.id, exercise_slug_hint="first", **slot_values
                    ),
                    TemplateReferenceSlot(
                        exercise_id=second.id, exercise_slug_hint="second", **slot_values
                    ),
                ),
            ),
        ),
    )

    with pytest.raises(TemplateConstructionError) as error:
        build_template_sessions(normalized, template, (first, second), RULESET)

    assert "TEMPLATE_CORE_SEMANTIC_DUPLICATE_UNRESOLVABLE" in error.value.reason_codes


def test_actual_batch2_service_path_replays_profiles_2_3_6_and_9(monkeypatch) -> None:
    import scripts.generate_e2e_report_batch2 as batch2

    selected_numbers = {2, 3, 6, 9}
    captured = []
    captured_requests = []
    original_generate = batch2.generate_program

    def capture_generate(*args, **kwargs):
        result = original_generate(*args, **kwargs)
        captured.append(result)
        captured_requests.append(args[0])
        return result

    monkeypatch.setattr(batch2, "generate_program", capture_generate)
    monkeypatch.setattr(
        batch2,
        "TEST_PROFILES_BATCH2",
        [
            dict(
                item,
                priority_muscles=item["priority_muscles"][:1],
                session_duration_minutes=30,
            )
            for item in batch2.TEST_PROFILES_BATCH2
            if item["num"] in selected_numbers
        ],
    )

    results = batch2.run_batch2_profiles()

    assert {profile["num"] for profile, _result in results} == selected_numbers
    assert len(captured) == len(selected_numbers)
    observed_stages = set()
    for (_profile, _response), generation, source in zip(
        results, captured, captured_requests, strict=True
    ):
        assert generation.is_success, generation.errors
        assert generation.program is not None
        assert validate_program(generation.program, source, RULESET).errors == ()
        for day in generation.program.weekly_schedule:
            signatures = [
                ExerciseRoleSignature.from_candidate(item).canonical_role for item in day.exercises
            ]
            strict_families = {
                "horizontal_push_push_up",
                "squat_primary",
                "hip_hinge_primary",
            }
            family_values = [
                signature.canonical_family
                for signature in (
                    ExerciseRoleSignature.from_candidate(item) for item in day.exercises
                )
                if signature.canonical_family in strict_families
            ]
            assert len(family_values) == len(set(family_values))
            assert len(signatures) == len(set(signatures))
            assert all(
                not near_equivalent_exercises(item, previous)
                for index, item in enumerate(day.exercises)
                for previous in day.exercises[:index]
            )
        stages = {entry.get("stage") for entry in generation.program.decision_trace}
        observed_stages.update(stages)
        assert "final_construction" in stages
    assert {
        "template_reference",
        "construction_recovery",
        "substitution_observability",
        "volume_repair",
        "session_duration",
        "final_construction",
    }.issubset(observed_stages)


def test_cross_session_progression_repeat_is_not_same_session_redundancy() -> None:
    source = request(available_training_days=3)
    result = generate_program(source, full_catalog(), RULESET)
    assert result.program is not None
    first_day, second_day = result.program.weekly_schedule[:2]
    repeated_second_day = replace(
        second_day,
        exercises=(first_day.exercises[0], *second_day.exercises[1:]),
    )
    repeated_program = replace(
        result.program,
        weekly_schedule=(first_day, repeated_second_day, *result.program.weekly_schedule[2:]),
    )

    report = validate_program(repeated_program, source, RULESET)

    assert "SEMANTIC_NEAR_DUPLICATE_EXERCISE" not in report.errors
