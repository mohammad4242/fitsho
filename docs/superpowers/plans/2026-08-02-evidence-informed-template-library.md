# Evidence-Informed Template Library Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make every Fitsho reference template evidence-informed in ordering and explain its programming logic in the admin library.

**Architecture:** A new JSON column holds five small bilingual rationale records per template. Seed normalization gives all session slots one deterministic order after current count and specialist-floor normalization. The admin API and card expose the persisted records.

**Tech Stack:** FastAPI, SQLAlchemy, Alembic, Pydantic, React, TypeScript, Vitest, pytest.

## Global Constraints

- Keep template library admin-only.
- Do not copy paid programs or source text.
- Preserve 5–9 exercises per session and current safety contracts.
- Add no third-party dependency.

---

### Task 1: Specify and test template rationale and ordering

**Files:**
- Modify: `backend/tests/training_templates/test_seed.py`
- Modify: `backend/tests/admin/test_training_template_api.py`
- Modify: `frontend/src/features/admin/AdminTrainingTemplatesPage.test.tsx`

- [ ] Write failing tests for five persisted rationale entries and exercise ordering.
- [ ] Run the targeted backend tests and confirm they fail because the field and normalization are absent.
- [ ] Write the failing admin UI test for the rationale heading and first reason.
- [ ] Run the targeted frontend test and confirm it fails because the rationale is not rendered.

### Task 2: Persist evidence-informed rationale and normalize seed order

**Files:**
- Modify: `backend/app/training_templates/models.py`
- Modify: `backend/app/training_templates/seed_data.py`
- Modify: `backend/app/training_templates/service.py`
- Modify: `backend/app/admin/schemas.py`
- Modify: `backend/app/admin/router.py`
- Create: `backend/alembic/versions/20260802_17_add_template_programming_rationale.py`

- [ ] Add the database field and migration.
- [ ] Add seed rationale records and deterministic ordering after existing normalization.
- [ ] Return the persisted records through the admin API.
- [ ] Run targeted backend tests until green.

### Task 3: Render the admin explanation panel

**Files:**
- Modify: `frontend/src/features/admin/types.ts`
- Modify: `frontend/src/features/admin/AdminTrainingTemplatesPage.tsx`
- Modify: `frontend/src/features/admin/admin.css`
- Modify: `frontend/src/i18n/fa.ts`
- Modify: `frontend/src/i18n/en.ts`

- [ ] Render the five persisted entries below each template card.
- [ ] Add the bilingual section label and a clear 2px divider.
- [ ] Run the focused frontend test until green.

### Task 4: Verify, seed, and publish

**Files:**
- Verify the files above only.

- [ ] Run backend tests, ruff, and mypy.
- [ ] Run frontend tests, lint, and production build.
- [ ] Apply migration and re-seed the active database.
- [ ] Restart the local backend and check the Vite proxy.
- [ ] Commit only tracked feature files and push `main`.
