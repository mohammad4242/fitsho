from __future__ import annotations

import asyncio
import logging
import socket
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import httpx
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.body_analysis.providers.models import (
    AIProviderError,
    ImageInput,
    ProviderErrorCode,
)
from app.config import Settings, get_settings
from app.database.session import get_engine
from app.notifications.content import build_notification_payload
from app.notifications.outbox import enqueue_notification_event

from . import food_photo_service
from .models import NutritionFoodPhotoAnalysisJob, NutritionFoodPhotoEstimate
from .security import audit_security_event, record_operational_event

logger = logging.getLogger(__name__)

_RETRYABLE_ERRORS = frozenset(
    {
        ProviderErrorCode.TIMEOUT,
        ProviderErrorCode.CONNECTION_FAILURE,
        ProviderErrorCode.RATE_LIMITED,
        ProviderErrorCode.PROVIDER_UNAVAILABLE,
    }
)

_SAFE_FAILURE_MESSAGES: dict[ProviderErrorCode, str] = {
    ProviderErrorCode.NOT_CONFIGURED: "سرویس تحلیل عکس غذا در دسترس نیست.",
    ProviderErrorCode.TIMEOUT: "تحلیل عکس غذا زمان زیادی برد؛ دوباره تلاش می‌کنیم.",
    ProviderErrorCode.CONNECTION_FAILURE: "سرویس تحلیل عکس غذا موقتاً در دسترس نیست.",
    ProviderErrorCode.RATE_LIMITED: "سرویس تحلیل عکس غذا شلوغ است؛ دوباره تلاش می‌کنیم.",
    ProviderErrorCode.PROVIDER_UNAVAILABLE: "سرویس تحلیل عکس غذا موقتاً در دسترس نیست.",
    ProviderErrorCode.INVALID_OUTPUT: "نتیجه تحلیل عکس غذا معتبر نبود.",
    ProviderErrorCode.INVALID_REQUEST: "درخواست تحلیل عکس غذا پذیرفته نشد.",
    ProviderErrorCode.UNAUTHORIZED: "تنظیمات سرویس تحلیل عکس غذا معتبر نیست.",
    ProviderErrorCode.MODEL_NOT_FOUND: "مدل تحلیل عکس غذا در دسترس نیست.",
    ProviderErrorCode.REFUSAL: "تحلیل این عکس غذا کامل نشد.",
    ProviderErrorCode.MALFORMED_RESPONSE: "نتیجه تحلیل عکس غذا معتبر نبود.",
    ProviderErrorCode.LOCATION_UNSUPPORTED: "سرویس تحلیل عکس غذا در این موقعیت در دسترس نیست.",
}


def claim_food_photo_jobs(
    db: Session,
    *,
    worker_id: str,
    now: datetime,
    lease_seconds: int,
    batch_size: int,
) -> list[UUID]:
    stale_before = now - timedelta(seconds=lease_seconds)
    jobs = db.scalars(
        select(NutritionFoodPhotoAnalysisJob)
        .where(
            or_(
                (
                    (NutritionFoodPhotoAnalysisJob.status == "queued")
                    & (NutritionFoodPhotoAnalysisJob.available_at <= now)
                ),
                (
                    (NutritionFoodPhotoAnalysisJob.status == "processing")
                    & (NutritionFoodPhotoAnalysisJob.locked_at <= stale_before)
                ),
            )
        )
        .order_by(NutritionFoodPhotoAnalysisJob.created_at)
        .limit(batch_size)
        .with_for_update(skip_locked=True)
    ).all()
    if not jobs:
        db.rollback()
        return []
    for job in jobs:
        job.status = "processing"
        job.locked_at = now
        job.locked_by = worker_id
        job.attempt_count += 1
    db.commit()
    return [job.id for job in jobs]


def _failure_details(error: Exception) -> tuple[ProviderErrorCode, str | None]:
    if isinstance(error, AIProviderError):
        return error.code, error.provider_request_id
    return ProviderErrorCode.PROVIDER_UNAVAILABLE, None


def _safe_message(code: ProviderErrorCode) -> str:
    return _SAFE_FAILURE_MESSAGES.get(
        code,
        _SAFE_FAILURE_MESSAGES[ProviderErrorCode.PROVIDER_UNAVAILABLE],
    )


def _retry_delay(settings: Settings, attempt_count: int) -> int:
    exponent = attempt_count - 1
    if exponent < 0:
        exponent = 0
    retry_max = int(settings.food_photo_retry_max_seconds)
    retry_base = int(settings.food_photo_retry_base_seconds)
    delay = retry_base * (2**exponent)
    return retry_max if delay > retry_max else delay


def _config_float(config: dict[str, object], key: str, default: float) -> float:
    value = config.get(key, default)
    return float(value) if isinstance(value, (int, float, str)) else default


def _config_int(config: dict[str, object], key: str, default: int) -> int:
    value = config.get(key, default)
    return int(value) if isinstance(value, (int, str)) else default


