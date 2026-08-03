from __future__ import annotations

import pytest
from pydantic import ValidationError
from sqlalchemy import UniqueConstraint

from app.body_analysis.enums import (
    BodyAnalysisClassification,
    BodyAnalysisStatus,
    BodyArea,
)
from app.body_analysis.normalization import MedicalClaimError, normalize_body_analysis
from app.body_analysis.schemas import NormalizedBodyAnalysis


def _valid_payload() -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "overall_confidence": 0.81,
        "findings": [
            {
                "body_area": "shoulders",
                "classification": "clear_lag",
                "severity": 0.78,
                "confidence": 0.86,
                "supporting_views": ["front", "back"],
                "explanation": (
                    "Shoulder development appears lower relative to visible torso proportions."
                ),
                "limitations": [],
                "suggested_training_emphasis": ["lateral_deltoid", "rear_deltoid"],
                "medical_review_recommended": False,
            },
            {
                "body_area": "hamstrings",
                "classification": "uncertain",
                "severity": None,
                "confidence": 0.39,
                "supporting_views": ["side", "back"],
                "explanation": "The area is not visible clearly enough for comparison.",
                "limitations": ["clothing_occlusion"],
                "suggested_training_emphasis": [],
                "medical_review_recommended": False,
            },
        ],
        "summary": {
            "visible_strengths": [],
            "priority_areas": ["shoulders"],
            "moderate_attention_areas": [],
            "uncertain_areas": ["hamstrings"],
        },
        "requires_coach_review": True,
        "requires_doctor_review": True,
    }


def test_normalizes_provider_independent_analysis() -> None:
    result = normalize_body_analysis(_valid_payload())

    assert isinstance(result, NormalizedBodyAnalysis)
    assert result.schema_version == "1.0"
    assert result.findings[0].body_area is BodyArea.SHOULDERS
    assert result.findings[0].classification is BodyAnalysisClassification.CLEAR_LAG
    assert result.findings[1].severity is None
    assert result.requires_coach_review is True
    assert result.requires_doctor_review is True


def test_rejects_unrecognized_body_area() -> None:
    payload = _valid_payload()
    findings = payload["findings"]
    assert isinstance(findings, list)
    finding = findings[0]
    assert isinstance(finding, dict)
    finding["body_area"] = "knee_injury"

    with pytest.raises(ValidationError):
        normalize_body_analysis(payload)


@pytest.mark.parametrize(
    "medical_claim",
    [
        "The user has scoliosis.",
        "This indicates an injured rotator cuff.",
        "A medical diagnosis of arthritis is visible.",
        "The image proves a fracture.",
        "A torn tendon is visible.",
        "This diagnoses osteoporosis.",
        "Kyphosis is present.",
        "Shoulder impingement is visible.",
        "This medical condition is confirmed.",
        "The images show a musculoskeletal disorder.",
        "Inflammation is present.",
    ],
)
def test_rejects_medical_diagnostic_claims(medical_claim: str) -> None:
    payload = _valid_payload()
    findings = payload["findings"]
    assert isinstance(findings, list)
    finding = findings[0]
    assert isinstance(finding, dict)
    finding["explanation"] = medical_claim

    with pytest.raises(MedicalClaimError):
        normalize_body_analysis(payload)


def test_allows_visible_development_language_without_medical_claim() -> None:
    payload = _valid_payload()
    findings = payload["findings"]
    assert isinstance(findings, list)
    finding = findings[0]
    assert isinstance(finding, dict)
    finding["explanation"] = (
        "Shoulders appear visibly less developed than the chest in these images."
    )

    result = normalize_body_analysis(payload)

    assert result.findings[0].classification is BodyAnalysisClassification.CLEAR_LAG


@pytest.mark.parametrize("classification", ["mild_lag", "clear_lag"])
def test_actionable_lag_requires_bounded_severity(classification: str) -> None:
    payload = _valid_payload()
    findings = payload["findings"]
    assert isinstance(findings, list)
    finding = findings[0]
    assert isinstance(finding, dict)
    finding["classification"] = classification
    finding["severity"] = None
    summary = payload["summary"]
    assert isinstance(summary, dict)
    summary["priority_areas"] = []
    summary["moderate_attention_areas"] = ["shoulders"]
    if classification == "clear_lag":
        summary["priority_areas"] = ["shoulders"]
        summary["moderate_attention_areas"] = []

    with pytest.raises(ValidationError):
        normalize_body_analysis(payload)


def test_rejects_unknown_fields_and_malformed_confidence() -> None:
    payload = _valid_payload()
    payload["provider_secret"] = "must-not-be-accepted"
    payload["overall_confidence"] = 1.2

    with pytest.raises(ValidationError):
        normalize_body_analysis(payload)


def test_uncertain_finding_cannot_add_training_emphasis() -> None:
    payload = _valid_payload()
    findings = payload["findings"]
    assert isinstance(findings, list)
    finding = findings[1]
    assert isinstance(finding, dict)
    finding["suggested_training_emphasis"] = ["hamstrings"]

    with pytest.raises(ValidationError):
        normalize_body_analysis(payload)


def test_summary_must_match_finding_classifications() -> None:
    payload = _valid_payload()
    summary = payload["summary"]
    assert isinstance(summary, dict)
    summary["visible_strengths"] = ["shoulders"]

    with pytest.raises(ValidationError):
        normalize_body_analysis(payload)


def test_analysis_status_values_are_stable() -> None:
    assert BodyAnalysisStatus.QUEUED.value == "queued"
    assert BodyAnalysisStatus.REVIEW_PENDING.value == "review_pending"
    assert BodyAnalysisStatus.COMPLETED.value == "completed"


def test_body_analysis_persistence_contract_is_versioned() -> None:
    from app.body_analysis.models import BodyAnalysis

    table = BodyAnalysis.__table__
    assert next(iter(table.c.session_id.foreign_keys)).target_fullname == "body_photo_sessions.id"
    assert table.c.revision.nullable is False
    assert table.c.raw_result.nullable is True
    assert table.c.normalized_result.nullable is True
    assert table.c.request_cost.type.scale == 8
    assert any(
        isinstance(constraint, UniqueConstraint)
        and tuple(constraint.columns.keys()) == ("session_id", "revision")
        for constraint in table.constraints
    )
