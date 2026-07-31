# AI Model Availability History Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make each admin model test a lightweight API-availability check and show a persistent, safe history of successful and failed tests beside workout-generation failures.

**Architecture:** Add a provider-level availability method that uses the configured Zen API kind without a workout schema. Persist every result in a new append-only `ai_model_test_runs` table, return the stored run from the existing test endpoint, and expose recent runs through a read-only admin endpoint. The frontend merges model-test runs and existing workout-generation failures into one chronological AI events card.

**Tech Stack:** FastAPI, SQLAlchemy, Alembic, httpx, Pydantic, PostgreSQL, React, TypeScript, Vitest, pytest.

## Global Constraints

- Do not send profile data, exercise data, workout schemas, tool definitions, API keys, or raw provider responses in an availability test.
- Send only a short `Reply only: OK` instruction and one-token output limit through the selected API kind.
- Persist only safe error code/message, outcome, model identity, and timestamp.
- Keep workout generation's structured JSON request and existing generation-failure diagnostics unchanged.
- Success copy is exactly `با موفقیت متصل شد` and must render green in the recent AI events card.
- All test-run routes remain admin-only and trusted-origin protected where they mutate state.

---

### Task 1: Minimal provider availability request

**Files:**
- Modify: `backend/app/ai/opencode_zen.py`
- Test: `backend/tests/ai/test_opencode_zen.py`

**Interfaces:**
- Produces: `OpenCodeZenWorkoutPlanProvider.check_availability() -> None`
- Consumes: existing `_endpoint()`, `_headers()`, `_raise_for_status()`, and `_parse_response_envelope()`.
- Does not call: `_parse_plan()` or `WorkoutPlanModelOutput.model_validate()`.

- [ ] **Step 1: Write failing provider tests for all API kinds**

```python
@pytest.mark.parametrize("api_kind", list(ZenApiKind))
def test_zen_provider_availability_check_uses_minimal_request(api_kind: ZenApiKind) -> None:
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json={"id": "available"})

    provider = _provider_for(api_kind, "test-model", httpx.MockTransport(handler))
    _run(provider.check_availability())

    assert "fitsho_workout_plan" not in json.dumps(seen["body"])
    assert "Reply only: OK" in json.dumps(seen["body"])
```

Add assertions per API kind:

```python
assert body["max_tokens"] == 1  # chat_completions and messages
assert body["max_output_tokens"] == 1  # responses
assert body["generationConfig"]["maxOutputTokens"] == 1  # gemini
```

- [ ] **Step 2: Run the new test and verify RED**

Run: `uv run pytest tests/ai/test_opencode_zen.py::test_zen_provider_availability_check_uses_minimal_request -q`

Expected: FAIL because `check_availability` does not exist.

- [ ] **Step 3: Add the API-kind-specific request builder and availability method**

```python
async def check_availability(self) -> None:
    api_key = self._api_key_value()
    if api_key is None:
        raise WorkoutProviderError(
            ProviderErrorCode.NOT_CONFIGURED,
            "Workout generation is not configured.",
        )
    response = await self._client.post(
        self._endpoint(),
        headers=self._headers(api_key),
        json=self._availability_request_body(),
        timeout=self._timeout,
    )
    self._raise_for_status(response)
    self._parse_response_envelope(response)
```

Implement `_availability_request_body()` with these exact payload concepts:

```python
# responses
{"model": self._model, "input": "Reply only: OK", "max_output_tokens": 1, "store": False}
# chat completions
{"model": self._model, "messages": [{"role": "user", "content": "Reply only: OK"}], "max_tokens": 1}
# messages
{"model": self._model, "max_tokens": 1, "messages": [{"role": "user", "content": "Reply only: OK"}]}
# gemini
{"contents": [{"role": "user", "parts": [{"text": "Reply only: OK"}]}], "generationConfig": {"maxOutputTokens": 1}}
```

Keep the existing HTTP timeout, network, status-code, and HTTP-200 error-envelope mapping unchanged.

