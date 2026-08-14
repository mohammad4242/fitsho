from collections.abc import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.exercises.enums import (
    BodyRegion,
    Difficulty,
    Equipment,
    ExerciseCautionTag,
    ExerciseType,
    MediaType,
    MovementPattern,
    MuscleFocus,
    MuscleGroup,
)
from app.exercises.focus_classifier import classify_muscle_focus, refine_primary_muscle
from app.exercises.models import (
    Exercise,
    ExerciseCautionTagItem,
    ExerciseEquipment,
    ExerciseSecondaryMuscle,
)
from app.training_templates.seed_data import TemplateSlotSeed

TEMPLATE_PLACEHOLDER_SOURCE = "fitsho_training_template"
PLACEHOLDER_MEDIA_PATH = "/exercises/exercise-placeholder.svg"

_UPPER_BODY_MUSCLES = frozenset(
    {
        MuscleGroup.CHEST,
        MuscleGroup.BACK,
        MuscleGroup.SHOULDERS,
        MuscleGroup.BICEPS,
        MuscleGroup.TRICEPS,
        MuscleGroup.TRAPS,
        MuscleGroup.FOREARMS,
        MuscleGroup.NECK,
    }
)
_CORE_MUSCLES = frozenset({MuscleGroup.ABS, MuscleGroup.OBLIQUES, MuscleGroup.LOWER_BACK})
_COMPOUND_PATTERNS = frozenset(
    {
        MovementPattern.HORIZONTAL_PUSH,
        MovementPattern.VERTICAL_PUSH,
        MovementPattern.HORIZONTAL_PULL,
        MovementPattern.VERTICAL_PULL,
        MovementPattern.SQUAT,
        MovementPattern.HIP_HINGE,
        MovementPattern.LUNGE,
        MovementPattern.HIP_EXTENSION,
    }
)
_CORE_PATTERNS = frozenset(
    {
        MovementPattern.CORE_ANTI_EXTENSION,
        MovementPattern.CORE_ANTI_ROTATION,
        MovementPattern.CORE_ANTI_LATERAL_FLEXION,
        MovementPattern.SPINAL_FLEXION,
    }
)
_ISOLATION_SLOTS = frozenset(
    {"cable-fly", "pec-deck-fly", "cable-pullover", "rear-delt-fly", "face-pull"}
)
_NAMES = {
    "overhead-dumbbell-extension": (
        "Overhead Dumbbell Triceps Extension",
        "پشت بازو دمبل بالای سر",
    ),
    "rear-delt-fly": ("Rear Delt Fly", "فلای پشت سرشانه"),
    "romanian-deadlift": ("Romanian Deadlift", "ددلیفت رومانیایی"),
}


def is_template_catalog_placeholder(exercise: Exercise) -> bool:
    return exercise.source == TEMPLATE_PLACEHOLDER_SOURCE


def ensure_template_catalog_placeholders(
    db: Session,
    slots: Iterable[TemplateSlotSeed],
) -> None:
    slot_items = tuple(slots)
    candidate_slugs = {
        candidate_slug
        for slot in slot_items
        for candidate_slug in slot.catalog_slug_hints
    }
    existing = {
        exercise.slug: exercise
        for exercise in db.scalars(select(Exercise).where(Exercise.slug.in_(candidate_slugs)))
    }

    for slot in slot_items:
        candidates = [
            existing[candidate_slug]
            for candidate_slug in slot.catalog_slug_hints
            if candidate_slug in existing
        ]
        if any(not is_template_catalog_placeholder(candidate) for candidate in candidates):
            continue
        if slot.exercise_slug_hint in existing:
            continue
        placeholder = _placeholder_exercise(slot)
        db.add(placeholder)
        existing[placeholder.slug] = placeholder


