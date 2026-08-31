# Agent Model Profiles and Task Smoke Tests Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Agent Service model/reasoning profiles selectable in Admin AI Settings only after the selected profile passes a real, task-specific end-to-end smoke test for workout generation, body-photo analysis, food-photo estimation, or food-price web search.

**Architecture:** Agent Service owns a bounded profile catalog and resolves stable profile IDs to allow-listed runner arguments. Backend owns task configuration and durable verification records, builds the same provider requests and validators used by production, and exposes only safe smoke-test status. Frontend presents candidate and active profiles, invokes the task smoke endpoint, and persists only profiles that are currently verified for the selected task.

**Tech Stack:** Python 3.12, FastAPI, Pydantic, SQLAlchemy/Alembic, pytest, React 19, TypeScript, Vitest, Docker Compose.

**Spec:** `docs/superpowers/specs/2026-09-01-agent-model-profiles-and-task-smoke-tests-design.md`

## Global Constraints

- Only catalog profile IDs cross the public Admin API; arbitrary model IDs, effort values, CLI flags, prompts, and shell commands are rejected.
- A profile is active for one task only after that exact profile passes that task's smoke test; stale fingerprints are not eligible for save.
- Agent Service remains internal-only on port 9001; the browser talks only to Backend.
- Smoke fixtures are synthetic and packaged; smoke tests never read user photos, profiles, prompts, credentials, stdout, or stderr into persisted records or responses.
- Keep existing `agent_model_id` as a compatibility field, but new Agent Service selections use `agent_profile_id` and resolve through the profile catalog.
- Preserve existing API/OpenRouter behavior and unrelated worktree files.
- Use TDD: each production behavior starts with a failing focused test, then minimal implementation and a green regression run.

---

### Task 1: Agent Service profile catalog and stable runner resolution

**Files:**
- Create: `agent-service/app/profiles.py`
- Modify: `agent-service/app/schemas.py`
- Modify: `agent-service/app/config.py`
- Modify: `agent-service/app/runners/base.py`
- Modify: `agent-service/app/runners/antigravity.py`
- Modify: `agent-service/app/runners/codex.py`
- Modify: `agent-service/app/runners/claude.py`
- Modify: `agent-service/app/runners/registry.py`
- Modify: `agent-service/app/service.py`
- Modify: `agent-service/app/main.py`
- Test: `agent-service/tests/test_profiles.py`
- Test: `agent-service/tests/runners/test_antigravity.py`
- Test: `agent-service/tests/runners/test_codex.py`
- Test: `agent-service/tests/runners/test_claude.py`
- Test: `agent-service/tests/test_capabilities.py`

**Interfaces:**
- `AgentTaskKind`: `workout_plan_generation`, `body_photo_analysis`, `food_photo_estimation`, `food_price_search`.
- `ReasoningEffort`: `low`, `medium`, `high`, `thinking`.
- `AgentModelProfile`: frozen Pydantic model with `profile_id`, `agent`, `display_name`, `model_id`, `effort`, `task_kinds`, `fingerprint`, and capability booleans.
- `ProfileCatalog.profiles(agent: AgentName | None = None) -> tuple[AgentModelProfile, ...]`.
- `ProfileCatalog.resolve(agent: AgentName, profile_id: str) -> ResolvedProfile` where `ResolvedProfile` contains the exact allow-listed model ID and optional runner effort.
- `RunnerRequest` gains `effort: str | None` and no public request can construct it from an arbitrary value.
- `RunnerCapabilities` gains `profiles: list[AgentModelProfile]`; retain `models` as a compatibility projection.

- [ ] **Step 1: Write failing profile and command tests.**

  Add tests that prove:

  ```python
  def test_antigravity_catalog_parses_only_bounded_model_rows(): ...
  def test_profile_id_is_stable_and_contains_model_effort(): ...
  def test_codex_profile_maps_effort_to_exact_config_override(): ...
  def test_claude_thinking_profile_maps_to_supported_effort_flag(): ...
  def test_unknown_profile_id_is_rejected_before_runner_execution(): ...
  def test_capabilities_expose_candidates_and_compatibility_models(): ...
  ```

  Use fake process results for discovery and command construction; assert no user-supplied shell text is interpolated. Run:

  ```bash
  cd agent-service && pytest tests/test_profiles.py tests/runners/test_antigravity.py tests/runners/test_codex.py tests/runners/test_claude.py tests/test_capabilities.py -q
  ```

  Expected: FAIL because profiles, effort mapping, and capability fields do not exist yet.