- [ ] **Step 4: Run focused provider tests and lint**

Run: `uv run pytest tests/ai/test_opencode_zen.py -q && uv run ruff check app/ai/opencode_zen.py tests/ai/test_opencode_zen.py`

Expected: PASS.

- [ ] **Step 5: Commit Task 1**

```bash
git add backend/app/ai/opencode_zen.py backend/tests/ai/test_opencode_zen.py
git commit -m "feat(ai): add lightweight model availability checks"
```

### Task 2: Persist model-test runs and expose admin API

**Files:**
- Modify: `backend/app/ai/models.py`
- Create: `backend/alembic/versions/20260731_11_create_ai_model_test_runs.py`
- Modify: `backend/app/admin/ai_models.py`
- Modify: `backend/app/admin/schemas.py`
- Modify: `backend/app/admin/router.py`
- Modify: `backend/tests/admin/test_ai_model_api.py`

**Interfaces:**
- Produces: `AiModelTestRun`, `AiModelTestOutcome`, `list_ai_model_test_runs(db, limit)`, and `AdminAiModelTestRun`.
- Changes: `check_ai_model(...) -> tuple[bool, AiModel, AiModelTestRun]`.
- Produces: `GET /api/v1/admin/ai-model-test-runs?limit=20`.

- [ ] **Step 1: Write failing API tests for persistent success and failure runs**

Add a mock `httpx.AsyncClient` transport test that calls the existing POST endpoint twice: once with an API response that succeeds and once with `{"error": {"type": "server_error"}}`.

```python
assert successful.json()["success"] is True
assert successful.json()["test_run"]["outcome"] == "succeeded"
assert failed.json()["success"] is False
assert failed.json()["test_run"]["outcome"] == "failed"
assert failed.json()["test_run"]["error_code"] == "provider_unavailable"
```

Then request the history endpoint:

```python
runs = client.get("/api/v1/admin/ai-model-test-runs?limit=20")
assert runs.status_code == 200
assert [item["outcome"] for item in runs.json()] == ["failed", "succeeded"]
assert "user_id" not in runs.text
assert "Reply only: OK" not in runs.text
```

Add an unauthenticated assertion that the history endpoint returns `401`.

- [ ] **Step 2: Run the tests and verify RED**

Run: `uv run pytest tests/admin/test_ai_model_api.py -q`

Expected: FAIL because the model/table/schema/endpoint do not exist and the test response has no `test_run`.

- [ ] **Step 3: Add model and migration**

In `app/ai/models.py`, define:

```python
class AiModelTestOutcome(StrEnum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"

class AiModelTestRun(Base):
    __tablename__ = "ai_model_test_runs"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    ai_model_id: Mapped[UUID] = mapped_column(
        ForeignKey("ai_models.id", ondelete="CASCADE"), nullable=False
    )
    model_id: Mapped[str] = mapped_column(String(160), nullable=False)
    outcome: Mapped[AiModelTestOutcome] = mapped_column(..., nullable=False)
    error_code: Mapped[str | None] = mapped_column(String(80))
    safe_error_message: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(..., nullable=False)
```

Add an index on `created_at` and an index on `(ai_model_id, created_at)`. Create Alembic revision `20260731_11` with `down_revision = "20260730_10"`; upgrade creates the table and indexes, downgrade drops indexes then table.

- [ ] **Step 4: Record the exact outcome in the admin service**

Replace the workout-plan request in `check_ai_model` with:

```python
model.last_checked_at = datetime.now(UTC)
try:
    await provider.check_availability()
except WorkoutProviderError as error:
    model.last_error_code = error.code.value
    model.last_error_message = error.safe_message
    run = AiModelTestRun(
        ai_model_id=model.id,
        model_id=model.model_id,
        outcome=AiModelTestOutcome.FAILED,
        error_code=error.code.value,
        safe_error_message=error.safe_message,
    )
    db.add(run)
    db.commit()
    db.refresh(model)
    db.refresh(run)
    return False, model, run
```

