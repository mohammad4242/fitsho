"""Seed the minimum exercise catalog required by CI benchmark scripts.

The production exercise seed intentionally contains only Fitsho-curated rows.  The
canonical training-template catalog references the imported exercise library, so a
fresh CI database needs deterministic stand-ins for those referenced movements.
"""

from __future__ import annotations

from collections.abc import Iterable
from uuid import NAMESPACE_URL, UUID, uuid5

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database.session import get_engine
from app.exercises.enums import (
    BodyRegion,
    Difficulty,
    Equipment,
    ExerciseContentType,
    ExerciseType,
    MediaType,
    MovementPattern,
    MuscleFocus,
    MuscleGroup,
)
from app.exercises.models import Exercise, ExerciseEquipment, ExerciseSecondaryMuscle
from app.exercises.taxonomy import FOCUSES_BY_MUSCLE
from app.profile.enums import ExperienceLevel
from app.training_templates.seed_data import TRAINING_PROGRAM_TEMPLATE_SEEDS
from app.workouts.bodyweight_templates import get_bodyweight_template

BENCHMARK_SOURCE = "fitsho-ci-benchmark"
BENCHMARK_ID_NAMESPACE = "https://fitsho.local/ci-benchmark/catalog/"

_BODYWEIGHT_METADATA: dict[str, tuple[MuscleGroup, MovementPattern]] = {
    "fedb-drv-squat-squat": (MuscleGroup.QUADRICEPS, MovementPattern.SQUAT),
    "fedb-0493-incline-push-up": (MuscleGroup.CHEST, MovementPattern.HORIZONTAL_PUSH),
    "fedb-drv-push-ups-push-up": (MuscleGroup.CHEST, MovementPattern.HORIZONTAL_PUSH),
    "fedb-0259-close-grip-push-up": (MuscleGroup.TRICEPS, MovementPattern.HORIZONTAL_PUSH),
    "fedb-0499-inverted-row-between-chairs": (
        MuscleGroup.BACK,
        MovementPattern.HORIZONTAL_PULL,
    ),
    "fedb-0651-shoulder-width-pull-up": (MuscleGroup.BACK, MovementPattern.VERTICAL_PULL),
    "fedb-2327-reverse-grip-pull-up": (MuscleGroup.BACK, MovementPattern.VERTICAL_PULL),
    "fedb-2987-close-grip-chin-up": (MuscleGroup.BACK, MovementPattern.VERTICAL_PULL),
    "fedb-1429-pull-up-wide-grip": (MuscleGroup.BACK, MovementPattern.VERTICAL_PULL),
    "fedb-0668-rear-decline-bridge": (MuscleGroup.GLUTES, MovementPattern.HIP_EXTENSION),
    "fedb-0464-front-plank": (MuscleGroup.ABS, MovementPattern.CORE_ANTI_EXTENSION),
    "fedb-0705-side-plank": (
        MuscleGroup.OBLIQUES,
        MovementPattern.CORE_ANTI_LATERAL_FLEXION,
    ),
    "fedb-0872-reverse-crunch": (MuscleGroup.ABS, MovementPattern.SPINAL_FLEXION),
}

_CORE_PATTERNS = frozenset(
    {
        MovementPattern.SPINAL_FLEXION,
        MovementPattern.CORE_ANTI_EXTENSION,
        MovementPattern.CORE_ANTI_ROTATION,
        MovementPattern.CORE_ANTI_LATERAL_FLEXION,
    }
)
_ISOLATION_PATTERNS = frozenset(
    {
        MovementPattern.KNEE_EXTENSION,
        MovementPattern.KNEE_FLEXION,
        MovementPattern.CALF_RAISE,
        MovementPattern.ELBOW_FLEXION,
        MovementPattern.ELBOW_EXTENSION,
        MovementPattern.SHOULDER_ABDUCTION,
    }
)
_LOWER_BODY_MUSCLES = frozenset(
    {
        MuscleGroup.GLUTES,
        MuscleGroup.QUADRICEPS,
        MuscleGroup.HAMSTRINGS,
        MuscleGroup.ADDUCTORS,
        MuscleGroup.ABDUCTORS,
        MuscleGroup.LEGS,
        MuscleGroup.CALVES,
    }
)
_CORE_MUSCLES = frozenset({MuscleGroup.ABS, MuscleGroup.OBLIQUES})


def _catalog_specs() -> dict[str, tuple[tuple[MuscleGroup, ...], MovementPattern]]:
    specs: dict[str, tuple[tuple[MuscleGroup, ...], MovementPattern]] = {}
    for template in TRAINING_PROGRAM_TEMPLATE_SEEDS:
        for day in template.days:
            for slot in day.slots:
                for slug in slot.catalog_slug_hints:
                    candidate = (slot.target_muscles, slot.movement_pattern)
                    previous = specs.setdefault(slug, candidate)
                    if previous[1] != candidate[1]:
                        raise ValueError(f"Conflicting movement pattern for benchmark slug: {slug}")

    for experience_level in (ExperienceLevel.FIRST_MONTH, ExperienceLevel.BEGINNER):
        for days_per_week in (2, 3, 4):
            template = get_bodyweight_template(experience_level, days_per_week)
            if template is None:
                raise ValueError(
                    f"Missing bodyweight benchmark template for {experience_level}/{days_per_week}"
                )
            for day in template.days:
                for slot in day.exercises:
                    muscle, pattern = _BODYWEIGHT_METADATA[slot.exercise_slug]
                    specs.setdefault(slot.exercise_slug, ((muscle,), pattern))
    return specs


