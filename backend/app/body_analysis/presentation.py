from __future__ import annotations

import math

from app.body_analysis.api_schemas import (
    BodyAnalysisExperienceDirection,
    BodyAnalysisExperienceIndicator,
    BodyAnalysisExperienceIndicators,
    BodyAnalysisExperienceMessage,
    BodyAnalysisExperienceRegion,
    BodyAnalysisExperienceV4,
    BodyAnalysisInputSnapshotResponse,
)
from app.body_analysis.body_composition import calculate_body_composition
from app.body_analysis.enums import BodyAnalysisClassification, BodyArea
from app.body_analysis.schemas import BodyAnalysisEvidenceV4Payload, NormalizedBodyAnalysis
from app.body_analysis.service import BodyAnalysisInputSnapshot
from app.profile.enums import FitnessGoal

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

_UPPER_BODY_AREAS = (
    BodyArea.SHOULDERS,
    BodyArea.CHEST,
    BodyArea.BACK,
    BodyArea.LATS,
    BodyArea.ARMS,
    BodyArea.FOREARMS,
)

_LOWER_BODY_AREAS = (
    BodyArea.GLUTES,
    BodyArea.QUADS,
    BodyArea.HAMSTRINGS,
    BodyArea.CALVES,
)

_MUSCLE_AREAS = _UPPER_BODY_AREAS + _LOWER_BODY_AREAS

_ORDINAL_CLASSIFICATION = {
    BodyAnalysisClassification.STRENGTH: 3,
    BodyAnalysisClassification.NEUTRAL: 2,
    BodyAnalysisClassification.MILD_LAG: 1,
    BodyAnalysisClassification.CLEAR_LAG: 0,
}

_DISPLAY_CLASSIFICATION = {
    BodyAnalysisClassification.STRENGTH: "stronger",
    BodyAnalysisClassification.NEUTRAL: "balanced",
    BodyAnalysisClassification.MILD_LAG: "room_to_grow",
    BodyAnalysisClassification.CLEAR_LAG: "primary_priority",
    BodyAnalysisClassification.UNCERTAIN: "not_assessable",
}

