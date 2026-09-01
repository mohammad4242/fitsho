# Agent Service Food Price Search Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Route production food-price updates through live Agent Service research when the verified `FOOD_PRICE_SEARCH` task is enabled, while preserving the deterministic Fitsho price engine and direct-provider fallback mode.

**Architecture:** Add one Backend research module that builds the canonical structured request, validates bounded evidence, performs the deterministic two-pass/domain/median policy, and returns evidence without persistence. Add one execution selector used by scheduler, manual refresh, and CLI; extend the existing price update orchestration to persist evidence and pass only trusted normalized observations to `decide_reference_price(...)`. Agent Service remains the generic `/v1/generate` transport.

**Tech Stack:** Python 3.12, FastAPI, Pydantic, SQLAlchemy, Alembic, httpx, pytest, React 19, TypeScript, Vitest, Vite.

**Spec:** `docs/superpowers/specs/2026-09-01-agent-food-price-search-design.md`

## Global Constraints

- The only production food-price prompt and request builder live in `backend/app/nutrition/ai_price_research.py`.
- Agent Service is called only through existing `AgentServiceProvider.generate_structured_text()` and generic `POST /v1/generate`.
- The LLM returns evidence only; Backend owns domain validation, matching, normalization, median clustering, reference calculation, review decisions, and persistence.
- Initial research requests exactly three sources; one bounded second phase can request only enough additional domains to reach five total.
- A trusted quote satisfies `abs(price - median) / median <= 0.20`; at least three trusted independent domains are required before the existing `decide_reference_price(...)` flow can accept a new reference.
- Normal prices drive reference calculation; promotional prices remain audit/display evidence.
- Agent web domains map to stable distinct provider codes and create no fake mapping rows.
- Failed Agent research is isolated per food and never silently falls back to direct providers during an enabled Agent run.
- Existing direct providers, price normalization, price history, overrides, jump protection, reviews, and weekly scheduling remain behaviorally compatible.
- Automated tests mock Agent responses and never contact shopping websites.
- Stage only task files; preserve unrelated dirty/untracked work.

---

### Task 1: Canonical research contract and deterministic research policy

**Files:**
- Create: `backend/app/nutrition/ai_price_research.py`
- Create: `backend/tests/nutrition/test_agent_food_price_research.py`
- Modify: `backend/app/nutrition/public_price_matching.py`
- Test: `backend/tests/nutrition/test_agent_food_price_research.py`

**Interfaces:**
- Consumes: existing `StructuredGenerationRequest`, `StructuredGenerationResponse`, `ModelRoute`, `ProviderRoutingPreferences`, `PriceObservation`, `normalize_observation(...)`, `CanonicalFoodIdentity`, `PublicProductCandidate`, and `match_candidate(...)`.
- Produces:
  ```python
  @dataclass(frozen=True)
  class FoodPriceResearchFood:
      slug: str
      name_fa: str
      name_en: str
      category: str
      aliases: tuple[str, ...] = ()

  def build_food_price_research_request(
      food: FoodPriceResearchFood,
      *,
      route: ModelRoute,
      requested_source_count: int,
      excluded_domains: Iterable[str] = (),
      as_of_date: date | None = None,
      preferences: ProviderRoutingPreferences | None = None,
      temperature: float = 0.0,
      max_output_tokens: int = 4096,
  ) -> StructuredGenerationRequest

  class FoodPriceResearchQuote(BaseModel):
      source_name: str
      source_url: str
      product_title: str
      normal_price: Decimal
      promotional_price: Decimal | None = None
      currency: Literal["TOMAN", "IRR"]
      package_quantity: Decimal
      package_unit: Literal["g", "kg", "ml", "l", "unit", "item"]
      region: str | None = None

  class FoodPriceResearchOutput(BaseModel):
      food_slug: str
      quotes: tuple[FoodPriceResearchQuote, ...] = ()

  @dataclass(frozen=True)
  class FoodPriceResearchEvidence:
      observation: PriceObservation
      source_name: str
      source_url: str
      source_domain: str
      product_title: str
      provider_code: str
      provider_product_id: str
      normalized_normal_price_toman: Decimal
      match_accepted: bool

  @dataclass(frozen=True)
  class AgentFoodPriceResearchResult:
      evidence: tuple[FoodPriceResearchEvidence, ...]
      request_ids: tuple[str, ...]
      expanded: bool

  class FoodPriceResearchError(Exception):
      code: str
      evidence: tuple[FoodPriceResearchEvidence, ...]

      def __init__(
          self,
          code: str,
          message: str,
          evidence: tuple[FoodPriceResearchEvidence, ...] = (),
      ) -> None:
          super().__init__(message)
          self.code = code
          self.evidence = evidence

  class AgentFoodPriceResearcher:
      async def research(self, food: FoodPriceResearchFood) -> AgentFoodPriceResearchResult:
          raise NotImplementedError
  ```

