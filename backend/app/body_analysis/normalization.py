from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

from app.body_analysis.enums import (
    AnalysisLimitation,
    BodyAnalysisClassification,
    TrainingEmphasis,
)
from app.body_analysis.schemas import (
    BodyAnalysisFinding,
    BodyAnalysisSummary,
    NormalizedBodyAnalysis,
    VisualPhysiqueAssessment,
    VisualPhysiqueAssessmentPayload,
    VisualPhysiqueAssessmentV3,
    VisualPhysiqueAssessmentV3Payload,
)
from app.body_photos.enums import BodyPhotoView


class MedicalClaimError(ValueError):
    """Raised when provider prose crosses the non-diagnostic product boundary."""


_MEDICAL_CLAIM_PATTERN = re.compile(
    r"\b(?:arthritis|diagnos(?:e|es|ed|is|tic)|disease|deformit(?:y|ies)|"
    r"disorder|fracture|hernia|impingement|inflammation|injur(?:y|ed|ies)|kyphosis|"
    r"medical\s+condition|osteoporosis|prov(?:e|es|ed|ing)|scoliosis|tear(?:s|ing)?|"
    r"tendinitis|tendonitis|torn)\b",
    flags=re.IGNORECASE,
)


def normalize_body_analysis(payload: Mapping[str, Any]) -> NormalizedBodyAnalysis:
    """Validate and normalize a provider payload without retaining provider envelopes."""

    normalized = NormalizedBodyAnalysis.model_validate(payload)
    for finding in normalized.findings:
        if _MEDICAL_CLAIM_PATTERN.search(finding.explanation):
            raise MedicalClaimError("body analysis cannot contain medical diagnostic claims")
    return normalized


def normalize_visual_physique_assessment(
    payload: Mapping[str, Any],
) -> VisualPhysiqueAssessment:
    """Validate a provider-owned v2 payload and add backend-owned policy fields."""

    visual = VisualPhysiqueAssessmentPayload.model_validate(payload)
    for finding in visual.findings:
        if _MEDICAL_CLAIM_PATTERN.search(finding.evidence_fa):
            raise MedicalClaimError("body analysis cannot contain medical diagnostic claims")
    return VisualPhysiqueAssessment.model_validate(visual.model_dump(mode="json"))


def normalize_visual_physique_assessment_v3(
    payload: Mapping[str, Any],
) -> VisualPhysiqueAssessmentV3:
    """Validate a provider-owned v3 checklist and add product policy fields."""

    visual = VisualPhysiqueAssessmentV3Payload.model_validate(payload)
    prose = [visual.overall_assessment.summary_fa, visual.goal_suggestion.reasoning_fa]
    prose.extend(finding.overall_summary_fa for finding in visual.findings)
    prose.extend(
        checklist.evidence_fa
        for finding in visual.findings
        for checklist in (finding.front, finding.side, finding.back)
    )
    if any(_MEDICAL_CLAIM_PATTERN.search(value) for value in prose):
        raise MedicalClaimError("body analysis cannot contain medical diagnostic claims")
    return VisualPhysiqueAssessmentV3.model_validate(visual.model_dump(mode="json"))


_EMPHASIS_MAP: dict[str, tuple[TrainingEmphasis, ...]] = {
    "overall_shoulders": (TrainingEmphasis.LATERAL_DELTOID, TrainingEmphasis.REAR_DELTOID),
    "lateral_delts": (TrainingEmphasis.LATERAL_DELTOID,),
    "rear_delts": (TrainingEmphasis.REAR_DELTOID,),
    "overall_chest": (TrainingEmphasis.CHEST,),
    "upper_chest": (TrainingEmphasis.UPPER_CHEST,),
    "upper_back": (TrainingEmphasis.BACK_THICKNESS,),
    "mid_back": (TrainingEmphasis.BACK_THICKNESS,),
    "lat_width": (TrainingEmphasis.BACK_WIDTH,),
    "overall_arms": (TrainingEmphasis.BICEPS, TrainingEmphasis.TRICEPS),
    "biceps": (TrainingEmphasis.BICEPS,),
    "triceps": (TrainingEmphasis.TRICEPS,),
    "forearms": (TrainingEmphasis.FOREARMS,),
    "trunk_musculature": (TrainingEmphasis.WAIST_MIDSECTION,),
    "glutes": (TrainingEmphasis.GLUTES,),
    "quads": (TrainingEmphasis.QUADS,),
    "hamstrings": (TrainingEmphasis.HAMSTRINGS,),
    "calves": (TrainingEmphasis.CALVES,),
    "left_right_balance": (),
}


