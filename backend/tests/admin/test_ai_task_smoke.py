import asyncio
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

import httpx
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.models import User
from app.body_analysis.admin_config.enums import AIAgentName, AITaskType
from app.body_analysis.admin_config.models import AIAgentProfileVerification
from app.body_analysis.admin_config.schemas import (
    AgentServiceModelProfile,
    AgentServiceTaskSmokeRequest,
)
from app.body_analysis.admin_config.task_smoke import TaskSmokeResult, run_task_smoke
from app.body_analysis.enums import BodyArea
from app.body_analysis.providers.models import (
    ImageInput,
    StructuredGenerationRequest,
    StructuredGenerationResponse,
)
from app.config import Settings
from app.nutrition.food_photo_service import build_food_photo_request

ORIGIN = {"Origin": "http://localhost:5173"}


def _register_admin(client: TestClient, db: Session) -> None:
    response = client.post(
        "/api/v1/auth/register",
        headers=ORIGIN,
        json={"email": "task-smoke-admin@example.com", "password": "long password"},
    )
    assert response.status_code == 201
    user = db.scalar(select(User).where(User.email == "task-smoke-admin@example.com"))
    assert user is not None
    user.is_admin = True
    db.commit()


def test_task_smoke_request_allows_only_catalog_profile_reference() -> None:
    request = AgentServiceTaskSmokeRequest(
        task_type="food_price_search",
        agent="antigravity",
        profile_id="antigravity-gemini-3.7-flash-high",
    )

    assert request.task_type.value == "food_price_search"
    assert request.profile_id == "antigravity-gemini-3.7-flash-high"


def _profile() -> AgentServiceModelProfile:
    return AgentServiceModelProfile(
        profile_id="antigravity-gemini-smoke-high",
        agent=AIAgentName.ANTIGRAVITY,
        display_name="Gemini Smoke (High)",
        model_id="gemini-smoke",
        effort="high",
        task_kinds=[
            AITaskType.WORKOUT_PLAN_GENERATION,
            AITaskType.BODY_PHOTO_ANALYSIS,
            AITaskType.FOOD_PHOTO_ESTIMATION,
            AITaskType.FOOD_PRICE_SEARCH,
        ],
        fingerprint="a" * 64,
        supports_text_input=True,
        supports_image_input=True,
        supports_structured_output=True,
    )


def _capabilities_handler(
    profile: AgentServiceModelProfile,
) -> Callable[[httpx.Request], httpx.Response]:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.path == "/v1/capabilities"
        return httpx.Response(
            200,
            json={
                "runners": [
                    {
                        "agent": "antigravity",
                        "installed": True,
                        "version": "1.1.22",
                        "auth_state": "authenticated",
                        "auth_mode": "browser_link",
                        "models": [],
                        "profiles": [profile.model_dump(mode="json")],
                    }
                ]
            },
        )

    return handler


class _SmokeProvider:
    def __init__(self) -> None:
        self.requests: list[tuple[str, StructuredGenerationRequest, tuple[ImageInput, ...]]] = []

    async def generate_structured_text(
        self, request: StructuredGenerationRequest
    ) -> StructuredGenerationResponse:
        self.requests.append(("text", request, ()))
        if request.schema_name == "fitsho_ai_coach_recommendation":
            payload: dict[str, Any] = {
                "selected_candidate_id": "smoke-upper",
                "program_explanation_fa": "برنامهٔ نمونه از کاندیدای معتبر انتخاب شد.",
                "day_explanations": [],
            }
        else:
            payload = {
                "query": "قیمت برنج ایرانی یک کیلویی در تهران",
                "quotes": [
                    {
                        "product_name": "برنج ایرانی",
                        "price": 100000,
                        "currency": "TOMAN",
                        "source_url": "https://example.com/price",
                    }
                ],
            }
        return StructuredGenerationResponse(
            payload=payload,
            model_id=request.route.primary_model,
            attempted_models=(request.route.primary_model,),
            provider_request_id=f"request-{len(self.requests)}",
        )

    async def analyze_images(
        self,
        request: StructuredGenerationRequest,
        *,
        images: tuple[ImageInput, ...],
    ) -> StructuredGenerationResponse:
        self.requests.append(("image", request, images))
        if request.schema_name == "fitsho_body_photo_preflight":
            payload: dict[str, Any] = {"accepted": True, "confidence": 1, "issues": []}
        elif request.schema_name == "fitsho_physique_assessment_v3":
            payload = _body_output()
        else:
            payload = {
                "meal_name_guess": "نمونه غذا",
                "items": [
                    {
                        "name_guess": "rice",
                        "estimated_amount": 100,
                        "unit": "g",
                        "confidence": 0.9,
                        "visible_evidence": ["visible portion"],
                        "uncertainties": [],
                    }
                ],
                "overall_confidence": 0.9,
                "needs_user_confirmation": False,
            }
        return StructuredGenerationResponse(
            payload=payload,
            model_id=request.route.primary_model,
            attempted_models=(request.route.primary_model,),
            provider_request_id=f"request-{len(self.requests)}",
        )

    def normalize_error(self, error: Exception) -> Exception:
        return error