On success, clear the model's last-error summary, add a `SUCCEEDED` run with
null error fields, commit, refresh, and return it. Add
`list_ai_model_test_runs` ordered by `created_at.desc()` and bounded by `limit`.

- [ ] **Step 5: Add explicit response schemas and routes**

Add `AdminAiModelTestRun` with `id`, `model_id`, `outcome`, nullable
`error_code`, nullable `safe_error_message`, and `created_at`. Add
`test_run: AdminAiModelTestRun` to `AdminAiModelCheckResponse`.

Add the admin-only route:

```python
@router.get("/ai-model-test-runs", response_model=list[AdminAiModelTestRun])
def read_ai_model_test_runs(
    db: DatabaseSession,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> list[AdminAiModelTestRun]:
    return [_ai_model_test_run_detail(run) for run in list_ai_model_test_runs(db, limit=limit)]
```

Update the POST route to serialize and return its stored `test_run`.

- [ ] **Step 6: Run migration and backend verification**

Run:

```bash
uv run alembic upgrade head
uv run pytest tests/admin/test_ai_model_api.py tests/ai/test_opencode_zen.py -q
uv run ruff check app/ai app/admin tests/admin/test_ai_model_api.py tests/ai/test_opencode_zen.py
uv run mypy app/ai/opencode_zen.py app/ai/models.py app/admin/ai_models.py app/admin/router.py app/admin/schemas.py
```

Expected: migration reaches `20260731_11`; all focused checks PASS.

- [ ] **Step 7: Commit Task 2**

```bash
git add backend/app/ai/models.py backend/app/admin/ai_models.py backend/app/admin/schemas.py backend/app/admin/router.py backend/alembic/versions/20260731_11_create_ai_model_test_runs.py backend/tests/admin/test_ai_model_api.py
git commit -m "feat(admin): retain model test history"
```

### Task 3: Show green and red test results in recent AI events

**Files:**
- Modify: `frontend/src/features/admin/types.ts`
- Modify: `frontend/src/features/admin/api.ts`
- Modify: `frontend/src/features/admin/AdminAiModelsPage.tsx`
- Modify: `frontend/src/features/admin/AdminAiModelsPage.test.tsx`
- Modify: `frontend/src/features/admin/api.test.ts`
- Modify: `frontend/src/features/admin/admin.css`
- Modify: `frontend/src/i18n/fa.ts`
- Modify: `frontend/src/i18n/en.ts`

**Interfaces:**
- Produces: `AdminAiModelTestRun` TypeScript type and `getAdminAiModelTestRuns(limit?: number)`.
- Consumes: POST test response `test_run` and GET history response.
- Retains: `AdminAiGenerationFailure` and existing workout failure display.

- [ ] **Step 1: Write failing frontend tests**

Mock both event sources and verify the event card renders green success and red failure:

```tsx
adminApi.getAdminAiModelTestRuns.mockResolvedValue([
  { id: "run-success", model_id: "nemotron-3-ultra-free", outcome: "succeeded", error_code: null, safe_error_message: null, created_at: "2026-07-31T12:00:00Z" },
  { id: "run-failure", model_id: "free-model", outcome: "failed", error_code: "provider_unavailable", safe_error_message: "Workout generation is temporarily unavailable. Please try again.", created_at: "2026-07-31T11:00:00Z" },
]);

expect(await screen.findByText("با موفقیت متصل شد")).toHaveClass("admin-ai-event--success");
expect(screen.getByText("provider_unavailable")).toHaveClass("admin-ai-event--error");
```

Add a post-click test that `testAdminAiModel` returns `test_run` and the newly
returned success entry appears without a full page reload. Add API-client test:

```tsx
await expect(getAdminAiModelTestRuns()).resolves.toEqual(runs);
expect(fetch).toHaveBeenCalledWith(
  "/api/v1/admin/ai-model-test-runs?limit=20",
  expect.objectContaining({ credentials: "include" }),
);
```

- [ ] **Step 2: Run the tests and verify RED**

