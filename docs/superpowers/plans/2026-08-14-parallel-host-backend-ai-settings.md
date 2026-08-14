# Parallel Host Backend and AI Settings Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Run an isolated local Fitsho frontend/database pair with a host-native backend that can reach OpenRouter, while restoring clear masked-key and mobile AI-settings behavior.

**Architecture:** A dedicated Compose project owns a PostgreSQL clone on `5433` and Vite on `5174`; Vite proxies to the host backend on `8002` through `host.docker.internal`. A checked-in launcher gives the host backend non-secret runtime overrides while `backend/.env` remains the source of local secrets and proxy configuration.

**Tech Stack:** Docker Compose, PostgreSQL 18, FastAPI/Uvicorn, React 19, TypeScript, Vite, Vitest, Bash

## Global Constraints

- Keep the current frontend `5173`, backend `8001`, and PostgreSQL `5432` stack running unchanged.
- Never commit `.env`, API credentials, encryption keys, database dumps, or private body photos.
- Use a separate named volume for the cloned PostgreSQL database.
- Preserve the Vite proxy default of `http://localhost:8001` when no override is supplied.
- Preserve encrypted credential storage; expose only an ASCII mask such as `********1f4e`.
- Preserve all unrelated working-tree files, including the existing modified `compose.yaml`.
- Do not add Xray or another proxy service to Compose.

---

### Task 1: Configurable Vite proxy and parallel Compose stack

**Files:**
- Create: `frontend/Dockerfile.dev`
- Create: `compose.host-backend.yaml`
- Modify: `frontend/vite.config.ts`
- Test: `frontend/src/test/viteProxyConfig.test.ts`

**Interfaces:**
- Consumes: `VITE_API_PROXY_TARGET` from the frontend process environment.
- Produces: `resolveApiProxyTarget(value?: string): string`, frontend port `5174`, and database port `5433`.

- [ ] **Step 1: Write the failing proxy-target test**

Test that `resolveApiProxyTarget(undefined)` returns `http://localhost:8001` and that an explicit `http://host.docker.internal:8002` value is retained.

- [ ] **Step 2: Run the focused test and verify RED**

Run: `npm run test -- --run src/test/viteProxyConfig.test.ts`

Expected: FAIL because `resolveApiProxyTarget` is not exported.

- [ ] **Step 3: Implement the configurable target and isolated containers**

Export the pure resolver from `vite.config.ts` and use it for both `/api` and `/media`. Add a Node development image that installs the locked frontend dependencies. Add `hostdev-db` and `hostdev-frontend` services to the dedicated Compose file, including `host.docker.internal:host-gateway`, separate named volumes, health checks, and only ports `5433` and `5174`.

- [ ] **Step 4: Verify the focused test and rendered Compose configuration**

Run: `npm run test -- --run src/test/viteProxyConfig.test.ts`

Run: `docker compose -p fitsho-hostdev -f compose.host-backend.yaml config`

Expected: PASS; the rendered configuration contains no backend service and no host ports from the current stack.

- [ ] **Step 5: Commit**

Commit message: `feat(dev): add parallel host-backend stack`

### Task 2: Host backend launcher and safe database clone

**Files:**
- Create: `scripts/run-host-backend.sh`
- Create: `scripts/clone-hostdev-database.sh`
- Create: `scripts/test_hostdev_scripts.sh`

**Interfaces:**
- Consumes: existing `backend/.env`, source Compose service `db`, destination project `fitsho-hostdev`, and optional `FITSHO_HOSTDEV_LAN_IP`.
- Produces: host backend URL `http://0.0.0.0:8002` and an independently cloned database at `localhost:5433`.

- [ ] **Step 1: Write failing shell contract checks**

The test script must assert that the launcher sets database port `5433`, backend port `8002`, cookie settings for local HTTP, and frontend origins on `5174`; it must also assert that the clone script names only the dedicated destination database and never writes a dump outside the workspace.

- [ ] **Step 2: Run the contract test and verify RED**

Run: `bash scripts/test_hostdev_scripts.sh`

Expected: FAIL because the launch and clone scripts do not exist.

- [ ] **Step 3: Implement both scripts**

The launcher changes into `backend/`, derives a LAN IPv4 unless overridden, exports only non-secret hostdev settings, and executes `uv run uvicorn app.main:app --host 0.0.0.0 --port 8002`. The clone script starts the dedicated database, waits for health, performs a read-only `pg_dump` from the current `db` service, and restores through stdin to the dedicated `fitsho` database without persisting dump contents.

- [ ] **Step 4: Verify scripts without mutating either database**

Run: `bash scripts/test_hostdev_scripts.sh`

Run: `bash -n scripts/run-host-backend.sh scripts/clone-hostdev-database.sh`

Expected: all checks PASS.

- [ ] **Step 5: Commit**

Commit message: `feat(dev): add host backend and database clone scripts`

