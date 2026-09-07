from __future__ import annotations

import asyncio
from datetime import UTC, datetime

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.account_deletion.service import execute_due_account_deletions
from app.config import Settings
from app.database.session import get_engine

_LOCK_KEY = 58421093


def trigger_account_deletions(settings: Settings, *, now: datetime | None = None) -> int:
    if not settings.account_deletion_enabled:
        return 0
    current = now or datetime.now(UTC)
    with get_engine(settings.database_url).connect() as connection:
        if not connection.scalar(text("SELECT pg_try_advisory_lock(:key)"), {"key": _LOCK_KEY}):
            return 0
        try:
            with Session(bind=connection) as db:
                return execute_due_account_deletions(db, settings, now=current)
        finally:
            connection.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": _LOCK_KEY})
            connection.commit()


async def account_deletion_scheduler_loop(settings: Settings) -> None:
    while True:
        try:
            trigger_account_deletions(settings)
        except Exception:
            # The next attempt retries safely; a failed deletion remains pending.
            pass
        await asyncio.sleep(settings.account_deletion_worker_interval_seconds)