- [ ] **Step 1: Write failing contract and policy tests**

  Add tests with a fake structured provider and no network calls for:

  ```python
  def test_request_targets_three_sources_and_uses_canonical_prompt():
      request = build_food_price_research_request(food, route=route, requested_source_count=3)
      assert request.input_payload["requested_source_count"] == 3
      assert request.input_payload["excluded_domains"] == []
      assert "Use live web search/browser tools" in request.system_prompt
      assert "Do not calculate the Fitsho reference price" in request.system_prompt
      assert "final average" not in request.system_prompt.lower()

  async def test_coherent_first_pass_does_not_expand():
      provider = FakeStructuredProvider([
          output(190000, "digikala.com"),
          output(198000, "okala.ir"),
          output(205000, "basalam.com"),
      ])
      result = await AgentFoodPriceResearcher(provider, route=route).research(food)
      assert provider.requests[0].input_payload["requested_source_count"] == 3
      assert len(provider.requests) == 1

  async def test_incoherent_first_pass_expands_with_exclusions_and_two_slots():
      provider = FakeStructuredProvider([
          output(190000, "digikala.com"),
          output(200000, "okala.ir"),
          output(430000, "basalam.com"),
          output(195000, "torob.com"),
          output(205000, "emalls.ir"),
      ])
      result = await AgentFoodPriceResearcher(provider, route=route).research(food)
      assert len(provider.requests) == 2
      assert provider.requests[1].input_payload["requested_source_count"] == 2
      assert set(provider.requests[1].input_payload["excluded_domains"]) == {
          "digikala.com", "okala.ir", "basalam.com"
      }
      assert len({item.source_domain for item in result.evidence}) == 5
  ```

  Also cover same-domain `www.digikala.com`/`digikala.com`, non-HTTPS,
  credentials, localhost, private IP, malformed URL, invalid quantity, wrong
  currency, the prepared-food mismatch `ساندویچ سینه مرغ آماده`, a malformed
  structured payload, and a second response that cannot make the evidence
  exceed five canonical domains. Assert that all invalid/rejected cases fail
  safely without exposing raw provider output.

- [ ] **Step 2: Run the new tests and verify red**

  Run from `backend/`:

  ```bash
  uv run pytest tests/nutrition/test_agent_food_price_research.py -q
  ```

  Expected: collection or assertion failures because the canonical module,
  researcher, and production matching rejection do not yet exist.

- [ ] **Step 3: Implement the strict models and canonical request builder**

  Define `FoodPriceResearchQuote` and `FoodPriceResearchOutput` with
  `ConfigDict(extra="forbid")`, bounded strings, positive `Decimal` fields,
  literal currencies/units, and `quotes` limited to five. Put the complete
  approved live-web system prompt in one module-level constant. Build the
  normal `StructuredGenerationRequest` with the current date, Iran market,
  canonical food identity, requested count, and sorted canonical exclusions;
  reject counts outside `1..5`.

