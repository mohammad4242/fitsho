"""split the five wide neutral-grip lat pulldown videos"""

from __future__ import annotations

from collections.abc import Sequence
from copy import deepcopy
from uuid import uuid4

import sqlalchemy as sa

from alembic import op

revision: str = "20260816_84"
down_revision: str | Sequence[str] | None = "20260816_83"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TARGET_SOURCE = "owner-video"
TARGET_SOURCE_ID = "a4a25c322a76c64bbce28aae12b5f0d728ba5364ab58d10aa66a0b93dd3fb31e"

VARIATIONS: tuple[dict[str, str], ...] = (
    {
        "source_id": "68e61505aafd03733258f1179b26a85dc1a788a064bd961b8c859cda02d027df",
        "slug": "owner-68e61505aafd-wide-overhand-lat-pulldown-upper-lats",
        "name_en": "Wide Overhand Lat Pulldown - Upper Lats",
        "name_fa": "لت سیم‌کش دست باز رو به جلو - بخش بالایی لت",
        "grip_en": "wide overhand",
        "grip_fa": "دست باز رو به جلو",
        "target_en": "upper lats",
        "target_fa": "بخش بالایی لت",
    },
    {
        "source_id": "da3c8c259901827c33ef5bef4d3fe6fba8c392f3c48aa7953e6c6244c16365f3",
        "slug": "owner-da3c8c259901-close-overhand-lat-pulldown-lower-lats",
        "name_en": "Close Overhand Lat Pulldown - Lower Lats",
        "name_fa": "لت سیم‌کش دست جمع رو به جلو - بخش پایینی لت",
        "grip_en": "close overhand",
        "grip_fa": "دست جمع رو به جلو",
        "target_en": "lower lats",
        "target_fa": "بخش پایینی لت",
    },
    {
        "source_id": "2be5b59c8936746aa20374595ee0a1d6b009ed1fe58e488185697624dbee0708",
        "slug": "owner-2be5b59c8936-underhand-lat-pulldown-entire-lats",
        "name_en": "Underhand Lat Pulldown - Entire Lats",
        "name_fa": "لت سیم‌کش دست برعکس - کل لت",
        "grip_en": "underhand",
        "grip_fa": "دست برعکس",
        "target_en": "entire lats",
        "target_fa": "کل لت",
    },
    {
        "source_id": "435983d4e255403d32d7767e296dc1a0a1b2e9147014102d8767951e54f76bf1",
        "slug": "owner-435983d4e255-close-neutral-lat-pulldown-lower-lats",
        "name_en": "Close Neutral-Grip Lat Pulldown - Lower Lats",
        "name_fa": "لت سیم‌کش دست جمع موازی - بخش پایینی لت",
        "grip_en": "close neutral",
        "grip_fa": "دست جمع موازی",
        "target_en": "lower lats",
        "target_fa": "بخش پایینی لت",
    },
    {
        "source_id": TARGET_SOURCE_ID,
        "slug": "owner-a4a25c322a76-wide-neutral-grip-lat-pulldown-entire-lats",
        "name_en": "Wide Neutral-Grip Lat Pulldown - Entire Lats",
        "name_fa": "لت سیم‌کش دست باز موازی - کل لت",
        "grip_en": "wide neutral",
        "grip_fa": "دست باز موازی",
        "target_en": "entire lats",
        "target_fa": "کل لت",
    },
)


def _split_tables(bind: sa.Connection) -> tuple[sa.Table, sa.Table]:
    metadata = sa.MetaData()
    metadata.reflect(bind=bind, only=("exercises", "exercise_media_assets"))
    return metadata.tables["exercises"], metadata.tables["exercise_media_assets"]


def _assert_unreferenced(bind: sa.Connection, exercise_ids: Sequence[object]) -> None:
    for exercise_id in exercise_ids:
        for table_name, condition in (
            (
                "workout_plan_exercises",
                "exercise_id = :exercise_id",
            ),
            (
                "training_program_template_slots",
                "exercise_id = :exercise_id",
            ),
            (
                "exercise_alternatives",
                "exercise_id = :exercise_id OR alternative_exercise_id = :exercise_id",
            ),
        ):
            referenced = bind.execute(
                sa.text(f"SELECT EXISTS (SELECT 1 FROM {table_name} WHERE {condition})"),
                {"exercise_id": exercise_id},
            ).scalar_one()
            if referenced:
                raise RuntimeError(
                    f"Cannot split exercise {exercise_id}; it is referenced by {table_name}"
                )


def _copy_associations(bind: sa.Connection, parent_id: object, exercise_id: object) -> None:
    for table_name, value_column in (
        ("exercise_secondary_muscles", "muscle"),
        ("exercise_equipment", "equipment"),
        ("exercise_caution_tags", "caution_tag"),
        ("exercise_label_items", "label"),
    ):
        bind.execute(
            sa.text(
                f"INSERT INTO {table_name} (exercise_id, {value_column}) "
                f"SELECT :exercise_id, {value_column} FROM {table_name} "
                "WHERE exercise_id = :parent_id"
            ),
            {"exercise_id": exercise_id, "parent_id": parent_id},
        )


def _variation_metadata(
    metadata: object,
    variation: dict[str, str],
    source_id: str,
) -> dict[str, object]:
    result = deepcopy(metadata) if isinstance(metadata, dict) else {}
    result["owner_video_asset_source_id"] = source_id
    result["split_variation"] = {
        "grip_en": variation["grip_en"],
        "grip_fa": variation["grip_fa"],
        "target_en": variation["target_en"],
        "target_fa": variation["target_fa"],
    }
    return result


