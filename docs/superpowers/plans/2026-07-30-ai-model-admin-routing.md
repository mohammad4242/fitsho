# AI Model Admin Routing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give administrators a live OpenCode Zen model catalogue, manual model selection, and ordered automatic fallback across free models for workout generation.

**Architecture:** Persist Zen models and one global routing setting in PostgreSQL. A routing dependency snapshots the selected model(s) for one generation; the workout service validates every response and advances through automatic candidates until one produces a valid plan. The provider owns four HTTP wire adapters while the admin module owns authorization and HTTP presentation.

**Tech Stack:** FastAPI, SQLAlchemy, Alembic, httpx, Pydantic, pytest, React 19, TypeScript, Vite, Vitest, i18next.

## Global Constraints

- Keep `OPENCODE_ZEN_API_KEY` in backend environment configuration only; never return or store it in the database.
- Preserve every existing generation-payload field for every model adapter.
- Support Zen `responses`, `chat_completions`, `messages`, and `gemini` API kinds.
- Automatic routing must use enabled `free` models only, in administrator-defined ascending priority.
- Zen `/v1/models` supplies only IDs: unknown synchronized IDs remain disabled until an administrator classifies API kind and billing class.
- All new administrator routes use the existing `require_admin` guard and mutation routes use `require_trusted_origin`.
- Do not stage or alter unrelated dirty files, the preview compose override, or `backend/.env`.

## File Structure

- Create: `backend/app/ai/models.py` — SQLAlchemy `AiModel` and singleton `AiRoutingSettings`.
- Create: `backend/app/ai/catalog.py` — documented Zen metadata, catalog sync, and model-selection queries.
- Create: `backend/app/ai/routing.py` — typed model candidates and provider construction.
- Modify: `backend/app/ai/opencode_zen.py` — four Zen request/response adapters behind the existing provider protocol.
- Modify: `backend/app/ai/provider.py` and `backend/app/ai/schemas.py` — candidate/result interfaces needed by fallback.
- Modify: `backend/app/workouts/dependencies.py` and `backend/app/workouts/service.py` — snapshot routing and retry semantic failures on later free models.
- Modify: `backend/app/admin/schemas.py`, `backend/app/admin/router.py`, and `backend/app/main.py` — protected AI-model API routes.
- Create: `backend/alembic/versions/20260730_09_create_ai_model_routing.py` — tables, constraints, documented Zen seed, and default manual Nemotron setting.
- Create: backend tests under `backend/tests/ai/` and `backend/tests/admin/` for models, adapters, selection, and API authorization.
- Create: `frontend/src/features/admin/AdminAiModelsPage.tsx` and `AdminAiModelsPage.test.tsx` — AI-model control page.
- Modify: `frontend/src/features/admin/api.ts`, `types.ts`, `admin.css`, `api.test.ts`, `frontend/src/App.tsx`, `frontend/src/shared/AuthenticatedHeader.tsx`, and `frontend/src/i18n/{fa,en}.ts` — API client, route, navigation, localized UI, and styling.

---

### Task 1: Persist the catalogue and routing settings

**Files:**
- Create: `backend/app/ai/models.py`
- Create: `backend/app/ai/catalog.py`
- Create: `backend/alembic/versions/20260730_09_create_ai_model_routing.py`
- Modify: `backend/alembic/env.py`
- Test: `backend/tests/ai/test_model_catalog.py`
- Test: `backend/tests/database/test_ai_models.py`

**Interfaces:**
- Produces `ZenApiKind` with `RESPONSES`, `CHAT_COMPLETIONS`, `MESSAGES`, and `GEMINI` values.
- Produces `BillingClass` with `FREE` and `PAID`; `RoutingMode` with `MANUAL` and `AUTOMATIC`.
- Produces `AiModel(id, model_id, display_name, api_kind, billing_class, is_enabled, priority, is_custom, classification_required, last_synced_at, last_checked_at, last_error_code, last_error_message)`.
- Produces `AiRoutingSettings(id=1, mode, manual_model_id, updated_at)` and `select_route_models(db) -> tuple[AiModel, ...]`.

- [ ] **Step 1: Write failing persistence and selection tests**