- [ ] **Step 4: Implement URL/domain helpers and bounded median policy**

  Add helpers that parse only HTTPS URLs, reject userinfo, invalid ports,
  localhost/local names, and loopback/private/link-local/reserved IP literals.
  Lowercase and strip a trailing dot, remove `www.`, and derive registrable
  identities using the last two labels except `.co.ir`, `.org.ir`, `.net.ir`,
  `.gov.ir`, and `.ac.ir`, which use the last three labels. Normalize the URL
  for product IDs by removing fragments and normalizing the hostname.

  Implement Decimal median selection with the exact inclusive rule:

  ```python
  MEDIAN_BAND_FRACTION = Decimal("0.20")
  trusted = {
      quote for quote in quotes
      if abs(quote.normalized_normal_price_toman - median) / median
      <= MEDIAN_BAND_FRACTION
  }
  ```

- [ ] **Step 5: Implement evidence parsing and two-pass research**

  For each structured response, validate the output model and canonical slug,
  derive the URL/domain/provider code/product ID, construct a
  `PublicProductCandidate`, reuse `match_candidate(...)`, and call
  `normalize_observation(...)`. Keep at most one usable evidence item per
  canonical domain and at most five domains across both phases. Preserve
  request IDs only as bounded metadata.

  Always make the first request with count `3` and no exclusions. Skip the
  second request only when three distinct accepted, normalized domains all
  fit the first-pass median band. Otherwise make exactly one request for
  `min(5 - collected_domain_count, 5)` additional domains, excluding all
  collected domains. Raise `FoodPriceResearchError` for transport,
  validation, or malformed response failure while retaining bounded partial
  evidence; never retry the expansion beyond the second phase.

- [ ] **Step 6: Add the prepared-food matcher regression and run green**

  Add `"ساندویچ"` to the existing reject-term mechanism (or the smallest
  existing semantic rule that rejects prepared dishes) and assert the
  canonical chicken-breast candidate is not accepted. Run:

  ```bash
  uv run pytest tests/nutrition/test_agent_food_price_research.py -q
  uv run ruff check app/nutrition/ai_price_research.py app/nutrition/public_price_matching.py tests/nutrition/test_agent_food_price_research.py
  ```

  Expected: all new research tests pass without any live website access.

- [ ] **Step 7: Commit the canonical research unit**

  ```bash
  git add backend/app/nutrition/ai_price_research.py backend/app/nutrition/public_price_matching.py backend/tests/nutrition/test_agent_food_price_research.py
  git commit -m "feat(nutrition): add bounded Agent food price research"
  git push origin main
  ```

### Task 2: Review quote relationship and Agent provider persistence primitives

**Files:**
- Modify: `backend/app/nutrition/models.py`
- Create: `backend/alembic/versions/20260901_116_add_price_review_source_quote_ids.py`
- Modify: `backend/tests/nutrition/test_food_pricing.py`
- Modify: `backend/tests/nutrition/test_admin_monitoring_api.py`

**Interfaces:**
- Consumes: current Alembic head `20260901_115` and existing nutrition quote/provider models.
- Produces: `NutritionFoodPriceReview.source_quote_ids: Mapped[list[str]]` with a non-null empty-list default; an Alembic upgrade that adds JSON, backfills existing rows with `[]`, then enforces `NOT NULL`; helper logic in the price service to create stable Agent provider rows.

- [ ] **Step 1: Write failing persistence tests**

  Add a schema-focused database assertion that a new review defaults to `[]`
  and an existing row is unaffected by the migration. Keep the Agent review
  quote-ID and monitoring-resolution assertions in Tasks 4 and 6, where the
  service and response behavior are implemented.

- [ ] **Step 2: Run the persistence tests and verify red**

  ```bash
  uv run pytest tests/nutrition/test_food_pricing.py tests/nutrition/test_admin_monitoring_api.py -q
  ```

  Expected: failure because the review model has no `source_quote_ids` column.

- [ ] **Step 3: Add the model field and migration from the verified head**

  Add:

  ```python
  source_quote_ids: Mapped[list[str]] = mapped_column(
      JSON,
      nullable=False,
      default=list,
      server_default=text("'[]'::json"),
  )
  ```

  Create the migration with `down_revision = "20260901_115"`. Upgrade in a
  safe sequence: add the JSON column nullable with an empty-array server
  default, update null existing rows to `[]`, then alter it to non-null. The
  downgrade drops only this column.

