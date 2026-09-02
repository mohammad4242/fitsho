from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.models import User
from app.body_analysis.comparison_service import BodyProgressComparisonService
from app.body_analysis.enums import (
    BodyAnalysisClassification,
    BodyAnalysisResultSource,
    BodyAnalysisStatus,
    BodyArea,
)
from app.body_analysis.models import BodyAnalysis, BodyAnalysisResultVersion
from app.body_photos.enums import BodyPhotoPurpose, BodyPhotoSessionState, BodyPhotoView
from app.body_photos.models import BodyPhoto, BodyPhotoSession

ORIGIN = {"Origin": "http://localhost:5173"}


def _normalized_payload(classification: BodyAnalysisClassification) -> dict[str, object]:
    area = BodyArea.SHOULDERS.value
    summary = {
        "visible_strengths": (
            [area] if classification is BodyAnalysisClassification.STRENGTH else []
        ),
        "priority_areas": [],
        "moderate_attention_areas": [],
        "uncertain_areas": [area] if classification is BodyAnalysisClassification.UNCERTAIN else [],
    }
    if classification is BodyAnalysisClassification.CLEAR_LAG:
        summary["priority_areas"] = [area]
    elif classification is BodyAnalysisClassification.MILD_LAG:
        summary["moderate_attention_areas"] = [area]
    return {
        "schema_version": "1.0",
        "overall_confidence": 0.9,
        "findings": [
            {
                "body_area": area,
                "classification": classification.value,
                "severity": 0.7
                if classification
                in {
                    BodyAnalysisClassification.CLEAR_LAG,
                    BodyAnalysisClassification.MILD_LAG,
                }
                else None,
                "confidence": 0.9,
                "supporting_views": ["front", "back"],
                "explanation": "Visible development was assessed from standardized views.",
                "limitations": [],
                "suggested_training_emphasis": [],
                "medical_review_recommended": False,
            }
        ],
        "summary": summary,
        "requires_coach_review": True,
        "requires_doctor_review": True,
    }


def _session_with_analysis(
    db: Session,
    user: User,
    *,
    created_at: datetime,
    classification: BodyAnalysisClassification,
    legacy_photo_validation: bool = False,
) -> tuple[BodyPhotoSession, BodyAnalysisResultVersion]:
    session = BodyPhotoSession(
        user_id=user.id,
        purpose=BodyPhotoPurpose.PROGRESS_CHECK,
        state=BodyPhotoSessionState.REVIEW_PENDING,
        submitted_at=created_at,
        created_at=created_at,
    )
    db.add(session)
    db.flush()
    for view in BodyPhotoView:
        db.add(
            BodyPhoto(
                session_id=session.id,
                view=view,
                storage_key=f"history/{uuid4().hex}.jpg",
                mime_type="image/jpeg",
                byte_size=2048,
                width=600,
                height=1200,
            )
        )
    payload = _normalized_payload(classification)
    analysis = BodyAnalysis(
        session_id=session.id,
        revision=1,
        provider="openrouter",
        model_id="vision-model",
        prompt_version="body-v1",
        schema_version="1.0",
        status=BodyAnalysisStatus.REVIEW_PENDING,
        normalized_result=payload,
        raw_result=(
            {
                "photo_validation": {
                    "accepted": False,
                    "confidence": 0.94,
                    "issues": [{"view": "front", "reasons": ["low_lighting"]}],
                }
            }
            if legacy_photo_validation
            else None
        ),
        overall_confidence=0.9,
        completed_at=created_at,
        created_at=created_at,
    )
    db.add(analysis)
    db.flush()
    version = BodyAnalysisResultVersion(
        analysis_id=analysis.id,
        version=1,
        source=BodyAnalysisResultSource.AI,
        normalized_result=payload,
        overall_confidence=0.9,
        created_at=created_at,
    )
    db.add(version)
    db.commit()
    return session, version


def _register(client: TestClient, email: str) -> None:
    response = client.post(
        "/api/v1/auth/register",
        headers=ORIGIN,
        json={"email": email, "password": "long password"},
    )
    assert response.status_code == 201


def test_timeline_is_one_owner_scoped_read_model_with_protected_photos(
    client: TestClient,
    db: Session,
) -> None:
    email = f"history-api-{uuid4()}@example.com"
    _register(client, email)
    owner = db.scalar(select(User).where(User.email == email))
    assert owner is not None
    now = datetime.now(UTC)
    previous, _ = _session_with_analysis(
        db,
        owner,
        created_at=now - timedelta(days=14),
        classification=BodyAnalysisClassification.NEUTRAL,
    )
    current, current_version = _session_with_analysis(
        db,
        owner,
        created_at=now,
        classification=BodyAnalysisClassification.STRENGTH,
        legacy_photo_validation=True,
    )
    comparison = BodyProgressComparisonService(db).create_for_result(
        current_version.id,
        owner.id,
    )
    assert comparison is not None

    response = client.get("/api/v1/body-progress/timeline")

    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_version"] == "1.0"
    assert [item["session"]["id"] for item in payload["items"]] == [
        str(current.id),
        str(previous.id),
    ]
    latest = payload["items"][0]
    assert latest["analysis"]["id"] == str(current_version.analysis_id)
    assert latest["analysis"]["photo_validation"] == {
        "accepted": False,
        "confidence": 0.94,
        "issues": [{"view": "front", "reasons": ["low_lighting"]}],
    }
    assert latest["snapshot"] is None
    assert latest["review_state"]["coach"]["decision"] is None
    assert latest["photos"][0]["content_url"].startswith(
        f"/api/v1/body-photo-sessions/{current.id}/photos/"
    )
    assert latest["comparison"]["interval_days"] == 14
    assert latest["comparison"]["before_photos"][0]["content_url"].startswith(
        f"/api/v1/body-photo-sessions/{previous.id}/photos/"
    )
    assert latest["comparison"]["after_photos"][0]["content_url"].startswith(
        f"/api/v1/body-photo-sessions/{current.id}/photos/"
    )
    assert "storage_key" not in response.text

    assert client.post("/api/v1/auth/logout", headers=ORIGIN).status_code == 204
    _register(client, f"history-other-{uuid4()}@example.com")
    other_response = client.get("/api/v1/body-progress/timeline")
    assert other_response.status_code == 200
    assert other_response.json()["items"] == []
