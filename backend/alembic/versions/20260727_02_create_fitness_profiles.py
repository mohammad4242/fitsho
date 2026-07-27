from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision = "20260727_02"
down_revision = "20260724_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "user_profiles",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("display_name", sa.String(length=80), nullable=False),
        sa.Column("birth_date", sa.Date(), nullable=False),
        sa.Column("sex", sa.String(length=17), nullable=False),
        sa.Column("height_cm", sa.SmallInteger(), nullable=False),
        sa.Column("fitness_goal", sa.String(length=15), nullable=False),
        sa.Column("experience_level", sa.String(length=12), nullable=False),
        sa.Column("training_days_per_week", sa.SmallInteger(), nullable=False),
        sa.Column("training_location", sa.String(length=4), nullable=False),
        sa.Column("home_training_setup", sa.String(length=19), nullable=True),
        sa.Column("session_duration_minutes", sa.SmallInteger(), nullable=False),
        sa.Column("physical_limitations", sa.Text(), nullable=True),
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
            "char_length(btrim(display_name)) BETWEEN 2 AND 80",
            name="ck_user_profiles_display_name_length",
        ),
        sa.CheckConstraint(
            "height_cm BETWEEN 100 AND 250", name="ck_user_profiles_height_cm_range"
        ),
        sa.CheckConstraint(
            "training_days_per_week BETWEEN 1 AND 7",
            name="ck_user_profiles_training_days_range",
        ),
        sa.CheckConstraint(
            "physical_limitations IS NULL OR char_length(physical_limitations) <= 1000",
            name="ck_user_profiles_limitations_length",
        ),
        sa.CheckConstraint(
            "sex IN ('female', 'male', 'other', 'prefer_not_to_say')",
            name="ck_user_profiles_sex_values",
        ),
        sa.CheckConstraint(
            "fitness_goal IN ('lose_weight', 'build_muscle', 'improve_fitness', 'maintain_weight')",
            name="ck_user_profiles_fitness_goal_values",
        ),
        sa.CheckConstraint(
            "experience_level IN ('beginner', 'intermediate', 'advanced')",
            name="ck_user_profiles_experience_level_values",
        ),
        sa.CheckConstraint(
            "training_location IN ('home', 'gym')",
            name="ck_user_profiles_training_location_values",
        ),
        sa.CheckConstraint(
            "home_training_setup IS NULL OR "
            "home_training_setup IN ('bodyweight_only', 'dumbbells_available')",
            name="ck_user_profiles_home_training_setup_values",
        ),
        sa.CheckConstraint(
            "session_duration_minutes IN (30, 45, 60, 75, 90)",
            name="ck_user_profiles_session_duration_values",
        ),
        sa.CheckConstraint(
            "(training_location = 'home' AND home_training_setup IS NOT NULL) OR "
            "(training_location = 'gym' AND home_training_setup IS NULL)",
            name="ck_user_profiles_training_setup_consistency",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id"),
    )
    op.create_table(
        "body_measurements",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("weight_kg", sa.Numeric(precision=5, scale=2), nullable=False),
        sa.Column(
            "measured_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "weight_kg BETWEEN 20 AND 500", name="ck_body_measurements_weight_kg_range"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_body_measurements_user_id_measured_at",
        "body_measurements",
        ["user_id", "measured_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_body_measurements_user_id_measured_at", table_name="body_measurements")
    op.drop_table("body_measurements")
    op.drop_table("user_profiles")
