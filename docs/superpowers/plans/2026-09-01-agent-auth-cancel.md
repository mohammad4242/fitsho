# Admin Agent Authentication Cancellation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Let an administrator cancel another active Agent authentication session from the Admin → AI Settings dialog, send `Esc` to PTY-backed CLIs, and close the dialog safely.

**Architecture:** Keep the existing Backend → internal Agent Service boundary. Add an idempotent Agent Service `cancel-active` endpoint backed by an atomic `AuthManager.cancel_active` operation; the manager marks the active session canceled before sending one fixed `Esc` byte and reaping the process. Add a protected backend proxy and render a translated frontend action only when the start request returns `auth_in_progress`.

**Tech Stack:** Python 3.12, asyncio PTY, FastAPI, Pydantic, pytest, React 19, TypeScript, Vitest.

**Spec:** `docs/superpowers/specs/2026-09-01-agent-auth-cancel-design.md`

## Global Constraints

- Keep Browser → Backend → internal Agent Service; the browser never calls port 9001 directly.
- The new operation accepts only a known `AgentName`; no command, PID, URL, token, or arbitrary control byte is accepted.
- Mark the active session canceled under the manager lock before process I/O; a second cancellation returns `{agent, canceled:false}` without error.
- Send `Esc` only to PTY-backed processes, then use the existing SIGTERM/SIGKILL and wait/reap path; pipe-backed agents still terminate safely.
- Preserve existing per-session cancellation, polling, URL allowlists, StrictMode cleanup, auth TTL, and Codex/Claude behavior.
- Do not add raw terminal output, OAuth URLs, authorization codes, credentials, or downstream error text to logs or responses.
- Protect both HTTP layers with their existing internal bearer/admin/trusted-origin checks.
- Stage only files listed in each task and preserve unrelated untracked WIP.

---

### Task 1: Add Agent Service active-cancel lifecycle

**Files:**
- Modify: `agent-service/app/auth/process.py`
- Modify: `agent-service/app/auth/manager.py`
- Modify: `agent-service/app/auth/schemas.py`
- Modify: `agent-service/app/main.py`
- Test: `agent-service/tests/test_process.py`
- Test: `agent-service/tests/auth/test_manager.py`
- Test: `agent-service/tests/auth/test_schemas.py`
- Test: `agent-service/tests/test_auth_api.py`

**Interfaces:**
- Consume the existing `AuthCommand`, `AuthProcess`, `AuthManager`, `AuthStartRequest`, and internal bearer dependency.
- Produce `AuthProcess.press_escape() -> None`, `AuthManager.cancel_active(agent: AgentName) -> bool`, `AuthActiveCancellationResponse(agent: AgentName, canceled: bool)`, and `POST /v1/auth/cancel-active`.

- [ ] **Step 1: Write failing PTY and manager tests**

  Extend the PTY process test child to wait for one byte and print a marker
  only when it receives `\x1b`; call `press_escape()` and assert the marker is
  captured. In the manager tests, start a fake Antigravity PTY process that
  sleeps after printing its handoff, call `cancel_active(AgentName.ANTIGRAVITY)`,
  assert it returns `True`, the session view is `canceled`, the process is no
  longer running, and a second call returns `False`. Add a schema test that
  validates `{agent: "antigravity", canceled: true}` and rejects extra fields.
  Add an API test that starts a PTY session, calls
  `POST /v1/auth/cancel-active`, and asserts the safe response fields.

- [ ] **Step 2: Run the focused tests and verify the expected failure**

  Run from `agent-service/`:

  ```bash
  .venv/bin/pytest -q tests/test_process.py tests/auth/test_manager.py tests/auth/test_schemas.py tests/test_auth_api.py
  ```

  Expected failure: `AuthProcess` has no `press_escape`, `AuthManager` has no
  `cancel_active`, and the new route/response model is absent.

- [ ] **Step 3: Implement the fixed Esc primitive and atomic manager operation**

  Add `press_escape()` beside `press_enter()`; require a running PTY process
  and call `_write_pty(master_fd, b"\x1b")`. Add a private manager helper that
  calls `process.press_escape()` only when `process.command.use_pty`, ignores
  `AuthProcessError` from an already-closed PTY, and always awaits
  `process.terminate()`.

  Implement `cancel_active()` as follows: under `_lock`, resolve
  `self._active[agent]`, return `False` when there is no live session, mark a
  live session `CANCELED`, release the active slot, and capture its process;
  outside the lock, run the helper and return `True`. If the active session is
  already expired, mark it `EXPIRED`, release it, reap its process, and return
  `False`. Reuse the helper in the existing per-session `cancel()` path so all
  PTY cancellations send `Esc` before termination.

  Add `AuthActiveCancellationResponse` to auth schemas and register the static
  route before `/v1/auth/{session_id}`. It validates the agent request with
  `AuthStartRequest`, calls `cancel_active`, and returns only `agent` and
  `canceled`.

