from collections import Counter

from app.profile.enums import ExperienceLevel
from app.training_templates.models import TrainingTemplateMethod
from app.training_templates.seed_data import (
    APPROVED_STRUCTURE_SEEDS,
    TRAINING_PROGRAM_TEMPLATE_SEEDS,
)
from app.training_templates.tags import TemplateFocusTag


def test_all_49_programs_have_role_aware_prescription_diversity() -> None:
    signatures = Counter(
        (slot.sets, slot.rep_min, slot.rep_max, slot.target_rir, slot.rest_seconds)
        for template in TRAINING_PROGRAM_TEMPLATE_SEEDS
        for day in template.days
        for slot in day.slots
    )

    assert len(TRAINING_PROGRAM_TEMPLATE_SEEDS) == 49
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
        if template.supported_levels == (ExperienceLevel.ADVANCED,) and template.days_per_week <= 4
    ]

    assert len(advanced) == 7
    assert all(
        template.intensity_methods == (TrainingTemplateMethod.STANDARD,) for template in advanced
    )
    assert all(
        any(
            (slot.sets, slot.rep_min, slot.rep_max, slot.target_rir) == (4, 5, 8, 1)
            for day in template.days
            for slot in day.slots
        )
        for template in advanced
    )


def test_t03_is_a_neutral_upper_lower_structure() -> None:
    template = next(
        item
        for item in TRAINING_PROGRAM_TEMPLATE_SEEDS
        if item.slug == "p08-3-day-upper-lower-upper-beginner"
    )

    assert TemplateFocusTag.UPPER_LOWER in template.focus_tags
    assert "upper_priority" not in template.focus_tags


def test_active_catalog_has_no_user_visible_generic_upper_priority_wording() -> None:
    template_text = " ".join(
        text
        for template in TRAINING_PROGRAM_TEMPLATE_SEEDS
        if template.is_active
        for text in (
            template.name_en,
            template.name_fa,
            template.description_en,
            template.description_fa,
            *(day.title_en for day in template.days),
            *(day.title_fa for day in template.days),
            *(
                text
                for rationale in template.programming_rationale
                for text in (
                    rationale.title_en,
                    rationale.title_fa,
                    rationale.detail_en,
                    rationale.detail_fa,
                )
            ),
        )
    )
    structure_text = " ".join(
        text
        for structure in APPROVED_STRUCTURE_SEEDS
        for text in (
            structure.name_en,
            structure.name_fa,
            structure.description_en,
            structure.description_fa,
            *(label_en for _, label_en, _ in structure.days),
            *(label_fa for _, _, label_fa in structure.days),
        )
    )
    visible_text = f"{template_text} {structure_text}".lower()

    assert "upper priority" not in visible_text
    assert "upper-priority" not in visible_text
    assert "اولویت بالاتنه" not in visible_text