- [ ] **Step 4: Verify migration and model behavior**

  ```bash
  uv run alembic heads
  uv run alembic upgrade head
  uv run pytest tests/nutrition/test_food_pricing.py tests/nutrition/test_admin_monitoring_api.py -q
  ```

  Expected: the new head is reported, upgrade succeeds, and the schema-focused
  review default assertion passes.

- [ ] **Step 5: Commit the schema change**

  ```bash
  git add backend/app/nutrition/models.py backend/alembic/versions/20260901_116_add_price_review_source_quote_ids.py backend/tests/nutrition/test_food_pricing.py backend/tests/nutrition/test_admin_monitoring_api.py
  git commit -m "feat(nutrition): retain review source quote relationships"
  git push origin main
  ```

### Task 3: Single execution selector and Agent-only configuration

**Files:**
- Create: `backend/app/nutrition/price_execution.py`
- Modify: `backend/app/body_analysis/admin_config/service.py`
- Modify: `backend/tests/admin/test_ai_task_settings_api.py`
- Modify: `backend/tests/nutrition/test_food_pricing.py`

**Interfaces:**
- Consumes: `AITaskType.FOOD_PRICE_SEARCH`, `AIExecutionBackend`, existing
  config lookup/save/verification service, `build_task_provider(...)`,
  `configured_providers(...)`, `AgentFoodPriceResearcher`, and application
  settings/HTTP clients.
- Produces:

  ```python
  @dataclass(frozen=True)
  class PriceUpdateExecution:
      providers: tuple[FoodPriceProvider, ...]
      agent_researcher: AgentFoodPriceResearcher | None

  def resolve_price_update_execution(
      db: Session,
      *,
      settings: Settings,
      price_http_client: httpx.AsyncClient,
      agent_http_client: httpx.AsyncClient | None,
      direct_provider_factory: Callable[[], Iterable[FoodPriceProvider]] | None = None,
  ) -> PriceUpdateExecution:
      raise NotImplementedError
  ```

- [ ] **Step 1: Write failing selector and settings tests**

  Replace the old expectation that Food Price Search is absent. Assert the
  task appears disabled by default with `execution_backend="agent_service"`;
  enabling API/OpenRouter returns a clear 4xx; Agent enablement requires
  agent/model/profile fields and passed task-scoped verification; a passed
  profile can save. Add selector tests that disabled/missing config returns
  direct providers and enabled Agent config returns no direct providers plus
  a researcher. Add a test that enabled Agent construction without an Agent
  client fails as configuration error rather than selecting direct providers.

- [ ] **Step 2: Run settings and selector tests and verify red**

  ```bash
  uv run pytest tests/admin/test_ai_task_settings_api.py tests/nutrition/test_food_pricing.py -q
  ```

  Expected: failures because the service still excludes/rejects the task and
  the selector does not exist.

- [ ] **Step 3: Implement `price_execution.py`**

  Query the existing `AITaskConfig`. For missing/disabled config, call the
  existing configured provider factory. For enabled Food Price Search, reject
  any backend other than `AGENT_SERVICE`, call `build_task_provider(...)` with
  the selected Agent/model/profile/timeout settings and the supplied lifetime
  Agent client, then construct `AgentFoodPriceResearcher` with the returned
  provider and `ModelRoute`. Do not reconstruct Agent auth or profile logic.

- [ ] **Step 4: Update admin configuration rules**

  Include `FOOD_PRICE_SEARCH` in configurable and Agent Service task tuples.
  Remove the old production-updater rejection. Keep the missing-task default
  API behavior for every other task, but return Agent Service/disabled for
  Food Price Search. Reject enabled API/OpenRouter configuration with a clear
  `AIConfigError`. Leave existing verification and other task validation
  unchanged.

- [ ] **Step 5: Run green checks and commit**

  ```bash
  uv run pytest tests/admin/test_ai_task_settings_api.py tests/nutrition/test_food_pricing.py -q
  uv run ruff check app/nutrition/price_execution.py app/body_analysis/admin_config/service.py tests/admin/test_ai_task_settings_api.py
  git add backend/app/nutrition/price_execution.py backend/app/body_analysis/admin_config/service.py backend/tests/admin/test_ai_task_settings_api.py backend/tests/nutrition/test_food_pricing.py
  git commit -m "feat(ai): enable Agent Service food price task selection"
  git push origin main
  ```

