import asyncio
import io
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, cast

import httpx
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.task_provider import ConfiguredAIProvider
from app.body_analysis.admin_config.enums import AIProviderName, AITaskType
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
from app.notifications.models import NotificationOutboxEvent
from app.nutrition.food_photo_worker import claim_food_photo_jobs, run_food_photo_analysis_once
from app.nutrition.models import NutritionFoodPhotoAnalysisJob, NutritionFoodPhotoEstimate

ORIGIN = {"Origin": "http://localhost:5173"}


def _image() -> bytes:
    output = io.BytesIO()
    Image.new("RGB", (100, 100), "white").save(output, "PNG")
    return output.getvalue()


def _register(client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/register",
        headers=ORIGIN,
        json={"email": "food-photo-queue@example.com", "password": "long password"},
    )
    assert response.status_code == 201


class _SuccessfulProvider:
    async def analyze_images(
        self, request: StructuredGenerationRequest, *, images: tuple[ImageInput, ...]
    ) -> StructuredGenerationResponse:
        return StructuredGenerationResponse(
            payload={
                "meal_name_guess": "صبحانه",
                "items": [
                    {
                        "name_guess": "نان",
                        "estimated_amount": 100,
                        "unit": "g",
                        "confidence": 0.8,
                        "visible_evidence": ["نان روی بشقاب"],
                        "uncertainties": [],
                        "calories": 250,
                        "protein_g": 8,
                        "carbohydrate_g": 50,
                        "fat_g": 2,
                    }
                ],
                "overall_confidence": 0.8,
                "needs_user_confirmation": True,
            },
            model_id="test/vision",
            attempted_models=("test/vision",),
        )


class _FailingProvider:
    async def analyze_images(
        self, request: StructuredGenerationRequest, *, images: tuple[ImageInput, ...]
    ) -> StructuredGenerationResponse:
        raise AIProviderError(ProviderErrorCode.PROVIDER_UNAVAILABLE, "provider unavailable")


def _configured_provider(provider: Any) -> ConfiguredAIProvider:
    return ConfiguredAIProvider(
        provider=cast(AIProvider, provider),
        provider_name="openrouter",
        primary_model_id="test/vision",
        fallback_model_ids=(),
        routing_preferences=ProviderRoutingPreferences(),
        supports_cost_accounting=True,
    )


def _configure_photo_task(db: Session) -> None:
    db.add(
        AITaskConfig(
            task_type=AITaskType.FOOD_PHOTO_ESTIMATION,
            provider=AIProviderName.OPENROUTER,
            enabled=True,
            primary_model_id="test/vision",
        )
    )
    db.flush()


def _enqueue_photo(
    client: TestClient,
    db: Session,
    test_settings: Settings,
    tmp_path: Path,
) -> str:
    test_settings.food_photo_storage_root = tmp_path / "food-photos"
    _register(client)
    _configure_photo_task(db)
    response = client.post(
        "/api/v1/nutrition/tracking/photo-estimates",
        headers={**ORIGIN, "X-Fitsho-Food-Photo-Consent": "true"},
        files={"file": ("meal.png", _image(), "image/png")},
    )
    assert response.status_code == 202, response.text
    return response.json()["id"]


def _run_worker_once(db: Session, settings: Settings) -> int:
    async def execute() -> int:
        async with httpx.AsyncClient() as client:
            return await run_food_photo_analysis_once(
                db,
                settings=settings,
                ai_client=client,
                agent_http_client=client,
                worker_id="test-food-worker",
                now=datetime.now(UTC),
            )

    return asyncio.run(execute())


def test_food_photo_upload_commits_a_queued_job_without_running_ai(
    client: TestClient,
    db: Session,
    test_settings: Settings,
    tmp_path: Path,
) -> None:
    test_settings.food_photo_storage_root = tmp_path / "food-photos"
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
    response = client.post(
        "/api/v1/nutrition/tracking/photo-estimates",
        headers={**ORIGIN, "X-Fitsho-Food-Photo-Consent": "true"},
        files={"file": ("meal.png", _image(), "image/png")},
    )

    assert response.status_code == 202, response.text
    body = response.json()
    assert body["status"] == "queued"
    assert body["items"] == []
    assert body["macro_totals_complete"] is False

    estimate = db.get(NutritionFoodPhotoEstimate, body["id"])
    assert estimate is not None
    assert estimate.raw_estimate == {}
    job = db.scalar(
        select(NutritionFoodPhotoAnalysisJob).where(
            NutritionFoodPhotoAnalysisJob.estimate_id == estimate.id
        )
    )
    assert job is not None
    assert job.status == "queued"
    assert job.attempt_count == 0
    assert job.execution_config["language"] == "fa"
    assert (test_settings.food_photo_storage_root / estimate.storage_key).is_file()


def test_food_photo_queue_has_owner_scoped_get_and_history_endpoints(
    client: TestClient,
    db: Session,
    test_settings: Settings,
    tmp_path: Path,
) -> None:
    test_settings.food_photo_storage_root = tmp_path / "food-photos"
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

    created = client.post(
        "/api/v1/nutrition/tracking/photo-estimates",
        headers={**ORIGIN, "X-Fitsho-Food-Photo-Consent": "true"},
        files={"file": ("meal.png", _image(), "image/png")},
    )
    assert created.status_code == 202
    estimate_id = created.json()["id"]

    current = client.get(
        f"/api/v1/nutrition/tracking/photo-estimates/{estimate_id}", headers=ORIGIN
    )
    assert current.status_code == 200
    assert current.json()["id"] == estimate_id
    assert current.json()["status"] == "queued"

    history = client.get("/api/v1/nutrition/tracking/photo-estimates", headers=ORIGIN)
    assert history.status_code == 200
    assert [item["id"] for item in history.json()] == [estimate_id]


