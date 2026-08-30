from types import SimpleNamespace

from app.exercises.enums import MuscleGroup
from app.training_templates.tags import TemplateFocusTag
from app.workouts.program_engine.duration_policy import (
    get_session_duration_policy,
    get_session_exercise_count_policy,
)
from app.workouts.program_engine.rulesets.resistance_training_v1 import RULESET
from app.workouts.program_engine.schemas import WorkoutDay
from app.workouts.program_engine.validation import narrow_priority_count_exception
from scripts.audit_template_specialization import priority_muscles_for_tags


def test_specialization_priority_mapping_uses_semantic_tags() -> None:
    assert priority_muscles_for_tags(
        (TemplateFocusTag.SPECIALIZATION, TemplateFocusTag.ARMS_PRIORITY)
    ) == frozenset({MuscleGroup.BICEPS, MuscleGroup.TRICEPS})
    assert priority_muscles_for_tags(
        (TemplateFocusTag.SPECIALIZATION, TemplateFocusTag.CHEST_PRIORITY)
    ) == frozenset({MuscleGroup.CHEST})


def test_non_specialization_tags_do_not_create_a_priority_profile() -> None:
    assert priority_muscles_for_tags((TemplateFocusTag.UPPER_LOWER,)) == frozenset()


def test_satisfied_narrow_priority_day_can_use_four_meaningful_exercises() -> None:
    day = WorkoutDay(
        day_index=5,
        weekday=6,
        title="Arms",
        focus="template_reference_5",
        estimated_duration_minutes=40,
        exercises=(),
        template_target_muscles=(MuscleGroup.BICEPS, MuscleGroup.TRICEPS),
        template_structure_focus="arms",
    )
    priority_metrics = {
        "biceps": {"status": "satisfied"},
        "triceps": {"status": "satisfied"},
    }

    assert narrow_priority_count_exception(
        day,
        exercise_count=4,
        main_minutes=35,
        request=SimpleNamespace(
            priority_muscles=frozenset({MuscleGroup.BICEPS, MuscleGroup.TRICEPS})
        ),
        priority_metrics=priority_metrics,
        count_policy=get_session_exercise_count_policy(45, RULESET),
        duration_policy=get_session_duration_policy(45),
    )
