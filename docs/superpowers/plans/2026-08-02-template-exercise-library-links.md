# Template Exercise Library Links Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Link each training-template exercise to its catalog detail and create safe catalog records for missing exercises.

**Architecture:** `training_templates` owns a small deterministic catalog-placeholder builder. The existing seed service invokes it before resolving template slots. The admin API returns review status and React renders the detail link.

**Tech Stack:** FastAPI, SQLAlchemy, React, TypeScript, pytest, Vitest.

## Global Constraints

- Placeholder exercises must stay `is_programmable=false` and `needs_review=true`.
- Do not overwrite an admin-updated placeholder.
- Do not add dependencies or alter workout eligibility rules.

---

### Task 1: Write failing catalogue and UI tests

**Files:**
- Modify: `backend/tests/training_templates/test_seed.py`
- Modify: `backend/tests/admin/test_training_template_api.py`
- Modify: `frontend/src/features/admin/AdminTrainingTemplatesPage.test.tsx`

- [ ] Assert that a missing template exercise becomes a linked, review-needed, non-programmable catalog record.
- [ ] Assert a reseed preserves custom media assigned by an admin.
- [ ] Assert the API returns the linked record and the template card renders its detail link.

### Task 2: Create safe template catalog placeholders

**Files:**
- Create: `backend/app/training_templates/catalog_placeholders.py`
- Modify: `backend/app/training_templates/service.py`

- [ ] Build records from the template slot target, pattern, and bilingual placeholder name.
- [ ] Prefer reviewed catalog exercises over generated placeholder records.
- [ ] Keep generated placeholders out of program generation.

### Task 3: Render per-exercise links

**Files:**
- Modify: `backend/app/admin/schemas.py`
- Modify: `backend/app/admin/router.py`
- Modify: `frontend/src/features/admin/types.ts`
- Modify: `frontend/src/features/admin/AdminTrainingTemplatesPage.tsx`
- Modify: `frontend/src/features/admin/admin.css`
- Modify: `frontend/src/i18n/fa.ts`
- Modify: `frontend/src/i18n/en.ts`

- [ ] Return review status for the slot exercise.
- [ ] Render the distinct detail action beside every linked exercise.
- [ ] Show an explicit review/media-needed note for placeholder records.

### Task 4: Verify and seed active data

- [ ] Run backend tests, Ruff, and mypy.
- [ ] Run frontend tests, lint, and production build.
- [ ] Seed the active library, restart the backend, and check port 5173.
