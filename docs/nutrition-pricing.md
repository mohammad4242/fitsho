# Nutrition pricing and freshness

## Provider boundary

`FoodPriceProvider` adapters return observations only. They cannot write plans or nutrition
composition. Three isolated keyless adapters are active: Basalam's public product API, Digikala's
public catalogue API, and Tapsi Shop's anonymous guest catalogue. Each source starts disabled in the database and becomes healthy only
after a successful public probe. Failures remain isolated; no paid key, authenticated customer
session, CAPTCHA bypass, or whole-market crawl is used.

Future providers can implement the same adapter and use the disabled backend-only PersianAPI,
Basalam API, or generic provider credential slots. Empty keys are supported and never appear in the
monitoring API. Canonical-food aliases discover at most bounded candidates; accepted mappings store
the exact public product ID and URL so later refreshes request only Fitsho-relevant products.

## Normalization and reference prices

Original title, product ID, provider, region, package quantity/unit, normal price, promotional price,
effective date, observation time, and raw quote remain immutable. Decimal arithmetic normalizes to
TOMAN per kg, litre, or unit internally; persisted quote fields retain comparable IRR values.
Promotions stay explicit and do not replace the normal reference price.

Reference policy `public-price-v3` requires at least three distinct sources. It removes statistical
outliers using MAD with a deterministic IQR fallback, then calculates the Decimal arithmetic mean of
the remaining normal prices. Promotional prices remain traceable but are excluded from the normal
reference. Invalid units, insufficient sources, source spread over 75%, or a change over 50% create
a review record and preserve the previous trusted price. Stored mapping titles are revalidated on
every run so a previously matched prepared or irrelevant product cannot remain silently active.
Provider failures and 429s use bounded backoff and cannot corrupt existing quotes.

## Freshness and planning

Quote/reference states are `FRESH`, `STALE`, `ESTIMATED`, and `UNAVAILABLE`. The weekly planner policy
requires accepted references no older than 168 hours. Historical plans keep their own price snapshot.
A missing food price removes only that candidate. If remaining role coverage cannot produce a valid
plan, generation returns `LIVE_PRICE_UNAVAILABLE` with `INSUFFICIENT_PRICE_COVERAGE`; it never
fabricates a live price or favors an incomplete candidate pool silently.

The idempotent refresh runs Saturdays at noon in `Asia/Tehran` under a PostgreSQL advisory lock. A
restart after the slot performs one catch-up for the latest missed Saturday; the persisted unique
slot prevents duplicate worker execution. Admin monitoring is exception-focused and shows provider
health, coverage warnings, review codes, broken mappings, and recent run metrics.
Manual refresh:

```bash
cd backend
uv run python -m app.nutrition.price_update
```

To claim the latest missed weekly slot once (for first deployment or recovery), run:

```bash
uv run python -m app.nutrition.price_update --catch-up
```

Optional credential providers remain off unless their matching `*_ENABLED` setting is explicitly
enabled. The public weekly workflow does not require any API key.

## Member food catalogue

Authenticated members whose product mode is `nutrition` or `both` can open `/food-catalogue`.
Training-only members are excluded in both the React route guard and
`GET /api/v1/nutrition/food-catalogue`. The view combines verified composition with the latest
accepted effective price without joining or mutating the underlying nutrition-source records.

The catalogue always shows energy, protein, carbohydrate, fat, and fibre per 100 g, with the full
verified nutrient list and provenance available in the detail dialog. When no fresh accepted price
exists, the API returns `not_found` and the UI renders `یافت نشد` / `Not found`; no estimated market
price is created.

Admins use the same page to add a verified catalogue food or create a temporary price override.
Each override stores the food, positive price, canonical unit, reason, acting admin, creation time,
active state, and eventual expiry metadata. Overrides are fallback-only: they take precedence while
active, remain in the audit history permanently, and expire after the next successful automatic
market refresh. Automatic quotes and accepted reference-price history remain immutable.
