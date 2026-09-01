# Private Media Storage-Key Transport Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move production Body/Food image transport from multipart bytes to secure storage references resolved by the read-only Agent Service mount.

**Architecture:** `ImageInput` is the canonical mutually-exclusive inline/stored reference. Body and Food create stored references; Agent Service receives composed JSON and resolves paths under its configured read-only roots. OpenRouter alone resolves stored references and encodes bytes for its external API.

**Tech Stack:** Python 3.12, Pydantic 2, FastAPI, httpx, Pillow, pytest, Ruff, mypy, Docker Compose.

**Spec:** `docs/superpowers/specs/2026-09-01-private-media-storage-key-transport-design.md`

## Global Constraints

- Keep `./backend/var/private/body-photos` and `./backend/var/private/food-photos` unchanged.
- Do not modify database tables, records, prompts, response schemas, model selection, reasoning effort, auth, pricing, or frontend behavior.
- Agent Service must keep `read_only: true`, `/home/agent` persistent, `/tmp` temporary, and shared media read-only.
- Reject absolute paths, traversal, symlink escapes, unsupported files, and mixed inline/stored batches.
- Never copy production images into `/tmp/fitsho-agent` or another temporary path.
- Keep existing inline multipart compatibility.

---

### Task 1: Backend image-source contract and private resolver

**Files:**
- Create: `backend/app/private_media.py`
- Modify: `backend/app/body_analysis/providers/models.py`
- Test: `backend/tests/ai/test_private_media.py`, `backend/tests/ai/test_agent_service_provider.py`

**Interfaces:**
- `ImageInput` exposes optional `base64_data`, `storage_scope`, and `storage_key`, with exactly one valid source state.
- `PrivateMediaResolver(settings).resolve(scope, storage_key, expected_mime_type) -> Path` validates containment and file type.
- `PrivateMediaResolver(settings).read(scope, storage_key, expected_mime_type) -> bytes` reads only after the path checks.

- [ ] **Step 1: Write failing contract tests in `test_private_media.py`** for inline-only, stored-only, mixed, empty, traversal, symlink escape, missing, directory, extension mismatch, and successful body/food reads.
- [ ] **Step 2: Run the focused tests and confirm they fail because the stored source and resolver are absent.**
- [ ] **Step 3: Add the mutually-exclusive Pydantic model and a root-aware resolver using `PurePosixPath`, strict resolution, containment, and MIME/extension checks.**
- [ ] **Step 4: Run the focused tests and confirm they pass.**
- [ ] **Step 5: Commit with proposed message `feat(ai): add secure private media storage references`.**

### Task 2: Backend provider transport split and OpenRouter resolution

**Files:**
- Modify: `backend/app/body_analysis/providers/agent_service.py`
- Modify: `backend/app/body_analysis/providers/openrouter.py`
- Modify: `backend/app/ai/task_provider.py`
- Test: `backend/tests/ai/test_agent_service_provider.py`, `backend/tests/body_analysis/test_providers.py`, `backend/tests/ai/test_task_provider.py`

**Interfaces:**
- Stored Agent Service requests use `POST /v1/analyze-stored-images` with `{ "generation": <existing metadata>, "images": <stored refs> }`.
- Inline Agent Service requests keep `POST /v1/analyze-images` multipart behavior.
- `OpenRouterProvider` accepts an injected `PrivateMediaResolver` and asynchronously builds the same external data URLs from inline data or resolved stored bytes.

- [ ] **Step 1: Add failing tests** for stored JSON routing, no bytes/Base64/multipart in the stored request, mixed rejection, and OpenRouter resolution to the expected data URL.
- [ ] **Step 2: Run those tests and confirm the current provider routes stored data to multipart or cannot construct it.**
- [ ] **Step 3: Implement source classification, stored JSON transport, resolver injection, and OpenRouter-only byte encoding without changing generation fields or message semantics.**
- [ ] **Step 4: Run the provider tests and confirm inline compatibility and stored behavior pass.**
- [ ] **Step 5: Commit with proposed message `feat(ai): route stored images by reference`.**

### Task 3: Backend Body/Food production references

**Files:**
- Modify: `backend/app/body_analysis/service.py`
- Modify: `backend/app/body_analysis/runtime.py`
- Modify: `backend/app/body_analysis/router.py`
- Modify: `backend/app/nutrition/food_photo_service.py`
- Modify: `backend/tests/body_analysis/test_execution_and_reviews.py`, `backend/tests/body_analysis/test_analysis_api.py`, `backend/tests/nutrition/test_food_photo_estimation.py`, and the affected E2E contract

**Interfaces:**
- Body `execute` builds one stored `(body, storage_key)` image tuple and reuses it for preflight and analysis without a storage reader.
- Food stores normalized JPEG first, then sends `ImageInput(label="food_photo", mime_type="image/jpeg", storage_scope="food", storage_key=key)`.

- [ ] **Step 1: Update failing tests** to assert stored references, provider parity, normalized-file-before-provider ordering, and cleanup on failure.
- [ ] **Step 2: Run the Body/Food tests and confirm old Base64 expectations fail.**
- [ ] **Step 3: Remove Body analysis read/Base64 preparation and Food production Base64 construction; remove only now-unused runtime/storage plumbing.**
- [ ] **Step 4: Run the focused Body/Food tests and confirm they pass.**
- [ ] **Step 5: Commit with proposed message `refactor(ai): preserve production images as storage references`.**

