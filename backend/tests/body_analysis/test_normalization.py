from __future__ import annotations

import inspect

import pytest
from pydantic import ValidationError
from sqlalchemy import UniqueConstraint

import app.body_analysis.normalization as normalization
from app.body_analysis.enums import (
    BodyAnalysisClassification,
    BodyAnalysisStatus,
    BodyArea,
)
from app.body_analysis.normalization import MedicalClaimError, normalize_body_analysis
from app.body_analysis.schemas import NormalizedBodyAnalysis

_V4_AREAS = [
    "shoulders",
    "chest",
    "back",
    "lats",
    "arms",
    "forearms",
    "waist_midsection",
    "glutes",
    "quads",
    "hamstrings",
    "calves",
]


def _v4_payload() -> dict[str, object]:
    return {
        "schema_version": "4.0",
        "assessment_status": "complete",
        "area_observations": [
            {
                "area": area,
                "classification": "balanced",
                "evidence_strength": "moderate",
                "supporting_views": ["front", "side"],
                "observation_tags": ["relative_width"],
                "limitation_codes": [],
                "suggested_training_emphasis": [],
            }
            for area in _V4_AREAS
        ],
        "upper_lower_balance": {
            "state": "balanced",
            "evidence_strength": "moderate",
            "supporting_views": ["front", "side"],
        },
        "visible_symmetry": {
            "state": "no_clear_difference",
            "evidence_strength": "moderate",
            "supporting_views": ["front", "back"],
        },
    }


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


def test_normalizes_schema_v2_visual_assessment_and_derives_legacy_projection() -> None:
    areas = [
        "shoulders",
        "chest",
        "back",
        "lats",
        "arms",
        "forearms",
        "waist_midsection",
        "glutes",
        "quads",
        "hamstrings",
        "calves",
        "symmetry",
        "visible_alignment_or_posture",
    ]
    payload = {
        "assessment_status": "complete",
        "photo_quality": {
            "front": {"usable": True, "issues_fa": []},
            "side": {"usable": True, "issues_fa": []},
            "back": {"usable": True, "issues_fa": []},
            "global_limitations_fa": [],
        },
        "overall_assessment": {
            "development_pattern": "mixed",
            "shoulder_to_waist_taper": "moderate",
            "upper_lower_balance": "balanced",
            "summary_fa": "تناسب کلی بدن در نماهای موجود بررسی شد.",
        },
        "findings": [
            {
                "area": area,
                "classification": "clear_lag" if area == "lats" else "neutral",
                "severity": 0.72 if area == "lats" else None,
                "confidence": 0.8,
                "views_used": ["back"],
                "evidence_fa": "شواهد صرفاً از نمای قابل مشاهده ثبت شده است.",
                "suggested_training_emphasis": ["lat_width"] if area == "lats" else [],
            }
            for area in areas
        ],
    }

    visual = normalization.normalize_visual_physique_assessment(payload)
    legacy = normalization.visual_assessment_to_normalized(visual)

    assert visual.human_coach_review_required is True
    assert visual.medical_review_recommended is False
    assert len(visual.findings) == 13
    assert legacy.schema_version == "2.0"
    assert legacy.summary.priority_areas == ("lats",)
    assert legacy.findings[3].suggested_training_emphasis == ("back_width",)


def test_normalizes_schema_v3_checklist_and_projects_program_priorities() -> None:
    from app.body_analysis.normalization import (
        normalize_visual_physique_assessment_v3,
        visual_assessment_v3_to_normalized,
    )

    areas = [area.value for area in BodyArea]
    payload = {
        "assessment_status": "complete",
        "photo_quality": {
            "front": {"usable": True, "issues_fa": []},
            "side": {"usable": True, "issues_fa": []},
            "back": {"usable": True, "issues_fa": []},
            "global_limitations_fa": [],
        },
        "overall_assessment": {
            "development_pattern": "mixed",
            "shoulder_to_waist_taper": "moderate",
            "upper_lower_balance": "balanced",
            "summary_fa": "تناسب کلی بر پایهٔ نماهای قابل مشاهده بررسی شد.",
        },
        "goal_suggestion": {
            "suggested_goal": "build_muscle",
            "reasoning_fa": "هدف فعلی کاربر با تناسب قابل مشاهده و داده‌های ثبت‌شده هم‌راستاست.",
            "inputs_unavailable_fa": ["اندازهٔ دور شانه ثبت نشده است."],
        },
        "findings": [
            {
                "area": area,
                "front": {
                    "rating": "average",
                    "evidence_fa": "نمای روبه‌رو برای مقایسه قابل استفاده است.",
                },
                "side": {
                    "rating": "average",
                    "evidence_fa": "نمای نیمرخ برای مقایسه قابل استفاده است.",
                },
                "back": {
                    "rating": "average",
                    "evidence_fa": "نمای پشت برای مقایسه قابل استفاده است.",
                },
                "overall_rating": "focus_priority" if area == "lats" else "average",
                "overall_summary_fa": "جمع‌بندی فقط بر پایهٔ تناسب قابل مشاهده است.",
                "confidence": 0.8,
                "suggested_training_emphasis": ["lat_width"] if area == "lats" else [],
            }
            for area in areas
        ],
    }
    lats = next(item for item in payload["findings"] if item["area"] == "lats")
    lats["back"] = {
        "rating": "focus_priority",
        "evidence_fa": "در نمای پشت عرض لت‌ها نسبت به بالاتنه کمتر دیده می‌شود.",
    }

    visual = normalize_visual_physique_assessment_v3(payload)
    normalized = visual_assessment_v3_to_normalized(visual)

    assert visual.goal_suggestion.suggested_goal == "build_muscle"
    assert len(visual.findings) == 13
    assert normalized.schema_version == "3.0"
    assert normalized.summary.priority_areas == (BodyArea.LATS,)
    assert normalized.findings[3].suggested_training_emphasis == ("back_width",)


