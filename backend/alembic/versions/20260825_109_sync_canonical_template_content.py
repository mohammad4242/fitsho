"""Sync consolidated templates from the approved canonical catalog.

Revision ID: 20260825_109
Revises: 20260825_108
Create Date: 2026-08-25
"""

from collections.abc import Sequence
from uuid import UUID, uuid4

import sqlalchemy as sa

from alembic import op
from app.training_templates.seed_data import (
    SOURCE_NAME,
    SOURCE_URL,
    TRAINING_PROGRAM_TEMPLATE_SEEDS,
    TemplateSlotSeed,
    TrainingProgramTemplateSeed,
)

revision: str = "20260825_109"
down_revision: str | Sequence[str] | None = "20260825_108"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    templates = _templates_table()
    days = _days_table()
    slots = _slots_table()
    exercises = _exercises_table()

    managed_ids = list(
        bind.scalars(
            sa.select(templates.c.id).where(
                templates.c.source_name == SOURCE_NAME,
                templates.c.source_url == SOURCE_URL,
            )
        )
    )
    if not managed_ids:
        return

    canonical_slugs = tuple(seed.slug for seed in TRAINING_PROGRAM_TEMPLATE_SEEDS)
    bind.execute(
        templates.delete().where(
            templates.c.source_name == SOURCE_NAME,
            templates.c.source_url == SOURCE_URL,
            templates.c.slug.not_in(canonical_slugs),
        )
    )

    exercise_ids_by_slug = dict(
        bind.execute(
            sa.select(exercises.c.slug, exercises.c.id).where(
                exercises.c.content_type == "exercise",
                exercises.c.is_active.is_(True),
                exercises.c.is_programmable.is_(True),
                sa.or_(
                    exercises.c.source.is_(None),
                    exercises.c.source != "fitsho_training_template",
                ),
            )
        ).all()
    )

    for seed in TRAINING_PROGRAM_TEMPLATE_SEEDS:
        template_id = bind.scalar(sa.select(templates.c.id).where(templates.c.slug == seed.slug))
        if template_id is None:
            template_id = uuid4()
            bind.execute(
                templates.insert().values(
                    id=template_id,
                    slug=seed.slug,
                    **_template_values(seed),
                )
            )
        else:
            bind.execute(
                templates.update()
                .where(templates.c.id == template_id)
                .values(**_template_values(seed))
            )

        bind.execute(days.delete().where(days.c.template_id == template_id))
        for day_number, day_seed in enumerate(seed.days, start=1):
            day_id = uuid4()
            bind.execute(
                days.insert().values(
                    id=day_id,
                    template_id=template_id,
                    day_number=day_number,
                    title_en=day_seed.title_en,
                    title_fa=day_seed.title_fa,
                    structure_focus=day_seed.structure_focus,
                    direct_target_muscles=[
                        muscle.value for muscle in day_seed.direct_target_muscles
                    ],
                )
            )
            bind.execute(
                slots.insert(),
                [
                    _slot_values(
                        day_id=day_id,
                        slot_order=slot_order,
                        slot_seed=slot_seed,
                        exercise_ids_by_slug=exercise_ids_by_slug,
                    )
                    for slot_order, slot_seed in enumerate(day_seed.slots, start=1)
                ],
            )

    final_count = bind.scalar(
        sa.select(sa.func.count())
        .select_from(templates)
        .where(
            templates.c.source_name == SOURCE_NAME,
            templates.c.source_url == SOURCE_URL,
        )
    )
    if final_count != len(TRAINING_PROGRAM_TEMPLATE_SEEDS):
        raise RuntimeError("Canonical training-template migration did not produce 17 rows")


def downgrade() -> None:
    # The approved shared catalog cannot be mapped back to level-specific prescriptions.
    pass


