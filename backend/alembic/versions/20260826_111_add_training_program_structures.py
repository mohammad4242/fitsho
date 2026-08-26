"""Add TrainingProgramStructure and seed initial structures from canonical templates.

Revision ID: 20260826_111
Revises: 375f20e220a9
Create Date: 2026-08-26
"""

from collections.abc import Sequence
from uuid import NAMESPACE_URL, uuid5

import sqlalchemy as sa
from alembic import op

revision: str = "20260826_111"
down_revision: str | Sequence[str] | None = "375f20e220a9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# ---------------------------------------------------------------------------
# Initial structure definitions inferred from the canonical template catalog.
# Each entry: (slug, name_en, name_fa, days_per_week, description_en, description_fa, days)
# days: list of (day_number, day_type, label_en, label_fa)
# ---------------------------------------------------------------------------
_STRUCTURES: list[tuple] = [
    (
        "2d-full-body-ab",
        "2-Day Full Body A/B",
        "تمام‌بدن دو روزه A/B",
        2,
        "Two full-body sessions per week with A/B variation.",
        "دو جلسه تمام‌بدن در هفته با تنوع A/B.",
        [
            (1, "full_body", "Full Body A", "تمام‌بدن A"),
            (2, "full_body", "Full Body B", "تمام‌بدن B"),
        ],
    ),
    (
        "3d-upper-lower-full-body",
        "Upper / Lower / Full Body",
        "بالاتنه / پایین‌تنه / تمام‌بدن",
        3,
        "Three-day split ending with a broad full-body session.",
        "تقسیم سه‌روزه با پایان در یک جلسه تمام‌بدن.",
        [
            (1, "upper", "Upper", "بالاتنه"),
            (2, "lower", "Lower", "پایین‌تنه"),
            (3, "full_body", "Full Body", "تمام‌بدن"),
        ],
    ),
    (
        "3d-upper-lower-upper",
        "Upper / Lower / Upper",
        "بالاتنه / پایین‌تنه / بالاتنه",
        3,
        "Three-day upper-priority split with two upper sessions.",
        "تقسیم سه‌روزه با اولویت بالاتنه و دو جلسه بالاتنه.",
        [
            (1, "upper", "Upper A", "بالاتنه A"),
            (2, "lower", "Lower", "پایین‌تنه"),
            (3, "upper", "Upper B", "بالاتنه B"),
        ],
    ),
    (
        "3d-lower-upper-lower",
        "Lower / Upper / Lower",
        "پایین‌تنه / بالاتنه / پایین‌تنه",
        3,
        "Three-day lower-priority split with two lower sessions.",
        "تقسیم سه‌روزه با اولویت پایین‌تنه و دو جلسه پایین‌تنه.",
        [
            (1, "lower", "Lower A", "پایین‌تنه A"),
            (2, "upper", "Upper", "بالاتنه"),
            (3, "lower", "Lower B", "پایین‌تنه B"),
        ],
    ),
    (
        "4d-upper-lower-2x",
        "Upper / Lower \u00d72",
        "بالاتنه / پایین‌تنه دو بار در هفته",
        4,
        "Balanced four-day split with two exposures per region.",
        "تقسیم متعادل چهارروزه با دو مواجهه برای هر ناحیه.",
        [
            (1, "upper", "Upper A", "بالاتنه A"),
            (2, "lower", "Lower A", "پایین‌تنه A"),
            (3, "upper", "Upper B", "بالاتنه B"),
            (4, "lower", "Lower B", "پایین‌تنه B"),
        ],
    ),
    (
        "4d-3-upper-1-lower",
        "3 Upper / 1 Lower",
        "سه بالاتنه و یک پایین‌تنه",
        4,
        "Upper-priority four-day split with three upper sessions.",
        "تقسیم چهارروزه با اولویت بالاتنه و سه جلسه بالاتنه.",
        [
            (1, "upper", "Upper A: Chest + Back", "بالاتنه A: سینه + پشت"),
            (2, "lower", "Lower", "پایین‌تنه"),
            (3, "upper", "Upper B: Shoulders + Arms", "بالاتنه B: سرشانه + بازو"),
            (4, "upper", "Upper C: Chest + Back", "بالاتنه C: سینه + پشت"),
        ],
    ),
    (
        "4d-3-lower-1-upper",
        "3 Lower / 1 Upper",
        "سه پایین‌تنه و یک بالاتنه",
        4,
        "Lower-priority four-day split with three lower sessions.",
        "تقسیم چهارروزه با اولویت پایین‌تنه و سه جلسه پایین‌تنه.",
        [
            (1, "lower", "Lower A: Quad Bias", "پایین‌تنه A: تأکید چهارسر"),
            (2, "upper", "Upper", "بالاتنه"),
            (3, "lower", "Lower B: Posterior Bias", "پایین‌تنه B: تأکید خلفی"),
            (4, "lower", "Lower C: Quad + Glute", "پایین‌تنه C: چهارسر + باسن"),
        ],
    ),
    (
        "4d-push-pull-quads-posterior",
        "Push / Pull / Quads / Posterior",
        "پوش / پول / چهارسر / خلفی",
        4,
        "Four-day split with distinct push, pull, quad, and posterior days.",
        "تقسیم چهارروزه با روزهای جداگانه پوش، پول، چهارسر و خلفی.",
        [
            (1, "push", "Push", "پوش"),
            (2, "pull", "Pull", "پول"),
            (3, "lower", "Quads", "چهارسر"),
            (4, "posterior_chain", "Posterior", "خلفی"),
        ],
    ),
    (
        "5d-ppl-upper-lower",
        "Push / Pull / Legs / Upper / Lower",
        "پوش / پول / پا / بالاتنه / پایین‌تنه",
        5,
        "Five-day structure combining focused PPL sessions with broad upper/lower exposures.",
        "ساختار پنج‌روزه با ترکیب جلسات متمرکز PPL و مواجهه گسترده بالاتنه/پایین‌تنه.",
        [
            (1, "push", "Push", "پوش"),
            (2, "pull", "Pull", "پول"),
            (3, "lower", "Legs", "پا"),
            (4, "upper", "Upper", "بالاتنه"),
            (5, "lower", "Lower", "پایین‌تنه"),
        ],
    ),
    (
        "5d-classic-body-part",
        "5-Day Classic Body-Part Split",
        "تقسیم کلاسیک عضله‌ای پنج‌روزه",
        5,
        "Classic body-part rotation: Chest, Back, Legs, Shoulders, Arms.",
        "چرخش کلاسیک عضله‌ای: سینه، پشت، پا، سرشانه، بازو.",
        [
            (1, "chest_triceps", "Chest", "سینه"),
            (2, "back_biceps", "Back", "پشت"),
            (3, "lower", "Legs", "پا"),
            (4, "shoulders_traps", "Shoulders", "سرشانه"),
            (5, "arms", "Arms", "بازو"),
        ],
    ),
    (
        "5d-chest-spec-body-part",
        "5-Day Chest Specialization Body-Part",
        "تقسیم عضله‌ای پنج‌روزه با تخصص سینه",
        5,
        "Body-part split with a dedicated second chest session for specialization.",
        "تقسیم عضله‌ای با یک جلسه سینه دوم برای تخصص.",
        [
            (1, "chest_triceps", "Chest + Triceps", "سینه + پشت بازو"),
            (2, "back_biceps", "Back + Biceps", "پشت + جلو بازو"),
            (3, "lower", "Legs", "پا"),
            (4, "shoulders_arms", "Shoulders + Arms", "سرشانه + بازو"),
            (5, "chest_priority", "Chest Priority", "اولویت سینه"),
        ],
    ),
    (
        "5d-back-spec-body-part",
        "5-Day Back Specialization Body-Part",
        "تقسیم عضله‌ای پنج‌روزه با تخصص پشت",
        5,
        "Body-part split with a dedicated second back session for specialization.",
        "تقسیم عضله‌ای با یک جلسه پشت دوم برای تخصص.",
        [
            (1, "back_biceps", "Back + Biceps", "پشت + جلو بازو"),
            (2, "chest_triceps", "Chest + Triceps", "سینه + پشت بازو"),
            (3, "lower", "Legs", "پا"),
            (4, "shoulders_arms", "Shoulders + Arms", "سرشانه + بازو"),
            (5, "back_priority", "Back Priority", "اولویت پشت"),
        ],
    ),
    (
        "5d-leg-spec-body-part",
        "5-Day Leg Specialization Body-Part",
        "تقسیم عضله‌ای پنج‌روزه با تخصص پا",
        5,
        "Body-part split rotating quad and posterior-chain emphasis.",
        "تقسیم عضله‌ای با چرخش تأکید چهارسر و خلفی.",
        [
            (1, "lower", "Quads", "چهارسر"),
            (2, "chest_triceps", "Chest", "سینه"),
            (3, "back_biceps", "Back", "پشت"),
            (4, "shoulders_arms", "Shoulders + Arms", "سرشانه + بازو"),
            (5, "posterior_chain", "Posterior Chain", "زنجیره خلفی"),
        ],
    ),
    (
        "6d-ppl-2x",
        "PPL \u00d72",
        "PPL دو بار در هفته",
        6,
        "Six-day split with two planned push, pull, and legs rotations.",
        "تقسیم شش‌روزه با دو چرخه برنامه‌ریزی‌شده پوش، پول و پا.",
        [
            (1, "push", "Push A", "پوش A"),
            (2, "pull", "Pull A", "پول A"),
            (3, "lower", "Legs A", "پا A"),
            (4, "push", "Push B", "پوش B"),
            (5, "pull", "Pull B", "پول B"),
            (6, "lower", "Legs B", "پا B"),
        ],
    ),
    (
        "6d-advanced-body-part",
        "6-Day Advanced Body-Part",
        "شش‌روزه پیشرفته عضله‌ای",
        6,
        "Six-day body-part split with dedicated days for each major muscle group.",
        "تقسیم عضله‌ای شش‌روزه با روزهای اختصاصی برای هر گروه عضلانی اصلی.",
        [
            (1, "chest_triceps", "Chest", "سینه"),
            (2, "back_biceps", "Back", "پشت"),
            (3, "lower", "Quads", "چهارسر"),
            (4, "shoulders_traps", "Shoulders", "سرشانه"),
            (5, "arms", "Arms", "بازو"),
            (6, "posterior_chain", "Hamstrings + Glutes", "همسترینگ + باسن"),
        ],
    ),
    (
        "6d-ppl-specialization",
        "6-Day PPL Specialization",
        "شش‌روزه PPL با تخصص",
        6,
        "Six-day PPL base with dedicated specialization sessions after the main rotation.",
        "پایه PPL شش‌روزه با جلسات تخصصی بعد از چرخه اصلی.",
        [
            (1, "push", "Push", "پوش"),
            (2, "pull", "Pull", "پول"),
            (3, "lower", "Legs", "پا"),
            (4, "chest_priority", "Chest Priority", "اولویت سینه"),
            (5, "back_priority", "Back Priority", "اولویت پشت"),
            (6, "lower", "Legs B", "پا B"),
        ],
    ),
]

