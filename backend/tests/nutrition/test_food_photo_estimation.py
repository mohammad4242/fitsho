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
from app.nutrition.food_photo_service import (
    EstimatedPhotoItem,
    _normalize_image,
    build_food_photo_request,
)
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


def _configured_provider(provider: Any, *, name: str, model_id: str) -> ConfiguredAIProvider:
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
    request_fa = build_food_photo_request(
        primary_model="vision-primary",
        fallback_models=("vision-fallback",),
        provider_preferences=ProviderRoutingPreferences(zdr=True),
        temperature=0.2,
        max_output_tokens=777,
        language="fa",
    )

    assert "name_guess" in request_fa.system_prompt
    assert "فارسی روان" in request_fa.system_prompt
    assert "calories" in request_fa.system_prompt
    assert "protein_g" in request_fa.system_prompt
    assert "carbohydrate_g" in request_fa.system_prompt
    assert "fat_g" in request_fa.system_prompt
    assert request_fa.input_payload == {
        "instruction": (
            "این تصویر غذا را بدون اطلاعات شخصی تحلیل کن و خروجی را با نام‌های فارسی روان "
            "و روزمره ارائه بده."
        )
    }
    assert request_fa.schema_name == "fitsho_food_photo_estimate_v1"
    assert request_fa.route.primary_model == "vision-primary"
    assert request_fa.route.fallback_models == ("vision-fallback",)
    assert request_fa.provider_preferences == ProviderRoutingPreferences(zdr=True)
    assert request_fa.temperature == 0.2
    assert request_fa.max_output_tokens == 777
    assert request_fa.web_access == "disabled"

    request_en = build_food_photo_request(
        primary_model="vision-primary",
        fallback_models=("vision-fallback",),
        provider_preferences=ProviderRoutingPreferences(zdr=True),
        temperature=0.2,
        max_output_tokens=777,
        language="en",
    )
    assert "everyday English" in request_en.system_prompt
    assert "calories" in request_en.system_prompt
    assert request_en.input_payload == {
        "instruction": (
            "Analyze this food image without personal data and provide nutritional estimates."
        )
    }


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
    normalized, normalized_mime = _normalize_image(_image(), test_settings.food_photo_max_pixels)
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


# ---------------------------------------------------------------------------
# New macro-totals tests
# ---------------------------------------------------------------------------


