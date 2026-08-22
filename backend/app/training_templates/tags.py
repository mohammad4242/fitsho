from __future__ import annotations

from collections.abc import Iterable
from enum import StrEnum

from app.exercises.enums import MuscleGroup


class TemplateFocusTag(StrEnum):
    """Canonical structural vocabulary for workout-template ranking."""

    FULL_BODY = "full_body"
    UPPER_LOWER = "upper_lower"
    PUSH_PULL_LEGS = "push_pull_legs"
    BODY_PART_ROTATION = "body_part_rotation"

    BALANCED = "balanced"
    UPPER_PRIORITY = "upper_priority"
    LOWER_PRIORITY = "lower_priority"

    CHEST_PRIORITY = "chest_priority"
    BACK_PRIORITY = "back_priority"
    SHOULDERS_PRIORITY = "shoulders_priority"
    ARMS_PRIORITY = "arms_priority"
    GLUTE_PRIORITY = "glute_priority"
    QUAD_PRIORITY = "quad_priority"
    HAMSTRINGS_PRIORITY = "hamstrings_priority"

    STRENGTH_BIAS = "strength_bias"
    COMPOUND_FOCUS = "compound_focus"
    SPECIALIZATION = "specialization"
    TIME_EFFICIENT = "time_efficient"


TEMPLATE_FOCUS_TAG_DEFINITIONS: dict[str, str] = {
    TemplateFocusTag.FULL_BODY: "Each training day directly trains the major movement regions.",
    TemplateFocusTag.UPPER_LOWER: "The week alternates upper-body and lower-body sessions.",
    TemplateFocusTag.PUSH_PULL_LEGS: (
        "The week separates pushing, pulling, and lower-body sessions."
    ),
    TemplateFocusTag.BODY_PART_ROTATION: (
        "The week rotates dedicated body-part or muscle-region sessions."
    ),
    TemplateFocusTag.BALANCED: "No muscle region receives a deliberate structural priority.",
    TemplateFocusTag.UPPER_PRIORITY: (
        "The weekly layout dedicates additional upper-body sessions relative to a balanced split."
    ),
    TemplateFocusTag.LOWER_PRIORITY: (
        "The weekly layout dedicates additional lower-body sessions relative to a balanced split."
    ),
    TemplateFocusTag.CHEST_PRIORITY: (
        "Chest receives repeated or additional direct structural exposure."
    ),
    TemplateFocusTag.BACK_PRIORITY: (
        "Back receives repeated or additional direct structural exposure."
    ),
    TemplateFocusTag.SHOULDERS_PRIORITY: (
        "Shoulders receive repeated or additional direct structural exposure."
    ),
    TemplateFocusTag.ARMS_PRIORITY: (
        "Biceps and/or triceps receive repeated or additional direct structural exposure."
    ),
    TemplateFocusTag.GLUTE_PRIORITY: (
        "Glutes receive repeated or additional direct structural exposure."
    ),
    TemplateFocusTag.QUAD_PRIORITY: (
        "Quadriceps receive repeated or additional direct structural exposure."
    ),
    TemplateFocusTag.HAMSTRINGS_PRIORITY: (
        "Hamstrings receive repeated or additional direct structural exposure."
    ),
    TemplateFocusTag.STRENGTH_BIAS: (
        "The layout gives compound strength-oriented work a structural priority."
    ),
    TemplateFocusTag.COMPOUND_FOCUS: (
        "Primary compound movement roles lead the sessions before accessory work."
    ),
    TemplateFocusTag.SPECIALIZATION: (
        "The template contains a dedicated or repeated specialization exposure."
    ),
    TemplateFocusTag.TIME_EFFICIENT: (
        "The session layout deliberately concentrates work to reduce transition time."
    ),
}

CANONICAL_TEMPLATE_FOCUS_TAGS = frozenset(TEMPLATE_FOCUS_TAG_DEFINITIONS)

# These aliases exist only for deterministic seed migration. They are not
# accepted by the admin API or persisted in the active library.
LEGACY_FOCUS_TAG_REPLACEMENTS: dict[str, tuple[str, ...]] = {
    "classic": (TemplateFocusTag.BALANCED,),
    "foundation": (),
    "compound_first": (TemplateFocusTag.COMPOUND_FOCUS,),
    "strength_hypertrophy": (TemplateFocusTag.COMPOUND_FOCUS,),
    "legs_priority": (TemplateFocusTag.LOWER_PRIORITY,),
    "hamstrings_glutes": (),
    "direct_targets": (),
    "drop_set": (),
    "frequency_two": (),
    "general_fitness": (TemplateFocusTag.BALANCED,),
    "high_frequency": (),
    "hypertrophy": (TemplateFocusTag.BALANCED,),
    "long_session": (),
    "strength": (),
    "fat_loss": (TemplateFocusTag.BALANCED,),
    "build_muscle": (),
    "superset": (),
    "three_day": (),
    "volume": (),
    "weak_point": (),
}

