# Agent Service Food Price Search Design

**Status:** Approved for implementation

## Goal

Add production Food Price Search through the existing Agent Service generic
`POST /v1/generate` contract while keeping Fitsho Backend deterministic and
authoritative for validation, normalization, confidence, reference pricing,
review decisions, and persistence.

## Architecture

Backend owns one canonical food-price research request builder and prompt. The
Agent Service receives a generic structured-generation request and returns only
bounded raw retail evidence. Backend validates URLs, derives independent source
domains, reuses canonical product matching and price normalization, applies an
exact 20%-of-median cluster rule, and then passes trusted observations through
the existing `decide_reference_price(...)` policy.

The existing direct marketplace providers remain the disabled/legacy execution
path. A single Backend execution selector chooses either direct providers or an
`AgentFoodPriceResearcher`; an enabled Agent task never silently falls back to
direct providers during a failed run.

## Canonical research contract

The Backend module `backend/app/nutrition/ai_price_research.py` contains the
only production prompt and request builder. It emits a normal
`StructuredGenerationRequest` with schema name
`fitsho_food_price_research_v1` and a bounded response model:

- `FoodPriceResearchQuote` has source identity, inspected HTTPS URL, exact
  product title, positive normal/promotional prices, explicit `TOMAN`/`IRR`
  currency, positive package quantity/unit, and optional region.
- `FoodPriceResearchOutput` has the canonical food slug and at most five
  quotes. Extra fields are forbidden.
- The request contains current Backend date, Iran market, canonical food
  identity, requested source count, and excluded canonical domains. It never
  contains user PII or asks for an average, reference price, confidence score,
  decision, database ID, or provider code.

The prompt requires live web inspection, public HTTPS evidence, exact food
matching, one quote per domain, explicit normal versus promotional pricing,
and no invented or averaged values. Agent Service remains generic and gains no
food-price endpoint or Fitsho-specific semantics.

## Bounded two-pass research

Each Agent-mode food update makes at most two research phases:

1. Request exactly three sources with no exclusions.
2. If fewer than three usable distinct domains exist, or the usable first-pass
   normal prices do not all fit the inclusive 20% median band, request only the
   remaining number needed to attempt five total domains. The second request
   excludes all already collected domains.

Responses are parsed and validated in Backend. URLs are HTTPS-only, reject
credentials, localhost, malformed hosts, and private/local IPs. Hostnames are
lowercased, trailing dots removed, `www.` normalized, and common Iranian
multi-label suffixes such as `.co.ir`, `.org.ir`, `.net.ir`, `.gov.ir`, and
`.ac.ir` are handled conservatively. Duplicate domains never count twice and
the run never collects more than five domains.

For normalized normal prices, Backend calculates the Decimal median. A quote is
trusted when `abs(price - median) / median <= 0.20`. If the final trusted set
has at least three distinct domains, only those values enter the existing
`decide_reference_price(...)` flow. Existing outlier, jump, source-spread,
previous-reference, history, override, and review policies remain unchanged.

## Evidence and persistence

Agent domains receive stable provider codes of the form
`agent_web_<sha256(domain)[:16]>` and corresponding enabled
`PUBLIC_CATALOG` provider rows. A quote product ID is derived from the
canonical inspected URL. Agent evidence creates no persistent mapping rows.

Each quote preserves bounded provenance in `raw_quote`, including title,
region, explicit currency, source name, canonical URL/domain, backend marker,
and Agent request ID. Numeric fields use the existing IRR database convention.
Normal price drives reference calculation; promotional price is audit/display
evidence only.

Review rows gain a non-null JSON `source_quote_ids` list. Every Agent evidence
quote is flushed before IDs are serialized. Accepted histories retain all
evidence, with `accepted_quote_ids` containing only trusted values surviving
existing decision outlier filtering and `rejected_quote_ids` containing median
band rejects plus existing decision outliers. Reviews retain all initial and
additional evidence, including rejected quotes. If no trusted three-domain
cluster exists, the prior accepted reference is preserved and an appropriate
review is created.

## Execution integration

`backend/app/nutrition/price_execution.py` resolves `AITaskConfig` once for
manual, scheduled, and CLI runs. Missing/disabled `FOOD_PRICE_SEARCH` returns
the existing configured providers. Enabled Agent Service builds its provider
through `build_task_provider(...)` and wraps it in the researcher. Enabled API
or OpenRouter configuration is rejected clearly; no fake API web-search path
is added. Agent failures are isolated per food and never trigger direct
provider fallback.

The scheduler reuses the application-lifetime Agent HTTP client. Manual
refresh and CLI create/use one lifetime client as appropriate. Agent mode
attempts all verified catalogue foods and does not query direct providers in
the same run.

## Configuration and UI

`FOOD_PRICE_SEARCH` becomes a configurable Agent Service task with a disabled,
Agent Service default when absent. Agent profile verification continues to be
task-specific and is based on the canonical structured smoke request. The
smoke checks real structured generation, live-web evidence shape, HTTPS URLs,
and distinct domains without writing nutrition price data. A runner that
cannot research the web fails verification and cannot be enabled.

The AI settings page shows Food Price Search under Agent Service, disables or
blocks API/OpenRouter for this task, and keeps existing task behavior unchanged.
Nutrition monitoring returns only stored quote evidence referenced by each
review and the frontend renders the bounded sources, prices, package data,
product titles, safe external links, and the existing manual-override warning.

## Verification

Focused Backend tests cover the request contract, prompt reuse, URL/domain
validation, matching, two-pass bounds, median clustering, Agent/direct
selection, persistence, review quote relationships, settings, smoke, and
monitoring. Frontend tests cover Agent-only settings and source evidence UI.
Automated tests mock Agent responses and never contact shopping websites.
Alembic is created from the actual current head and validated with
`alembic heads` and `alembic upgrade head`; focused suites, relevant broader
tests, lint, frontend build, and `docker compose config` are run before the
final report. A real Agent smoke is reported separately only if a local
authenticated service/profile is available.