# Map canonical template slug → structure slug
_TEMPLATE_STRUCTURE_MAP: dict[str, str] = {
    "t01-2-day-full-body-ab": "2d-full-body-ab",
    "t02-3-day-upper-lower-full": "3d-upper-lower-full-body",
    "t03-3-day-upper-lower-upper": "3d-upper-lower-upper",
    "t04-3-day-lower-upper-lower": "3d-lower-upper-lower",
    "t05-4-day-upper-lower-2x": "4d-upper-lower-2x",
    "t06-4-day-3-upper-1-lower": "4d-3-upper-1-lower",
    "t07-4-day-3-lower-1-upper": "4d-3-lower-1-upper",
    "t08-4-day-push-pull-quads-posterior": "4d-push-pull-quads-posterior",
    "t09-5-day-ppl-upper-lower": "5d-ppl-upper-lower",
    "t10-5-day-classic-body-part": "5d-classic-body-part",
    "t11-5-day-ppl-upper-lower-priority": "5d-ppl-upper-lower",  # shares structure with t09
    "t12-5-day-chest-specialization": "5d-chest-spec-body-part",
    "t13-5-day-back-specialization": "5d-back-spec-body-part",
    "t14-5-day-leg-specialization": "5d-leg-spec-body-part",
    "t15-6-day-ppl-2x": "6d-ppl-2x",
    "t16-6-day-advanced-body-part": "6d-advanced-body-part",
    "t17-6-day-balanced-specialization": "6d-ppl-specialization",
}


