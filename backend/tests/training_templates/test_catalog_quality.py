from collections import Counter

from app.profile.enums import ExperienceLevel
from app.training_templates.models import TrainingTemplateMethod
from app.training_templates.seed_data import TRAINING_PROGRAM_TEMPLATE_SEEDS
from app.training_templates.tags import TemplateFocusTag


def test_all_seventeen_templates_have_role_aware_prescription_diversity() -> None:
    signatures = Counter(
        (slot.sets, slot.rep_min, slot.rep_max, slot.target_rir, slot.rest_seconds)
        for template in TRAINING_PROGRAM_TEMPLATE_SEEDS
        for day in template.days
        for slot in day.slots
    )

    assert len(TRAINING_PROGRAM_TEMPLATE_SEEDS) == 17
    assert len(signatures) >= 10
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


def test_advanced_bodybuilding_templates_have_real_safe_weekly_methods() -> None:
    advanced = {
        template.slug: template
        for template in TRAINING_PROGRAM_TEMPLATE_SEEDS
        if template.slug
        in {
            "t16-6-day-advanced-body-part",
            "t17-6-day-balanced-specialization",
        }
    }

    assert set(advanced) == {
        "t16-6-day-advanced-body-part",
        "t17-6-day-balanced-specialization",
    }
    for template in advanced.values():
        slots = [slot for day in template.days for slot in day.slots]
        groups: dict[str, list[object]] = {}
        for day in template.days:
            for index, slot in enumerate(day.slots):
                if slot.superset_group is not None:
                    groups.setdefault(slot.superset_group, []).append((day, index, slot))
        assert TrainingTemplateMethod.SUPERSET in template.intensity_methods
        assert TrainingTemplateMethod.DROP_SET in template.intensity_methods
        assert any(slot.intensity_method is TrainingTemplateMethod.DROP_SET for slot in slots)
        assert groups
        assert all(
            len(items) == 2
            and items[0][0] is items[1][0]
            and items[1][1] == items[0][1] + 1
            and all(
                item[2].adaptation_priority.value in {"accessory", "optional"}
                for item in items
            )
            for items in groups.values()
        )


def test_t03_declares_its_structural_upper_priority() -> None:
    template = next(
        item
        for item in TRAINING_PROGRAM_TEMPLATE_SEEDS
        if item.slug == "t03-3-day-upper-lower-upper"
    )

    assert TemplateFocusTag.UPPER_PRIORITY in template.focus_tags
