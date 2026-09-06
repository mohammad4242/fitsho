from __future__ import annotations

import importlib
import importlib.util
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.body_analysis.api_schemas import BodyAnalysisExperienceIndicator
from app.body_analysis.enums import BodyArea
from app.body_analysis.normalization import (
    normalize_visual_physique_assessment_v4,
    visual_assessment_v4_to_normalized,
)
from app.body_analysis.service import BodyAnalysisInputSnapshot, BodyAnalysisPhotoSnapshot
from app.body_photos.enums import BodyPhotoView
from app.profile.enums import FitnessGoal, Sex

from .test_normalization import _v4_payload


def _snapshot(
    *,
    height_cm: int = 178,
    weight_kg: float = 82.5,
    waist_circumference_cm: float = 84.0,
    selected_goal: FitnessGoal = FitnessGoal.BUILD_MUSCLE,
) -> BodyAnalysisInputSnapshot:
    now = datetime.now(UTC)
    return BodyAnalysisInputSnapshot(
        captured_at=now,
        confirmed_at=now,
        profile_updated_at=now,
        measurement_id=uuid4(),
        measurement_measured_at=now,
        sex=Sex.MALE,
        height_cm=height_cm,
        weight_kg=weight_kg,
        shoulder_circumference_cm=122.0,
        waist_circumference_cm=waist_circumference_cm,
        hip_circumference_cm=98.0,
        selected_goal=selected_goal,
        photo_versions=tuple(
            BodyAnalysisPhotoSnapshot(
                view=view,
                photo_id=uuid4(),
                storage_key=f"aa/{uuid4().hex}.jpg",
                updated_at=now,
            )
            for view in BodyPhotoView
        ),
    )


def test_v4_presentation_v2_uses_three_scores_and_balanced_insights() -> None:
    assert importlib.util.find_spec("app.body_analysis.presentation") is not None
    presentation = importlib.import_module("app.body_analysis.presentation")
    builder = getattr(presentation, "build_body_analysis_experience_v4", None)
    assert builder is not None

    payload = _v4_payload()
    evidence = normalize_visual_physique_assessment_v4(payload)
    normalized = visual_assessment_v4_to_normalized(evidence)
    experience = builder(
        normalized_result=normalized,
        evidence=evidence,
        snapshot=_snapshot(),
        coach_approved=False,
        doctor_approved=False,
    )

    assert experience.schema_version == "4.0"
    assert experience.presentation_version == "body-analysis-experience-v2"
    assert experience.body_composition is not None
    assert experience.body_composition.bmi == 26.0
    assert experience.body_composition.estimated_body_fat_percent == 21.6
    assert experience.body_composition.body_fat_estimation_method == "rfm"
    assert experience.first_impression.message_key.startswith("body_analysis.")
    assert experience.direction.status == "aligned_with_current_goal"
    assert experience.direction.goal is FitnessGoal.BUILD_MUSCLE
    assert set(experience.indicators.model_dump()) == {
        "upper_lower_balance",
        "visible_symmetry",
        "muscle_balance",
        "body_shape",
    }
    assert experience.indicators.upper_lower_balance.score_percent == 100
    assert experience.indicators.visible_symmetry.score_percent == 90
    assert experience.indicators.muscle_balance.score_percent == 100
    assert experience.indicators.body_shape.score_percent == 85
    assert all(
        indicator["score_percent"] is None
        or 0 <= indicator["score_percent"] <= 100
        for indicator in experience.indicators.model_dump().values()
    )
    assert len(experience.regions) == 11
    assert {region.area for region in experience.regions} == {
        area
        for area in BodyArea
        if area not in {BodyArea.SYMMETRY, BodyArea.VISIBLE_ALIGNMENT_OR_POSTURE}
    }
    assert all(
        region.insight_key == "body_analysis.insights.balanced" for region in experience.regions
    )
    assert experience.review_notice_code == "review_pending"


