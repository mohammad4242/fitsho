from types import SimpleNamespace

import pytest

from app.exercises.enums import MuscleGroup
from app.training_templates import tags as template_tags
from app.training_templates.seed_data import TRAINING_PROGRAM_TEMPLATE_SEEDS
from app.training_templates.tags import (
    CANONICAL_TEMPLATE_FOCUS_TAGS,
    MINIMUM_DIRECT_SLOTS_BY_PRIORITY_TAG,
    MUSCLE_PRIORITY_TAGS,
    MUSCLES_BY_PRIORITY_TAG,
    TEMPLATE_FOCUS_TAG_DEFINITIONS,
    TemplateFocusTag,
    validate_focus_tags,
)
from app.workouts.program_engine import body_analysis


def test_focus_tags_have_one_canonical_vocabulary() -> None:
    assert set(TEMPLATE_FOCUS_TAG_DEFINITIONS) == {tag.value for tag in TemplateFocusTag}
    assert CANONICAL_TEMPLATE_FOCUS_TAGS == {
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
    }
    assert TemplateFocusTag.BALANCED.value == "balanced"


def test_every_focus_tag_has_one_semantic_category_and_documented_contract() -> None:
    category_type = getattr(template_tags, "TemplateTagCategory", None)
    assert category_type is not None
    expected_categories = {
        "full_body": "primary_structure",
        "upper_lower": "primary_structure",
        "push_pull_legs": "primary_structure",
        "body_part_rotation": "primary_structure",
        "balanced": "regional_balance",
        "upper_priority": "regional_balance",
        "lower_priority": "regional_balance",
        "chest_priority": "muscle_priority",
        "back_priority": "muscle_priority",
        "shoulders_priority": "muscle_priority",
        "arms_priority": "muscle_priority",
        "glute_priority": "muscle_priority",
        "quad_priority": "muscle_priority",
        "hamstrings_priority": "muscle_priority",
        "strength_bias": "structural_character",
        "compound_focus": "structural_character",
        "specialization": "structural_character",
    }

    assert {
        tag.value: definition.category.value
        for tag, definition in TEMPLATE_FOCUS_TAG_DEFINITIONS.items()
    } == expected_categories
    assert all(definition.meaning.strip() for definition in TEMPLATE_FOCUS_TAG_DEFINITIONS.values())


def test_unknown_and_duplicate_focus_tags_are_rejected() -> None:
    with pytest.raises(ValueError, match="Unknown template focus tag"):
        validate_focus_tags(("balanced", "classic"))

    with pytest.raises(ValueError, match="Focus tags must be unique"):
        validate_focus_tags(("balanced", "balanced"))


