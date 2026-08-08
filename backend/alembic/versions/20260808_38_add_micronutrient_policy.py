"""add versioned micronutrient reference policy foundation"""

from collections.abc import Sequence
from datetime import date, datetime
from decimal import Decimal
from uuid import uuid4

import sqlalchemy as sa

from alembic import op

revision: str = "20260808_38"
down_revision: str | Sequence[str] | None = "20260808_37"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ACCESS_DATE = date(2026, 8, 8)
NASEM_URL = "https://nap.nationalacademies.org/collection/57/dietary-reference-intakes"
SODIUM_URL = "https://nap.nationalacademies.org/catalog/25353/dietary-reference-intakes-for-sodium-and-potassium"
ODS_URLS = {
    "calcium": "https://ods.od.nih.gov/factsheets/Calcium-HealthProfessional/",
    "iron": "https://ods.od.nih.gov/factsheets/Iron-HealthProfessional/",
    "magnesium": "https://ods.od.nih.gov/factsheets/Magnesium-HealthProfessional/",
    "zinc": "https://ods.od.nih.gov/factsheets/Zinc-HealthProfessional/",
    "vitamin_c": "https://ods.od.nih.gov/factsheets/VitaminC-HealthProfessional/",
    "vitamin_d": "https://ods.od.nih.gov/factsheets/VitaminD-HealthProfessional/",
    "vitamin_b12": "https://ods.od.nih.gov/factsheets/VitaminB12-HealthProfessional/",
    "folate": "https://ods.od.nih.gov/factsheets/Folate-HealthProfessional/",
    "potassium": "https://ods.od.nih.gov/factsheets/Potassium-HealthProfessional/",
}


