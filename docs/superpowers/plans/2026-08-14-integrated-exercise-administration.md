# Integrated Exercise Administration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `/exercises` the only exercise browser while exposing protected create, edit, inactive, and needs-review workflows only to administrators.

**Architecture:** Keep the existing public read API as the default catalog source. Add category and review filters to the existing protected admin list API, and call it only when an admin selects an administrative status filter. Reuse the current protected create/edit pages, passing category and return context in query parameters.

**Tech Stack:** FastAPI, SQLAlchemy, Pydantic, React 19, TypeScript, React Router, i18next, Vitest, pytest.

## Global Constraints

- `/exercises` remains the single browser for members and administrators.
- Member rendering and public API behavior remain unchanged.
- Write operations remain under `/api/v1/admin/exercises` and `AdminRoute`.
- Administrative controls require `user.is_admin === true`.
- Existing uncommitted files outside this feature are preserved.

---

### Task 1: Protected admin list filtering

**Files:**
- Modify: `backend/app/admin/schemas.py`
- Modify: `backend/app/admin/service.py`
- Test: `backend/tests/admin/test_exercise_api.py`

**Interfaces:**
- Consumes: `AdminExerciseFilters` query dependency and existing exercise relationships.
- Produces: protected filters `body_region`, `primary_muscle`, `equipment`, `difficulty`, `exercise_type`, `labels`, and `needs_review`.

- [ ] Write API tests that seed exercises and request category, equipment, status, and needs-review combinations from `/api/v1/admin/exercises`.
- [ ] Run `pytest tests/admin/test_exercise_api.py -q` and confirm the new assertions fail because the query filters are absent.
- [ ] Extend `AdminExerciseFilters` with the exercise enum fields and apply equivalent SQLAlchemy conditions in `list_admin_exercises`, including relationship filtering for equipment and labels.
- [ ] Run `pytest tests/admin/test_exercise_api.py -q`, `ruff check app/admin tests/admin/test_exercise_api.py`, and `mypy app`.

### Task 2: Library context model and administrator controls

**Files:**
- Modify: `frontend/src/features/exercises/ExerciseCatalogPage.tsx`
- Modify: `frontend/src/features/exercises/ExerciseCatalogPage.test.tsx`
- Modify: `frontend/src/features/admin/types.ts`
- Modify: `frontend/src/features/admin/api.ts`
- Modify: `frontend/src/i18n/en.ts`
- Modify: `frontend/src/i18n/fa.ts`
- Modify: `frontend/src/features/exercises/exercises.css`

**Interfaces:**
- Consumes: `useAuth().user.is_admin`, catalog query parameters, `getExercises`, and `getAdminExercises`.
- Produces: `admin_status=inactive|needs_review|all`, contextual add/edit links, and protected admin-result loading.

- [ ] Add failing catalog tests proving members see no add/edit/status controls and administrators see them.
- [ ] Add failing tests proving selected body region, muscle, search, equipment, and difficulty are encoded in add/edit navigation.
- [ ] Add failing tests proving explicit admin status filters call `getAdminExercises` with category and result filters while the default catalog still calls `getExercises`.
- [ ] Run `npm run test -- src/features/exercises/ExerciseCatalogPage.test.tsx` and confirm failures describe missing controls and protected loading.
- [ ] Implement admin-only actions, status parsing/serialization, protected result mapping, and accessible bilingual copy.
- [ ] Add scoped responsive styles that preserve the existing member card layout when controls are absent.
- [ ] Run the focused catalog and API tests until green.

### Task 3: Context-aware create and edit return flow

**Files:**
- Modify: `frontend/src/features/admin/AdminExerciseNewPage.tsx`
- Modify: `frontend/src/features/admin/AdminExerciseNewPage.test.tsx`
- Modify: `frontend/src/features/admin/AdminExerciseEditPage.tsx`
- Modify: `frontend/src/features/admin/AdminExerciseEditPage.test.tsx`
- Create: `frontend/src/features/admin/exerciseLibraryNavigation.ts`
- Create: `frontend/src/features/admin/exerciseLibraryNavigation.test.ts`

**Interfaces:**
- Consumes: `body_region`, `primary_muscle`, and `return_to` query parameters.
- Produces: validated create defaults and `/exercises?...` return URLs updated to the saved exercise category/status.

- [ ] Add failing unit tests for safe return-path validation and saved-category replacement across upper body, lower body, and core muscles.
- [ ] Add failing page tests for create prefill, editable preselection, cancel/back links, and post-save return navigation.
- [ ] Run the focused tests and confirm the new expectations fail.
- [ ] Implement the shared navigation helper and use it in both existing form pages without duplicating form fields.
- [ ] Run the focused navigation, new-page, and edit-page tests until green.

### Task 4: Remove the duplicate browser and obsolete route entry

**Files:**
- Delete: `frontend/src/features/admin/AdminExercisesPage.tsx`
- Delete: `frontend/src/features/admin/AdminExercisesPage.test.tsx`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/App.test.tsx`
- Modify: `frontend/src/pages/MorePage.tsx`
- Modify: `frontend/src/pages/MorePage.test.tsx`
- Modify: `frontend/src/features/admin/admin.css`
- Modify: `frontend/src/i18n/en.ts`
- Modify: `frontend/src/i18n/fa.ts`

**Interfaces:**
- Consumes: existing `AdminRoute` and exercise form routes.
- Produces: `/admin/exercises` redirect to `/exercises`, no More-page administration link, and no duplicate browser bundle.

- [ ] Add failing route and More-page tests for the redirect and removed workspace entry.
- [ ] Run the focused tests and confirm the previous page/link behavior causes failure.
- [ ] Replace the list route with a protected redirect, remove the lazy page import and workspace link, delete obsolete browser files, copy, and unused CSS.
- [ ] Run `npm run test -- src/App.test.tsx src/pages/MorePage.test.tsx` until green.

### Task 5: Verification and delivery

**Files:**
- Verify all feature files above.

**Interfaces:**
- Consumes: completed backend and frontend behavior.
- Produces: tested, committed, and pushed implementation on `main`.

- [ ] Run backend focused tests, `ruff check`, `ruff format --check`, and `mypy app` from `backend/`.
- [ ] Run frontend focused tests, full `npm run test`, `npm run lint`, and `npm run build` from `frontend/`.
- [ ] Review `git diff`, ensure unrelated files and sensitive data are unstaged, and verify every requirement against the implementation.
- [ ] Commit tracked feature files with `feat(exercises): integrate admin actions into exercise library`.
- [ ] Push `main` to `origin` and report the exact verification and Git result.