- [ ] **Step 2: Implement the bounded catalog.**

  Parse only the installed `agy models` table rows matching a strict model-ID pattern. Map each parsed Antigravity ID to a stable profile ID such as `antigravity-gemini-3.7-flash-high`; derive labels from the parsed row and keep model IDs unchanged. Add bounded default Codex policy profiles for `gpt-5.6-sol`, `gpt-5.6-terra`, and `gpt-5.6-luna` with low/medium/high effort. Add Claude aliases only from the verified installed aliases and map `thinking` profiles to the exact supported `--effort` argument. A profile fingerprint must hash the runner version plus the serialized mapping and task capability set.

- [ ] **Step 3: Resolve profiles inside each runner.**

  Change generation/test requests to carry a resolved profile, not arbitrary model/effort input. Antigravity uses the discovered model ID (its high/medium/low suffix is the model's actual mapping). Codex uses `-c model_reasoning_effort=\"<low|medium|high>\"`; keep the model in `-m`. Claude uses `--effort <low|medium|high>` only for effort profiles and keeps `--model` allow-listed. Preserve existing image and structured-output gates.

- [ ] **Step 4: Expose profile candidates through capabilities and reject mismatches.**

  Make `RunnerRegistry` own one `ProfileCatalog`, include profiles in `/v1/capabilities`, and make `AgentService.test`, `generate`, and `analyze_images` resolve `profile_id` before `_check_capability`. Keep a compatibility path for old internal clients that send a model ID only while the Backend migration is rolled out; it must resolve only an exact catalog model with one unambiguous profile.

- [ ] **Step 5: Run focused tests and commit.**

  Run the focused command again, then `cd agent-service && pytest -q`. Proposed commit:

  ```text
  feat(agent-service): expose verified model reasoning profiles
  ```

### Task 2: Agent Service task-specific smoke contract

**Files:**
- Modify: `agent-service/app/schemas.py`
- Modify: `agent-service/app/service.py`
- Modify: `agent-service/app/main.py`
- Modify: `agent-service/app/workspace.py`
- Test: `agent-service/tests/test_task_smoke.py`
- Test: `agent-service/tests/test_generate_api.py`
- Test: `agent-service/tests/test_image_api.py`

**Interfaces:**
- `TaskSmokeKind` mirrors `AgentTaskKind`.
- `TaskSmokeRequest`: `agent`, `profile_id`, `task_kind`, and the already validated task payload; no arbitrary prompt or executable fields.
- `TaskSmokeResponse`: `ok`, `agent`, `profile_id`, `task_kind`, `request_id`, `stage`, `duration_seconds`, `error_code`, and `safe_error_message`.
- `POST /v1/task-smoke` executes the resolved profile using the same `/v1/generate` or multipart image path and returns safe stage names only.

- [ ] **Step 1: Add failing endpoint and safety tests.**

  Cover all four task kinds, profile/task capability mismatch, image count/size limits, schema rejection, model mismatch, timeout, and safe error redaction. Assert the response never contains prompt text, model output, URLs, credentials, stdout, or stderr. Run:

  ```bash
  cd agent-service && pytest tests/test_task_smoke.py tests/test_generate_api.py tests/test_image_api.py -q
  ```

- [ ] **Step 2: Implement the internal smoke endpoint.**

  Reuse `AgentService.generate` and `AgentService.analyze_images` after the profile resolver. For task smoke, use only request payloads produced by Backend and enforce the task's profile capability before starting a runner. Clean the request workspace in every success and failure path.

- [ ] **Step 3: Verify and commit.**

  Run `cd agent-service && pytest -q`. Proposed commit:

  ```text
  feat(agent-service): add safe task smoke execution contract
  ```

### Task 3: Backend verification persistence and profile-aware configuration

**Files:**
- Create: `backend/alembic/versions/20260901_115_agent_profile_verification.py`
- Modify: `backend/app/body_analysis/admin_config/models.py`
- Modify: `backend/app/body_analysis/admin_config/schemas.py`
- Modify: `backend/app/body_analysis/admin_config/service.py`
- Modify: `backend/app/body_analysis/admin_config/router.py`
- Modify: `backend/app/body_analysis/providers/agent_service.py`
- Modify: `backend/app/ai/task_provider.py`
- Test: `backend/tests/admin/test_ai_task_settings_api.py`
- Test: `backend/tests/ai/test_agent_service_admin_contract.py`
- Test: `backend/tests/ai/test_agent_service_provider.py`
- Test: `backend/tests/database/test_ai_models.py`

**Interfaces:**
- `AITaskConfig.agent_profile_id: str | None`.
- `AIAgentProfileVerification`: UUID, `profile_id`, `task_type`, `profile_fingerprint`, `status`, `checked_at`, `duration_seconds`, `error_code`, and `safe_error_message`, with a unique `(profile_id, task_type)` constraint.
- `AgentProfileSummary`: profile fields plus `verification_status`, `verified_at`, and `stale`.
- `AgentServiceCapabilitiesResponse` includes runner profiles and Backend-enriched verification status.
- `AgentServiceTaskSmokeRequest`: `task_type`, `agent`, `profile_id`.
- `AgentServiceTaskSmokeResponse`: safe stages and verification result only.
- `test_agent_service_task(...)` performs the Backend task harness and upserts one verification row without changing user/task data.

- [ ] **Step 1: Write failing migration/model/schema tests.**

  Prove the new column and table migrate, uniqueness is enforced, stale fingerprints are not active, and response schemas reject arbitrary model IDs/effort fields. Run:

  ```bash
  cd backend && pytest tests/database/test_ai_models.py tests/admin/test_ai_task_settings_api.py tests/ai/test_agent_service_admin_contract.py -q
  ```

  Expected: FAIL because no profile ID, verification table, or task-smoke route exists.

- [ ] **Step 2: Add migration and persistence models.**

  Use the current head `20260831_114` as `down_revision`. Add nullable `agent_profile_id` to `ai_task_configs`. Create the verification table with enum/string task values, safe status/error fields, timestamps, duration, fingerprint, and unique profile/task key. The downgrade drops only this new table and column.

- [ ] **Step 3: Add profile-aware save rules.**

  Return candidate profiles from Agent Service capabilities and match them by `agent` and `profile_id`. When enabling an Agent Service task, require `agent_profile_id`, a matching current fingerprint, and `status == passed`; reject stale/failed/unverified profiles with 422. Populate `agent_model_id` from the resolved profile for compatibility. Existing saved raw model IDs may be read during migration but cannot activate a new task.

- [ ] **Step 4: Extend Backend Agent Service provider routing.**

  Send `profile_id` on generation and image requests while retaining the resolved model ID in response identity checks. Ensure body analysis and food photo requests still use multipart image inputs and workout/price requests use structured text. Map all new safe errors to the existing `ProviderErrorCode` set without exposing runner details.

- [ ] **Step 5: Run migration and focused tests, then commit.**

  Run `cd backend && uv run alembic upgrade head`, the focused tests, and `uv run ruff check app tests`. Proposed commit:

  ```text
  feat(backend): persist task-scoped agent profile verification
  ```

### Task 4: Backend real task smoke harness

**Files:**
- Create: `backend/app/body_analysis/admin_config/task_smoke.py`
- Create: `backend/tests/admin/test_ai_task_smoke.py`
- Modify: `backend/app/body_analysis/admin_config/service.py`
- Modify: `backend/app/body_analysis/admin_config/router.py`
- Modify: `backend/app/body_analysis/providers/agent_service.py`
- Modify: `backend/app/workouts/prompt_builder.py`
- Modify: `backend/app/workouts/validator.py`
- Modify: `backend/app/body_analysis/service.py`
- Modify: `backend/app/nutrition/food_photo_service.py`

**Interfaces:**
- `SmokeFixtureRevision = "agent-task-fixtures-v1"`.
- `TaskSmokeResult`: `passed`, `stage`, `duration_seconds`, `request_id`, `error_code`, `safe_error_message`.
- `run_task_smoke(db, task_type, agent, profile_id, settings, agent_client, fixture_root) -> TaskSmokeResult`.
- `build_smoke_request(task_type, profile_id, ...)` uses the same production prompt/schema builders and returns a provider request plus optional synthetic `ImageInput` values.

- [ ] **Step 1: Write failing harness tests with deterministic fake provider.**

  Add one test per task. Assert:

  - workout uses `build_workout_generation_model_request`, returns a candidate ID, and passes `WorkoutPlanValidator` against the synthetic candidate set;
  - body analysis uses the existing conservative body-analysis schema/normalizer and two synthetic front/back images, without a `BodyAnalysis` row;
  - food photo uses `FoodPhotoOutput` and existing validation/mapping logic without `NutritionFoodPhotoEstimate` persistence;
  - food price search uses the fixed Persian grocery query and validates a structured observation list without calling marketplace persistence;
  - fake provider failures create a failed verification record with only safe error fields;
  - repeated tests replace the same `(profile_id, task_type)` row and a changed fixture revision/fingerprint is stale.

  Run:

  ```bash
  cd backend && pytest tests/admin/test_ai_task_smoke.py -q
  ```

  Expected: FAIL because the harness and route are missing.

- [ ] **Step 2: Add synthetic fixtures without user data.**

  Generate deterministic small RGB JPEGs in the test fixture module (solid neutral-gray background with labelled front/back/meal geometry) using Pillow at test time; do not read `bodyanalysis.jpg`, `foodanalysis.jpg`, or any untracked user asset. Keep the fixed query Persian and non-personal, for example `قیمت برنج ایرانی یک کیلویی در تهران`.

- [ ] **Step 3: Implement the shared harness.**

  Select the configured task, resolve the current profile, build the exact production request/schema, and call the Agent Service task-smoke endpoint. Validate the returned payload with the same Pydantic and semantic validators used in production. Use an isolated fixture root, bounded timeouts, and no database writes except the verification row. For prices, validate source/product/price/currency/observed-at fields and treat “no quote” as a safe semantic failure rather than a pass.

- [ ] **Step 4: Add the admin endpoint and safe persistence.**

  `POST /api/v1/admin/ai/agent-service/task-smoke` accepts only `task_type`, `agent`, and `profile_id`. It returns stage transitions (`backend_request`, `agent_service`, `runner`, `schema`, `semantic_validation`, `passed`/`failed`) and upserts verification status in a transaction. Do not commit user rows, images, model payloads, or raw errors.

- [ ] **Step 5: Run backend checks and commit.**

  Run the focused smoke tests, all AI/admin tests, `uv run ruff check`, and `uv run mypy`. Proposed commit:

  ```text
  feat(backend): verify agent profiles with real task smoke tests
  ```

### Task 5: Frontend profile selection and task test UX

**Files:**
- Modify: `frontend/src/features/admin/types.ts`
- Modify: `frontend/src/features/admin/api.ts`
- Modify: `frontend/src/features/admin/AdminAiSettingsPage.tsx`
- Modify: `frontend/src/features/admin/AgentServicePanel.tsx`
- Modify: `frontend/src/features/admin/AiModelSelector.tsx`
- Modify: `frontend/src/features/admin/admin.css`
- Modify: `frontend/src/i18n/fa.ts`
- Modify: `frontend/src/i18n/en.ts`
- Test: `frontend/src/features/admin/AgentServicePanel.test.tsx`
- Test: `frontend/src/features/admin/AdminAiSettingsPage.test.tsx`

**Interfaces:**
- `AdminAiAgentModelProfile`: profile ID, agent, display/model/effort labels, model ID, fingerprint, task kinds, capability flags, verification status, verified time, stale.
- `AdminAiAgentServiceTaskSmokeRequest` and `AdminAiAgentServiceTaskSmoke` mirror the safe Backend contract.
- `testAdminAiAgentServiceTask(input) -> Promise<AdminAiAgentServiceTaskSmoke>`.

- [ ] **Step 1: Write failing UI/API tests.**

  Test that Antigravity displays Gemini Flash/Pro and Claude profiles with one readable model+effort label, Codex displays Luna/Terra/Sol effort variants, unverified profiles are testable but not saveable, only passed profiles become active, image tasks filter out profiles lacking image support, and the test button displays stage/status feedback. Test `food_price_search` appears as an Agent Service task. Run:

  ```bash
  cd frontend && npm run test -- src/features/admin/AgentServicePanel.test.tsx src/features/admin/AdminAiSettingsPage.test.tsx
  ```

  Expected: FAIL because profile fields, task-smoke API, and task tab behavior are missing.

- [ ] **Step 2: Implement API/types and task wiring.**

  Add `agent_profile_id` to config/update types, add profile/status fields to capabilities, add the task-smoke request function, and include `food_price_search` in the Agent Service-supported task list. Keep candidate profiles visible with a “needs verification” state; save uses only a passed, non-stale profile ID.

- [ ] **Step 3: Implement selection and progress UI.**

  Replace raw model selection for Agent Service with profile selection. Show agent auth state, profile model and effort, candidate versus active status, last verification time, and safe failure. The selected-agent test calls the task-specific endpoint, disables during an operation, selects the profile after a pass, and never displays response payloads or raw errors.

- [ ] **Step 4: Run frontend checks and commit.**

  Run the focused tests, `npm run lint`, and `npm run build`. Proposed commit:

  ```text
  feat(frontend): add verified agent profile task testing
  ```

### Task 6: Runtime configuration, live acceptance, and release verification

**Files:**
- Modify: `.env.example`
- Modify: `docker-compose.yml`
- Modify: `agent-service/Dockerfile`
- Modify: `backend/Dockerfile`
- Modify: `frontend/src/i18n/fa.ts`
- Create: `docs/superpowers/reports/2026-09-01-agent-profile-live-verification.md`

- [ ] **Step 1: Configure bounded catalog discovery.**

  Keep secrets out of Git. Configure the Agent Service to discover Antigravity models at runtime, enable only image capability flags that pass real image smoke tests, and keep Codex/Claude profiles candidate-only until authenticated task tests pass. Do not mark a model active from `--help`, `/health`, or `/capabilities` alone.

- [ ] **Step 2: Run complete automated verification.**

  Run:

  ```bash
  cd agent-service && pytest -q && ruff check . && mypy .
  cd ../backend && uv run alembic upgrade head && uv run pytest -q && uv run ruff check app tests && uv run mypy
  cd ../frontend && npm run test && npm run lint && npm run build
  ```

  Fix only regressions caused by this feature; preserve unrelated WIP.

- [ ] **Step 3: Build, deploy, and inspect runtime.**

  Build the changed Agent Service/Backend/Frontend images with Docker Compose, inspect the final container environment and logs, verify internal-only Agent Service networking, and call the authenticated Backend admin capabilities endpoint. Confirm no secrets or raw model output appear in logs.

- [ ] **Step 4: Execute live task smoke tests with safe fixtures.**

  For each authenticated runner/profile that is actually available, run the four task tests where capability permits. Record exact pass/fail, profile ID, fingerprint, stage, duration, and safe error code in the release report. Do not call a profile active unless its task-specific verification is `passed`; report Claude or any other unavailable profile as candidate/failed honestly.

- [ ] **Step 5: Commit and push each verified release step.**

  Proposed final commit:

  ```text
  chore(agent-service): deploy verified task profile catalog
  ```

  Push the current branch only after the focused and full checks pass. Final handoff must include the exact Admin UI test path and the live verification table.

## Plan self-review

- Spec coverage: catalog discovery and fingerprints (Task 1), safe task endpoint (Task 2), Backend persistence/staleness (Task 3), all four real task harnesses (Task 4), Admin UX (Task 5), runtime/live evidence (Task 6).
- Placeholder scan: no deferred or vague implementation step is used; every task has concrete files, interfaces, tests, and commands.
- Type consistency: `profile_id`, `task_type`, `fingerprint`, `TaskSmokeResult`, and verification statuses are defined before their consumers; Frontend mirrors the Backend contract.
