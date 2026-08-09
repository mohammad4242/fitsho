# Public Food Price Engine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a no-key ten-source weekly food-price collector that accepts a reference only from at least three reliable sources after outlier removal, persists immutable history, and runs immediately once and every Saturday at 12:00 Tehran.

**Architecture:** Public source adapters discover and fetch only Fitsho canonical-food candidates and return immutable observations. A domain aggregation layer validates mappings and packages, removes outliers, computes a Decimal arithmetic mean, and writes snapshots/reference/history through the existing service. A restart-safe scheduler uses a PostgreSQL advisory lock and persisted weekly slots; the nutrition planner reads only accepted Fitsho references.

**Tech Stack:** Python 3.12, FastAPI, HTTPX, SQLAlchemy 2, PostgreSQL, Alembic, pytest, React 19, TypeScript, Vitest.

## Global Constraints

- Do not use undocumented/private marketplace endpoints or authenticated customer sessions.
- Do not bypass CAPTCHA, robots restrictions, access controls, or provider rate limits.
- Query only active verified Fitsho foods and approved aliases; never crawl whole catalogues.
- Keep nutrition composition completely separate from price observations.
- Keep credential providers disabled by default; empty API keys must not fail startup.
- Require at least three distinct reliable sources for an accepted reference.
- Remove statistical outliers before calculating the Decimal arithmetic mean.
- Preserve normal and promotional prices separately; promotion is never the normal reference input.
- Preserve the previous trusted price when a candidate is suspicious or retrieval fails.
- Run Saturdays at 12:00 `Asia/Tehran`, with restart catch-up and multi-worker idempotency.
- Never fabricate a current/live price.

---

### Task 1: Versioned aggregation and review policy

**Files:**
- Modify: `backend/app/nutrition/pricing.py`
- Modify: `backend/app/nutrition/planner_policy.py`
- Test: `backend/tests/nutrition/test_food_pricing.py`

**Interfaces:**
- Consumes: `PriceObservation`, `NormalizedPriceQuote`, current reference price.
- Produces: `PublicPricePolicy`, `calculate_reference_mean(values, policy)`, and `ReferencePriceDecision` with accepted values, rejected outliers, source count, and review codes.

- [ ] **Step 1: Write failing tests for three-source acceptance and arithmetic mean**

```python
def test_reference_requires_three_sources_and_uses_mean_after_outlier_removal() -> None:
    decision = decide_reference_price(
        [Decimal("270000"), Decimal("275000"), Decimal("285000"), Decimal("920000")],
        distinct_source_count=4,
    )
    assert decision.accepted is True
    assert decision.reference_price == Decimal("276666.6666666666666666666667")
    assert decision.outliers == (Decimal("920000"),)
```

- [ ] **Step 2: Run the focused test and confirm RED**

Run: `cd backend && uv run pytest tests/nutrition/test_food_pricing.py -q`

Expected: FAIL because the current decision requires two samples and returns a median.

- [ ] **Step 3: Implement versioned MAD/IQR outlier removal and Decimal mean**

```python
@dataclass(frozen=True)
class PublicPricePolicy:
    version: str = "public-price-v2"
    minimum_distinct_sources: int = 3
    mad_multiplier: Decimal = Decimal("3.5")
    maximum_jump_fraction: Decimal = Decimal("0.50")
```

Use median/MAD, a deterministic IQR fallback when MAD is zero, `sum(values) / len(values)`, and explicit review codes. Do not mutate the previous trusted reference in domain code.

- [ ] **Step 4: Run focused tests and confirm GREEN**

Run: `cd backend && uv run pytest tests/nutrition/test_food_pricing.py -q`

- [ ] **Step 5: Commit**

```bash
git add backend/app/nutrition/pricing.py backend/app/nutrition/planner_policy.py backend/tests/nutrition/test_food_pricing.py
git commit -m "feat(nutrition): add robust multi-source price policy"
```

### Task 2: Durable public-source schema and provider registry

**Files:**
- Create: `backend/alembic/versions/20260809_52_add_public_price_sources.py`
- Modify: `backend/app/nutrition/models.py`
- Modify: `backend/app/nutrition/enums.py`
- Modify: `backend/app/config.py`
- Modify: `.env.example`
- Test: `backend/tests/nutrition/test_food_pricing.py`

