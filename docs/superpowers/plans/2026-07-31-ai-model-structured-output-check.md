# AI Model Structured-Output Check Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the admin model test verify simple reachability and compact structured JSON support without sending real Fitsho generation data.

**Architecture:** `OpenCodeZenWorkoutPlanProvider` retains the availability check, then sends a fixed structured request using the output mechanism matching the model API kind. The response is validated as `{"status":"ok"}`. Existing admin persistence records one combined success or safe failure.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy, httpx, Pydantic, pytest.

## Global Constraints

- Do not send profile data, exercise catalogue data, a workout prompt, a generated program, or a user identifier during either test.
- Do not change real workout generation payloads, schemas, retry behavior, or fallback behavior.
- A green test proves reachability and compact structured JSON validation, not full-generation capacity or rate-limit availability.

---

### Task 1: Provider structured-output contract check

**Files:**
- Modify: `backend/app/ai/opencode_zen.py`
- Test: `backend/tests/ai/test_opencode_zen.py`

**Interfaces:**
- Consumes: `OpenCodeZenWorkoutPlanProvider.check_availability() -> None`
- Produces: `OpenCodeZenWorkoutPlanProvider.check_model_test_contract() -> None`

- [ ] **Step 1: Write failing provider tests**

```python
@pytest.mark.parametrize("api_kind", list(ZenApiKind))
async def test_zen_provider_model_test_contract_uses_compact_structured_output(api_kind):
    provider = make_provider(api_kind=api_kind, response=structured_ok_response(api_kind))
    await provider.check_model_test_contract()
    assert captured_request_uses_the_matching_structured_output_mechanism(api_kind)
    assert "profile" not in captured_request_json
    assert "exercises" not in captured_request_json


async def test_zen_provider_model_test_contract_rejects_invalid_structured_output():
    provider = make_provider(api_kind=ZenApiKind.CHAT_COMPLETIONS, response=chat_json({"status": "no"}))
    with pytest.raises(WorkoutProviderError, match="structured JSON"):
        await provider.check_model_test_contract()
```

- [ ] **Step 2: Run failing test**

Run: `uv run pytest tests/ai/test_opencode_zen.py -q`

Expected: FAIL because `check_model_test_contract` does not exist.

- [ ] **Step 3: Implement compact request and parser**

```python
class _ModelTestContract(BaseModel):
    status: Literal["ok"]


async def check_model_test_contract(self) -> None:
    response = await self._post_model_test_request(self._model_test_contract_request_body())
    payload = self._parse_response_envelope(response)
    output = self._extract_model_test_contract_output(payload)
    _ModelTestContract.model_validate(output)
```

Use `response_format.json_schema`, `text.format.json_schema`, required tool input, or Gemini JSON schema configuration according to `api_kind`. Convert validation errors to `The model did not complete the structured JSON check.` All requests contain only fixed text and a one-field schema.

- [ ] **Step 4: Verify provider implementation**

Run: `uv run pytest tests/ai/test_opencode_zen.py -q && uv run ruff check app/ai/opencode_zen.py tests/ai/test_opencode_zen.py && uv run mypy app/ai/opencode_zen.py`

Expected: PASS.

- [ ] **Step 5: Commit**

Run: `git add backend/app/ai/opencode_zen.py backend/tests/ai/test_opencode_zen.py && git commit -m "feat(ai): verify structured model test output"`

### Task 2: Run both checks in the admin test action

**Files:**
- Modify: `backend/app/admin/ai_models.py`
- Test: `backend/tests/admin/test_ai_model_api.py`

**Interfaces:**
- Consumes: `OpenCodeZenWorkoutPlanProvider.check_availability() -> None` and `check_model_test_contract() -> None`
- Produces: existing `POST /api/v1/admin/ai-models/{model_id}/test`, recording one succeeded or failed `AiModelTestRun`.

- [ ] **Step 1: Write failing admin API test**

```python
def test_admin_model_test_requires_compact_structured_output(client, admin_auth):
    response = client.post(f"/api/v1/admin/ai-models/{model_id}/test", headers=admin_auth)
    assert response.json()["success"] is False
    assert response.json()["test_run"]["error_code"] == "invalid_output"
    assert "structured JSON" in response.json()["test_run"]["safe_error_message"]
```

Mock Zen: availability returns `OK`, while compact structured output is nonconforming. Assert neither captured request contains full generation data.

- [ ] **Step 2: Run failing test**

Run: `uv run pytest tests/admin/test_ai_model_api.py::test_admin_model_test_requires_compact_structured_output -q`

Expected: FAIL because the action runs only `check_availability`.

- [ ] **Step 3: Invoke the contract check after availability**

```python
try:
    await provider.check_availability()
    await provider.check_model_test_contract()
except WorkoutProviderError as error:
    # retain existing failed-run persistence
```

Keep the current persistence and response schema. Do not add a migration or change frontend contracts.

- [ ] **Step 4: Verify focused backend behavior**

Run: `uv run pytest tests/admin/test_ai_model_api.py tests/ai/test_opencode_zen.py -q && uv run ruff check app/admin/ai_models.py app/ai/opencode_zen.py && uv run mypy app/admin/ai_models.py app/ai/opencode_zen.py`

Expected: PASS.

- [ ] **Step 5: Commit**

Run: `git add backend/app/admin/ai_models.py backend/tests/admin/test_ai_model_api.py && git commit -m "feat(admin): require structured output in model tests"`

### Task 3: Full verification and preview restart

**Files:** No source changes expected.

**Interfaces:** Consumes completed provider and admin behavior; produces a running preview.

- [ ] **Step 1: Run full verification**

Run: `TEST_DATABASE_URL=postgresql+psycopg://fitsho:fitsho@localhost:5432/fitsho_test uv run pytest -q`, `uv run ruff check`, `npm run test -- --run`, `npm run lint`, and `npm run build`.

Expected: all checks pass.

- [ ] **Step 2: Restart and inspect preview**

Run: `docker restart fitsho-ai-model-admin-preview`, `docker exec fitsho-ai-model-admin-preview alembic current`, and `curl --fail http://localhost:8000/openapi.json`.

Expected: backend starts and Alembic remains `20260731_11 (head)`.
