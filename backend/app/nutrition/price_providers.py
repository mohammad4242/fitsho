# ruff: noqa: E501
"""Provider adapters; they return observations and never write Nutrition tables."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import httpx

from app.config import Settings
from app.nutrition.marketplace_price_providers import (
    BasalamPublicProvider,
    DigikalaPublicProvider,
    TapsiShopProvider,
)
from app.nutrition.pricing import FoodPriceProvider, PriceObservation, ProviderRateLimitedError


class PublicJsonCatalogProvider:
    """Adapter for an approved public JSON catalogue endpoint.

    No marketplace private endpoint is assumed. The endpoint is opt-in through
    configuration and must return only the explicitly requested product ids.
    """

    code = "public_catalog"

    def __init__(self, client: httpx.AsyncClient, base_url: str) -> None:
        self._client = client
        self._base_url = base_url.rstrip("/")

    async def get_quotes(self, product_ids: list[str]) -> list[PriceObservation]:
        response = await self._client.post(
            f"{self._base_url}/prices", json={"product_ids": product_ids}
        )
        if response.status_code == 429:
            raise ProviderRateLimitedError("public provider returned 429")
        response.raise_for_status()
        payload = response.json()
        rows = payload.get("items", []) if isinstance(payload, dict) else []
        return [
            PriceObservation(
                provider_code=self.code,
                provider_product_id=str(row["product_id"]),
                product_title=str(row["title"]),
                currency=str(row.get("currency", "TOMAN")),
                normal_price=Decimal(str(row["normal_price"]))
                if row.get("normal_price") is not None
                else None,
                promotional_price=Decimal(str(row["promotional_price"]))
                if row.get("promotional_price") is not None
                else None,
                package_quantity=Decimal(str(row["package_quantity"])),
                package_unit=str(row["package_unit"]),
                observed_at=datetime.fromisoformat(
                    str(row.get("observed_at") or datetime.now(UTC).isoformat())
                ),
                region=str(row["region"]) if row.get("region") else None,
            )
            for row in rows
            if isinstance(row, dict)
        ]


def configured_providers(
    settings: Settings,
    client: httpx.AsyncClient,
) -> list[FoodPriceProvider]:
    providers: list[FoodPriceProvider] = [
        BasalamPublicProvider(client),
        DigikalaPublicProvider(client),
        TapsiShopProvider(client),
    ]
    if settings.food_price_public_source_url:
        providers.append(PublicJsonCatalogProvider(client, settings.food_price_public_source_url))
    return providers
