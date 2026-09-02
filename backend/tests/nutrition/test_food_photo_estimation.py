import io
from datetime import date
from pathlib import Path
from typing import Any, cast

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.ai.task_provider import ConfiguredAIProvider
from app.body_analysis.admin_config.enums import (
    AIAgentName,
    AIExecutionBackend,
    AIProviderName,
    AITaskType,
)
from app.body_analysis.admin_config.models import AITaskConfig
from app.body_analysis.providers import AIProvider
from app.body_analysis.providers.models import (
    AIProviderError,
    ImageInput,
    ProviderErrorCode,
    ProviderRoutingPreferences,
    StructuredGenerationRequest,
    StructuredGenerationResponse,
)
from app.config import Settings
from app.nutrition.food_photo_service import _normalize_image, build_food_photo_request
from app.nutrition.models import (
    NutritionConsumptionEntry,
    NutritionFoodPhotoEstimate,
    NutritionOperationalEvent,
)
from tests.nutrition.test_weekly_plan_api import ORIGIN, _seed_foods_and_prices


class FakeVisionProvider:
    def __init__(self, model_id: str = "test/vision", storage_root: Path | None = None) -> None:
        self.model_id = model_id
        self.storage_root = storage_root
        self.requests: list[StructuredGenerationRequest] = []
        self.images: list[tuple[ImageInput, ...]] = []

    async def analyze_images(
        self, request: StructuredGenerationRequest, *, images: tuple[ImageInput, ...]
    ) -> StructuredGenerationResponse:
        self.requests.append(request)
        self.images.append(images)
        assert images[0].mime_type == "image/jpeg"
        if self.storage_root is not None:
            assert images[0].storage_key is not None
            assert (self.storage_root / images[0].storage_key).is_file()
        assert "email" not in str(request.input_payload).lower()
        return StructuredGenerationResponse(
            payload={
                "meal_name_guess": "مرغ",
                "items": [
                    {
                        "name_guess": "task6-chicken",
                        "estimated_amount": 140,
                        "unit": "g",
                        "confidence": 0.82,
                        "visible_evidence": ["portion visible"],
                        "uncertainties": ["depth unknown"],
                    }
                ],
                "overall_confidence": 0.78,
                "needs_user_confirmation": True,
            },
            model_id=self.model_id,
            attempted_models=(self.model_id,),
            input_tokens=100,
            output_tokens=40,
            cost="0.001",
        )


class FailingVisionProvider:
    async def analyze_images(
        self, request: StructuredGenerationRequest, *, images: tuple[ImageInput, ...]
    ) -> StructuredGenerationResponse:
        raise AIProviderError(
            ProviderErrorCode.PROVIDER_UNAVAILABLE,
            "provider unavailable",
        )


class InvalidOutputVisionProvider:
    async def analyze_images(
        self, request: StructuredGenerationRequest, *, images: tuple[ImageInput, ...]
    ) -> StructuredGenerationResponse:
        return StructuredGenerationResponse(
            payload={"items": [], "overall_confidence": 0.5, "needs_user_confirmation": True},
            model_id="gemini-test",
            attempted_models=("gemini-test",),
        )


def _configured_provider(
    provider: Any, *, name: str, model_id: str
) -> ConfiguredAIProvider:
    return ConfiguredAIProvider(
        provider=cast(AIProvider, provider),
        provider_name=name,
        primary_model_id=model_id,
        fallback_model_ids=(),
        routing_preferences=ProviderRoutingPreferences(),
        supports_cost_accounting=name == "openrouter",
    )


def _image() -> bytes:
    output = io.BytesIO()
    Image.new("RGB", (100, 100), "white").save(output, "PNG")
    return output.getvalue()