### Task 4: Production price update integration and failure isolation

**Files:**
- Modify: `backend/app/nutrition/price_update_service.py`
- Modify: `backend/app/nutrition/price_update.py`
- Modify: `backend/tests/nutrition/test_food_pricing.py`

**Interfaces:**
- Consumes: `AgentFoodPriceResearcher`, `FoodPriceResearchFood`, existing
  `normalize_observation(...)`, `decide_reference_price(...)`, quote/history/
  review models, and the selector result.
- Produces:

  ```python
  async def run_price_update_async(
      db: Session,
      *,
      providers: Iterable[FoodPriceProvider],
      agent_researcher: AgentFoodPriceResearcher | None = None,
      scheduled_for: datetime | None = None,
      retry_attempts: int = 3,
      trigger_kind: PriceUpdateTriggerKind = PriceUpdateTriggerKind.MANUAL,
  ) -> PriceUpdateRun:
      raise NotImplementedError
  ```

  Existing callers that pass only `providers` retain the direct path.

- [ ] **Step 1: Write failing Agent integration tests**

  Add fake researcher cases to `test_food_pricing.py`:

  - `190000/198000/205000` from Digikala/Okala/Basalam: three provider rows,
    accepted Backend-calculated reference, sample count three, history, URLs,
    no review, and no second research call.
  - `190000/200000/430000` then `195000/205000`: two calls, trusted accepted
    cluster excludes 430000, all five quotes persist, and rejected IDs retain
    the outlier.
  - `190000/350000/520000/760000/1100000`: review with disagreement, all
    source IDs, unchanged previous reference, and no new accepted reference.
  - fewer than three usable domains: `INSUFFICIENT_SOURCES`, no average.
  - normal/promotion separation, previous-price `PRICE_JUMP`, and direct mode
    regression.
  - one food research failure does not prevent a later food from updating.

- [ ] **Step 2: Run the integration tests and verify red**

  ```bash
  uv run pytest tests/nutrition/test_food_pricing.py -q
  ```

  Expected: failures because `run_price_update_async` has no Agent argument
  and no Agent evidence persistence branch.

- [ ] **Step 3: Extend orchestration without changing direct behavior**

  Add the optional researcher argument. When present, skip direct discovery
  and provider collection, make every verified food a candidate, and process
  each food inside an isolation boundary. When absent, preserve the existing
  mapping/discovery/provider flow and retry behavior.

- [ ] **Step 4: Persist bounded Agent evidence**

  For every validated evidence item, upsert a `NutritionPriceProvider` using
  `agent_web_` plus the first 16 SHA-256 hex characters of the canonical
  domain; set `PUBLIC_CATALOG`, domain name, `https://<domain>/`,
  `agent-web-v1`, enabled, and current success time. Create no mapping.
  Derive `provider_product_id` from the first 32 SHA-256 characters of the
  canonical source URL. Store normal/promo/normalized numeric values using
  the current IRR database convention and bounded provenance in `raw_quote`.
  Add `source_url` to direct-provider raw quote data from
  `mapping.public_product_url` when present.

- [ ] **Step 5: Apply trusted-cluster and existing decision policy**

  Normalize Agent observations through the existing function. Calculate the
  final Decimal median band in the research module, require three trusted
  distinct domains, and pass only trusted values plus the previous reference
  to `decide_reference_price(...)`. Never calculate an LLM-supplied average.
  Preserve existing jump/outlier/source-spread policy. Flush quotes before
  serializing IDs. Accepted history keeps all quote IDs; accepted IDs contain
  only trusted non-outliers, rejected IDs contain median-band rejects and
  existing decision outliers. Review IDs contain every evidence quote.

- [ ] **Step 6: Isolate failure and record run details**

  Catch bounded research/structured-response/provider exceptions per food,
  create an appropriate review with previous reference untouched, and
  continue. Add only counts and execution metadata to run details, including
  `execution_mode`, `agent_research_failures`, and `agent_expanded_foods`.
  Do not log prompts, raw Agent payloads, credentials, or page contents.
  Expire overrides only according to the existing successful-update behavior.

