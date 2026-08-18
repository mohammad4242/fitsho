"""persist structured exercise programming metadata"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260819_100"
down_revision: str | Sequence[str] | None = "20260818_99"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


BODY_POSITION_VALUES = ("standing", "seated", "lying", "supported")
STABILITY_DEMAND_VALUES = ("low", "moderate", "high")
SKILL_DEMAND_VALUES = ("low", "moderate", "high")
IMPACT_LEVEL_VALUES = ("low", "moderate", "high")
AXIAL_LOADING_LEVEL_VALUES = ("none", "low", "moderate", "high")
LATERALITY_VALUES = ("bilateral", "unilateral", "not_applicable")


def _enum_values(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{value}'" for value in values)


def upgrade() -> None:
    op.add_column(
        "exercises",
        sa.Column(
            "body_position",
            sa.Enum(*BODY_POSITION_VALUES, native_enum=False, create_constraint=False),
            nullable=True,
        ),
    )
    op.add_column(
        "exercises",
        sa.Column(
            "stability_demand",
            sa.Enum(*STABILITY_DEMAND_VALUES, native_enum=False, create_constraint=False),
            nullable=True,
        ),
    )
    op.add_column(
        "exercises",
        sa.Column(
            "skill_demand",
            sa.Enum(*SKILL_DEMAND_VALUES, native_enum=False, create_constraint=False),
            nullable=True,
        ),
    )
    op.add_column(
        "exercises",
        sa.Column(
            "impact_level",
            sa.Enum(*IMPACT_LEVEL_VALUES, native_enum=False, create_constraint=False),
            nullable=True,
        ),
    )
    op.add_column(
        "exercises",
        sa.Column(
            "axial_loading_level",
            sa.Enum(*AXIAL_LOADING_LEVEL_VALUES, native_enum=False, create_constraint=False),
            nullable=True,
        ),
    )
    op.add_column("exercises", sa.Column("fatigue_cost", sa.SmallInteger(), nullable=True))
    op.add_column("exercises", sa.Column("setup_cost", sa.SmallInteger(), nullable=True))
    op.add_column(
        "exercises",
        sa.Column(
            "laterality",
            sa.Enum(*LATERALITY_VALUES, native_enum=False, create_constraint=False),
            nullable=True,
        ),
    )
    op.add_column(
        "exercises",
        sa.Column("substitution_group", sa.String(length=120), nullable=True),
    )
    op.add_column(
        "exercises",
        sa.Column("range_of_motion_profile", sa.JSON(), nullable=True),
    )

    op.create_index(
        "ix_exercises_substitution_group",
        "exercises",
        ["substitution_group"],
    )
    op.create_check_constraint(
        "ck_exercises_body_position_values",
        "exercises",
        f"body_position IS NULL OR body_position IN ({_enum_values(BODY_POSITION_VALUES)})",
    )
    op.create_check_constraint(
        "ck_exercises_stability_demand_values",
        "exercises",
        "stability_demand IS NULL OR stability_demand IN "
        f"({_enum_values(STABILITY_DEMAND_VALUES)})",
    )
    op.create_check_constraint(
        "ck_exercises_skill_demand_values",
        "exercises",
        f"skill_demand IS NULL OR skill_demand IN ({_enum_values(SKILL_DEMAND_VALUES)})",
    )
    op.create_check_constraint(
        "ck_exercises_impact_level_values",
        "exercises",
        f"impact_level IS NULL OR impact_level IN ({_enum_values(IMPACT_LEVEL_VALUES)})",
    )
    op.create_check_constraint(
        "ck_exercises_axial_loading_level_values",
        "exercises",
        "axial_loading_level IS NULL OR axial_loading_level IN "
        f"({_enum_values(AXIAL_LOADING_LEVEL_VALUES)})",
    )
    op.create_check_constraint(
        "ck_exercises_laterality_values",
        "exercises",
        f"laterality IS NULL OR laterality IN ({_enum_values(LATERALITY_VALUES)})",
    )
    op.create_check_constraint(
        "ck_exercises_fatigue_cost_range",
        "exercises",
        "fatigue_cost IS NULL OR fatigue_cost BETWEEN 1 AND 5",
    )
    op.create_check_constraint(
        "ck_exercises_setup_cost_range",
        "exercises",
        "setup_cost IS NULL OR setup_cost BETWEEN 1 AND 5",
    )
    op.create_check_constraint(
        "ck_exercises_range_of_motion_profile_items",
        "exercises",
        "range_of_motion_profile IS NULL OR json_typeof(range_of_motion_profile) = 'array'",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_exercises_range_of_motion_profile_items",
        "exercises",
        type_="check",
    )
    op.drop_constraint("ck_exercises_setup_cost_range", "exercises", type_="check")
    op.drop_constraint("ck_exercises_fatigue_cost_range", "exercises", type_="check")
    op.drop_constraint("ck_exercises_laterality_values", "exercises", type_="check")
    op.drop_constraint("ck_exercises_axial_loading_level_values", "exercises", type_="check")
    op.drop_constraint("ck_exercises_impact_level_values", "exercises", type_="check")
    op.drop_constraint("ck_exercises_skill_demand_values", "exercises", type_="check")
    op.drop_constraint("ck_exercises_stability_demand_values", "exercises", type_="check")
    op.drop_constraint("ck_exercises_body_position_values", "exercises", type_="check")
    op.drop_index("ix_exercises_substitution_group", table_name="exercises")
    op.drop_column("exercises", "range_of_motion_profile")
    op.drop_column("exercises", "substitution_group")
    op.drop_column("exercises", "laterality")
    op.drop_column("exercises", "setup_cost")
    op.drop_column("exercises", "fatigue_cost")
    op.drop_column("exercises", "axial_loading_level")
    op.drop_column("exercises", "impact_level")
    op.drop_column("exercises", "skill_demand")
    op.drop_column("exercises", "stability_demand")
    op.drop_column("exercises", "body_position")