def test_food_photo_request_builder_is_the_canonical_task_contract() -> None:
    request = build_food_photo_request(
        primary_model="vision-primary",
        fallback_models=("vision-fallback",),
        provider_preferences=ProviderRoutingPreferences(zdr=True),
        temperature=0.2,
        max_output_tokens=777,
    )

    assert request.system_prompt == (
        "Identify only visible foods and estimate portions. Return uncertainty. "
        "Do not provide calories, medical advice, allergy claims, or suitability."
    )
    assert request.input_payload == {
        "instruction": "Analyze this food image without personal data."
    }
    assert request.schema_name == "fitsho_food_photo_estimate_v1"
    assert request.route.primary_model == "vision-primary"
    assert request.route.fallback_models == ("vision-fallback",)
    assert request.provider_preferences == ProviderRoutingPreferences(zdr=True)
    assert request.temperature == 0.2
    assert request.max_output_tokens == 777
    assert request.web_access == "disabled"


def _register(client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/register",
        headers=ORIGIN,
        json={"email": "food-photo@example.com", "password": "long password"},
    )
    assert response.status_code == 201


def test_photo_requires_explicit_consent(client: TestClient) -> None:
    _register(client)
    response = client.post(
        "/api/v1/nutrition/tracking/photo-estimates",
        headers={**ORIGIN, "X-Fitsho-Food-Photo-Consent": "false"},
        files={"file": ("meal.png", _image(), "image/png")},
    )
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "THIRD_PARTY_PROCESSING_CONSENT_REQUIRED"


def test_photo_estimation_is_safely_disabled_without_openrouter_task_config(
    client: TestClient,
) -> None:
    _register(client)
    response = client.post(
        "/api/v1/nutrition/tracking/photo-estimates",
        headers={**ORIGIN, "X-Fitsho-Food-Photo-Consent": "true"},
        files={"file": ("meal.png", _image(), "image/png")},
    )
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "FOOD_PHOTO_ESTIMATION_DISABLED"


def test_photo_estimate_maps_catalogue_and_writes_only_after_confirmation(
    client: TestClient,
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
    test_settings: Settings,
) -> None:
    test_settings.food_photo_rate_limit = 1
    _register(client)
    _seed_foods_and_prices(db)
    db.add(
        AITaskConfig(
            task_type=AITaskType.FOOD_PHOTO_ESTIMATION,
            provider=AIProviderName.OPENROUTER,
            enabled=True,
            primary_model_id="test/vision",
        )
    )
    db.flush()
    monkeypatch.setattr(
        "app.nutrition.food_photo_service.decrypted_key", lambda *_args, **_kwargs: "secret"
    )
    monkeypatch.setattr(
        "app.nutrition.food_photo_service.build_task_provider",
        lambda *_args, **_kwargs: _configured_provider(
            FakeVisionProvider(), name="openrouter", model_id="test/vision"
        ),
    )

    estimated = client.post(
        "/api/v1/nutrition/tracking/photo-estimates",
        headers={
            **ORIGIN,
            "X-Fitsho-Food-Photo-Consent": "true",
            "Idempotency-Key": "meal-photo-request-1",
        },
        files={"file": ("meal.png", _image(), "image/png")},
    )
    assert estimated.status_code == 201, estimated.text
    body = estimated.json()
    assert body["needs_user_confirmation"] is True
    assert body["items"][0]["mapping_status"] == "resolved"
    assert db.scalar(select(NutritionConsumptionEntry)) is None
    replayed = client.post(
        "/api/v1/nutrition/tracking/photo-estimates",
        headers={
            **ORIGIN,
            "X-Fitsho-Food-Photo-Consent": "true",
            "Idempotency-Key": "meal-photo-request-1",
        },
        files={"file": ("meal.png", _image(), "image/png")},
    )
    assert replayed.status_code == 201
    assert replayed.json()["id"] == body["id"]
    assert db.scalar(select(func.count()).select_from(NutritionFoodPhotoEstimate)) == 1

    grant = client.post(
        f"/api/v1/nutrition/tracking/photo-estimates/{body['id']}/access-grant",
        headers=ORIGIN,
    )
    assert grant.status_code == 200
    assert client.get(grant.json()["access_url"]).headers["content-type"] == "image/jpeg"

    corrected = client.patch(
        f"/api/v1/nutrition/tracking/photo-estimates/{body['id']}/items/{body['items'][0]['item_id']}",
        headers=ORIGIN,
        json={"estimated_amount": 90},
    )
    assert corrected.status_code == 200, corrected.text
    assert corrected.json()["items"][0]["estimated_amount"] == 90

    confirmed = client.post(
        f"/api/v1/nutrition/tracking/photo-estimates/{body['id']}/confirm",
        headers=ORIGIN,
        json={"entry_date": date.today().isoformat()},
    )
    assert confirmed.status_code == 200
    entry = db.scalar(select(NutritionConsumptionEntry))
    assert entry is not None
    assert float(entry.quantity_grams or 0) == 90
    assert entry.source.value == "photo_estimated_confirmed"
    assert entry.warning_codes == ["PHOTO_ESTIMATE_APPROXIMATE"]

    deleted = client.delete(
        f"/api/v1/nutrition/tracking/photo-estimates/{body['id']}", headers=ORIGIN
    )
    assert deleted.status_code == 204
    estimate = db.scalar(select(NutritionFoodPhotoEstimate))
    assert estimate is not None and estimate.status == "deleted"
    assert estimate.raw_estimate == {}


