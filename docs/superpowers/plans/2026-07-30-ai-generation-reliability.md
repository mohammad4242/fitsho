# AI Generation Reliability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make model tests production-compatible, normalize deterministic workout fields, persist safe validation diagnostics, and display recent failures to administrators.

**Architecture:** Provider health checks use the production output schema and reject HTTP 200 error envelopes. A dedicated workout normalizer owns exercise ordering while the backend remains authoritative for durations. Validation diagnostics are stored on generation records and exposed through a separate admin-only history endpoint consumed by the AI model page.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy, Alembic, PostgreSQL JSON, pytest, React 19, TypeScript, Vitest

## Global Constraints

- Never log or expose profiles, prompts, full model responses, credentials, or user identity.
- Preserve all safety, equipment, prescription, candidate, balance, duplication, and session-limit validation.
- Preserve unrelated frontend priority-order changes already present in the worktree.
- A successful model test must show the green Persian message `با موفقیت متصل شد`.

---

### Task 1: Production-Compatible Model Health Check

**Files:**
- Modify: `backend/app/admin/ai_models.py`
- Modify: `backend/app/ai/opencode_zen.py`
- Test: `backend/tests/admin/test_ai_model_api.py`
- Test: `backend/tests/ai/test_opencode_zen.py`

**Interfaces:**
- Consumes: `WorkoutPlanModelOutput.model_json_schema()`
- Produces: health request with `{"expected_output":{"days":[]}}`
- Produces: safe provider error for HTTP 200 bodies containing `error`

- [ ] **Step 1: Add failing provider and admin tests**

Add a provider test asserting an HTTP 200 error envelope raises
`ProviderErrorCode.PROVIDER_UNAVAILABLE`. Extend the admin health-check test to inspect
the outgoing request body and assert its JSON schema equals
`WorkoutPlanModelOutput.model_json_schema()` and its input requests an empty days array.

- [ ] **Step 2: Run focused tests and verify RED**

```bash
cd backend
TEST_DATABASE_URL=postgresql+psycopg://fitsho:fitsho@localhost:5432/fitsho_test \
  .venv/bin/pytest \
  tests/ai/test_opencode_zen.py::test_zen_provider_rejects_http_200_error_envelope \
  tests/admin/test_ai_model_api.py::test_admin_can_run_a_model_health_check -q
```

Expected: provider test does not map the envelope and the admin schema assertion fails.

- [ ] **Step 3: Implement the provider and health request**

After parsing a response dictionary, inspect `payload["error"]`. Map an auth-shaped
error to `UNAUTHORIZED`, an invalid-request error to `MALFORMED_RESPONSE`, and all other
error envelopes to `PROVIDER_UNAVAILABLE`.

Replace the ad-hoc health schema with:

```python
request = WorkoutGenerationModelRequest(
    system_prompt='Return exactly {"days":[]}.',
    input_payload={"health_check": True, "expected_output": {"days": []}},
    response_schema=WorkoutPlanModelOutput.model_json_schema(),
)
```

- [ ] **Step 4: Verify Task 1**

```bash
cd backend
TEST_DATABASE_URL=postgresql+psycopg://fitsho:fitsho@localhost:5432/fitsho_test \
  .venv/bin/pytest tests/ai/test_opencode_zen.py tests/admin/test_ai_model_api.py -q
.venv/bin/ruff check app/ai/opencode_zen.py app/admin/ai_models.py \
  tests/ai/test_opencode_zen.py tests/admin/test_ai_model_api.py
```

---

### Task 2: Normalize Workouts and Persist Validation Diagnostics

**Files:**
- Create: `backend/app/workouts/normalizer.py`
- Create: `backend/alembic/versions/20260730_10_add_generation_diagnostics.py`
- Modify: `backend/app/workouts/models.py`
- Modify: `backend/app/workouts/repository.py`
- Modify: `backend/app/workouts/service.py`
- Modify: `backend/app/workouts/validator.py`
- Test: `backend/tests/workouts/test_service.py`
- Test: `backend/tests/workouts/test_validator.py`
- Test: `backend/tests/workouts/test_repository.py`

**Interfaces:**
- Produces: `normalize_workout_plan(plan, candidates) -> WorkoutPlanModelOutput`
- Produces: `WorkoutPlanGeneration.validation_diagnostics`
- Stores entries shaped as `{"model_id": str, "phase": str, "problems": list[dict]}`

- [ ] **Step 1: Add failing normalization, validator, and persistence tests**

Add tests asserting:

- a plan with intentionally wrong model duration estimates is accepted when its sets and
  rests fit the deterministic session budget;
- isolation-before-compound output is normalized to compound-before-isolation;
- failed initial and repair diagnostics are stored on the generation record;
- repository failure persistence retains diagnostic JSON.

- [ ] **Step 2: Run focused tests and verify RED**

