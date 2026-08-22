import pytest

from app.exercises.enums import MuscleGroup
from app.training_templates.seed_data import TRAINING_PROGRAM_TEMPLATE_SEEDS
from app.training_templates.tags import (
    CANONICAL_TEMPLATE_FOCUS_TAGS,
    TEMPLATE_FOCUS_TAG_DEFINITIONS,
    TemplateFocusTag,
    normalize_focus_tags,
    validate_focus_tags,
)


def test_focus_tags_have_one_canonical_vocabulary() -> None:
    assert set(TEMPLATE_FOCUS_TAG_DEFINITIONS) == {
        tag.value for tag in TemplateFocusTag
    }
    assert {
        "full_body",
        "upper_lower",
        "push_pull_legs",
        "body_part_rotation",
        "balanced",
        "upper_priority",
        "lower_priority",
        "chest_priority",
        "back_priority",
        "shoulders_priority",
        "arms_priority",
        "glute_priority",
        "quad_priority",
        "hamstrings_priority",
        "strength_bias",
        "compound_focus",
        "specialization",
        "time_efficient",
    }.issubset(CANONICAL_TEMPLATE_FOCUS_TAGS)
    assert TemplateFocusTag.BALANCED.value == "balanced"


def test_unknown_and_duplicate_focus_tags_are_rejected() -> None:
    with pytest.raises(ValueError, match="Unknown template focus tag"):
        validate_focus_tags(("balanced", "classic"))

    with pytest.raises(ValueError, match="Focus tags must be unique"):
        validate_focus_tags(("balanced", "balanced"))


def test_normalization_deduplicates_canonical_tags() -> None:
    assert normalize_focus_tags(("balanced", "full_body", "balanced")) == (
        "balanced",
        "full_body",
    )


def test_seed_library_contains_only_unique_canonical_tags() -> None:
    assert all(
        len(template.focus_tags) == len(set(template.focus_tags))
        and set(template.focus_tags).issubset(CANONICAL_TEMPLATE_FOCUS_TAGS)
        for template in TRAINING_PROGRAM_TEMPLATE_SEEDS
    )
    assert all(
        not {
            "female",
            "male",
            "women_program",
            "men_program",
            "fat_loss",
            "build_muscle",
            "general_fitness",
        }.intersection(template.focus_tags)
        for template in TRAINING_PROGRAM_TEMPLATE_SEEDS
    )


def test_priority_tags_have_structural_exposure_and_balanced_is_not_priority() -> None:
    priority_muscles = {
        "chest_priority": (MuscleGroup.CHEST,),
        "back_priority": (MuscleGroup.BACK,),
        "shoulders_priority": (MuscleGroup.SHOULDERS,),
        "arms_priority": (MuscleGroup.BICEPS, MuscleGroup.TRICEPS),
        "quad_priority": (MuscleGroup.QUADRICEPS,),
        "hamstrings_priority": (MuscleGroup.HAMSTRINGS,),
        "glute_priority": (MuscleGroup.GLUTES,),
    }
    for template in TRAINING_PROGRAM_TEMPLATE_SEEDS:
        priority_tags = {
            tag for tag in template.focus_tags if tag.endswith("_priority")
        }
        if "balanced" in template.focus_tags:
            assert not priority_tags, template.slug
        for tag, muscles in priority_muscles.items():
            if tag not in template.focus_tags:
                continue
            direct_slots = sum(
                muscle in slot.target_muscles
                for day in template.days
                for slot in day.slots
                for muscle in muscles
            )
            assert direct_slots >= 3, (template.slug, tag)


def test_upper_and_lower_priority_tags_match_the_weekly_layout() -> None:
    upper = next(
        template
        for template in TRAINING_PROGRAM_TEMPLATE_SEEDS
        if "upper_priority" in template.focus_tags
    )
    lower = next(
        template
        for template in TRAINING_PROGRAM_TEMPLATE_SEEDS
        if "lower_priority" in template.focus_tags
    )
    upper_muscles = {
        MuscleGroup.CHEST,
        MuscleGroup.BACK,
        MuscleGroup.SHOULDERS,
        MuscleGroup.BICEPS,
        MuscleGroup.TRICEPS,
    }
    lower_muscles = {
        MuscleGroup.QUADRICEPS,
        MuscleGroup.HAMSTRINGS,
        MuscleGroup.GLUTES,
        MuscleGroup.CALVES,
    }
    upper_days = sum(bool(set(day.direct_target_muscles) & upper_muscles) for day in upper.days)
    lower_days = sum(bool(set(day.direct_target_muscles) & lower_muscles) for day in lower.days)
    assert upper_days >= 3
    assert lower_days >= 2


def test_seed_library_keeps_structural_emphasis_tags_without_user_mutation() -> None:
    upper_priority = next(
        template
        for template in TRAINING_PROGRAM_TEMPLATE_SEEDS
        if template.slug == "five-day-ppl-upper-lower"
    )
    assert "upper_priority" in upper_priority.focus_tags
    assert "push_pull_legs" in upper_priority.focus_tags
    assert "upper_lower" in upper_priority.focus_tags

    lower_priority = next(
        template
        for template in TRAINING_PROGRAM_TEMPLATE_SEEDS
        if template.slug == "five-day-advanced-leg-specialization"
    )
    assert "lower_priority" in lower_priority.focus_tags
    assert {"glute_priority", "hamstrings_priority"}.issubset(
        lower_priority.focus_tags
    )
