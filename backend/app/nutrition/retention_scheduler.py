from __future__ import annotations

import asyncio
from datetime import UTC, datetime

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.config import Settings
from app.database.session import get_engine
from app.nutrition.models import NutritionOperationalEvent
from app.nutrition.retention import cleanup_private_nutrition_files

_LOCK_KEY = 58421092


def trigger_retention_cleanup(settings: Settings, *, now: datetime | None = None) -> bool:
    current = now or datetime.now(UTC)
    with get_engine(settings.database_url).connect() as connection:
        if not connection.scalar(text("SELECT pg_try_advisory_lock(:key)"), {"key": _LOCK_KEY}):
            return False
        try:
            with Session(bind=connection) as db:
                latest = db.scalar(
                    select(func.max(NutritionOperationalEvent.created_at)).where(
                        NutritionOperationalEvent.category == "retention",
                        NutritionOperationalEvent.event_name == "private_file_cleanup",
                        NutritionOperationalEvent.status == "completed",
                    )
                )
                if latest is not None and latest.date() >= current.date():
                    return False
                cleanup_private_nutrition_files(db, settings, now=current)
                return True
        finally:
            connection.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": _LOCK_KEY})


async def retention_scheduler_loop(settings: Settings) -> None:
    while True:
        try:
            trigger_retention_cleanup(settings)
        except Exception:
            # The next hourly attempt retries safely; previous private records remain intact.
            pass
        await asyncio.sleep(3600)
