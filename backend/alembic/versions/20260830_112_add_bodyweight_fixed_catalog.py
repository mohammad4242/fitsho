"""Expose the fixed bodyweight programs in the admin template catalog.

Revision ID: 20260830_112
Revises: 20260830_111
Create Date: 2026-08-30
"""

from collections.abc import Sequence
from uuid import uuid4

import sqlalchemy as sa
from sqlalchemy.orm import Session

from alembic import op
from app.training_templates.seed_data import SOURCE_NAME, SOURCE_URL
from app.training_templates.service import upgrade_training_program_template_catalog

revision: str = "20260830_112"
down_revision: str | Sequence[str] | None = "20260830_111"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

FIXED_CATEGORY = "bodyweight_fixed"
BODYWEIGHT_SOURCE_NAME = "Fitsho fixed bodyweight templates"
BODYWEIGHT_SOURCE_URL = "https://fitsho.local/bodyweight-templates"

SLOT_METADATA: dict[str, tuple[list[str], str]] = {
    "fedb-drv-squat-squat": (["quadriceps"], "squat"),
    "fedb-0493-incline-push-up": (["chest"], "horizontal_push"),
    "fedb-drv-push-ups-push-up": (["chest"], "horizontal_push"),
    "fedb-0259-close-grip-push-up": (["triceps"], "horizontal_push"),
    "fedb-0499-inverted-row-between-chairs": (["back"], "horizontal_pull"),
    "fedb-0651-shoulder-width-pull-up": (["back"], "vertical_pull"),
    "fedb-2327-reverse-grip-pull-up": (["back"], "vertical_pull"),
    "fedb-2987-close-grip-chin-up": (["back"], "vertical_pull"),
    "fedb-1429-pull-up-wide-grip": (["back"], "vertical_pull"),
    "fedb-0668-rear-decline-bridge": (["glutes"], "hip_extension"),
    "fedb-0464-front-plank": (["abs"], "core_anti_extension"),
    "fedb-0705-side-plank": (["obliques"], "core_anti_lateral_flexion"),
    "fedb-0872-reverse-crunch": (["abs"], "spinal_flexion"),
}