```python
def test_automatic_route_returns_only_enabled_free_models_in_priority_order(db: Session) -> None:
    _model(db, "nemotron-3-ultra-free", BillingClass.FREE, priority=20)
    _model(db, "big-pickle", BillingClass.FREE, priority=10)
    _model(db, "gpt-5.6-terra", BillingClass.PAID, priority=1)
    _settings(db, RoutingMode.AUTOMATIC)

    assert [model.model_id for model in select_route_models(db)] == [
        "big-pickle", "nemotron-3-ultra-free",
    ]
```

```python
def test_unknown_zen_id_is_disabled_until_admin_classifies_it(db: Session) -> None:
    result = synchronize_zen_catalogue(db, {"new-free-model"})

    assert result.needs_classification == ["new-free-model"]
    model = get_model_by_id(db, "new-free-model")
    assert model is not None
    assert model.is_enabled is False
    assert model.classification_required is True
```

- [ ] **Step 2: Run the new tests to verify RED**

Run: `cd backend && TEST_DATABASE_URL=postgresql+psycopg://fitsho:fitsho@localhost:5432/fitsho_test uv run pytest tests/ai/test_model_catalog.py tests/database/test_ai_models.py -q`

Expected: FAIL because the model classes and catalogue functions do not exist.

- [ ] **Step 3: Add models, migration, and documented metadata**

```python
class ZenApiKind(StrEnum):
    RESPONSES = "responses"
    CHAT_COMPLETIONS = "chat_completions"
    MESSAGES = "messages"
    GEMINI = "gemini"


class AiRoutingSettings(Base):
    __tablename__ = "ai_routing_settings"
    id: Mapped[int] = mapped_column(primary_key=True, default=1)
    mode: Mapped[RoutingMode] = mapped_column(
        Enum(RoutingMode, native_enum=False, values_callable=enum_values), nullable=False
    )
    manual_model_id: Mapped[UUID | None] = mapped_column(ForeignKey("ai_models.id"))
```

Create `ai_models` with a unique `model_id`, non-negative `priority`, enum check constraints, and indexes for `(is_enabled, billing_class, priority)` and `model_id`. Seed every currently documented Zen ID in the migration: GPT IDs as `responses`; Claude and Qwen IDs as `messages`; Gemini IDs as `gemini`; Grok, DeepSeek, MiniMax, GLM, Kimi, Big Pickle, MiMo, Laguna, Ling, North, and Nemotron IDs as `chat_completions`. Mark only `big-pickle`, `deepseek-v4-flash-free`, `mimo-v2.5-free`, `laguna-s-2.1-free`, `ling-3.0-flash-free`, `north-mini-code-free`, and `nemotron-3-ultra-free` as `free`. Seed singleton manual routing to `nemotron-3-ultra-free`.

`catalog.py` owns the same documented mapping for later sync. `synchronize_zen_catalogue` upserts known IDs, preserves custom rows, disables missing built-in rows, and inserts unknown IDs as disabled/classification-required. `select_route_models` raises a domain `NoEnabledRouteModelsError` for an invalid manual selection or an empty automatic list.

- [ ] **Step 4: Run migration and tests to verify GREEN**

Run: `cd backend && TEST_DATABASE_URL=postgresql+psycopg://fitsho:fitsho@localhost:5432/fitsho_test uv run pytest tests/ai/test_model_catalog.py tests/database/test_ai_models.py -q`

Expected: PASS; a fresh test database contains the documented rows and one valid routing row.

- [ ] **Step 5: Commit**

```bash
git add backend/app/ai/models.py backend/app/ai/catalog.py backend/alembic/env.py \
  backend/alembic/versions/20260730_09_create_ai_model_routing.py \
  backend/tests/ai/test_model_catalog.py backend/tests/database/test_ai_models.py
git commit -m "feat(ai-routing): persist Zen model catalogue"
```

### Task 2: Make the Zen provider API-kind aware

**Files:**
- Modify: `backend/app/ai/opencode_zen.py`
- Modify: `backend/app/ai/provider.py`
- Modify: `backend/app/ai/schemas.py`
- Create: `backend/app/ai/routing.py`
- Test: `backend/tests/ai/test_opencode_zen.py`
- Test: `backend/tests/ai/test_routing.py`