Run: `npm run test -- --run src/features/admin/AdminAiModelsPage.test.tsx src/features/admin/api.test.ts`

Expected: FAIL because the API client/type/event data do not exist.

- [ ] **Step 3: Add types, API client, and state loading**

Define:

```ts
export type AdminAiModelTestRun = {
  id: string;
  model_id: string;
  outcome: "succeeded" | "failed";
  error_code: string | null;
  safe_error_message: string | null;
  created_at: string;
};
```

Add `getAdminAiModelTestRuns(limit = 20)` and load it together with
`getAdminAiModels()` and `getAdminAiGenerationFailures()`. Store test runs in
their own state. When POST test returns, prepend `result.test_run`, de-duplicated
by run ID, then update the catalogue model summary.

- [ ] **Step 4: Render a single chronological AI event card**

Create a page-local discriminated union for model test and generation failure
events. Sort it descending by `created_at`. Rename the section through i18n to
the Persian equivalent of `Recent AI events`.

Render model-test entries as:

```tsx
<article className={`admin-ai-event admin-ai-event--${run.outcome === "succeeded" ? "success" : "error"}`}>
  <header><code>{run.model_id}</code><time dateTime={run.created_at}>{formatTime(run.created_at)}</time></header>
  <strong>{run.outcome === "succeeded" ? t("admin.aiModels.testSuccess") : run.error_code}</strong>
  {run.safe_error_message !== null && <p>{run.safe_error_message}</p>}
</article>
```

Keep existing workout-generation failure diagnostics in the same section, but
prefix them with a distinct i18n event label so they cannot be confused with a
model availability test.

- [ ] **Step 5: Add visual and copy rules**

Add `admin-ai-event--success` using the existing turquoise/green token and
`admin-ai-event--error` using the existing danger token. Add Persian and English
labels for recent AI events, model-test event, workout-generation event, and no
recent events. Preserve the exact existing Persian success copy.

- [ ] **Step 6: Run frontend verification**

Run:

```bash
npm run lint
npm run test -- --run
npm run build
```

Expected: PASS.

- [ ] **Step 7: Commit Task 3**

```bash
git add frontend/src/features/admin/types.ts frontend/src/features/admin/api.ts frontend/src/features/admin/AdminAiModelsPage.tsx frontend/src/features/admin/AdminAiModelsPage.test.tsx frontend/src/features/admin/api.test.ts frontend/src/features/admin/admin.css frontend/src/i18n/fa.ts frontend/src/i18n/en.ts
git commit -m "feat(admin): show model test availability history"
```

### Task 4: Full verification and live preview

**Files:**
- Verify only: backend and frontend files from Tasks 1–3

**Interfaces:**
- Verifies: persisted availability records, green/red admin events, existing generation diagnostics, and live migration.

- [ ] **Step 1: Run complete checks from the final tree**

Run:

```bash
cd backend && uv run ruff check && TEST_DATABASE_URL=postgresql+psycopg://fitsho:fitsho@localhost:5432/fitsho_test uv run pytest -q
cd frontend && npm run lint && npm run test -- --run && npm run build
```

Expected: all checks PASS; the explicit live Zen test remains skipped unless
`ZEN_LIVE_TEST=true` is deliberately configured.

- [ ] **Step 2: Apply migration and restart the feature preview**

Run:

```bash
docker restart fitsho-ai-model-admin-preview
docker exec fitsho-ai-model-admin-preview alembic current
curl -sS -o /dev/null -w "backend=%{http_code}\n" http://localhost:8000/openapi.json
curl -sS -o /dev/null -w "frontend=%{http_code}\n" http://localhost:5173
```

Expected: migration revision `20260731_11 (head)`, backend `200`, frontend `200`.

- [ ] **Step 3: Commit and push verified implementation**

```bash
git status --short
git push origin feature/ai-model-admin-routing
```

Use the repository-required commit approval before creating the final commit,
then update Draft PR #7 with the pushed commits. Do not merge the PR.