def _locked_job_and_estimate(
    db: Session,
    job_id: UUID,
    worker_id: str,
) -> tuple[NutritionFoodPhotoAnalysisJob | None, NutritionFoodPhotoEstimate | None]:
    job = db.scalar(
        select(NutritionFoodPhotoAnalysisJob)
        .where(
            NutritionFoodPhotoAnalysisJob.id == job_id,
            NutritionFoodPhotoAnalysisJob.status == "processing",
            NutritionFoodPhotoAnalysisJob.locked_by == worker_id,
        )
        .with_for_update()
    )
    if job is None:
        db.rollback()
        return None, None
    estimate = db.scalar(
        select(NutritionFoodPhotoEstimate)
        .where(NutritionFoodPhotoEstimate.id == job.estimate_id)
        .with_for_update()
    )
    return job, estimate


def _finish_deleted_job(
    db: Session,
    job: NutritionFoodPhotoAnalysisJob,
    *,
    now: datetime,
) -> bool:
    job.status = "completed"
    job.completed_at = now
    job.locked_at = None
    job.locked_by = None
    db.commit()
    return True


def _record_failure(
    db: Session,
    job_id: UUID,
    *,
    worker_id: str,
    settings: Settings,
    code: ProviderErrorCode,
    provider_request_id: str | None,
    now: datetime,
) -> bool:
    job, estimate = _locked_job_and_estimate(db, job_id, worker_id)
    if job is None:
        return False
    if estimate is None or estimate.status in {"deleted", "expired"}:
        return _finish_deleted_job(db, job, now=now)

    message = _safe_message(code)
    job.last_error_code = code.value
    job.last_error_message = message
    if provider_request_id is not None:
        estimate.provider_request_id = provider_request_id
    retry = code in _RETRYABLE_ERRORS and job.attempt_count < job.max_attempts
    if retry:
        estimate.status = "queued"
        estimate.error_code = code.value
        estimate.error_message = message
        job.status = "queued"
        job.available_at = now + timedelta(seconds=_retry_delay(settings, job.attempt_count))
        job.locked_at = None
        job.locked_by = None
        record_operational_event(
            db,
            category="ai",
            event_name="food_photo_estimation",
            status="retry",
            provider=estimate.provider,
            counters={"requests": 1, "errors": 1, "retry": 1},
        )
        db.commit()
        return True

    estimate.status = "failed"
    estimate.error_code = code.value
    estimate.error_message = message
    job.status = "failed"
    job.completed_at = now
    job.locked_at = None
    job.locked_by = None
    audit_security_event(
        db,
        actor_user_id=None,
        owner_user_id=estimate.user_id,
        event_type="food_photo_analysis_failed",
        resource_type="food_photo_estimate",
        resource_id=estimate.id,
        metadata={"error_code": code.value},
    )
    record_operational_event(
        db,
        category="ai",
        event_name="food_photo_estimation",
        status="error",
        provider=estimate.provider,
        counters={"requests": 1, "errors": 1, "retry": 0},
    )
    enqueue_notification_event(
        db,
        user_id=estimate.user_id,
        event_type="food_photo_analysis_failed",
        category="nutrition_updates",
        deduplication_key=f"food-photo:{estimate.id}:failed",
        payload=build_notification_payload(
            "food_photo_analysis_failed",
            data={"estimate_id": estimate.id},
        ),
    )
    db.commit()
    return True