def test_normalizes_schema_v4_evidence_and_projects_posture_as_uncertain() -> None:
    normalizer = getattr(normalization, "normalize_visual_physique_assessment_v4", None)
    projector = getattr(normalization, "visual_assessment_v4_to_normalized", None)
    assert normalizer is not None
    assert projector is not None
    assert tuple(inspect.signature(projector).parameters) == ("assessment",)

    evidence = normalizer(_v4_payload())
    normalized = projector(evidence)

    assert evidence.schema_version == "4.0"
    assert len(evidence.area_observations) == 11
    assert normalized.schema_version == "4.0"
    assert normalized.overall_confidence == 0.85
    posture = next(
        finding
        for finding in normalized.findings
        if finding.body_area is BodyArea.VISIBLE_ALIGNMENT_OR_POSTURE
    )
    assert posture.classification is BodyAnalysisClassification.UNCERTAIN
    assert posture.suggested_training_emphasis == ()


def test_v4_rejects_duplicate_areas_and_free_form_fields() -> None:
    normalizer = getattr(normalization, "normalize_visual_physique_assessment_v4", None)
    assert normalizer is not None

    duplicate = _v4_payload()
    observations = duplicate["area_observations"]
    assert isinstance(observations, list)
    assert isinstance(observations[0], dict)
    assert isinstance(observations[1], dict)
    observations[1] = {**observations[1], "area": observations[0]["area"]}
    with pytest.raises(ValidationError):
        normalizer(duplicate)

    extra_field = _v4_payload()
    observations = extra_field["area_observations"]
    assert isinstance(observations, list)
    assert isinstance(observations[0], dict)
    observations[0] = {**observations[0], "observation_fa": "متن آزاد"}
    with pytest.raises(ValidationError):
        normalizer(extra_field)


@pytest.mark.parametrize("classification", ["stronger", "balanced", "not_assessable"])
def test_v4_rejects_training_emphasis_on_non_actionable_classifications(
    classification: str,
) -> None:
    normalizer = getattr(normalization, "normalize_visual_physique_assessment_v4", None)
    assert normalizer is not None
    payload = _v4_payload()
    observations = payload["area_observations"]
    assert isinstance(observations, list)
    assert isinstance(observations[0], dict)
    observations[0] = {
        **observations[0],
        "classification": classification,
        "suggested_training_emphasis": ["lat_width"],
    }

    with pytest.raises(ValidationError):
        normalizer(payload)


def test_v4_caps_high_evidence_when_an_area_lacks_required_views() -> None:
    normalizer = getattr(normalization, "normalize_visual_physique_assessment_v4", None)
    projector = getattr(normalization, "visual_assessment_v4_to_normalized", None)
    assert normalizer is not None
    assert projector is not None
    payload = _v4_payload()
    observations = payload["area_observations"]
    assert isinstance(observations, list)
    assert isinstance(observations[3], dict)
    observations[3] = {
        **observations[3],
        "classification": "primary_priority",
        "evidence_strength": "high",
        "supporting_views": ["back"],
        "suggested_training_emphasis": ["lat_width"],
    }

    normalized = projector(normalizer(payload))
    lats = next(finding for finding in normalized.findings if finding.body_area is BodyArea.LATS)

    assert lats.classification is BodyAnalysisClassification.MILD_LAG
    assert lats.confidence == 0.65
    assert lats.suggested_training_emphasis == ("back_width",)


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