def _placeholder_exercise(slot: TemplateSlotSeed) -> Exercise:
    name_en, name_fa = _placeholder_names(slot)
    primary_muscle = refine_primary_muscle(
        slot.target_muscles[0],
        name_en,
        slot.movement_pattern,
    )
    if primary_muscle is None:
        raise ValueError(f"Template placeholder {slot.exercise_slug_hint} has no primary muscle")
    exercise_type = _exercise_type(slot)
    muscle_focus = _placeholder_focus(
        primary_muscle,
        name_en,
        slot.movement_pattern,
        exercise_type,
    )
    return Exercise(
        slug=slot.exercise_slug_hint,
        name_en=name_en,
        name_fa=name_fa,
        body_region=_body_region(primary_muscle),
        primary_muscle=primary_muscle,
        muscle_focus=muscle_focus,
        difficulty=Difficulty.INTERMEDIATE,
        movement_pattern=slot.movement_pattern,
        exercise_type=exercise_type,
        instructions_en=[
            "Set up the equipment securely and choose a controlled load.",
            "Move through the prescribed range while controlling the target muscle.",
            "Stop the set if technique changes or pain appears.",
        ],
        instructions_fa=[
            "وسیله را ایمن تنظیم کن و وزنه‌ای قابل‌کنترل انتخاب کن.",
            "در دامنهٔ تعیین‌شده با کنترل عضلهٔ هدف حرکت کن.",
            "اگر فرم به‌هم خورد یا درد ایجاد شد، ست را متوقف کن.",
        ],
        safety_notes_en=[
            (
                "This catalog draft needs a coach review and approved media "
                "before it can be programmed."
            ),
        ],
        safety_notes_fa=[
            (
                "این پیش‌نویس کتابخانه پیش از استفاده در برنامه به بازبینی مربی و "
                "رسانهٔ تأییدشده نیاز دارد."
            ),
        ],
        media_path=PLACEHOLDER_MEDIA_PATH,
        media_type=MediaType.PLACEHOLDER,
        source=TEMPLATE_PLACEHOLDER_SOURCE,
        source_id=slot.exercise_slug_hint,
        short_description_en=(
            "Template-library placeholder awaiting reviewed media and coaching details."
        ),
        source_metadata_en={
            "created_for": "training_program_template",
            "target_muscles": [muscle.value for muscle in slot.target_muscles],
        },
        needs_review=True,
        is_active=True,
        is_programmable=False,
        secondary_muscles=[
            ExerciseSecondaryMuscle(muscle=muscle)
            for muscle in slot.target_muscles[1:]
            if muscle is not primary_muscle
        ],
        equipment_items=[ExerciseEquipment(equipment=_equipment(slot.exercise_slug_hint))],
        caution_tag_items=[
            ExerciseCautionTagItem(caution_tag=tag) for tag in _caution_tags(slot.movement_pattern)
        ],
    )


def _placeholder_focus(
    primary_muscle: MuscleGroup,
    name_en: str,
    movement_pattern: MovementPattern,
    exercise_type: ExerciseType,
) -> MuscleFocus:
    classification = classify_muscle_focus(
        primary_muscle=primary_muscle,
        source_target=None,
        source_muscle_group=None,
        secondary_targets=(),
        name_en=name_en,
        movement_pattern=movement_pattern,
        exercise_type=exercise_type,
        instructions_en=(),
    )
    if classification is None:
        raise ValueError(f"Template placeholder {name_en} has unresolved muscle focus")
    return classification.focus


def _placeholder_names(slot: TemplateSlotSeed) -> tuple[str, str]:
    if slot.placeholder_name_en is not None and slot.placeholder_name_fa is not None:
        return slot.placeholder_name_en, slot.placeholder_name_fa
    return _NAMES.get(
        slot.exercise_slug_hint,
        (slot.exercise_slug_hint.replace("-", " ").title(), slot.exercise_slug_hint),
    )


def _body_region(muscle: MuscleGroup) -> BodyRegion:
    if muscle in _UPPER_BODY_MUSCLES:
        return BodyRegion.UPPER_BODY
    if muscle in _CORE_MUSCLES:
        return BodyRegion.CORE
    return BodyRegion.LOWER_BODY


def _exercise_type(slot: TemplateSlotSeed) -> ExerciseType:
    if slot.movement_pattern in _CORE_PATTERNS:
        return ExerciseType.CORE
    if (
        slot.movement_pattern in _COMPOUND_PATTERNS
        and slot.exercise_slug_hint not in _ISOLATION_SLOTS
    ):
        return ExerciseType.COMPOUND
    return ExerciseType.ISOLATION


def _equipment(slug: str) -> Equipment:
    if "cable" in slug or "rope" in slug or slug == "pallof-press":
        return Equipment.CABLE
    if "dumbbell" in slug:
        return Equipment.DUMBBELL
    if "barbell" in slug or slug == "romanian-deadlift":
        return Equipment.BARBELL
    if slug in {"dead-bug", "side-plank"}:
        return Equipment.BODYWEIGHT
    if any(term in slug for term in ("machine", "hack", "pec-deck", "leg-curl", "calf")):
        return Equipment.MACHINE
    return Equipment.OTHER


def _caution_tags(pattern: MovementPattern) -> tuple[ExerciseCautionTag, ...]:
    if pattern is MovementPattern.HIP_HINGE:
        return (ExerciseCautionTag.LOWER_BACK_LOADING,)
    if pattern in {MovementPattern.SQUAT, MovementPattern.LUNGE}:
        return (ExerciseCautionTag.DEEP_KNEE_FLEXION,)
    if pattern is MovementPattern.VERTICAL_PUSH:
        return (ExerciseCautionTag.OVERHEAD_POSITION,)
    return ()