- [ ] **Step 4: Run the focused tests and checks**

  Run:

  ```bash
  .venv/bin/pytest -q tests/test_process.py tests/auth/test_manager.py tests/auth/test_schemas.py tests/test_auth_api.py
  .venv/bin/ruff check app/auth/process.py app/auth/manager.py app/auth/schemas.py app/main.py tests/test_process.py tests/auth/test_manager.py tests/auth/test_schemas.py tests/test_auth_api.py
  .venv/bin/mypy app/auth/process.py app/auth/manager.py app/auth/schemas.py app/main.py
  ```

  Expected: all focused tests pass, Ruff is clean, and mypy reports no issues.

- [ ] **Step 5: Commit**

  ```bash
  git add agent-service/app/auth/process.py agent-service/app/auth/manager.py agent-service/app/auth/schemas.py agent-service/app/main.py agent-service/tests/test_process.py agent-service/tests/auth/test_manager.py agent-service/tests/auth/test_schemas.py agent-service/tests/test_auth_api.py
  git commit -m "feat: cancel active agent auth sessions"
  git push origin main
  ```

### Task 2: Add the protected Backend cancellation proxy

**Files:**
- Modify: `backend/app/body_analysis/admin_config/schemas.py`
- Modify: `backend/app/body_analysis/admin_config/service.py`
- Modify: `backend/app/body_analysis/admin_config/router.py`
- Test: `backend/tests/admin/test_agent_service_auth_api.py`

**Interfaces:**
- Consume Agent Service `POST /v1/auth/cancel-active` with `{agent}`.
- Produce `AgentServiceAuthActiveCancellationResponse`,
  `cancel_active_agent_service_auth(...)`, and
  `POST /api/v1/admin/ai/agent-service/auth/cancel-active`.

- [ ] **Step 1: Write the failing backend contract test**

  Extend the existing admin Agent Service mock transport to return
  `{"agent":"codex","canceled":true}` for the new downstream path. Call
  the new route as an unauthenticated user, as a non-admin, without the
  trusted `Origin`, and as an admin with the origin. Assert statuses `401`,
  `403`, `403`, and `200`; assert the successful body contains exactly
  `agent` and `canceled`; assert the mock saw `POST`, the JSON body
  `{"agent":"codex"}`, and the configured bearer token. Add a false response
  test to ensure `{agent, canceled:false}` is passed through without exposing
  downstream fields.

- [ ] **Step 2: Run the backend test and verify it fails**

  Run from `backend/`:

  ```bash
  .venv/bin/pytest -q tests/admin/test_agent_service_auth_api.py -k cancel_active
  ```

  Expected failure: the route, schema, and service function do not exist.

- [ ] **Step 3: Implement the backend schema, service function, and route**

  Define the response model with `extra="forbid"`, `agent: AIAgentName`, and
  `canceled: bool`. In the service module, call `_agent_service_json` with
  method `POST`, path `/v1/auth/cancel-active`, body `{"agent":
  payload.agent.value}`, and `preserve_auth_errors=True`; validate the
  response with the new model and map validation failures through the existing
  malformed-response error. Add the router endpoint beside the other auth
  routes with `require_trusted_origin`, reusing the admin dependency and
  existing error mapping.

- [ ] **Step 4: Run focused backend checks**

  Run:

  ```bash
  .venv/bin/pytest -q tests/admin/test_agent_service_auth_api.py
  .venv/bin/ruff check app/body_analysis/admin_config/schemas.py app/body_analysis/admin_config/service.py app/body_analysis/admin_config/router.py tests/admin/test_agent_service_auth_api.py
  .venv/bin/mypy app/body_analysis/admin_config/schemas.py app/body_analysis/admin_config/service.py app/body_analysis/admin_config/router.py
  ```

  Expected: all focused tests pass with safe response assertions intact.

- [ ] **Step 5: Commit**

  ```bash
  git add backend/app/body_analysis/admin_config/schemas.py backend/app/body_analysis/admin_config/service.py backend/app/body_analysis/admin_config/router.py backend/tests/admin/test_agent_service_auth_api.py
  git commit -m "feat: proxy active agent auth cancellation"
  git push origin main
  ```

### Task 3: Add the Admin UI recovery action

