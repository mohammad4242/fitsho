"""Reapply exact structure_focus mapping for seeded template days

Revision ID: c0b1dd908291
Revises: 21c79457f43e
Create Date: 2026-08-24

Corrective data migration that sets the correct explicit structure_focus for
every Fitsho-seeded template day using a stable (slug, day_number) mapping
derived from the seed definitions at the time of this migration.

Rows belonging to unknown / custom templates (not in this mapping) are set to
'other' (a safe non-strict fallback) rather than silently keeping the
misleading 'full_body' server-default that was applied by the previous
migration (ddb30ebe5d49).

Safe to run even if ddb30ebe5d49 has already applied.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c0b1dd908291"
down_revision: str | Sequence[str] | None = "21c79457f43e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# ---------------------------------------------------------------------------
# Stable mapping: (template_slug, day_number) -> structure_focus
# Derived from TRAINING_PROGRAM_TEMPLATE_SEEDS at the time of this migration.
# Do NOT import mutable application code here — the mapping is self-contained.
# ---------------------------------------------------------------------------
_SEED_STRUCTURE_FOCUS: dict[tuple[str, int], str] = {
    ("two-day-first-month-full-body", 1): "full_body",
    ("two-day-first-month-full-body", 2): "full_body",
    ("three-day-first-month-full-body", 1): "full_body",
    ("three-day-first-month-full-body", 2): "full_body",
    ("three-day-first-month-full-body", 3): "full_body",
    ("four-day-first-month-upper-lower", 1): "upper",
    ("four-day-first-month-upper-lower", 2): "lower",
    ("four-day-first-month-upper-lower", 3): "upper",
    ("four-day-first-month-upper-lower", 4): "lower",
    ("two-day-full-body-foundation", 1): "full_body",
    ("two-day-full-body-foundation", 2): "full_body",
    ("two-day-upper-lower-foundation", 1): "full_body",
    ("two-day-upper-lower-foundation", 2): "full_body",
    ("two-day-full-body-hypertrophy", 1): "full_body",
    ("two-day-full-body-hypertrophy", 2): "full_body",
    ("two-day-upper-lower-strength-hypertrophy", 1): "full_body",
    ("two-day-upper-lower-strength-hypertrophy", 2): "full_body",
    ("three-day-full-body-foundation", 1): "full_body",
    ("three-day-full-body-foundation", 2): "full_body",
    ("three-day-full-body-foundation", 3): "full_body",
    ("three-day-push-pull-legs", 1): "push",
    ("three-day-push-pull-legs", 2): "pull",
    ("three-day-push-pull-legs", 3): "lower",
    ("three-day-chest-priority", 1): "other",
    ("three-day-chest-priority", 2): "other",
    ("three-day-chest-priority", 3): "upper",
    ("three-day-back-priority", 1): "other",
    ("three-day-back-priority", 2): "other",
    ("three-day-back-priority", 3): "back_biceps",
    ("three-day-full-body-drop-set", 1): "full_body",
    ("three-day-full-body-drop-set", 2): "full_body",
    ("three-day-full-body-drop-set", 3): "full_body",
    ("four-day-classic-body-part", 1): "chest_triceps",
    ("four-day-classic-body-part", 2): "back_biceps",
    ("four-day-classic-body-part", 3): "lower",
    ("four-day-classic-body-part", 4): "shoulders_traps",
    ("four-day-chest-priority", 1): "chest_triceps",
    ("four-day-chest-priority", 2): "back_biceps",
    ("four-day-chest-priority", 3): "lower",
    ("four-day-chest-priority", 4): "upper",
    ("four-day-back-priority", 1): "chest_triceps",
    ("four-day-back-priority", 2): "back_biceps",
    ("four-day-back-priority", 3): "lower",
    ("four-day-back-priority", 4): "upper",
    ("four-day-quad-hamstring-split", 1): "upper",
    ("four-day-quad-hamstring-split", 2): "quadriceps_calves",
    ("four-day-quad-hamstring-split", 3): "other",
    ("four-day-quad-hamstring-split", 4): "posterior_chain_core",
    ("four-day-phul", 1): "upper",
    ("four-day-phul", 2): "lower",
    ("four-day-phul", 3): "upper",
    ("four-day-phul", 4): "lower",
    ("five-day-classic-body-part", 1): "chest_triceps",
    ("five-day-classic-body-part", 2): "back_biceps",
    ("five-day-classic-body-part", 3): "lower",
    ("five-day-classic-body-part", 4): "shoulders_traps",
    ("five-day-classic-body-part", 5): "other",
    ("five-day-ppl-upper-lower", 1): "push",
    ("five-day-ppl-upper-lower", 2): "pull",
    ("five-day-ppl-upper-lower", 3): "lower",
    ("five-day-ppl-upper-lower", 4): "upper",
    ("five-day-ppl-upper-lower", 5): "lower",
    ("five-day-chest-specialization", 1): "chest_triceps",
    ("five-day-chest-specialization", 2): "back_biceps",
    ("five-day-chest-specialization", 3): "lower",
    ("five-day-chest-specialization", 4): "upper",
    ("five-day-chest-specialization", 5): "other",
    ("five-day-back-specialization", 1): "chest_triceps",
    ("five-day-back-specialization", 2): "back_biceps",
    ("five-day-back-specialization", 3): "lower",
    ("five-day-back-specialization", 4): "upper",
    ("five-day-back-specialization", 5): "other",
    ("four-day-beginner-body-part-foundation", 1): "chest_triceps",
    ("four-day-beginner-body-part-foundation", 2): "back_biceps",
    ("four-day-beginner-body-part-foundation", 3): "lower",
    ("four-day-beginner-body-part-foundation", 4): "shoulders_traps",
    ("four-day-shoulder-priority", 1): "chest_triceps",
    ("four-day-shoulder-priority", 2): "back_biceps",
    ("four-day-shoulder-priority", 3): "lower",
    ("four-day-shoulder-priority", 4): "shoulders_traps",
    ("four-day-arms-priority", 1): "chest_triceps",
    ("four-day-arms-priority", 2): "back_biceps",
    ("four-day-arms-priority", 3): "lower",
    ("four-day-arms-priority", 4): "other",
    ("four-day-advanced-chest-specialization", 1): "chest_triceps",
    ("four-day-advanced-chest-specialization", 2): "back_biceps",
    ("four-day-advanced-chest-specialization", 3): "lower",
    ("four-day-advanced-chest-specialization", 4): "shoulders_traps",
    ("four-day-advanced-posterior-chain", 1): "chest_triceps",
    ("four-day-advanced-posterior-chain", 2): "back_biceps",
    ("four-day-advanced-posterior-chain", 3): "quadriceps_calves",
    ("four-day-advanced-posterior-chain", 4): "posterior_chain_core",
    ("five-day-shoulder-priority", 1): "chest_triceps",
    ("five-day-shoulder-priority", 2): "back_biceps",
    ("five-day-shoulder-priority", 3): "lower",
    ("five-day-shoulder-priority", 4): "shoulders_traps",
    ("five-day-shoulder-priority", 5): "other",
    ("five-day-quad-priority", 1): "chest_triceps",
    ("five-day-quad-priority", 2): "back_biceps",
    ("five-day-quad-priority", 3): "quadriceps_calves",
    ("five-day-quad-priority", 4): "posterior_chain_core",
    ("five-day-quad-priority", 5): "other",
    ("five-day-advanced-arm-specialization", 1): "chest_triceps",
    ("five-day-advanced-arm-specialization", 2): "back_biceps",
    ("five-day-advanced-arm-specialization", 3): "quadriceps_calves",
    ("five-day-advanced-arm-specialization", 4): "posterior_chain_core",
    ("five-day-advanced-arm-specialization", 5): "other",
    ("five-day-advanced-leg-specialization", 1): "chest_triceps",
    ("five-day-advanced-leg-specialization", 2): "back_biceps",
    ("five-day-advanced-leg-specialization", 3): "quadriceps_calves",
    ("five-day-advanced-leg-specialization", 4): "posterior_chain_core",
    ("five-day-advanced-leg-specialization", 5): "other",
    ("six-day-ppl-twice", 1): "push",
    ("six-day-ppl-twice", 2): "pull",
    ("six-day-ppl-twice", 3): "lower",
    ("six-day-ppl-twice", 4): "push",
    ("six-day-ppl-twice", 5): "pull",
    ("six-day-ppl-twice", 6): "lower",
    ("six-day-ppl-volume", 1): "chest_triceps",
    ("six-day-ppl-volume", 2): "back_biceps",
    ("six-day-ppl-volume", 3): "quadriceps_calves",
    ("six-day-ppl-volume", 4): "push",
    ("six-day-ppl-volume", 5): "back_biceps",
    ("six-day-ppl-volume", 6): "posterior_chain_core",
    ("six-day-chest-back-legs-shoulders-arms-legs", 1): "chest_triceps",
    ("six-day-chest-back-legs-shoulders-arms-legs", 2): "back_biceps",
    ("six-day-chest-back-legs-shoulders-arms-legs", 3): "quadriceps_calves",
    ("six-day-chest-back-legs-shoulders-arms-legs", 4): "shoulders_traps",
    ("six-day-chest-back-legs-shoulders-arms-legs", 5): "other",
    ("six-day-chest-back-legs-shoulders-arms-legs", 6): "posterior_chain_core",
    ("six-day-chest-priority", 1): "chest_triceps",
    ("six-day-chest-priority", 2): "back_biceps",
    ("six-day-chest-priority", 3): "lower",
    ("six-day-chest-priority", 4): "chest_triceps",
    ("six-day-chest-priority", 5): "other",
    ("six-day-chest-priority", 6): "other",
    ("six-day-back-priority", 1): "back_biceps",
    ("six-day-back-priority", 2): "chest_triceps",
    ("six-day-back-priority", 3): "lower",
    ("six-day-back-priority", 4): "back_biceps",
    ("six-day-back-priority", 5): "other",
    ("six-day-back-priority", 6): "other",
    ("two-day-full-body-strength-beginner", 1): "full_body",
    ("two-day-full-body-strength-beginner", 2): "full_body",
    ("three-day-full-body-strength-beginner", 1): "full_body",
    ("three-day-full-body-strength-beginner", 2): "full_body",
    ("three-day-full-body-strength-beginner", 3): "full_body",
    ("three-day-full-body-strength-intermediate", 1): "full_body",
    ("three-day-full-body-strength-intermediate", 2): "full_body",
    ("three-day-full-body-strength-intermediate", 3): "full_body",
    ("four-day-upper-lower-strength-intermediate", 1): "lower",
    ("four-day-upper-lower-strength-intermediate", 2): "upper",
    ("four-day-upper-lower-strength-intermediate", 3): "lower",
    ("four-day-upper-lower-strength-intermediate", 4): "upper",
    ("four-day-upper-lower-strength-advanced", 1): "lower",
    ("four-day-upper-lower-strength-advanced", 2): "upper",
    ("four-day-upper-lower-strength-advanced", 3): "lower",
    ("four-day-upper-lower-strength-advanced", 4): "upper",
    ("five-day-strength-intermediate", 1): "quadriceps_calves",
    ("five-day-strength-intermediate", 2): "chest_triceps",
    ("five-day-strength-intermediate", 3): "posterior_chain_core",
    ("five-day-strength-intermediate", 4): "other",
    ("five-day-strength-intermediate", 5): "upper",
    ("five-day-strength-advanced", 1): "quadriceps_calves",
    ("five-day-strength-advanced", 2): "chest_triceps",
    ("five-day-strength-advanced", 3): "posterior_chain_core",
    ("five-day-strength-advanced", 4): "upper",
    ("five-day-strength-advanced", 5): "other",
    ("six-day-push-pull-legs-strength", 1): "push",
    ("six-day-push-pull-legs-strength", 2): "pull",
    ("six-day-push-pull-legs-strength", 3): "lower",
    ("six-day-push-pull-legs-strength", 4): "push",
    ("six-day-push-pull-legs-strength", 5): "pull",
    ("six-day-push-pull-legs-strength", 6): "lower",
    ("three-day-full-body-fat-loss-intermediate", 1): "full_body",
    ("three-day-full-body-fat-loss-intermediate", 2): "full_body",
    ("three-day-full-body-fat-loss-intermediate", 3): "full_body",
    ("four-day-upper-lower-fat-loss-intermediate", 1): "upper",
    ("four-day-upper-lower-fat-loss-intermediate", 2): "lower",
    ("four-day-upper-lower-fat-loss-intermediate", 3): "upper",
    ("four-day-upper-lower-fat-loss-intermediate", 4): "lower",
    ("four-day-upper-lower-fat-loss-advanced", 1): "upper",
    ("four-day-upper-lower-fat-loss-advanced", 2): "lower",
    ("four-day-upper-lower-fat-loss-advanced", 3): "upper",
    ("four-day-upper-lower-fat-loss-advanced", 4): "lower",
    ("five-day-ppl-fat-loss-advanced", 1): "push",
    ("five-day-ppl-fat-loss-advanced", 2): "pull",
    ("five-day-ppl-fat-loss-advanced", 3): "lower",
    ("five-day-ppl-fat-loss-advanced", 4): "full_body",
    ("five-day-ppl-fat-loss-advanced", 5): "full_body",
    ("three-day-full-body-general-fitness-intermediate", 1): "full_body",
    ("three-day-full-body-general-fitness-intermediate", 2): "full_body",
    ("three-day-full-body-general-fitness-intermediate", 3): "full_body",
    ("four-day-upper-lower-general-fitness-intermediate", 1): "upper",
    ("four-day-upper-lower-general-fitness-intermediate", 2): "lower",
    ("four-day-upper-lower-general-fitness-intermediate", 3): "upper",
    ("four-day-upper-lower-general-fitness-intermediate", 4): "lower",
}


def upgrade() -> None:
    """Reapply exact structure_focus mapping for seeded template days.

    Strategy:
    1. For every day whose (slug, day_number) is in the seed mapping, apply
       the correct explicit value from the mapping.
    2. Any remaining row that still has the misleading server-default
       'full_body' value (written by migration ddb30ebe5d49) and does NOT
       belong to a known seed is conservatively set to 'other'.
    """
    conn = op.get_bind()

    # Build a joined query: days join templates to get slug + day_number
    # We use raw SQL to avoid importing application models.
    days_with_slug = sa.text(
        """
        SELECT d.id, t.slug, d.day_number
        FROM training_program_template_days d
        JOIN training_program_templates t ON t.id = d.template_id
        """
    )
    rows = conn.execute(days_with_slug).fetchall()

    # Batch the updates for efficiency
    known_updates: list[dict[str, object]] = []
    unknown_ids: list[object] = []

    for row in rows:
        day_id, slug, day_number = row.id, row.slug, row.day_number
        key = (slug, day_number)
        if key in _SEED_STRUCTURE_FOCUS:
            known_updates.append({"id": day_id, "sf": _SEED_STRUCTURE_FOCUS[key]})
        else:
            unknown_ids.append(day_id)

    # Apply known-seed correct values
    for item in known_updates:
        conn.execute(
            sa.text(
                "UPDATE training_program_template_days SET structure_focus = :sf WHERE id = :id"
            ),
            {"sf": item["sf"], "id": item["id"]},
        )

    # Unknown/custom rows: keep their current value UNLESS it is the
    # misleading 'full_body' server-default, in which case set 'other'
    # so they don't silently receive strict full-body block logic.
    if unknown_ids:
        conn.execute(
            sa.text(
                """
                UPDATE training_program_template_days
                SET structure_focus = 'other'
                WHERE id = ANY(:ids) AND structure_focus = 'full_body'
                """
            ),
            {"ids": list(unknown_ids)},
        )


def downgrade() -> None:
    """Reset all structure_focus to the server-default 'full_body'.

    This matches the state left by the previous migration (ddb30ebe5d49).
    """
    op.execute(
        "UPDATE training_program_template_days SET structure_focus = 'full_body'"
    )
