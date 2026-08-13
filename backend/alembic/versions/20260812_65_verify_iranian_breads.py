"""verify source-backed Iranian breads"""

from collections.abc import Sequence
from datetime import date
from decimal import Decimal
from uuid import NAMESPACE_URL, uuid5

import sqlalchemy as sa

from alembic import op

revision: str = "20260812_65"
down_revision: str | Sequence[str] | None = "20260812_64"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

MACRO_SOURCE_NAME = "Glycemic Index Values for Major Carbohydrates in Iran"
MACRO_SOURCE_REFERENCE = "https://doi.org/10.5812/ijem.99793"
MACRO_DATA_VERSION = "ijem-2020-e99793"
MICRO_SOURCE_NAME = "Evaluation of nutrients in bread: a systematic review"
MICRO_SOURCE_REFERENCE = "https://doi.org/10.1186/s41043-022-00327-9"
MICRO_DATA_VERSION = "jhpn-2022-41-50"
PORTION_SOURCE_NAME = "Iran Ministry of Health nutrition training package"
PORTION_SOURCE_REFERENCE = "https://sedayesalmand.ir/cms/content/contentfile/download/580"
ACCESS_DATE = date(2026, 8, 12)

BREADS = {
    "sangak-bread": {
        "macro": ("258", "7.7", "57.4", "0.7", "4.1", "1.5"),
        "micro": {
            "potassium_mg": "110",
            "zinc_mg": "1.66",
            "copper_mg": "0.3445",
            "calcium_mg": "80.05",
        },
        "palm_grams": "30",
        "label_fa": "۱ کف دست بدون انگشت",
        "label_en": "1 palm without fingers",
    },
    "barbari-bread": {
        "macro": ("272", "8.4", "59.5", "0.6", "2.2", "0.8"),
        "micro": {"potassium_mg": "112", "zinc_mg": "0.884", "copper_mg": "0.218"},
        "palm_grams": "30",
        "label_fa": "۱ کف دست بدون انگشت",
        "label_en": "1 palm without fingers",
    },
    "taftoon-bread": {
        "macro": ("279", "8.1", "61.1", "0.7", "2.2", "0.8"),
        "micro": {"potassium_mg": "106", "zinc_mg": "1.35", "copper_mg": "0.289"},
        "palm_grams": "30",
        "label_fa": "۱ کف دست بدون انگشت",
        "label_en": "1 palm without fingers",
    },
    "lavash-bread": {
        "macro": ("291", "8.8", "63.4", "0.8", "2.4", "0.8"),
        "micro": {"potassium_mg": "103", "zinc_mg": "0.561", "copper_mg": "0.2805"},
        "palm_grams": "7.5",
        "label_fa": "۱ کف دست",
        "label_en": "1 palm",
    },
}
MACRO_CODES = (
    "energy_kcal",
    "protein_g",
    "carbohydrate_g",
    "total_fat_g",
    "fibre_g",
    "total_sugars_g",
)