**Files:**
- Modify: `frontend/src/features/admin/api.ts`
- Modify: `frontend/src/features/admin/types.ts`
- Modify: `frontend/src/features/admin/AgentAuthDialog.tsx`
- Modify: `frontend/src/i18n/fa.ts`
- Modify: `frontend/src/i18n/en.ts`
- Test: `frontend/src/features/admin/api.test.ts`
- Test: `frontend/src/features/admin/AgentAuthDialog.test.tsx`

**Interfaces:**
- Consume `ApiError.code === "auth_in_progress"` and the Backend proxy.
- Produce `cancelAdminAiAgentAuthActive(agent: AdminAiAgentName)` and the
  translated `لغو احراز هویت قبلی` action.

- [ ] **Step 1: Write failing frontend API and dialog tests**

  Add an API test that mocks a successful JSON cancellation response and
  asserts `POST /api/v1/admin/ai/agent-service/auth/cancel-active` with
  `{"agent":"codex"}` and credentials included. In the dialog test, reject
  `startAdminAiAgentAuth` with `new ApiError(409, "private", null,
  "auth_in_progress")`, assert the translated in-progress message and the
  new button, click it, assert the active-agent cancellation call, and assert
  `onClose` is called. Keep the existing explicit-current-session cancel test
  unchanged.

- [ ] **Step 2: Run the frontend tests and verify they fail**

  Run from `frontend/`:

  ```bash
  npm run test -- --run src/features/admin/api.test.ts src/features/admin/AgentAuthDialog.test.tsx
  ```

  Expected failure: the API function, translation key, and button do not
  exist.

- [ ] **Step 3: Implement the API and dialog state**

  Add the response type `{ agent: AdminAiAgentName; canceled: boolean }` and
  the API helper using the existing `request` wrapper. In
  `AgentAuthDialog`, keep a separate `startErrorCode` state; set it from
  `ApiError.code` only for the failed start and clear it on a successful
  session. Render the new button when `startErrorCode === "auth_in_progress"`.
  Its handler sets the existing busy cancellation state, calls the helper for
  `agent`, and invokes `onClose()` after any successful response; on failure,
  restore the button and show the existing safe error mapping. Add Persian and
  English labels and a short cancellation-in-progress label. Do not render
  raw `ApiError.message`.

- [ ] **Step 4: Run focused frontend checks**

  Run:

  ```bash
  npm run test -- --run src/features/admin/api.test.ts src/features/admin/AgentAuthDialog.test.tsx
  npm run lint
  ```

  Expected: focused tests pass, the button appears only for
  `auth_in_progress`, and lint is clean.

- [ ] **Step 5: Commit**

  ```bash
  git add frontend/src/features/admin/api.ts frontend/src/features/admin/types.ts frontend/src/features/admin/AgentAuthDialog.tsx frontend/src/i18n/fa.ts frontend/src/i18n/en.ts frontend/src/features/admin/api.test.ts frontend/src/features/admin/AgentAuthDialog.test.tsx
  git commit -m "feat: add admin active auth cancellation action"
  git push origin main
  ```

### Task 4: Full verification and runtime handoff

**Files:**
- Inspect only the staged task diff and runtime configuration.

**Interfaces:**
- Consume the three completed task commits.
- Produce verified images, a live cancellation smoke result, and exact Persian
  test instructions.

- [ ] **Step 1: Run full Agent Service checks**

  From `agent-service/`, run `.venv/bin/pytest -q`, `.venv/bin/ruff check .`,
  and `.venv/bin/mypy app`.

- [ ] **Step 2: Run full Backend and Frontend checks**

  From `backend/`, run `.venv/bin/pytest -q`; from `frontend/`, run
  `npm run test -- --run`, `npm run lint`, and `npm run build`.

- [ ] **Step 3: Rebuild and smoke the deployed services**

  Run `docker compose build agent-service backend`, restart both services with
  `docker compose up -d --no-deps agent-service backend`, wait for Agent
  Service health, then use its bearer-authenticated API to start one isolated
  fake or real auth session and call `POST /v1/auth/cancel-active`. Record only
  status, `canceled`, and whether an `agy` process remains; never print the
  token, URL, code, or session identifier. Verify Backend `/docs` and the
  Agent Service `/healthz` are reachable.

- [ ] **Step 4: Review and deliver**

  Run `git diff --check`, inspect each staged diff, confirm `git status` shows
  only pre-existing unrelated untracked WIP, and verify `git log` matches
  `origin/main`. Report the three commit hashes, test counts, runtime result,
  and the Persian steps: open Admin → AI Settings, choose the Agent, start
  authentication twice, click «لغو احراز هویت قبلی» on the second dialog, and
  confirm the old container auth screen exits and the dialog closes.
