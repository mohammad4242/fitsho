from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum

from app.exercises.enums import MovementPattern, MuscleGroup
from app.training_templates.catalog_invariants import validate_catalog_topology


class TemplateFocusTag(StrEnum):
    """Canonical structural vocabulary for workout-template ranking."""

    FULL_BODY = "full_body"
    UPPER_LOWER = "upper_lower"
    PUSH_PULL_LEGS = "push_pull_legs"
    BODY_PART_ROTATION = "body_part_rotation"

    BALANCED = "balanced"
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


class TemplateTagCategory(StrEnum):
    PRIMARY_STRUCTURE = "primary_structure"
    REGIONAL_BALANCE = "regional_balance"
    MUSCLE_PRIORITY = "muscle_priority"
    STRUCTURAL_CHARACTER = "structural_character"


@dataclass(frozen=True)
class TemplateTagDefinition:
    category: TemplateTagCategory
    meaning: str


TEMPLATE_FOCUS_TAG_DEFINITIONS: dict[TemplateFocusTag, TemplateTagDefinition] = {
    TemplateFocusTag.FULL_BODY: TemplateTagDefinition(
        TemplateTagCategory.PRIMARY_STRUCTURE,
        "The week trains the whole body through repeated mixed-region sessions.",
    ),
    TemplateFocusTag.UPPER_LOWER: TemplateTagDefinition(
        TemplateTagCategory.PRIMARY_STRUCTURE,
        "The week contains explicit upper-body and lower-body session blocks.",
    ),
    TemplateFocusTag.PUSH_PULL_LEGS: TemplateTagDefinition(
        TemplateTagCategory.PRIMARY_STRUCTURE,
        "The week contains explicit push, pull, and lower-body session blocks.",
    ),
    TemplateFocusTag.BODY_PART_ROTATION: TemplateTagDefinition(
        TemplateTagCategory.PRIMARY_STRUCTURE,
        "The week rotates dedicated muscle or body-region sessions.",
    ),
    TemplateFocusTag.BALANCED: TemplateTagDefinition(
        TemplateTagCategory.REGIONAL_BALANCE,
        "No region or muscle receives deliberate additional structural exposure.",
    ),
    TemplateFocusTag.LOWER_PRIORITY: TemplateTagDefinition(
        TemplateTagCategory.REGIONAL_BALANCE,
        "The weekly layout deliberately adds lower-body structural exposure.",
    ),
    TemplateFocusTag.CHEST_PRIORITY: TemplateTagDefinition(
        TemplateTagCategory.MUSCLE_PRIORITY,
        "Chest receives deliberate additional direct structural exposure.",
    ),
    TemplateFocusTag.BACK_PRIORITY: TemplateTagDefinition(
        TemplateTagCategory.MUSCLE_PRIORITY,
        "Back receives deliberate additional direct structural exposure.",
    ),
    TemplateFocusTag.SHOULDERS_PRIORITY: TemplateTagDefinition(
        TemplateTagCategory.MUSCLE_PRIORITY,
        "Shoulders receive deliberate additional direct structural exposure.",
    ),
    TemplateFocusTag.ARMS_PRIORITY: TemplateTagDefinition(
        TemplateTagCategory.MUSCLE_PRIORITY,
        "Biceps and/or triceps receive deliberate additional direct structural exposure.",
    ),
    TemplateFocusTag.GLUTE_PRIORITY: TemplateTagDefinition(
        TemplateTagCategory.MUSCLE_PRIORITY,
        "Glutes receive deliberate additional direct structural exposure.",
    ),
    TemplateFocusTag.QUAD_PRIORITY: TemplateTagDefinition(
        TemplateTagCategory.MUSCLE_PRIORITY,
        "Quadriceps receive deliberate additional direct structural exposure.",
    ),
    TemplateFocusTag.HAMSTRINGS_PRIORITY: TemplateTagDefinition(
        TemplateTagCategory.MUSCLE_PRIORITY,
        "Hamstrings receive deliberate additional direct structural exposure.",
    ),
    TemplateFocusTag.STRENGTH_BIAS: TemplateTagDefinition(
        TemplateTagCategory.STRUCTURAL_CHARACTER,
        "Compound exposure, ordering, frequency, and recovery make the layout strength-friendly.",
    ),
    TemplateFocusTag.COMPOUND_FOCUS: TemplateTagDefinition(
        TemplateTagCategory.STRUCTURAL_CHARACTER,
        "Compound movement roles consistently lead meaningful session structure.",
    ),
    TemplateFocusTag.SPECIALIZATION: TemplateTagDefinition(
        TemplateTagCategory.STRUCTURAL_CHARACTER,
        "The week deliberately adds dedicated or repeated specialization exposure.",
    ),
}