def test_v4_presentation_map_follows_the_current_normalized_version() -> None:
    presentation = importlib.import_module("app.body_analysis.presentation")
    builder = presentation.build_body_analysis_experience_v4
    payload = _v4_payload()
    observations = payload["area_observations"]
    assert isinstance(observations, list)
    assert isinstance(observations[3], dict)
    observations[3] = {
        **observations[3],
        "classification": "primary_priority",
        "evidence_strength": "high",
        "supporting_views": ["front", "back"],
        "suggested_training_emphasis": ["lat_width"],
    }
    evidence = normalize_visual_physique_assessment_v4(payload)
    normalized = visual_assessment_v4_to_normalized(evidence)
    corrected_payload = _v4_payload()
    corrected_evidence = normalize_visual_physique_assessment_v4(corrected_payload)
    corrected_normalized = visual_assessment_v4_to_normalized(corrected_evidence)

    experience = builder(
        normalized_result=normalized,
        evidence=corrected_evidence,
        snapshot=_snapshot(),
        coach_approved=True,
        doctor_approved=False,
    )
    corrected_experience = builder(
        normalized_result=corrected_normalized,
        evidence=evidence,
        snapshot=_snapshot(),
        coach_approved=True,
        doctor_approved=False,
    )

    lats = next(region for region in experience.regions if region.area is BodyArea.LATS)
    corrected_lats = next(
        region for region in corrected_experience.regions if region.area is BodyArea.LATS
    )
    assert lats.display_classification == "primary_priority"
    assert corrected_lats.display_classification == "balanced"
    assert experience.review_notice_code == "coach_reviewed_doctor_pending"


def test_v4_presentation_direction_prioritizes_low_body_mass_gain() -> None:
    presentation = importlib.import_module("app.body_analysis.presentation")
    evidence = normalize_visual_physique_assessment_v4(_v4_payload())
    normalized = visual_assessment_v4_to_normalized(evidence)

    experience = presentation.build_body_analysis_experience_v4(
        normalized_result=normalized,
        evidence=evidence,
        snapshot=_snapshot(height_cm=180, weight_kg=55),
        coach_approved=False,
        doctor_approved=False,
    )

    assert experience.direction.goal is FitnessGoal.GAIN_WEIGHT
    assert experience.direction.reason_codes == ("low_body_mass_gain_priority",)


def test_v4_presentation_direction_requires_high_weight_and_waist_context() -> None:
    presentation = importlib.import_module("app.body_analysis.presentation")
    evidence = normalize_visual_physique_assessment_v4(_v4_payload())
    normalized = visual_assessment_v4_to_normalized(evidence)

    experience = presentation.build_body_analysis_experience_v4(
        normalized_result=normalized,
        evidence=evidence,
        snapshot=_snapshot(height_cm=180, weight_kg=100, waist_circumference_cm=100),
        coach_approved=False,
        doctor_approved=False,
    )

    assert experience.direction.goal is FitnessGoal.LOSE_WEIGHT
    assert experience.direction.reason_codes == ("high_body_mass_reduction_priority",)


def test_v4_presentation_direction_preserves_a_normal_selected_goal() -> None:
    presentation = importlib.import_module("app.body_analysis.presentation")
    evidence = normalize_visual_physique_assessment_v4(_v4_payload())
    normalized = visual_assessment_v4_to_normalized(evidence)

    experience = presentation.build_body_analysis_experience_v4(
        normalized_result=normalized,
        evidence=evidence,
        snapshot=_snapshot(selected_goal=FitnessGoal.STRENGTH),
        coach_approved=False,
        doctor_approved=False,
    )

    assert experience.direction.goal is FitnessGoal.STRENGTH
    assert experience.direction.reason_codes == ("current_goal_preserved",)


def test_v4_presentation_uses_null_scores_for_uncertain_or_insufficient_evidence() -> None:
    presentation = importlib.import_module("app.body_analysis.presentation")
    payload = _v4_payload()
    payload["upper_lower_balance"] = {
        "state": "uncertain",
        "evidence_strength": "high",
        "supporting_views": ["front", "side"],
    }
    payload["visible_symmetry"] = {
        "state": "no_clear_difference",
        "evidence_strength": "low",
        "supporting_views": ["front", "back"],
    }
    observations = payload["area_observations"]
    assert isinstance(observations, list)
    payload["area_observations"] = [
        {**observation, "classification": "not_assessable", "evidence_strength": "low"}
        if isinstance(observation, dict)
        else observation
        for observation in observations
    ]
    evidence = normalize_visual_physique_assessment_v4(payload)
    normalized = visual_assessment_v4_to_normalized(evidence)

    experience = presentation.build_body_analysis_experience_v4(
        normalized_result=normalized,
        evidence=evidence,
        snapshot=_snapshot(),
        coach_approved=False,
        doctor_approved=False,
    )

    assert experience.indicators.upper_lower_balance.score_percent is None
    assert experience.indicators.visible_symmetry.score_percent is None
    assert experience.indicators.muscle_balance.score_percent is None
    assert experience.indicators.body_shape.score_percent is None


def test_experience_indicator_rejects_scores_outside_display_range() -> None:
    with pytest.raises(ValueError):
        BodyAnalysisExperienceIndicator(
            status="available",
            message_key="body_analysis.indicators.body_shape",
            score_percent=101,
        )
