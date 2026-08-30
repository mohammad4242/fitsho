"""Make active canonical template sessions muscle-coherent.

Revision ID: 20260830_110
Revises: 98e4be28c62d
Create Date: 2026-08-30
"""

from collections.abc import Sequence
from uuid import uuid4

import sqlalchemy as sa

from alembic import op

revision: str = "20260830_110"
down_revision: str | Sequence[str] | None = "98e4be28c62d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


DAY_UPDATES: dict[tuple[str, int], tuple[list[str], str | None]] = {
    ("p21-4-day-3-lower-1-upper-beginner", 3): (
        ["hamstrings", "glutes", "calves"],
        None,
    ),
    ("p21-4-day-3-lower-1-upper-beginner", 4): (
        ["quadriceps", "glutes", "calves"],
        "lower",
    ),
    ("p22-4-day-3-lower-1-upper-intermediate", 3): (
        ["hamstrings", "glutes", "calves"],
        None,
    ),
    ("p22-4-day-3-lower-1-upper-intermediate", 4): (
        ["quadriceps", "glutes", "calves"],
        "lower",
    ),
    ("p23-4-day-3-lower-1-upper-advanced", 3): (
        ["hamstrings", "glutes", "calves"],
        None,
    ),
    ("p23-4-day-3-lower-1-upper-advanced", 4): (
        ["quadriceps", "glutes", "calves"],
        "lower",
    ),
    ("p24-4-day-push-pull-quads-posterior-intermediate", 4): (
        ["hamstrings", "glutes", "calves"],
        None,
    ),
    ("p25-4-day-push-pull-quads-posterior-advanced", 4): (
        ["hamstrings", "glutes", "calves"],
        None,
    ),
    ("p50-4-day-iranmuscle-intermediate", 4): (
        ["shoulders", "hamstrings"],
        "shoulders",
    ),
    ("p30-5-day-upper-priority-iranian-intermediate", 1): (["chest", "triceps"], None),
    ("p30-5-day-upper-priority-iranian-intermediate", 2): (
        ["shoulders", "biceps"],
        None,
    ),
    ("p30-5-day-upper-priority-iranian-intermediate", 4): (["chest", "biceps"], None),
    ("p30-5-day-upper-priority-iranian-intermediate", 5): (["back"], None),
    ("p31-5-day-upper-priority-iranian-advanced", 1): (["chest", "triceps"], None),
    ("p31-5-day-upper-priority-iranian-advanced", 2): (["shoulders", "biceps"], None),
    ("p31-5-day-upper-priority-iranian-advanced", 4): (["chest", "biceps"], None),
    ("p31-5-day-upper-priority-iranian-advanced", 5): (["back"], None),
    ("p34-5-day-fst7-arms-priority-intermediate", 1): (["chest", "biceps"], None),
    ("p34-5-day-fst7-arms-priority-intermediate", 2): (["back", "triceps"], None),
    ("p34-5-day-fst7-arms-priority-intermediate", 4): (
        ["shoulders", "traps", "calves"],
        None,
    ),
    ("p35-5-day-fst7-arms-priority-advanced", 1): (["chest", "biceps"], None),
    ("p35-5-day-fst7-arms-priority-advanced", 2): (["back", "triceps"], None),
    ("p35-5-day-fst7-arms-priority-advanced", 4): (
        ["shoulders", "traps", "calves"],
        None,
    ),
    ("p36-5-day-professional-compound-intermediate", 1): (["chest", "triceps"], None),
    ("p36-5-day-professional-compound-intermediate", 3): (["back", "biceps"], None),
    ("p37-5-day-professional-compound-advanced", 1): (["chest", "triceps"], None),
    ("p37-5-day-professional-compound-advanced", 3): (["back", "biceps"], None),
}

OLD_DAY_VALUES: dict[tuple[str, int], tuple[list[str], str | None]] = {
    ("p21-4-day-3-lower-1-upper-beginner", 3): (["hamstrings", "glutes"], None),
    ("p21-4-day-3-lower-1-upper-beginner", 4): (
        ["quadriceps", "glutes"],
        "quadriceps_calves",
    ),
    ("p22-4-day-3-lower-1-upper-intermediate", 3): (["hamstrings", "glutes"], None),
    ("p22-4-day-3-lower-1-upper-intermediate", 4): (
        ["quadriceps", "glutes"],
        "quadriceps_calves",
    ),
    ("p23-4-day-3-lower-1-upper-advanced", 3): (["hamstrings", "glutes"], None),
    ("p23-4-day-3-lower-1-upper-advanced", 4): (
        ["quadriceps", "glutes"],
        "quadriceps_calves",
    ),
    ("p24-4-day-push-pull-quads-posterior-intermediate", 4): (
        ["hamstrings", "glutes"],
        None,
    ),
    ("p25-4-day-push-pull-quads-posterior-advanced", 4): (
        ["hamstrings", "glutes"],
        None,
    ),
    ("p50-4-day-iranmuscle-intermediate", 4): (["shoulders", "hamstrings"], "shoulders"),
}