def split_target_exercise(bind: sa.Connection) -> None:
    exercises, media_assets = _split_tables(bind)
    parent = (
        bind.execute(
            sa.select(exercises).where(
                exercises.c.source == TARGET_SOURCE,
                exercises.c.source_id == TARGET_SOURCE_ID,
            )
        )
        .mappings()
        .first()
    )
    if parent is None:
        return

    parent_id = parent["id"]
    assets = (
        bind.execute(
            sa.select(media_assets)
            .where(media_assets.c.exercise_id == parent_id)
            .where(media_assets.c.source_id.in_([item["source_id"] for item in VARIATIONS]))
            .order_by(media_assets.c.source_id)
        )
        .mappings()
        .all()
    )
    assets_by_source_id = {asset["source_id"]: asset for asset in assets}
    if len(assets) != len(VARIATIONS) or set(assets_by_source_id) != {
        item["source_id"] for item in VARIATIONS
    }:
        raise RuntimeError("Wide neutral-grip lat pulldown must have exactly five known videos")

    _assert_unreferenced(bind, [parent_id])
    bind.execute(
        sa.update(exercises)
        .where(exercises.c.id == parent_id)
        .values(source="owner-video-split-parent")
    )

    exercise_columns = [column for column in parent if column != "id"]
    for variation in VARIATIONS:
        source_id = variation["source_id"]
        asset = assets_by_source_id[source_id]
        exercise_id = uuid4()
        values = {column: parent[column] for column in exercise_columns}
        values.update(
            {
                "id": exercise_id,
                "slug": variation["slug"],
                "name_en": variation["name_en"],
                "name_fa": variation["name_fa"],
                "muscle_focus": "lats",
                "media_path": asset["media_path"],
                "media_type": asset["media_type"],
                "source": TARGET_SOURCE,
                "source_id": source_id,
                "source_metadata_en": _variation_metadata(
                    parent["source_metadata_en"], variation, source_id
                ),
            }
        )
        bind.execute(exercises.insert().values(values))
        _copy_associations(bind, parent_id, exercise_id)
        bind.execute(
            sa.update(media_assets)
            .where(media_assets.c.id == asset["id"])
            .values(exercise_id=exercise_id, sort_order=0)
        )

    bind.execute(exercises.delete().where(exercises.c.id == parent_id))


def _restore_original_metadata(metadata: object) -> dict[str, object]:
    result = deepcopy(metadata) if isinstance(metadata, dict) else {}
    result.pop("owner_video_asset_source_id", None)
    result.pop("split_variation", None)
    return result


def restore_target_exercise(bind: sa.Connection) -> None:
    exercises, media_assets = _split_tables(bind)
    rows = (
        bind.execute(
            sa.select(exercises)
            .where(exercises.c.source == TARGET_SOURCE)
            .where(exercises.c.source_id.in_([item["source_id"] for item in VARIATIONS]))
        )
        .mappings()
        .all()
    )
    if not rows:
        return
    rows_by_source_id = {row["source_id"]: row for row in rows}
    if set(rows_by_source_id) != {item["source_id"] for item in VARIATIONS}:
        raise RuntimeError("Cannot restore an incomplete wide neutral-grip lat pulldown split")

    _assert_unreferenced(bind, [row["id"] for row in rows])
    canonical = rows_by_source_id[TARGET_SOURCE_ID]
    canonical_asset = (
        bind.execute(sa.select(media_assets).where(media_assets.c.exercise_id == canonical["id"]))
        .mappings()
        .first()
    )
    if canonical_asset is None:
        raise RuntimeError("Cannot restore wide neutral-grip lat pulldown without its video")

    all_assets = (
        bind.execute(
            sa.select(media_assets)
            .where(media_assets.c.exercise_id.in_([row["id"] for row in rows]))
            .order_by(media_assets.c.source_id)
        )
        .mappings()
        .all()
    )
    for index, asset in enumerate(all_assets):
        bind.execute(
            sa.update(media_assets)
            .where(media_assets.c.id == asset["id"])
            .values(exercise_id=canonical["id"], sort_order=100 + index)
        )
    for index, source_id in enumerate(item["source_id"] for item in VARIATIONS):
        bind.execute(
            sa.update(media_assets)
            .where(media_assets.c.exercise_id == canonical["id"])
            .where(media_assets.c.source_id == source_id)
            .values(sort_order=index)
        )

    original = {
        "slug": "owner-a4a25c322a76-wide-grip-lat-pulldown",
        "name_en": "Wide Neutral-Grip Lat Pulldown",
        "name_fa": "لت سیم‌کش دست باز دست موازی",
        "muscle_focus": "upper_back",
        "source": TARGET_SOURCE,
        "source_id": TARGET_SOURCE_ID,
        "media_path": canonical_asset["media_path"],
        "media_type": canonical_asset["media_type"],
        "source_metadata_en": _restore_original_metadata(canonical["source_metadata_en"]),
    }
    bind.execute(sa.update(exercises).where(exercises.c.id == canonical["id"]).values(original))
    bind.execute(
        exercises.delete().where(
            exercises.c.id.in_([row["id"] for row in rows if row["id"] != canonical["id"]])
        )
    )


def upgrade() -> None:
    split_target_exercise(op.get_bind())


def downgrade() -> None:
    restore_target_exercise(op.get_bind())
