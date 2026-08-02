# Training Template Library Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an admin-only, seeded library of two-to-six-day hypertrophy template structures.

**Architecture:** A `training_templates` backend module owns normalized template, day, and slot entities plus idempotent seed data. Admin routes expose the fully loaded graph, while a focused React page presents filters and read-only details. Nullable exercise links deliberately represent curated slots missing from the exercise catalog.

**Tech Stack:** FastAPI, SQLAlchemy, Alembic, Pydantic, pytest, React, TypeScript, Vitest.

## Global Constraints

- No public endpoint, user route, or training-engine selection behavior is added.
- The seed must contain at least five templates for every days-per-week value from 2 through 6.
- A slot must either reference a real `exercises.id` or visibly remain an unresolved placeholder.
- Use test-first implementation; run backend and frontend gates before merge.

---

### Task 1: Persist and seed template structures

**Files:**
- Create: `backend/app/training_templates/models.py`, `seed_data.py`, `service.py`, `seed.py`
- Create: `backend/alembic/versions/20260802_15_create_training_program_templates.py`
- Test: `backend/tests/training_templates/test_seed.py`

- [ ] Write a failing seed test asserting five templates per 2–6 day bucket and a nullable unresolved slot.
- [ ] Implement normalized models, migration, idempotent seeding, and catalog-slug resolution.
- [ ] Run the test and Alembic upgrade; commit `feat(training-templates): persist curated template library`.

### Task 2: Expose an admin-only template API

**Files:**
- Modify: `backend/app/admin/router.py`, `schemas.py`
- Modify: `backend/app/admin/service.py`
- Test: `backend/tests/admin/test_training_template_api.py`

- [ ] Write failing route tests for authentication, admin authorization, days filter, and slot serialization.
- [ ] Implement eager-loading service and read-only protected routes.
- [ ] Run API tests; commit `feat(admin): expose training template library`.

### Task 3: Add the admin library page

**Files:**
- Create: `frontend/src/features/admin/AdminTrainingTemplatesPage.tsx`, `.test.tsx`
- Modify: `frontend/src/features/admin/types.ts`, `api.ts`, `admin.css`, `frontend/src/i18n/fa.ts`, `en.ts`, `frontend/src/App.tsx`

- [ ] Write a failing UI test for day tabs, focus labels, resolved exercise, and unresolved placeholder.
- [ ] Implement the read-only page and protected route.
- [ ] Run Vitest, lint, and build; commit `feat(admin): add training template library page`.

### Task 4: Verify integration and deliver

**Files:**
- Modify only if tests expose integration defects.
- [ ] Run the full backend suite, Ruff, mypy, full frontend suite, lint, and production build.
- [ ] Apply migration and seed to the active 317-exercise database only after checks pass.
- [ ] Fast-forward merge the feature branch to `main`, push it, remove the merged feature branch/worktree, and verify 5173 and the admin API.
