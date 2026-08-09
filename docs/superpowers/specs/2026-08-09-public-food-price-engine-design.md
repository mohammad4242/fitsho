# Fitsho Public Food Price Engine Design

## Scope

This step repairs the food-price capability only. It does not change nutrition composition,
scientific targets, plan generation, physician review, or later audit gaps.

Fitsho will collect public market observations for canonical catalogue foods, normalize package
prices, reject unsafe observations and statistical outliers, calculate an arithmetic mean from the
remaining observations, and persist both the current accepted reference and immutable history.

The first refresh runs manually after implementation. Later refreshes run every Saturday at 12:00
in `Asia/Tehran`.

## Initial source registry

The initial no-key provider registry contains ten independent public sources:

1. Digikala
2. Torob
3. Basalam
4. Okala
5. Snapp Market
6. Hyperstar
7. Shahrvand
8. Refah
9. Emalls
10. Tehran Municipality public market price list

Only publicly accessible pages or official public files may be used. Private or undocumented
application endpoints, authenticated customer sessions, CAPTCHA bypasses, and aggressive crawling
are prohibited. A provider that cannot expose a reliable public observation fails independently and
does not weaken validation for other providers.

## Provider boundary

Every source implements `FoodPriceProvider`. Providers return immutable raw observations and never
write nutrition plans or composition records.

The registry keeps future credential-based adapters separate. Configuration includes empty,
backend-only credential slots for PersianAPI, Basalam API, and a generic future provider. All
credential-based adapters are disabled by default and empty credentials never fail application
startup or the public-source job.

Each public provider defines:

- stable provider code and display name;
- public search or official-file location;
- conservative request rate and timeout;
- parser version;
- provider-specific product locator;
- region/store metadata when available;
- health and failure state.

## Catalogue matching

The job searches only active verified Fitsho foods and their approved aliases. It never crawls a
complete marketplace catalogue.

Discovery produces candidate mappings. A mapping becomes active only when deterministic normalized
tokens, food category, package type, and exclusion rules identify a comparable ordinary food.
Prepared meals, restaurant items, supplements, bundles, mixed products, irrelevant brands/forms,
and ambiguous matches are rejected or sent to review.

Once a reliable public product locator exists, later runs fetch that mapped product directly where
possible. Broken locators return `BROKEN_MAPPING` and preserve the last trusted reference.

## Normalization and aggregation

Every observation preserves provider, canonical food, public product identifier/URL, title, normal
price, promotional price, currency, package quantity/unit, normalized price, region/store, observed
time, fetch time, and parser version.

Canonical persisted comparison units are:

- `IRR_PER_GRAM`
- `IRR_PER_MILLILITRE`
- `IRR_PER_UNIT`

The normal price is the reference input. Promotional prices remain explicit and never silently
replace the normal market price.

For each food:

1. validate mapping, package quantity, unit, currency, value, and observation time;
2. keep at most one deterministic representative observation per provider/product;
3. reject statistical outliers using a versioned median/MAD policy with an IQR fallback;
4. require observations from at least three distinct reliable providers;
5. calculate the arithmetic mean of accepted normalized normal prices using `Decimal`;
6. round only at the documented persistence/display boundary;
7. compare the candidate with the previous accepted reference;
8. accept it only when jump, disagreement, coverage, and confidence policies pass.

Suspicious candidates become `needs_review`; the last trusted reference remains current. Reference
history and quote snapshots are append-only.

## Scheduling and idempotency

The scheduler calculates the most recent due Saturday 12:00 Tehran slot and uses a PostgreSQL
advisory lock plus a unique slot key. This prevents duplicate work across workers and catches a
missed slot after an application restart.

The first manual run uses its own idempotency key and does not consume the next scheduled slot. The
next planned slot after the initial implementation run is Saturday, 2026-08-15 at 12:00 Tehran.

The job records start/end time, attempted foods, successful updates, unchanged foods, review items,
provider failures, observations, and overall status. A zero-provider or zero-mapping run is not
reported as a successful update.

## Failure and review behavior

Provider failures, timeouts, rate limits, parser failures, and invalid products are isolated. Bounded
retry/backoff applies only to transient failures. No failure deletes valid history or fabricates a
current price.

Review codes include:

- `INSUFFICIENT_SOURCES`
- `PRICE_JUMP`
- `SOURCE_DISAGREEMENT`
- `UNIT_PARSE_ERROR`
- `AMBIGUOUS_MATCH`
- `OUTLIER`
- `BROKEN_MAPPING`
- `UNREALISTIC_VALUE`
- `PROVIDER_FAILURE`

Planner requests continue to read only Fitsho's accepted reference table. They never perform public
network requests.

## Admin and observability

Admin APIs and UI focus on provider health, broken mappings, insufficient coverage, suspicious
updates, run history, and audited manual fallback. Routine entry of every price is not the primary
workflow.

Manual overrides remain audited, time-bounded fallbacks and are never labeled as multi-source live
prices.

## Tests

Tests use saved fixtures and mocked HTTP responses; they never depend on live sites. Coverage
includes source isolation, conservative matching, package parsing, unit normalization, promotions,
outlier rejection, arithmetic mean, minimum three-source acceptance, suspicious jumps, immutable
history, zero-provider failure, rate limits/retries, scheduler catch-up/idempotency, secret masking,
and planner compatibility.

After automated checks pass, one explicit live smoke run records the actual accessibility and
coverage of every public source. Only observations that pass the same production validation may
become accepted references.
