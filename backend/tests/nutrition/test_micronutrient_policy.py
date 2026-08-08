from sqlalchemy import select
from sqlalchemy.orm import Session

from app.nutrition.enums import MicronutrientReferenceKind
from app.nutrition.models import (
    MicronutrientPolicyVersion,
    MicronutrientReference,
    MicronutrientSource,
)


def test_seeded_policy_has_authoritative_sources_and_core_adult_rows(db: Session) -> None:
    policy = db.get(MicronutrientPolicyVersion, "micronutrient-dri-v1")
    assert policy is not None
    assert policy.source_manifest["primary"] == "NASEM DRI collection"
    assert policy.source_manifest["deficiency_diagnosis"] is False
    assert policy.source_manifest["vitamin_d_conversion"] == "1 mcg vitamin D = 40 IU"
    assert policy.completeness_thresholds["minimum_supported_nutrient_coverage"] == 0.8
    assert "medical override" in policy.medical_override_precedence

    sources = db.scalars(
        select(MicronutrientSource).where(
            MicronutrientSource.policy_version == "micronutrient-dri-v1"
        )
    ).all()
    assert any(source.organization.startswith("National Academies") for source in sources)
    assert any(source.organization == "NIH Office of Dietary Supplements" for source in sources)

    zinc_male = db.scalar(
        select(MicronutrientReference).where(
            MicronutrientReference.policy_version == "micronutrient-dri-v1",
            MicronutrientReference.nutrient_code == "zinc",
            MicronutrientReference.reference_kind == MicronutrientReferenceKind.RDA,
            MicronutrientReference.age_min == 19,
            MicronutrientReference.sex == "male",
        )
    )
    assert zinc_male is not None
    assert zinc_male.target_value == 11
    assert zinc_male.unit == "mg"
    assert zinc_male.unit_form == "nutrient_mass"

    vitamin_d = db.scalar(
        select(MicronutrientReference).where(
            MicronutrientReference.policy_version == "micronutrient-dri-v1",
            MicronutrientReference.nutrient_code == "vitamin_d",
            MicronutrientReference.reference_kind == MicronutrientReferenceKind.RDA,
        )
    )
    assert vitamin_d is not None
    assert vitamin_d.unit_conversion == {"from": "mcg", "to": "iu", "multiplier": 40}

    folate = db.scalar(
        select(MicronutrientReference).where(
            MicronutrientReference.policy_version == "micronutrient-dri-v1",
            MicronutrientReference.nutrient_code == "folate",
        )
    )
    assert folate is not None
    assert folate.unit == "mcg_dfe"
    assert folate.unit_form == "dietary_folate_equivalent"


def test_policy_preserves_ai_cdrr_and_upper_limit_scope_semantics(db: Session) -> None:
    potassium = db.scalars(
        select(MicronutrientReference).where(
            MicronutrientReference.policy_version == "micronutrient-dri-v1",
            MicronutrientReference.nutrient_code == "potassium",
        )
    ).all()
    sodium = db.scalars(
        select(MicronutrientReference).where(
            MicronutrientReference.policy_version == "micronutrient-dri-v1",
            MicronutrientReference.nutrient_code == "sodium",
        )
    ).all()

    assert {row.reference_kind for row in potassium} == {MicronutrientReferenceKind.AI}
    assert {row.reference_kind for row in sodium} == {
        MicronutrientReferenceKind.AI,
        MicronutrientReferenceKind.CDRR,
    }
    assert not any(row.reference_kind is MicronutrientReferenceKind.UL for row in potassium)
    assert not any(row.reference_kind is MicronutrientReferenceKind.UL for row in sodium)
