from __future__ import annotations

from collections.abc import Iterable
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy.orm import Session

from app.exercises.enums import (
    Difficulty,
    ExerciseType,
    MediaType,
    MovementPattern,
    MuscleFocus,
    MuscleGroup,
)
from app.exercises.models import Exercise

REAL_CATALOG_SLUGS = {
    "fedb-0750-smith-chair-squat",
    "fedb-1435-barbell-back-squat",
    "fedb-0042-barbell-front-squat",
    "fedb-2611-lever-horizontal-leg-press",
    "fedb-0585-lever-leg-extension",
    "fedb-0336-dumbbell-lunge",
    "fedb-0300-dumbbell-deadlift",
    "fedb-0599-lever-seated-leg-curl",
    "fedb-0586-lever-lying-leg-curl",
    "fedb-0668-rear-decline-bridge",
    "fedb-0605-lever-standing-calf-raise",
    "fedb-0577-lever-lying-chest-press",
    "fedb-1299-lever-incline-hammer-chest-press",
    "fedb-0025-barbell-bench-press",
    "fedb-0314-dumbbell-incline-bench-press",
    "fedb-1269-cable-standing-fly",
    "fedb-0581-lever-high-row",
    "owner-e0c26a271aac-barbell-bent-over-row",
    "owner-2a5de4dc7ba3-seated-cable-row",
    "fedb-0974-cable-close-grip-lat-pulldown",
    "fedb-0238-cable-straight-arm-pulldown",
    "fedb-0765-smith-seated-shoulder-press",
    "fedb-0289-seated-dumbbell-shoulder-press",
    "fedb-0553-military-press",
    "fedb-0584-lever-lateral-raise",
    "fedb-0178-cable-lateral-raise",
    "fedb-0602-lever-seated-reverse-fly",
    "fedb-0592-lever-preacher-curl",
    "fedb-0285-seated-alternating-dumbbell-curl",
    "fedb-0298-dumbbell-cross-body-hammer-curl",
    "fedb-0031-barbell-curl",
    "fedb-0229-cable-standing-inner-curl",
    "fedb-1723-cable-triceps-pushdown",
    "fedb-0200-cable-rope-triceps-pushdown",
    "fedb-0194-cable-rope-overhead-triceps-extension",
    "fedb-0095-barbell-shrug",
    "fedb-1452-lever-seated-crunch",
    "fedb-0464-front-plank",
    "fedb-0705-side-plank",
    "fedb-0334-dumbbell-lateral-raise",
    "owner-cb58d2dbac7f-dumbbell-bench-press",
}