- [ ] **Step 7: Run green checks and commit**

  ```bash
  uv run pytest tests/nutrition/test_food_pricing.py -q
  uv run ruff check app/nutrition/price_update_service.py app/nutrition/price_update.py tests/nutrition/test_food_pricing.py
  git add backend/app/nutrition/price_update_service.py backend/app/nutrition/price_update.py backend/tests/nutrition/test_food_pricing.py
  git commit -m "feat(nutrition): persist Agent price evidence safely"
  git push origin main
  ```

### Task 5: Scheduler, manual refresh, and CLI use the selector

**Files:**
- Modify: `backend/app/nutrition/price_scheduler.py`
- Modify: `backend/app/nutrition/router.py`
- Modify: `backend/app/nutrition/price_update.py`
- Modify: `backend/app/main.py`
- Modify: `backend/tests/nutrition/test_food_pricing.py`
- Modify: `backend/tests/nutrition/test_admin_monitoring_api.py`

**Interfaces:**
- Consumes: `resolve_price_update_execution(...)` and the extended
  `run_price_update_async(...)`.
- Produces: every scheduled/manual/CLI entry point resolves one execution mode;
  the application lifespan supplies one reusable `agent_http_client`, and the
  CLI owns one Agent client for its lifetime.

- [ ] **Step 1: Write failing entry-point selection tests**

  Extend existing scheduler/manual tests and add a CLI resolver test to assert
  Agent researcher selection when the task is enabled, direct providers when
  disabled/missing, and no simultaneous direct providers in Agent mode. Mock
  HTTP clients and researchers; do not contact Agent Service.

- [ ] **Step 2: Run the entry-point tests and verify red**

  ```bash
  uv run pytest tests/nutrition/test_food_pricing.py tests/nutrition/test_admin_monitoring_api.py -q
  ```

  Expected: failures because entry points currently call
  `configured_providers(...)` directly.

- [ ] **Step 3: Wire scheduler and lifespan clients**

  Add an optional Agent client to `trigger_scheduled_update(...)` and
  `scheduler_loop(...)`. Resolve execution inside the existing DB session and
  pass both fields to `run_price_update_async(...)`. Pass the app-lifetime
  `agent_http_client` from `main.py`; do not create one client per food.

- [ ] **Step 4: Wire manual refresh and CLI**

  Use the same resolver in the admin route and map `AIConfigError` to a clear
  client error. In the CLI, create one Agent client alongside the existing
  food-price HTTP client and resolve once for the run. Keep direct factory
  injection/local monkeypatch compatibility for existing tests. Never catch
  an enabled Agent failure by selecting direct providers.

- [ ] **Step 5: Run green checks and commit**

  ```bash
  uv run pytest tests/nutrition/test_food_pricing.py tests/nutrition/test_admin_monitoring_api.py -q
  uv run ruff check app/nutrition/price_scheduler.py app/nutrition/router.py app/nutrition/price_update.py app/main.py
  git add backend/app/nutrition/price_scheduler.py backend/app/nutrition/router.py backend/app/nutrition/price_update.py backend/app/main.py backend/tests/nutrition/test_food_pricing.py backend/tests/nutrition/test_admin_monitoring_api.py
  git commit -m "feat(nutrition): route all price runs through one executor"
  git push origin main
  ```

### Task 6: Smoke test and admin monitoring evidence API

**Files:**
- Modify: `backend/app/body_analysis/admin_config/task_smoke.py`
- Modify: `backend/app/nutrition/router.py`
- Modify: `backend/tests/admin/test_ai_task_smoke.py`
- Modify: `backend/tests/nutrition/test_admin_monitoring_api.py`

**Interfaces:**
- Consumes: canonical `build_food_price_research_request(...)`,
  `FoodPriceResearchOutput`, matching/domain/normalization helpers, and
  persisted quote/provider rows.
- Produces: task smoke using the production request/schema with no nutrition
  writes; monitoring review objects with at most five exact stored quote
  records.

