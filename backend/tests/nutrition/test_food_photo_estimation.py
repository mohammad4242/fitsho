import io
from datetime import date

from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.body_analysis.admin_config.enums import AIProviderName, AITaskType
from app.body_analysis.admin_config.models import AITaskConfig
from app.body_analysis.providers.models import StructuredGenerationResponse
from app.nutrition.models import NutritionConsumptionEntry, NutritionFoodPhotoEstimate
from tests.nutrition.test_weekly_plan_api import ORIGIN, _seed_foods_and_prices


class FakeVisionProvider:
    async def analyze_images(self, request, *, images):  # type: ignore[no-untyped-def]
        assert images[0].mime_type == "image/jpeg"
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
            model_id="test/vision",
            attempted_models=("test/vision",),
            input_tokens=100,
            output_tokens=40,
            cost="0.001",
        )


def _image() -> bytes:
    output = io.BytesIO()
    Image.new("RGB", (100, 100), "white").save(output, "PNG")
    return output.getvalue()


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
    client: TestClient, db: Session, monkeypatch, test_settings
) -> None:  # type: ignore[no-untyped-def]
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
        "app.nutrition.food_photo_service.openrouter_provider",
        lambda *_args, **_kwargs: FakeVisionProvider(),
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
