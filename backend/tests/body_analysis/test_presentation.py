from __future__ import annotations

import importlib
import importlib.util
from datetime import UTC, datetime
from uuid import uuid4

from app.body_analysis.enums import BodyArea
from app.body_analysis.normalization import (
    normalize_visual_physique_assessment_v4,
    visual_assessment_v4_to_normalized,
)
from app.body_analysis.service import BodyAnalysisInputSnapshot, BodyAnalysisPhotoSnapshot
from app.body_photos.enums import BodyPhotoView
from app.profile.enums import FitnessGoal, Sex

from .test_normalization import _v4_payload


def _snapshot() -> BodyAnalysisInputSnapshot:
    now = datetime.now(UTC)
    return BodyAnalysisInputSnapshot(
        captured_at=now,
        confirmed_at=now,
        profile_updated_at=now,
        measurement_id=uuid4(),
        measurement_measured_at=now,
        sex=Sex.MALE,
        height_cm=178,
        weight_kg=82.5,
        shoulder_circumference_cm=122.0,
        waist_circumference_cm=84.0,
        hip_circumference_cm=98.0,
        selected_goal=FitnessGoal.BUILD_MUSCLE,
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


def test_v4_presentation_uses_deterministic_keys_and_effective_normalized_result() -> None:
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
    assert experience.presentation_version == "body-analysis-experience-v1"
    assert experience.first_impression.message_key.startswith("body_analysis.")
    assert experience.direction.status == "aligned_with_current_goal"
    assert experience.direction.goal is FitnessGoal.BUILD_MUSCLE
    assert set(experience.indicators.model_dump()) == {
        "body_proportion",
        "upper_lower_balance",
        "visible_symmetry",
        "current_development_focus",
    }
    assert experience.indicators.body_proportion.parameters["waist_to_hip_ratio"] == 0.86
    assert len(experience.regions) == 11
    assert all(region.insight_key is None for region in experience.regions)
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
