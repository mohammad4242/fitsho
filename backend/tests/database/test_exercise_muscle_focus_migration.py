from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

from app.exercises.enums import MuscleFocus, MuscleGroup
from app.exercises.focus_manifest import FOCUS_MANIFEST
from app.exercises.taxonomy import is_compatible_muscle_focus


def test_migration_revision_follows_current_head() -> None:
    path = Path(__file__).parents[2] / "alembic/versions/20260814_78_add_exercise_muscle_focus.py"
    spec = spec_from_file_location("exercise_muscle_focus_migration", path)
    assert spec is not None and spec.loader is not None
    migration = module_from_spec(spec)
    spec.loader.exec_module(migration)
    assert migration.revision == "20260814_78"
    assert migration.down_revision == "20260814_77"


def test_migration_manifest_is_complete_and_compatible() -> None:
    assert len(FOCUS_MANIFEST) == 341
    assert all(
        is_compatible_muscle_focus(entry.primary_muscle, entry.muscle_focus)
        for entry in FOCUS_MANIFEST.values()
    )
    corrections = {
        entry.key
        for entry in FOCUS_MANIFEST.values()
        if entry.previous_primary_muscle is MuscleGroup.ABS
        and entry.primary_muscle is MuscleGroup.OBLIQUES
        and entry.muscle_focus
        in {
            MuscleFocus.TRUNK_ROTATION,
            MuscleFocus.LATERAL_FLEXION,
            MuscleFocus.ANTI_ROTATION,
        }
    }
    assert corrections == {
        "free-exercise-db:0230",
        "free-exercise-db:0407",
        "free-exercise-db:0562",
        "free-exercise-db:0777",
        "free-exercise-db:0862",
        "fitsho_training_template:pallof-press",
        "fitsho_training_template:side-plank",
    }
