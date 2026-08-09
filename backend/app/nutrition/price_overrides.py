"""Audited manual price overrides and effective-price resolution."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.nutrition.enums import PriceReferenceStatus
from app.nutrition.models import (
    NutritionFoodPriceOverride,
    NutritionFoodPriceReference,
    NutritionFoodPriceUpdateRun,
)

DEFAULT_PRICE_MAX_AGE_HOURS = 168


@dataclass(frozen=True)
class EffectivePrice:
    food_id: UUID
    reference_id: str
    reference_price_toman: Decimal
    canonical_unit: str
    accepted_at: datetime
    source: str
    sample_count: int
    confidence: str


def effective_prices(
    db: Session,
    food_ids: list[UUID],
    *,
    now: datetime | None = None,
    maximum_age_hours: int = DEFAULT_PRICE_MAX_AGE_HOURS,
) -> dict[UUID, EffectivePrice]:
    if not food_ids:
        return {}
    current_time = now or datetime.now(UTC)
    fresh_after = current_time - timedelta(hours=maximum_age_hours)
    references = db.scalars(
        select(NutritionFoodPriceReference).where(
            NutritionFoodPriceReference.food_id.in_(food_ids),
            NutritionFoodPriceReference.status == PriceReferenceStatus.ACCEPTED,
            NutritionFoodPriceReference.accepted_at >= fresh_after,
        )
    ).all()
    resolved = {
        reference.food_id: EffectivePrice(
            food_id=reference.food_id,
            reference_id=str(reference.food_id),
            reference_price_toman=reference.reference_price_toman,
            canonical_unit=reference.canonical_unit,
            accepted_at=reference.accepted_at,
            source="automatic",
            sample_count=reference.sample_count,
            confidence=reference.confidence.value,
        )
        for reference in references
    }
    overrides = db.scalars(
        select(NutritionFoodPriceOverride).where(
            NutritionFoodPriceOverride.food_id.in_(food_ids),
            NutritionFoodPriceOverride.active.is_(True),
        )
    ).all()
    for override in overrides:
        resolved[override.food_id] = EffectivePrice(
            food_id=override.food_id,
            reference_id=str(override.id),
            reference_price_toman=override.reference_price_toman,
            canonical_unit=override.canonical_unit,
            accepted_at=override.created_at,
            source="manual_override",
            sample_count=1,
            confidence="medium",
        )
    return resolved


def expire_active_overrides(
    db: Session,
    *,
    run: NutritionFoodPriceUpdateRun,
    expired_at: datetime,
) -> int:
    overrides = db.scalars(
        select(NutritionFoodPriceOverride).where(
            NutritionFoodPriceOverride.active.is_(True)
        )
    ).all()
    for override in overrides:
        override.active = False
        override.expired_at = expired_at
        override.expired_by_run_id = run.id
    return len(overrides)