def _template_values(seed: TrainingProgramTemplateSeed) -> dict[str, object]:
    return {
        "name_en": seed.name_en,
        "name_fa": seed.name_fa,
        "description_en": seed.description_en,
        "description_fa": seed.description_fa,
        "days_per_week": seed.days_per_week,
        "supported_levels": [level.value for level in seed.supported_levels],
        "fitness_goal": seed.fitness_goal.value,
        "focus_tags": [tag.value for tag in seed.focus_tags],
        "intensity_methods": [method.value for method in seed.intensity_methods],
        "programming_rationale": [
            {
                "title_en": rationale.title_en,
                "title_fa": rationale.title_fa,
                "detail_en": rationale.detail_en,
                "detail_fa": rationale.detail_fa,
            }
            for rationale in seed.programming_rationale
        ],
        "source_name": SOURCE_NAME,
        "source_url": SOURCE_URL,
        "is_active": seed.is_active,
    }


def _slot_values(
    *,
    day_id: UUID,
    slot_order: int,
    slot_seed: TemplateSlotSeed,
    exercise_ids_by_slug: dict[str, UUID],
) -> dict[str, object]:
    exercise_id = next(
        (
            exercise_ids_by_slug[candidate]
            for candidate in slot_seed.catalog_slug_hints
            if candidate in exercise_ids_by_slug
        ),
        None,
    )
    if exercise_id is None:
        raise RuntimeError(
            "Missing active programmable exercise for canonical template slot: "
            + ", ".join(slot_seed.catalog_slug_hints)
        )
    return {
        "id": uuid4(),
        "template_day_id": day_id,
        "slot_order": slot_order,
        "exercise_id": exercise_id,
        "exercise_slug_hint": slot_seed.exercise_slug_hint,
        "placeholder_name_en": slot_seed.placeholder_name_en,
        "placeholder_name_fa": slot_seed.placeholder_name_fa,
        "target_muscles": [muscle.value for muscle in slot_seed.target_muscles],
        "movement_pattern": slot_seed.movement_pattern.value,
        "intensity_method": slot_seed.intensity_method.value,
        "adaptation_priority": slot_seed.adaptation_priority.value,
        "superset_group": slot_seed.superset_group,
        "sets": slot_seed.sets,
        "rep_min": slot_seed.rep_min,
        "rep_max": slot_seed.rep_max,
        "target_rir": slot_seed.target_rir,
        "rest_seconds": slot_seed.rest_seconds,
    }


def _templates_table() -> sa.TableClause:
    return sa.table(
        "training_program_templates",
        sa.column("id", sa.Uuid()),
        sa.column("slug", sa.String()),
        sa.column("name_en", sa.String()),
        sa.column("name_fa", sa.String()),
        sa.column("description_en", sa.String()),
        sa.column("description_fa", sa.String()),
        sa.column("days_per_week", sa.Integer()),
        sa.column("supported_levels", sa.JSON()),
        sa.column("fitness_goal", sa.String()),
        sa.column("focus_tags", sa.JSON()),
        sa.column("intensity_methods", sa.JSON()),
        sa.column("programming_rationale", sa.JSON()),
        sa.column("source_name", sa.String()),
        sa.column("source_url", sa.String()),
        sa.column("is_active", sa.Boolean()),
    )


def _days_table() -> sa.TableClause:
    return sa.table(
        "training_program_template_days",
        sa.column("id", sa.Uuid()),
        sa.column("template_id", sa.Uuid()),
        sa.column("day_number", sa.Integer()),
        sa.column("title_en", sa.String()),
        sa.column("title_fa", sa.String()),
        sa.column("structure_focus", sa.String()),
        sa.column("direct_target_muscles", sa.JSON()),
    )


def _slots_table() -> sa.TableClause:
    return sa.table(
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
        sa.column("rep_min", sa.Integer()),
        sa.column("rep_max", sa.Integer()),
        sa.column("target_rir", sa.Integer()),
        sa.column("rest_seconds", sa.Integer()),
    )


def _exercises_table() -> sa.TableClause:
    return sa.table(
        "exercises",
        sa.column("id", sa.Uuid()),
        sa.column("slug", sa.String()),
        sa.column("content_type", sa.String()),
        sa.column("source", sa.String()),
        sa.column("is_active", sa.Boolean()),
        sa.column("is_programmable", sa.Boolean()),
    )