# Additions are explicit because the old tags did not always describe the
# complete structural layout. Values are canonical and are de-duplicated.
STRUCTURAL_FOCUS_TAG_ADDITIONS_BY_TEMPLATE: dict[str, tuple[str, ...]] = {
    "two-day-full-body-foundation": (TemplateFocusTag.BALANCED,),
    "two-day-upper-lower-foundation": (TemplateFocusTag.BALANCED,),
    "two-day-upper-lower-strength-hypertrophy": (TemplateFocusTag.BALANCED,),
    "three-day-full-body-foundation": (TemplateFocusTag.BALANCED,),
    "three-day-full-body-drop-set": (TemplateFocusTag.BALANCED,),
    "four-day-classic-body-part": (TemplateFocusTag.BALANCED,),
    "four-day-phul": (TemplateFocusTag.BALANCED,),
    "five-day-ppl-upper-lower": (TemplateFocusTag.UPPER_PRIORITY,),
    "five-day-posterior-chain-superset": (
        TemplateFocusTag.BODY_PART_ROTATION,
        TemplateFocusTag.LOWER_PRIORITY,
        TemplateFocusTag.HAMSTRINGS_PRIORITY,
        TemplateFocusTag.GLUTE_PRIORITY,
    ),
    "four-day-beginner-body-part-foundation": (TemplateFocusTag.BALANCED,),
    "four-day-advanced-posterior-chain": (
        TemplateFocusTag.LOWER_PRIORITY,
        TemplateFocusTag.HAMSTRINGS_PRIORITY,
        TemplateFocusTag.GLUTE_PRIORITY,
    ),
    "five-day-quad-priority": (TemplateFocusTag.LOWER_PRIORITY,),
    "five-day-advanced-leg-specialization": (
        TemplateFocusTag.QUAD_PRIORITY,
        TemplateFocusTag.HAMSTRINGS_PRIORITY,
        TemplateFocusTag.GLUTE_PRIORITY,
    ),
    "six-day-ppl-twice": (TemplateFocusTag.BALANCED,),
    "six-day-ppl-volume": (TemplateFocusTag.BALANCED,),
    "six-day-chest-back-legs-shoulders-arms-legs": (TemplateFocusTag.BALANCED,),
    "two-day-full-body-strength-beginner": (TemplateFocusTag.STRENGTH_BIAS,),
    "three-day-full-body-strength-beginner": (TemplateFocusTag.STRENGTH_BIAS,),
    "three-day-full-body-strength-intermediate": (TemplateFocusTag.STRENGTH_BIAS,),
    "four-day-upper-lower-strength-intermediate": (TemplateFocusTag.STRENGTH_BIAS,),
    "four-day-upper-lower-strength-advanced": (TemplateFocusTag.STRENGTH_BIAS,),
    "five-day-strength-intermediate": (TemplateFocusTag.STRENGTH_BIAS,),
    "five-day-strength-advanced": (TemplateFocusTag.STRENGTH_BIAS,),
    "six-day-push-pull-legs-strength": (TemplateFocusTag.STRENGTH_BIAS,),
}

TEMPLATE_FOCUS_TAGS_TO_REMOVE: dict[str, frozenset[str]] = {
    "three-day-full-body-drop-set": frozenset({TemplateFocusTag.TIME_EFFICIENT}),
    "five-day-posterior-chain-superset": frozenset({TemplateFocusTag.TIME_EFFICIENT}),
}

PRIORITY_TAG_BY_MUSCLE: dict[MuscleGroup, str] = {
    MuscleGroup.CHEST: TemplateFocusTag.CHEST_PRIORITY,
    MuscleGroup.BACK: TemplateFocusTag.BACK_PRIORITY,
    MuscleGroup.SHOULDERS: TemplateFocusTag.SHOULDERS_PRIORITY,
    MuscleGroup.BICEPS: TemplateFocusTag.ARMS_PRIORITY,
    MuscleGroup.TRICEPS: TemplateFocusTag.ARMS_PRIORITY,
    MuscleGroup.FOREARMS: TemplateFocusTag.ARMS_PRIORITY,
    MuscleGroup.GLUTES: TemplateFocusTag.GLUTE_PRIORITY,
    MuscleGroup.QUADRICEPS: TemplateFocusTag.QUAD_PRIORITY,
    MuscleGroup.HAMSTRINGS: TemplateFocusTag.HAMSTRINGS_PRIORITY,
}


def validate_focus_tags(tags: Iterable[str]) -> tuple[str, ...]:
    values = tuple(str(tag) for tag in tags)
    unknown = sorted(set(values) - CANONICAL_TEMPLATE_FOCUS_TAGS)
    if unknown:
        raise ValueError(f"Unknown template focus tag(s): {', '.join(unknown)}")
    if len(values) != len(set(values)):
        raise ValueError("Focus tags must be unique")
    return values


def normalize_focus_tags(tags: Iterable[str]) -> tuple[str, ...]:
    values = tuple(str(tag) for tag in tags)
    unknown = sorted(set(values) - CANONICAL_TEMPLATE_FOCUS_TAGS)
    if unknown:
        raise ValueError(f"Unknown template focus tag(s): {', '.join(unknown)}")
    return tuple(dict.fromkeys(values))


def normalize_seed_focus_tags(slug: str, tags: Iterable[str]) -> tuple[str, ...]:
    normalized: list[str] = []
    for tag in tags:
        replacement = LEGACY_FOCUS_TAG_REPLACEMENTS.get(tag, (tag,))
        normalized.extend(replacement)
    normalized.extend(STRUCTURAL_FOCUS_TAG_ADDITIONS_BY_TEMPLATE.get(slug, ()))
    removed = TEMPLATE_FOCUS_TAGS_TO_REMOVE.get(slug, frozenset())
    normalized = [tag for tag in normalized if tag not in removed]
    if any(tag.endswith("_priority") for tag in normalized):
        normalized = [tag for tag in normalized if tag != TemplateFocusTag.BALANCED]
    return normalize_focus_tags(normalized)


def priority_tag_for_muscle(muscle: MuscleGroup) -> str | None:
    return PRIORITY_TAG_BY_MUSCLE.get(muscle)
