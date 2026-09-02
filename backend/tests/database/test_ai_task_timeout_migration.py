from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import select

from app.body_analysis.admin_config.enums import AIProviderName, AITaskType
from app.body_analysis.admin_config.models import AITaskConfig

AI_TIMEOUT_SECONDS = 420


def _load_migration():
    path = Path(__file__).parents[2] / "alembic/versions/20260903_118_default_ai_timeout.py"
    assert path.is_file(), "AI timeout migration is missing"
    spec = spec_from_file_location("default_ai_timeout_migration", path)
    assert spec is not None and spec.loader is not None
    migration = module_from_spec(spec)
    spec.loader.exec_module(migration)
    return migration


def test_ai_timeout_migration_updates_existing_task_configs(db) -> None:
    task = AITaskConfig(
        task_type=AITaskType.BODY_PHOTO_ANALYSIS,
        provider=AIProviderName.OPENROUTER,
        timeout_seconds=180,
    )
    db.add(task)
    db.flush()

    migration = _load_migration()
    migration.op = Operations(MigrationContext.configure(db.connection()))
    migration.upgrade()
    db.expire_all()

    stored = db.scalar(select(AITaskConfig).where(AITaskConfig.id == task.id))

    assert stored is not None
    assert stored.timeout_seconds == AI_TIMEOUT_SECONDS
