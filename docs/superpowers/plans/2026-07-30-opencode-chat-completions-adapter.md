# OpenCode Chat Completions Adapter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Generate workout plans through OpenCode Zen models that require the OpenAI-compatible Chat Completions API, including `nemotron-3-ultra-free`.

**Architecture:** Keep a single `OpenCodeZenWorkoutPlanProvider`. It selects the endpoint from a private model-to-API-style mapping, creates the matching request body, and extracts JSON from the matching response envelope. Existing `responses` handling remains the fallback for unknown models and GPT 5.6 models.

**Tech Stack:** Python 3.12, FastAPI, httpx, Pydantic, pytest.

## Global Constraints

- Do not log API keys, prompts containing profile data, or raw provider responses.
- Preserve the existing safe `WorkoutProviderError` mapping.
- Keep `backend/.env` out of Git.
- Unknown models must retain the existing `/responses` behavior.

---

## File Structure

- Modify `backend/app/ai/opencode_zen.py`: select API style, build both request envelopes, and parse both response envelopes.
- Modify `backend/tests/ai/test_opencode_zen.py`: cover Chat Completions without changing the existing Responses API assertions.
- Modify `docs/workout-plan-generator.md`: document which OpenCode API styles Fitsho supports.

### Task 1: Add Chat Completions provider support

**Files:**
- Modify: `backend/app/ai/opencode_zen.py`
- Test: `backend/tests/ai/test_opencode_zen.py`

**Interfaces:**
- Consumes: `WorkoutGenerationModelRequest` and `WorkoutPlanModelOutput`.
- Produces: `OpenCodeZenWorkoutPlanProvider.generate_plan()` responses for either OpenCode endpoint.

- [ ] **Step 1: Write failing Chat Completions tests**

```python
def test_zen_provider_uses_chat_completions_for_nemotron() -> None:
    provider = _provider(httpx.MockTransport(handler), model="nemotron-3-ultra-free")
    response = _run(provider.generate_plan(_request()))

    assert response.provider_request_id == "chatcmpl_123"
    assert seen["url"] == "https://zen.example/v1/chat/completions"
    assert seen["body"]["response_format"]["type"] == "json_schema"


def test_zen_provider_rejects_chat_completions_without_message_content() -> None:
    provider = _provider(httpx.MockTransport(lambda _: httpx.Response(200, json={"choices": []})), model="nemotron-3-ultra-free")

    with pytest.raises(WorkoutProviderError) as exc_info:
        _run(provider.generate_plan(_request()))

    assert exc_info.value.code is ProviderErrorCode.MALFORMED_RESPONSE
```

- [ ] **Step 2: Run the focused tests to verify they fail**

Run: `cd backend && .venv/bin/pytest tests/ai/test_opencode_zen.py -q`

Expected: the Nemotron URL assertion fails because the provider currently posts to `/responses`.

- [ ] **Step 3: Implement model-to-style selection and Chat Completions handling**

```python
_CHAT_COMPLETIONS_MODELS = frozenset({"nemotron-3-ultra-free"})

def _uses_chat_completions(self) -> bool:
    return self._model in _CHAT_COMPLETIONS_MODELS

def _chat_completions_request_body(self, request: WorkoutGenerationModelRequest) -> dict[str, object]:
    return {
        "model": self._model,
        "messages": [
            {"role": "system", "content": request.system_prompt},
            {"role": "user", "content": json.dumps(request.input_payload, ensure_ascii=False, separators=(",", ":"))},
        ],
        "response_format": {
            "type": "json_schema",
            "json_schema": {"name": "fitsho_workout_plan", "strict": True, "schema": request.response_schema},
        },
    }
```

Set the endpoint to `/chat/completions` only for known compatible models. Extract `id`, token usage, and `choices[0].message.content`; then reuse the existing JSON and Pydantic plan validation. Preserve the existing Responses API body and parser for all other models.

- [ ] **Step 4: Run provider tests to verify they pass**

Run: `cd backend && .venv/bin/pytest tests/ai/test_opencode_zen.py -q`

Expected: PASS.

- [ ] **Step 5: Run static checks**

Run: `cd backend && .venv/bin/ruff check app/ai/opencode_zen.py tests/ai/test_opencode_zen.py && .venv/bin/mypy app/ai/opencode_zen.py`

Expected: both commands exit `0`.

- [ ] **Step 6: Commit the provider change**

```bash
git add backend/app/ai/opencode_zen.py backend/tests/ai/test_opencode_zen.py
git commit -m "feat(ai): support OpenCode chat completions models"
```

### Task 2: Document supported OpenCode API styles

**Files:**
- Modify: `docs/workout-plan-generator.md`

**Interfaces:**
- Consumes: the provider endpoint-selection behavior from Task 1.
- Produces: operator guidance for selecting OpenCode models through `OPENCODE_ZEN_MODEL`.

- [ ] **Step 1: Document endpoint selection**

Add a concise note that GPT 5.6 models use Responses API, known OpenAI-compatible models such as `nemotron-3-ultra-free` use Chat Completions, and unknown models retain Responses API compatibility.

- [ ] **Step 2: Check documentation diff**

Run: `git diff --check -- docs/workout-plan-generator.md`

Expected: exit `0`.

- [ ] **Step 3: Commit the documentation change**

```bash
git add docs/workout-plan-generator.md
git commit -m "docs(ai): describe OpenCode endpoint selection"
```

### Task 3: Verify the configured runtime

**Files:**
- Modify: none

**Interfaces:**
- Consumes: the rebuilt backend image, `backend/.env`, and the existing workout catalog.
- Produces: evidence that Nemotron is configured with Chat Completions support.

- [ ] **Step 1: Rebuild and restart backend without starting a second database**

Run: `docker compose up -d --no-deps --build --force-recreate backend`

Expected: `fitsho-backend-1` starts successfully.

- [ ] **Step 2: Verify configuration without printing the secret**

Run: `docker exec fitsho-backend-1 python -c 'from app.config import get_settings; s = get_settings(); print(s.opencode_zen_model); print(s.opencode_zen_timeout_seconds); print("set" if s.opencode_zen_api_key else "missing")'`

Expected: `nemotron-3-ultra-free`, `300.0`, and `set`.

- [ ] **Step 3: Verify API readiness**

Run: `curl -sS -o /dev/null -w '%{http_code}\n' http://localhost:8000/openapi.json`

Expected: `200`.

- [ ] **Step 4: Confirm generation through the UI**

Open the existing signed-in session and select workout-plan generation once. Inspect the most recent `workout_plan_generations` row after it completes; do not retry automatically because provider usage and cooldown are user-facing state.