async def process_food_photo_job(
    db: Session,
    job_id: UUID,
    *,
    worker_id: str,
    settings: Settings,
    ai_client: httpx.AsyncClient | None,
    agent_http_client: httpx.AsyncClient | None,
    now: datetime | None = None,
) -> bool:
    current = now or datetime.now(UTC)
    job, estimate = _locked_job_and_estimate(db, job_id, worker_id)
    if job is None:
        return False
    if estimate is None or estimate.status in {"deleted", "expired"}:
        return _finish_deleted_job(db, job, now=current)

    execution_config = dict(job.execution_config)
    estimate.status = "analyzing"
    estimate.error_code = None
    estimate.error_message = None
    job.started_at = job.started_at or current
    db.commit()

    try:
        configured = food_photo_service.build_food_photo_provider(
            db,
            settings,
            execution_config,
            ai_client=ai_client,
            agent_http_client=agent_http_client,
        )
        request = food_photo_service.build_food_photo_request(
            primary_model=configured.primary_model_id,
            fallback_models=configured.fallback_model_ids,
            provider_preferences=configured.routing_preferences,
            temperature=_config_float(execution_config, "temperature", 0.0),
            max_output_tokens=_config_int(execution_config, "max_output_tokens", 4096),
            language=str(execution_config.get("language", "fa")),
        )
    except ValueError:
        return _record_failure(
            db,
            job_id,
            worker_id=worker_id,
            settings=settings,
            code=ProviderErrorCode.NOT_CONFIGURED,
            provider_request_id=None,
            now=current,
        )

    try:
        result = await configured.provider.analyze_images(
            request,
            images=(
                ImageInput(
                    label="food_photo",
                    mime_type="image/jpeg",
                    storage_scope="food",
                    storage_key=estimate.storage_key,
                ),
            ),
        )
        output = food_photo_service.FoodPhotoOutput.model_validate(result.payload)
    except AIProviderError as error:
        code, provider_request_id = _failure_details(error)
        return _record_failure(
            db,
            job_id,
            worker_id=worker_id,
            settings=settings,
            code=code,
            provider_request_id=provider_request_id,
            now=current,
        )
    except ValueError:
        return _record_failure(
            db,
            job_id,
            worker_id=worker_id,
            settings=settings,
            code=ProviderErrorCode.INVALID_OUTPUT,
            provider_request_id=None,
            now=current,
        )
    except Exception:
        logger.exception("Food photo worker provider call failed")
        return _record_failure(
            db,
            job_id,
            worker_id=worker_id,
            settings=settings,
            code=ProviderErrorCode.PROVIDER_UNAVAILABLE,
            provider_request_id=None,
            now=current,
        )

    job, estimate = _locked_job_and_estimate(db, job_id, worker_id)
    if job is None:
        return False
    if estimate is None or estimate.status in {"deleted", "expired"}:
        return _finish_deleted_job(db, job, now=current)

    estimate.status = "estimated"
    estimate.provider = configured.provider_name
    estimate.model_id = result.model_id
    estimate.provider_request_id = result.provider_request_id
    estimate.raw_estimate = output.model_dump(mode="json")
    estimate.mapped_items = food_photo_service._map_items(db, output)
    estimate.input_tokens = result.input_tokens
    estimate.output_tokens = result.output_tokens
    estimate.estimated_cost = result.cost
    estimate.error_code = None
    estimate.error_message = None
    job.status = "completed"
    job.completed_at = current
    job.locked_at = None
    job.locked_by = None
    audit_security_event(
        db,
        actor_user_id=None,
        owner_user_id=estimate.user_id,
        event_type="food_photo_estimated",
        resource_type="food_photo_estimate",
        resource_id=estimate.id,
        metadata={"provider": configured.provider_name, "byte_size": estimate.byte_size},
    )
    record_operational_event(
        db,
        category="ai",
        event_name="food_photo_estimation",
        status="success",
        provider=configured.provider_name,
        counters={
            "requests": 1,
            "errors": 0,
            "input_tokens": result.input_tokens or 0,
            "output_tokens": result.output_tokens or 0,
        },
    )
    enqueue_notification_event(
        db,
        user_id=estimate.user_id,
        event_type="food_photo_analysis_completed",
        category="nutrition_updates",
        deduplication_key=f"food-photo:{estimate.id}:completed",
        payload=build_notification_payload(
            "food_photo_analysis_completed",
            data={"estimate_id": estimate.id},
        ),
    )
    db.commit()
    return True


async def run_food_photo_analysis_once(
    db: Session,
    *,
    settings: Settings,
    ai_client: httpx.AsyncClient | None,
    agent_http_client: httpx.AsyncClient | None,
    worker_id: str,
    now: datetime | None = None,
) -> int:
    current = now or datetime.now(UTC)
    job_ids = claim_food_photo_jobs(
        db,
        worker_id=worker_id,
        now=current,
        lease_seconds=settings.food_photo_worker_lease_seconds,
        batch_size=settings.food_photo_worker_batch_size,
    )
    processed = 0
    for job_id in job_ids:
        if await process_food_photo_job(
            db,
            job_id,
            worker_id=worker_id,
            settings=settings,
            ai_client=ai_client,
            agent_http_client=agent_http_client,
            now=current,
        ):
            processed += 1
    return processed


def _worker_id() -> str:
    return f"{socket.gethostname()}:{uuid4()}"


async def run_worker(settings: Settings) -> None:
    worker_id = _worker_id()
    engine = get_engine(settings.database_url)
    ai_timeout = httpx.Timeout(settings.openrouter_timeout_seconds)
    agent_timeout = httpx.Timeout(settings.agent_service_connect_timeout_seconds)
    async with (
        httpx.AsyncClient(
            timeout=ai_timeout,
            proxy=settings.openrouter_proxy_url or None,
            trust_env=False,
        ) as ai_client,
        httpx.AsyncClient(timeout=agent_timeout, trust_env=False) as agent_http_client,
    ):
        while True:
            try:
                with Session(engine) as db:
                    await run_food_photo_analysis_once(
                        db,
                        settings=settings,
                        ai_client=ai_client,
                        agent_http_client=agent_http_client,
                        worker_id=worker_id,
                    )
            except Exception:
                logger.exception("Food photo worker iteration failed")
            await asyncio.sleep(settings.food_photo_worker_poll_seconds)


if __name__ == "__main__":
    asyncio.run(run_worker(get_settings()))
