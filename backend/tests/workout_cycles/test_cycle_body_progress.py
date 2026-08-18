from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.body_analysis.service import (
    AnalysisExecutionConfig,
    BodyAnalysisNotFoundError,
    BodyAnalysisService,
)
from app.body_photos.enums import BodyPhotoPurpose, BodyPhotoSessionState, BodyPhotoView
from app.body_photos.models import BodyPhoto, BodyPhotoSession
from app.profile.models import BodyMeasurement
from tests.body_photos.test_session_api import ORIGIN
from tests.profile.test_profile_update_api import VALID_PROFILE
from tests.workout_cycles.test_replacement_api import _plan_with_cycle, _register, _user


def _create_profile(client: TestClient) -> None:
    response = client.post("/api/v1/profile", headers=ORIGIN, json=VALID_PROFILE)
    assert response.status_code == 201


def _analysis_config() -> AnalysisExecutionConfig:
    return AnalysisExecutionConfig(
        provider_name="openrouter",
        primary_model="vision-primary",
        fallback_models=("vision-fallback",),
        prompt_version="body-v1",
        schema_version="1.0",
        max_output_tokens=3000,
    )


def test_cycle_measurement_update_is_linked_to_the_owned_cycle(
    client: TestClient,
    db: Session,
) -> None:
    user_id = _register(client, f"cycle-measurement-{uuid4()}@example.com")
    _create_profile(client)
    _plan, _prescribed, cycle, _original, _safe, _unsafe = _plan_with_cycle(db, user_id)
    assert cycle is not None

    response = client.patch(
        "/api/v1/profile",
        headers=ORIGIN,
        json={"cycle_id": str(cycle.id), "current_weight_kg": VALID_PROFILE["current_weight_kg"]},
    )

    assert response.status_code == 200
    measurement = db.query(BodyMeasurement).filter_by(cycle_id=cycle.id).one()
    assert measurement.user_id == user_id


def test_measurement_cannot_attach_to_another_users_cycle(
    client: TestClient,
    db: Session,
) -> None:
    user_id = _register(client, f"cycle-measurement-owner-{uuid4()}@example.com")
    _create_profile(client)
    other = _user(db)
    _plan, _prescribed, other_cycle, _original, _safe, _unsafe = _plan_with_cycle(
        db, other.id
    )
    assert other_cycle is not None

    response = client.patch(
        "/api/v1/profile",
        headers=ORIGIN,
        json={"cycle_id": str(other_cycle.id), "current_weight_kg": 77.0},
    )

    assert response.status_code == 404
    assert db.query(BodyMeasurement).filter_by(cycle_id=other_cycle.id).count() == 0
    assert user_id != other.id


def test_cycle_photo_session_is_linked_and_existing_photo_flow_remains_owned(
    client: TestClient,
    db: Session,
) -> None:
    user_id = _register(client, f"cycle-photo-session-{uuid4()}@example.com")
    _plan, _prescribed, cycle, _original, _safe, _unsafe = _plan_with_cycle(db, user_id)
    assert cycle is not None

    response = client.post(
        "/api/v1/body-photo-sessions",
        headers=ORIGIN,
        json={"purpose": "cycle_completion", "cycle_id": str(cycle.id)},
    )

    assert response.status_code == 201
    assert response.json()["cycle_id"] == str(cycle.id)
    session = db.get(BodyPhotoSession, UUID(response.json()["id"]))
    assert session is not None
    assert session.user_id == user_id
    assert session.cycle_id == cycle.id


def test_photo_session_cannot_attach_to_another_users_cycle(
    client: TestClient,
    db: Session,
) -> None:
    _register(client, f"cycle-photo-owner-{uuid4()}@example.com")
    other = _user(db)
    _plan, _prescribed, other_cycle, _original, _safe, _unsafe = _plan_with_cycle(
        db, other.id
    )
    assert other_cycle is not None

    response = client.post(
        "/api/v1/body-photo-sessions",
        headers=ORIGIN,
        json={"purpose": "cycle_completion", "cycle_id": str(other_cycle.id)},
    )

    assert response.status_code == 404


def test_queued_body_analysis_inherits_cycle_link_from_photo_session(db: Session) -> None:
    user = _user(db)
    _plan, _prescribed, cycle, _original, _safe, _unsafe = _plan_with_cycle(db, user.id)
    assert cycle is not None
    session = BodyPhotoSession(
        user_id=user.id,
        cycle_id=cycle.id,
        purpose=BodyPhotoPurpose.CYCLE_COMPLETION,
        state=BodyPhotoSessionState.QUEUED,
    )
    db.add(session)
    db.flush()
    for view in BodyPhotoView:
        db.add(
            BodyPhoto(
                session_id=session.id,
                view=view,
                storage_key=f"cycle/{uuid4().hex}.jpg",
                mime_type="image/jpeg",
                byte_size=1024,
                width=600,
                height=1200,
            )
        )
    db.flush()

    analysis = BodyAnalysisService(db).queue(session.id, user.id, _analysis_config())

    assert analysis.cycle_id == cycle.id
    assert analysis.session.cycle_id == cycle.id


def test_body_analysis_cannot_be_queued_for_another_users_photo_session(db: Session) -> None:
    owner = _user(db)
    other = _user(db)
    _plan, _prescribed, cycle, _original, _safe, _unsafe = _plan_with_cycle(db, other.id)
    assert cycle is not None
    session = BodyPhotoSession(
        user_id=other.id,
        cycle_id=cycle.id,
        purpose=BodyPhotoPurpose.CYCLE_COMPLETION,
        state=BodyPhotoSessionState.QUEUED,
    )
    db.add(session)
    db.flush()
    for view in BodyPhotoView:
        db.add(
            BodyPhoto(
                session_id=session.id,
                view=view,
                storage_key=f"cycle/{uuid4().hex}.jpg",
                mime_type="image/jpeg",
                byte_size=1024,
                width=600,
                height=1200,
            )
        )
    db.flush()

    with pytest.raises(BodyAnalysisNotFoundError):
        BodyAnalysisService(db).queue(session.id, owner.id, _analysis_config())
