# Agent Authentication Link Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make the Antigravity auth button show the real `agy` browser URL through the existing secure Backend → Agent Service path, without exposing a terminal.

**Architecture:** Add a standard-library PTY mode to the existing in-memory auth process, enable it only for the Antigravity adapter, and parse the bounded ANSI-cleaned stream into the existing safe auth session contract. Add a capability flag so the admin panel represents browser-link auth correctly while preserving Codex/Claude behavior.

**Tech Stack:** Python 3.12, asyncio, `pty`/`termios`, FastAPI, Pydantic, pytest, React 19, TypeScript, Vitest.

**Spec:** `docs/superpowers/specs/2026-08-31-agent-auth-link-design.md`

## Global Constraints

- Keep Browser → Backend → internal Agent Service; the browser never calls port 9001 directly.
- Do not send or persist CLI credentials, tokens, raw stdout/stderr, or raw prompts.
- Use only fixed known agent commands; no shell command, `shell=True`, arbitrary executable, or user-controlled URL.
- Keep auth sessions in memory with bounded output and the existing 600-second TTL.
- Preserve the persistent `/home/agent` volume and all Codex/Claude auth behavior.
- Allow only HTTPS URLs with the exact Google OAuth hostname for Antigravity.
- Stage only task files; preserve the repository’s existing untracked WIP.

---

### Task 1: Add failing PTY process tests

**Files:**
- Modify: `agent-service/tests/auth/test_process.py`
- Modify: `agent-service/tests/auth/test_manager.py`

**Interfaces:**
- Consume the current `AuthCommand(use_pty=True)`, `AuthProcess`, and `AuthManager` interfaces.
- Produce executable regression cases for PTY output, input, termination, and fake Antigravity URL handoff.

- [ ] **Step 1: Write tests**

  Add a fake executable test that emits a URL through a PTY, accepts a code on
  the PTY, emits an authenticated marker, and assert that the manager exposes
  `WAITING_FOR_USER`, accepts input only after `WAITING_FOR_INPUT`, and ends
  authenticated. Add termination coverage asserting the child process is not
  running after cancellation/expiry.

- [ ] **Step 2: Run the focused tests and verify they fail**

  Run `uv run pytest -q tests/auth/test_process.py tests/auth/test_manager.py`.
  Expected: the PTY test fails because `AuthProcess` currently rejects PTY
  commands.

- [ ] **Step 3: Commit the failing-test checkpoint**

  Run `git add agent-service/tests/auth/test_process.py agent-service/tests/auth/test_manager.py` then `git commit -m "test: define Antigravity PTY auth lifecycle"`.

### Task 2: Implement safe PTY process infrastructure

**Files:**
- Modify: `agent-service/app/auth/process.py`
- Test: `agent-service/tests/auth/test_process.py`
- Test: `agent-service/tests/auth/test_manager.py`

**Interfaces:**
- Consume `AuthCommand`, `AuthOutputCallback`, and `AuthProcessResult`.
- Produce `AuthProcess.start`, `send_input`, `wait`, and `terminate` behavior for both pipe and PTY modes.

- [ ] **Step 1: Implement PTY start**

  Use `pty.openpty()` and `asyncio.create_subprocess_exec` with the slave fd
  attached to stdin/stdout/stderr, `start_new_session=True`, and no shell. Keep
  the master fd in the parent, set it non-blocking for reads, and close the
  slave fd after spawn. Preserve the existing pipe path unchanged.

- [ ] **Step 2: Implement bounded PTY monitoring and input**

  Read the master fd asynchronously, treat PTY `EIO` as EOF, feed only accepted
  bytes to the existing callback, and append to the bounded final buffer. Route
  `send_input` through `os.write(master_fd, value + newline)` after the current
  printable validation. Ensure terminate sends SIGTERM/SIGKILL to the process
  group, closes the PTY master, and awaits/reaps all monitor tasks.

- [ ] **Step 3: Run focused tests**

  Run `uv run pytest -q tests/auth/test_process.py tests/auth/test_manager.py`.
  Expected: PASS, including no leaked child process assertions.

- [ ] **Step 4: Run scoped lint/type checks**

  Run `uv run ruff check app/auth/process.py tests/auth/test_process.py tests/auth/test_manager.py` and `uv run mypy app/auth/process.py`.
  Expected: PASS.

- [ ] **Step 5: Commit**

  Run `git add agent-service/app/auth/process.py agent-service/tests/auth/test_process.py agent-service/tests/auth/test_manager.py` then `git commit -m "feat: support bounded PTY auth processes"`.

### Task 3: Enable and parse Antigravity remote auth

**Files:**
- Modify: `agent-service/app/auth/adapters/antigravity.py`
- Modify: `agent-service/app/auth/process.py`
- Modify: `agent-service/app/auth/base.py` if a fixed environment hook is needed
- Test: `agent-service/tests/auth/test_antigravity_auth.py`
- Test: `agent-service/tests/auth/test_manager.py`
- Modify: `agent-service/docs/auth-flow-probe.md`

**Interfaces:**
- Consume the PTY process and `ParsedAuthUpdate` contract from Task 2.
- Produce an Antigravity adapter with `manual_auth_only=False`, fixed `agy` command, fixed remote markers, an exact OAuth host allowlist, and safe URL/code/status parsing.