def test_agent_photo_estimate_uses_agent_metadata_without_api_credential_decrypt(
    client: TestClient,
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
    test_settings: Settings,
) -> None:
    _register(client)
    _seed_foods_and_prices(db)
    db.add(
        AITaskConfig(
            task_type=AITaskType.FOOD_PHOTO_ESTIMATION,
            provider=AIProviderName.OPENROUTER,
            execution_backend=AIExecutionBackend.AGENT_SERVICE,
            agent_name=AIAgentName.ANTIGRAVITY,
            enabled=True,
            agent_model_id="gemini-test",
        )
    )
    db.flush()
    monkeypatch.setattr(
        "app.nutrition.food_photo_service.decrypted_key",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("API credentials must not be decrypted for Agent Service")
        ),
    )
    provider = FakeVisionProvider(
        model_id="gemini-test", storage_root=test_settings.food_photo_storage_root
    )
    monkeypatch.setattr(
        "app.nutrition.food_photo_service.build_task_provider",
        lambda *_args, **_kwargs: _configured_provider(
            provider, name="agent_service:antigravity", model_id="gemini-test"
        ),
    )

    response = client.post(
        "/api/v1/nutrition/tracking/photo-estimates",
        headers={**ORIGIN, "X-Fitsho-Food-Photo-Consent": "true"},
        files={"file": ("meal.png", _image(), "image/png")},
    )

    assert response.status_code == 201, response.text
    assert provider.requests == [
        build_food_photo_request(
            primary_model="gemini-test",
            fallback_models=(),
            provider_preferences=ProviderRoutingPreferences(),
            temperature=0.0,
            max_output_tokens=4096,
        )
    ]
    assert len(provider.images) == 1
    assert provider.images[0][0].label == "food_photo"
    assert provider.images[0][0].mime_type == "image/jpeg"
    assert provider.images[0][0].storage_scope == "food"
    assert provider.images[0][0].storage_key
    assert provider.images[0][0].base64_data is None
    normalized, normalized_mime = _normalize_image(
        _image(), test_settings.food_photo_max_pixels
    )
    assert normalized_mime == "image/jpeg"
    stored_path = test_settings.food_photo_storage_root / provider.images[0][0].storage_key
    assert stored_path.is_file()
    assert stored_path.read_bytes() == normalized
    body = response.json()
    assert body["model_id"] == "gemini-test"
    estimate = db.get(NutritionFoodPhotoEstimate, body["id"])
    assert estimate is not None
    assert estimate.provider == "agent_service:antigravity"
    assert estimate.model_id == "gemini-test"
    event = db.scalar(
        select(NutritionOperationalEvent).where(
            NutritionOperationalEvent.event_name == "food_photo_estimation",
            NutritionOperationalEvent.status == "success",
        )
    )
    assert event is not None and event.provider == "agent_service:antigravity"


