from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


def _load_migration():
    path = Path(__file__).parents[2] / "alembic/versions/20260908_133_add_account_deletion.py"
    spec = spec_from_file_location("account_deletion_migration", path)
    assert spec is not None and spec.loader is not None
    migration = module_from_spec(spec)
    spec.loader.exec_module(migration)
    return migration


def test_account_deletion_migration_has_retention_safe_revision_and_foreign_keys() -> None:
    migration = _load_migration()

    assert migration.revision == "20260908_133"
    assert migration.down_revision == "20260908_132"
    source = Path(migration.__file__).read_text(encoding="utf-8")
    assert 'op.create_table(\n        "account_deletion_requests"' in source
    assert 'sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL")' in source

    for table, column in (
        ("body_analysis_reviews", "reviewer_id"),
        ("workout_plan_reviews", "claimed_by_user_id"),
        ("nutrition_plan_physician_reviews", "physician_user_id"),
        ("nutrition_review_audit_events", "actor_user_id"),
    ):
        assert f'"{table}"' in source
        assert f'"{column}"' in source
        assert 'ondelete="SET NULL"' in source