- [ ] **Step 1: Write failing smoke and monitoring assertions**

  Update the fake smoke provider to return the canonical rice-shaped output.
  Assert the smoke calls structured generation with the canonical schema,
  validates at least three distinct HTTPS domains and price/package shape, and
  writes no quote/reference/history/review rows. Add a monitoring fixture with
  two related quote IDs and one unrelated quote; assert only the referenced
  rows are returned with source URL/domain/name, title, normal/promo/normalized
  Toman values, package fields, and observed time.

- [ ] **Step 2: Run smoke and monitoring tests and verify red**

  ```bash
  uv run pytest tests/admin/test_ai_task_smoke.py tests/nutrition/test_admin_monitoring_api.py -q
  ```

  Expected: failures because smoke still uses its duplicated prompt/schema and
  monitoring does not resolve review quote IDs.

- [ ] **Step 3: Reuse the canonical smoke request**

  Remove the smoke-only models and prompt. Build a stable synthetic Iranian
  rice identity through `build_food_price_research_request(...)`, use
  `generate_structured_text(...)`, validate `FoodPriceResearchOutput`, exact
  slug, HTTPS URLs, distinct domains, semantic match, and normalized prices.
  Record only pass/fail capability information through the existing smoke
  result path. Do not write nutrition rows or weaken runner sandbox settings.

- [ ] **Step 4: Return bounded stored review evidence**

  Load quote IDs from each review, parse only valid bounded IDs, query the
  corresponding quote/provider rows, and preserve review order. Convert
  stored IRR values to Toman by dividing by ten. Return raw provenance fields
  already stored in `raw_quote`, with provider fallback values when necessary;
  never expose raw Agent output or make a live call. Limit nested quotes to
  five.

- [ ] **Step 5: Run green checks and commit**

  ```bash
  uv run pytest tests/admin/test_ai_task_smoke.py tests/nutrition/test_admin_monitoring_api.py -q
  uv run ruff check app/body_analysis/admin_config/task_smoke.py app/nutrition/router.py tests/admin/test_ai_task_smoke.py
  git add backend/app/body_analysis/admin_config/task_smoke.py backend/app/nutrition/router.py backend/tests/admin/test_ai_task_smoke.py backend/tests/nutrition/test_admin_monitoring_api.py
  git commit -m "feat(admin): expose Agent food price evidence in monitoring"
  git push origin main
  ```

### Task 7: AI settings and nutrition monitoring frontend

**Files:**
- Modify: `frontend/src/features/admin/AdminAiSettingsPage.tsx`
- Modify: `frontend/src/features/admin/AdminNutritionMonitoringPage.tsx`
- Modify: `frontend/src/features/nutrition/api.ts`
- Modify: `frontend/src/i18n/fa.ts`
- Modify: `frontend/src/i18n/en.ts`
- Modify: `frontend/src/features/admin/AdminAiSettingsPage.test.tsx`
- Modify: `frontend/src/features/admin/AdminNutritionMonitoringPage.test.tsx`

**Interfaces:**
- Consumes: existing admin task config/capability APIs and the backend
  monitoring `price_reviews[].quotes[]` contract.
- Produces: Food Price Search visible in the Agent task list; API/OpenRouter
  cannot be selected for this task; monitoring renders the bounded evidence
  and safe external links without adding an override workflow.

- [ ] **Step 1: Write failing frontend assertions**

  Add AI settings tests for task visibility, Agent selection, supported
  models, unverified profile blocking, passed smoke enablement, and API mode
  blocking. Add monitoring fixture/tests for slug, reasons, candidate,
  warning text, every quote’s source/title/price/package, and anchors with
  `target="_blank"` and `rel="noopener noreferrer"`.

- [ ] **Step 2: Run frontend tests and verify red**

  ```bash
  npm run test -- src/features/admin/AdminAiSettingsPage.test.tsx src/features/admin/AdminNutritionMonitoringPage.test.tsx
  ```

  Expected: failures because the task list excludes Food Price Search and the
  monitoring page has no nested quote rendering.

- [ ] **Step 3: Implement Agent-only AI settings UI**

  Add `food_price_search` to `agentTasks`. For that task disable the API radio
  and add one small existing-style translated “Agent Service only” note. Keep
  the current verification-based enabled control and all other task switches
  unchanged. Ensure a disabled food task cannot accidentally submit an API
  execution backend.

