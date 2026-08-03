from __future__ import annotations

import asyncio
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.models import User
from app.body_analysis.enums import BodyAnalysisStatus, SpecialistRole
from app.body_analysis.models import UserSpecialistRole
from app.body_analysis.runtime import BodyAnalysisRuntime, get_body_analysis_runtime
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


def _runtime_override(client: TestClient) -> None:
    client.app.dependency_overrides[get_body_analysis_runtime] = lambda: BodyAnalysisRuntime(
        provider=_Provider(),
        config=_config(),
        storage=_Storage(),  # type: ignore[arg-type]
    )


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
    db.add(UserSpecialistRole(user_id=reviewer.id, role=SpecialistRole.COACH))
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


def test_start_and_retry_do_not_disclose_another_users_photo_session(
    client: TestClient, db: Session
) -> None:
    _runtime_override(client)
    owner_email = f"owner-{uuid4()}@example.com"
    _register(client, owner_email)
    owner = db.scalar(select(User).where(User.email == owner_email))
    assert owner is not None
    _, photo_session = _submitted_session(db, owner)
    _logout(client)
    _register(client, f"other-{uuid4()}@example.com")

    start = client.post(f"/api/v1/body-photo-sessions/{photo_session.id}/analysis", headers=ORIGIN)
    retry = client.post(
        f"/api/v1/body-photo-sessions/{photo_session.id}/analysis/retry",
        headers=ORIGIN,
    )

    assert start.status_code == 404
    assert retry.status_code == 404


def test_fresh_queued_analysis_is_not_replaced_by_retry(client: TestClient, db: Session) -> None:
    _runtime_override(client)
    email = f"queued-{uuid4()}@example.com"
    _register(client, email)
    owner = db.scalar(select(User).where(User.email == email))
    assert owner is not None
    _, photo_session = _submitted_session(db, owner)
    analysis = BodyAnalysisService(db).queue(photo_session.id, owner.id, _config())

    response = client.post(
        f"/api/v1/body-photo-sessions/{photo_session.id}/analysis/retry",
        headers=ORIGIN,
    )

    assert response.status_code == 202
    assert response.json()["id"] == str(analysis.id)
    assert BodyAnalysisService(db).latest_for_session(photo_session.id, owner.id).id == analysis.id


def test_admin_retry_requires_admin_and_can_queue_failed_analysis(
    client: TestClient, db: Session
) -> None:
    _runtime_override(client)
    email = f"admin-retry-{uuid4()}@example.com"
    _register(client, email)
    actor = db.scalar(select(User).where(User.email == email))
    assert actor is not None
    owner, photo_session = _submitted_session(db)
    analysis = BodyAnalysisService(db).queue(photo_session.id, owner.id, _config())
    analysis.status = BodyAnalysisStatus.FAILED
    db.commit()
    path = f"/api/v1/admin/body-analyses/{analysis.id}/retry"

    assert client.post(path, headers=ORIGIN).status_code == 403
    actor.is_admin = True
    db.commit()
    response = client.post(path, headers=ORIGIN)

    assert response.status_code == 202
    assert response.json()["id"] != str(analysis.id)