# Historical database rows may still contain this value. It is parsed and
# discarded before a reference becomes active engine data.
LEGACY_UPPER_PRIORITY_TAG = "upper_priority"

CANONICAL_TEMPLATE_FOCUS_TAGS = frozenset(TEMPLATE_FOCUS_TAG_DEFINITIONS)
TEMPLATE_FOCUS_TAGS_BY_CATEGORY: dict[TemplateTagCategory, frozenset[TemplateFocusTag]] = {
    category: frozenset(
        tag
        for tag, definition in TEMPLATE_FOCUS_TAG_DEFINITIONS.items()
        if definition.category is category
    )
    for category in TemplateTagCategory
}
PRIMARY_STRUCTURE_TAGS = TEMPLATE_FOCUS_TAGS_BY_CATEGORY[TemplateTagCategory.PRIMARY_STRUCTURE]
REGIONAL_BALANCE_TAGS = TEMPLATE_FOCUS_TAGS_BY_CATEGORY[TemplateTagCategory.REGIONAL_BALANCE]
MUSCLE_PRIORITY_TAGS = TEMPLATE_FOCUS_TAGS_BY_CATEGORY[TemplateTagCategory.MUSCLE_PRIORITY]
REGIONAL_PRIORITY_TAGS = frozenset({TemplateFocusTag.LOWER_PRIORITY})
PRIORITY_TAGS = REGIONAL_PRIORITY_TAGS | MUSCLE_PRIORITY_TAGS
_ALLOWED_HYBRID_STRUCTURES = frozenset(
    {frozenset({TemplateFocusTag.PUSH_PULL_LEGS, TemplateFocusTag.UPPER_LOWER})}
)