def _metadata(
    slug: str,
) -> tuple[MuscleGroup, MuscleFocus | None, MovementPattern, ExerciseType]:
    if "shoulder-press" in slug or "military-press" in slug:
        return (
            MuscleGroup.SHOULDERS,
            MuscleFocus.GENERAL_SHOULDERS,
            MovementPattern.VERTICAL_PUSH,
            ExerciseType.COMPOUND,
        )
    if "triceps" in slug:
        return (
            MuscleGroup.TRICEPS,
            MuscleFocus.GENERAL_TRICEPS,
            MovementPattern.ELBOW_EXTENSION,
            ExerciseType.ISOLATION,
        )
    if ("curl" in slug and "leg-curl" not in slug) or "preacher" in slug:
        return (
            MuscleGroup.BICEPS,
            MuscleFocus.GENERAL_BICEPS,
            MovementPattern.ELBOW_FLEXION,
            ExerciseType.ISOLATION,
        )
    if "shrug" in slug:
        return (
            MuscleGroup.TRAPS,
            MuscleFocus.UPPER_TRAPS,
            MovementPattern.SHRUG,
            ExerciseType.ISOLATION,
        )
    if "crunch" in slug:
        return (
            MuscleGroup.ABS,
            MuscleFocus.TRUNK_FLEXION,
            MovementPattern.SPINAL_FLEXION,
            ExerciseType.CORE,
        )
    if "side-plank" in slug:
        return (
            MuscleGroup.OBLIQUES,
            MuscleFocus.LATERAL_FLEXION,
            MovementPattern.CORE_ANTI_LATERAL_FLEXION,
            ExerciseType.CORE,
        )
    if "plank" in slug:
        return (
            MuscleGroup.ABS,
            MuscleFocus.ANTI_EXTENSION,
            MovementPattern.CORE_ANTI_EXTENSION,
            ExerciseType.CORE,
        )
    if "calf" in slug:
        return (
            MuscleGroup.CALVES,
            MuscleFocus.GENERAL_CALVES,
            MovementPattern.CALF_RAISE,
            ExerciseType.ISOLATION,
        )
    if "glute" in slug or "bridge" in slug:
        return (
            MuscleGroup.GLUTES,
            MuscleFocus.GLUTE_MAX,
            MovementPattern.HIP_EXTENSION,
            ExerciseType.COMPOUND,
        )
    if "leg-curl" in slug:
        return (
            MuscleGroup.HAMSTRINGS,
            MuscleFocus.HAMSTRINGS_KNEE_FLEXION,
            MovementPattern.KNEE_FLEXION,
            ExerciseType.ISOLATION,
        )
    if "deadlift" in slug:
        return (
            MuscleGroup.HAMSTRINGS,
            MuscleFocus.HAMSTRINGS_HIP_EXTENSION,
            MovementPattern.HIP_HINGE,
            ExerciseType.COMPOUND,
        )
    if "lunge" in slug:
        return MuscleGroup.QUADRICEPS, None, MovementPattern.LUNGE, ExerciseType.COMPOUND
    if "squat" in slug or "leg-press" in slug:
        return MuscleGroup.QUADRICEPS, None, MovementPattern.SQUAT, ExerciseType.COMPOUND
    if "leg-extension" in slug:
        return MuscleGroup.QUADRICEPS, None, MovementPattern.KNEE_EXTENSION, ExerciseType.ISOLATION
    if "lateral-raise" in slug:
        return (
            MuscleGroup.SHOULDERS,
            MuscleFocus.LATERAL_DELT,
            MovementPattern.SHOULDER_ABDUCTION,
            ExerciseType.ISOLATION,
        )
    if "reverse-fly" in slug:
        return (
            MuscleGroup.SHOULDERS,
            MuscleFocus.REAR_DELT,
            MovementPattern.HORIZONTAL_PULL,
            ExerciseType.ISOLATION,
        )
    if "row" in slug or "pulldown" in slug:
        pattern = (
            MovementPattern.VERTICAL_PULL if "pulldown" in slug else MovementPattern.HORIZONTAL_PULL
        )
        return MuscleGroup.BACK, MuscleFocus.GENERAL_BACK, pattern, ExerciseType.COMPOUND
    if "press" in slug or "fly" in slug:
        return (
            MuscleGroup.CHEST,
            MuscleFocus.GENERAL_CHEST,
            MovementPattern.HORIZONTAL_PUSH,
            ExerciseType.ISOLATION if "fly" in slug else ExerciseType.COMPOUND,
        )
    raise AssertionError(f"No catalog fixture metadata for {slug}")


def seed_real_catalog_exercises(
    db: Session,
    slugs: Iterable[str] = REAL_CATALOG_SLUGS,
) -> None:
    for slug in slugs:
        primary_muscle, muscle_focus, movement_pattern, exercise_type = _metadata(slug)
        db.add(
            Exercise(
                id=uuid5(NAMESPACE_URL, f"https://fitsho.test/catalog/{slug}"),
                slug=slug,
                name_en=slug.replace("-", " ").title(),
                name_fa="حرکت واقعی کتابخانه",
                primary_muscle=primary_muscle,
                muscle_focus=muscle_focus,
                difficulty=Difficulty.INTERMEDIATE,
                movement_pattern=movement_pattern,
                exercise_type=exercise_type,
                instructions_en=["Set up safely.", "Use controlled form.", "Stop if pain appears."],
                instructions_fa=["ایمن آماده شو.", "فرم را کنترل کن.", "در صورت درد توقف کن."],
                safety_notes_en=["Use a controlled load."],
                safety_notes_fa=["از وزنه قابل‌کنترل استفاده کن."],
                media_path=f"/media/exercises/{slug}.gif",
                media_type=MediaType.GIF,
                source="free-exercise-db",
                source_id=f"test-{slug}",
                is_active=True,
                is_programmable=True,
            )
        )
    db.flush()
