from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.models import User
from app.body_analysis.comparison_enums import BodyProgressState
from app.body_analysis.comparison_models import BodyProgressComparison
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
from app.workout_cycles.enums import WorkoutCycleStatus
from app.workout_cycles.models import WorkoutCycle, WorkoutCycleFeedback
from app.workouts.enums import WorkoutPlanStatus
from app.workouts.models import WorkoutPlan

ORIGIN = {"Origin": "http://localhost:5173"}


def _payload(
    findings: dict[BodyArea, tuple[BodyAnalysisClassification, float]],
) -> dict[str, object]:
    normalized_findings: list[dict[str, object]] = []
    summaries: dict[str, list[str]] = {
        "visible_strengths": [],
        "priority_areas": [],
        "moderate_attention_areas": [],
        "uncertain_areas": [],
    }
    for area, (classification, confidence) in findings.items():
        if classification is BodyAnalysisClassification.STRENGTH:
            summaries["visible_strengths"].append(area.value)
        elif classification is BodyAnalysisClassification.CLEAR_LAG:
            summaries["priority_areas"].append(area.value)
        elif classification is BodyAnalysisClassification.MILD_LAG:
            summaries["moderate_attention_areas"].append(area.value)
        elif classification is BodyAnalysisClassification.UNCERTAIN:
            summaries["uncertain_areas"].append(area.value)
        normalized_findings.append(
            {
                "body_area": area.value,
                "classification": classification.value,
                "severity": (
                    0.7
                    if classification
                    in {
                        BodyAnalysisClassification.CLEAR_LAG,
                        BodyAnalysisClassification.MILD_LAG,
                    }
                    else None
                ),
                "confidence": confidence,
                "supporting_views": ["front", "back"],
                "explanation": "Visible development was assessed from standardized views.",
                "limitations": [],
                "suggested_training_emphasis": [],
                "medical_review_recommended": False,
            }
        )
    return {
        "schema_version": "1.0",
        "overall_confidence": 0.9,
        "findings": normalized_findings,
        "summary": summaries,
        "requires_coach_review": True,
        "requires_doctor_review": True,
    }