- [ ] **Step 1: Write failing adapter tests**

  Assert the adapter requests PTY mode, supplies no user arguments, emits a
  `WAITING_FOR_USER` update for a Google OAuth URL, extracts only a bounded
  authorization code, rejects non-Google URLs, recognizes the fixed code-input
  prompt, and classifies a successful exit as authenticated.

- [ ] **Step 2: Run adapter tests and verify they fail**

  Run `uv run pytest -q tests/auth/test_antigravity_auth.py`.
  Expected: FAIL because the adapter is currently manual-only and always fails.

- [ ] **Step 3: Implement the adapter**

  Set `manual_auth_only=False`, return `AuthCommand("agy", (), use_pty=True)`,
  provide fixed `SSH_CONNECTION`/`SSH_CLIENT`/`SSH_TTY` markers through the
  process environment hook, and reuse the shared parser with the observed
  `accounts.google.com` allowlist. Map the documented browser-code prompt to
  `AuthInputLabel.AUTHORIZATION_CODE`; never forward arbitrary prompt text.

- [ ] **Step 4: Run adapter and manager tests**

  Run `uv run pytest -q tests/auth/test_antigravity_auth.py tests/auth/test_manager.py`.
  Expected: PASS.

- [ ] **Step 5: Run a disposable pinned-image smoke test**

  Build with `docker compose build agent-service`, run an isolated PTY smoke
  with the remote markers, and report only URL hostname/state/exit status. Do
  not print or save the generated URL or code.

- [ ] **Step 6: Update probe evidence and commit**

  Record the safe smoke result in `agent-service/docs/auth-flow-probe.md`, then
  run `git add agent-service/app/auth/adapters/antigravity.py agent-service/app/auth/process.py agent-service/app/auth/base.py agent-service/tests/auth/test_antigravity_auth.py agent-service/tests/auth/test_manager.py agent-service/docs/auth-flow-probe.md` (only existing files) and commit `feat: expose Antigravity browser auth handoff`.

### Task 4: Expose browser-link capability and preserve the admin UX

**Files:**
- Modify: `agent-service/app/schemas.py`
- Modify: `agent-service/app/runners/registry.py`
- Modify: `backend/app/body_analysis/admin_config/schemas.py`
- Modify: `frontend/src/features/admin/types.ts`
- Modify: `frontend/src/features/admin/AgentServicePanel.tsx`
- Modify: `frontend/src/features/admin/AgentAuthDialog.tsx`
- Modify: `frontend/src/i18n/fa.ts`
- Modify: `frontend/src/i18n/en.ts`
- Test: `agent-service/tests/test_capabilities.py`
- Test: `backend/tests/ai/test_agent_service_admin_contract.py`
- Test: `frontend/src/features/admin/AgentServicePanel.test.tsx`
- Test: `frontend/src/features/admin/AgentAuthDialog.test.tsx`

**Interfaces:**
- Consume `manual_auth_only=False` and safe auth session responses.
- Produce a capability field such as `auth_mode="browser_link"` for Antigravity and a disabled/manual explanatory state only when appropriate.

- [ ] **Step 1: Write failing contract/UI tests**

  Add capability validation for the new field, assert Antigravity’s auth action
  is enabled only when the service reports browser-link support, and assert a
  session URL renders with open/copy actions while no raw terminal text is
  rendered.

- [ ] **Step 2: Run focused tests and verify failures**

  Run `uv run pytest -q tests/test_capabilities.py` from `agent-service/`, the
  focused backend contract test, and `npm run test -- --run src/features/admin/AgentServicePanel.test.tsx src/features/admin/AgentAuthDialog.test.tsx` from `frontend/`.
  Expected: the new field/action assertions fail.

- [ ] **Step 3: Implement the capability and UI wiring**

  Add the field with a backward-compatible default, serialize it through the
  Agent Service → Backend schema, and update the panel to render Antigravity’s
  browser-link action. Keep `AgentAuthDialog`’s existing URL safety check and
  polling; map only stable error codes and display no raw service message.

- [ ] **Step 4: Run focused checks**

  Run the same Agent Service/backend/frontend focused tests, then `npm run lint`.
  Expected: PASS.

- [ ] **Step 5: Commit**

  Commit with `feat: surface Antigravity browser auth in admin settings` after staging only the listed files.

### Task 5: Full verification and delivery

**Files:**
- No new source files; inspect only the task diff and runtime configuration.

- [ ] **Step 1: Run full Agent Service checks**

  From `agent-service/`, run `uv run pytest -q`, `uv run ruff check .`, and
  `uv run mypy .`.

- [ ] **Step 2: Run backend and frontend regression checks**

  From `backend/`, run `uv run pytest -q`; from `frontend/`, run
  `npm run test -- --run` and `npm run build`.

- [ ] **Step 3: Run live contract smoke**

  Verify `docker compose ps`, Agent Service health, authenticated capabilities,
  and Antigravity auth start. Capture only status code, stable error/status,
  URL hostname, and request ID redacted from output.

- [ ] **Step 4: Review and commit final evidence**

  Run `git diff --check`, inspect every staged diff, confirm no secrets or
  generated auth values are present, and report all test counts honestly.