def test_food_photo_worker_persists_result_and_completion_notification(
    client: TestClient,
    db: Session,
    test_settings: Settings,
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    estimate_id = _enqueue_photo(client, db, test_settings, tmp_path)
    monkeypatch.setattr(
        "app.nutrition.food_photo_service.decrypted_key", lambda *_args, **_kwargs: "secret"
    )
    monkeypatch.setattr(
        "app.nutrition.food_photo_service.build_task_provider",
        lambda *_args, **_kwargs: _configured_provider(_SuccessfulProvider()),
    )

    assert _run_worker_once(db, test_settings) == 1

    current = client.get(
        f"/api/v1/nutrition/tracking/photo-estimates/{estimate_id}", headers=ORIGIN
    )
    assert current.status_code == 200
    assert current.json()["status"] == "estimated"
    assert current.json()["items"][0]["name_guess"] == "نان"
    job = db.scalar(
        select(NutritionFoodPhotoAnalysisJob).where(
            NutritionFoodPhotoAnalysisJob.estimate_id == estimate_id
        )
    )
    assert job is not None and job.status == "completed"
    event = db.scalar(
        select(NotificationOutboxEvent).where(
            NotificationOutboxEvent.event_type == "food_photo_analysis_completed"
        )
    )
    assert event is not None
    assert event.payload["data"] == {
        "event_type": "food_photo_analysis_completed",
        "estimate_id": estimate_id,
    }


def test_food_photo_worker_retries_transient_failure_then_marks_failed(
    client: TestClient,
    db: Session,
    test_settings: Settings,
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    test_settings.food_photo_max_attempts = 2
    estimate_id = _enqueue_photo(client, db, test_settings, tmp_path)
    monkeypatch.setattr(
        "app.nutrition.food_photo_service.decrypted_key", lambda *_args, **_kwargs: "secret"
    )
    monkeypatch.setattr(
        "app.nutrition.food_photo_service.build_task_provider",
        lambda *_args, **_kwargs: _configured_provider(_FailingProvider()),
    )

    assert _run_worker_once(db, test_settings) == 1
    job = db.scalar(
        select(NutritionFoodPhotoAnalysisJob).where(
            NutritionFoodPhotoAnalysisJob.estimate_id == estimate_id
        )
    )
    assert job is not None and job.status == "queued" and job.attempt_count == 1
    assert db.get(NutritionFoodPhotoEstimate, estimate_id).status == "queued"

    job.available_at = datetime.now(UTC) - timedelta(seconds=1)
    db.commit()
    assert _run_worker_once(db, test_settings) == 1

    db.expire_all()
    job = db.scalar(
        select(NutritionFoodPhotoAnalysisJob).where(
            NutritionFoodPhotoAnalysisJob.estimate_id == estimate_id
        )
    )
    estimate = db.get(NutritionFoodPhotoEstimate, estimate_id)
    assert job is not None and job.status == "failed" and job.attempt_count == 2
    assert estimate is not None and estimate.status == "failed"
    assert estimate.error_code == ProviderErrorCode.PROVIDER_UNAVAILABLE.value
    event = db.scalar(
        select(NotificationOutboxEvent).where(
            NotificationOutboxEvent.event_type == "food_photo_analysis_failed"
        )
    )
    assert event is not None


def test_food_photo_worker_reclaims_an_expired_lease(
    client: TestClient,
    db: Session,
    test_settings: Settings,
    tmp_path: Path,
) -> None:
    estimate_id = _enqueue_photo(client, db, test_settings, tmp_path)
    job = db.scalar(
        select(NutritionFoodPhotoAnalysisJob).where(
            NutritionFoodPhotoAnalysisJob.estimate_id == estimate_id
        )
    )
    assert job is not None
    old = datetime.now(UTC) - timedelta(seconds=test_settings.food_photo_worker_lease_seconds + 1)
    job.status = "processing"
    job.locked_at = old
    job.locked_by = "dead-worker"
    job.attempt_count = 1
    db.commit()

    claimed = claim_food_photo_jobs(
        db,
        worker_id="live-worker",
        now=datetime.now(UTC),
        lease_seconds=test_settings.food_photo_worker_lease_seconds,
        batch_size=1,
    )

    assert claimed == [job.id]
    db.refresh(job)
    assert job.status == "processing"
    assert job.locked_by == "live-worker"
    assert job.attempt_count == 2


def test_deleting_a_photo_removes_its_pending_job(
    client: TestClient,
    db: Session,
    test_settings: Settings,
    tmp_path: Path,
) -> None:
    estimate_id = _enqueue_photo(client, db, test_settings, tmp_path)
    deleted = client.delete(
        f"/api/v1/nutrition/tracking/photo-estimates/{estimate_id}", headers=ORIGIN
    )

    assert deleted.status_code == 204
    assert db.scalar(
        select(NutritionFoodPhotoAnalysisJob).where(
            NutritionFoodPhotoAnalysisJob.estimate_id == estimate_id
        )
    ) is None
    estimate = db.get(NutritionFoodPhotoEstimate, estimate_id)
    assert estimate is not None and estimate.status == "deleted"
