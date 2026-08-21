from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from uuid import uuid4

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.exercises.enums import (
    BodyRegion,
    Difficulty,
    Equipment,
    ExerciseType,
    MediaType,
    MovementPattern,
    MuscleFocus,
    MuscleGroup,
)
from app.exercises.models import Exercise, ExerciseEquipment


def _load_migration():
    path = (
        Path(__file__).parents[2]
        / "alembic/versions/20260821_102_complete_vertical_pull_equipment.py"
    )
    spec = spec_from_file_location("complete_vertical_pull_equipment", path)
    assert spec is not None and spec.loader is not None
    migration = module_from_spec(spec)
    spec.loader.exec_module(migration)
    return migration


def test_vertical_pull_metadata_migration_adds_bar_and_bench_requirements(
    db: Session,
) -> None:
    source_id = f"equipment-regression-{uuid4().hex}"
    exercise = Exercise(
        slug=f"equipment-regression-{uuid4().hex}",
        name_en="Bench Pull-Up",
        name_fa="بارفیکس روی نیمکت",
        body_region=BodyRegion.UPPER_BODY,
        primary_muscle=MuscleGroup.BACK,
        muscle_focus=MuscleFocus.LATS,
        difficulty=Difficulty.BEGINNER,
        movement_pattern=MovementPattern.VERTICAL_PULL,
        exercise_type=ExerciseType.COMPOUND,
        instructions_en=["Set up", "Pull", "Lower"],
        instructions_fa=["آماده شو", "بکش", "پایین بیا"],
        safety_notes_en=[],
        safety_notes_fa=[],
        media_path="placeholder.webp",
        media_type=MediaType.PLACEHOLDER,
        source="free-exercise-db",
        source_id=source_id,
        equipment_items=[ExerciseEquipment(equipment=Equipment.BODYWEIGHT)],
    )
    db.add(exercise)
    db.flush()

    migration = _load_migration()
    migration.op = Operations(MigrationContext.configure(db.connection()))
    migration.upgrade()
    db.expire_all()

    stored = db.scalar(select(Exercise).where(Exercise.id == exercise.id))

    assert stored is not None
    assert {item.equipment for item in stored.equipment_items} == {
        Equipment.BODYWEIGHT,
        Equipment.PULL_UP_BAR,
        Equipment.BENCH,
    }
