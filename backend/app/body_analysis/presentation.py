from __future__ import annotations

from app.body_analysis.api_schemas import (
    BodyAnalysisExperienceDirection,
    BodyAnalysisExperienceIndicator,
    BodyAnalysisExperienceIndicators,
    BodyAnalysisExperienceMessage,
    BodyAnalysisExperienceRegion,
    BodyAnalysisExperienceV4,
    BodyAnalysisInputSnapshotResponse,
)
from app.body_analysis.enums import BodyAnalysisClassification, BodyArea
from app.body_analysis.schemas import BodyAnalysisEvidenceV4Payload, NormalizedBodyAnalysis
from app.body_analysis.service import BodyAnalysisInputSnapshot

_V4_REGION_ORDER = (
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

_DISPLAY_CLASSIFICATION = {
    BodyAnalysisClassification.STRENGTH: "stronger",
    BodyAnalysisClassification.NEUTRAL: "balanced",
    BodyAnalysisClassification.MILD_LAG: "room_to_grow",
    BodyAnalysisClassification.CLEAR_LAG: "primary_priority",
    BodyAnalysisClassification.UNCERTAIN: "not_assessable",
}


def build_body_analysis_experience_v4(
    *,
    normalized_result: NormalizedBodyAnalysis,
    evidence: BodyAnalysisEvidenceV4Payload,
    snapshot: BodyAnalysisInputSnapshot,
    coach_approved: bool,
    doctor_approved: bool,
) -> BodyAnalysisExperienceV4:
    """Build the deterministic v4 read model from the effective result version."""

    findings_by_area = {finding.body_area: finding for finding in normalized_result.findings}
    regions = tuple(
        _region(findings_by_area[area])
        for area in _V4_REGION_ORDER
        if area in findings_by_area
    )
    return BodyAnalysisExperienceV4(
        schema_version="4.0",
        presentation_version="body-analysis-experience-v1",
        assessment_status=evidence.assessment_status,
        input_snapshot=BodyAnalysisInputSnapshotResponse.model_validate(
            snapshot.model_dump(mode="json", exclude={"photo_versions"})
        ),
        first_impression=_first_impression(normalized_result),
        direction=_direction(snapshot),
        indicators=_indicators(normalized_result, evidence, snapshot),
        regions=regions,
        review_notice_code=_review_notice_code(coach_approved, doctor_approved),
    )


def _region(finding: object) -> BodyAnalysisExperienceRegion:
    from app.body_analysis.schemas import BodyAnalysisFinding

    if not isinstance(finding, BodyAnalysisFinding):
        raise TypeError("normalized v4 region is invalid")
    display_classification = _DISPLAY_CLASSIFICATION[finding.classification]
    insight_key = None
    if display_classification != "balanced":
        insight_key = f"body_analysis.insights.{display_classification}"
    return BodyAnalysisExperienceRegion(
        area=finding.body_area,
        display_classification=display_classification,
        insight_key=insight_key,
        insight_parameters=(
            {"area": finding.body_area.value} if insight_key is not None else {}
        ),
        supporting_views=finding.supporting_views,
    )


def _first_impression(result: NormalizedBodyAnalysis) -> BodyAnalysisExperienceMessage:
    if result.summary.priority_areas:
        message_key = "body_analysis.first_impression.primary_priority"
        areas = result.summary.priority_areas
    elif result.summary.moderate_attention_areas:
        message_key = "body_analysis.first_impression.room_to_grow"
        areas = result.summary.moderate_attention_areas
    elif result.summary.visible_strengths:
        message_key = "body_analysis.first_impression.visible_strengths"
        areas = result.summary.visible_strengths
    else:
        message_key = "body_analysis.first_impression.balanced"
        areas = ()
    return BodyAnalysisExperienceMessage(
        message_key=message_key,
        parameters={"areas": [area.value for area in areas]},
    )


def _direction(snapshot: BodyAnalysisInputSnapshot) -> BodyAnalysisExperienceDirection:
    if snapshot.selected_goal.value == "improve_fitness":
        return BodyAnalysisExperienceDirection(
            status="goal_confirmation_required",
            goal=snapshot.selected_goal,
            reason_codes=("legacy_goal_requires_confirmation",),
        )
    return BodyAnalysisExperienceDirection(
        status="aligned_with_current_goal",
        goal=snapshot.selected_goal,
        reason_codes=("current_goal_preserved",),
    )


def _indicators(
    result: NormalizedBodyAnalysis,
    evidence: BodyAnalysisEvidenceV4Payload,
    snapshot: BodyAnalysisInputSnapshot,
) -> BodyAnalysisExperienceIndicators:
    symmetry = next(
        finding for finding in result.findings if finding.body_area is BodyArea.SYMMETRY
    )
    symmetry_state = {
        BodyAnalysisClassification.NEUTRAL: "no_clear_difference",
        BodyAnalysisClassification.MILD_LAG: "minor_visible_difference",
        BodyAnalysisClassification.CLEAR_LAG: "clear_visible_difference",
        BodyAnalysisClassification.STRENGTH: "no_clear_difference",
        BodyAnalysisClassification.UNCERTAIN: "uncertain",
    }[symmetry.classification]
    if result.summary.priority_areas:
        focus_status = "primary_priority"
        focus_areas = result.summary.priority_areas
    elif result.summary.moderate_attention_areas:
        focus_status = "room_to_grow"
        focus_areas = result.summary.moderate_attention_areas
    else:
        focus_status = "balanced"
        focus_areas = ()
    return BodyAnalysisExperienceIndicators(
        body_proportion=BodyAnalysisExperienceIndicator(
            status="available",
            message_key="body_analysis.indicators.body_proportion",
            parameters={
                "shoulder_to_waist_ratio": round(
                    snapshot.shoulder_circumference_cm / snapshot.waist_circumference_cm,
                    2,
                ),
                "waist_to_hip_ratio": round(
                    snapshot.waist_circumference_cm / snapshot.hip_circumference_cm,
                    2,
                ),
            },
        ),
        upper_lower_balance=BodyAnalysisExperienceIndicator(
            status=evidence.upper_lower_balance.state,
            message_key="body_analysis.indicators.upper_lower_balance",
            parameters={"state": evidence.upper_lower_balance.state},
        ),
        visible_symmetry=BodyAnalysisExperienceIndicator(
            status=symmetry_state,
            message_key="body_analysis.indicators.visible_symmetry",
            parameters={"state": symmetry_state},
        ),
        current_development_focus=BodyAnalysisExperienceIndicator(
            status=focus_status,
            message_key="body_analysis.indicators.current_development_focus",
            parameters={"areas": [area.value for area in focus_areas]},
        ),
    )


def _review_notice_code(coach_approved: bool, doctor_approved: bool) -> str:
    if coach_approved and doctor_approved:
        return "approved"
    if coach_approved:
        return "coach_reviewed_doctor_pending"
    if doctor_approved:
        return "doctor_reviewed_coach_pending"
    return "review_pending"
