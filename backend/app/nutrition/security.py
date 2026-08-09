from __future__ import annotations

import base64
import hashlib
import hmac
import json
from datetime import UTC, datetime, timedelta
from typing import cast
from uuid import UUID, uuid4

from sqlalchemy import Table
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.config import Settings
from app.nutrition.models import (
    NutritionOperationalEvent,
    NutritionOperationRateLimit,
    NutritionSecurityAuditEvent,
)


class PrivateAccessError(Exception):
    pass


class RateLimitExceeded(Exception):
    def __init__(self, retry_after_seconds: int) -> None:
        self.retry_after_seconds = retry_after_seconds


def audit_security_event(
    db: Session,
    *,
    actor_user_id: UUID | None,
    owner_user_id: UUID | None,
    event_type: str,
    resource_type: str,
    resource_id: UUID | None,
    outcome: str = "success",
    metadata: dict[str, object] | None = None,
) -> None:
    db.add(
        NutritionSecurityAuditEvent(
            actor_user_id=actor_user_id,
            owner_user_id=owner_user_id,
            event_type=event_type,
            resource_type=resource_type,
            resource_id=resource_id,
            outcome=outcome,
            metadata_snapshot=metadata or {},
        )
    )


def record_operational_event(
    db: Session,
    *,
    category: str,
    event_name: str,
    status: str,
    provider: str | None = None,
    counters: dict[str, object] | None = None,
    duration_ms: int | None = None,
) -> None:
    db.add(
        NutritionOperationalEvent(
            category=category,
            event_name=event_name,
            status=status,
            provider=provider,
            counters=counters or {},
            duration_ms=duration_ms,
        )
    )


def _encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def create_private_access_token(
    settings: Settings,
    *,
    actor_user_id: UUID,
    resource_id: UUID,
    purpose: str,
    now: datetime | None = None,
) -> str:
    issued = now or datetime.now(UTC)
    payload = {
        "actor": str(actor_user_id),
        "resource": str(resource_id),
        "purpose": purpose,
        "exp": int(
            (issued + timedelta(seconds=settings.private_file_access_ttl_seconds)).timestamp()
        ),
    }
    encoded = _encode(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode())
    secret = settings.private_file_signing_key.get_secret_value().encode()
    signature = _encode(hmac.new(secret, encoded.encode(), hashlib.sha256).digest())
    return f"{encoded}.{signature}"


def verify_private_access_token(
    settings: Settings,
    token: str,
    *,
    actor_user_id: UUID,
    resource_id: UUID,
    purpose: str,
    now: datetime | None = None,
) -> None:
    try:
        encoded, signature = token.split(".", 1)
        secret = settings.private_file_signing_key.get_secret_value().encode()
        expected = _encode(hmac.new(secret, encoded.encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(signature, expected):
            raise PrivateAccessError
        payload = json.loads(_decode(encoded))
        current = now or datetime.now(UTC)
        valid = (
            payload.get("actor") == str(actor_user_id)
            and payload.get("resource") == str(resource_id)
            and payload.get("purpose") == purpose
            and int(payload.get("exp", 0)) >= int(current.timestamp())
        )
    except (ValueError, TypeError, json.JSONDecodeError, UnicodeDecodeError):
        raise PrivateAccessError from None
    if not valid:
        raise PrivateAccessError


def consume_rate_limit(
    db: Session,
    *,
    actor_user_id: UUID,
    operation: str,
    limit: int,
    window_seconds: int,
    now: datetime | None = None,
) -> None:
    current = now or datetime.now(UTC)
    epoch = int(current.timestamp())
    window_epoch = epoch - (epoch % window_seconds)
    window_start = datetime.fromtimestamp(window_epoch, UTC)
    table = cast(Table, NutritionOperationRateLimit.__table__)
    base_statement = insert(table).values(
        id=uuid4(),
        actor_user_id=actor_user_id,
        operation=operation,
        window_started_at=window_start,
        request_count=1,
    )
    statement = base_statement.on_conflict_do_update(
        constraint="uq_nutrition_rate_window",
        set_={
            "request_count": table.c.request_count + 1,
            "updated_at": current,
        },
    ).returning(table.c.request_count)
    count = int(db.execute(statement).scalar_one())
    db.commit()
    if count > limit:
        raise RateLimitExceeded(window_epoch + window_seconds - epoch)