**Interfaces:**
- Consumes: existing provider, mapping, quote, reference, history, review, and run tables.
- Produces: ten seeded public provider rows, parser/version metadata, discovery state, run trigger kind, explicit provider/run health, and disabled credential slots.

- [ ] **Step 1: Write failing migration/model/config tests**

Assert that the ten provider codes are seeded, `minimum_sources=3`, credential-enabled flags default to false, secret fields are `SecretStr`, and the scheduled slot remains unique.

- [ ] **Step 2: Run focused tests and confirm RED**

Run: `cd backend && uv run pytest tests/nutrition/test_food_pricing.py tests/test_config.py -q`

- [ ] **Step 3: Add backward-compatible migration and models**

Add only nullable/defaulted columns where old rows exist. Seed:

```text
digikala, torob, basalam_public, okala, snapp_market,
hyperstar, shahrvand, refah, emalls, tehran_market_official
```

Persist public URL/product locator, parser version, fetched time, provider observation key, run trigger (`manual|scheduled|catch_up`), policy version, accepted/rejected quote IDs, and safe failure codes. Do not delete old quotes/history.

- [ ] **Step 4: Add disabled future credential configuration**

```text
FOOD_PRICE_PERSIANAPI_ENABLED=false
FOOD_PRICE_PERSIANAPI_API_KEY=
FOOD_PRICE_BASALAM_API_ENABLED=false
FOOD_PRICE_BASALAM_API_KEY=
FOOD_PRICE_PROVIDER_API_ENABLED=false
FOOD_PRICE_PROVIDER_API_KEY=
FOOD_PRICE_PROVIDER_BASE_URL=
```

- [ ] **Step 5: Run migration and focused tests**

Run: `cd backend && uv run alembic upgrade head && uv run pytest tests/nutrition/test_food_pricing.py tests/test_config.py -q`

- [ ] **Step 6: Commit**

```bash
git add .env.example backend/alembic/versions/20260809_52_add_public_price_sources.py backend/app/config.py backend/app/nutrition/enums.py backend/app/nutrition/models.py backend/tests/nutrition/test_food_pricing.py backend/tests/test_config.py
git commit -m "feat(nutrition): persist public price source registry"
```

### Task 3: Public page parsing and conservative matching

**Files:**
- Create: `backend/app/nutrition/public_price_sources.py`
- Create: `backend/app/nutrition/public_price_matching.py`
- Create: `backend/tests/fixtures/nutrition/prices/`
- Modify: `backend/app/nutrition/price_providers.py`
- Test: `backend/tests/nutrition/test_public_price_sources.py`

**Interfaces:**
- Consumes: canonical food slug, category, approved aliases, provider public configuration, `httpx.AsyncClient`.
- Produces: `PublicProductCandidate`, `PublicSourceDefinition`, ten `FoodPriceProvider` adapters, and deterministic `match_candidate(food, candidate)`.

- [ ] **Step 1: Save minimal sanitized provider fixtures**

Fixtures contain only the minimum HTML/JSON-LD/official-table structures necessary to parse title, URL/identifier, normal/promotional price, package quantity/unit, observed/effective date, and region/store.

- [ ] **Step 2: Write failing parser and matching tests**

Cover Persian digits, rial/toman labels, kg/g/l/ml/item packages, crossed-out promotions, missing quantities, bundles, restaurant/prepared meals, supplements, ambiguous names, irrelevant matches, and provider failures.

- [ ] **Step 3: Run focused tests and confirm RED**

Run: `cd backend && uv run pytest tests/nutrition/test_public_price_sources.py -q`

- [ ] **Step 4: Implement a small public parser boundary**

Use HTTPX and Python standard-library parsing. Prefer JSON-LD or official structured files when present; provider-specific code only supplies public search/locator construction and extraction hints. Return no observation when package quantity or comparable identity is uncertain.

- [ ] **Step 5: Implement ten isolated source definitions**

Each definition has a conservative request interval, a descriptive user agent, a provider code, a public base URL, and no credential. HTTP 403/429/CAPTCHA becomes a safe provider failure, not a bypass attempt.

- [ ] **Step 6: Run focused tests and confirm GREEN**

Run: `cd backend && uv run pytest tests/nutrition/test_public_price_sources.py tests/nutrition/test_food_pricing.py -q`

- [ ] **Step 7: Commit**