PRIORITY_TAG_BY_MUSCLE: dict[MuscleGroup, TemplateFocusTag] = {
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

REGIONAL_PRIORITY_TAG_BY_MUSCLE: dict[MuscleGroup, TemplateFocusTag] = {
    MuscleGroup.GLUTES: TemplateFocusTag.LOWER_PRIORITY,
    MuscleGroup.QUADRICEPS: TemplateFocusTag.LOWER_PRIORITY,
    MuscleGroup.HAMSTRINGS: TemplateFocusTag.LOWER_PRIORITY,
    MuscleGroup.ADDUCTORS: TemplateFocusTag.LOWER_PRIORITY,
    MuscleGroup.ABDUCTORS: TemplateFocusTag.LOWER_PRIORITY,
    MuscleGroup.LEGS: TemplateFocusTag.LOWER_PRIORITY,
    MuscleGroup.CALVES: TemplateFocusTag.LOWER_PRIORITY,
}

MUSCLES_BY_PRIORITY_TAG: dict[TemplateFocusTag, frozenset[MuscleGroup]] = {
    TemplateFocusTag.CHEST_PRIORITY: frozenset({MuscleGroup.CHEST}),
    TemplateFocusTag.BACK_PRIORITY: frozenset({MuscleGroup.BACK}),
    TemplateFocusTag.SHOULDERS_PRIORITY: frozenset({MuscleGroup.SHOULDERS}),
    TemplateFocusTag.ARMS_PRIORITY: frozenset({MuscleGroup.BICEPS, MuscleGroup.TRICEPS}),
    TemplateFocusTag.GLUTE_PRIORITY: frozenset({MuscleGroup.GLUTES}),
    TemplateFocusTag.QUAD_PRIORITY: frozenset({MuscleGroup.QUADRICEPS}),
    TemplateFocusTag.HAMSTRINGS_PRIORITY: frozenset({MuscleGroup.HAMSTRINGS}),
}

MINIMUM_DIRECT_SLOTS_BY_PRIORITY_TAG: dict[TemplateFocusTag, int] = {
    TemplateFocusTag.CHEST_PRIORITY: 5,
    TemplateFocusTag.BACK_PRIORITY: 5,
    TemplateFocusTag.SHOULDERS_PRIORITY: 5,
    TemplateFocusTag.ARMS_PRIORITY: 6,
    TemplateFocusTag.GLUTE_PRIORITY: 3,
    TemplateFocusTag.QUAD_PRIORITY: 5,
    TemplateFocusTag.HAMSTRINGS_PRIORITY: 3,
}

_UPPER_BODY_MUSCLES = frozenset(
    {
        MuscleGroup.CHEST,
        MuscleGroup.BACK,
        MuscleGroup.SHOULDERS,
        MuscleGroup.BICEPS,
        MuscleGroup.TRICEPS,
    }
)
_LOWER_BODY_MUSCLES = frozenset(
    {
        MuscleGroup.QUADRICEPS,
        MuscleGroup.HAMSTRINGS,
        MuscleGroup.GLUTES,
        MuscleGroup.CALVES,
    }
)
_BALANCE_AUDIT_MUSCLES = (
    MuscleGroup.CHEST,
    MuscleGroup.BACK,
    MuscleGroup.SHOULDERS,
    MuscleGroup.QUADRICEPS,
    MuscleGroup.HAMSTRINGS,
    MuscleGroup.GLUTES,
)
_PUSH_MUSCLES = frozenset({MuscleGroup.CHEST, MuscleGroup.SHOULDERS, MuscleGroup.TRICEPS})
_PULL_MUSCLES = frozenset({MuscleGroup.BACK, MuscleGroup.BICEPS})
_COMPOUND_MOVEMENT_PATTERNS = frozenset(
    {
        MovementPattern.SQUAT,
        MovementPattern.HIP_HINGE,
        MovementPattern.LUNGE,
        MovementPattern.HORIZONTAL_PUSH,
        MovementPattern.HORIZONTAL_PULL,
        MovementPattern.VERTICAL_PUSH,
        MovementPattern.VERTICAL_PULL,
        MovementPattern.HIP_EXTENSION,
    }
)


def validate_focus_tags(tags: Iterable[str | TemplateFocusTag]) -> tuple[TemplateFocusTag, ...]:
    values = tuple(
        str(tag) for tag in tags if str(tag) != LEGACY_UPPER_PRIORITY_TAG
    )
    unknown = sorted(set(values) - CANONICAL_TEMPLATE_FOCUS_TAGS)
    if unknown:
        raise ValueError(f"Unknown template focus tag(s): {', '.join(unknown)}")
    if len(values) != len(set(values)):
        raise ValueError("Focus tags must be unique")
    canonical = tuple(TemplateFocusTag(value) for value in values)
    tag_set = frozenset(canonical)
    structures = tag_set & PRIMARY_STRUCTURE_TAGS
    if not structures:
        raise ValueError("Focus tags require a primary structure")
    if len(structures) > 1 and structures not in _ALLOWED_HYBRID_STRUCTURES:
        raise ValueError("Unsupported primary structure combination")
    if TemplateFocusTag.BALANCED in tag_set and tag_set & PRIORITY_TAGS:
        raise ValueError("Balanced templates cannot declare priority tags")
    if TemplateFocusTag.SPECIALIZATION in tag_set and not tag_set & PRIORITY_TAGS:
        raise ValueError("Specialization requires a priority tag")
    return canonical


def validate_template_focus_tags(
    tags: Iterable[str | TemplateFocusTag],
    *,
    intensity_methods: Iterable[object] = (),
    days: Iterable[object] = (),
) -> tuple[TemplateFocusTag, ...]:
    canonical = validate_focus_tags(tags)
    tag_values = {tag.value for tag in canonical}
    method_values = {_enum_value(method) for method in intensity_methods}
    if overlap := sorted(tag_values & method_values):
        raise ValueError(f"Intensity methods cannot be template focus tags: {', '.join(overlap)}")
    day_items = tuple(days)
    if day_items:
        validate_catalog_topology(len(day_items), canonical)
        _validate_structural_evidence(frozenset(canonical), day_items)
    return canonical


def _enum_value(value: object) -> str:
    raw = getattr(value, "value", value)
    return str(raw)


def _validate_structural_evidence(
    tags: frozenset[TemplateFocusTag],
    days: tuple[object, ...],
) -> None:
    direct_muscles = tuple(_direct_muscles_for_day(day) for day in days)
    slot_groups = tuple(
        tuple(_muscles_for_slot(slot) for slot in _slots_for_day(day)) for day in days
    )

    if TemplateFocusTag.FULL_BODY in tags:
        mixed_days = sum(
            bool(muscles & _UPPER_BODY_MUSCLES) and bool(muscles & _LOWER_BODY_MUSCLES)
            for muscles in direct_muscles
        )
        if mixed_days < (len(days) + 1) // 2:
            raise ValueError("full_body lacks structural evidence")
    if TemplateFocusTag.UPPER_LOWER in tags and not (
        any(
            muscles & _UPPER_BODY_MUSCLES and not muscles & _LOWER_BODY_MUSCLES
            for muscles in direct_muscles
        )
        and any(
            muscles & _LOWER_BODY_MUSCLES and not muscles & _UPPER_BODY_MUSCLES
            for muscles in direct_muscles
        )
    ):
        raise ValueError("upper_lower lacks structural evidence")
    if TemplateFocusTag.PUSH_PULL_LEGS in tags and not (
        any(muscles & _PUSH_MUSCLES and not muscles & _PULL_MUSCLES for muscles in direct_muscles)
        and any(
            muscles & _PULL_MUSCLES and not muscles & _PUSH_MUSCLES for muscles in direct_muscles
        )
        and any(muscles & _LOWER_BODY_MUSCLES for muscles in direct_muscles)
    ):
        raise ValueError("push_pull_legs lacks structural evidence")
    if TemplateFocusTag.BODY_PART_ROTATION in tags and (
        len(days) < 3 or len(set(direct_muscles)) < 3
    ):
        raise ValueError("body_part_rotation lacks structural evidence")

    lower_days = sum(
        bool(muscles & _LOWER_BODY_MUSCLES) and not bool(muscles & _UPPER_BODY_MUSCLES)
        for muscles in direct_muscles
    )
    if TemplateFocusTag.LOWER_PRIORITY in tags and lower_days < 2:
        raise ValueError("lower_priority lacks structural evidence")
    if TemplateFocusTag.BALANCED in tags:
        exposure_days = tuple(
            sum(
                any(muscle in slot_muscles for slot_muscles in day_slot_groups)
                for day_slot_groups in slot_groups
            )
            for muscle in _BALANCE_AUDIT_MUSCLES
        )
        if max(exposure_days) - min(exposure_days) > 2:
            raise ValueError("balanced lacks structural evidence")

    for tag in tags & MUSCLE_PRIORITY_TAGS:
        muscles = MUSCLES_BY_PRIORITY_TAG[tag]
        direct_slots = sum(
            bool(slot_muscles & muscles)
            for day_slot_groups in slot_groups
            for slot_muscles in day_slot_groups
        )
        if direct_slots < MINIMUM_DIRECT_SLOTS_BY_PRIORITY_TAG[tag]:
            raise ValueError(f"{tag.value} lacks structural evidence")

    if TemplateFocusTag.COMPOUND_FOCUS in tags:
        compound_led_days = sum(
            bool(slots) and _movement_pattern_for_slot(slots[0]) in _COMPOUND_MOVEMENT_PATTERNS
            for slots in (_slots_for_day(day) for day in days)
        )
        compound_core_days = sum(
            sum(
                _movement_pattern_for_slot(slot) in _COMPOUND_MOVEMENT_PATTERNS
                and _enum_value(getattr(slot, "adaptation_priority", "")) == "core"
                for slot in _slots_for_day(day)
            )
            >= 2
            for day in days
        )
        required_core_days = (4 * len(days) + 4) // 5
        if compound_led_days != len(days) or compound_core_days < required_core_days:
            raise ValueError("compound_focus lacks structural evidence")
    if TemplateFocusTag.STRENGTH_BIAS in tags and TemplateFocusTag.COMPOUND_FOCUS not in tags:
        raise ValueError("strength_bias lacks structural evidence")
    if TemplateFocusTag.SPECIALIZATION in tags:
        priority_muscles = frozenset(
            muscle for tag in tags & MUSCLE_PRIORITY_TAGS for muscle in MUSCLES_BY_PRIORITY_TAG[tag]
        )
        specialized_slots = sum(
            bool(slot_muscles & priority_muscles)
            for day_slot_groups in slot_groups
            for slot_muscles in day_slot_groups
        )
        if specialized_slots < 5:
            raise ValueError("specialization lacks structural evidence")


def _direct_muscles_for_day(day: object) -> frozenset[MuscleGroup]:
    raw = getattr(day, "direct_target_muscles", getattr(day, "focus", ()))
    return _muscle_values(raw)


def _slots_for_day(day: object) -> tuple[object, ...]:
    return tuple(getattr(day, "slots", ()))


def _muscles_for_slot(slot: object) -> frozenset[MuscleGroup]:
    return _muscle_values(getattr(slot, "target_muscles", ()))


def _muscle_values(values: Iterable[object]) -> frozenset[MuscleGroup]:
    return frozenset(MuscleGroup(_enum_value(value)) for value in values)


def _movement_pattern_for_slot(slot: object) -> MovementPattern | None:
    raw = _enum_value(getattr(slot, "movement_pattern", ""))
    try:
        return MovementPattern(raw)
    except ValueError:
        return None


def priority_tag_for_muscle(muscle: MuscleGroup) -> TemplateFocusTag | None:
    return PRIORITY_TAG_BY_MUSCLE.get(muscle)


def priority_tags_for_muscles(
    muscles: Iterable[MuscleGroup],
) -> frozenset[TemplateFocusTag]:
    return frozenset(
        tag for muscle in muscles if (tag := priority_tag_for_muscle(muscle)) is not None
    )


def regional_priority_tags_for_muscles(
    muscles: Iterable[MuscleGroup],
) -> frozenset[TemplateFocusTag]:
    return frozenset(
        tag
        for muscle in muscles
        if (tag := REGIONAL_PRIORITY_TAG_BY_MUSCLE.get(muscle)) is not None
    )


def has_template_tag(
    tags: Iterable[str | TemplateFocusTag],
    tag: TemplateFocusTag,
) -> bool:
    return tag.value in {str(value) for value in tags}
