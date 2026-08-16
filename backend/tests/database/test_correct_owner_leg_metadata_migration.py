from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

from app.exercises.enums import Equipment, MovementPattern, MuscleGroup

EXPECTED_CORRECTIONS = {
    "35889cc979dbaa7b11f910d20a107832c1bda537f426d5a8f912efb75c925908": (
        "Landmine Squat",
        MuscleGroup.LEGS,
        MovementPattern.SQUAT,
        Equipment.OTHER,
    ),
    "3be618aac4fed3a795d09a8737f6d24d91ea8163e22973c12d01672de5901ae7": (
        "Split Squat",
        MuscleGroup.LEGS,
        MovementPattern.LUNGE,
        Equipment.OTHER,
    ),
    "f20d44173274d17b351db5066edd8096810572211023b1c8e3ea10f18516d05f": (
        "Leg Press - Quads",
        MuscleGroup.QUADRICEPS,
        MovementPattern.SQUAT,
        Equipment.MACHINE,
    ),
    "157b4670b7d3685c85fc834e6cb82550663cd6f84140318100515596064e8127": (
        "Leg Press - Vastus Lateralis",
        MuscleGroup.QUADRICEPS,
        MovementPattern.SQUAT,
        Equipment.MACHINE,
    ),
    "0583f6d60222523f45f9e9eb226f37ac2bba3a3162aab1627bee50c1706c0b4d": (
        "Leg Press - Quadriceps",
        MuscleGroup.QUADRICEPS,
        MovementPattern.SQUAT,
        Equipment.MACHINE,
    ),
    "4169deae978152bbf0bc5ebc188a861397d5ba1fb5dc9b23bf9096544324d8bb": (
        "Leg Press - Front Quads",
        MuscleGroup.QUADRICEPS,
        MovementPattern.SQUAT,
        Equipment.MACHINE,
    ),
}


def test_owner_leg_video_metadata_migration_contains_the_visual_corrections() -> None:
    path = (
        Path(__file__).parents[2]
        / "alembic/versions/20260816_86_correct_owner_leg_video_metadata.py"
    )
    spec = spec_from_file_location("correct_owner_leg_video_metadata", path)
    assert spec is not None and spec.loader is not None
    migration = module_from_spec(spec)
    spec.loader.exec_module(migration)

    assert migration.revision == "20260816_86"
    assert migration.down_revision == "20260816_85"
    assert set(migration.CORRECTIONS) == set(EXPECTED_CORRECTIONS)
    for source_id, expected in EXPECTED_CORRECTIONS.items():
        correction = migration.CORRECTIONS[source_id]
        assert correction["name_en"] == expected[0]
        assert correction["primary_muscle"] is expected[1]
        assert correction["movement_pattern"] is expected[2]
        assert correction["equipment"] == (expected[3],)