**Interfaces:**
- Consumes `AiModel`, `ZenApiKind`, `WorkoutGenerationModelRequest`, and the shared app `httpx.AsyncClient`.
- Produces `ModelProviderCandidate(model_id: str, provider: WorkoutPlanModelProvider)`.
- Produces `build_model_candidates(models, client, settings) -> tuple[ModelProviderCandidate, ...]`.
- `OpenCodeZenWorkoutPlanProvider(client, api_key, base_url, model, api_kind, timeout_seconds)` retains `generate_plan(request)`.

- [ ] **Step 1: Write failing adapter contract tests**

```python
@pytest.mark.parametrize(
    ("api_kind", "url"),
    [
        (ZenApiKind.RESPONSES, "https://zen.example/v1/responses"),
        (ZenApiKind.CHAT_COMPLETIONS, "https://zen.example/v1/chat/completions"),
        (ZenApiKind.MESSAGES, "https://zen.example/v1/messages"),
        (ZenApiKind.GEMINI, "https://zen.example/v1/models/gemini-3.6-flash:generateContent"),
    ],
)
def test_zen_adapter_uses_the_documented_endpoint(
    api_kind: ZenApiKind, url: str
) -> None:
    seen_url: list[str] = []
    provider = _provider(api_kind, lambda request: seen_url.append(str(request.url)) or _success(api_kind))
    _run(provider.generate_plan(_request()))
    assert seen_url == [url]
```

Add fixtures that prove the original `input_payload` is JSON-serialized unchanged for every kind, that each successful envelope becomes `WorkoutPlanModelOutput`, and that timeout, 401/403, 429, 5xx, malformed output, and refusal map to existing safe `ProviderErrorCode` values.

- [ ] **Step 2: Run adapter tests to verify RED**

Run: `cd backend && uv run pytest tests/ai/test_opencode_zen.py tests/ai/test_routing.py -q`

Expected: FAIL because the constructor has no `api_kind` and Messages/Gemini routes do not exist.

- [ ] **Step 3: Implement four adapter serializers and parsers**

```python
def _request_body(self, request: WorkoutGenerationModelRequest) -> dict[str, object]:
    return {
        ZenApiKind.RESPONSES: self._responses_body,
        ZenApiKind.CHAT_COMPLETIONS: self._chat_completions_body,
        ZenApiKind.MESSAGES: self._messages_body,
        ZenApiKind.GEMINI: self._gemini_body,
    }[self._api_kind](request)
```

Keep `responses` behavior byte-for-byte equivalent to the current payload. Use OpenAI-compatible `messages` and `response_format` for Chat Completions. Use Anthropic Messages tool choice named `fitsho_workout_plan` with the existing response schema as `input_schema`, then parse the returned `tool_use.input` object. Use Gemini `systemInstruction`, one user JSON part, `responseMimeType: application/json`, and `responseJsonSchema`; parse `candidates[0].content.parts[*].text`. Put exact required API headers, endpoint suffixes, usage-field mapping, and refusal detection in one API-kind dispatch table. No adapter may drop fields from `request.input_payload`.

`routing.py` maps one database row to one typed provider candidate; it never selects paid or disabled rows in automatic mode.

- [ ] **Step 4: Run adapter and static checks to verify GREEN**

Run: `cd backend && uv run pytest tests/ai/test_opencode_zen.py tests/ai/test_routing.py -q && uv run ruff check app/ai tests/ai && uv run mypy app/ai`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/ai/opencode_zen.py backend/app/ai/provider.py backend/app/ai/schemas.py \
  backend/app/ai/routing.py backend/tests/ai/test_opencode_zen.py backend/tests/ai/test_routing.py
git commit -m "feat(ai-routing): support Zen API kinds"
```

### Task 3: Route generation attempts and preserve the successful model

**Files:**
- Modify: `backend/app/workouts/dependencies.py`
- Modify: `backend/app/workouts/service.py`
- Modify: `backend/app/workouts/repository.py`
- Modify: `backend/app/ai/catalog.py`
- Test: `backend/tests/workouts/test_service.py`
- Test: `backend/tests/workouts/test_workout_plan_api.py`

**Interfaces:**
- Consumes `tuple[ModelProviderCandidate, ...]` selected once at request start.
- Produces `SuccessfulModelResponse(response: WorkoutGenerationModelResponse, model_id: str)` internally in `WorkoutGenerationService`.
- `WorkoutGenerationService` receives `providers: tuple[ModelProviderCandidate, ...]` instead of one provider.

- [ ] **Step 1: Write failing manual and automatic routing tests**

```python
def test_automatic_generation_uses_second_free_model_after_first_provider_failure(
    db: Session, seeded_generation_context: GenerationContext
) -> None:
    service = _service(candidates=(
        _candidate("nemotron-3-ultra-free", _raising_provider(ProviderErrorCode.TIMEOUT)),
        _candidate("big-pickle", _returning_provider(_valid_response(seeded_generation_context))),
    ))

    result = asyncio.run(service.generate(seeded_generation_context.user.id))

    assert result.reused is False
    assert _generation(db).model_id == "big-pickle"
