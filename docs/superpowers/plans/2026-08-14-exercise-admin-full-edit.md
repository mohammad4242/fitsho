# Exercise Admin Full Edit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the protected exercise editor update every exercise field and make its library Edit action readable.

**Architecture:** Move the complete exercise input UI into a shared controlled component used by both create and edit pages. Keep serialization and protected API contracts unchanged, and add edit-specific validation/error handling around the shared form.

**Tech Stack:** React 19, TypeScript, React Router, Vitest, Testing Library, FastAPI

## Global Constraints

- Normal-user Exercise Library behavior must not change.
- Exercise writes remain under `/api/v1/admin/exercises` with existing admin and trusted-origin checks.
- Create and edit must share the same complete field UI.
- Preserve the Exercise Library return context after save.

---

### Task 1: Shared full exercise fields

**Files:**
- Create: `frontend/src/features/admin/AdminExerciseFields.tsx`
- Modify: `frontend/src/features/admin/AdminExerciseNewPage.tsx`
- Test: `frontend/src/features/admin/AdminExerciseNewPage.test.tsx`

**Interfaces:**
- Consumes: `AdminExerciseForm`, `AdminValidationErrors`, and the existing exercise taxonomies.
- Produces: `AdminExerciseFields({ value, errors, duplicateSlug, onChange })`.

- [ ] Add a test assertion that the create page still exposes identity, targeting, equipment, difficulty, guidance, programming, and active-state controls.
- [ ] Run `npm test -- AdminExerciseNewPage.test.tsx` and confirm the new assertion is meaningful.
- [ ] Extract the full controlled field UI and helper controls from `AdminExerciseNewPage` into `AdminExerciseFields`.
- [ ] Run the focused test and confirm it passes.

### Task 2: Full edit behavior

**Files:**
- Modify: `frontend/src/features/admin/AdminExerciseEditPage.tsx`
- Modify: `frontend/src/features/admin/AdminExerciseFields.tsx`
- Test: `frontend/src/features/admin/AdminExerciseEditPage.test.tsx`

**Interfaces:**
- Consumes: `AdminExerciseFields` and existing `validateAdminExercise`/`toAdminExerciseCreate` helpers.
- Produces: a complete edit request containing all controlled exercise fields.

- [ ] Extend the edit test to change Persian/English names, equipment, difficulty, execution steps, and safety notes and assert the PATCH input.
- [ ] Run `npm test -- AdminExerciseEditPage.test.tsx` and confirm it fails because those controls are absent.
- [ ] Render the shared fields, add primary-media replacement support, and apply create-equivalent client/API validation.
- [ ] Run both admin exercise page tests and confirm they pass.

### Task 3: Readable card action and regression verification

**Files:**
- Modify: `frontend/src/features/exercises/exercises.css`
- Modify: `frontend/src/features/admin/adminStyles.test.ts`

**Interfaces:**
- Produces: white Edit-link text across normal, visited, hover, and focus states.

- [ ] Add a stylesheet assertion for white `.exercise-card__edit` text.
- [ ] Run the focused stylesheet test and confirm it fails on the current petrol color.
- [ ] Set the edit-link color to white without changing the Add Exercise action.
- [ ] Run frontend tests, lint, and build plus focused backend admin exercise tests.
- [ ] Commit and push the verified implementation.