### Task 4: Agent Service schemas, configuration, and resolver

**Files:**
- Create: `agent-service/app/private_media.py`
- Modify: `agent-service/app/config.py`
- Modify: `agent-service/app/schemas.py`
- Test: `agent-service/tests/test_stored_image_api.py`

**Interfaces:**
- `StoredImageReference` is strict and contains only label, supported MIME, body/food scope, and storage key.
- `StoredImageGenerationInput` contains `generation: AgentGenerationInput` and a bounded tuple of references.
- `PrivateMediaResolver.resolve_many(references) -> tuple[Path, ...]` enforces configured count, per-file, total-size, extension, containment, and symlink rules.

- [ ] **Step 1: Write failing resolver/schema tests** for valid body/food keys and every listed invalid condition.
- [ ] **Step 2: Run them and confirm the new schema/resolver is missing.**
- [ ] **Step 3: Implement strict models, `AGENT_SHARED_PRIVATE_MEDIA_ROOT`, and secure strict-resolution/size enforcement without exposing paths.**
- [ ] **Step 4: Run the focused tests and confirm they pass.**
- [ ] **Step 5: Commit with proposed message `feat(agent-service): add secure stored-image references`.**

### Task 5: Agent Service stored-image endpoint and execution

**Files:**
- Modify: `agent-service/app/main.py`
- Modify: `agent-service/app/service.py`
- Test: `agent-service/tests/test_stored_image_api.py`, `agent-service/tests/test_observability.py`

**Interfaces:**
- `POST /v1/analyze-stored-images` requires internal auth and calls `AgentService.analyze_stored_images`.
- The service validates schema/profile/capability, resolves and validates original files, creates only the normal output workspace, passes original paths in `RunnerRequest.image_paths`, validates output, and cleans the workspace.

- [ ] **Step 1: Add failing endpoint tests** for valid path passthrough, labels/MIME, no workspace image copy, cleanup, source preservation, auth, and image capability rejection.
- [ ] **Step 2: Run them and confirm the endpoint and method are absent.**
- [ ] **Step 3: Implement the JSON route, telemetry fields, resolver/file validation, and original-path execution flow while preserving multipart `analyze_images`.**
- [ ] **Step 4: Run stored-image and existing image API tests and confirm both routes pass.**
- [ ] **Step 5: Commit with proposed message `feat(agent-service): execute stored images in place`.**

### Task 6: Shared runner path security and CLI transport framing

**Files:**
- Modify: `agent-service/app/runners/base.py`
- Modify: `agent-service/app/runners/registry.py`
- Modify: `agent-service/app/runners/codex.py`
- Modify: `agent-service/app/runners/claude.py`
- Modify: `agent-service/app/runners/antigravity.py`
- Test: runner tests and `agent-service/tests/test_runner_request_passthrough.py`

**Interfaces:**
- A shared helper accepts only paths resolved beneath the request workspace or configured shared-media root.
- `Settings.agent_shared_private_media_root` flows through `RunnerRegistry` and all runner factories.
- Codex passes shared paths directly to `--image`; Claude/Antigravity list validated absolute paths in transport framing only.

- [ ] **Step 1: Add failing runner tests** for valid shared paths, `/etc/passwd`, `/home/agent`, arbitrary absolute paths, symlink escapes, and transport framing.
- [ ] **Step 2: Run them and confirm the current workspace-only validation rejects valid shared paths.**
- [ ] **Step 3: Implement one shared validator and update all three runners/factories without weakening sandbox or secrets filtering.**
- [ ] **Step 4: Run all runner tests and confirm inline workspace behavior remains green.**
- [ ] **Step 5: Commit with proposed message `security(agent-service): allow only configured media image paths`**.

### Task 7: Compose contract and documentation

**Files:**
- Modify: `compose.yaml`
- Modify: `agent-service/README.md`
- Test/verify: `docker compose config`

- [ ] **Step 1: Add the exact Agent Service read-only body/food bind mounts and `AGENT_SHARED_PRIVATE_MEDIA_ROOT`.**
- [ ] **Step 2: Run `docker compose config` and verify the two `:ro` mounts, read-only container, unchanged Backend mounts, and no database/private nutrition-lab Agent mount.**
- [ ] **Step 3: Update the stale Agent Service mount description to state that only the two read-only private-media roots are available.**
- [ ] **Step 4: Commit with proposed message `chore(compose): mount private media read-only for agent service`.**

### Task 8: Full verification and source audit

**Files:**
- Inspect only the final diff and test outputs.

- [ ] **Step 1: Run focused Backend tests, focused Agent Service tests, broader affected suites, Ruff, and mypy with fresh output.**
- [ ] **Step 2: Run Compose rendering and container checks when Docker is available; record unavailable runtime checks honestly.**
- [ ] **Step 3: Audit the final diff for allowed/forbidden Base64, transport endpoints, storage scopes/keys, prompt ownership, migrations, and unrelated files.**
- [ ] **Step 4: Commit any narrowly coupled verification-only test corrections with a specific message, then push the current branch if the remote is configured.**
- [ ] **Step 5: Report exact changed files, flows, controls, pass/fail counts, lint/type results, and runner limitations.**
