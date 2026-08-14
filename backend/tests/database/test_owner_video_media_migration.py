from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from uuid import uuid4

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import text
from sqlalchemy.orm import Session


def test_owner_video_media_migration_round_trip_preserves_colliding_assets(
    db: Session,
) -> None:
    path = (
        Path(__file__).parents[2]
        / "alembic/versions/20260814_80_add_owner_video_media_provenance.py"
    )
    assert path.is_file(), "owner-video media migration is missing"
    spec = spec_from_file_location("owner_video_media_migration", path)
    assert spec is not None and spec.loader is not None
    migration = module_from_spec(spec)
    spec.loader.exec_module(migration)

    schema = f"owner_video_migration_{uuid4().hex}"
    connection = db.connection()
    connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    connection.execute(text(f'SET LOCAL search_path TO "{schema}", public'))
    connection.execute(
        text(
            """
            CREATE TABLE exercise_media_assets (
                id uuid PRIMARY KEY,
                exercise_id uuid NOT NULL,
                presentation varchar(20) NOT NULL,
                role varchar(20) NOT NULL,
                sort_order integer NOT NULL DEFAULT 0,
                media_path varchar(255) NOT NULL,
                media_type varchar(20) NOT NULL,
                CONSTRAINT ck_exercise_media_assets_presentation_values
                    CHECK (presentation IN ('male', 'female')),
                CONSTRAINT uq_exercise_media_assets_exercise_presentation_role_order
                    UNIQUE (exercise_id, presentation, role, sort_order)
            )
            """
        )
    )
    migration.op = Operations(MigrationContext.configure(connection))

    migration.upgrade()
    exercise_id = uuid4()
    connection.execute(
        text(
            """
            INSERT INTO exercise_media_assets (
                id, exercise_id, presentation, role, sort_order,
                media_path, media_type, source, source_id
            ) VALUES
                (:male_id, :exercise_id, 'male', 'video', 0,
                 '/media/male.mp4', 'video', NULL, NULL),
                (:unspecified_id, :exercise_id, 'unspecified', 'video', 0,
                 '/media/owner.mp4', 'video', 'owner-video', :source_id)
            """
        ),
        {
            "male_id": uuid4(),
            "unspecified_id": uuid4(),
            "exercise_id": exercise_id,
            "source_id": "a" * 64,
        },
    )

    migration.downgrade()

    rows = connection.execute(
        text(
            """
            SELECT presentation, sort_order
            FROM exercise_media_assets
            WHERE exercise_id = :exercise_id
            ORDER BY sort_order
            """
        ),
        {"exercise_id": exercise_id},
    ).all()
    assert rows == [("male", 0), ("male", 1)]
    columns = {
        row[0]
        for row in connection.execute(
            text(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = :schema
                  AND table_name = 'exercise_media_assets'
                """
            ),
            {"schema": schema},
        )
    }
    assert "source" not in columns
    assert "source_id" not in columns
