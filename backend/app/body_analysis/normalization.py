from __future__ import annotations

import re
from collections.abc import Collection, Mapping
from typing import Any

from app.body_analysis.enums import (
    AnalysisLimitation,
    BodyAnalysisClassification,
    BodyArea,
    TrainingEmphasis,
)
from app.body_analysis.schemas import (
    BodyAnalysisEvidenceV4Observation,
    BodyAnalysisEvidenceV4Payload,
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


def normalize_visual_physique_assessment_v4(
    payload: Mapping[str, Any],
) -> BodyAnalysisEvidenceV4Payload:
    """Validate the provider-owned, prose-free v4 evidence contract."""

    return BodyAnalysisEvidenceV4Payload.model_validate(payload)


_V4_EVIDENCE_AREA_ORDER = (
    BodyArea.SHOULDERS,
    BodyArea.CHEST,
    BodyArea.BACK,
    BodyArea.LATS,
    BodyArea.ARMS,
    BodyArea.FOREARMS,
    BodyArea.WAIST_MIDSECTION,
    BodyArea.GLUTES,
    BodyArea.QUADS,
    BodyArea.HAMSTRINGS,
    BodyArea.CALVES,
)

_V4_EVIDENCE_SCORES = {"low": 0.40, "moderate": 0.65, "high": 0.85}

_V4_HIGH_EVIDENCE_REQUIRED_VIEWS: dict[BodyArea, frozenset[BodyPhotoView]] = {
    BodyArea.SHOULDERS: frozenset({BodyPhotoView.FRONT, BodyPhotoView.BACK}),
    BodyArea.CHEST: frozenset({BodyPhotoView.FRONT, BodyPhotoView.SIDE}),
    BodyArea.BACK: frozenset({BodyPhotoView.SIDE, BodyPhotoView.BACK}),
    BodyArea.LATS: frozenset({BodyPhotoView.FRONT, BodyPhotoView.BACK}),
    BodyArea.ARMS: frozenset({BodyPhotoView.FRONT, BodyPhotoView.BACK}),
    BodyArea.FOREARMS: frozenset({BodyPhotoView.FRONT, BodyPhotoView.SIDE}),
    BodyArea.WAIST_MIDSECTION: frozenset({BodyPhotoView.FRONT, BodyPhotoView.SIDE}),
    BodyArea.GLUTES: frozenset({BodyPhotoView.SIDE, BodyPhotoView.BACK}),
    BodyArea.QUADS: frozenset({BodyPhotoView.FRONT, BodyPhotoView.SIDE}),
    BodyArea.HAMSTRINGS: frozenset({BodyPhotoView.SIDE, BodyPhotoView.BACK}),
    BodyArea.CALVES: frozenset({BodyPhotoView.SIDE, BodyPhotoView.BACK}),
    BodyArea.SYMMETRY: frozenset({BodyPhotoView.FRONT, BodyPhotoView.BACK}),
}


def visual_assessment_v4_to_normalized(
    assessment: BodyAnalysisEvidenceV4Payload,
    *,
    preflight_confidence: float = 1.0,
    usable_views: Collection[BodyPhotoView | str] | None = None,
) -> NormalizedBodyAnalysis:
    """Project controlled v4 evidence into the stable 13-area engine contract."""

    if not 0 <= preflight_confidence <= 1:
        raise ValueError("preflight confidence must be between 0 and 1")
    normalized_usable_views = (
        {BodyPhotoView(view) for view in usable_views} if usable_views is not None else None
    )
    findings = [
        _v4_observation_to_finding(observation, normalized_usable_views)
        for area in _V4_EVIDENCE_AREA_ORDER
        for observation in assessment.area_observations
        if observation.area == area.value
    ]
    findings.append(_v4_symmetry_to_finding(assessment, normalized_usable_views))
    findings.append(_v4_posture_finding(assessment, normalized_usable_views))
    if len(findings) != len(BodyArea):
        raise ValueError("v4 projection must produce all 13 normalized body areas")

    confidence_ceiling = 0.85 if assessment.assessment_status == "complete" else 0.75
    normalized_findings = tuple(findings)
    return NormalizedBodyAnalysis(
        schema_version="4.0",
        overall_confidence=min(preflight_confidence, confidence_ceiling),
        findings=normalized_findings,
        summary=_summary_for_findings(normalized_findings),
        requires_coach_review=True,
        requires_doctor_review=True,
    )


def _v4_observation_to_finding(
    observation: BodyAnalysisEvidenceV4Observation,
    usable_views: set[BodyPhotoView] | None,
) -> BodyAnalysisFinding:
    supporting_views = tuple(observation.supporting_views)
    _validate_v4_supporting_views(supporting_views, usable_views)
    strength = _v4_effective_strength(
        observation.evidence_strength,
        observation.area,
        supporting_views,
    )
    classification, severity = _v4_classification(observation.classification, strength)
    emphasis = (
        tuple(
            emphasis
            for item in observation.suggested_training_emphasis
            for emphasis in _EMPHASIS_MAP[item]
        )
        if classification
        in {BodyAnalysisClassification.MILD_LAG, BodyAnalysisClassification.CLEAR_LAG}
        else ()
    )
    limitations = tuple(
        dict.fromkeys(
            (
                *observation.limitation_codes,
                *((AnalysisLimitation.VISIBILITY,)
                  if classification is BodyAnalysisClassification.UNCERTAIN
                  else ()),
            )
        )
    )
    return BodyAnalysisFinding(
        body_area=BodyArea(observation.area),
        classification=classification,
        severity=severity,
        confidence=_V4_EVIDENCE_SCORES[strength],
        supporting_views=supporting_views,
        explanation=(
            "Structured visual evidence supports the "
            f"{observation.classification.replace('_', ' ')} classification."
        ),
        limitations=limitations,
        suggested_training_emphasis=tuple(dict.fromkeys(emphasis)),
        medical_review_recommended=False,
    )


def _v4_symmetry_to_finding(
    assessment: BodyAnalysisEvidenceV4Payload,
    usable_views: set[BodyPhotoView] | None,
) -> BodyAnalysisFinding:
    symmetry = assessment.visible_symmetry
    supporting_views = tuple(symmetry.supporting_views)
    _validate_v4_supporting_views(supporting_views, usable_views)
    strength = _v4_effective_strength(
        symmetry.evidence_strength,
        BodyArea.SYMMETRY,
        supporting_views,
    )
    if symmetry.state == "uncertain" or strength == "low":
        classification = BodyAnalysisClassification.UNCERTAIN
        severity = None
    elif symmetry.state == "no_clear_difference":
        classification = BodyAnalysisClassification.NEUTRAL
        severity = None
    elif symmetry.state == "minor_visible_difference":
        classification = BodyAnalysisClassification.MILD_LAG
        severity = 0.5
    else:
        classification = BodyAnalysisClassification.CLEAR_LAG
        severity = 0.75
    limitations = (
        (AnalysisLimitation.VISIBILITY,)
        if classification is BodyAnalysisClassification.UNCERTAIN
        else ()
    )
    return BodyAnalysisFinding(
        body_area=BodyArea.SYMMETRY,
        classification=classification,
        severity=severity,
        confidence=_V4_EVIDENCE_SCORES[strength],
        supporting_views=supporting_views,
        explanation=f"Structured visual evidence reports {symmetry.state.replace('_', ' ')}.",
        limitations=limitations,
        suggested_training_emphasis=(),
        medical_review_recommended=False,
    )


def _v4_posture_finding(
    assessment: BodyAnalysisEvidenceV4Payload,
    usable_views: set[BodyPhotoView] | None,
) -> BodyAnalysisFinding:
    supporting_views = tuple(
        view
        for view in (BodyPhotoView.FRONT, BodyPhotoView.SIDE, BodyPhotoView.BACK)
        if any(view in observation.supporting_views for observation in assessment.area_observations)
    )
    if usable_views is not None:
        supporting_views = tuple(view for view in supporting_views if view in usable_views)
    supporting_views = supporting_views or (BodyPhotoView.FRONT,)
    return BodyAnalysisFinding(
        body_area=BodyArea.VISIBLE_ALIGNMENT_OR_POSTURE,
        classification=BodyAnalysisClassification.UNCERTAIN,
        severity=None,
        confidence=_V4_EVIDENCE_SCORES["low"],
        supporting_views=supporting_views,
        explanation="Posture is outside the v4 evidence contract.",
        limitations=(AnalysisLimitation.VISIBILITY,),
        suggested_training_emphasis=(),
        medical_review_recommended=False,
    )


def _validate_v4_supporting_views(
    supporting_views: tuple[BodyPhotoView, ...],
    usable_views: set[BodyPhotoView] | None,
) -> None:
    if usable_views is not None and not set(supporting_views).issubset(usable_views):
        raise ValueError("v4 evidence can reference only usable photo views")


def _v4_effective_strength(
    strength: str,
    area: str | BodyArea,
    supporting_views: tuple[BodyPhotoView, ...],
) -> str:
    area_key = BodyArea(area)
    if strength == "high" and not _V4_HIGH_EVIDENCE_REQUIRED_VIEWS[area_key].issubset(
        supporting_views
    ):
        return "moderate"
    return strength


def _v4_classification(
    classification: str,
    strength: str,
) -> tuple[BodyAnalysisClassification, float | None]:
    if classification == "not_assessable" or strength == "low":
        return BodyAnalysisClassification.UNCERTAIN, None
    if classification == "stronger":
        return (
            BodyAnalysisClassification.STRENGTH
            if strength == "high"
            else BodyAnalysisClassification.NEUTRAL,
            None,
        )
    if classification == "balanced":
        return BodyAnalysisClassification.NEUTRAL, None
    if classification == "primary_priority" and strength == "high":
        return BodyAnalysisClassification.CLEAR_LAG, 0.75
    return BodyAnalysisClassification.MILD_LAG, 0.5


def _summary_for_findings(
    findings: tuple[BodyAnalysisFinding, ...],
) -> BodyAnalysisSummary:
    return BodyAnalysisSummary(
        visible_strengths=tuple(
            finding.body_area
            for finding in findings
            if finding.classification is BodyAnalysisClassification.STRENGTH
        ),
        priority_areas=tuple(
            finding.body_area
            for finding in findings
            if finding.classification is BodyAnalysisClassification.CLEAR_LAG
        ),
        moderate_attention_areas=tuple(
            finding.body_area
            for finding in findings
            if finding.classification is BodyAnalysisClassification.MILD_LAG
        ),
        uncertain_areas=tuple(
            finding.body_area
            for finding in findings
            if finding.classification is BodyAnalysisClassification.UNCERTAIN
        ),
    )


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
