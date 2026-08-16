from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


def test_migration_follows_current_taxonomy_revision() -> None:
    path = (
        Path(__file__).parents[2]
        / "alembic/versions/20260816_82_simplify_adductors_focus.py"
    )
    spec = spec_from_file_location("simplify_adductors_focus_migration", path)
    assert spec is not None and spec.loader is not None
    migration = module_from_spec(spec)
    spec.loader.exec_module(migration)

    assert migration.revision == "20260816_82"
    assert migration.down_revision == "20260816_81"
