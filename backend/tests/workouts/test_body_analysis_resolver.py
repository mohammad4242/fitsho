from uuid import uuid4

from sqlalchemy.orm import Session

from app.auth.models import User
from app.body_analysis.enums import (
    BodyAnalysisResultSource,
    BodyAnalysisReviewDecision,
    BodyAnalysisReviewerRole,
    BodyAnalysisStatus,
)
from app.body_analysis.models import BodyAnalysis, BodyAnalysisResultVersion, BodyAnalysisReview
from app.body_analysis.schemas import NormalizedBodyAnalysis
from app.body_analysis.service import EffectiveBodyAnalysisResult
from app.body_photos.enums import BodyPhotoPurpose, BodyPhotoSessionState
from app.body_photos.models import BodyPhotoSession
from app.exercises.enums import MuscleGroup
from app.workouts.body_analysis_resolver import (
    WorkoutBodyAnalysisResolver,
    to_body_analysis_influence,
)


def normalized_result() -> NormalizedBodyAnalysis:
    return NormalizedBodyAnalysis.model_validate(
        {
            "schema_version": "1.0",
            "overall_confidence": 0.88,
            "findings": [
                {
                    "body_area": "shoulders",
                    "classification": "clear_lag",
                    "severity": 0.8,
                    "confidence": 0.9,
                    "supporting_views": ["front", "back"],
                    "explanation": "Visibly less developed relative to nearby areas.",
                    "limitations": [],
                    "suggested_training_emphasis": [
                        "lateral_deltoid",
                        "rear_deltoid",
                    ],
                    "medical_review_recommended": False,
                },
                {
                    "body_area": "hamstrings",
                    "classification": "uncertain",
                    "severity": None,
                    "confidence": 0.35,
                    "supporting_views": ["side"],
                    "explanation": "The area is not visible clearly enough.",
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
    )


def effective(*, version: int = 1, coach: bool = False, doctor: bool = False):
    return EffectiveBodyAnalysisResult(
        analysis_id=uuid4(),
        result_version_id=uuid4(),
        version=version,
        normalized_result=normalized_result(),
        source=BodyAnalysisResultSource.AI,
        coach_approved=coach,
        doctor_approved=doctor,
    )


def test_maps_only_explicit_lag_emphasis_and_drops_uncertain_findings() -> None:
    result = effective()

    influence = to_body_analysis_influence(result, analysis_revision=2)

    assert influence.analysis_revision == 2
    assert influence.source == "ai_provisional"
    assert [item.muscle for item in influence.priorities] == [MuscleGroup.SHOULDERS]
    assert influence.priorities[0].emphasis == ("lateral_deltoid", "rear_deltoid")


def test_both_specialist_approvals_mark_exact_result_fully_reviewed() -> None:
    result = effective(coach=True, doctor=True)

    influence = to_body_analysis_influence(result, analysis_revision=1)

    assert influence.source == "fully_reviewed"
    assert influence.result_version_id == result.result_version_id


def _corrected_chest_result() -> NormalizedBodyAnalysis:
    return NormalizedBodyAnalysis.model_validate(
        {
            "schema_version": "1.0",
            "overall_confidence": 0.9,
            "findings": [
                {
                    "body_area": "chest",
                    "classification": "mild_lag",
                    "severity": 0.5,
                    "confidence": 0.9,
                    "supporting_views": ["front"],
                    "explanation": "Chest is relatively lagging in the visible views.",
                    "limitations": [],
                    "suggested_training_emphasis": ["chest"],
                    "medical_review_recommended": False,
                }
            ],
            "summary": {
                "visible_strengths": [],
                "priority_areas": [],
                "moderate_attention_areas": ["chest"],
                "uncertain_areas": [],
            },
            "requires_coach_review": True,
            "requires_doctor_review": True,
        }
    )


def test_resolver_prefers_current_specialist_correction_over_ai_result(db: Session) -> None:
    owner = User(email=f"owner-{uuid4()}@example.com", password_hash="x")
    coach = User(email=f"coach-{uuid4()}@example.com", password_hash="x", is_admin=True)
    doctor = User(email=f"doctor-{uuid4()}@example.com", password_hash="x", is_admin=True)
    db.add_all([owner, coach, doctor])
    db.flush()
    session = BodyPhotoSession(
        user_id=owner.id,
        purpose=BodyPhotoPurpose.PROGRESS_CHECK,
        state=BodyPhotoSessionState.COMPLETED,
    )
    db.add(session)
    db.flush()
    analysis = BodyAnalysis(
        session_id=session.id,
        revision=1,
        provider="openrouter",
        model_id="vision",
        prompt_version="body-v1",
        schema_version="1.0",
        status=BodyAnalysisStatus.COMPLETED,
    )
    db.add(analysis)
    db.flush()
    ai_version = BodyAnalysisResultVersion(
        analysis_id=analysis.id,
        version=1,
        source=BodyAnalysisResultSource.AI,
        normalized_result=normalized_result().model_dump(mode="json"),
        overall_confidence=0.88,
    )
    db.add(ai_version)
    db.flush()
    corrected = BodyAnalysisResultVersion(
        analysis_id=analysis.id,
        replaces_version_id=ai_version.id,
        version=2,
        source=BodyAnalysisResultSource.COACH,
        normalized_result=_corrected_chest_result().model_dump(mode="json"),
        overall_confidence=0.9,
        created_by_user_id=coach.id,
    )
    db.add(corrected)
    db.flush()
    db.add_all(
        [
            BodyAnalysisReview(
                analysis_id=analysis.id,
                result_version_id=corrected.id,
                reviewer_id=coach.id,
                reviewer_role=BodyAnalysisReviewerRole.COACH,
                decision=BodyAnalysisReviewDecision.APPROVED,
            ),
            BodyAnalysisReview(
                analysis_id=analysis.id,
                result_version_id=corrected.id,
                reviewer_id=doctor.id,
                reviewer_role=BodyAnalysisReviewerRole.DOCTOR,
                decision=BodyAnalysisReviewDecision.APPROVED,
            ),
        ]
    )
    db.commit()

    influence = WorkoutBodyAnalysisResolver(db).resolve(owner.id)

    assert influence is not None
    assert influence.result_version_id == corrected.id
    assert influence.source == "fully_reviewed"
    assert [priority.muscle for priority in influence.priorities] == [MuscleGroup.CHEST]
