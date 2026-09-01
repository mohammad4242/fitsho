from __future__ import annotations

import json
from typing import Any
from uuid import UUID, uuid4

import httpx
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.body_analysis.admin_config.enums import (
    AIAgentName,
    AIExecutionBackend,
    AIProviderName,
    AITaskType,
)
from app.body_analysis.admin_config.models import AITaskConfig
from app.body_analysis.models import BodyAnalysis
from app.body_photos.enums import BodyPhotoSessionState
from app.body_photos.models import BodyPhotoSession
from app.config import Settings
from tests.body_photos.test_session_api import ORIGIN, _png


def _v3_payload() -> dict[str, Any]:
    areas = (
        "shoulders",
        "chest",
        "back",
        "lats",
        "arms",
        "forearms",
        "waist_midsection",
        "glutes",
        "quads",
        "hamstrings",
        "calves",
        "symmetry",
        "visible_alignment_or_posture",
    )
    checklist = {
        "rating": "average",
        "evidence_fa": "شواهد بصری کافی برای ارزیابی اولیه وجود دارد.",
    }
    return {
        "assessment_status": "complete",
        "photo_quality": {
            "front": {"usable": True, "issues_fa": []},
            "side": {"usable": True, "issues_fa": []},
            "back": {"usable": True, "issues_fa": []},
            "global_limitations_fa": [],
        },
        "overall_assessment": {
            "development_pattern": "visually_balanced",
            "shoulder_to_waist_taper": "moderate",
            "upper_lower_balance": "balanced",
            "summary_fa": "این نتیجه یک بررسی بصری اولیه و غیرتشخیصی است.",
        },
        "goal_suggestion": {
            "suggested_goal": "build_muscle",
            "reasoning_fa": "این پیشنهاد فقط بر اساس شواهد بصری ثبت‌شده ارائه شده است.",
            "inputs_unavailable_fa": [],
        },
        "findings": [
            {
                "area": area,
                "front": checklist,
                "side": checklist,
                "back": checklist,
                "overall_rating": "average",
                "overall_summary_fa": "ارزیابی بصری خنثی و محدود به همین تصویرهاست.",
                "confidence": 0.86,
                "suggested_training_emphasis": [],
            }
            for area in areas
        ],
    }


def _register_and_submit(client: TestClient, email: str) -> UUID:
    registered = client.post(
        "/api/v1/auth/register",
        headers=ORIGIN,
        json={"email": email, "password": "long password"},
    )
    assert registered.status_code == 201
    created = client.post(
        "/api/v1/body-photo-sessions",
        headers=ORIGIN,
        json={"purpose": "progress_check"},
    )
    assert created.status_code == 201
    session_id = UUID(created.json()["id"])
    for view in ("front", "side", "back"):
        uploaded = client.put(
            f"/api/v1/body-photo-sessions/{session_id}/photos/{view}",
            headers=ORIGIN,
            files={"file": (f"{view}.png", _png(), "image/png")},
        )
        assert uploaded.status_code == 200
    submitted = client.post(
        f"/api/v1/body-photo-sessions/{session_id}/submit",
        headers=ORIGIN,
        json={
            "operational_processing": {"granted": True, "version": "operational-v1"},
            "model_training": {"granted": False, "version": "training-v1"},
        },
    )
    assert submitted.status_code == 200
    return session_id


def test_body_analysis_agent_service_e2e_uses_current_images_and_normalizes_v3(
    client: TestClient,
    db: Session,
    test_settings: Settings,
) -> None:
    test_settings.body_photo_storage_root = test_settings.media_root.parent / "body-private"
    test_settings.agent_service_token = SecretStr("agent-service-test-token")
    test_settings.agent_service_base_url = "http://agent-service.test"
    task = AITaskConfig(
        task_type=AITaskType.BODY_PHOTO_ANALYSIS,
        provider=AIProviderName.OPENROUTER,
        execution_backend=AIExecutionBackend.AGENT_SERVICE,
        agent_name=AIAgentName.ANTIGRAVITY,
        agent_model_id="gemini-test",
        enabled=True,
        temperature=0.0,
        max_output_tokens=4096,
        timeout_seconds=30,
        minimum_confidence=0.7,
    )
    db.add(task)
    db.commit()

    calls: list[tuple[str, bytes]] = []

    def agent_handler(request: httpx.Request) -> httpx.Response:
        body = request.content
        calls.append((request.url.path, body))
        assert request.url.path == "/v1/analyze-stored-images"
        assert request.headers["authorization"] == "Bearer agent-service-test-token"
        assert request.headers["content-type"] == "application/json"
        assert b"base64_data" not in body
        stored_request = json.loads(body)
        assert sorted(image["label"] for image in stored_request["images"]) == [
            "back",
            "front",
            "side",
        ]
        assert all(image["storage_scope"] == "body" for image in stored_request["images"])
        assert all(image["storage_key"] for image in stored_request["images"])
        return httpx.Response(
            200,
            json={
                "payload": (
                    {"accepted": True, "confidence": 0.99, "issues": []}
                    if len(calls) == 1
                    else _v3_payload()
                ),
                "agent": "antigravity",
                "model_id": "gemini-test",
                "request_id": f"agent-e2e-{len(calls)}",
                "duration_seconds": 0.1,
                "input_tokens": 11,
                "output_tokens": 7,
            },
        )

    def api_handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError(f"OpenRouter/API transport was called: {request.url}")

    old_agent = client.app.state.agent_http_client
    old_api = client.app.state.ai_http_client
    client.app.state.agent_http_client = httpx.AsyncClient(
        transport=httpx.MockTransport(agent_handler)
    )
    client.app.state.ai_http_client = httpx.AsyncClient(transport=httpx.MockTransport(api_handler))
    try:
        session_id = _register_and_submit(client, f"agent-e2e-{uuid4()}@example.com")
        started = client.post(f"/api/v1/body-photo-sessions/{session_id}/analysis", headers=ORIGIN)
        assert started.status_code == 202

        analysis = db.scalar(
            select(BodyAnalysis).join(BodyPhotoSession).where(BodyAnalysis.session_id == session_id)
        )
        assert analysis is not None
        assert analysis.status.value == "review_pending"
        assert analysis.provider == "agent_service:antigravity"
        assert analysis.schema_version == "3.0"
        assert analysis.visual_result is not None
        assert analysis.normalized_result is not None
        assert analysis.normalized_result["schema_version"] == "3.0"
        assert analysis.normalized_result["requires_coach_review"] is True
        assert analysis.normalized_result["requires_doctor_review"] is True
        session = db.get(BodyPhotoSession, session_id)
        assert session is not None and session.state is BodyPhotoSessionState.REVIEW_PENDING
        assert len(calls) == 2
        assert all(path == "/v1/analyze-stored-images" for path, _ in calls)
    finally:
        import asyncio

        asyncio.run(client.app.state.agent_http_client.aclose())
        asyncio.run(client.app.state.ai_http_client.aclose())
        client.app.state.agent_http_client = old_agent
        client.app.state.ai_http_client = old_api
