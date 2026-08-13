"""rename beef catalogue identity to explicit 90/10 ground beef"""

from collections.abc import Sequence
from datetime import date
from uuid import NAMESPACE_URL, uuid5

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert

from alembic import op

revision: str = "20260813_71"
down_revision: str | Sequence[str] | None = "20260812_70"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_NEW_ALIASES = (
    "گوشت چرخ‌کرده گوساله (۱۰٪ چربی)",
    "گوشت چرخ‌کرده گوساله",
    "گوشت چرخ کرده گوساله",
    "گوشت گاو چرخ‌کرده",
)


def upgrade() -> None:
    connection = op.get_bind()
    foods = _foods_table()
    aliases = _aliases_table()
    compositions = _compositions_table()

    legacy_id = connection.scalar(sa.select(foods.c.id).where(foods.c.slug == "beef"))
    current_id = connection.scalar(sa.select(foods.c.id).where(foods.c.slug == "ground-beef"))
    if legacy_id is not None and current_id is not None:
        raise RuntimeError("Both beef and ground-beef catalogue identities exist")
    food_id = legacy_id or current_id
    if food_id is None:
        return

    connection.execute(
        foods.update()
        .where(foods.c.id == food_id)
        .values(
            slug="ground-beef",
            name_fa="گوشت چرخ‌کرده گوساله (۱۰٪ چربی)",
            name_en="Ground beef, 90% lean / 10% fat",
            measurement_basis="raw",
            source_name="USDA FoodData Central SR Legacy",
            source_reference="https://fdc.nal.usda.gov/food-details/174030/nutrients",
            source_food_id="174030",
            data_version="sr-legacy-2018-04",
            source_access_date=date(2026, 8, 13),
        )
    )
    connection.execute(
        compositions.update()
        .where(compositions.c.food_id == food_id)
        .values(
            source_name="USDA FoodData Central SR Legacy",
            source_reference="https://fdc.nal.usda.gov/food-details/174030/nutrients",
            source_food_id="174030",
            data_version="sr-legacy-2018-04",
            source_access_date=date(2026, 8, 13),
        )
    )
    for alias in _NEW_ALIASES:
        connection.execute(
            insert(aliases)
            .values(
                id=uuid5(NAMESPACE_URL, f"fitsho:nutrition:alias:ground-beef:{alias}"),
                food_id=food_id,
                alias=alias,
                normalized_alias=_normalize_alias(alias),
                language="fa",
            )
            .on_conflict_do_nothing(constraint="uq_nutrition_food_alias")
        )


def downgrade() -> None:
    connection = op.get_bind()
    foods = _foods_table()
    aliases = _aliases_table()
    compositions = _compositions_table()
    food_id = connection.scalar(sa.select(foods.c.id).where(foods.c.slug == "ground-beef"))
    if food_id is None:
        return

    alias_ids = [
        uuid5(NAMESPACE_URL, f"fitsho:nutrition:alias:ground-beef:{alias}")
        for alias in _NEW_ALIASES
    ]
    connection.execute(aliases.delete().where(aliases.c.id.in_(alias_ids)))
    connection.execute(
        foods.update()
        .where(foods.c.id == food_id)
        .values(
            slug="beef",
            name_fa="گوشت گوساله",
            name_en="Beef",
            source_reference="https://fdc.nal.usda.gov/download-datasets/",
            source_access_date=date(2026, 8, 9),
        )
    )
    connection.execute(
        compositions.update()
        .where(compositions.c.food_id == food_id)
        .values(
            source_reference="https://fdc.nal.usda.gov/download-datasets/",
            source_access_date=date(2026, 8, 9),
        )
    )


def _normalize_alias(value: str) -> str:
    return " ".join(value.strip().casefold().replace("ي", "ی").replace("ك", "ک").split())


def _foods_table() -> sa.TableClause:
    return sa.table(
        "nutrition_catalogue_foods",
        sa.column("id", sa.Uuid()),
        sa.column("slug", sa.String()),
        sa.column("name_fa", sa.String()),
        sa.column("name_en", sa.String()),
        sa.column("measurement_basis", sa.String()),
        sa.column("source_name", sa.String()),
        sa.column("source_reference", sa.String()),
        sa.column("source_food_id", sa.String()),
        sa.column("data_version", sa.String()),
        sa.column("source_access_date", sa.Date()),
    )


def _aliases_table() -> sa.TableClause:
    return sa.table(
        "nutrition_catalogue_food_aliases",
        sa.column("id", sa.Uuid()),
        sa.column("food_id", sa.Uuid()),
        sa.column("alias", sa.String()),
        sa.column("normalized_alias", sa.String()),
        sa.column("language", sa.String()),
    )


def _compositions_table() -> sa.TableClause:
    return sa.table(
        "nutrition_food_compositions",
        sa.column("food_id", sa.Uuid()),
        sa.column("source_name", sa.String()),
        sa.column("source_reference", sa.String()),
        sa.column("source_food_id", sa.String()),
        sa.column("data_version", sa.String()),
        sa.column("source_access_date", sa.Date()),
    )
