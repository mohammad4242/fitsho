# ruff: noqa: E501
"""Persistence and orchestration for the weekly food-price update."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Iterable
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.nutrition.enums import (
    EstimateConfidence,
    FoodVerificationStatus,
    PriceQuoteStatus,
    PriceReferenceStatus,
    PriceUpdateRunStatus,
)
from app.nutrition.models import (
    NutritionCatalogueFood,
    NutritionFoodPriceHistory,
    NutritionFoodPriceMapping,
    NutritionFoodPriceQuote,
    NutritionFoodPriceReference,
    NutritionFoodPriceReview,
    NutritionFoodPriceUpdateRun,
    NutritionPriceProvider,
)
from app.nutrition.pricing import (
    FoodPriceProvider,
    PriceObservation,
    PriceReviewReason,
    PriceValidationError,
    decide_reference_price,
    normalize_observation,
    retry_quotes,
)
from app.nutrition.security import record_operational_event


def update_slot(now: datetime) -> datetime:
    return now.replace(minute=0, second=0, microsecond=0)


def run_price_update(
    db: Session,
    *,
    providers: Iterable[FoodPriceProvider],
    scheduled_for: datetime | None = None,
    retry_attempts: int = 3,
) -> NutritionFoodPriceUpdateRun:
    now = datetime.now(UTC)
    slot = scheduled_for or update_slot(now)
    existing = db.scalar(select(NutritionFoodPriceUpdateRun).where(NutritionFoodPriceUpdateRun.scheduled_for == slot))
    if existing is not None:
        return existing
    run = NutritionFoodPriceUpdateRun(scheduled_for=slot, started_at=now, status=PriceUpdateRunStatus.RUNNING)
    db.add(run)
    db.flush()
    mappings = db.scalars(
        select(NutritionFoodPriceMapping).join(NutritionCatalogueFood).where(
            NutritionFoodPriceMapping.active.is_(True),
            NutritionCatalogueFood.verification_status == FoodVerificationStatus.VERIFIED,
        ).order_by(
            NutritionFoodPriceMapping.provider_code,
            NutritionFoodPriceMapping.food_id,
            NutritionFoodPriceMapping.provider_product_id,
        )
    ).all()
    by_provider: dict[str, list[NutritionFoodPriceMapping]] = {}
    for mapping in mappings:
        by_provider.setdefault(mapping.provider_code, []).append(mapping)
    enabled = {provider.code: provider for provider in providers}
    observations: dict[tuple[str, str], list[PriceObservation]] = {}
    failures: list[str] = []
    for code, provider_mappings in by_provider.items():
        provider = enabled.get(code)
        if provider is None:
            continue
        provider_instance = enabled[code]
        provider_started = time.perf_counter()
        try:
            product_ids = [mapping.provider_product_id for mapping in provider_mappings]

            async def collect(
                selected_provider: FoodPriceProvider = provider_instance,
                selected_product_ids: list[str] = product_ids,
            ) -> list[PriceObservation]:
                return await selected_provider.get_quotes(selected_product_ids)

            result = asyncio.run(
                retry_quotes(
                    collect,
                    attempts=retry_attempts,
                    base_delay_seconds=0.1,
                )
            )
            for item in result:
                if isinstance(item, PriceObservation):
                    observations.setdefault((code, item.provider_product_id), []).append(item)
            record = db.get(NutritionPriceProvider, code)
            if record is not None:
                record.last_success_at = now
                record.last_error = None
            record_operational_event(
                db,
                category="price_provider",
                event_name="quote_collection",
                status="success",
                provider=code,
                counters={"quotes": len(result), "products": len(product_ids)},
                duration_ms=int((time.perf_counter() - provider_started) * 1000),
            )
        except Exception:  # Provider isolation: an outage never aborts other providers.
            failures.append(code)
            record = db.get(NutritionPriceProvider, code)
            if record is not None:
                record.last_error = "provider collection failed"
            record_operational_event(
                db,
                category="price_provider",
                event_name="quote_collection",
                status="error",
                provider=code,
                counters={"products": len(provider_mappings)},
                duration_ms=int((time.perf_counter() - provider_started) * 1000),
            )

    run.foods_attempted = len({mapping.food_id for mapping in mappings})
    run.provider_failures = len(failures)
    for food_id in {mapping.food_id for mapping in mappings}:
        food_mappings = [mapping for mapping in mappings if mapping.food_id == food_id]
        saved: list[NutritionFoodPriceQuote] = []
        values: list[Decimal] = []
        unit: str | None = None
        invalid = False
        for mapping in food_mappings:
            for observed in observations.get((mapping.provider_code, mapping.provider_product_id), []):
                try:
                    normalized = normalize_observation(observed)
                except PriceValidationError:
                    invalid = True
                    continue
                if unit is not None and unit != normalized.canonical_unit:
                    invalid = True
                    continue
                unit = normalized.canonical_unit
                quote = NutritionFoodPriceQuote(
                    food_id=food_id, provider_code=observed.provider_code,
                    provider_product_id=observed.provider_product_id, package_quantity=observed.package_quantity,
                    package_unit=observed.package_unit, normal_price_irr=(observed.normal_price * 10 if observed.currency == "TOMAN" and observed.normal_price else observed.normal_price),
                    promotional_price_irr=(observed.promotional_price * 10 if observed.currency == "TOMAN" and observed.promotional_price else observed.promotional_price),
                    normalized_normal_irr=(normalized.normalized_normal_price * 10 if normalized.normalized_normal_price else None),
                    normalized_promotional_irr=(normalized.normalized_promotional_price * 10 if normalized.normalized_promotional_price else None),
                    observed_at=observed.observed_at, effective_date=observed.observed_at.date(), status=PriceQuoteStatus.FRESH,
                    raw_quote={"title": observed.product_title, "region": observed.region, "currency": observed.currency},
                )
                db.add(quote)
                saved.append(quote)
                # Normal price is the market reference. Promotions remain traceable but do not silently bias it.
                if normalized.normalized_normal_price is not None:
                    values.append(normalized.normalized_normal_price)
        previous = db.get(NutritionFoodPriceReference, food_id)
        decision = decide_reference_price(values, previous_reference=previous.reference_price_toman if previous else None) if values else None
        reasons = list(decision.review_reasons) if decision else [PriceReviewReason.INSUFFICIENT_SAMPLES]
        if invalid:
            reasons.append(PriceReviewReason.UNIT_PARSE_ERROR)
        if decision is not None and decision.accepted and unit is not None:
            confidence = EstimateConfidence.HIGH if decision.sample_count >= 3 else EstimateConfidence.MEDIUM
            reference = NutritionFoodPriceReference(
                food_id=food_id, canonical_unit=unit, reference_price_toman=decision.reference_price,
                sample_count=decision.sample_count, confidence=confidence, status=PriceReferenceStatus.ACCEPTED,
                calculated_at=now, accepted_at=now,
            )
            if previous is None:
                db.add(reference)
            else:
                previous.canonical_unit = reference.canonical_unit
                previous.reference_price_toman = reference.reference_price_toman
                previous.sample_count = reference.sample_count
                previous.confidence = reference.confidence
                previous.status = reference.status
                previous.calculated_at = now
                previous.accepted_at = now
            db.flush()
            db.add(NutritionFoodPriceHistory(
                food_id=food_id, canonical_unit=unit, reference_price_toman=decision.reference_price,
                sample_count=decision.sample_count, confidence=confidence, accepted_at=now,
                source_quote_ids=[str(quote.id) for quote in saved],
            ))
            run.foods_updated += 1
        else:
            db.add(NutritionFoodPriceReview(
                run_id=run.id, food_id=food_id, reason_codes=[reason.value for reason in dict.fromkeys(reasons)],
                candidate_reference_price_toman=(decision.reference_price if decision else None),
            ))
            run.foods_needing_review += 1
            if previous is not None:
                run.foods_unchanged += 1
    run.status = PriceUpdateRunStatus.COMPLETED_WITH_ERRORS if failures else PriceUpdateRunStatus.COMPLETED
    run.finished_at = datetime.now(UTC)
    run.details = {"provider_failures": failures}
    record_operational_event(
        db,
        category="background_job",
        event_name="food_price_update",
        status=run.status.value,
        counters={
            "foods_attempted": run.foods_attempted,
            "foods_updated": run.foods_updated,
            "foods_needing_review": run.foods_needing_review,
            "provider_failures": run.provider_failures,
        },
    )
    db.commit()
    db.refresh(run)
    return run


def current_reference_prices(db: Session, food_ids: list[object]) -> dict[object, NutritionFoodPriceReference]:
    return {
        reference.food_id: reference
        for reference in db.scalars(
            select(NutritionFoodPriceReference).where(
                NutritionFoodPriceReference.food_id.in_(food_ids),
                NutritionFoodPriceReference.status == PriceReferenceStatus.ACCEPTED,
            )
        )
    }
