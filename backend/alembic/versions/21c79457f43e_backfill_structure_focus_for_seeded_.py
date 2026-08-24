"""Backfill structure_focus for seeded template days

Revision ID: 21c79457f43e
Revises: ddb30ebe5d49
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
revision: str = "21c79457f43e"
down_revision: str | Sequence[str] | None = "ddb30ebe5d49"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# ---------------------------------------------------------------------------
# Stable mapping: (template_slug, day_number) -> structure_focus
# Derived from TRAINING_PROGRAM_TEMPLATE_SEEDS at the time of this migration.
# Do NOT import mutable application code here — the mapping is self-contained.
# ---------------------------------------------------------------------------
_SEED_STRUCTURE_FOCUS: dict[tuple[str, int], str] = {
    # ── FIRST-MONTH TEMPLATES ────────────────────────────────────────────────
    ("two-day-first-month-full-body", 1): "full_body",    # Full Body A
    ("two-day-first-month-full-body", 2): "full_body",    # Full Body B
    ("three-day-first-month-full-body", 1): "full_body",  # Full Body A
    ("three-day-first-month-full-body", 2): "full_body",  # Full Body B
    ("three-day-first-month-full-body", 3): "full_body",  # Full Body C
    ("four-day-first-month-upper-lower", 1): "upper",     # Upper A
    ("four-day-first-month-upper-lower", 2): "lower",     # Lower A
    ("four-day-first-month-upper-lower", 3): "upper",     # Upper B
    ("four-day-first-month-upper-lower", 4): "lower",     # Lower B
    # ── BEGINNER FULL-BODY ───────────────────────────────────────────────────
    ("two-day-full-body-beginner", 1): "full_body",       # Full Body A
    ("two-day-full-body-beginner", 2): "full_body",       # Full Body B
    ("three-day-full-body-beginner", 1): "full_body",     # Full Body A
    ("three-day-full-body-beginner", 2): "full_body",     # Full Body B
    ("three-day-full-body-beginner", 3): "full_body",     # Full Body C
    # ── INTERMEDIATE FULL-BODY ───────────────────────────────────────────────
    ("three-day-full-body-intermediate", 1): "full_body", # Full Body A
    ("three-day-full-body-intermediate", 2): "full_body", # Full Body B
    ("three-day-full-body-intermediate", 3): "full_body", # Full Body C
    # ── ADVANCED FULL-BODY ───────────────────────────────────────────────────
    ("three-day-full-body-advanced", 1): "full_body",     # Full Body A
    ("three-day-full-body-advanced", 2): "full_body",     # Full Body B
    ("three-day-full-body-advanced", 3): "full_body",     # Full Body C
    # ── UPPER / LOWER ────────────────────────────────────────────────────────
    ("four-day-upper-lower-beginner", 1): "upper",        # Upper A
    ("four-day-upper-lower-beginner", 2): "lower",        # Lower A
    ("four-day-upper-lower-beginner", 3): "upper",        # Upper B
    ("four-day-upper-lower-beginner", 4): "lower",        # Lower B
    ("four-day-upper-lower-intermediate", 1): "upper",    # Upper A
    ("four-day-upper-lower-intermediate", 2): "lower",    # Lower A
    ("four-day-upper-lower-intermediate", 3): "upper",    # Upper B
    ("four-day-upper-lower-intermediate", 4): "lower",    # Lower B
    ("four-day-upper-lower-advanced", 1): "upper",        # Upper A
    ("four-day-upper-lower-advanced", 2): "lower",        # Lower A
    ("four-day-upper-lower-advanced", 3): "upper",        # Upper B
    ("four-day-upper-lower-advanced", 4): "lower",        # Lower B
    # ── PPL ──────────────────────────────────────────────────────────────────
    ("three-day-ppl-beginner", 1): "push",                # Push
    ("three-day-ppl-beginner", 2): "pull",                # Pull
    ("three-day-ppl-beginner", 3): "lower",               # Legs
    ("three-day-ppl-intermediate", 1): "push",            # Push
    ("three-day-ppl-intermediate", 2): "pull",            # Pull
    ("three-day-ppl-intermediate", 3): "lower",           # Legs
    ("three-day-ppl-advanced", 1): "push",                # Push
    ("three-day-ppl-advanced", 2): "pull",                # Pull
    ("three-day-ppl-advanced", 3): "lower",               # Legs
    # ── PRIORITY / ROTATION TEMPLATES ───────────────────────────────────────
    ("three-day-chest-priority", 1): "other",             # Chest + Quads (hybrid)
    ("three-day-chest-priority", 2): "other",             # Back + Hamstrings (hybrid)
    ("three-day-chest-priority", 3): "upper",             # Chest + Shoulders
    ("three-day-back-priority", 1): "other",              # Back + Quads (hybrid)
    ("three-day-back-priority", 2): "other",              # Chest + Hamstrings (hybrid)
    ("three-day-back-priority", 3): "back_biceps",        # Back + Arms
    ("three-day-full-body-drop-set", 1): "full_body",     # Full Body A
    ("three-day-full-body-drop-set", 2): "full_body",     # Full Body B
    ("three-day-full-body-drop-set", 3): "full_body",     # Full Body C
    # ── 4-DAY BODY PART ──────────────────────────────────────────────────────
    ("four-day-body-part-beginner", 1): "chest_triceps",  # Chest + Triceps
    ("four-day-body-part-beginner", 2): "back_biceps",    # Back + Biceps
    ("four-day-body-part-beginner", 3): "lower",          # Legs
    ("four-day-body-part-beginner", 4): "shoulders_traps",# Shoulders + Traps
    ("four-day-body-part-intermediate", 1): "chest_triceps",
    ("four-day-body-part-intermediate", 2): "back_biceps",
    ("four-day-body-part-intermediate", 3): "lower",
    ("four-day-body-part-intermediate", 4): "upper",      # Upper
    ("four-day-body-part-advanced", 1): "chest_triceps",
    ("four-day-body-part-advanced", 2): "back_biceps",
    ("four-day-body-part-advanced", 3): "lower",
    ("four-day-body-part-advanced", 4): "upper",
    # ── 4-DAY ADVANCED POSTERIOR CHAIN ──────────────────────────────────────
    ("four-day-advanced-posterior-chain", 1): "upper",          # Upper
    ("four-day-advanced-posterior-chain-superset", 1): "upper", # Upper
    ("four-day-phul", 1): "lower",                              # Lower Power
    ("four-day-phul", 2): "upper",                              # Upper Power
    ("four-day-phul", 3): "lower",                              # Lower Hypertrophy
    ("four-day-phul", 4): "upper",                              # Upper Hypertrophy
    # ── 5-DAY TEMPLATES ──────────────────────────────────────────────────────
    ("five-day-body-part-intermediate", 1): "chest_triceps",
    ("five-day-body-part-intermediate", 2): "back_biceps",
    ("five-day-body-part-intermediate", 3): "lower",
    ("five-day-body-part-intermediate", 4): "shoulders_traps",
    ("five-day-body-part-intermediate", 5): "other",             # Arms
    ("five-day-body-part-advanced", 1): "chest_triceps",
    ("five-day-body-part-advanced", 2): "back_biceps",
    ("five-day-body-part-advanced", 3): "lower",
    ("five-day-body-part-advanced", 4): "shoulders_traps",
    ("five-day-body-part-advanced", 5): "other",                 # Arms
    ("five-day-ppl-intermediate", 1): "push",
    ("five-day-ppl-intermediate", 2): "pull",
    ("five-day-ppl-intermediate", 3): "lower",
    ("five-day-ppl-intermediate", 4): "upper",
    ("five-day-ppl-intermediate", 5): "other",
    ("five-day-ppl-advanced", 1): "push",
    ("five-day-ppl-advanced", 2): "pull",
    ("five-day-ppl-advanced", 3): "lower",
    ("five-day-ppl-advanced", 4): "upper",
    ("five-day-ppl-advanced", 5): "other",
    # ── PRIORITY ─────────────────────────────────────────────────────────────
    ("five-day-shoulder-priority", 1): "chest_triceps",
    ("five-day-shoulder-priority", 2): "back_biceps",
    ("five-day-shoulder-priority", 3): "lower",
    ("five-day-shoulder-priority", 4): "shoulders_traps",
    ("five-day-shoulder-priority", 5): "other",                  # Arms
    ("five-day-quad-priority", 1): "chest_triceps",
    ("five-day-quad-priority", 2): "back_biceps",
    ("five-day-quad-priority", 3): "quadriceps_calves",
    ("five-day-quad-priority", 4): "posterior_chain_core",
    ("five-day-quad-priority", 5): "other",                      # Shoulders + Arms (hybrid)
    # ── SPECIALISATION ───────────────────────────────────────────────────────
    ("five-day-advanced-arm-specialization", 1): "chest_triceps",
    ("five-day-advanced-arm-specialization", 2): "back_biceps",
    ("five-day-advanced-arm-specialization", 3): "quadriceps_calves",
    ("five-day-advanced-arm-specialization", 4): "posterior_chain_core",
    ("five-day-advanced-arm-specialization", 5): "other",        # Arms + Delts
    ("five-day-advanced-leg-specialization", 1): "chest_triceps",
    ("five-day-advanced-leg-specialization", 2): "back_biceps",
    ("five-day-advanced-leg-specialization", 3): "quadriceps_calves",
    ("five-day-advanced-leg-specialization", 4): "posterior_chain_core",
    ("five-day-advanced-leg-specialization", 5): "other",        # Shoulders + Arms (hybrid)
    # ── 5-DAY POSTERIOR CHAIN ────────────────────────────────────────────────
    ("five-day-posterior-chain", 1): "chest_triceps",
    ("five-day-posterior-chain", 2): "back_biceps",
    ("five-day-posterior-chain", 3): "quadriceps_calves",
    ("five-day-posterior-chain", 4): "posterior_chain_core",
    ("five-day-posterior-chain", 5): "shoulders_traps",
    ("five-day-posterior-chain-superset", 1): "chest_triceps",
    ("five-day-posterior-chain-superset", 2): "back_biceps",
    ("five-day-posterior-chain-superset", 3): "quadriceps_calves",
    ("five-day-posterior-chain-superset", 4): "posterior_chain_core",
    ("five-day-posterior-chain-superset", 5): "other",           # Shoulders + Arms (hybrid)
    # ── 6-DAY PPL ────────────────────────────────────────────────────────────
    ("six-day-ppl-twice", 1): "push",
    ("six-day-ppl-twice", 2): "pull",
    ("six-day-ppl-twice", 3): "lower",
    ("six-day-ppl-twice", 4): "push",
    ("six-day-ppl-twice", 5): "pull",
    ("six-day-ppl-twice", 6): "lower",
    ("six-day-ppl-volume", 1): "chest_triceps",                  # Push Chest
    ("six-day-ppl-volume", 2): "back_biceps",                    # Pull Width
    ("six-day-ppl-volume", 3): "quadriceps_calves",              # Legs Quadriceps
    ("six-day-ppl-volume", 4): "push",                           # Push Shoulders (push day)
    ("six-day-ppl-volume", 5): "back_biceps",                    # Pull Thickness
    ("six-day-ppl-volume", 6): "posterior_chain_core",           # Legs Posterior
    # ── 6-DAY BODY PART ──────────────────────────────────────────────────────
    ("six-day-chest-back-legs-shoulders-arms-legs", 1): "chest_triceps",
    ("six-day-chest-back-legs-shoulders-arms-legs", 2): "back_biceps",
    ("six-day-chest-back-legs-shoulders-arms-legs", 3): "quadriceps_calves",
    ("six-day-chest-back-legs-shoulders-arms-legs", 4): "shoulders_traps",
    ("six-day-chest-back-legs-shoulders-arms-legs", 5): "other",  # Arms
    ("six-day-chest-back-legs-shoulders-arms-legs", 6): "posterior_chain_core",
    # ── 6-DAY PRIORITY ───────────────────────────────────────────────────────
    ("six-day-chest-priority", 1): "chest_triceps",              # Chest Heavy
    ("six-day-chest-priority", 2): "back_biceps",                # Back + Biceps
    ("six-day-chest-priority", 3): "lower",                      # Legs
    ("six-day-chest-priority", 4): "chest_triceps",              # Chest Volume
    ("six-day-chest-priority", 5): "other",                      # Shoulders + Triceps (hybrid)
    ("six-day-chest-priority", 6): "other",                      # Calves + Core
    ("six-day-back-priority", 1): "back_biceps",                 # Back Width
    ("six-day-back-priority", 2): "chest_triceps",               # Chest + Triceps
    ("six-day-back-priority", 3): "lower",                       # Legs
    ("six-day-back-priority", 4): "back_biceps",                 # Back Thickness
    ("six-day-back-priority", 5): "other",                       # Shoulders + Biceps (hybrid)
    ("six-day-back-priority", 6): "other",                       # Calves + Core
    # ── STRENGTH ─────────────────────────────────────────────────────────────
    ("two-day-full-body-strength-beginner", 1): "full_body",
    ("two-day-full-body-strength-beginner", 2): "full_body",
    ("three-day-full-body-strength-beginner", 1): "full_body",
    ("three-day-full-body-strength-beginner", 2): "full_body",
    ("three-day-full-body-strength-beginner", 3): "full_body",
    ("three-day-full-body-strength-intermediate", 1): "full_body",
    ("three-day-full-body-strength-intermediate", 2): "full_body",
    ("three-day-full-body-strength-intermediate", 3): "full_body",
    ("four-day-upper-lower-strength-intermediate", 1): "lower",  # Lower Power
    ("four-day-upper-lower-strength-intermediate", 2): "upper",  # Upper Power
    ("four-day-upper-lower-strength-intermediate", 3): "lower",  # Lower Hypertrophy
    ("four-day-upper-lower-strength-intermediate", 4): "upper",  # Upper Hypertrophy
    ("four-day-upper-lower-strength-advanced", 1): "lower",      # Lower Power
    ("four-day-upper-lower-strength-advanced", 2): "upper",      # Upper Power
    ("four-day-upper-lower-strength-advanced", 3): "lower",      # Lower Volume
    ("four-day-upper-lower-strength-advanced", 4): "upper",      # Upper Volume
    ("five-day-strength-intermediate", 1): "quadriceps_calves",  # Squat Day
    ("five-day-strength-intermediate", 2): "chest_triceps",      # Bench Day
    ("five-day-strength-intermediate", 3): "posterior_chain_core", # Deadlift Day
    ("five-day-strength-intermediate", 4): "other",              # Overhead Press Day
    ("five-day-strength-intermediate", 5): "upper",              # Upper Accessory
    ("five-day-strength-advanced", 1): "quadriceps_calves",      # Squat — Heavy
    ("five-day-strength-advanced", 2): "chest_triceps",          # Bench — Heavy
    ("five-day-strength-advanced", 3): "posterior_chain_core",   # Deadlift — Heavy
    ("five-day-strength-advanced", 4): "upper",                  # Press + Pull Accessory
    ("five-day-strength-advanced", 5): "other",                  # Leg Accessory + Core
    ("six-day-push-pull-legs-strength", 1): "push",              # Push — Heavy
    ("six-day-push-pull-legs-strength", 2): "pull",              # Pull — Heavy
    ("six-day-push-pull-legs-strength", 3): "lower",             # Legs — Heavy
    ("six-day-push-pull-legs-strength", 4): "push",              # Push — Volume
    ("six-day-push-pull-legs-strength", 5): "pull",              # Pull — Volume
    ("six-day-push-pull-legs-strength", 6): "lower",             # Legs — Volume
    # ── FAT-LOSS / GENERAL FITNESS ───────────────────────────────────────────
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
    """Backfill structure_focus for seeded template days.

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
