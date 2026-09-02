# Body Analysis Codex Retry Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let a submitted body-photo session with exhausted Antigravity attempts retry against the currently selected Codex task configuration using the same private photos.

**Architecture:** Keep the existing owner-scoped retry endpoint, durable analysis revisions, and stored-image transport. Change only the retry-budget query so attempts are bounded per provider execution scope and photo snapshot; a provider change creates a fresh bounded recovery scope while preserving all previous rows.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy, PostgreSQL, pytest, React 19, TypeScript, Vitest, Docker Compose

**Spec:** `docs/superpowers/specs/2026-09-03-body-analysis-codex-retry-design.md`

## Global Constraints

- Reuse the existing standardized private photos; never require original-photo re-upload for an unchanged snapshot.
- Preserve owner authorization, stale-analysis recovery, same-provider retry limits, safe errors, and previous analysis history.
- Read the current AI task configuration at retry time; do not silently fall back from Codex to Antigravity.
- Keep Agent Service requests reference-only for stored body images; do not log or expose image bytes or storage keys.
- Do not change frontend behavior or unrelated work unless a focused regression proves it is required.

---

### Task 1: Specify the provider-switch retry regression

**Files:**
- Modify: `backend/tests/body_analysis/test_execution_and_reviews.py:788-807`

**Interfaces:**
- Consumes: `BodyAnalysisService.queue`, `BodyAnalysisService.retry`, and `AnalysisExecutionConfig`.
- Produces: a failing regression proving three failed revisions under `openrouter` do not block a retry under `agent_service:codex` for unchanged photos.

- [x] **Step 1: Write the failing test**

Add this test after the existing bounded-retry test:

```python
def test_provider_change_reopens_retry_budget_for_same_stored_photos(db: Session) -> None:
    user, session = _submitted_session(db)
    service = BodyAnalysisService(db)
    old_config = _config()
    failed = service.queue(session.id, user.id, old_config)
    for attempt in range(3):
        failed.status = BodyAnalysisStatus.FAILED
        db.commit()
        if attempt < 2:
            failed = service.retry(failed.id, user.id, old_config)

    codex_config = old_config.model_copy(
        update={
            "provider_name": "agent_service:codex",
            "primary_model": "gpt-5.6-luna",
        }
    )
    retried = service.retry(failed.id, user.id, codex_config)

    assert retried.revision == 4
    assert retried.replaces_analysis_id == failed.id
    assert retried.provider == "agent_service:codex"
    assert retried.model_id == "gpt-5.6-luna"
    assert retried.raw_result == failed.raw_result
```

- [x] **Step 2: Run the focused test and verify RED**

Run from `backend/`:

```bash
uv run pytest tests/body_analysis/test_execution_and_reviews.py::test_provider_change_reopens_retry_budget_for_same_stored_photos -q
```

Expected: FAIL with `BodyAnalysisStateError: analysis retry limit reached`, because the current query counts the three old-provider revisions together.

- [x] **Step 3: Commit the red test**

```bash
git add backend/tests/body_analysis/test_execution_and_reviews.py
git commit -m "test(body-analysis): cover retry after provider switch"
git push origin main
```

### Task 2: Scope retry limits to the active provider

**Files:**
- Modify: `backend/app/body_analysis/service.py:508-530`
- Test: `backend/tests/body_analysis/test_execution_and_reviews.py`

**Interfaces:**
- Consumes: `session_id` and `AnalysisExecutionConfig.provider_name` in `_assert_retry_available`.
- Produces: the same retry-limit error for repeated attempts under one provider and a new revision when the current provider changes.

- [x] **Step 1: Implement the minimal query change**

Keep the latest-photo boundary and existing `retry_limit + 1` arithmetic. Add the durable provider scope to the count:

```python
.where(
    BodyAnalysis.session_id == session_id,
    BodyAnalysis.created_at >= latest_photo_change,
    BodyAnalysis.provider == config.provider_name,
)
```

Add a short comment explaining that provider changes create a fresh bounded recovery scope while prior rows remain immutable history. Do not remove the limit or alter photo storage.

- [x] **Step 2: Run retry and snapshot tests**

```bash
uv run pytest \
  tests/body_analysis/test_execution_and_reviews.py \
  tests/body_analysis/test_analysis_api.py \
  tests/ai/test_agent_service_provider.py -q
```

Expected: all focused body-analysis, API authorization, stored-reference, stale-recovery, same-provider-limit, and photo-snapshot tests pass.

- [x] **Step 3: Commit the implementation**

```bash
git add backend/app/body_analysis/service.py
git commit -m "fix(body-analysis): reset retry scope after provider change"
git push origin main
```

### Task 3: Verify the existing UI and live Codex path

**Files:**
- Inspect only: `frontend/src/features/bodyPhotos/BodyAnalysisResultPage.tsx`, `frontend/src/features/bodyPhotos/api.ts`
- Test: `frontend/src/features/bodyPhotos/BodyAnalysisResultPage.test.tsx`

**Interfaces:**
- Consumes: the existing `retryBodyPhotoAnalysis(sessionId)` action and queued-state polling.
- Produces: no frontend code change; evidence that the visible retry action calls the owner endpoint and that the backend still sends stored image references.

- [x] **Step 1: Run focused frontend checks**

```bash
cd frontend
npm run test -- src/features/bodyPhotos/BodyAnalysisResultPage.test.tsx src/features/bodyPhotos/api.test.ts
npm run lint
npm run build
```

Expected: retry UI, API method, lint, and production build pass without a frontend diff.

- [x] **Step 2: Rebuild the live backend without touching database volumes**

```bash
docker compose up -d --build backend
docker compose ps
```

Confirm the backend is running and the existing Agent Service remains healthy.

- [x] **Step 3: Verify current task routing and the affected session**

Use read-only PostgreSQL queries and redacted service logs to confirm the task is enabled on `agent_service:codex`, the affected session still has three old Antigravity failures, and no old row was deleted. Do not claim the user's new attempt succeeded until the user clicks Retry and the database plus Agent Service logs show the new Codex revision and stored-image request.

- [x] **Step 4: Commit only if verification adds a required test change**

No frontend commit is expected. If no additional source change is required, finish with the two focused commits above and the live verification evidence.
