# Admin Training Template Editor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give administrators a dedicated editor to create and maintain reference training programs and their exercise links.

**Architecture:** Keep training templates as the persistent reference source. Add admin-only create/update service functions that replace a template's ordered days and slots atomically. Add a dedicated React editor route; the library page only navigates to it and supplies default day/level context.

**Tech Stack:** FastAPI, Pydantic, SQLAlchemy, PostgreSQL, React, TypeScript, React Router, Vitest, pytest.

## Global Constraints

- Only admins can read or write template-editor data.
- Do not modify global exercise records from the template editor.
- Validate all exercise links against active library records.
- Preserve stable template slugs when editing; create new unique slugs deterministically.
- Use no new dependencies.

---

### Task 1: Admin template write contract and persistence

**Files:**
- Modify: `backend/app/admin/schemas.py`
- Modify: `backend/app/admin/router.py`
- Create: `backend/app/training_templates/admin_service.py`
- Test: `backend/tests/admin/test_training_template_api.py`

**Interfaces:**
- Produces `create_training_program_template(db, payload)` and `update_training_program_template(db, template_id, payload)`.
- Consumes full ordered day and slot payloads and returns loaded `TrainingProgramTemplate`.

- [ ] Write failing tests for admin create/update, deletion by replacement, invalid exercise IDs, and non-admin rejection.
- [ ] Run targeted pytest and confirm new write routes are missing.
- [ ] Add Pydantic payloads, transactional replacement service, and POST/PUT routes.
- [ ] Run targeted pytest and backend type/lint checks.
- [ ] Commit backend contract.

### Task 2: Editor API client, types, and dedicated route

**Files:**
- Modify: `frontend/src/features/admin/types.ts`
- Modify: `frontend/src/features/admin/api.ts`
- Create: `frontend/src/features/admin/AdminTrainingTemplateEditorPage.tsx`
- Modify: `frontend/src/App.tsx`
- Test: `frontend/src/features/admin/AdminTrainingTemplateEditorPage.test.tsx`

**Interfaces:**
- Produces `createAdminTrainingProgramTemplate` and `updateAdminTrainingProgramTemplate`.
- Editor accepts edit route ID or `days`/`level` query defaults.

- [ ] Write failing editor test for an initially blank program with selected day/level defaults.
- [ ] Run focused Vitest and confirm the editor route/component does not exist.
- [ ] Implement client types, fetch/load/save states, and the dedicated route.
- [ ] Run focused Vitest.
- [ ] Commit editor shell.

### Task 3: Day, slot, and exercise-library search controls

**Files:**
- Modify: `frontend/src/features/admin/AdminTrainingTemplateEditorPage.tsx`
- Modify: `frontend/src/features/admin/admin.css`
- Modify: `frontend/src/i18n/fa.ts`
- Modify: `frontend/src/i18n/en.ts`
- Test: `frontend/src/features/admin/AdminTrainingTemplateEditorPage.test.tsx`

**Interfaces:**
- Consumes paginated `getAdminExercises({ search, is_active: true })` results.
- Produces complete ordered editor payloads with per-slot display names and exercise IDs.

- [ ] Write failing tests for exercise search/selection and removing a slot.
- [ ] Run focused Vitest and confirm the controls are absent.
- [ ] Implement accessible search results, selection, add/remove/reorder controls, and validation copy.
- [ ] Run focused Vitest, frontend lint, and build.
- [ ] Commit editor controls.

### Task 4: Library entry points and complete verification

**Files:**
- Modify: `frontend/src/features/admin/AdminTrainingTemplatesPage.tsx`
- Modify: `frontend/src/features/admin/AdminTrainingTemplatesPage.test.tsx`

**Interfaces:**
- Library navigates to `/admin/training-program-templates/new?days=<2..6>&level=<level>` and `/admin/training-program-templates/<id>/edit`.

- [ ] Write failing library-page test for edit and add-program entry points.
- [ ] Run focused Vitest and confirm actions are absent.
- [ ] Implement entry points at every selected day-count view.
- [ ] Run backend and frontend full suites, lints, type checks, and production build.
- [ ] Seed active runtime data only if necessary, restart backend, smoke-test 5173, commit and push.