_UPPER_LOWER_SCORES = {
    "balanced": 90,
    "upper_body_dominant": 60,
    "lower_body_dominant": 60,
}
_SYMMETRY_SCORES = {
    "no_clear_difference": 90,
    "minor_visible_difference": 65,
    "clear_visible_difference": 35,
}
_BODY_SHAPE_SCORES = {
    "stronger": 95,
    "balanced": 85,
    "room_to_grow": 60,
    "primary_priority": 35,
}
_MIN_ASSESSABLE_BODY_SHAPE_AREAS = 2
_MAX_FIRST_LOOK_AREAS = 4


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
        _region(findings_by_area[area]) for area in _V4_REGION_ORDER if area in findings_by_area
    )
    body_comp = calculate_body_composition(
        sex=snapshot.sex,
        height_cm=snapshot.height_cm,
        weight_kg=snapshot.weight_kg,
        waist_circumference_cm=snapshot.waist_circumference_cm,
    )
    return BodyAnalysisExperienceV4(
        schema_version="4.0",
        presentation_version="body-analysis-experience-v2",
        assessment_status=evidence.assessment_status,
        input_snapshot=BodyAnalysisInputSnapshotResponse.model_validate(
            snapshot.model_dump(mode="json", exclude={"photo_versions"})
        ),
        body_composition=body_comp,
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
    insight_key = f"body_analysis.insights.{display_classification}"
    return BodyAnalysisExperienceRegion(
        area=finding.body_area,
        display_classification=display_classification,
        insight_key=insight_key,
        insight_parameters=({"area": finding.body_area.value} if insight_key is not None else {}),
        supporting_views=finding.supporting_views,
    )


def _first_impression(result: NormalizedBodyAnalysis) -> BodyAnalysisExperienceMessage:
    priority_areas = _displayable_areas(result.summary.priority_areas)
    moderate_areas = _displayable_areas(result.summary.moderate_attention_areas)
    if priority_areas:
        message_key = "body_analysis.first_impression.primary_priority"
        areas = (*priority_areas, *moderate_areas)[:_MAX_FIRST_LOOK_AREAS]
    elif moderate_areas:
        message_key = "body_analysis.first_impression.room_to_grow"
        areas = moderate_areas[:_MAX_FIRST_LOOK_AREAS]
    elif visible_strengths := _displayable_areas(result.summary.visible_strengths):
        message_key = "body_analysis.first_impression.visible_strengths"
        areas = visible_strengths[:_MAX_FIRST_LOOK_AREAS]
    else:
        message_key = "body_analysis.first_impression.balanced"
        areas = ()
    return BodyAnalysisExperienceMessage(
        message_key=message_key,
        parameters={"areas": [area.value for area in areas]},
    )


def _direction(snapshot: BodyAnalysisInputSnapshot) -> BodyAnalysisExperienceDirection:
    height_m = snapshot.height_cm / 100
    bmi = snapshot.weight_kg / (height_m**2) if height_m > 0 else None
    waist_to_height = (
        snapshot.waist_circumference_cm / snapshot.height_cm if snapshot.height_cm > 0 else None
    )
    if bmi is not None and bmi < 18.5:
        return BodyAnalysisExperienceDirection(
            status="aligned_with_current_goal",
            goal=FitnessGoal.GAIN_WEIGHT,
            reason_codes=("low_body_mass_gain_priority",),
        )
    if bmi is not None and bmi >= 30 and waist_to_height is not None and waist_to_height >= 0.55:
        return BodyAnalysisExperienceDirection(
            status="aligned_with_current_goal",
            goal=FitnessGoal.LOSE_WEIGHT,
            reason_codes=("high_body_mass_reduction_priority",),
        )
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
    upper_lower_state = evidence.upper_lower_balance.state
    symmetry_score = _display_score(
        symmetry_state,
        evidence.visible_symmetry.evidence_strength,
        _SYMMETRY_SCORES,
    )
    upper_lower_score = _upper_lower_balance_score(result, evidence)
    muscle_balance_score = _muscle_balance_score(result)
    body_shape_score = _body_shape_score(result)
    return BodyAnalysisExperienceIndicators(
        upper_lower_balance=BodyAnalysisExperienceIndicator(
            status=upper_lower_state,
            message_key="body_analysis.indicators.upper_lower_balance",
            parameters={"state": upper_lower_state},
            score_percent=upper_lower_score,
        ),
        visible_symmetry=BodyAnalysisExperienceIndicator(
            status=symmetry_state,
            message_key="body_analysis.indicators.visible_symmetry",
            parameters={"state": symmetry_state},
            score_percent=symmetry_score,
        ),
        muscle_balance=BodyAnalysisExperienceIndicator(
            status="available" if muscle_balance_score is not None else "uncertain",
            message_key="body_analysis.indicators.muscle_balance",
            score_percent=muscle_balance_score,
        ),
        body_shape=BodyAnalysisExperienceIndicator(
            status="available" if body_shape_score is not None else "uncertain",
            message_key="body_analysis.indicators.body_shape",
            score_percent=body_shape_score,
        ),
    )


def _muscle_balance_score(result: NormalizedBodyAnalysis) -> int | None:
    values = [
        _ORDINAL_CLASSIFICATION[finding.classification]
        for finding in result.findings
        if finding.body_area in _MUSCLE_AREAS and finding.classification in _ORDINAL_CLASSIFICATION
    ]
    if len(values) < 4:
        return None
    mean = sum(values) / len(values)
    variance = sum((x - mean) ** 2 for x in values) / len(values)
    sigma = math.sqrt(variance)
    return round(max(0.0, min(100.0, 100.0 * (1.0 - (sigma / 1.5)))))


def _upper_lower_balance_score(
    result: NormalizedBodyAnalysis,
    evidence: BodyAnalysisEvidenceV4Payload,
) -> int | None:
    if (
        evidence.upper_lower_balance.evidence_strength == "low"
        or evidence.upper_lower_balance.state == "uncertain"
    ):
        return None

    upper_values = [
        _ORDINAL_CLASSIFICATION[finding.classification]
        for finding in result.findings
        if finding.body_area in _UPPER_BODY_AREAS
        and finding.classification in _ORDINAL_CLASSIFICATION
    ]
    lower_values = [
        _ORDINAL_CLASSIFICATION[finding.classification]
        for finding in result.findings
        if finding.body_area in _LOWER_BODY_AREAS
        and finding.classification in _ORDINAL_CLASSIFICATION
    ]
    if len(upper_values) < 2 or len(lower_values) < 2:
        return None

    upper_mean = sum(upper_values) / len(upper_values)
    lower_mean = sum(lower_values) / len(lower_values)
    diff = abs(upper_mean - lower_mean)
    return round(max(0.0, min(100.0, 100.0 * (1.0 - (diff / 3.0)))))


def _displayable_areas(areas: tuple[BodyArea, ...]) -> tuple[BodyArea, ...]:
    return tuple(area for area in areas if area in _V4_REGION_ORDER)


def _display_score(
    state: str,
    evidence_strength: str,
    scores: dict[str, int],
) -> int | None:
    if evidence_strength == "low" or state == "uncertain":
        return None
    return scores.get(state)


def _body_shape_score(result: NormalizedBodyAnalysis) -> int | None:
    scores = [
        _BODY_SHAPE_SCORES[display_classification]
        for finding in result.findings
        if finding.body_area in _V4_REGION_ORDER
        if (display_classification := _DISPLAY_CLASSIFICATION[finding.classification])
        in _BODY_SHAPE_SCORES
    ]
    if len(scores) < _MIN_ASSESSABLE_BODY_SHAPE_AREAS:
        return None
    return round(sum(scores) / len(scores))


def _review_notice_code(coach_approved: bool, doctor_approved: bool) -> str:
    if coach_approved and doctor_approved:
        return "approved"
    if coach_approved:
        return "coach_reviewed_doctor_pending"
    if doctor_approved:
        return "doctor_reviewed_coach_pending"
    return "review_pending"