TEMPLATES: dict[
    str,
    tuple[
        str,
        int,
        list[str],
        list[list[tuple[str, int, int | None, int | None, int | None, int | None, int]]],
    ],
] = {
    "bw-first-month-2d-v1": (
        "first_month",
        2,
        ["full_body", "balanced"],
        [
            [
                ("fedb-drv-squat-squat", 2, 10, 15, 4, None, 75),
                ("fedb-0493-incline-push-up", 2, 8, 12, 4, None, 60),
                ("fedb-0499-inverted-row-between-chairs", 2, 6, 10, 4, None, 75),
                ("fedb-0668-rear-decline-bridge", 2, 10, 15, 4, None, 60),
                ("fedb-0464-front-plank", 2, None, None, None, 20, 45),
            ],
            [
                ("fedb-drv-squat-squat", 2, 10, 15, 4, None, 75),
                ("fedb-drv-push-ups-push-up", 2, 6, 10, 4, None, 60),
                ("fedb-0499-inverted-row-between-chairs", 2, 6, 10, 4, None, 75),
                ("fedb-0668-rear-decline-bridge", 2, 10, 15, 4, None, 60),
                ("fedb-0705-side-plank", 2, None, None, None, 20, 45),
            ],
        ],
    ),
    "bw-first-month-3d-v1": (
        "first_month",
        3,
        ["full_body", "balanced"],
        [
            [
                ("fedb-drv-squat-squat", 2, 10, 15, 4, None, 75),
                ("fedb-0493-incline-push-up", 2, 8, 12, 4, None, 60),
                ("fedb-0499-inverted-row-between-chairs", 2, 6, 10, 4, None, 75),
                ("fedb-0668-rear-decline-bridge", 2, 10, 15, 4, None, 60),
                ("fedb-0464-front-plank", 2, None, None, None, 20, 45),
            ],
            [
                ("fedb-drv-squat-squat", 2, 10, 15, 4, None, 75),
                ("fedb-drv-push-ups-push-up", 2, 6, 10, 4, None, 60),
                ("fedb-0499-inverted-row-between-chairs", 2, 6, 10, 4, None, 75),
                ("fedb-0668-rear-decline-bridge", 2, 10, 15, 4, None, 60),
                ("fedb-0872-reverse-crunch", 2, 10, 15, 4, None, 45),
            ],
            [
                ("fedb-drv-squat-squat", 2, 10, 15, 4, None, 75),
                ("fedb-0493-incline-push-up", 2, 8, 12, 4, None, 60),
                ("fedb-0499-inverted-row-between-chairs", 2, 6, 10, 4, None, 75),
                ("fedb-0668-rear-decline-bridge", 2, 10, 15, 4, None, 60),
                ("fedb-0705-side-plank", 2, None, None, None, 20, 45),
            ],
        ],
    ),
    "bw-first-month-4d-v1": (
        "first_month",
        4,
        ["upper_lower", "balanced"],
        [
            [
                ("fedb-0493-incline-push-up", 2, 8, 12, 4, None, 60),
                ("fedb-0499-inverted-row-between-chairs", 2, 6, 10, 4, None, 75),
                ("fedb-0259-close-grip-push-up", 2, 6, 10, 4, None, 60),
                ("fedb-0464-front-plank", 2, None, None, None, 20, 45),
            ],
            [
                ("fedb-drv-squat-squat", 2, 10, 15, 4, None, 75),
                ("fedb-0668-rear-decline-bridge", 2, 10, 15, 4, None, 60),
                ("fedb-0872-reverse-crunch", 2, 10, 15, 4, None, 45),
                ("fedb-0705-side-plank", 2, None, None, None, 20, 45),
            ],
            [
                ("fedb-drv-push-ups-push-up", 2, 6, 10, 4, None, 60),
                ("fedb-0499-inverted-row-between-chairs", 2, 6, 10, 4, None, 75),
                ("fedb-0259-close-grip-push-up", 2, 6, 10, 4, None, 60),
                ("fedb-0464-front-plank", 2, None, None, None, 20, 45),
            ],
            [
                ("fedb-drv-squat-squat", 2, 10, 15, 4, None, 75),
                ("fedb-0668-rear-decline-bridge", 2, 12, 15, 4, None, 60),
                ("fedb-0872-reverse-crunch", 2, 10, 15, 4, None, 45),
                ("fedb-0705-side-plank", 2, None, None, None, 20, 45),
            ],
        ],
    ),
    "bw-beginner-2d-v1": (
        "beginner",
        2,
        ["full_body", "balanced"],
        [
            [
                ("fedb-drv-squat-squat", 3, 10, 15, 3, None, 75),
                ("fedb-drv-push-ups-push-up", 3, 6, 12, 3, None, 75),
                ("fedb-0651-shoulder-width-pull-up", 3, 3, 8, 3, None, 90),
                ("fedb-0668-rear-decline-bridge", 3, 10, 15, 3, None, 75),
                ("fedb-0464-front-plank", 2, None, None, None, 25, 45),
            ],
            [
                ("fedb-drv-squat-squat", 3, 10, 15, 3, None, 75),
                ("fedb-0259-close-grip-push-up", 2, 6, 12, 3, None, 75),
                ("fedb-2327-reverse-grip-pull-up", 3, 3, 8, 3, None, 90),
                ("fedb-0668-rear-decline-bridge", 3, 10, 15, 3, None, 75),
                ("fedb-0705-side-plank", 2, None, None, None, 20, 45),
            ],
        ],
    ),
    "bw-beginner-3d-v1": (
        "beginner",
        3,
        ["full_body", "balanced"],
        [
            [
                ("fedb-drv-squat-squat", 3, 10, 15, 3, None, 75),
                ("fedb-drv-push-ups-push-up", 3, 6, 12, 3, None, 75),
                ("fedb-0651-shoulder-width-pull-up", 3, 3, 8, 3, None, 90),
                ("fedb-0668-rear-decline-bridge", 3, 10, 15, 3, None, 75),
                ("fedb-0464-front-plank", 2, None, None, None, 25, 45),
            ],
            [
                ("fedb-drv-squat-squat", 2, 10, 15, 3, None, 75),
                ("fedb-0493-incline-push-up", 2, 10, 15, 3, None, 60),
                ("fedb-2987-close-grip-chin-up", 2, 3, 8, 3, None, 90),
                ("fedb-0668-rear-decline-bridge", 2, 12, 15, 3, None, 60),
                ("fedb-0872-reverse-crunch", 2, 10, 15, 3, None, 45),
            ],
            [
                ("fedb-drv-squat-squat", 3, 10, 15, 3, None, 75),
                ("fedb-0259-close-grip-push-up", 3, 6, 12, 3, None, 75),
                ("fedb-2327-reverse-grip-pull-up", 3, 3, 8, 3, None, 90),
                ("fedb-0668-rear-decline-bridge", 3, 10, 15, 3, None, 75),
                ("fedb-0705-side-plank", 2, None, None, None, 20, 45),
            ],
        ],
    ),
    "bw-beginner-4d-v1": (
        "beginner",
        4,
        ["upper_lower", "balanced"],
        [
            [
                ("fedb-drv-push-ups-push-up", 3, 6, 12, 3, None, 75),
                ("fedb-0651-shoulder-width-pull-up", 3, 3, 8, 3, None, 90),
                ("fedb-0259-close-grip-push-up", 2, 6, 12, 3, None, 75),
                ("fedb-2987-close-grip-chin-up", 2, 3, 8, 3, None, 90),
                ("fedb-0464-front-plank", 2, None, None, None, 30, 45),
            ],
            [
                ("fedb-drv-squat-squat", 3, 10, 15, 3, None, 75),
                ("fedb-0668-rear-decline-bridge", 3, 10, 15, 3, None, 75),
                ("fedb-0872-reverse-crunch", 2, 10, 15, 3, None, 45),
                ("fedb-0705-side-plank", 2, None, None, None, 20, 45),
            ],
            [
                ("fedb-0493-incline-push-up", 3, 8, 15, 3, None, 75),
                ("fedb-2327-reverse-grip-pull-up", 3, 3, 8, 3, None, 90),
                ("fedb-drv-push-ups-push-up", 2, 6, 12, 3, None, 75),
                ("fedb-1429-pull-up-wide-grip", 2, 3, 6, 3, None, 90),
                ("fedb-0464-front-plank", 2, None, None, None, 30, 45),
            ],
            [
                ("fedb-drv-squat-squat", 3, 10, 15, 3, None, 75),
                ("fedb-0668-rear-decline-bridge", 3, 12, 15, 3, None, 75),
                ("fedb-0872-reverse-crunch", 2, 10, 15, 3, None, 45),
                ("fedb-0705-side-plank", 2, None, None, None, 20, 45),
            ],
        ],
    ),
}


