from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


def test_nested_lower_back_migration_contract() -> None:
    path = (
        Path(__file__).parents[2]
        / "alembic/versions/20260816_87_move_lower_back_into_back_focus.py"
    )
    spec = spec_from_file_location("nested_lower_back_migration", path)
    assert spec is not None and spec.loader is not None
    migration = module_from_spec(spec)
    spec.loader.exec_module(migration)

    assert migration.revision == "20260816_87"
    assert migration.down_revision == "20260816_86"
    assert migration._OLD_PRIMARY == "lower_back"
    assert migration._NEW_PRIMARY == "back"
    assert migration._NEW_FOCUS == "lower_back"