- [ ] **Step 4: Implement source evidence rendering**

  Extend the `NutritionMonitoring` TypeScript type with quote evidence. For
  each review render food slug, reason codes, candidate price, the Persian and
  English confidence warning, and each bounded source’s name/domain/title,
  normal/promo price, package, and URL. Use only the existing manual override
  mechanism elsewhere in Fitsho. Add safe external-link attributes.

- [ ] **Step 5: Run green checks, build, and commit**

  ```bash
  npm run test -- src/features/admin/AdminAiSettingsPage.test.tsx src/features/admin/AdminNutritionMonitoringPage.test.tsx
  npm run build
  npm run lint
  git add frontend/src/features/admin/AdminAiSettingsPage.tsx frontend/src/features/admin/AdminNutritionMonitoringPage.tsx frontend/src/features/nutrition/api.ts frontend/src/i18n/fa.ts frontend/src/i18n/en.ts frontend/src/features/admin/AdminAiSettingsPage.test.tsx frontend/src/features/admin/AdminNutritionMonitoringPage.test.tsx
  git commit -m "feat(admin): show Agent food price review evidence"
  git push origin main
  ```

### Task 8: Full verification, source audit, and real smoke assessment

**Files:**
- Modify only if a focused test exposes a scoped defect in the files above.
- Inspect: all `run_price_update_async`, `scheduler_loop`,
  `trigger_scheduled_update`, and `configured_providers` call sites.

**Interfaces:**
- Consumes: all implementation commits and the actual migrated database.
- Produces: verified test results, source-audit findings, and an honest real
  Agent smoke/profile report.

- [ ] **Step 1: Run focused Backend verification**

  ```bash
  cd backend
  uv run pytest tests/nutrition/test_agent_food_price_research.py tests/nutrition/test_food_pricing.py tests/nutrition/test_admin_monitoring_api.py tests/admin/test_ai_task_settings_api.py tests/admin/test_ai_task_smoke.py -q
  ```

- [ ] **Step 2: Run broader Backend and migration checks**

  ```bash
  uv run pytest -q
  uv run ruff check .
  uv run alembic heads
  uv run alembic upgrade head
  ```

- [ ] **Step 3: Run frontend and compose checks**

  ```bash
  cd ../frontend
  npm run test -- src/features/admin/AdminAiSettingsPage.test.tsx src/features/admin/AdminNutritionMonitoringPage.test.tsx
  npm run build
  npm run lint
  cd ..
  docker compose config
  ```

- [ ] **Step 4: Perform the required source audit**

  ```bash
  rg -n "Use live web search|research_current_iran_food_retail_prices|fitsho_food_price_research_v1|FOOD_PRICE_SEARCH|food_price_search" backend agent-service frontend
  rg -n "run_price_update_async|scheduler_loop|trigger_scheduled_update|configured_providers" backend/app
  ```

  Confirm the full production prompt occurs only in the canonical Backend
  module, smoke reuses the builder, no food-price-specific Agent endpoint or
  duplicated production prompt exists, and every run entry point uses the
  selector.

- [ ] **Step 5: Run real smoke only when local prerequisites exist**

  Use the existing Admin `FOOD_PRICE_SEARCH` smoke with an available
  authenticated Agent Service profile. Record exact profile results. If a
  runner lacks live web capability, leave it failed/unverified and report the
  runner-specific blocker; do not weaken sandbox/security settings or fake a
  pass.

- [ ] **Step 6: Commit only scoped verification repairs**

  If a scoped repair is required, add a focused regression test, rerun the
  affected checks, and commit it with a specific Conventional Commit message.
  Otherwise leave source unchanged after verification.

- [ ] **Step 7: Prepare the final evidence report**

  Report only concrete facts: created/modified files, migration, exact
  3-to-5 and 20% behavior, domain de-duplication, Backend reference policy,
  review evidence rendering, exact test outcomes, real smoke/profile outcomes,
  and remaining blockers. Include the required memory citation block last.
