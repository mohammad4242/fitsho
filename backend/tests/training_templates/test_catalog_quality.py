from collections import Counter

from app.profile.enums import ExperienceLevel
from app.training_templates.models import TrainingTemplateMethod
from app.training_templates.seed_data import TRAINING_PROGRAM_TEMPLATE_SEEDS
from app.training_templates.tags import TemplateFocusTag


def test_all_25_programs_have_role_aware_prescription_diversity() -> None:
    signatures = Counter(
        (slot.sets, slot.rep_min, slot.rep_max, slot.target_rir, slot.rest_seconds)
        for template in TRAINING_PROGRAM_TEMPLATE_SEEDS
        for day in template.days
        for slot in day.slots
    )

    assert len(TRAINING_PROGRAM_TEMPLATE_SEEDS) == 25
    assert len(signatures) >= 7
    assert (3, 8, 12, 2, 90) not in dict(signatures.most_common(1))
    assert all(
        len(
            {
                (slot.sets, slot.rep_min, slot.rep_max, slot.target_rir, slot.rest_seconds)
                for day in template.days
                for slot in day.slots
            }
        )
        >= 3
        for template in TRAINING_PROGRAM_TEMPLATE_SEEDS
    )


def test_first_month_and_beginner_templates_use_standard_methods_only() -> None:
    novice_levels = {ExperienceLevel.FIRST_MONTH, ExperienceLevel.BEGINNER}

    for template in TRAINING_PROGRAM_TEMPLATE_SEEDS:
        if novice_levels.intersection(template.supported_levels):
            assert template.intensity_methods == (TrainingTemplateMethod.STANDARD,)


def test_advanced_programs_use_the_approved_advanced_prescription() -> None:
    advanced = [
        template
        for template in TRAINING_PROGRAM_TEMPLATE_SEEDS
        if template.supported_levels == (ExperienceLevel.ADVANCED,)
    ]

    assert len(advanced) == 7
    assert all(
        template.intensity_methods == (TrainingTemplateMethod.STANDARD,) for template in advanced
    )
    assert all(
        any((slot.sets, slot.rep_min, slot.rep_max, slot.target_rir) == (4, 5, 8, 1)
            for day in template.days for slot in day.slots)
        for template in advanced
    )


def test_t03_declares_its_structural_upper_priority() -> None:
    template = next(
        item
        for item in TRAINING_PROGRAM_TEMPLATE_SEEDS
        if item.slug == "p08-3-day-upper-lower-upper-beginner"
    )

    assert TemplateFocusTag.UPPER_PRIORITY in template.focus_tags