```

```python
def test_automatic_generation_tries_next_model_after_semantic_validation_failure(
    db: Session, seeded_generation_context: GenerationContext
) -> None:
    invalid = _response_for_exercise_ids([uuid4()])
    valid = _valid_response(seeded_generation_context)
    service = _service(candidates=(
        _candidate("nemotron-3-ultra-free", _returning_provider(invalid)),
        _candidate("big-pickle", _returning_provider(valid)),
    ))

    asyncio.run(service.generate(seeded_generation_context.user.id))

    assert _generation(db).model_id == "big-pickle"
```

Also cover: manual mode exposes only its selected model; repairs remain on the same candidate before moving to the next; all candidates failing return the current safe generation error; and cached/reused plans do not call any model.

- [ ] **Step 2: Run targeted service tests to verify RED**

Run: `cd backend && TEST_DATABASE_URL=postgresql+psycopg://fitsho:fitsho@localhost:5432/fitsho_test uv run pytest tests/workouts/test_service.py tests/workouts/test_workout_plan_api.py -q`

Expected: FAIL because the service accepts exactly one provider and records the configured environment model.

- [ ] **Step 3: Implement candidate iteration and health updates**

```python
for candidate in self._providers:
    try:
        response = await self._generate_and_validate(candidate, request, validator)
    except (WorkoutProviderError, WorkoutPlanValidationError) as error:
        self._record_model_failure(candidate.model_id, error)
        continue
    self._record_model_success(candidate.model_id)
    return SuccessfulModelResponse(response=response, model_id=candidate.model_id)
raise last_safe_provider_error
```

Snapshot candidates before `create_generation`; start the record with the first candidate ID, then overwrite both `WorkoutPlan.model_id` and `WorkoutPlanGeneration.model_id` with the successful candidate ID before activation. On terminal failure preserve the final attempted model ID and safe existing error behavior. Update `AiModel.last_checked_at`, clear last error after success, and record only safe code/message after failure. The dependency reads settings from the database on every new request, then builds candidates using the app HTTP client and env-only API key.

- [ ] **Step 4: Run service checks to verify GREEN**

Run: `cd backend && TEST_DATABASE_URL=postgresql+psycopg://fitsho:fitsho@localhost:5432/fitsho_test uv run pytest tests/workouts/test_service.py tests/workouts/test_workout_plan_api.py -q && uv run ruff check app/workouts tests/workouts && uv run mypy app/workouts`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/workouts/dependencies.py backend/app/workouts/service.py \
  backend/app/workouts/repository.py backend/app/ai/catalog.py \
  backend/tests/workouts/test_service.py backend/tests/workouts/test_workout_plan_api.py
git commit -m "feat(ai-routing): add ordered free-model fallback"
```

### Task 4: Expose protected administrator model APIs

**Files:**
- Modify: `backend/app/admin/schemas.py`
- Modify: `backend/app/admin/router.py`
- Modify: `backend/app/main.py`
- Modify: `backend/app/ai/catalog.py`
- Create: `backend/tests/admin/test_ai_model_api.py`

**Interfaces:**
- `GET /api/v1/admin/ai-models` returns models plus global routing settings.
- `PATCH /api/v1/admin/ai-routing` accepts `{mode, manual_model_id}`.
- `PATCH /api/v1/admin/ai-models/{model_id}` updates name, API kind, billing class, enabled state, and priority.
- `POST /api/v1/admin/ai-models` creates a custom model.
- `POST /api/v1/admin/ai-models/sync` fetches `GET {base_url}/models` and returns classified/unknown counts.
- `POST /api/v1/admin/ai-models/{model_id}/test` records the safe result of a bounded health probe.

- [ ] **Step 1: Write failing authorization and validation tests**

```python
def test_non_admin_cannot_read_or_mutate_ai_models(client: TestClient) -> None:
    assert client.get("/api/v1/admin/ai-models").status_code == 403
    assert client.patch("/api/v1/admin/ai-routing", json={"mode": "automatic"}).status_code == 403
