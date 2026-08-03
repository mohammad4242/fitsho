from __future__ import annotations

import asyncio
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.models import User
from app.body_analysis.service import BodyAnalysisService
from app.body_photos.enums import BodyPhotoSessionState

from .test_execution_and_reviews import (
    _config,
    _Provider,
    _Storage,
    _submitted_session,
)

ORIGIN = {"Origin": "http://localhost:5173"}


def _register(client: TestClient, email: str) -> None:
    response = client.post(
        "/api/v1/auth/register",
        headers=ORIGIN,
        json={"email": email, "password": "long password"},
    )
    assert response.status_code == 201


def _logout(client: TestClient) -> None:
    assert client.post("/api/v1/auth/logout", headers=ORIGIN).status_code == 204


def test_analysis_result_api_is_owner_only_and_hides_provider_envelopes(
    client: TestClient, db: Session
) -> None:
    email = f"result-owner-{uuid4()}@example.com"
    _register(client, email)
    owner = db.scalar(select(User).where(User.email == email))
    assert owner is not None
    _, photo_session = _submitted_session(db, owner)
    service = BodyAnalysisService(db)
    analysis = service.queue(photo_session.id, owner.id, _config())
    asyncio.run(service.execute(analysis.id, _Provider(), _Storage()))

    result = client.get(f"/api/v1/body-photo-sessions/{photo_session.id}/analysis")

    assert result.status_code == 200
    assert result.json()["status"] == "review_pending"
    assert result.json()["unverified_warning"] is True
    assert result.json()["coach_review"]["decision"] is None
    assert result.json()["doctor_review"]["decision"] is None
    assert "raw_result" not in result.text
    assert "provider_request_id" not in result.text

    _logout(client)
    _register(client, f"result-other-{uuid4()}@example.com")
    assert client.get(f"/api/v1/body-photo-sessions/{photo_session.id}/analysis").status_code == 404


def test_review_api_requires_admin_and_records_reviewer_identity(
    client: TestClient, db: Session
) -> None:
    email = f"reviewer-{uuid4()}@example.com"
    _register(client, email)
    reviewer = db.scalar(select(User).where(User.email == email))
    assert reviewer is not None
    owner, photo_session = _submitted_session(db)
    service = BodyAnalysisService(db)
    analysis = service.queue(photo_session.id, owner.id, _config())
    asyncio.run(service.execute(analysis.id, _Provider(), _Storage()))
    path = f"/api/v1/reviews/body-analyses/{analysis.id}/review"
    payload = {
        "role": "coach",
        "decision": "approved",
        "notes": "Reviewed as a provisional visible-development result.",
    }

    assert client.post(path, headers=ORIGIN, json=payload).status_code == 403
    assert client.get(f"/api/v1/reviews/body-analyses/{analysis.id}").status_code == 403
    reviewer.is_admin = True
    db.commit()
    approved = client.post(path, headers=ORIGIN, json=payload)
    history = client.get(f"/api/v1/reviews/body-analyses/{analysis.id}")

    assert approved.status_code == 200
    assert approved.json()["reviewer_id"] == str(reviewer.id)
    assert approved.json()["role"] == "coach"
    assert history.status_code == 200
    assert [item["version"] for item in history.json()["result_versions"]] == [1]
    assert history.json()["reviews"][0]["reviewer_id"] == str(reviewer.id)


def test_unconfigured_analysis_returns_safe_failure_without_changing_photo_session(
    client: TestClient, db: Session
) -> None:
    email = f"unconfigured-{uuid4()}@example.com"
    _register(client, email)
    owner = db.scalar(select(User).where(User.email == email))
    assert owner is not None
    _, photo_session = _submitted_session(db, owner)

    response = client.post(
        f"/api/v1/body-photo-sessions/{photo_session.id}/analysis",
        headers=ORIGIN,
    )

    db.refresh(photo_session)
    assert response.status_code == 503
    assert response.json() == {"detail": "Body analysis is temporarily unavailable"}
    assert photo_session.state is BodyPhotoSessionState.QUEUED