def _structure_id(slug: str) -> str:
    """Stable deterministic UUID for a structure slug."""
    return str(uuid5(NAMESPACE_URL, f"https://fitsho.local/training-structure/{slug}"))


def upgrade() -> None:
    # ---- Create tables -------------------------------------------------------
    op.create_table(
        "training_program_structures",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("slug", sa.String(length=120), nullable=False),
        sa.Column("name_en", sa.String(length=160), nullable=False),
        sa.Column("name_fa", sa.String(length=160), nullable=False),
        sa.Column("days_per_week", sa.Integer(), nullable=False),
        sa.Column("description_en", sa.String(length=500), nullable=True),
        sa.Column("description_fa", sa.String(length=500), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug", name="uq_training_program_structures_slug"),
        sa.CheckConstraint(
            "days_per_week BETWEEN 2 AND 6",
            name="ck_training_program_structures_days_per_week",
        ),
        sa.CheckConstraint(
            "slug ~ '^[a-z0-9]+(-[a-z0-9]+)*$'",
            name="ck_training_program_structures_slug_format",
        ),
    )
    op.create_index(
        "ix_training_program_structures_days_per_week",
        "training_program_structures",
        ["days_per_week"],
    )

    op.create_table(
        "training_program_structure_days",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("structure_id", sa.Uuid(), nullable=False),
        sa.Column("day_number", sa.Integer(), nullable=False),
        sa.Column("label_en", sa.String(length=120), nullable=False),
        sa.Column("label_fa", sa.String(length=120), nullable=False),
        sa.Column("day_type", sa.String(length=60), nullable=True),
        sa.ForeignKeyConstraint(
            ["structure_id"],
            ["training_program_structures.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "structure_id",
            "day_number",
            name="uq_training_program_structure_days_structure_day",
        ),
        sa.CheckConstraint(
            "day_number >= 1",
            name="ck_training_program_structure_days_day_number",
        ),
    )

    op.add_column(
        "training_program_templates",
        sa.Column("structure_id", sa.Uuid(), nullable=True),
    )
    op.create_foreign_key(
        "fk_training_program_templates_structure_id",
        "training_program_templates",
        "training_program_structures",
        ["structure_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_training_program_templates_structure_id",
        "training_program_templates",
        ["structure_id"],
    )

    # ---- Seed initial structures --------------------------------------------
    bind = op.get_bind()
    structures_table = sa.table(
        "training_program_structures",
        sa.column("id", sa.Uuid()),
        sa.column("slug", sa.String()),
        sa.column("name_en", sa.String()),
        sa.column("name_fa", sa.String()),
        sa.column("days_per_week", sa.Integer()),
        sa.column("description_en", sa.String()),
        sa.column("description_fa", sa.String()),
        sa.column("is_active", sa.Boolean()),
    )
    structure_days_table = sa.table(
        "training_program_structure_days",
        sa.column("id", sa.Uuid()),
        sa.column("structure_id", sa.Uuid()),
        sa.column("day_number", sa.Integer()),
        sa.column("label_en", sa.String()),
        sa.column("label_fa", sa.String()),
        sa.column("day_type", sa.String()),
    )

    slug_to_id: dict[str, str] = {}
    for slug, name_en, name_fa, dpw, desc_en, desc_fa, days in _STRUCTURES:
        sid = _structure_id(slug)
        slug_to_id[slug] = sid
        bind.execute(
            structures_table.insert().values(
                id=sid,
                slug=slug,
                name_en=name_en,
                name_fa=name_fa,
                days_per_week=dpw,
                description_en=desc_en,
                description_fa=desc_fa,
                is_active=True,
            )
        )
        for day_number, day_type, label_en, label_fa in days:
            bind.execute(
                structure_days_table.insert().values(
                    id=str(uuid5(NAMESPACE_URL, f"{sid}/day/{day_number}")),
                    structure_id=sid,
                    day_number=day_number,
                    label_en=label_en,
                    label_fa=label_fa,
                    day_type=day_type,
                )
            )

    # ---- Link canonical templates to their structures -----------------------
    templates_table = sa.table(
        "training_program_templates",
        sa.column("slug", sa.String()),
        sa.column("structure_id", sa.Uuid()),
    )
    for template_slug, structure_slug in _TEMPLATE_STRUCTURE_MAP.items():
        structure_uuid = slug_to_id[structure_slug]
        bind.execute(
            sa.update(templates_table)
            .where(templates_table.c.slug == template_slug)
            .values(structure_id=structure_uuid)
        )


def downgrade() -> None:
    op.drop_constraint(
        "fk_training_program_templates_structure_id",
        "training_program_templates",
        type_="foreignkey",
    )
    op.drop_index(
        "ix_training_program_templates_structure_id",
        table_name="training_program_templates",
    )
    op.drop_column("training_program_templates", "structure_id")
    op.drop_table("training_program_structure_days")
    op.drop_index(
        "ix_training_program_structures_days_per_week",
        table_name="training_program_structures",
    )
    op.drop_table("training_program_structures")
