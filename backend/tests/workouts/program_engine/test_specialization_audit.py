from app.exercises.enums import MuscleGroup
from app.training_templates.tags import TemplateFocusTag
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
