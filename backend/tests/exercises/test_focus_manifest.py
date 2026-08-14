from app.exercises.enums import (
    BodyRegion,
    Difficulty,
    ExerciseType,
    MediaType,
    MovementPattern,
    MuscleFocus,
    MuscleGroup,
)
from app.exercises.focus_manifest import FOCUS_MANIFEST, manifest_entry_for_exercise
from app.exercises.models import Exercise


def exercise(**overrides: object) -> Exercise:
    values: dict[str, object] = {
        "slug": "incline-press",
        "name_en": "Incline Press",
        "name_fa": "پرس بالاسینه",
        "body_region": BodyRegion.UPPER_BODY,
        "primary_muscle": MuscleGroup.CHEST,
        "difficulty": Difficulty.INTERMEDIATE,
        "movement_pattern": MovementPattern.HORIZONTAL_PUSH,
        "exercise_type": ExerciseType.COMPOUND,
        "instructions_en": ["Set up.", "Lower.", "Press."],
        "instructions_fa": ["آماده شوید.", "پایین ببرید.", "پرس کنید."],
        "safety_notes_en": [],
        "safety_notes_fa": [],
        "media_path": "/exercise.mp4",
        "media_type": MediaType.VIDEO,
        "source": "free-exercise-db",
        "source_id": "incline-press",
        "source_metadata_en": {
            "target": "upper pectorals",
            "muscleGroup": "pectoralis major, clavicular head",
            "secondaryMuscles": ["triceps", "anterior deltoid"],
        },
    }
    values.update(overrides)
    return Exercise(**values)


def test_manifest_entry_uses_stable_source_identity_and_source_metadata() -> None:
    entry = manifest_entry_for_exercise(exercise())
    assert entry.key == "free-exercise-db:incline-press"
    assert entry.primary_muscle is MuscleGroup.CHEST
    assert entry.muscle_focus is MuscleFocus.UPPER_CHEST
    assert entry.basis == "source_target:upper pectorals"


def test_manifest_entry_records_approved_core_primary_correction() -> None:
    entry = manifest_entry_for_exercise(
        exercise(
            slug="pallof-press",
            name_en="Pallof Press",
            source="fitsho_training_template",
            source_id="pallof-press",
            body_region=BodyRegion.CORE,
            primary_muscle=MuscleGroup.ABS,
            movement_pattern=MovementPattern.CORE_ANTI_ROTATION,
            exercise_type=ExerciseType.CORE,
            source_metadata_en=None,
        )
    )
    assert entry.previous_primary_muscle is MuscleGroup.ABS
    assert entry.primary_muscle is MuscleGroup.OBLIQUES
    assert entry.muscle_focus is MuscleFocus.ANTI_ROTATION


def test_checked_in_manifest_covers_the_reviewed_live_catalogue() -> None:
    assert len(FOCUS_MANIFEST) == 341
    assert sum(item.muscle_focus is not None for item in FOCUS_MANIFEST.values()) == 318
    assert sum(item.muscle_focus is None for item in FOCUS_MANIFEST.values()) == 23
    assert all(
        item.primary_muscle is not None
        for item in FOCUS_MANIFEST.values()
        if item.muscle_focus
    )