def _setup_estimate(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> dict[str, Any]:
    """Register a user, seed catalogue, configure a fake provider, and run estimation."""
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
        "app.nutrition.food_photo_service.decrypted_key", lambda *_a, **_k: "secret"
    )
    monkeypatch.setattr(
        "app.nutrition.food_photo_service.build_task_provider",
        lambda *_a, **_k: _configured_provider(
            FakeVisionProvider(), name="openrouter", model_id="test/vision"
        ),
    )
    response = client.post(
        "/api/v1/nutrition/tracking/photo-estimates",
        headers={**ORIGIN, "X-Fitsho-Food-Photo-Consent": "true"},
        files={"file": ("meal.png", _image(), "image/png")},
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_macro_totals_returned_after_estimation(
    client: TestClient,
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
    test_settings: Settings,
) -> None:
    """A: Macro totals are returned after estimation with correct scaled values."""
    test_settings.food_photo_rate_limit = 10
    body = _setup_estimate(client, db, monkeypatch)

    assert "macro_totals" in body
    assert "macro_totals_complete" in body
    totals = body["macro_totals"]
    # task6-chicken: 165 kcal, 31g protein, 0g carbs, 3.6g fat per 100g at 140g
    assert abs(totals["calories"] - 165 * 1.4) < 0.01
    assert abs(totals["protein_g"] - 31 * 1.4) < 0.01
    assert abs(totals["carbohydrate_g"] - 0 * 1.4) < 0.01
    assert abs(totals["fat_g"] - 3.6 * 1.4) < 0.01
    assert body["macro_totals_complete"] is True


def test_amount_correction_recalculates_macro_totals(
    client: TestClient,
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
    test_settings: Settings,
) -> None:
    """B: Amount correction recalculates totals."""
    test_settings.food_photo_rate_limit = 10
    body = _setup_estimate(client, db, monkeypatch)
    item_id = body["items"][0]["item_id"]
    estimate_id = body["id"]

    corrected = client.patch(
        f"/api/v1/nutrition/tracking/photo-estimates/{estimate_id}/items/{item_id}",
        headers=ORIGIN,
        json={"estimated_amount": 90},
    )
    assert corrected.status_code == 200, corrected.text
    totals = corrected.json()["macro_totals"]
    # 90g instead of 140g
    assert abs(totals["calories"] - 165 * 0.9) < 0.01
    assert abs(totals["protein_g"] - 31 * 0.9) < 0.01
    assert abs(totals["fat_g"] - 3.6 * 0.9) < 0.01
    assert corrected.json()["macro_totals_complete"] is True


def test_unresolved_item_produces_incomplete_summary(
    client: TestClient,
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
    test_settings: Settings,
) -> None:
    """C: Unresolved items produce an incomplete summary."""
    test_settings.food_photo_rate_limit = 10
    body = _setup_estimate(client, db, monkeypatch)
    estimate_id = body["id"]
    item_id = body["items"][0]["item_id"]

    # Add an unresolved item by removing the food_id via a patch that sets no food_id,
    # and also test that mapping_status=unresolved items cause incompleteness.
    # We simulate this by directly mutating the DB row.
    row = db.scalar(select(NutritionFoodPhotoEstimate))
    assert row is not None
    items = list(row.mapped_items)
    items.append(
        {
            "item_id": "unresolved-sauce",
            "name_guess": "White sauce",
            "estimated_amount": 50,
            "unit": "unknown",
            "confidence": 0.4,
            "visible_evidence": [],
            "uncertainties": [],
            "food_id": None,
            "food_slug": None,
            "mapping_status": "unresolved",
        }
    )
    row.mapped_items = items
    db.commit()

    # Fetch the estimate via correction (any endpoint that calls photo_response with db)
    corrected = client.patch(
        f"/api/v1/nutrition/tracking/photo-estimates/{estimate_id}/items/{item_id}",
        headers=ORIGIN,
        json={"estimated_amount": 140},
    )
    assert corrected.status_code == 200
    assert corrected.json()["macro_totals_complete"] is False
    # Known chicken should still contribute partial totals
    assert corrected.json()["macro_totals"]["calories"] > 0


def test_confirmation_rejects_unresolved_items(
    client: TestClient,
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
    test_settings: Settings,
) -> None:
    """D: Final confirmation rejects unresolved/non-gram items."""
    test_settings.food_photo_rate_limit = 10
    body = _setup_estimate(client, db, monkeypatch)
    estimate_id = body["id"]

    # Add an unresolved item
    row = db.scalar(select(NutritionFoodPhotoEstimate))
    assert row is not None
    items = list(row.mapped_items)
    items.append(
        {
            "item_id": "unresolved-sauce",
            "name_guess": "White sauce",
            "estimated_amount": 50,
            "unit": "unknown",
            "confidence": 0.4,
            "visible_evidence": [],
            "uncertainties": [],
            "food_id": None,
            "food_slug": None,
            "mapping_status": "unresolved",
        }
    )
    row.mapped_items = items
    db.commit()

    confirmed = client.post(
        f"/api/v1/nutrition/tracking/photo-estimates/{estimate_id}/confirm",
        headers=ORIGIN,
        json={"entry_date": date.today().isoformat()},
    )
    assert confirmed.status_code == 409
    assert confirmed.json()["detail"]["code"] == "UNRESOLVED_ITEMS_REQUIRE_EDIT"
    # Estimate must remain in "estimated" status
    db.expire_all()
    row = db.scalar(select(NutritionFoodPhotoEstimate))
    assert row is not None and row.status == "estimated"


def test_resolving_unresolved_item_makes_summary_complete(
    client: TestClient,
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
    test_settings: Settings,
) -> None:
    """E: Resolving an unresolved item makes the summary complete."""
    test_settings.food_photo_rate_limit = 10
    body = _setup_estimate(client, db, monkeypatch)
    estimate_id = body["id"]

    # Add an unresolved item
    row = db.scalar(select(NutritionFoodPhotoEstimate))
    assert row is not None
    items = list(row.mapped_items)
    items.append(
        {
            "item_id": "unresolved-sauce",
            "name_guess": "White sauce",
            "estimated_amount": 50,
            "unit": "unknown",
            "confidence": 0.4,
            "visible_evidence": [],
            "uncertainties": [],
            "food_id": None,
            "food_slug": None,
            "mapping_status": "unresolved",
        }
    )
    row.mapped_items = items
    db.commit()

    # Resolve by providing food_id and estimated_amount
    from app.nutrition.enums import FoodVerificationStatus as FVS
    from app.nutrition.models import NutritionCatalogueFood as NCF

    food = db.scalar(
        select(NCF).where(NCF.slug == "task6-chicken", NCF.verification_status == FVS.VERIFIED)
    )
    assert food is not None

    resolved = client.patch(
        f"/api/v1/nutrition/tracking/photo-estimates/{estimate_id}/items/unresolved-sauce",
        headers=ORIGIN,
        json={"food_id": str(food.id), "estimated_amount": 80},
    )
    assert resolved.status_code == 200, resolved.text
    assert resolved.json()["macro_totals_complete"] is True
    assert resolved.json()["macro_totals"]["calories"] > 0


def test_removing_unresolved_item_makes_summary_complete(
    client: TestClient,
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
    test_settings: Settings,
) -> None:
    """F: Removing the unresolved item makes summary complete."""
    test_settings.food_photo_rate_limit = 10
    body = _setup_estimate(client, db, monkeypatch)
    estimate_id = body["id"]

    # Add an unresolved item
    row = db.scalar(select(NutritionFoodPhotoEstimate))
    assert row is not None
    items = list(row.mapped_items)
    items.append(
        {
            "item_id": "unresolved-sauce",
            "name_guess": "White sauce",
            "estimated_amount": 50,
            "unit": "unknown",
            "confidence": 0.4,
            "visible_evidence": [],
            "uncertainties": [],
            "food_id": None,
            "food_slug": None,
            "mapping_status": "unresolved",
        }
    )
    row.mapped_items = items
    db.commit()

    removed = client.patch(
        f"/api/v1/nutrition/tracking/photo-estimates/{estimate_id}/items/unresolved-sauce",
        headers=ORIGIN,
        json={"remove": True},
    )
    assert removed.status_code == 200, removed.text
    data = removed.json()
    assert data["macro_totals_complete"] is True
    assert len(data["items"]) == 1
    assert data["macro_totals"]["calories"] > 0


def test_free_meal_macro_preview_uses_same_calculation_and_confirms(
    client: TestClient,
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
    test_settings: Settings,
) -> None:
    """G: Free Meal confirmation produces same macros as estimate summary then confirms."""
    test_settings.food_photo_rate_limit = 10
    body = _setup_estimate(client, db, monkeypatch)
    estimate_id = body["id"]
    # The read-only macro_totals from estimation
    read_only_totals = body["macro_totals"]

    free_meal_response = client.post(
        f"/api/v1/nutrition/tracking/photo-estimates/{estimate_id}/free-meal-preview",
        headers=ORIGIN,
    )
    assert free_meal_response.status_code == 200, free_meal_response.text
    confirmed_totals = free_meal_response.json()

    # Same calculation
    assert abs(confirmed_totals["calories"] - read_only_totals["calories"]) < 0.01
    assert abs(confirmed_totals["protein_g"] - read_only_totals["protein_g"]) < 0.01
    assert abs(confirmed_totals["fat_g"] - read_only_totals["fat_g"]) < 0.01

    # State should now be confirmed
    db.expire_all()
    row = db.scalar(select(NutritionFoodPhotoEstimate))
    assert row is not None and row.status == "confirmed"


def test_macro_totals_do_not_confirm_estimate(
    client: TestClient,
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
    test_settings: Settings,
) -> None:
    """H: Receiving macro_totals in estimate response does NOT confirm the estimate."""
    test_settings.food_photo_rate_limit = 10
    body = _setup_estimate(client, db, monkeypatch)

    # macro_totals are present in the estimation response
    assert "macro_totals" in body
    assert body["macro_totals"]["calories"] > 0

    # Status must remain "estimated"
    db.expire_all()
    row = db.scalar(select(NutritionFoodPhotoEstimate))
    assert row is not None and row.status == "estimated"
    assert db.scalar(select(NutritionConsumptionEntry)) is None


def test_food_photo_ai_contract_direct_nutrition(
    client: TestClient,
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
    test_settings: Settings,
) -> None:
    """The canonical AI contract test — prompt instructs model to calculate macros in grams."""
    request_fa = build_food_photo_request(
        primary_model="vision-primary",
        fallback_models=("vision-fallback",),
        provider_preferences=ProviderRoutingPreferences(zdr=True),
        temperature=0.2,
        max_output_tokens=777,
        language="fa",
    )
    prompt_fa = request_fa.system_prompt.lower()
    assert "فارسی روان" in prompt_fa
    assert "calories" in prompt_fa
    assert "protein_g" in prompt_fa
    assert "carbohydrate_g" in prompt_fa
    assert "fat_g" in prompt_fa

    request_en = build_food_photo_request(
        primary_model="vision-primary",
        fallback_models=("vision-fallback",),
        provider_preferences=ProviderRoutingPreferences(zdr=True),
        temperature=0.2,
        max_output_tokens=777,
        language="en",
    )
    prompt_en = request_en.system_prompt.lower()
    assert "identify" in prompt_en
    assert "grams" in prompt_en
    assert "calories" in prompt_en
    assert "protein_g" in prompt_en
    assert "carbohydrate_g" in prompt_en
    assert "fat_g" in prompt_en
    assert "medical advice" in prompt_en


def test_estimated_photo_item_calculates_atwater_calories_when_zero() -> None:
    item = EstimatedPhotoItem.model_validate(
        {
            "name_guess": "جوجه کباب",
            "estimated_amount": 200,
            "unit": "g",
            "confidence": 0.9,
            "visible_evidence": ["Grilled chicken"],
            "uncertainties": [],
            "calories": 0.0,
            "protein_g": 36.3,
            "carbohydrate_g": 4.0,
            "fat_g": 22.9,
        }
    )
    expected = round(36.3 * 4.0 + 4.0 * 4.0 + 22.9 * 9.0, 1)
    assert item.calories == expected


def test_unmapped_food_with_direct_ai_macros_is_complete_and_confirms(
    client: TestClient,
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
    test_settings: Settings,
) -> None:
    """Option 1 test: unmapped food with direct AI macros is complete and confirms directly."""

    class JoojehVisionProvider:
        async def analyze_images(
            self, request: StructuredGenerationRequest, *, images: tuple[ImageInput, ...]
        ) -> StructuredGenerationResponse:
            return StructuredGenerationResponse(
                payload={
                    "meal_name_guess": "جوجه کباب با برنج",
                    "items": [
                        {
                            "name_guess": "جوجه کباب",
                            "estimated_amount": 250,
                            "unit": "g",
                            "confidence": 0.9,
                            "visible_evidence": ["Grilled chicken skewers"],
                            "uncertainties": [],
                            "calories": 350.0,
                            "protein_g": 52.0,
                            "carbohydrate_g": 2.0,
                            "fat_g": 14.0,
                        },
                        {
                            "name_guess": "برنج زعفرانی",
                            "estimated_amount": 200,
                            "unit": "g",
                            "confidence": 0.88,
                            "visible_evidence": ["Yellow saffron rice"],
                            "uncertainties": [],
                            "calories": 260.0,
                            "protein_g": 5.0,
                            "carbohydrate_g": 58.0,
                            "fat_g": 1.0,
                        },
                    ],
                    "overall_confidence": 0.89,
                    "needs_user_confirmation": True,
                },
                model_id="test-vision",
                attempted_models=("test-vision",),
                input_tokens=100,
                output_tokens=60,
                cost="0.001",
            )

    provider = JoojehVisionProvider()
    _register(client)
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
        "app.nutrition.food_photo_service.decrypted_key", lambda *_a, **_k: "secret"
    )
    monkeypatch.setattr(
        "app.nutrition.food_photo_service.build_task_provider",
        lambda *_a, **_k: _configured_provider(provider, name="openrouter", model_id="test/vision"),
    )

    resp = client.post(
        "/api/v1/nutrition/tracking/photo-estimates",
        files={"file": ("joojeh.jpg", _image(), "image/png")},
        headers={**ORIGIN, "X-Fitsho-Food-Photo-Consent": "true"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["macro_totals_complete"] is True
    assert body["macro_totals"]["calories"] == 610.0
    assert body["macro_totals"]["protein_g"] == 57.0
    assert body["macro_totals"]["carbohydrate_g"] == 60.0
    assert body["macro_totals"]["fat_g"] == 15.0

    # User confirms the estimate directly without manual mapping
    confirm_resp = client.post(
        f"/api/v1/nutrition/tracking/photo-estimates/{body['id']}/confirm",
        headers=ORIGIN,
        json={"entry_date": "2026-09-04"},
    )
    assert confirm_resp.status_code == 200

    # Two consumption entries created with direct nutrients
    entries = db.scalars(
        select(NutritionConsumptionEntry).where(
            NutritionConsumptionEntry.entry_date == date(2026, 9, 4)
        )
    ).all()
    assert len(entries) == 2
    names = {e.display_name for e in entries}
    assert "جوجه کباب" in names
    assert "برنج زعفرانی" in names
