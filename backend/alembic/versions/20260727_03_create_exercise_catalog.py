from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision = "20260727_03"
down_revision = "20260727_02"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

BODY_REGIONS = ("upper_body", "lower_body", "core")
MUSCLE_GROUPS = (
    "chest",
    "back",
    "shoulders",
    "biceps",
    "triceps",
    "traps",
    "glutes",
    "quadriceps",
    "hamstrings",
    "adductors",
    "calves",
    "abs",
    "obliques",
    "lower_back",
)
EQUIPMENT = (
    "bodyweight",
    "dumbbell",
    "barbell",
    "cable",
    "machine",
    "resistance_band",
    "bench",
    "pull_up_bar",
    "other",
)
DIFFICULTIES = ("beginner", "intermediate", "advanced")
MEDIA_TYPES = ("image", "animated_webp", "gif", "video", "placeholder")


def quoted_values(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{value}'" for value in values)


def upgrade() -> None:
    op.create_table(
        "exercises",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("slug", sa.String(length=120), nullable=False),
        sa.Column("name_en", sa.String(length=160), nullable=False),
        sa.Column("name_fa", sa.String(length=160), nullable=False),
        sa.Column("body_region", sa.String(length=10), nullable=False),
        sa.Column("primary_muscle", sa.String(length=14), nullable=False),
        sa.Column("difficulty", sa.String(length=12), nullable=False),
        sa.Column("instructions_en", sa.JSON(), nullable=False),
        sa.Column("instructions_fa", sa.JSON(), nullable=False),
        sa.Column("safety_notes_en", sa.JSON(), nullable=False),
        sa.Column("safety_notes_fa", sa.JSON(), nullable=False),
        sa.Column("media_path", sa.String(length=255), nullable=False),
        sa.Column("media_type", sa.String(length=13), nullable=False),
        sa.Column("media_source_url", sa.String(length=500), nullable=True),
        sa.Column("media_license", sa.String(length=120), nullable=True),
        sa.Column("media_attribution", sa.String(length=500), nullable=True),
        sa.Column(
            "is_active",
            sa.Boolean(),
            server_default=sa.true(),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            f"body_region IN ({quoted_values(BODY_REGIONS)})",
            name="ck_exercises_body_region_values",
        ),
        sa.CheckConstraint(
            f"primary_muscle IN ({quoted_values(MUSCLE_GROUPS)})",
            name="ck_exercises_primary_muscle_values",
        ),
        sa.CheckConstraint(
            f"difficulty IN ({quoted_values(DIFFICULTIES)})",
            name="ck_exercises_difficulty_values",
        ),
        sa.CheckConstraint(
            f"media_type IN ({quoted_values(MEDIA_TYPES)})",
            name="ck_exercises_media_type_values",
        ),
        sa.CheckConstraint(
            "slug ~ '^[a-z0-9]+(-[a-z0-9]+)*$'",
            name="ck_exercises_slug_format",
        ),
        sa.CheckConstraint(
            "char_length(btrim(name_en)) BETWEEN 2 AND 160",
            name="ck_exercises_name_en_length",
        ),
        sa.CheckConstraint(
            "char_length(btrim(name_fa)) BETWEEN 2 AND 160",
            name="ck_exercises_name_fa_length",
        ),
        sa.CheckConstraint(
            "json_typeof(instructions_en) = 'array' "
            "AND json_array_length(instructions_en) BETWEEN 3 AND 6",
            name="ck_exercises_instructions_en_steps",
        ),
        sa.CheckConstraint(
            "json_typeof(instructions_fa) = 'array' "
            "AND json_array_length(instructions_fa) BETWEEN 3 AND 6",
            name="ck_exercises_instructions_fa_steps",
        ),
        sa.CheckConstraint(
            "json_typeof(safety_notes_en) = 'array' AND json_array_length(safety_notes_en) >= 1",
            name="ck_exercises_safety_notes_en_items",
        ),
        sa.CheckConstraint(
            "json_typeof(safety_notes_fa) = 'array' AND json_array_length(safety_notes_fa) >= 1",
            name="ck_exercises_safety_notes_fa_items",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug", name="uq_exercises_slug"),
    )
    op.create_index("ix_exercises_body_region", "exercises", ["body_region"])
    op.create_index("ix_exercises_primary_muscle", "exercises", ["primary_muscle"])
    op.create_index("ix_exercises_difficulty", "exercises", ["difficulty"])
    op.create_index("ix_exercises_is_active", "exercises", ["is_active"])

    op.create_table(
        "exercise_secondary_muscles",
        sa.Column("exercise_id", sa.Uuid(), nullable=False),
        sa.Column("muscle", sa.String(length=14), nullable=False),
        sa.CheckConstraint(
            f"muscle IN ({quoted_values(MUSCLE_GROUPS)})",
            name="ck_exercise_secondary_muscles_muscle_values",
        ),
        sa.ForeignKeyConstraint(["exercise_id"], ["exercises.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("exercise_id", "muscle"),
    )
    op.create_index(
        "ix_exercise_secondary_muscles_muscle",
        "exercise_secondary_muscles",
        ["muscle"],
    )

    op.create_table(
        "exercise_equipment",
        sa.Column("exercise_id", sa.Uuid(), nullable=False),
        sa.Column("equipment", sa.String(length=15), nullable=False),
        sa.CheckConstraint(
            f"equipment IN ({quoted_values(EQUIPMENT)})",
            name="ck_exercise_equipment_equipment_values",
        ),
        sa.ForeignKeyConstraint(["exercise_id"], ["exercises.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("exercise_id", "equipment"),
    )
    op.create_index(
        "ix_exercise_equipment_equipment",
        "exercise_equipment",
        ["equipment"],
    )

    op.create_table(
        "exercise_alternatives",
        sa.Column("exercise_id", sa.Uuid(), nullable=False),
        sa.Column("alternative_exercise_id", sa.Uuid(), nullable=False),
        sa.Column("reason_en", sa.String(length=300), nullable=False),
        sa.Column("reason_fa", sa.String(length=300), nullable=False),
        sa.CheckConstraint(
            "exercise_id <> alternative_exercise_id",
            name="ck_exercise_alternatives_distinct_exercises",
        ),
        sa.ForeignKeyConstraint(["exercise_id"], ["exercises.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["alternative_exercise_id"],
            ["exercises.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("exercise_id", "alternative_exercise_id"),
    )
    op.create_index(
        "ix_exercise_alternatives_alternative_id",
        "exercise_alternatives",
        ["alternative_exercise_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_exercise_alternatives_alternative_id",
        table_name="exercise_alternatives",
    )
    op.drop_table("exercise_alternatives")
    op.drop_index("ix_exercise_equipment_equipment", table_name="exercise_equipment")
    op.drop_table("exercise_equipment")
    op.drop_index(
        "ix_exercise_secondary_muscles_muscle",
        table_name="exercise_secondary_muscles",
    )
    op.drop_table("exercise_secondary_muscles")
    op.drop_index("ix_exercises_is_active", table_name="exercises")
    op.drop_index("ix_exercises_difficulty", table_name="exercises")
    op.drop_index("ix_exercises_primary_muscle", table_name="exercises")
    op.drop_index("ix_exercises_body_region", table_name="exercises")
    op.drop_table("exercises")