def visual_assessment_to_normalized(
    assessment: VisualPhysiqueAssessment,
) -> NormalizedBodyAnalysis:
    """Project v2 visual data into the stable workout and comparison contract."""

    findings = tuple(_legacy_finding(finding) for finding in assessment.findings)
    return NormalizedBodyAnalysis(
        schema_version="2.0",
        overall_confidence=sum(item.confidence for item in findings) / len(findings),
        findings=findings,
        summary=BodyAnalysisSummary(
            visible_strengths=tuple(
                item.body_area
                for item in findings
                if item.classification is BodyAnalysisClassification.STRENGTH
            ),
            priority_areas=tuple(
                item.body_area
                for item in findings
                if item.classification is BodyAnalysisClassification.CLEAR_LAG
            ),
            moderate_attention_areas=tuple(
                item.body_area
                for item in findings
                if item.classification is BodyAnalysisClassification.MILD_LAG
            ),
            uncertain_areas=tuple(
                item.body_area
                for item in findings
                if item.classification is BodyAnalysisClassification.UNCERTAIN
            ),
        ),
        requires_coach_review=True,
        requires_doctor_review=True,
    )


def visual_assessment_v3_to_normalized(
    assessment: VisualPhysiqueAssessmentV3,
) -> NormalizedBodyAnalysis:
    """Project the v3 checklist into the stable workout and comparison contract."""

    findings = tuple(_v3_legacy_finding(finding) for finding in assessment.findings)
    return NormalizedBodyAnalysis(
        schema_version="3.0",
        overall_confidence=sum(item.confidence for item in findings) / len(findings),
        findings=findings,
        summary=BodyAnalysisSummary(
            visible_strengths=tuple(
                item.body_area
                for item in findings
                if item.classification is BodyAnalysisClassification.STRENGTH
            ),
            priority_areas=tuple(
                item.body_area
                for item in findings
                if item.classification is BodyAnalysisClassification.CLEAR_LAG
            ),
            moderate_attention_areas=tuple(
                item.body_area
                for item in findings
                if item.classification is BodyAnalysisClassification.MILD_LAG
            ),
            uncertain_areas=tuple(
                item.body_area
                for item in findings
                if item.classification is BodyAnalysisClassification.UNCERTAIN
            ),
        ),
        requires_coach_review=True,
        requires_doctor_review=True,
    )


def _legacy_finding(finding: object) -> BodyAnalysisFinding:
    from app.body_analysis.schemas import VisualPhysiqueFinding

    if not isinstance(finding, VisualPhysiqueFinding):
        raise TypeError("visual assessment finding is invalid")
    classification = (
        BodyAnalysisClassification.UNCERTAIN
        if finding.classification == "not_assessable"
        else BodyAnalysisClassification(finding.classification)
    )
    emphasis = tuple(
        emphasis for item in finding.suggested_training_emphasis for emphasis in _EMPHASIS_MAP[item]
    )
    return BodyAnalysisFinding(
        body_area=finding.area,
        classification=classification,
        severity=finding.severity,
        confidence=finding.confidence,
        supporting_views=finding.views_used,
        explanation=finding.evidence_fa,
        limitations=(AnalysisLimitation.VISIBILITY,)
        if finding.classification == "not_assessable"
        else (),
        suggested_training_emphasis=tuple(dict.fromkeys(emphasis)),
        medical_review_recommended=False,
    )


def _v3_legacy_finding(finding: object) -> BodyAnalysisFinding:
    from app.body_analysis.schemas import VisualChecklistFinding

    if not isinstance(finding, VisualChecklistFinding):
        raise TypeError("visual assessment v3 finding is invalid")
    ratings = (finding.front.rating, finding.side.rating, finding.back.rating)
    supported_views = tuple(
        view
        for view, rating in zip(("front", "side", "back"), ratings, strict=True)
        if rating != "not_assessable"
    )
    if finding.overall_rating == "focus_priority":
        classification = BodyAnalysisClassification.CLEAR_LAG
        severity: float | None = 0.75
    elif finding.overall_rating == "needs_attention":
        classification = BodyAnalysisClassification.MILD_LAG
        severity = 0.5
    elif all(rating == "not_assessable" for rating in ratings):
        classification = BodyAnalysisClassification.UNCERTAIN
        severity = None
    elif (
        finding.overall_rating in {"excellent", "good"}
        and sum(rating in {"excellent", "good"} for rating in ratings) >= 2
    ):
        classification = BodyAnalysisClassification.STRENGTH
        severity = None
    else:
        classification = BodyAnalysisClassification.NEUTRAL
        severity = None
    emphasis = tuple(
        emphasis for item in finding.suggested_training_emphasis for emphasis in _EMPHASIS_MAP[item]
    )
    return BodyAnalysisFinding(
        body_area=finding.area,
        classification=classification,
        severity=severity,
        confidence=finding.confidence,
        supporting_views=tuple(BodyPhotoView(view) for view in supported_views)
        or (BodyPhotoView.FRONT,),
        explanation=finding.overall_summary_fa,
        limitations=(AnalysisLimitation.VISIBILITY,)
        if classification is BodyAnalysisClassification.UNCERTAIN
        else (),
        suggested_training_emphasis=tuple(dict.fromkeys(emphasis)),
        medical_review_recommended=False,
    )