def test_agent_photo_invalid_output_is_rejected_and_stored_photo_removed(
    client: TestClient,
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
    test_settings: Settings,
    tmp_path: Path,
) -> None:
    test_settings.food_photo_storage_root = tmp_path / "food-photos"
    _register(client)
    db.add(
        AITaskConfig(
            task_type=AITaskType.FOOD_PHOTO_ESTIMATION,
            provider=AIProviderName.OPENROUTER,
            execution_backend=AIExecutionBackend.AGENT_SERVICE,
            agent_name=AIAgentName.ANTIGRAVITY,
            enabled=True,
            agent_model_id="gemini-test",
        )
    )
    db.flush()
    monkeypatch.setattr(
        "app.nutrition.food_photo_service.decrypted_key",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("API credentials must not be decrypted for Agent Service")
        ),
    )
    monkeypatch.setattr(
        "app.nutrition.food_photo_service.build_task_provider",
        lambda *_args, **_kwargs: _configured_provider(
            InvalidOutputVisionProvider(),
            name="agent_service:antigravity",
            model_id="gemini-test",
        ),
    )

    response = client.post(
        "/api/v1/nutrition/tracking/photo-estimates",
        headers={**ORIGIN, "X-Fitsho-Food-Photo-Consent": "true"},
        files={"file": ("meal.png", _image(), "image/png")},
    )

    assert response.status_code == 503, response.text
    assert response.json()["detail"]["code"] == "FOOD_PHOTO_PROVIDER_UNAVAILABLE"
    assert db.scalar(select(NutritionFoodPhotoEstimate)) is None
    event = db.scalar(
        select(NutritionOperationalEvent).where(
            NutritionOperationalEvent.event_name == "food_photo_estimation",
            NutritionOperationalEvent.status == "error",
        )
    )
    assert event is not None and event.provider == "agent_service:antigravity"
    assert not any(test_settings.food_photo_storage_root.rglob("*.jpg"))


def test_agent_photo_provider_failure_deletes_only_stored_photo(
    client: TestClient,
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
    test_settings: Settings,
    tmp_path: Path,
) -> None:
    test_settings.food_photo_rate_limit = 2
    test_settings.food_photo_storage_root = tmp_path / "food-photos"
    _register(client)
    db.add(
        AITaskConfig(
            task_type=AITaskType.FOOD_PHOTO_ESTIMATION,
            provider=AIProviderName.OPENROUTER,
            execution_backend=AIExecutionBackend.AGENT_SERVICE,
            agent_name=AIAgentName.ANTIGRAVITY,
            enabled=True,
            agent_model_id="gemini-test",
        )
    )
    db.flush()
    keep = test_settings.food_photo_storage_root / "keep.txt"
    keep.parent.mkdir(parents=True, exist_ok=True)
    keep.write_text("preserve", encoding="utf-8")
    monkeypatch.setattr(
        "app.nutrition.food_photo_service.decrypted_key",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("API credentials must not be decrypted for Agent Service")
        ),
    )
    monkeypatch.setattr(
        "app.nutrition.food_photo_service.build_task_provider",
        lambda *_args, **_kwargs: _configured_provider(
            FailingVisionProvider(), name="agent_service:antigravity", model_id="gemini-test"
        ),
    )

    response = client.post(
        "/api/v1/nutrition/tracking/photo-estimates",
        headers={**ORIGIN, "X-Fitsho-Food-Photo-Consent": "true"},
        files={"file": ("meal.png", _image(), "image/png")},
    )

    assert response.status_code == 503, response.text
    assert response.json()["detail"]["code"] == "FOOD_PHOTO_PROVIDER_UNAVAILABLE"
    assert db.scalar(select(NutritionFoodPhotoEstimate)) is None
    assert keep.read_text(encoding="utf-8") == "preserve"
    assert not any(test_settings.food_photo_storage_root.rglob("*.jpg"))