def _body_output() -> dict[str, Any]:
    findings = []
    for area in BodyArea:
        findings.append(
            {
                "area": area.value,
                "front": {"rating": "average", "evidence_fa": "نمای روبه‌رو قابل مشاهده است."},
                "side": {"rating": "average", "evidence_fa": "نمای جانبی قابل مشاهده است."},
                "back": {"rating": "average", "evidence_fa": "نمای پشت قابل مشاهده است."},
                "overall_rating": "average",
                "overall_summary_fa": "مقایسهٔ بصری نمونه انجام شد.",
                "confidence": 0.8,
            }
        )
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
            "summary_fa": "خلاصهٔ بصری نمونه.",
        },
        "goal_suggestion": {
            "suggested_goal": "build_muscle",
            "reasoning_fa": "هدف نمونه برای آزمون قرارداد انتخاب شد.",
            "inputs_unavailable_fa": [],
        },
        "findings": findings,
    }


def test_task_smoke_runs_all_four_safe_fixtures(db: Session, test_settings: Settings) -> None:
    test_settings.agent_service_token = "agent-service-test-token"
    profile = _profile()
    provider = _SmokeProvider()
    client = httpx.AsyncClient(transport=httpx.MockTransport(_capabilities_handler(profile)))

    async def run() -> list[Any]:
        return [
            await run_task_smoke(
                db,
                task_type=task,
                agent=AIAgentName.ANTIGRAVITY,
                profile_id=profile.profile_id,
                settings=test_settings,
                client=client,
                provider=provider,
            )
            for task in (
                AITaskType.WORKOUT_PLAN_GENERATION,
                AITaskType.BODY_PHOTO_ANALYSIS,
                AITaskType.FOOD_PHOTO_ESTIMATION,
                AITaskType.FOOD_PRICE_SEARCH,
            )
        ]

    try:
        results = asyncio.run(run())
    finally:
        asyncio.run(client.aclose())

    assert all(result.passed for result, _ in results)
    assert [result.request_id for result, _ in results] == [
        "request-1",
        "request-3",
        "request-4",
        "request-5",
    ]
    body_images = [images for kind, request, images in provider.requests if kind == "image"]
    assert len(body_images[0]) == 3
    assert len(body_images[1]) == 3
    assert len(body_images[2]) == 1
    food_request = next(
        request
        for kind, request, _ in provider.requests
        if kind == "image" and request.schema_name == "fitsho_food_photo_estimate_v1"
    )
    assert food_request == build_food_photo_request(
        primary_model=profile.model_id,
        fallback_models=(),
        provider_preferences=ProviderRoutingPreferences(),
        temperature=0,
        max_output_tokens=1024,
    )
    price_request = next(
        request
        for kind, request, _ in provider.requests
        if kind == "text" and request.schema_name == "fitsho_food_price_search_v1"
    )
    assert price_request.input_payload["fixture_revision"] == "agent-task-fixtures-v1"


def test_task_smoke_verification_record_is_task_scoped(db: Session) -> None:
    db.add(
        AIAgentProfileVerification(
            profile_id="antigravity-gemini-smoke-high",
            task_type=AITaskType.FOOD_PRICE_SEARCH,
            profile_fingerprint="a" * 64,
            status="passed",
            checked_at=datetime.now(UTC),
            duration_seconds=0.2,
        )
    )
    db.commit()

    row = db.scalar(
        select(AIAgentProfileVerification).where(
            AIAgentProfileVerification.profile_id == "antigravity-gemini-smoke-high",
            AIAgentProfileVerification.task_type == AITaskType.FOOD_PRICE_SEARCH,
        )
    )
    assert row is not None
    assert row.status == "passed"


def test_task_smoke_endpoint_persists_result_without_user_data(
    client: TestClient,
    db: Session,
    test_settings: Settings,
    monkeypatch: Any,
) -> None:
    _register_admin(client, db)
    test_settings.agent_service_token = "agent-service-test-token-with-32-bytes-123"
    profile = _profile()

    async def fake_smoke(
        *args: Any, **kwargs: Any
    ) -> tuple[TaskSmokeResult, AgentServiceModelProfile]:
        del args, kwargs
        return (
            TaskSmokeResult(
                passed=True,
                stage="passed",
                request_id="smoke-request",
                duration_seconds=0.3,
            ),
            profile,
        )

    monkeypatch.setattr("app.body_analysis.admin_config.router.run_task_smoke", fake_smoke)
    response = client.post(
        "/api/v1/admin/ai/agent-service/task-smoke",
        headers=ORIGIN,
        json={
            "task_type": "food_price_search",
            "agent": "antigravity",
            "profile_id": profile.profile_id,
        },
    )

    assert response.status_code == 200, response.text
    assert response.json()["ok"] is True
    assert response.json()["request_id"] == "smoke-request"
    row = db.scalar(
        select(AIAgentProfileVerification).where(
            AIAgentProfileVerification.profile_id == profile.profile_id,
            AIAgentProfileVerification.task_type == AITaskType.FOOD_PRICE_SEARCH,
        )
    )
    assert row is not None
    assert row.status == "passed"
    assert row.profile_fingerprint == profile.fingerprint