def upgrade() -> None:
    op.add_column(
        "training_program_templates",
        sa.Column("category", sa.String(length=40), server_default="generic", nullable=False),
    )
    op.create_check_constraint(
        "ck_training_program_templates_category_values",
        "training_program_templates",
        "category IN ('generic', 'bodyweight_fixed')",
    )
    op.add_column(
        "training_program_templates",
        sa.Column("engine_eligible", sa.Boolean(), server_default=sa.true(), nullable=False),
    )
    op.create_index(
        "ix_training_program_templates_category",
        "training_program_templates",
        ["category"],
    )
    op.create_index(
        "ix_training_program_templates_engine_eligible",
        "training_program_templates",
        ["engine_eligible"],
    )

    op.add_column(
        "training_program_template_slots",
        sa.Column("prescription_mode", sa.String(length=16), server_default="reps", nullable=False),
    )
    op.add_column(
        "training_program_template_slots", sa.Column("duration_min_seconds", sa.Integer())
    )
    op.add_column(
        "training_program_template_slots", sa.Column("duration_max_seconds", sa.Integer())
    )
    op.drop_constraint(
        "ck_training_program_template_slots_reps", "training_program_template_slots", type_="check"
    )
    op.drop_constraint(
        "ck_training_program_template_slots_rir", "training_program_template_slots", type_="check"
    )
    op.alter_column("training_program_template_slots", "rep_min", nullable=True)
    op.alter_column("training_program_template_slots", "rep_max", nullable=True)
    op.alter_column("training_program_template_slots", "target_rir", nullable=True)
    op.create_check_constraint(
        "ck_training_program_template_slots_prescription_mode_values",
        "training_program_template_slots",
        "prescription_mode IN ('reps', 'duration')",
    )
    op.create_check_constraint(
        "ck_training_program_template_slots_prescription",
        "training_program_template_slots",
        "((prescription_mode = 'reps' AND rep_min BETWEEN 1 AND rep_max "
        "AND target_rir BETWEEN 0 AND 6 AND duration_min_seconds IS NULL "
        "AND duration_max_seconds IS NULL) OR "
        "(prescription_mode = 'duration' AND rep_min IS NULL AND rep_max IS NULL "
        "AND target_rir IS NULL AND duration_min_seconds BETWEEN 1 AND duration_max_seconds "
        "AND duration_max_seconds <= 3600))",
    )

    bind = op.get_bind()
    templates = sa.table(
        "training_program_templates",
        sa.column("id", sa.Uuid()),
        sa.column("slug", sa.String()),
        sa.column("name_en", sa.String()),
        sa.column("name_fa", sa.String()),
        sa.column("description_en", sa.String()),
        sa.column("description_fa", sa.String()),
        sa.column("days_per_week", sa.Integer()),
        sa.column("supported_levels", sa.JSON()),
        sa.column("focus_tags", sa.JSON()),
        sa.column("intensity_methods", sa.JSON()),
        sa.column("programming_rationale", sa.JSON()),
        sa.column("source_name", sa.String()),
        sa.column("source_url", sa.String()),
        sa.column("is_active", sa.Boolean()),
        sa.column("category", sa.String()),
        sa.column("engine_eligible", sa.Boolean()),
    )
    days = sa.table(
        "training_program_template_days",
        sa.column("id", sa.Uuid()),
        sa.column("template_id", sa.Uuid()),
        sa.column("day_number", sa.Integer()),
        sa.column("title_en", sa.String()),
        sa.column("title_fa", sa.String()),
        sa.column("structure_focus", sa.String()),
        sa.column("direct_target_muscles", sa.JSON()),
    )
    slots = sa.table(
        "training_program_template_slots",
        sa.column("id", sa.Uuid()),
        sa.column("template_day_id", sa.Uuid()),
        sa.column("slot_order", sa.Integer()),
        sa.column("exercise_id", sa.Uuid()),
        sa.column("exercise_slug_hint", sa.String()),
        sa.column("placeholder_name_en", sa.String()),
        sa.column("placeholder_name_fa", sa.String()),
        sa.column("target_muscles", sa.JSON()),
        sa.column("movement_pattern", sa.String()),
        sa.column("intensity_method", sa.String()),
        sa.column("adaptation_priority", sa.String()),
        sa.column("superset_group", sa.String()),
        sa.column("sets", sa.Integer()),
        sa.column("prescription_mode", sa.String()),
        sa.column("rep_min", sa.Integer()),
        sa.column("rep_max", sa.Integer()),
        sa.column("target_rir", sa.Integer()),
        sa.column("duration_min_seconds", sa.Integer()),
        sa.column("duration_max_seconds", sa.Integer()),
        sa.column("rest_seconds", sa.Integer()),
    )
    exercises = sa.table(
        "exercises",
        sa.column("id", sa.Uuid()),
        sa.column("slug", sa.String()),
    )
    exercise_ids = dict(bind.execute(sa.select(exercises.c.slug, exercises.c.id)).all())

    for slug, (level, days_per_week, focus_tags, template_days) in TEMPLATES.items():
        template_id = bind.scalar(sa.select(templates.c.id).where(templates.c.slug == slug))
        if template_id is not None:
            continue
        template_id = uuid4()
        bind.execute(
            templates.insert().values(
                id=template_id,
                slug=slug,
                name_en=("First Month" if level == "first_month" else "Beginner")
                + f" Bodyweight {days_per_week} Day",
                name_fa=("ماه اول" if level == "first_month" else "مبتدی")
                + f" — {days_per_week} روز وزن بدن",
                description_en="Fixed bodyweight-only template for the Fitsho admin catalog.",
                description_fa="قالب ثابت تمرین فقط با وزن بدن برای کاتالوگ ادمین فیتشو.",
                days_per_week=days_per_week,
                supported_levels=[level],
                focus_tags=focus_tags,
                intensity_methods=["standard"],
                programming_rationale=[
                    {
                        "title_en": "Fixed bodyweight route",
                        "title_fa": "مسیر ثابت وزن بدن",
                        "detail_en": "Used by the dedicated bodyweight route.",
                        "detail_fa": "توسط مسیر اختصاصی وزن بدن استفاده می‌شود.",
                    }
                ]
                * 5,
                source_name=BODYWEIGHT_SOURCE_NAME,
                source_url=BODYWEIGHT_SOURCE_URL,
                is_active=True,
                category=FIXED_CATEGORY,
                engine_eligible=False,
            )
        )
        for day_number, day_slots in enumerate(template_days, start=1):
            day_id = uuid4()
            focus = (
                "upper"
                if days_per_week == 4 and day_number % 2 == 1
                else "lower"
                if days_per_week == 4
                else "full_body"
            )
            day_letter = (
                chr(64 + (day_number + 1) // 2) if days_per_week == 4 else chr(64 + day_number)
            )
            bind.execute(
                days.insert().values(
                    id=day_id,
                    template_id=template_id,
                    day_number=day_number,
                    title_en=(
                        "Upper"
                        if focus == "upper"
                        else "Lower"
                        if focus == "lower"
                        else "Full Body"
                    )
                    + f" {day_letter}",
                    title_fa=(
                        "بالاتنه"
                        if focus == "upper"
                        else "پایین تنه"
                        if focus == "lower"
                        else "تمام بدن"
                    )
                    + f" {day_letter}",
                    structure_focus=focus,
                    direct_target_muscles=["chest", "back", "quadriceps", "glutes", "abs"],
                )
            )
            slot_rows = []
            for slot_order, (
                exercise_slug,
                sets,
                rep_min,
                rep_max,
                rir,
                duration_min,
                rest,
            ) in enumerate(day_slots, start=1):
                target_muscles, movement_pattern = SLOT_METADATA[exercise_slug]
                is_duration = duration_min is not None
                slot_rows.append(
                    {
                        "id": uuid4(),
                        "template_day_id": day_id,
                        "slot_order": slot_order,
                        "exercise_id": exercise_ids.get(exercise_slug),
                        "exercise_slug_hint": exercise_slug,
                        "placeholder_name_en": None,
                        "placeholder_name_fa": None,
                        "target_muscles": target_muscles,
                        "movement_pattern": movement_pattern,
                        "intensity_method": "standard",
                        "adaptation_priority": "accessory",
                        "superset_group": None,
                        "sets": sets,
                        "prescription_mode": "duration" if is_duration else "reps",
                        "rep_min": None if is_duration else rep_min,
                        "rep_max": None if is_duration else rep_max,
                        "target_rir": None if is_duration else rir,
                        "duration_min_seconds": duration_min,
                        "duration_max_seconds": (
                            40
                            if is_duration
                            and level == "beginner"
                            and exercise_slug == "fedb-0464-front-plank"
                            else duration_min + 10
                            if is_duration
                            else None
                        ),
                        "rest_seconds": rest,
                    }
                )
            bind.execute(slots.insert(), slot_rows)

    # Migration 110 cannot call the current catalog service before these columns exist.
    # Finish that upgrade here when an existing generic catalog is present.
    generic_catalog_count = bind.scalar(
        sa.select(sa.func.count())
        .select_from(templates)
        .where(
            templates.c.source_name == SOURCE_NAME,
            templates.c.source_url == SOURCE_URL,
        )
    )
    if generic_catalog_count:
        session = Session(bind=bind, join_transaction_mode="create_savepoint")
        try:
            upgrade_training_program_template_catalog(session)
        finally:
            session.close()


def downgrade() -> None:
    bind = op.get_bind()
    templates = sa.table(
        "training_program_templates",
        sa.column("id", sa.Uuid()),
        sa.column("category", sa.String()),
    )
    ids = list(
        bind.scalars(sa.select(templates.c.id).where(templates.c.category == FIXED_CATEGORY))
    )
    if ids:
        bind.execute(templates.delete().where(templates.c.id.in_(ids)))
    op.drop_constraint(
        "ck_training_program_template_slots_prescription",
        "training_program_template_slots",
        type_="check",
    )
    op.drop_constraint(
        "ck_training_program_template_slots_prescription_mode_values",
        "training_program_template_slots",
        type_="check",
    )
    op.drop_column("training_program_template_slots", "duration_max_seconds")
    op.drop_column("training_program_template_slots", "duration_min_seconds")
    op.drop_column("training_program_template_slots", "prescription_mode")
    op.alter_column("training_program_template_slots", "rep_min", nullable=False)
    op.alter_column("training_program_template_slots", "rep_max", nullable=False)
    op.alter_column("training_program_template_slots", "target_rir", nullable=False)
    op.create_check_constraint(
        "ck_training_program_template_slots_reps",
        "training_program_template_slots",
        "rep_min BETWEEN 1 AND rep_max",
    )
    op.create_check_constraint(
        "ck_training_program_template_slots_rir",
        "training_program_template_slots",
        "target_rir BETWEEN 0 AND 6",
    )
    op.drop_index(
        "ix_training_program_templates_engine_eligible", table_name="training_program_templates"
    )
    op.drop_index("ix_training_program_templates_category", table_name="training_program_templates")
    op.drop_constraint(
        "ck_training_program_templates_category_values",
        "training_program_templates",
        type_="check",
    )
    op.drop_column("training_program_templates", "engine_eligible")
    op.drop_column("training_program_templates", "category")
