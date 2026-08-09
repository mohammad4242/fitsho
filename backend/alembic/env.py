from logging.config import fileConfig

from sqlalchemy import Enum as SqlEnum
from sqlalchemy import String, engine_from_config, pool

from alembic import context
from app.ai import models as ai_models  # noqa: F401
from app.auth import models  # noqa: F401
from app.body_analysis import comparison_models as body_analysis_comparison_models  # noqa: F401
from app.body_analysis import models as body_analysis_models  # noqa: F401
from app.body_analysis.admin_config import models as ai_admin_config_models  # noqa: F401
from app.body_photos import models as body_photo_models  # noqa: F401
from app.config import get_settings
from app.database.base import Base
from app.exercises import models as exercise_models  # noqa: F401
from app.nutrition import models as nutrition_models  # noqa: F401
from app.profile import models as profile_models  # noqa: F401
from app.training_templates import models as training_template_models  # noqa: F401
from app.workout_cycles import models as workout_cycle_models  # noqa: F401
from app.workout_reviews import models as workout_review_models  # noqa: F401
from app.workouts import models as workout_models  # noqa: F401

config = context.config
config.set_main_option("sqlalchemy.url", get_settings().database_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def compare_type(
    _context: object,
    _inspected_column: object,
    _metadata_column: object,
    inspected_type: object,
    metadata_type: object,
) -> bool | None:
    if isinstance(metadata_type, SqlEnum) and not metadata_type.native_enum:
        if isinstance(inspected_type, String):
            return False
    return None


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=compare_type,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=compare_type,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