```

```python
def test_automatic_mode_rejects_paid_or_disabled_candidates(client: TestClient, db: Session) -> None:
    make_current_user_admin(client, db)
    model = _create_model(db, model_id="gpt-5.6-terra", billing_class="paid", is_enabled=True)
    response = client.patch(f"/api/v1/admin/ai-models/{model.id}", headers=ORIGIN, json={
        "billing_class": "paid", "is_enabled": True, "priority": 1,
    })
    assert response.status_code == 200
    assert "gpt-5.6-terra" not in _automatic_model_ids(db)
```

Use a mocked `httpx.AsyncClient` for sync and health probes. Assert unknown IDs are returned as classification-required; custom rows survive sync; an enabled custom row requires API kind and billing class; and API responses never contain the secret key.

- [ ] **Step 2: Run admin API tests to verify RED**

Run: `cd backend && TEST_DATABASE_URL=postgresql+psycopg://fitsho:fitsho@localhost:5432/fitsho_test uv run pytest tests/admin/test_ai_model_api.py -q`

Expected: FAIL because no AI model administrator routes exist.

- [ ] **Step 3: Implement schemas, routes, sync, and health probe**

```python
@router.patch("/ai-routing", response_model=AdminAiRoutingResponse,
              dependencies=[Depends(require_trusted_origin)])
def update_ai_routing(payload: AdminAiRoutingUpdate, db: DatabaseSession) -> AdminAiRoutingResponse:
    return update_routing_settings(db, payload)
```

Validate model IDs as stripped 1–160-character strings; validate custom name as 2–160 characters; disallow modifying `is_custom=False` model ID; reject manual selection of disabled or classification-required models. The health probe sends a minimal schema-valid request through the same typed adapter with a bounded output limit, updates only safe status data, and returns an administrator-readable result. The sync uses the app lifespan client, accepts only `{object: "list", data: [{id: str}]}`, and treats malformed upstream data as a safe 502 without mutating the catalogue.

- [ ] **Step 4: Run API and type checks to verify GREEN**

Run: `cd backend && TEST_DATABASE_URL=postgresql+psycopg://fitsho:fitsho@localhost:5432/fitsho_test uv run pytest tests/admin/test_ai_model_api.py -q && uv run ruff check app/admin app/ai tests/admin && uv run mypy app/admin app/ai`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/admin/schemas.py backend/app/admin/router.py backend/app/main.py \
  backend/app/ai/catalog.py backend/tests/admin/test_ai_model_api.py
git commit -m "feat(admin): manage Zen AI models"
```

### Task 5: Build the localized Admin AI Models page

**Files:**
- Create: `frontend/src/features/admin/AdminAiModelsPage.tsx`
- Create: `frontend/src/features/admin/AdminAiModelsPage.test.tsx`
- Modify: `frontend/src/features/admin/api.ts`
- Modify: `frontend/src/features/admin/api.test.ts`
- Modify: `frontend/src/features/admin/types.ts`
- Modify: `frontend/src/features/admin/admin.css`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/shared/AuthenticatedHeader.tsx`
- Modify: `frontend/src/i18n/fa.ts`
- Modify: `frontend/src/i18n/en.ts`

**Interfaces:**
- Consumes `AdminAiModelsResponse`, `AdminAiModel`, and `AdminAiRoutingSettings` from `api.ts`.
- Produces route `/admin/ai-models` behind the existing `AdminRoute`.
- Produces client calls `getAdminAiModels`, `updateAdminAiRouting`, `updateAdminAiModel`, `createAdminAiModel`, `syncAdminAiModels`, and `testAdminAiModel`.

- [ ] **Step 1: Write failing page and client tests**

```tsx
it("sets automatic routing and renders only free models in priority order", async () => {
  mockGetAdminAiModels({ mode: "automatic", models: [freeFirst, paidModel, freeSecond] });
  render(<AdminAiModelsPage />);

  await userEvent.click(screen.getByRole("radio", { name: /automatic/i }));

  expect(screen.getAllByTestId("free-priority-row")).toHaveLength(2);
  expect(mockUpdateAdminAiRouting).toHaveBeenCalledWith({ mode: "automatic" });
});
```

