from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


def test_migration_adds_abductors_and_legs_to_controlled_muscle_values() -> None:
    path = (
        Path(__file__).parents[2]
        / "alembic/versions/20260816_85_add_lower_leg_muscle_groups.py"
    )
    spec = spec_from_file_location("add_lower_leg_muscle_groups_migration", path)
    assert spec is not None and spec.loader is not None
    migration = module_from_spec(spec)
    spec.loader.exec_module(migration)

    assert migration.revision == "20260816_85"
    assert migration.down_revision == "20260816_84"
    assert "abductors" in migration.MUSCLE_GROUPS
    assert "legs" in migration.MUSCLE_GROUPS