@pytest.mark.parametrize(
    ("tags", "message"),
    (
        ((TemplateFocusTag.BALANCED,), "primary structure"),
        (
            (TemplateFocusTag.FULL_BODY, TemplateFocusTag.UPPER_LOWER),
            "Unsupported primary structure combination",
        ),
        (
            (
                TemplateFocusTag.FULL_BODY,
                TemplateFocusTag.BALANCED,
                TemplateFocusTag.CHEST_PRIORITY,
            ),
            "Balanced templates cannot declare priority tags",
        ),
        (
            (
                TemplateFocusTag.BODY_PART_ROTATION,
                TemplateFocusTag.UPPER_PRIORITY,
                TemplateFocusTag.LOWER_PRIORITY,
            ),
            "Upper and lower priority tags conflict",
        ),
        (
            (TemplateFocusTag.BODY_PART_ROTATION, TemplateFocusTag.SPECIALIZATION),
            "Specialization requires a priority tag",
        ),
    ),
)
def test_focus_tag_category_invariants_are_rejected(
    tags: tuple[TemplateFocusTag, ...],
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        validate_focus_tags(tags)


def test_priority_muscles_map_to_one_explicit_canonical_vocabulary() -> None:
    mapper = getattr(template_tags, "priority_tags_for_muscles", None)
    membership = getattr(template_tags, "has_template_tag", None)
    assert mapper is not None
    assert membership is not None

    assert mapper(
        (
            MuscleGroup.CHEST,
            MuscleGroup.BACK,
            MuscleGroup.SHOULDERS,
            MuscleGroup.BICEPS,
            MuscleGroup.TRICEPS,
            MuscleGroup.FOREARMS,
            MuscleGroup.GLUTES,
            MuscleGroup.QUADRICEPS,
            MuscleGroup.HAMSTRINGS,
        )
    ) == frozenset(
        {
            TemplateFocusTag.CHEST_PRIORITY,
            TemplateFocusTag.BACK_PRIORITY,
            TemplateFocusTag.SHOULDERS_PRIORITY,
            TemplateFocusTag.ARMS_PRIORITY,
            TemplateFocusTag.GLUTE_PRIORITY,
            TemplateFocusTag.QUAD_PRIORITY,
            TemplateFocusTag.HAMSTRINGS_PRIORITY,
        }
    )
    assert mapper((MuscleGroup.CALVES, MuscleGroup.ABS, MuscleGroup.TRAPS)) == frozenset()
    assert membership(
        (TemplateFocusTag.FULL_BODY, TemplateFocusTag.CHEST_PRIORITY),
        TemplateFocusTag.CHEST_PRIORITY,
    )


def test_body_analysis_does_not_keep_a_competing_template_tag_mapping() -> None:
    assert not hasattr(body_analysis, "TEMPLATE_TAGS_BY_MUSCLE")


def test_seed_library_contains_only_unique_canonical_tags() -> None:
    assert all(
        len(template.focus_tags) == len(set(template.focus_tags))
        and set(template.focus_tags).issubset(CANONICAL_TEMPLATE_FOCUS_TAGS)
        for template in TRAINING_PROGRAM_TEMPLATE_SEEDS
    )


def test_seed_tags_are_declared_canonically_without_alias_normalizers() -> None:
    assert all(
        isinstance(tag, TemplateFocusTag)
        for template in TRAINING_PROGRAM_TEMPLATE_SEEDS
        for tag in template.focus_tags
    )
    assert not hasattr(template_tags, "LEGACY_FOCUS_TAG_REPLACEMENTS")
    assert not hasattr(template_tags, "STRUCTURAL_FOCUS_TAG_ADDITIONS_BY_TEMPLATE")
    assert not hasattr(template_tags, "normalize_seed_focus_tags")
    assert not hasattr(template_tags, "normalize_focus_tags")


def test_every_active_seed_passes_central_structural_tag_validation() -> None:
    validator = getattr(template_tags, "validate_template_focus_tags", None)
    assert validator is not None

    for template in TRAINING_PROGRAM_TEMPLATE_SEEDS:
        assert validator(
            template.focus_tags,
            intensity_methods=template.intensity_methods,
            days=template.days,
        ) == tuple(TemplateFocusTag(tag) for tag in template.focus_tags)


def test_structural_validator_rejects_a_false_primary_structure_claim() -> None:
    classic = next(
        template
        for template in TRAINING_PROGRAM_TEMPLATE_SEEDS
        if template.slug == "p24-4-day-push-pull-quads-posterior-intermediate"
    )

    with pytest.raises(ValueError, match="Pure full-body"):
        template_tags.validate_template_focus_tags(
            (TemplateFocusTag.FULL_BODY, TemplateFocusTag.BALANCED),
            intensity_methods=classic.intensity_methods,
            days=classic.days,
        )


def test_structural_validator_rejects_an_incidental_muscle_priority_claim() -> None:
    classic = next(
        template
        for template in TRAINING_PROGRAM_TEMPLATE_SEEDS
        if template.slug == "p14-4-day-upper-lower-upper-lower-first-month"
    )

    with pytest.raises(ValueError, match="glute_priority lacks structural evidence"):
        template_tags.validate_template_focus_tags(
            (TemplateFocusTag.UPPER_LOWER, TemplateFocusTag.GLUTE_PRIORITY),
            intensity_methods=classic.intensity_methods,
            days=classic.days,
        )


def test_structural_validator_rejects_a_materially_unbalanced_week() -> None:
    chest_slot = SimpleNamespace(
        target_muscles=(MuscleGroup.CHEST,),
        movement_pattern="horizontal_push",
        adaptation_priority="core",
    )
    days = tuple(
        SimpleNamespace(
            direct_target_muscles=(MuscleGroup.CHEST, MuscleGroup.QUADRICEPS),
            slots=(chest_slot,) * 5,
        )
        for _ in range(3)
    )

    with pytest.raises(ValueError, match="balanced lacks structural evidence"):
        template_tags.validate_template_focus_tags(
            (TemplateFocusTag.FULL_BODY, TemplateFocusTag.BALANCED),
            intensity_methods=("standard",),
            days=days,
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


@pytest.mark.parametrize("day_count", (4, 5, 6))
def test_structural_validator_rejects_pure_high_frequency_full_body(
    day_count: int,
) -> None:
    mixed_day = SimpleNamespace(
        direct_target_muscles=(MuscleGroup.CHEST, MuscleGroup.QUADRICEPS),
        slots=(),
    )

    with pytest.raises(ValueError):
        template_tags.validate_template_focus_tags(
            (TemplateFocusTag.FULL_BODY,),
            days=(mixed_day,) * day_count,
        )


@pytest.mark.parametrize("day_count", (4, 5, 6))
def test_catalog_topology_rejects_full_body_with_non_structural_tags(
    day_count: int,
) -> None:
    with pytest.raises(ValueError, match="Pure full-body"):
        template_tags.validate_catalog_topology(
            day_count,
            (TemplateFocusTag.FULL_BODY, TemplateFocusTag.BALANCED),
        )


@pytest.mark.parametrize("day_count", (2, 3))
def test_structural_validator_allows_lower_frequency_full_body(day_count: int) -> None:
    mixed_day = SimpleNamespace(
        direct_target_muscles=(MuscleGroup.CHEST, MuscleGroup.QUADRICEPS),
        slots=(),
    )

    template_tags.validate_template_focus_tags(
        (TemplateFocusTag.FULL_BODY,),
        days=(mixed_day,) * day_count,
    )


def test_structural_validator_allows_valid_four_day_split() -> None:
    upper = SimpleNamespace(
        direct_target_muscles=(MuscleGroup.CHEST, MuscleGroup.BACK),
        slots=(),
    )
    lower = SimpleNamespace(
        direct_target_muscles=(MuscleGroup.QUADRICEPS, MuscleGroup.HAMSTRINGS),
        slots=(),
    )

    template_tags.validate_template_focus_tags(
        (TemplateFocusTag.UPPER_LOWER,),
        days=(upper, lower, upper, lower),
    )


def test_priority_tags_have_structural_exposure_and_balanced_is_not_priority() -> None:
    for template in TRAINING_PROGRAM_TEMPLATE_SEEDS:
        priority_tags = set(template.focus_tags) & MUSCLE_PRIORITY_TAGS
        if TemplateFocusTag.BALANCED in template.focus_tags:
            assert not priority_tags, template.slug
        for tag in priority_tags:
            muscles = MUSCLES_BY_PRIORITY_TAG[tag]
            direct_slots = sum(
                bool(set(slot.target_muscles) & muscles)
                for day in template.days
                for slot in day.slots
            )
            assert direct_slots >= MINIMUM_DIRECT_SLOTS_BY_PRIORITY_TAG[tag], (
                template.slug,
                tag,
            )


def test_upper_and_lower_priority_tags_match_the_weekly_layout() -> None:
    upper_templates = [
        template
        for template in TRAINING_PROGRAM_TEMPLATE_SEEDS
        if TemplateFocusTag.UPPER_PRIORITY in template.focus_tags
    ]
    lower = next(
        template
        for template in TRAINING_PROGRAM_TEMPLATE_SEEDS
        if TemplateFocusTag.LOWER_PRIORITY in template.focus_tags
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
    upper_day_counts = [
        sum(bool(set(day.direct_target_muscles) & upper_muscles) for day in template.days)
        for template in upper_templates
    ]
    lower_days = sum(bool(set(day.direct_target_muscles) & lower_muscles) for day in lower.days)
    assert all(
        upper_days >= (2 if len(template.days) == 3 else 3)
        for template, upper_days in zip(upper_templates, upper_day_counts, strict=True)
    )
    assert lower_days >= 2


def test_seed_library_keeps_structural_emphasis_tags_without_user_mutation() -> None:
    upper_priority = next(
        template
        for template in TRAINING_PROGRAM_TEMPLATE_SEEDS
        if template.slug == "p18-4-day-3-upper-1-lower-beginner"
    )
    assert TemplateFocusTag.UPPER_PRIORITY in upper_priority.focus_tags
    assert TemplateFocusTag.UPPER_LOWER in upper_priority.focus_tags

    lower_priority = next(
        template
        for template in TRAINING_PROGRAM_TEMPLATE_SEEDS
        if template.slug == "p21-4-day-3-lower-1-upper-beginner"
    )
    assert TemplateFocusTag.LOWER_PRIORITY in lower_priority.focus_tags