for _slug in (
    "p30-5-day-upper-priority-iranian-intermediate",
    "p31-5-day-upper-priority-iranian-advanced",
):
    for _day_number in (1, 2, 4, 5):
        OLD_DAY_VALUES[(_slug, _day_number)] = (
            ["chest", "back", "shoulders", "biceps", "triceps"],
            None,
        )
for _slug in (
    "p34-5-day-fst7-arms-priority-intermediate",
    "p35-5-day-fst7-arms-priority-advanced",
):
    OLD_DAY_VALUES[(_slug, 1)] = (
        ["chest", "back", "shoulders", "biceps", "triceps"],
        None,
    )
    OLD_DAY_VALUES[(_slug, 2)] = OLD_DAY_VALUES[(_slug, 1)]
    OLD_DAY_VALUES[(_slug, 4)] = (["shoulders", "traps"], None)
for _slug in (
    "p36-5-day-professional-compound-intermediate",
    "p37-5-day-professional-compound-advanced",
):
    for _day_number in (1, 3):
        OLD_DAY_VALUES[(_slug, _day_number)] = (
            ["chest", "back", "shoulders", "biceps", "triceps"],
            None,
        )


REMOVED_SLOTS = (
    (
        "p24-4-day-push-pull-quads-posterior-intermediate",
        3,
        4,
        "fedb-0599-lever-seated-leg-curl",
        ["hamstrings"],
        "knee_flexion",
        90,
    ),
    (
        "p24-4-day-push-pull-quads-posterior-intermediate",
        4,
        4,
        "fedb-0336-dumbbell-lunge",
        ["quadriceps", "glutes"],
        "lunge",
        90,
    ),
    (
        "p25-4-day-push-pull-quads-posterior-advanced",
        3,
        4,
        "fedb-0599-lever-seated-leg-curl",
        ["hamstrings"],
        "knee_flexion",
        120,
    ),
    (
        "p25-4-day-push-pull-quads-posterior-advanced",
        4,
        4,
        "fedb-0336-dumbbell-lunge",
        ["quadriceps", "glutes"],
        "lunge",
        120,
    ),
    (
        "p38-6-day-ppl-ab-intermediate",
        2,
        3,
        "fedb-0602-lever-seated-reverse-fly",
        ["shoulders"],
        "horizontal_pull",
        60,
    ),
    (
        "p39-6-day-ppl-ab-advanced",
        2,
        3,
        "fedb-0602-lever-seated-reverse-fly",
        ["shoulders"],
        "horizontal_pull",
        75,
    ),
    (
        "p42-6-day-fitclub-hybrid-intermediate",
        6,
        4,
        "fedb-0336-dumbbell-lunge",
        ["quadriceps", "glutes"],
        "lunge",
        120,
    ),
    (
        "p43-6-day-fitclub-hybrid-advanced",
        6,
        4,
        "fedb-0336-dumbbell-lunge",
        ["quadriceps", "glutes"],
        "lunge",
        120,
    ),
)


def upgrade() -> None:
    bind = op.get_bind()
    templates = _templates()
    days = _days()
    slots = _slots()
    for (slug, day_number), (muscles, structure_focus) in DAY_UPDATES.items():
        values: dict[str, object] = {"direct_target_muscles": muscles}
        if structure_focus is not None:
            values["structure_focus"] = structure_focus
        bind.execute(
            days.update()
            .where(
                days.c.template_id
                == sa.select(templates.c.id).where(templates.c.slug == slug).scalar_subquery(),
                days.c.day_number == day_number,
            )
            .values(**values)
        )
    for slug, day_number, slot_order, *_rest in REMOVED_SLOTS:
        day_id = _day_id(bind, slug, day_number)
        if day_id is None:
            continue
        bind.execute(
            slots.delete().where(
                slots.c.template_day_id == day_id,
                slots.c.slot_order == slot_order,
            )
        )
        _renumber_slots(bind, slots, day_id)
    p50_day_id = _day_id(bind, "p50-4-day-iranmuscle-intermediate", 4)
    if p50_day_id is not None:
        bind.execute(
            slots.update()
            .where(slots.c.template_day_id == p50_day_id, slots.c.slot_order == 4)
            .values(target_muscles=["hamstrings"])
        )


