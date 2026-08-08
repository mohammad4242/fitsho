# ruff: noqa: E501
from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import httpx
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import Settings
from app.database.session import get_engine
from app.nutrition.price_providers import configured_providers
from app.nutrition.price_update_service import run_price_update

_LOCK_KEY = 58421091


def is_due(now: datetime, settings: Settings) -> bool:
    local = now.astimezone(ZoneInfo(settings.food_price_update_timezone))
    return local.weekday() == 5 and (local.hour, local.minute) >= (
        settings.food_price_update_hour, settings.food_price_update_minute
    )


def weekly_slot(now: datetime, settings: Settings) -> datetime:
    local = now.astimezone(ZoneInfo(settings.food_price_update_timezone))
    return local.replace(
        hour=settings.food_price_update_hour,
        minute=settings.food_price_update_minute,
        second=0,
        microsecond=0,
    ).astimezone(UTC)


async def trigger_scheduled_update(settings: Settings, client: httpx.AsyncClient) -> bool:
    if not settings.food_price_update_enabled or not is_due(datetime.now(UTC), settings):
        return False
    with get_engine(settings.database_url).connect() as connection:
        if not connection.scalar(text("SELECT pg_try_advisory_lock(:key)"), {"key": _LOCK_KEY}):
            return False
        try:
            with Session(bind=connection) as db:
                run_price_update(
                    db,
                    providers=configured_providers(settings, client),
                    scheduled_for=weekly_slot(datetime.now(UTC), settings),
                )
        finally:
            connection.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": _LOCK_KEY})
    return True


async def scheduler_loop(settings: Settings, client: httpx.AsyncClient) -> None:
    while True:
        try:
            await trigger_scheduled_update(settings, client)
        except Exception:
            # Observability is persisted by the run/service; never crash the API process for the scheduler.
            pass
        await asyncio.sleep(60)