### Task 3: Credential mask and local operation feedback

**Files:**
- Modify: `backend/app/body_analysis/admin_config/service.py`
- Modify: `backend/tests/admin/test_ai_task_settings_api.py`
- Modify: `frontend/src/features/admin/AdminAiSettingsPage.tsx`
- Modify: `frontend/src/features/admin/AdminAiSettingsPage.test.tsx`

**Interfaces:**
- Consumes: `AdminAiTaskConfig.credential.masked` and `ApiError.message`.
- Produces: ASCII credential masks and feedback associated with `save`, `test`, or `refresh`.

- [ ] **Step 1: Write failing backend and frontend tests**

Assert that the backend returns `********cret`, that the mask is the API-key input placeholder, that a connection-test result is rendered inside the provider panel, and that a refresh `ApiError` displays its safe response message beside the refresh controls.

- [ ] **Step 2: Run focused tests and verify RED**

Run: `uv run pytest tests/admin/test_ai_task_settings_api.py -q`

Run: `npm run test -- --run src/features/admin/AdminAiSettingsPage.test.tsx`

Expected: FAIL on Unicode masking and feedback placement/error detail.

- [ ] **Step 3: Implement the minimal UI and service changes**

Change only the mask representation, give the password input an explicit visible text color and opaque ASCII placeholder, track which operation owns the current feedback, display provider-operation feedback in the first card, and use `ApiError.message` when it is safe and available.

- [ ] **Step 4: Verify GREEN**

Run both focused commands from Step 2.

Expected: all focused tests PASS.

- [ ] **Step 5: Commit**

Commit message: `fix(ai-settings): restore visible credential feedback`

### Task 4: Mobile containment

**Files:**
- Modify: `frontend/src/features/admin/admin.css`
- Modify: `frontend/src/features/admin/AdminAiSettingsPage.test.tsx`

**Interfaces:**
- Consumes: existing `admin-main--ai-settings` DOM structure.
- Produces: `admin-ai-provider-feedback` and mobile-safe card/grid/action layout hooks.

- [ ] **Step 1: Add failing structural regression assertions**

Assert the provider feedback has its dedicated class and the form sections retain the AI-settings containment classes used by the responsive stylesheet.

- [ ] **Step 2: Run the focused test and verify RED**

Run: `npm run test -- --run src/features/admin/AdminAiSettingsPage.test.tsx`

Expected: FAIL because the dedicated mobile feedback hook is absent.

- [ ] **Step 3: Add responsive containment rules**

Set `min-width: 0` on the AI main/form/panels/fields/model selectors, constrain long content with wrapping, collapse observability rows to one column below `760px`, make task tabs and actions fit the viewport, and keep all inputs/selectors at `max-width: 100%`.

- [ ] **Step 4: Verify tests, lint, and build**

Run: `npm run test -- --run src/features/admin/AdminAiSettingsPage.test.tsx`

Run: `npm run lint`

Run: `npm run build`

Expected: all commands PASS.

- [ ] **Step 5: Commit**

Commit message: `fix(ai-settings): contain mobile settings layout`

### Task 5: Parallel runtime, real provider verification, and handoff

**Files:**
- Modify only if runtime evidence exposes a tested defect in Tasks 1–4.

**Interfaces:**
- Consumes: scripts and Compose file from Tasks 1–2.
- Produces: a phone-accessible application at `http://<LAN-IP>:5174` using host backend `8002` and cloned database `5433`.

- [ ] **Step 1: Start and clone the isolated database**

Run: `docker compose -p fitsho-hostdev -f compose.host-backend.yaml up -d hostdev-db`

Run: `scripts/clone-hostdev-database.sh`

Expected: source database remains healthy; destination migration head and representative row counts match.

- [ ] **Step 2: Start the host backend and container frontend**

Run the backend launcher in a persistent PTY, then run the parallel frontend service in the dedicated Compose project.

Expected: `8002/openapi.json` and `5174` return HTTP 200; the existing `8001` and `5173` endpoints still return HTTP 200.

- [ ] **Step 3: Verify real OpenRouter connectivity and catalog refresh**

Using the stored encrypted key from the cloned database, invoke the provider connection service and catalog refresh through the host runtime. Print only status, model count, and timestamps; never print the key.

Expected: connection succeeds and the catalog contains current models, including image-input models used by Body Analysis.

- [ ] **Step 4: Run complete relevant checks**

Run: `uv run pytest tests/body_analysis -q`

Run: `ruff check app/body_analysis tests/body_analysis`

Run: `mypy app`

Run: `npm run test -- --run`

Run: `npm run lint`

Run: `npm run build`

Expected: all commands PASS, excluding only explicitly documented live-provider skips.

- [ ] **Step 5: Push and verify the remote**

Run: `git push origin main`

Confirm `git ls-remote origin refs/heads/main` equals local `HEAD` and report unrelated working-tree files as untouched.