def downgrade() -> None:
    bind = op.get_bind()
    templates = _templates()
    days = _days()
    slots = _slots()
    for (slug, day_number), (muscles, structure_focus) in OLD_DAY_VALUES.items():
        values: dict[str, object] = {"direct_target_muscles": muscles}
        if structure_focus is not None:
            values["structure_focus"] = structure_focus
        bind.execute(
            days.update()
            .where(
                days.c.template_id
                == sa.select(templates.c.id).where(templates.c.slug == slug).scalar_subquery(),
                days.c.day_number == day_number,
            )
            .values(**values)
        )
    exercises = sa.table("exercises", sa.column("id", sa.Uuid()), sa.column("slug", sa.String()))
    p50_day_id = _day_id(bind, "p50-4-day-iranmuscle-intermediate", 4)
    if p50_day_id is not None:
        bind.execute(
            slots.update()
            .where(slots.c.template_day_id == p50_day_id, slots.c.slot_order == 4)
            .values(target_muscles=["hamstrings", "glutes"])
        )
    for slug, day_number, slot_order, exercise_slug, muscles, pattern, rest in REMOVED_SLOTS:
        day_id = _day_id(bind, slug, day_number)
        if day_id is None:
            continue
        exercise_id = bind.scalar(
            sa.select(exercises.c.id).where(exercises.c.slug == exercise_slug)
        )
        bind.execute(
            slots.insert().values(
                id=uuid4(),
                template_day_id=day_id,
                # Use a temporary order so the unique (day, order) key remains valid
                # before the following contiguous renumbering pass.
                slot_order=1000 + slot_order,
                exercise_id=exercise_id,
                exercise_slug_hint=exercise_slug,
                placeholder_name_en=None,
                placeholder_name_fa=None,
                target_muscles=muscles,
                movement_pattern=pattern,
                intensity_method="standard",
                adaptation_priority="accessory",
                superset_group=None,
                superset_exercise_id=None,
                superset_exercise_slug_hint=None,
                sets=3,
                rep_min=10 if "reverse-fly" in exercise_slug else 8,
                rep_max=12,
                target_rir=2,
                rest_seconds=rest,
            )
        )
        _renumber_slots(bind, slots, day_id)


def _day_id(bind: sa.Connection, slug: str, day_number: int) -> object | None:
    templates = _templates()
    days = _days()
    value = bind.scalar(
        sa.select(days.c.id).where(
            days.c.template_id
            == sa.select(templates.c.id).where(templates.c.slug == slug).scalar_subquery(),
            days.c.day_number == day_number,
        )
    )
    return value


def _renumber_slots(bind: sa.Connection, slots: sa.TableClause, day_id: object) -> None:
    """Restore contiguous slot order without violating the day/order unique key."""
    rows = list(
        bind.execute(
            sa.select(slots.c.id, slots.c.slot_order)
            .where(slots.c.template_day_id == day_id)
            .order_by(slots.c.slot_order, slots.c.id)
        )
    )
    slot_ids = [row.id for row in rows]
    temporary_base = max((row.slot_order for row in rows), default=0) + len(slot_ids) + 1000
    for offset, slot_id in enumerate(slot_ids, start=1):
        bind.execute(
            slots.update()
            .where(slots.c.id == slot_id)
            .values(slot_order=temporary_base + offset)
        )
    for offset, slot_id in enumerate(slot_ids, start=1):
        bind.execute(
            slots.update()
            .where(slots.c.id == slot_id)
            .values(slot_order=offset)
        )


def _templates() -> sa.TableClause:
    return sa.table(
        "training_program_templates",
        sa.column("id", sa.Uuid()),
        sa.column("slug", sa.String()),
    )


def _days() -> sa.TableClause:
    return sa.table(
        "training_program_template_days",
        sa.column("id", sa.Uuid()),
        sa.column("template_id", sa.Uuid()),
        sa.column("day_number", sa.Integer()),
        sa.column("structure_focus", sa.String()),
        sa.column("direct_target_muscles", sa.JSON()),
    )


def _slots() -> sa.TableClause:
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
        sa.column("superset_exercise_id", sa.Uuid()),
        sa.column("superset_exercise_slug_hint", sa.String()),
        sa.column("sets", sa.Integer()),
        sa.column("rep_min", sa.Integer()),
        sa.column("rep_max", sa.Integer()),
        sa.column("target_rir", sa.Integer()),
        sa.column("rest_seconds", sa.Integer()),
    )