Add cases for manual selection, a disabled/needs-classification badge, save of a custom model with API kind and billing class, sync status, model-test result, API error/retry, and the header link.

- [ ] **Step 2: Run frontend tests to verify RED**

Run: `cd frontend && npm run test -- AdminAiModelsPage api`

Expected: FAIL because the route, page, types, and API client calls do not exist.

- [ ] **Step 3: Implement page, route, and localization**

```tsx
<fieldset className="admin-choice-group">
  <legend>{t("admin.aiModels.routingMode")}</legend>
  <label><input type="radio" value="manual" checked={mode === "manual"} />{t("admin.aiModels.manual")}</label>
  <label><input type="radio" value="automatic" checked={mode === "automatic"} />{t("admin.aiModels.automatic")}</label>
</fieldset>
```

Reuse `admin-page`, `admin-hero`, `admin-form-section`, and `admin-status` styles. Add focused styles for compact model rows, state badges, priority up/down controls, and mobile one-column layout. The automatic panel renders only enabled free models and updates priority with explicit up/down buttons; manual mode renders a selector of enabled classified models. Provide Free, Paid, and Custom filter tabs, Sync, Test, enable/disable, and custom-model form controls. Add Persian and English keys for every visible label/error; keep Model IDs as LTR text.

- [ ] **Step 4: Run frontend checks to verify GREEN**

Run: `cd frontend && npm run test -- AdminAiModelsPage api && npm run lint && npm run build`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/features/admin/AdminAiModelsPage.tsx \
  frontend/src/features/admin/AdminAiModelsPage.test.tsx frontend/src/features/admin/api.ts \
  frontend/src/features/admin/api.test.ts frontend/src/features/admin/types.ts \
  frontend/src/features/admin/admin.css frontend/src/App.tsx \
  frontend/src/shared/AuthenticatedHeader.tsx frontend/src/i18n/fa.ts frontend/src/i18n/en.ts
git commit -m "feat(admin): add AI model control panel"
```

### Task 6: Verify the integrated feature and document runtime use

**Files:**
- Modify: `README.md`
- Test: `backend/tests/ai/test_model_catalog.py`
- Test: `backend/tests/ai/test_opencode_zen.py`
- Test: `backend/tests/ai/test_routing.py`
- Test: `backend/tests/admin/test_ai_model_api.py`
- Test: `backend/tests/workouts/test_service.py`
- Test: `frontend/src/features/admin/AdminAiModelsPage.test.tsx`

**Interfaces:**
- Consumes all prior tasks.
- Produces a documented administrator workflow: Sync, classify unknown model, test, enable, select manual mode or prioritize automatic free fallback.

- [ ] **Step 1: Write the missing integration assertion**

```python
def test_admin_change_applies_to_the_next_generation_without_restart(
    db: Session, second: AiModel
) -> None:
    update_routing_settings(db, mode=RoutingMode.MANUAL, manual_model_id=second.id)
    assert [model.model_id for model in select_route_models(db)] == [second.model_id]
```

- [ ] **Step 2: Run it to verify the complete path**

Run: `cd backend && TEST_DATABASE_URL=postgresql+psycopg://fitsho:fitsho@localhost:5432/fitsho_test uv run pytest tests/ai tests/admin/test_ai_model_api.py tests/workouts/test_service.py -q`

Expected: PASS.

- [ ] **Step 3: Document the operational workflow**

Add a short README section stating that keys remain in `backend/.env`, administrators open `/admin/ai-models`, Sync Zen, classify any disabled unknown model, test it, then select Manual or order enabled free models for Automatic. State that the next generation picks up the change without a restart.

- [ ] **Step 4: Run full verification**

Run: `cd backend && TEST_DATABASE_URL=postgresql+psycopg://fitsho:fitsho@localhost:5432/fitsho_test uv run pytest -q && uv run ruff check && uv run mypy`

Run: `cd frontend && npm run test && npm run lint && npm run build`

Expected: all tests, lint, type checks, and production build PASS.

- [ ] **Step 5: Commit**

```bash
git add README.md backend/tests/ai backend/tests/admin/test_ai_model_api.py \
  backend/tests/workouts/test_service.py frontend/src/features/admin/AdminAiModelsPage.test.tsx
git commit -m "docs(ai-routing): document model administration"
```
