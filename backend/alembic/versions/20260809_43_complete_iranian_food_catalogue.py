"""complete approved Iranian food catalogue and composition basis"""

from collections.abc import Sequence
from datetime import date
from uuid import NAMESPACE_URL, uuid5

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert

from alembic import op

revision: str = "20260809_43"
down_revision: str | Sequence[str] | None = "20260809_42"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "nutrition_catalogue_foods",
        sa.Column("category", sa.String(64), nullable=False, server_default="uncategorized"),
    )
    op.add_column(
        "nutrition_catalogue_foods",
        sa.Column(
            "measurement_basis",
            sa.String(24),
            nullable=False,
            server_default="as_purchased",
        ),
    )
    op.add_column(
        "nutrition_catalogue_foods",
        sa.Column("canonical_quantity", sa.Numeric(12, 4), nullable=False, server_default="100"),
    )
    op.add_column(
        "nutrition_catalogue_foods",
        sa.Column("canonical_unit", sa.String(16), nullable=False, server_default="g"),
    )
    op.add_column(
        "nutrition_catalogue_foods",
        sa.Column("edible_portion", sa.Numeric(8, 6), nullable=False, server_default="1"),
    )
    op.add_column(
        "nutrition_catalogue_foods",
        sa.Column("data_version", sa.String(64), nullable=False, server_default="unversioned"),
    )
    op.add_column("nutrition_catalogue_foods", sa.Column("source_access_date", sa.Date()))
    op.create_check_constraint(
        "ck_nutrition_catalogue_food_basis_values",
        "nutrition_catalogue_foods",
        "measurement_basis IN ('raw', 'dry', 'as_purchased')",
    )
    op.create_check_constraint(
        "ck_nutrition_catalogue_food_quantity_positive",
        "nutrition_catalogue_foods",
        "canonical_quantity > 0",
    )
    op.create_check_constraint(
        "ck_nutrition_catalogue_food_edible_portion",
        "nutrition_catalogue_foods",
        "edible_portion > 0 AND edible_portion <= 1",
    )
    op.create_table(
        "nutrition_catalogue_food_aliases",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("food_id", sa.Uuid(), nullable=False),
        sa.Column("alias", sa.String(160), nullable=False),
        sa.Column("normalized_alias", sa.String(160), nullable=False),
        sa.Column("language", sa.String(8), nullable=False, server_default="und"),
        sa.ForeignKeyConstraint(["food_id"], ["nutrition_catalogue_foods.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("food_id", "normalized_alias", name="uq_nutrition_food_alias"),
    )
    op.create_index(
        "ix_nutrition_catalogue_food_aliases_food_id",
        "nutrition_catalogue_food_aliases",
        ["food_id"],
    )
    op.create_index(
        "ix_nutrition_catalogue_food_aliases_normalized_alias",
        "nutrition_catalogue_food_aliases",
        ["normalized_alias"],
    )
    op.add_column("nutrition_food_compositions", sa.Column("source_food_id", sa.String(120)))
    op.add_column(
        "nutrition_food_compositions",
        sa.Column("data_version", sa.String(64), nullable=False, server_default="unversioned"),
    )
    op.add_column("nutrition_food_compositions", sa.Column("source_access_date", sa.Date()))

    _seed_catalogue(op.get_bind())


def downgrade() -> None:
    op.drop_column("nutrition_food_compositions", "source_access_date")
    op.drop_column("nutrition_food_compositions", "data_version")
    op.drop_column("nutrition_food_compositions", "source_food_id")
    op.drop_index(
        "ix_nutrition_catalogue_food_aliases_normalized_alias",
        table_name="nutrition_catalogue_food_aliases",
    )
    op.drop_index(
        "ix_nutrition_catalogue_food_aliases_food_id",
        table_name="nutrition_catalogue_food_aliases",
    )
    op.drop_table("nutrition_catalogue_food_aliases")
    op.drop_constraint(
        "ck_nutrition_catalogue_food_edible_portion",
        "nutrition_catalogue_foods",
        type_="check",
    )
    op.drop_constraint(
        "ck_nutrition_catalogue_food_quantity_positive",
        "nutrition_catalogue_foods",
        type_="check",
    )
    op.drop_constraint(
        "ck_nutrition_catalogue_food_basis_values",
        "nutrition_catalogue_foods",
        type_="check",
    )
    op.drop_column("nutrition_catalogue_foods", "source_access_date")
    op.drop_column("nutrition_catalogue_foods", "data_version")
    op.drop_column("nutrition_catalogue_foods", "edible_portion")
    op.drop_column("nutrition_catalogue_foods", "canonical_unit")
    op.drop_column("nutrition_catalogue_foods", "canonical_quantity")
    op.drop_column("nutrition_catalogue_foods", "measurement_basis")
    op.drop_column("nutrition_catalogue_foods", "category")


def _seed_catalogue(connection: sa.Connection) -> None:
    from app.nutrition.catalogue_seed_data import (
        APPROVED_FOODS,
        NUTRIENT_UNITS,
        USDA_ACCESS_DATE,
        USDA_DATA_VERSION,
        USDA_SOURCE_NAME,
        USDA_SOURCE_REFERENCE,
        composition_for,
    )

    foods = sa.table(
        "nutrition_catalogue_foods",
        sa.column("id", sa.Uuid()),
        sa.column("slug", sa.String()),
        sa.column("name_fa", sa.String()),
        sa.column("name_en", sa.String()),
        sa.column("verification_status", sa.String()),
        sa.column("source_name", sa.String()),
        sa.column("source_reference", sa.String()),
        sa.column("source_food_id", sa.String()),
        sa.column("category", sa.String()),
        sa.column("measurement_basis", sa.String()),
        sa.column("canonical_quantity", sa.Numeric()),
        sa.column("canonical_unit", sa.String()),
        sa.column("edible_portion", sa.Numeric()),
        sa.column("data_version", sa.String()),
        sa.column("source_access_date", sa.Date()),
        sa.column("dietary_patterns", sa.JSON()),
    )
    roles = sa.table(
        "nutrition_catalogue_food_roles",
        sa.column("food_id", sa.Uuid()),
        sa.column("role", sa.String()),
    )
    aliases = sa.table(
        "nutrition_catalogue_food_aliases",
        sa.column("id", sa.Uuid()),
        sa.column("food_id", sa.Uuid()),
        sa.column("alias", sa.String()),
        sa.column("normalized_alias", sa.String()),
        sa.column("language", sa.String()),
    )
    compositions = sa.table(
        "nutrition_food_compositions",
        sa.column("id", sa.Uuid()),
        sa.column("food_id", sa.Uuid()),
        sa.column("nutrient_code", sa.String()),
        sa.column("value_per_100g", sa.Numeric()),
        sa.column("unit", sa.String()),
        sa.column("unit_form", sa.String()),
        sa.column("source_name", sa.String()),
        sa.column("source_reference", sa.String()),
        sa.column("source_food_id", sa.String()),
        sa.column("data_version", sa.String()),
        sa.column("source_access_date", sa.Date()),
        sa.column("confidence", sa.String()),
    )
    connection.execute(
        foods.update()
        .where(foods.c.slug.in_(("cooked-basmati-rice", "grilled-chicken-breast")))
        .values(verification_status="retired")
    )
    access_date = date.fromisoformat(USDA_ACCESS_DATE)
    for item in APPROVED_FOODS:
        nutrients = composition_for(item.slug)
        food_id = uuid5(NAMESPACE_URL, f"fitsho:nutrition:food:{item.slug}")
        values = {
            "id": food_id,
            "slug": item.slug,
            "name_fa": item.name_fa,
            "name_en": item.name_en,
            "verification_status": "verified" if nutrients else "draft",
            "source_name": USDA_SOURCE_NAME if nutrients else "Fitsho approved vocabulary",
            "source_reference": USDA_SOURCE_REFERENCE,
            "source_food_id": item.source_food_id,
            "category": item.category,
            "measurement_basis": item.measurement_basis,
            "canonical_quantity": 100,
            "canonical_unit": "g",
            "edible_portion": 1,
            "data_version": USDA_DATA_VERSION if nutrients else "awaiting-regional-source",
            "source_access_date": access_date if nutrients else None,
            "dietary_patterns": _dietary_patterns(item.slug),
        }
        connection.execute(
            insert(foods)
            .values(**values)
            .on_conflict_do_update(
                index_elements=[foods.c.slug],
                set_={key: value for key, value in values.items() if key not in {"id", "slug"}},
            )
        )
        stored_id = connection.scalar(sa.select(foods.c.id).where(foods.c.slug == item.slug))
        assert stored_id is not None
        connection.execute(roles.delete().where(roles.c.food_id == stored_id))
        connection.execute(aliases.delete().where(aliases.c.food_id == stored_id))
        connection.execute(compositions.delete().where(compositions.c.food_id == stored_id))
        connection.execute(
            roles.insert(), [{"food_id": stored_id, "role": role} for role in item.roles]
        )
        connection.execute(
            aliases.insert(),
            [
                {
                    "id": uuid5(
                        NAMESPACE_URL,
                        f"fitsho:nutrition:food:{item.slug}:alias:{_normalize(alias)}",
                    ),
                    "food_id": stored_id,
                    "alias": alias,
                    "normalized_alias": _normalize(alias),
                    "language": "fa"
                    if any("\u0600" <= char <= "\u06ff" for char in alias)
                    else "en",
                }
                for alias in dict.fromkeys(item.aliases)
            ],
        )
        if nutrients:
            connection.execute(
                compositions.insert(),
                [
                    {
                        "id": uuid5(
                            NAMESPACE_URL,
                            f"fitsho:nutrition:food:{item.slug}:nutrient:{code}",
                        ),
                        "food_id": stored_id,
                        "nutrient_code": code,
                        "value_per_100g": value,
                        "unit": NUTRIENT_UNITS[code],
                        "unit_form": "dietary_folate_equivalents"
                        if code == "folate_dfe_mcg"
                        else "nutrient_mass",
                        "source_name": USDA_SOURCE_NAME,
                        "source_reference": USDA_SOURCE_REFERENCE,
                        "source_food_id": item.source_food_id,
                        "data_version": USDA_DATA_VERSION,
                        "source_access_date": access_date,
                        "confidence": "high",
                    }
                    for code, value in nutrients.items()
                ],
            )


def _normalize(value: str) -> str:
    return " ".join(value.strip().casefold().replace("ي", "ی").replace("ك", "ک").split())


def _dietary_patterns(slug: str) -> list[str]:
    if slug in {
        "chicken-breast",
        "chicken-thigh-skinless",
        "beef",
        "lamb",
        "white-fish",
        "rainbow-trout",
        "canned-tuna",
    }:
        return ["omnivore"]
    if slug in {"egg", "milk", "plain-yogurt", "low-fat-cheese", "butter"}:
        return ["omnivore", "vegetarian"]
    return ["omnivore", "vegetarian", "vegan"]
