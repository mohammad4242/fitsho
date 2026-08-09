# Nutrition pricing and freshness

## Provider boundary

`FoodPriceProvider` adapters return observations only. They cannot write plans or nutrition
composition. The enabled first adapter is `PublicJsonCatalogProvider`, an opt-in contract for an
approved public JSON service configured by `FOOD_PRICE_PUBLIC_SOURCE_URL`. No provider is enabled by
default, no paid key is required, and no undocumented retailer endpoint is used.

Future providers can implement the same adapter and use optional backend-only
`FOOD_PRICE_API_BASE_URL` and `FOOD_PRICE_API_KEY`. Canonical-food mappings specify exact provider
product IDs, so refreshes request only Fitsho-relevant products and never crawl a marketplace.

## Normalization and reference prices

Original title, product ID, provider, region, package quantity/unit, normal price, promotional price,
effective date, observation time, and raw quote remain immutable. Decimal arithmetic normalizes to
TOMAN per kg, litre, or unit internally; persisted quote fields retain comparable IRR values.
Promotions stay explicit and do not replace the normal reference price.

Reference prices use the median after deterministic median-relative outlier rejection. A minimum of
two accepted samples is required. An outlier, invalid unit, insufficient sample count, or change over
50% creates a review record and preserves the previous trusted price. Provider failures and 429s
retry with bounded exponential backoff and cannot corrupt existing quotes.

## Freshness and planning

Quote/reference states are `FRESH`, `STALE`, `ESTIMATED`, and `UNAVAILABLE`. The weekly planner policy
requires accepted references no older than 168 hours. Historical plans keep their own price snapshot.
A missing food price removes only that candidate. If remaining role coverage cannot produce a valid
plan, generation returns `LIVE_PRICE_UNAVAILABLE` with `INSUFFICIENT_PRICE_COVERAGE`; it never
fabricates a live price or favors an incomplete candidate pool silently.

The idempotent refresh runs Saturdays at noon in `Asia/Tehran` under a PostgreSQL advisory lock.
Manual refresh:

```bash
cd backend
uv run python -m app.nutrition.price_update
```