def upgrade() -> None:
    connection = op.get_bind()
    foods = sa.table(
        "nutrition_catalogue_foods",
        sa.column("id", sa.Uuid()),
        sa.column("slug", sa.String()),
        sa.column("verification_status", sa.String()),
        sa.column("source_name", sa.String()),
        sa.column("source_reference", sa.String()),
        sa.column("source_food_id", sa.String()),
        sa.column("data_version", sa.String()),
        sa.column("source_access_date", sa.Date()),
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
    portions = sa.table(
        "nutrition_food_portions",
        sa.column("id", sa.Uuid()),
        sa.column("food_id", sa.Uuid()),
        sa.column("code", sa.String()),
        sa.column("quantity", sa.Numeric()),
        sa.column("label_fa", sa.String()),
        sa.column("label_en", sa.String()),
        sa.column("grams", sa.Numeric()),
        sa.column("is_default", sa.Boolean()),
        sa.column("sort_order", sa.Integer()),
        sa.column("source_name", sa.String()),
        sa.column("source_reference", sa.String()),
    )
    units = {
        "energy_kcal": "kcal",
        "protein_g": "g",
        "carbohydrate_g": "g",
        "total_fat_g": "g",
        "fibre_g": "g",
        "total_sugars_g": "g",
        "potassium_mg": "mg",
        "zinc_mg": "mg",
        "copper_mg": "mg",
        "calcium_mg": "mg",
    }
    for slug, bread in BREADS.items():
        food_id = connection.scalar(sa.select(foods.c.id).where(foods.c.slug == slug))
        if food_id is None:
            raise RuntimeError(f"Iranian bread is missing: {slug}")
        connection.execute(compositions.delete().where(compositions.c.food_id == food_id))
        connection.execute(
            portions.delete().where(portions.c.food_id == food_id, portions.c.code == "palm")
        )
        macro_values = bread["macro"]
        assert isinstance(macro_values, tuple)
        micro_values = bread["micro"]
        assert isinstance(micro_values, dict)
        rows = []
        for code, value in zip(MACRO_CODES, macro_values, strict=True):
            rows.append(_composition_row(food_id, slug, code, str(value), units[code], True))
        for code, value in micro_values.items():
            rows.append(_composition_row(food_id, slug, code, str(value), units[code], False))
        connection.execute(compositions.insert(), rows)
        connection.execute(
            portions.insert().values(
                id=uuid5(NAMESPACE_URL, f"fitsho:nutrition:food:{slug}:portion:palm"),
                food_id=food_id,
                code="palm",
                quantity=Decimal("1"),
                label_fa=str(bread["label_fa"]),
                label_en=str(bread["label_en"]),
                grams=Decimal(str(bread["palm_grams"])),
                is_default=True,
                sort_order=0,
                source_name=PORTION_SOURCE_NAME,
                source_reference=PORTION_SOURCE_REFERENCE,
            )
        )
        connection.execute(
            foods.update()
            .where(foods.c.id == food_id)
            .values(
                verification_status="verified",
                source_name=MACRO_SOURCE_NAME,
                source_reference=MACRO_SOURCE_REFERENCE,
                source_food_id=None,
                data_version=MACRO_DATA_VERSION,
                source_access_date=ACCESS_DATE,
            )
        )


def downgrade() -> None:
    connection = op.get_bind()
    foods = sa.table(
        "nutrition_catalogue_foods",
        sa.column("id", sa.Uuid()),
        sa.column("slug", sa.String()),
        sa.column("verification_status", sa.String()),
        sa.column("source_name", sa.String()),
        sa.column("source_reference", sa.String()),
        sa.column("source_food_id", sa.String()),
        sa.column("data_version", sa.String()),
        sa.column("source_access_date", sa.Date()),
    )
    compositions = sa.table("nutrition_food_compositions", sa.column("food_id", sa.Uuid()))
    portions = sa.table(
        "nutrition_food_portions", sa.column("food_id", sa.Uuid()), sa.column("code", sa.String())
    )
    for slug in BREADS:
        food_id = connection.scalar(sa.select(foods.c.id).where(foods.c.slug == slug))
        if food_id is None:
            continue
        connection.execute(compositions.delete().where(compositions.c.food_id == food_id))
        connection.execute(
            portions.delete().where(portions.c.food_id == food_id, portions.c.code == "palm")
        )
        connection.execute(
            foods.update()
            .where(foods.c.id == food_id)
            .values(
                verification_status="draft",
                source_name="Fitsho approved vocabulary",
                source_reference="https://fdc.nal.usda.gov/download-datasets/",
                source_food_id=None,
                data_version="awaiting-regional-source",
                source_access_date=None,
            )
        )


def _composition_row(
    food_id: object,
    slug: str,
    code: str,
    value: str,
    unit: str,
    macro: bool,
) -> dict[str, object]:
    return {
        "id": uuid5(NAMESPACE_URL, f"fitsho:nutrition:food:{slug}:composition:{code}"),
        "food_id": food_id,
        "nutrient_code": code,
        "value_per_100g": Decimal(value),
        "unit": unit,
        "unit_form": "nutrient_mass",
        "source_name": MACRO_SOURCE_NAME if macro else MICRO_SOURCE_NAME,
        "source_reference": MACRO_SOURCE_REFERENCE if macro else MICRO_SOURCE_REFERENCE,
        "source_food_id": None,
        "data_version": MACRO_DATA_VERSION if macro else MICRO_DATA_VERSION,
        "source_access_date": ACCESS_DATE,
        "confidence": "high",
    }