def upgrade() -> None:
    op.create_table(
        "nutrition_micronutrient_policy_versions",
        sa.Column("version", sa.String(length=64), primary_key=True),
        sa.Column("description", sa.String(length=300), nullable=False),
        sa.Column("source_manifest", sa.JSON(), nullable=False),
        sa.Column("adequacy_scoring", sa.JSON(), nullable=False),
        sa.Column("completeness_thresholds", sa.JSON(), nullable=False),
        sa.Column("repair_tolerances", sa.JSON(), nullable=False),
        sa.Column("medical_override_precedence", sa.String(length=300), nullable=False),
        sa.Column("effective_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_table(
        "nutrition_micronutrient_sources",
        sa.Column("source_id", sa.String(length=96), primary_key=True),
        sa.Column("organization", sa.String(length=160), nullable=False),
        sa.Column("reference_url", sa.String(length=500), nullable=False),
        sa.Column("publication_date", sa.Date()),
        sa.Column("access_date", sa.Date(), nullable=False),
        sa.Column("policy_version", sa.String(length=64), nullable=False),
        sa.Column("notes", sa.String(length=1000)),
        sa.ForeignKeyConstraint(
            ["policy_version"],
            ["nutrition_micronutrient_policy_versions.version"],
            ondelete="RESTRICT",
        ),
    )
    op.create_index(
        "ix_nutrition_micronutrient_sources_policy_version",
        "nutrition_micronutrient_sources",
        ["policy_version"],
    )
    op.create_table(
        "nutrition_micronutrient_references",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("policy_version", sa.String(length=64), nullable=False),
        sa.Column("nutrient_code", sa.String(length=48), nullable=False),
        sa.Column("reference_kind", sa.String(length=24), nullable=False),
        sa.Column("target_value", sa.Numeric(20, 8), nullable=False),
        sa.Column("unit", sa.String(length=24), nullable=False),
        sa.Column("unit_form", sa.String(length=48), nullable=False),
        sa.Column("unit_conversion", sa.JSON()),
        sa.Column("age_min", sa.SmallInteger(), nullable=False),
        sa.Column("age_max", sa.SmallInteger()),
        sa.Column("sex", sa.String(length=16), nullable=False),
        sa.Column("life_stage", sa.String(length=48), nullable=False),
        sa.Column("dietary_pattern_modifier", sa.String(length=48), nullable=False),
        sa.Column("modifier_multiplier_or_delta", sa.Numeric(20, 8)),
        sa.Column("upper_limit_scope", sa.String(length=32), nullable=False),
        sa.Column("aggregation_window", sa.String(length=24), nullable=False),
        sa.Column("source_organization", sa.String(length=160), nullable=False),
        sa.Column("source_reference", sa.String(length=500), nullable=False),
        sa.Column("source_date", sa.Date()),
        sa.Column("access_date", sa.Date(), nullable=False),
        sa.Column("source_id", sa.String(length=96), nullable=False),
        sa.Column("notes", sa.String(length=1000)),
        sa.ForeignKeyConstraint(
            ["policy_version"],
            ["nutrition_micronutrient_policy_versions.version"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["source_id"], ["nutrition_micronutrient_sources.source_id"], ondelete="RESTRICT"
        ),
        sa.CheckConstraint("age_min >= 0", name="ck_nutrition_micro_refs_age_min"),
        sa.CheckConstraint(
            "age_max IS NULL OR age_max >= age_min", name="ck_nutrition_micro_refs_age_order"
        ),
        sa.CheckConstraint("target_value >= 0", name="ck_nutrition_micro_refs_target_nonnegative"),
        sa.CheckConstraint(
            "reference_kind IN ('rda', 'ai', 'ear', 'ul', 'cdrr', 'medical_override')",
            name="ck_nutrition_micro_refs_kind_values",
        ),
        sa.CheckConstraint(
            "sex IN ('all', 'male', 'female')", name="ck_nutrition_micro_refs_sex_values"
        ),
        sa.CheckConstraint(
            "upper_limit_scope IN ('none', 'total_intake', 'supplemental_only', "
            "'source_form_specific')",
            name="ck_nutrition_micro_refs_ul_scope_values",
        ),
        sa.CheckConstraint(
            "aggregation_window IN ('daily', 'weekly_average')",
            name="ck_nutrition_micro_refs_window_values",
        ),
        sa.UniqueConstraint(
            "policy_version",
            "nutrient_code",
            "reference_kind",
            "age_min",
            "age_max",
            "sex",
            "life_stage",
            "dietary_pattern_modifier",
            name="uq_nutrition_micro_refs_population",
        ),
    )
    op.create_index(
        "ix_nutrition_micronutrient_references_policy_version",
        "nutrition_micronutrient_references",
        ["policy_version"],
    )
    op.create_index(
        "ix_nutrition_micronutrient_references_nutrient_code",
        "nutrition_micronutrient_references",
        ["nutrient_code"],
    )

    policy = sa.table(
        "nutrition_micronutrient_policy_versions",
        sa.column("version", sa.String),
        sa.column("description", sa.String),
        sa.column("source_manifest", sa.JSON),
        sa.column("adequacy_scoring", sa.JSON),
        sa.column("completeness_thresholds", sa.JSON),
        sa.column("repair_tolerances", sa.JSON),
        sa.column("medical_override_precedence", sa.String),
        sa.column("effective_at", sa.DateTime),
    )
    op.bulk_insert(
        policy,
        [
            {
                "version": "micronutrient-dri-v1",
                "description": "Adult micronutrient DRI semantics and core reference rows",
                "source_manifest": {
                    "primary": "NASEM DRI collection",
                    "cross_check": "NIH ODS Health Professional Fact Sheets",
                    "research_date": "2026-08-08",
                    "deficiency_diagnosis": False,
                    "supported_units": ["mg", "mcg", "mcg_dfe", "mcg_rae", "iu"],
                    "vitamin_d_conversion": "1 mcg vitamin D = 40 IU",
                    "usda_mapping": {
                        "composition_source": "USDA FoodData Central",
                        "requirements_source_is_separate": True,
                        "mapping_requires_provenance_and_unit_review": True,
                    },
                },
                "adequacy_scoring": {
                    "target_preference": ["rda", "ai"],
                    "ear_is_not_personal_minimum": True,
                    "ul_is_safety_ceiling": True,
                    "score_range": [0, 100],
                    "weekly_average_default": True,
                },
                "completeness_thresholds": {
                    "minimum_supported_nutrient_coverage": 0.8,
                    "minimum_measured_days_for_weekly_average": 4,
                    "missing_data_is_not_zero": True,
                },
                "repair_tolerances": {
                    "max_iterations": 3,
                    "max_daily_calorie_delta_percent": 5,
                    "max_macro_delta_percent": 5,
                    "reject_new_hard_safety_violation": True,
                },
                "medical_override_precedence": (
                    "approved medical override > nutrient-specific safety limit > "
                    "healthy-population DRI"
                ),
                "effective_at": datetime(2026, 8, 8),
            }
        ],
    )
    sources = sa.table(
        "nutrition_micronutrient_sources",
        sa.column("source_id", sa.String),
        sa.column("organization", sa.String),
        sa.column("reference_url", sa.String),
        sa.column("publication_date", sa.Date),
        sa.column("access_date", sa.Date),
        sa.column("policy_version", sa.String),
        sa.column("notes", sa.String),
    )
    source_rows = [
        {
            "source_id": "nasem-dri-collection",
            "organization": "National Academies of Sciences, Engineering, and Medicine",
            "reference_url": NASEM_URL,
            "publication_date": None,
            "access_date": ACCESS_DATE,
            "policy_version": "micronutrient-dri-v1",
            "notes": "Primary authority for DRI reference kinds and population tables.",
        },
        {
            "source_id": "nasem-sodium-potassium-2019",
            "organization": "National Academies of Sciences, Engineering, and Medicine",
            "reference_url": SODIUM_URL,
            "publication_date": date(2019, 3, 5),
            "access_date": ACCESS_DATE,
            "policy_version": "micronutrient-dri-v1",
            "notes": "Sodium AI/CDRR and potassium AI semantics; no fabricated sodium UL.",
        },
    ]
    for nutrient, url in ODS_URLS.items():
        source_rows.append(
            {
                "source_id": f"nih-ods-{nutrient}",
                "organization": "NIH Office of Dietary Supplements",
                "reference_url": url,
                "publication_date": None,
                "access_date": ACCESS_DATE,
                "policy_version": "micronutrient-dri-v1",
                "notes": (
                    "Cross-check for current values, units, forms, and interpretation caveats."
                ),
            }
        )
    op.bulk_insert(sources, source_rows)

    refs = sa.table(
        "nutrition_micronutrient_references",
        *[
            sa.column(name, type_)
            for name, type_ in [
                ("id", sa.Uuid()),
                ("policy_version", sa.String),
                ("nutrient_code", sa.String),
                ("reference_kind", sa.String),
                ("target_value", sa.Numeric),
                ("unit", sa.String),
                ("unit_form", sa.String),
                ("unit_conversion", sa.JSON),
                ("age_min", sa.SmallInteger),
                ("age_max", sa.SmallInteger),
                ("sex", sa.String),
                ("life_stage", sa.String),
                ("dietary_pattern_modifier", sa.String),
                ("modifier_multiplier_or_delta", sa.Numeric),
                ("upper_limit_scope", sa.String),
                ("aggregation_window", sa.String),
                ("source_organization", sa.String),
                ("source_reference", sa.String),
                ("source_date", sa.Date),
                ("access_date", sa.Date),
                ("source_id", sa.String),
                ("notes", sa.String),
            ]
        ],
    )
    rows: list[dict[str, object]] = []

    def add(
        nutrient: str,
        kind: str,
        value: str,
        unit: str,
        age_min: int,
        age_max: int | None,
        sex: str,
        source_id: str,
        *,
        unit_form: str = "unspecified",
        unit_conversion: dict[str, object] | None = None,
        scope: str = "none",
        window: str = "weekly_average",
        modifier: str = "none",
        modifier_value: str | None = None,
        notes: str | None = None,
    ) -> None:
        if unit_form == "unspecified":
            unit_form = {
                "mcg_dfe": "dietary_folate_equivalent",
                "mcg_rae": "retinol_activity_equivalent",
                "iu": "international_unit",
            }.get(unit, "nutrient_mass")
        if nutrient == "vitamin_d" and unit_conversion is None:
            unit_conversion = {"from": "mcg", "to": "iu", "multiplier": 40}
        source_url = NASEM_URL if source_id.startswith("nasem") else ODS_URLS[nutrient]
        rows.append(
            {
                "id": uuid4(),
                "policy_version": "micronutrient-dri-v1",
                "nutrient_code": nutrient,
                "reference_kind": kind,
                "target_value": Decimal(value),
                "unit": unit,
                "unit_form": unit_form,
                "unit_conversion": unit_conversion,
                "age_min": age_min,
                "age_max": age_max,
                "sex": sex,
                "life_stage": "adult",
                "dietary_pattern_modifier": modifier,
                "modifier_multiplier_or_delta": Decimal(modifier_value) if modifier_value else None,
                "upper_limit_scope": scope,
                "aggregation_window": window,
                "source_organization": (
                    "National Academies of Sciences, Engineering, and Medicine"
                    if source_id.startswith("nasem")
                    else "NIH Office of Dietary Supplements"
                ),
                "source_reference": source_url,
                "source_date": (
                    date(2019, 3, 5)
                    if source_id == "nasem-sodium-potassium-2019"
                    else None
                ),
                "access_date": ACCESS_DATE,
                "source_id": source_id,
                "notes": notes,
            }
        )

    core = [
        ("zinc", "rda", "11", "mg", 18, 18, "male", "nih-ods-zinc"),
        ("zinc", "rda", "9", "mg", 18, 18, "female", "nih-ods-zinc"),
        ("zinc", "rda", "11", "mg", 19, None, "male", "nih-ods-zinc"),
        ("zinc", "rda", "8", "mg", 19, None, "female", "nih-ods-zinc"),
        ("calcium", "rda", "1300", "mg", 18, 18, "all", "nih-ods-calcium"),
        ("calcium", "rda", "1000", "mg", 19, 50, "all", "nih-ods-calcium"),
        ("potassium", "ai", "3000", "mg", 18, 18, "male", "nasem-sodium-potassium-2019"),
        ("potassium", "ai", "2300", "mg", 18, 18, "female", "nasem-sodium-potassium-2019"),
        ("potassium", "ai", "3400", "mg", 19, None, "male", "nasem-sodium-potassium-2019"),
        ("potassium", "ai", "2600", "mg", 19, None, "female", "nasem-sodium-potassium-2019"),
        ("magnesium", "rda", "410", "mg", 18, 18, "male", "nih-ods-magnesium"),
        ("magnesium", "rda", "360", "mg", 18, 18, "female", "nih-ods-magnesium"),
        ("magnesium", "rda", "400", "mg", 19, 30, "male", "nih-ods-magnesium"),
        ("magnesium", "rda", "310", "mg", 19, 30, "female", "nih-ods-magnesium"),
        ("magnesium", "rda", "420", "mg", 31, 50, "male", "nih-ods-magnesium"),
        ("magnesium", "rda", "320", "mg", 31, 50, "female", "nih-ods-magnesium"),
        ("iron", "rda", "11", "mg", 18, 18, "male", "nih-ods-iron"),
        ("iron", "rda", "15", "mg", 18, 18, "female", "nih-ods-iron"),
        ("iron", "rda", "8", "mg", 19, 50, "male", "nih-ods-iron"),
        ("iron", "rda", "18", "mg", 19, 50, "female", "nih-ods-iron"),
        ("vitamin_c", "rda", "75", "mg", 18, 18, "male", "nih-ods-vitamin_c"),
        ("vitamin_c", "rda", "65", "mg", 18, 18, "female", "nih-ods-vitamin_c"),
        ("vitamin_c", "rda", "90", "mg", 19, None, "male", "nih-ods-vitamin_c"),
        ("vitamin_c", "rda", "75", "mg", 19, None, "female", "nih-ods-vitamin_c"),
        ("vitamin_d", "rda", "15", "mcg", 18, 70, "all", "nih-ods-vitamin_d"),
        ("vitamin_d", "rda", "20", "mcg", 71, None, "all", "nih-ods-vitamin_d"),
        ("vitamin_b12", "rda", "2.4", "mcg", 18, None, "all", "nih-ods-vitamin_b12"),
        ("folate", "rda", "400", "mcg_dfe", 18, None, "all", "nih-ods-folate"),
        ("sodium", "ai", "1500", "mg", 18, None, "all", "nasem-sodium-potassium-2019"),
        ("sodium", "cdrr", "2300", "mg", 18, None, "all", "nasem-sodium-potassium-2019",),
    ]
    for item in core:
        add(*item)
    for nutrient, value, unit, age_min, age_max, scope, source_id in [
        ("zinc", "34", "mg", 18, None, "total_intake", "nih-ods-zinc"),
        ("calcium", "2500", "mg", 19, 50, "total_intake", "nih-ods-calcium"),
        ("magnesium", "350", "mg", 18, None, "supplemental_only", "nih-ods-magnesium"),
        ("iron", "45", "mg", 18, None, "total_intake", "nih-ods-iron"),
        ("vitamin_c", "2000", "mg", 18, None, "total_intake", "nih-ods-vitamin_c"),
        ("vitamin_d", "100", "mcg", 18, None, "total_intake", "nih-ods-vitamin_d"),
        ("folate", "1000", "mcg", 18, None, "supplemental_only", "nih-ods-folate"),
    ]:
        add(
            nutrient,
            "ul",
            value,
            unit,
            age_min,
            age_max,
            "all",
            source_id,
            scope=scope,
            window="daily",
        )
    op.bulk_insert(refs, rows)


def downgrade() -> None:
    op.drop_index(
        "ix_nutrition_micronutrient_references_nutrient_code",
        table_name="nutrition_micronutrient_references",
    )
    op.drop_index(
        "ix_nutrition_micronutrient_references_policy_version",
        table_name="nutrition_micronutrient_references",
    )
    op.drop_table("nutrition_micronutrient_references")
    op.drop_index(
        "ix_nutrition_micronutrient_sources_policy_version",
        table_name="nutrition_micronutrient_sources",
    )
    op.drop_table("nutrition_micronutrient_sources")
    op.drop_table("nutrition_micronutrient_policy_versions")
