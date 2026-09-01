# ruff: noqa: E501
from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import httpx
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.config import Settings
from app.database.session import get_engine
from app.nutrition.enums import PriceUpdateTriggerKind
from app.nutrition.models import NutritionFoodPriceUpdateRun
from app.nutrition.price_execution import resolve_price_update_execution
from app.nutrition.price_providers import configured_providers
from app.nutrition.price_update_service import run_price_update_async

_LOCK_KEY = 58421091


def is_due(now: datetime, settings: Settings) -> bool:
    local = now.astimezone(ZoneInfo(settings.food_price_update_timezone))
    return local.weekday() == 5 and (local.hour, local.minute) >= (
        settings.food_price_update_hour,
        settings.food_price_update_minute,
    )


def weekly_slot(now: datetime, settings: Settings) -> datetime:
    local = now.astimezone(ZoneInfo(settings.food_price_update_timezone))
    return local.replace(
        hour=settings.food_price_update_hour,
        minute=settings.food_price_update_minute,
        second=0,
        microsecond=0,
    ).astimezone(UTC)


def most_recent_due_slot(now: datetime, settings: Settings) -> datetime:
    timezone = ZoneInfo(settings.food_price_update_timezone)
    local = now.astimezone(timezone)
    days_since_saturday = (local.weekday() - 5) % 7
    due_date = local.date() - timedelta(days=days_since_saturday)
    candidate = datetime.combine(
        due_date,
        datetime.min.time().replace(
            hour=settings.food_price_update_hour,
            minute=settings.food_price_update_minute,
        ),
        timezone,
    )
    if candidate > local:
        candidate -= timedelta(days=7)
    return candidate.astimezone(UTC)


async def trigger_scheduled_update(
    settings: Settings,
    client: httpx.AsyncClient,
    *,
    agent_http_client: httpx.AsyncClient | None = None,
    now: datetime | None = None,
) -> bool:
    if not settings.food_price_update_enabled:
        return False
    current = now or datetime.now(UTC)
    due_slot = most_recent_due_slot(current, settings)
    with get_engine(settings.database_url).connect() as connection:
        if not connection.scalar(text("SELECT pg_try_advisory_lock(:key)"), {"key": _LOCK_KEY}):
            return False
        try:
            with Session(bind=connection) as db:
                existing = db.scalar(
                    select(NutritionFoodPriceUpdateRun.id).where(
                        NutritionFoodPriceUpdateRun.scheduled_for == due_slot
                    )
                )
                if existing is not None:
                    return False
                local_now = current.astimezone(ZoneInfo(settings.food_price_update_timezone))
                local_slot = due_slot.astimezone(ZoneInfo(settings.food_price_update_timezone))
                trigger_kind = (
                    PriceUpdateTriggerKind.SCHEDULED
                    if local_now.date() == local_slot.date()
                    else PriceUpdateTriggerKind.CATCH_UP
                )
                execution = resolve_price_update_execution(
                    db,
                    settings=settings,
                    price_http_client=client,
                    agent_http_client=agent_http_client,
                    direct_provider_factory=lambda: configured_providers(settings, client),
                )
                await run_price_update_async(
                    db,
                    providers=execution.providers,
                    agent_researcher=execution.agent_researcher,
                    scheduled_for=due_slot,
                    retry_attempts=settings.food_price_provider_retries,
                    trigger_kind=trigger_kind,
                )
                connection.commit()
        finally:
            if connection.in_transaction():
                connection.rollback()
            connection.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": _LOCK_KEY})
            connection.commit()
    return True


async def scheduler_loop(
    settings: Settings,
    client: httpx.AsyncClient,
    agent_http_client: httpx.AsyncClient | None = None,
) -> None:
    while True:
        try:
            await trigger_scheduled_update(
                settings,
                client,
                agent_http_client=agent_http_client,
            )
        except Exception:
            # Observability is persisted by the run/service; never crash the API process for the scheduler.
            pass
        await asyncio.sleep(60)