```bash
cd backend
TEST_DATABASE_URL=postgresql+psycopg://fitsho:fitsho@localhost:5432/fitsho_test \
  .venv/bin/pytest tests/workouts/test_validator.py tests/workouts/test_service.py \
  tests/workouts/test_repository.py -q
```

Expected: duration/order tests fail and the model lacks `validation_diagnostics`.

- [ ] **Step 3: Implement normalization and storage**

Create `normalize_workout_plan` using `model_copy(update=...)`. Stable-sort each day's
exercises with compound candidates first and preserve relative order otherwise.

Remove only the `duration_mismatch` and `compound_order` rejection blocks from the
validator. Keep `fits_session_duration()` unchanged.

Add a nullable SQLAlchemy `JSON` column and Alembic migration:

```python
validation_diagnostics: Mapped[list[dict[str, object]] | None] = mapped_column(JSON)
```

Thread one request-local diagnostics list through generation. Append each logged initial
or repair problem event and assign it to the generation before success or failure is
committed.

- [ ] **Step 4: Verify migration and Task 2**

```bash
cd backend
.venv/bin/alembic upgrade head
.venv/bin/alembic current
TEST_DATABASE_URL=postgresql+psycopg://fitsho:fitsho@localhost:5432/fitsho_test \
  .venv/bin/pytest tests/workouts -q
.venv/bin/ruff check app/workouts tests/workouts \
  alembic/versions/20260730_10_add_generation_diagnostics.py
.venv/bin/mypy app/workouts
```

---

### Task 3: Admin Failure History and Green Success State

**Files:**
- Modify: `backend/app/admin/ai_models.py`
- Modify: `backend/app/admin/router.py`
- Modify: `backend/app/admin/schemas.py`
- Test: `backend/tests/admin/test_ai_model_api.py`
- Modify: `frontend/src/features/admin/api.ts`
- Modify: `frontend/src/features/admin/types.ts`
- Modify: `frontend/src/features/admin/AdminAiModelsPage.tsx`
- Modify: `frontend/src/features/admin/AdminAiModelsPage.test.tsx`
- Modify: `frontend/src/features/admin/admin.css`
- Modify: `frontend/src/i18n/fa.ts`
- Modify: `frontend/src/i18n/en.ts`

**Interfaces:**
- Produces: `GET /api/v1/admin/ai-generation-failures?limit=20`
- Produces: `AdminAiGenerationFailure[]`
- Consumes: failure history in `AdminAiModelsPage`

- [ ] **Step 1: Add failing admin API and frontend tests**

Backend tests must assert admin authorization, newest-first failed records, semantic
diagnostic fields, and absence of `user_id` and profile data.

Frontend tests must assert:

- successful model test renders `با موفقیت متصل شد` inside
  `.admin-status--success`;
- failed model test uses an error state;
- recent generation failures render model, phase, code, day, and exercise ID.

- [ ] **Step 2: Run focused tests and verify RED**

```bash
cd backend
TEST_DATABASE_URL=postgresql+psycopg://fitsho:fitsho@localhost:5432/fitsho_test \
  .venv/bin/pytest tests/admin/test_ai_model_api.py -q
cd ../frontend
npm run test -- src/features/admin/AdminAiModelsPage.test.tsx
```

Expected: endpoint, API client, failure history, and message tone do not exist.

- [ ] **Step 3: Implement admin API and UI**

Add Pydantic response models for validation problems, diagnostics, and generation
failures. Query only failed generations, order by `created_at DESC`, and cap `limit`
between 1 and 100. Never serialize `user_id`.

Load models and failure history together in the admin page. Render a responsive recent
failures section. Replace the plain message string with:

```ts
type Feedback = { text: string; tone: "success" | "error" };
```

Use `.admin-status--success` only when `result.success` is true and show the exact Persian
success text `با موفقیت متصل شد`.

- [ ] **Step 4: Run full verification**

```bash
cd backend
.venv/bin/ruff check
.venv/bin/mypy app/workouts app/admin app/ai
TEST_DATABASE_URL=postgresql+psycopg://fitsho:fitsho@localhost:5432/fitsho_test \
  .venv/bin/pytest -q
cd ../frontend
npm run lint
npm run test
npm run build
```

- [ ] **Step 5: Restart live preview and verify routes**

```bash
docker restart fitsho-ai-model-admin-preview
curl -sS -o /dev/null -w '%{http_code}\n' http://localhost:8000/api/v1/auth/me
curl -sS -o /dev/null -w '%{http_code}\n' http://localhost:5173/admin/ai-models
```

Expected: backend returns 401 without a session and frontend returns 200.

- [ ] **Step 6: Prepare commit**

Proposed commit:

```text
fix(ai): improve model checks and generation diagnostics
```

Stage only files listed in this plan. Do not commit until the required user approval is
recorded.