def _session_with_result(
    db: Session,
    user: User,
    *,
    created_at: datetime,
    findings: dict[BodyArea, tuple[BodyAnalysisClassification, float]],
    purpose: BodyPhotoPurpose = BodyPhotoPurpose.PROGRESS_CHECK,
    analysis_schema_version: str = "1.0",
    raw_result: dict[str, object] | None = None,
) -> tuple[BodyPhotoSession, BodyAnalysis, BodyAnalysisResultVersion]:
    session = BodyPhotoSession(
        user_id=user.id,
        purpose=purpose,
        state=BodyPhotoSessionState.REVIEW_PENDING,
        created_at=created_at,
    )
    db.add(session)
    db.flush()
    for view in BodyPhotoView:
        db.add(
            BodyPhoto(
                session_id=session.id,
                view=view,
                storage_key=f"comparison/{uuid4().hex}.jpg",
                mime_type="image/jpeg",
                byte_size=2048,
                width=600,
                height=1200,
            )
        )
    payload = _payload(findings)
    analysis = BodyAnalysis(
        session_id=session.id,
        revision=1,
        provider="openrouter",
        model_id="vision-model",
        prompt_version="body-v1",
        schema_version=analysis_schema_version,
        status=BodyAnalysisStatus.REVIEW_PENDING,
        raw_result=raw_result,
        normalized_result=payload,
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
    return session, analysis, version


def _snapshot(
    session: BodyPhotoSession,
    *,
    measurement_id: object,
    measured_at: datetime,
    weight_kg: float,
    shoulder_circumference_cm: float,
    waist_circumference_cm: float,
    hip_circumference_cm: float,
) -> dict[str, object]:
    return {
        "captured_at": measured_at.isoformat(),
        "confirmed_at": measured_at.isoformat(),
        "profile_updated_at": measured_at.isoformat(),
        "measurement_id": str(measurement_id),
        "measurement_measured_at": measured_at.isoformat(),
        "sex": "other",
        "height_cm": 180,
        "weight_kg": weight_kg,
        "shoulder_circumference_cm": shoulder_circumference_cm,
        "waist_circumference_cm": waist_circumference_cm,
        "hip_circumference_cm": hip_circumference_cm,
        "selected_goal": "build_muscle",
        "photo_versions": [
            {
                "view": photo.view.value,
                "photo_id": str(photo.id),
                "storage_key": photo.storage_key,
                "updated_at": photo.updated_at.isoformat(),
            }
            for photo in session.photos
        ],
    }


def _iso_z(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


def _user(db: Session, prefix: str = "comparison") -> User:
    user = User(email=f"{prefix}-{uuid4()}@example.com", password_hash="hash")
    db.add(user)
    db.commit()
    return user


def _areas(comparison: BodyProgressComparison) -> dict[str, dict[str, object]]:
    items = comparison.normalized_result["areas"]
    assert isinstance(items, list)
    return {str(item["body_area"]): item for item in items if isinstance(item, dict)}


def test_comparison_uses_normalized_classification_confidence_and_common_views(
    db: Session,
) -> None:
    user = _user(db)
    now = datetime.now(UTC)
    _session_with_result(
        db,
        user,
        created_at=now - timedelta(days=40),
        findings={
            BodyArea.SHOULDERS: (BodyAnalysisClassification.CLEAR_LAG, 0.9),
            BodyArea.CHEST: (BodyAnalysisClassification.STRENGTH, 0.85),
            BodyArea.CALVES: (BodyAnalysisClassification.MILD_LAG, 0.8),
            BodyArea.HAMSTRINGS: (BodyAnalysisClassification.UNCERTAIN, 0.4),
        },
    )
    current, _, current_version = _session_with_result(
        db,
        user,
        created_at=now,
        findings={
            BodyArea.SHOULDERS: (BodyAnalysisClassification.MILD_LAG, 0.88),
            BodyArea.CHEST: (BodyAnalysisClassification.STRENGTH, 0.86),
            BodyArea.CALVES: (BodyAnalysisClassification.CLEAR_LAG, 0.82),
            BodyArea.HAMSTRINGS: (BodyAnalysisClassification.NEUTRAL, 0.8),
        },
    )

    comparison = BodyProgressComparisonService(db).create_for_result(current_version.id, user.id)

    assert comparison is not None
    assert comparison.current_session_id == current.id
    areas = _areas(comparison)
    assert areas["shoulders"]["state"] == BodyProgressState.IMPROVED.value
    assert areas["chest"]["state"] == BodyProgressState.UNCHANGED.value
    assert areas["calves"]["state"] == BodyProgressState.DECLINED_OR_LESS_BALANCED.value
    assert areas["hamstrings"]["state"] == BodyProgressState.UNCERTAIN.value
    assert areas["shoulders"]["supporting_views"] == ["back", "front"]
    assert "hypertrophy" not in str(comparison.normalized_result).lower()
    assert "diagnos" not in str(comparison.normalized_result).lower()


def test_low_confidence_or_missing_findings_are_uncertain(db: Session) -> None:
    user = _user(db, "comparison-low-confidence")
    now = datetime.now(UTC)
    _session_with_result(
        db,
        user,
        created_at=now - timedelta(days=35),
        findings={BodyArea.SHOULDERS: (BodyAnalysisClassification.CLEAR_LAG, 0.9)},
    )
    current, _, current_version = _session_with_result(
        db,
        user,
        created_at=now,
        findings={BodyArea.SHOULDERS: (BodyAnalysisClassification.STRENGTH, 0.42)},
    )

    comparison = BodyProgressComparisonService(db).create_for_result(current_version.id, user.id)

    assert comparison is not None
    areas = _areas(comparison)
    assert areas["shoulders"]["state"] == BodyProgressState.UNCERTAIN.value
    assert "low_confidence" in areas["shoulders"]["limitations"]
    assert areas["lats"]["state"] == BodyProgressState.UNCERTAIN.value
    assert comparison.current_session_id == current.id


def test_comparisons_are_idempotent_and_new_result_versions_preserve_history(
    db: Session,
) -> None:
    user = _user(db, "comparison-version")
    now = datetime.now(UTC)
    _session_with_result(
        db,
        user,
        created_at=now - timedelta(days=30),
        findings={BodyArea.SHOULDERS: (BodyAnalysisClassification.CLEAR_LAG, 0.9)},
    )
    current, analysis, first_version = _session_with_result(
        db,
        user,
        created_at=now,
        findings={BodyArea.SHOULDERS: (BodyAnalysisClassification.MILD_LAG, 0.9)},
    )
    service = BodyProgressComparisonService(db)

    first = service.create_for_result(first_version.id, user.id)
    repeated = service.create_for_result(first_version.id, user.id)
    corrected_payload = _payload({BodyArea.SHOULDERS: (BodyAnalysisClassification.NEUTRAL, 0.9)})
    corrected_version = BodyAnalysisResultVersion(
        analysis_id=analysis.id,
        replaces_version_id=first_version.id,
        version=2,
        source=BodyAnalysisResultSource.COACH,
        normalized_result=corrected_payload,
        overall_confidence=0.9,
    )
    db.add(corrected_version)
    db.commit()
    corrected = service.create_for_result(corrected_version.id, user.id)

    assert first is not None and corrected is not None
    assert repeated is not None and repeated.id == first.id
    assert corrected.id != first.id
    assert first.comparison_version == 1
    assert corrected.comparison_version == 2
    assert corrected.current_session_id == current.id
    assert db.scalars(
        select(BodyProgressComparison).where(
            BodyProgressComparison.current_session_id == current.id
        )
    ).all() == [first, corrected]


def test_latest_cycle_feedback_and_user_reported_measurements_are_context_only(
    db: Session,
) -> None:
    user = _user(db, "comparison-feedback")
    now = datetime.now(UTC)
    previous_session, _, _ = _session_with_result(
        db,
        user,
        created_at=now - timedelta(days=60),
        findings={BodyArea.CHEST: (BodyAnalysisClassification.NEUTRAL, 0.9)},
    )
    previous_feedback = _completed_cycle_feedback(
        db,
        user,
        completed_at=previous_session.created_at - timedelta(days=1),
        measurements={"weight_kg": 80.0, "waist_cm": 85, "note": "ignored"},
    )
    current_session, _, current_version = _session_with_result(
        db,
        user,
        created_at=now,
        findings={BodyArea.CHEST: (BodyAnalysisClassification.STRENGTH, 0.9)},
    )
    current_feedback = _completed_cycle_feedback(
        db,
        user,
        completed_at=current_session.created_at - timedelta(hours=1),
        measurements={"weight_kg": 81.0, "waist_cm": 83, "note": "ignored"},
    )

    comparison = BodyProgressComparisonService(db).create_for_result(current_version.id, user.id)

    assert comparison is not None
    context = comparison.context_snapshot
    assert context["previous_feedback_id"] == str(previous_feedback.id)
    assert context["current_feedback_id"] == str(current_feedback.id)
    assert context["user_reported_measurement_changes"] == {
        "waist_cm": {"previous": 85.0, "current": 83.0, "delta": -2.0},
        "weight_kg": {"previous": 80.0, "current": 81.0, "delta": 1.0},
    }
    assert "note" not in str(context)
    assert "performance_changes" not in str(comparison.normalized_result)


def test_v4_comparison_uses_exact_snapshots_and_controlled_provenance(db: Session) -> None:
    user = _user(db, "comparison-v4")
    now = datetime.now(UTC)
    previous_session, _, _ = _session_with_result(
        db,
        user,
        created_at=now - timedelta(days=40),
        findings={
            BodyArea.SHOULDERS: (BodyAnalysisClassification.NEUTRAL, 0.9),
            BodyArea.LATS: (BodyAnalysisClassification.CLEAR_LAG, 0.9),
        },
        analysis_schema_version="4.0",
    )
    previous_measurement_id = uuid4()
    previous_analysis = db.scalar(
        select(BodyAnalysis).where(BodyAnalysis.session_id == previous_session.id)
    )
    assert previous_analysis is not None
    previous_analysis.raw_result = {
        "input_snapshot": _snapshot(
            previous_session,
            measurement_id=previous_measurement_id,
            measured_at=now - timedelta(days=41),
            weight_kg=80.0,
            shoulder_circumference_cm=118.0,
            waist_circumference_cm=84.0,
            hip_circumference_cm=98.0,
        )
    }
    db.commit()

    current_session, _, current_version = _session_with_result(
        db,
        user,
        created_at=now,
        findings={
            BodyArea.SHOULDERS: (BodyAnalysisClassification.STRENGTH, 0.9),
            BodyArea.LATS: (BodyAnalysisClassification.CLEAR_LAG, 0.9),
        },
        analysis_schema_version="4.0",
    )
    current_measurement_id = uuid4()
    current_analysis = db.scalar(
        select(BodyAnalysis).where(BodyAnalysis.session_id == current_session.id)
    )
    assert current_analysis is not None
    current_analysis.raw_result = {
        "input_snapshot": _snapshot(
            current_session,
            measurement_id=current_measurement_id,
            measured_at=now - timedelta(days=1),
            weight_kg=81.25,
            shoulder_circumference_cm=120.5,
            waist_circumference_cm=82.0,
            hip_circumference_cm=99.0,
        )
    }
    db.commit()

    comparison = BodyProgressComparisonService(db).create_for_result(
        current_version.id,
        user.id,
    )

    assert comparison is not None
    assert comparison.schema_version == "2.0"
    result = comparison.normalized_result
    assert result["schema_version"] == "2.0"
    assert result["interval_days"] == 40
    deltas = {
        item["measurement"]: item
        for item in result["measurement_deltas"]
        if isinstance(item, dict)
    }
    assert deltas["waist_circumference_cm"] == {
        "measurement": "waist_circumference_cm",
        "unit": "cm",
        "previous": 84.0,
        "current": 82.0,
        "delta": -2.0,
        "availability": "exact",
        "provenance": {
            "previous": {
                "source": "body_analysis_input_snapshot",
                "reference_id": str(previous_measurement_id),
                "recorded_at": _iso_z(now - timedelta(days=41)),
                "reason_code": "exact_analysis_input_snapshot",
            },
            "current": {
                "source": "body_analysis_input_snapshot",
                "reference_id": str(current_measurement_id),
                "recorded_at": _iso_z(now - timedelta(days=1)),
                "reason_code": "exact_analysis_input_snapshot",
            },
        },
    }
    transitions = {
        item["body_area"]: item
        for item in result["visual_transitions"]
        if isinstance(item, dict)
    }
    assert transitions["shoulders"]["state"] == "improved"
    assert "classification_changed" in transitions["shoulders"]["reason_codes"]
    assert transitions["shoulders"]["provenance"]["previous"]["source"] == "normalized_result"
    assert result["persistent_priorities"] == [
        {
            "body_area": "lats",
            "provenance": {
                "previous": {
                    "source": "normalized_result",
                    "reference_id": str(_session_version_id(db, previous_session.id)),
                    "recorded_at": _iso_z(now - timedelta(days=40)),
                    "reason_code": "effective_normalized_result",
                },
                "current": {
                    "source": "normalized_result",
                    "reference_id": str(current_version.id),
                    "recorded_at": _iso_z(current_version.created_at),
                    "reason_code": "effective_normalized_result",
                },
            },
        }
    ]


def _session_version_id(db: Session, session_id: object) -> object:
    session = db.get(BodyPhotoSession, session_id)
    assert session is not None
    analysis = db.scalar(select(BodyAnalysis).where(BodyAnalysis.session_id == session.id))
    assert analysis is not None
    version = db.scalar(
        select(BodyAnalysisResultVersion).where(
            BodyAnalysisResultVersion.analysis_id == analysis.id
        )
    )
    assert version is not None
    return version.id


def test_legacy_comparison_remains_schema_v1_without_guessed_measurements(db: Session) -> None:
    user = _user(db, "comparison-legacy")
    now = datetime.now(UTC)
    _session_with_result(
        db,
        user,
        created_at=now - timedelta(days=10),
        findings={BodyArea.SHOULDERS: (BodyAnalysisClassification.NEUTRAL, 0.9)},
    )
    current, _, current_version = _session_with_result(
        db,
        user,
        created_at=now,
        findings={BodyArea.SHOULDERS: (BodyAnalysisClassification.STRENGTH, 0.9)},
    )

    comparison = BodyProgressComparisonService(db).create_for_result(current_version.id, user.id)

    assert comparison is not None
    assert comparison.schema_version == "1.0"
    assert comparison.normalized_result["schema_version"] == "1.0"
    assert "measurement_deltas" not in comparison.normalized_result
    assert comparison.current_session_id == current.id


def _completed_cycle_feedback(
    db: Session,
    user: User,
    *,
    completed_at: datetime,
    measurements: dict[str, object],
) -> WorkoutCycleFeedback:
    plan = WorkoutPlan(
        user_id=user.id,
        status=WorkoutPlanStatus.SUPERSEDED,
        generation_signature=uuid4().hex * 2,
        profile_snapshot={"plan_duration_weeks": 4},
        provider="fake",
        model_id="fake-model",
        prompt_version="v1",
        generation_policy_version="v1",
        candidate_set_hash=uuid4().hex * 2,
        generation_method="deterministic",
    )
    db.add(plan)
    db.flush()
    cycle = WorkoutCycle(
        user_id=user.id,
        workout_plan_id=plan.id,
        duration_weeks=4,
        status=WorkoutCycleStatus.COMPLETED,
        completed_at=completed_at,
        started_at=completed_at - timedelta(weeks=4),
    )
    db.add(cycle)
    db.flush()
    feedback = WorkoutCycleFeedback(
        cycle_id=cycle.id,
        adherence_percent=85,
        performance_changes="User reported improved training performance.",
        pain_or_limitation_feedback=None,
        measurements=measurements,
        submitted_at=completed_at,
    )
    db.add(feedback)
    db.commit()
    return feedback


def _register(client: TestClient, email: str) -> None:
    response = client.post(
        "/api/v1/auth/register",
        headers=ORIGIN,
        json={"email": email, "password": "long password"},
    )
    assert response.status_code == 201


def test_comparison_api_is_owner_only_and_first_session_returns_null(
    client: TestClient,
    db: Session,
) -> None:
    email = f"comparison-api-{uuid4()}@example.com"
    _register(client, email)
    owner = db.scalar(select(User).where(User.email == email))
    assert owner is not None
    now = datetime.now(UTC)
    first_session, _, _ = _session_with_result(
        db,
        owner,
        created_at=now - timedelta(days=30),
        findings={BodyArea.SHOULDERS: (BodyAnalysisClassification.CLEAR_LAG, 0.9)},
    )
    current_session, _, _ = _session_with_result(
        db,
        owner,
        created_at=now,
        findings={BodyArea.SHOULDERS: (BodyAnalysisClassification.MILD_LAG, 0.9)},
    )

    first = client.get(f"/api/v1/body-photo-sessions/{first_session.id}/comparison")
    current = client.get(f"/api/v1/body-photo-sessions/{current_session.id}/comparison")

    assert first.status_code == 200
    assert first.json() is None
    assert current.status_code == 200
    assert current.json()["normalized_result"]["areas"][0]["body_area"] == "shoulders"
    assert "user_id" not in current.text
    assert client.post("/api/v1/auth/logout", headers=ORIGIN).status_code == 204
    _register(client, f"comparison-other-{uuid4()}@example.com")
    forbidden = client.get(f"/api/v1/body-photo-sessions/{current_session.id}/comparison")
    assert forbidden.status_code == 404