```bash
git add backend/app/nutrition/public_price_sources.py backend/app/nutrition/public_price_matching.py backend/app/nutrition/price_providers.py backend/tests/fixtures/nutrition/prices backend/tests/nutrition/test_public_price_sources.py
git commit -m "feat(nutrition): add conservative public price adapters"
```

### Task 4: Discovery, ingestion, immutable snapshots, and safe zero-work behavior

**Files:**
- Modify: `backend/app/nutrition/price_update_service.py`
- Modify: `backend/app/nutrition/price_update.py`
- Modify: `backend/app/nutrition/security.py`
- Test: `backend/tests/nutrition/test_food_pricing.py`
- Test: `backend/tests/nutrition/test_public_price_sources.py`

**Interfaces:**
- Consumes: ten providers, active verified foods/aliases, persisted mappings, `PublicPricePolicy`.
- Produces: `run_price_update(..., trigger, run_key)`, immutable observations, accepted reference/history, review records, and honest run status.

- [ ] **Step 1: Write failing orchestration tests**

Cover first-run discovery, mapped refresh, one representative quote per provider, minimum three providers, partial provider failure, all-provider failure, zero mapping/provider failure, promotions, broken mappings, suspicious jumps, immutable snapshots, and credentials absent from logs/API.

- [ ] **Step 2: Run focused tests and confirm RED**

Run: `cd backend && uv run pytest tests/nutrition/test_food_pricing.py tests/nutrition/test_public_price_sources.py -q`

- [ ] **Step 3: Implement bounded discovery and collection**

For each verified food, use approved aliases in deterministic order, cap candidates and requests per provider, persist only confirmed mappings/observations, and isolate failures per provider and food.

- [ ] **Step 4: Implement reference acceptance and history**

Accept only a minimum-three-source, non-suspicious mean. Preserve previous trusted references on review/failure. A run with zero attempted foods, zero enabled providers, or zero usable observations must be `COMPLETED_WITH_ERRORS` with explicit codes, never plain `COMPLETED`.

- [ ] **Step 5: Run focused tests and confirm GREEN**

Run: `cd backend && uv run pytest tests/nutrition/test_food_pricing.py tests/nutrition/test_public_price_sources.py tests/nutrition/test_weekly_plan_api.py -q`

- [ ] **Step 6: Commit**

```bash
git add backend/app/nutrition/price_update.py backend/app/nutrition/price_update_service.py backend/app/nutrition/security.py backend/tests/nutrition/test_food_pricing.py backend/tests/nutrition/test_public_price_sources.py
git commit -m "feat(nutrition): ingest public prices with immutable history"
```

### Task 5: Restart-safe Saturday scheduler

**Files:**
- Modify: `backend/app/nutrition/price_scheduler.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/nutrition/test_food_pricing.py`

**Interfaces:**
- Consumes: `Settings`, shared price HTTP client, persisted run slots.
- Produces: `most_recent_due_slot(now, settings)`, `trigger_scheduled_update(...)`, advisory-lock execution, same-day and missed-slot catch-up.

- [ ] **Step 1: Write failing scheduler tests**

Test before Saturday noon, exact Saturday noon, restart later Saturday, restart Sunday after a missed slot, repeated worker attempts, and manual run not consuming the scheduled slot.

- [ ] **Step 2: Run focused tests and confirm RED**

Run: `cd backend && uv run pytest tests/nutrition/test_food_pricing.py -q`

- [ ] **Step 3: Implement durable due-slot calculation**

Calculate the latest Saturday 12:00 Tehran instant not later than `now`; run it when no persisted scheduled/catch-up run exists. Keep PostgreSQL advisory locking and the unique slot constraint.

- [ ] **Step 4: Run focused tests and confirm GREEN**

Run: `cd backend && uv run pytest tests/nutrition/test_food_pricing.py -q`

- [ ] **Step 5: Commit**

```bash
git add backend/app/main.py backend/app/nutrition/price_scheduler.py backend/tests/nutrition/test_food_pricing.py
git commit -m "fix(nutrition): make weekly price refresh restart safe"
```

### Task 6: Admin exception APIs and monitoring UI