def _body_region(primary_muscle: MuscleGroup) -> BodyRegion:
    if primary_muscle in _CORE_MUSCLES:
        return BodyRegion.CORE
    if primary_muscle in _LOWER_BODY_MUSCLES:
        return BodyRegion.LOWER_BODY
    return BodyRegion.UPPER_BODY


def _exercise_type(pattern: MovementPattern) -> ExerciseType:
    if pattern in _CORE_PATTERNS:
        return ExerciseType.CORE
    if pattern in _ISOLATION_PATTERNS:
        return ExerciseType.ISOLATION
    return ExerciseType.COMPOUND


def _equipment(slug: str, pattern: MovementPattern) -> tuple[Equipment, ...]:
    if slug in _BODYWEIGHT_METADATA:
        if pattern is MovementPattern.VERTICAL_PULL:
            return (Equipment.BODYWEIGHT, Equipment.PULL_UP_BAR)
        return (Equipment.BODYWEIGHT,)
    if "barbell" in slug:
        return (Equipment.BARBELL,)
    if "dumbbell" in slug:
        return (Equipment.DUMBBELL,)
    if "cable" in slug:
        return (Equipment.CABLE,)
    if "lever" in slug or "smith" in slug:
        return (Equipment.MACHINE,)
    return (Equipment.BODYWEIGHT,)


def _primary_and_secondary(
    target_muscles: tuple[MuscleGroup, ...],
) -> tuple[MuscleGroup, tuple[MuscleGroup, ...]]:
    if not target_muscles:
        raise ValueError("Benchmark catalog movement must declare a target muscle")
    return target_muscles[0], tuple(target_muscles[1:])


def _stable_id(slug: str) -> UUID:
    return uuid5(NAMESPACE_URL, f"{BENCHMARK_ID_NAMESPACE}{slug}")


def seed_benchmark_catalog(db: Session, slugs: Iterable[str] | None = None) -> int:
    """Insert missing deterministic catalog rows and return the inserted count."""
    all_specs = _catalog_specs()
    requested_slugs = tuple(slugs) if slugs is not None else tuple(all_specs)
    unknown_slugs = set(requested_slugs).difference(all_specs)
    if unknown_slugs:
        raise ValueError(f"Unknown benchmark catalog slugs: {sorted(unknown_slugs)}")

    existing = {
        exercise.slug: exercise
        for exercise in db.scalars(select(Exercise).where(Exercise.slug.in_(requested_slugs)))
    }
    inserted = 0
    for slug in requested_slugs:
        if slug in existing:
            exercise = existing[slug]
            if (
                exercise.content_type is not ExerciseContentType.EXERCISE
                or not exercise.is_active
                or not exercise.is_programmable
            ):
                raise ValueError(f"Existing benchmark movement is not programmable: {slug}")
            continue

        target_muscles, pattern = all_specs[slug]
        primary_muscle, secondary_muscles = _primary_and_secondary(target_muscles)
        focus: MuscleFocus | None = (
            FOCUSES_BY_MUSCLE[primary_muscle][0]
            if FOCUSES_BY_MUSCLE[primary_muscle]
            else None
        )
        exercise = Exercise(
            id=_stable_id(slug),
            slug=slug,
            name_en=slug.replace("-", " ").title(),
            name_fa="حرکت benchmark کتابخانه",
            content_type=ExerciseContentType.EXERCISE,
            body_region=_body_region(primary_muscle),
            primary_muscle=primary_muscle,
            muscle_focus=focus,
            difficulty=Difficulty.INTERMEDIATE,
            movement_pattern=pattern,
            exercise_type=_exercise_type(pattern),
            instructions_en=[
                "Set up safely.",
                "Use controlled form.",
                "Stop if pain appears.",
            ],
            instructions_fa=["ایمن آماده شو.", "فرم را کنترل کن.", "در صورت درد توقف کن."],
            safety_notes_en=["Use a controlled load."],
            safety_notes_fa=["از وزنه قابل‌کنترل استفاده کن."],
            media_path="/exercises/exercise-placeholder.svg",
            media_type=MediaType.PLACEHOLDER,
            source=BENCHMARK_SOURCE,
            source_id=slug,
            is_active=True,
            is_programmable=True,
        )
        exercise.secondary_muscles = [
            # Relationship rows are not required by the template seed, but keep
            # multi-muscle benchmark movements semantically useful to the engine.
            ExerciseSecondaryMuscle(muscle=item) for item in secondary_muscles
        ]
        exercise.equipment_items = [
            ExerciseEquipment(equipment=item) for item in _equipment(slug, pattern)
        ]
        db.add(exercise)
        inserted += 1

    db.commit()
    return inserted


def main() -> None:
    settings = get_settings()
    with Session(get_engine(settings.database_url)) as db:
        inserted = seed_benchmark_catalog(db)
    print(f"Seeded {inserted} benchmark catalog exercises.")


if __name__ == "__main__":
    main()
