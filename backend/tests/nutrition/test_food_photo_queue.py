import io
from pathlib import Path

from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.body_analysis.admin_config.enums import AIProviderName, AITaskType
from app.body_analysis.admin_config.models import AITaskConfig
from app.config import Settings
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

    current = client.get(f"/api/v1/nutrition/tracking/photo-estimates/{estimate_id}", headers=ORIGIN)
    assert current.status_code == 200
    assert current.json()["id"] == estimate_id
    assert current.json()["status"] == "queued"

    history = client.get("/api/v1/nutrition/tracking/photo-estimates", headers=ORIGIN)
    assert history.status_code == 200
    assert [item["id"] for item in history.json()] == [estimate_id]