**Files:**
- Modify: `backend/app/nutrition/router.py`
- Modify: `backend/app/nutrition/schemas.py`
- Modify: `backend/tests/nutrition/test_admin_monitoring_api.py`
- Modify: `frontend/src/features/nutrition/api.ts`
- Modify: `frontend/src/features/admin/AdminNutritionMonitoringPage.tsx`
- Create: `frontend/src/features/admin/AdminNutritionMonitoringPage.test.tsx`

**Interfaces:**
- Consumes: provider health, mappings, review rows, run metrics, audited override service.
- Produces: admin-only provider/review/run endpoints, manual trigger endpoint, time-bounded audited override endpoint, and exception-focused UI.

- [ ] **Step 1: Write failing backend authorization and response tests**

Test admin-only manual trigger, provider health without secrets, review reasons, broken mappings, zero-coverage warning, audited override, and secret masking.

- [ ] **Step 2: Run backend tests and confirm RED**

Run: `cd backend && uv run pytest tests/nutrition/test_admin_monitoring_api.py -q`

- [ ] **Step 3: Implement minimal admin APIs**

Expose monitoring, exceptions, mappings, and manual trigger. Manual override requires reason, expiry, canonical unit, exact IRR amount, and audit actor; it must be labeled `manual_override`, never multi-source live.

- [ ] **Step 4: Write failing frontend tests**

Test source health, latest run, zero-coverage warning, review reasons, manual trigger state, RTL/English labels, and no API-key value rendering.

- [ ] **Step 5: Run frontend test and confirm RED**

Run: `cd frontend && npm test -- --run src/features/admin/AdminNutritionMonitoringPage.test.tsx`

- [ ] **Step 6: Implement exception-focused UI and confirm GREEN**

Run: `cd frontend && npm test -- --run src/features/admin/AdminNutritionMonitoringPage.test.tsx`

- [ ] **Step 7: Commit**

```bash
git add backend/app/nutrition/router.py backend/app/nutrition/schemas.py backend/tests/nutrition/test_admin_monitoring_api.py frontend/src/features/admin/AdminNutritionMonitoringPage.test.tsx frontend/src/features/admin/AdminNutritionMonitoringPage.tsx frontend/src/features/nutrition/api.ts
git commit -m "feat(nutrition): add price exception monitoring workflow"
```

### Task 7: Documentation, full verification, and first live run

**Files:**
- Modify: `README.md`
- Modify: `docs/nutrition-pricing.md`
- Modify: `docs/nutrition-api.md`
- Modify: `docs/nutrition-migrations.md`

**Interfaces:**
- Consumes: completed provider, aggregation, scheduler, admin, and migration behavior.
- Produces: operator instructions and verified first-run evidence.

- [ ] **Step 1: Update documentation**

Document ten sources, public-only restrictions, minimum-three policy, outlier/mean semantics, API-key-disabled defaults, Saturday schedule, catch-up, manual command/API, health review, and honest unavailable behavior.

- [ ] **Step 2: Run backend verification**

```bash
cd backend
uv run pytest
uv run ruff check
uv run mypy app
uv run alembic heads
```

Expected: all repository tests pass, Ruff exits 0, mypy exits 0, and one Alembic head is reported.

- [ ] **Step 3: Run frontend verification**

```bash
cd frontend
npm test -- --run
npm run lint
npm run build
```

Expected: all tests pass, lint exits 0, and production build exits 0.

- [ ] **Step 4: Rebuild the runtime and apply migration**

Run: `docker compose up -d --build backend`

Verify: `docker compose exec -T backend alembic current` reports the new head and `/openapi.json` returns HTTP 200.

- [ ] **Step 5: Run one explicit live manual refresh**

Run: `docker compose exec -T backend python -m app.nutrition.price_update`

Inspect the latest run, each provider result, quote count, accepted references, review rows, source count, dates, and next scheduled slot. Never convert a failed/blocked source into a fabricated quote.

- [ ] **Step 6: Commit docs and push**

```bash
git add README.md docs/nutrition-api.md docs/nutrition-migrations.md docs/nutrition-pricing.md
git commit -m "docs(nutrition): document public price operations"
git push origin nutrition
```

## Completion Evidence

- The first live run is reported with actual provider successes/failures and accepted/review counts.
- The next due slot is reported in both Tehran and UTC.
- At least three distinct reliable sources are required; lack of coverage remains unavailable/review.
- No API credential is required or enabled.
- Existing unrelated worktree changes remain unstaged and unmodified.
