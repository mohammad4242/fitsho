from dataclasses import replace
from uuid import uuid4

import pytest

from app.exercises.enums import Equipment, MovementPattern, MuscleGroup
from app.workouts.program_engine.engine import generate_program
from app.workouts.program_engine.enums import Goal, TrainingExperience
from app.workouts.program_engine.exercise_semantics import near_equivalent_exercises
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


@pytest.mark.parametrize(
    "days", [4, 6, 3, 4], ids=["profile-2", "profile-3", "profile-6", "profile-9"]
)
def test_batch2_profiles_have_no_same_session_semantic_redundancy(days: int) -> None:
    source = request(
        available_training_days=days,
        available_equipment=list(Equipment),
        training_age_months=72 if days == 6 else 30,
        training_experience=(
            TrainingExperience.ADVANCED if days == 6 else TrainingExperience.INTERMEDIATE
        ),
        primary_goal=Goal.STRENGTH if days == 6 else Goal.HYPERTROPHY,
    )
    result = generate_program(source, full_catalog(), RULESET)

    assert result.is_success, result.errors
    assert result.program is not None
    assert validate_program(result.program, source, RULESET).errors == ()
    for day in result.program.weekly_schedule:
        for index, exercise in enumerate(day.exercises):
            assert not any(
                near_equivalent_exercises(exercise, previous)
                for previous in day.exercises[:index]
            )


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
    first = next(
        item for item in full_catalog() if item.movement_pattern is MovementPattern.SQUAT
    )
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
