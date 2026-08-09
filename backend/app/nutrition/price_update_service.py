# ruff: noqa: E501
"""Persistence and orchestration for the weekly food-price update."""

from __future__ import annotations

import asyncio
import time
from collections import Counter
from collections.abc import Iterable
from datetime import UTC, datetime
from decimal import Decimal
from hashlib import sha256
from typing import cast

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.nutrition.enums import (
    EstimateConfidence,
    FoodVerificationStatus,
    PriceQuoteStatus,
    PriceReferenceStatus,
    PriceUpdateRunStatus,
    PriceUpdateTriggerKind,
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
from app.nutrition.public_price_matching import CanonicalFoodIdentity, match_candidate
from app.nutrition.public_price_sources import PublicDiscoveryProvider, PublicProductCandidate
from app.nutrition.security import record_operational_event


def update_slot(now: datetime) -> datetime:
    return now.replace(minute=0, second=0, microsecond=0)


def _observation_key(observation: PriceObservation) -> str:
    payload = "|".join(
        (
            observation.provider_code,
            observation.provider_product_id,
            observation.observed_at.isoformat(),
            str(observation.normal_price),
            str(observation.promotional_price),
            str(observation.package_quantity),
            observation.package_unit,
        )
    )
    return sha256(payload.encode()).hexdigest()


def run_price_update(
    db: Session,
    *,
    providers: Iterable[FoodPriceProvider],
    scheduled_for: datetime | None = None,
    retry_attempts: int = 3,
    trigger_kind: PriceUpdateTriggerKind = PriceUpdateTriggerKind.MANUAL,
) -> NutritionFoodPriceUpdateRun:
    now = datetime.now(UTC)
    slot = scheduled_for or update_slot(now)
    existing = db.scalar(
        select(NutritionFoodPriceUpdateRun).where(NutritionFoodPriceUpdateRun.scheduled_for == slot)
    )
    if existing is not None:
        return existing
    provider_list = sorted(providers, key=lambda provider: provider.code)
    run = NutritionFoodPriceUpdateRun(
        scheduled_for=slot,
        started_at=now,
        status=PriceUpdateRunStatus.RUNNING,
        trigger_kind=trigger_kind,
        policy_version="public-price-v2",
    )
    db.add(run)
    db.flush()
    foods = db.scalars(
        select(NutritionCatalogueFood)
        .options(selectinload(NutritionCatalogueFood.aliases))
        .where(NutritionCatalogueFood.verification_status == FoodVerificationStatus.VERIFIED)
        .order_by(NutritionCatalogueFood.slug)
    ).all()
    mappings = list(
        db.scalars(
            select(NutritionFoodPriceMapping)
            .join(NutritionCatalogueFood)
            .where(
                NutritionFoodPriceMapping.active.is_(True),
                NutritionCatalogueFood.verification_status == FoodVerificationStatus.VERIFIED,
            )
            .order_by(
                NutritionFoodPriceMapping.provider_code,
                NutritionFoodPriceMapping.food_id,
                NutritionFoodPriceMapping.provider_product_id,
            )
        ).all()
    )
    enabled = {provider.code: provider for provider in provider_list}
    observations: dict[tuple[str, str], list[PriceObservation]] = {}
    discovered_keys: set[tuple[str, str]] = set()
    failures: set[str] = set()
    successful_probes: set[str] = set()

    mapped_food_providers = {(mapping.food_id, mapping.provider_code) for mapping in mappings}
    mapped_provider_products = {
        (mapping.provider_code, mapping.provider_product_id) for mapping in mappings
    }
    for provider in provider_list:
        if not isinstance(provider, PublicDiscoveryProvider):
            continue
        discovery_provider = cast(PublicDiscoveryProvider, provider)
        provider_failed = False
        for food in foods:
            if (food.id, provider.code) in mapped_food_providers:
                continue
            identity = CanonicalFoodIdentity(
                slug=food.slug,
                name_fa=food.name_fa,
                category=food.category,
                aliases=tuple(alias.alias for alias in food.aliases),
            )
            aliases = tuple(
                dict.fromkeys(
                    (
                        food.name_fa,
                        *(alias.alias for alias in food.aliases if alias.language == "fa"),
                    )
                )
            )[:2]
            selected: tuple[PublicProductCandidate, Decimal, str] | None = None
            for alias in aliases:
                try:

                    async def discover(
                        selected_provider: PublicDiscoveryProvider = discovery_provider,
                        selected_alias: str = alias,
                    ) -> list[PublicProductCandidate]:
                        return await selected_provider.discover(selected_alias)

                    candidates = asyncio.run(
                        retry_quotes(
                            discover,
                            attempts=retry_attempts,
                            base_delay_seconds=0.1,
                        )
                    )
                    successful_probes.add(provider.code)
                except Exception:
                    failures.add(provider.code)
                    provider_failed = True
                    break
                matches: list[tuple[PublicProductCandidate, Decimal, str]] = []
                for candidate in candidates[:10]:
                    match = match_candidate(identity, candidate)
                    if (
                        match.accepted
                        and (
                            provider.code,
                            candidate.product_id,
                        )
                        not in mapped_provider_products
                    ):
                        matches.append((candidate, match.confidence, match.matched_alias or alias))
                if matches:
                    selected = max(
                        matches,
                        key=lambda item: (
                            item[1],
                            -len(item[0].title),
                            item[0].product_id,
                        ),
                    )
                    break
            if provider_failed:
                break
            if selected is None:
                continue
            candidate, match_confidence, matched_alias = selected
            mapping = NutritionFoodPriceMapping(
                food_id=food.id,
                provider_code=provider.code,
                provider_product_id=candidate.product_id,
                public_product_url=candidate.public_url,
                region=candidate.region,
                match_alias=matched_alias,
                match_confidence=match_confidence,
                active=True,
                discovered_at=now,
                last_verified_at=now,
            )
            db.add(mapping)
            mappings.append(mapping)
            mapped_food_providers.add((food.id, provider.code))
            mapped_provider_products.add((provider.code, candidate.product_id))
            key = (provider.code, candidate.product_id)
            observations.setdefault(key, []).append(candidate.to_observation())
            discovered_keys.add(key)
        record = db.get(NutritionPriceProvider, provider.code)
        if record is not None and provider.code in successful_probes:
            record.enabled = True
            record.last_success_at = now
            record.last_error = None

    by_provider: dict[str, list[NutritionFoodPriceMapping]] = {}
    for mapping in mappings:
        by_provider.setdefault(mapping.provider_code, []).append(mapping)
    for code, provider_mappings in sorted(by_provider.items()):
        provider_adapter = enabled.get(code)
        if provider_adapter is None or code in failures:
            continue
        provider_instance = provider_adapter
        provider_started = time.perf_counter()
        try:
            pending_mappings = [
                mapping
                for mapping in provider_mappings
                if (mapping.provider_code, mapping.provider_product_id) not in discovered_keys
            ]
            product_ids = [
                (
                    mapping.public_product_url
                    if isinstance(provider_instance, PublicDiscoveryProvider)
                    and mapping.public_product_url
                    else mapping.provider_product_id
                )
                for mapping in pending_mappings
            ]
            if not product_ids:
                continue

            async def collect(
                selected_provider: FoodPriceProvider = provider_instance,
                selected_product_ids: list[str] = product_ids,
            ) -> list[PriceObservation]:
                return await selected_provider.get_quotes(selected_product_ids)

            collected_quotes = asyncio.run(
                retry_quotes(
                    collect,
                    attempts=retry_attempts,
                    base_delay_seconds=0.1,
                )
            )
            for item in collected_quotes:
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
                counters={"quotes": len(collected_quotes), "products": len(product_ids)},
                duration_ms=int((time.perf_counter() - provider_started) * 1000),
            )
        except Exception:  # Provider isolation: an outage never aborts other providers.
            failures.add(code)
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

    discovery_enabled = any(
        isinstance(provider, PublicDiscoveryProvider) for provider in provider_list
    )
    attempted_food_ids = (
        {food.id for food in foods}
        if provider_list and discovery_enabled
        else {mapping.food_id for mapping in mappings}
    )
    run.foods_attempted = len(attempted_food_ids)
    run.provider_failures = len(failures)
    usable_observation_count = 0
    for food_id in sorted(attempted_food_ids, key=str):
        food_mappings = [mapping for mapping in mappings if mapping.food_id == food_id]
        saved: list[NutritionFoodPriceQuote] = []
        priced_quotes: list[tuple[NutritionFoodPriceQuote, Decimal]] = []
        unit: str | None = None
        invalid = False
        mappings_by_provider: dict[str, list[NutritionFoodPriceMapping]] = {}
        for mapping in food_mappings:
            mappings_by_provider.setdefault(mapping.provider_code, []).append(mapping)
        for provider_code, provider_mappings in sorted(mappings_by_provider.items()):
            mapping = max(
                provider_mappings,
                key=lambda item: (item.match_confidence, item.provider_product_id),
            )
            provider_observations = observations.get(
                (mapping.provider_code, mapping.provider_product_id), []
            )
            for observed in sorted(
                provider_observations, key=lambda item: item.observed_at, reverse=True
            )[:1]:
                try:
                    normalized = normalize_observation(observed)
                except PriceValidationError:
                    invalid = True
                    continue
                if unit is not None and unit != normalized.canonical_unit:
                    invalid = True
                    continue
                unit = normalized.canonical_unit
                provider_record = db.get(NutritionPriceProvider, provider_code)
                quote = NutritionFoodPriceQuote(
                    food_id=food_id,
                    provider_code=observed.provider_code,
                    provider_product_id=observed.provider_product_id,
                    package_quantity=observed.package_quantity,
                    package_unit=observed.package_unit,
                    normal_price_irr=(
                        observed.normal_price * 10
                        if observed.currency == "TOMAN" and observed.normal_price
                        else observed.normal_price
                    ),
                    promotional_price_irr=(
                        observed.promotional_price * 10
                        if observed.currency == "TOMAN" and observed.promotional_price
                        else observed.promotional_price
                    ),
                    normalized_normal_irr=(
                        normalized.normalized_normal_price * 10
                        if normalized.normalized_normal_price
                        else None
                    ),
                    normalized_promotional_irr=(
                        normalized.normalized_promotional_price * 10
                        if normalized.normalized_promotional_price
                        else None
                    ),
                    observed_at=observed.observed_at,
                    effective_date=observed.observed_at.date(),
                    status=PriceQuoteStatus.FRESH,
                    fetched_at=now,
                    parser_version=provider_record.parser_version if provider_record else None,
                    provider_observation_key=_observation_key(observed),
                    raw_quote={
                        "title": observed.product_title,
                        "region": observed.region,
                        "currency": observed.currency,
                    },
                )
                db.add(quote)
                saved.append(quote)
                # Normal price is the market reference. Promotions remain traceable but do not silently bias it.
                if normalized.normalized_normal_price is not None:
                    priced_quotes.append((quote, normalized.normalized_normal_price))
                    usable_observation_count += 1
        previous = db.get(NutritionFoodPriceReference, food_id)
        values = [value for _, value in priced_quotes]
        decision = (
            decide_reference_price(
                values,
                previous_reference=previous.reference_price_toman if previous else None,
                distinct_source_count=len({quote.provider_code for quote, _ in priced_quotes}),
            )
            if values
            else None
        )
        reasons = (
            list(decision.review_reasons) if decision else [PriceReviewReason.INSUFFICIENT_SAMPLES]
        )
        if invalid:
            reasons.append(PriceReviewReason.UNIT_PARSE_ERROR)
        if decision is not None and decision.accepted and unit is not None:
            estimate_confidence = (
                EstimateConfidence.HIGH if decision.sample_count >= 3 else EstimateConfidence.MEDIUM
            )
            reference = NutritionFoodPriceReference(
                food_id=food_id,
                canonical_unit=unit,
                reference_price_toman=decision.reference_price,
                sample_count=decision.sample_count,
                confidence=estimate_confidence,
                status=PriceReferenceStatus.ACCEPTED,
                calculated_at=now,
                accepted_at=now,
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
            outlier_counts = Counter(decision.outliers)
            rejected_quote_ids: list[str] = []
            accepted_quote_ids: list[str] = []
            for quote, value in priced_quotes:
                if outlier_counts[value] > 0:
                    rejected_quote_ids.append(str(quote.id))
                    outlier_counts[value] -= 1
                else:
                    accepted_quote_ids.append(str(quote.id))
            db.add(
                NutritionFoodPriceHistory(
                    food_id=food_id,
                    canonical_unit=unit,
                    reference_price_toman=decision.reference_price,
                    sample_count=decision.sample_count,
                    confidence=estimate_confidence,
                    accepted_at=now,
                    source_quote_ids=[str(quote.id) for quote in saved],
                    accepted_quote_ids=accepted_quote_ids,
                    rejected_quote_ids=rejected_quote_ids,
                )
            )
            run.foods_updated += 1
        else:
            db.add(
                NutritionFoodPriceReview(
                    run_id=run.id,
                    food_id=food_id,
                    reason_codes=[reason.value for reason in dict.fromkeys(reasons)],
                    candidate_reference_price_toman=(
                        decision.reference_price if decision else None
                    ),
                )
            )
            run.foods_needing_review += 1
            if previous is not None:
                run.foods_unchanged += 1
    failure_codes: list[str] = []
    if not provider_list:
        failure_codes.append("NO_PROVIDERS")
    if not foods:
        failure_codes.append("NO_VERIFIED_FOODS")
    if failures:
        failure_codes.append("PROVIDER_FAILURE")
    if usable_observation_count == 0:
        failure_codes.append("NO_USABLE_OBSERVATIONS")
    if run.foods_needing_review:
        failure_codes.append("INSUFFICIENT_PRICE_COVERAGE")
    run.failure_codes = list(dict.fromkeys(failure_codes))
    run.status = (
        PriceUpdateRunStatus.COMPLETED_WITH_ERRORS
        if run.failure_codes
        else PriceUpdateRunStatus.COMPLETED
    )
    run.finished_at = datetime.now(UTC)
    run.details = {
        "provider_failures": sorted(failures),
        "providers_succeeded": sorted(successful_probes),
        "usable_observations": usable_observation_count,
    }
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


def current_reference_prices(
    db: Session, food_ids: list[object]
) -> dict[object, NutritionFoodPriceReference]:
    return {
        reference.food_id: reference
        for reference in db.scalars(
            select(NutritionFoodPriceReference).where(
                NutritionFoodPriceReference.food_id.in_(food_ids),
                NutritionFoodPriceReference.status == PriceReferenceStatus.ACCEPTED,
            )
        )
    }
