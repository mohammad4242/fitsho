# Nutrition Program Catalogue Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an admin-only seven-day Nutrition Program Catalogue grouped by diet style and composed only from verified Meal Catalogue meals.

**Architecture:** Add normalized program, day, and slot tables inside the nutrition module. A focused service owns validation, replacement, filtering, archive, and restore; existing admin nutrition routing exposes the service without changing planner behavior. The React admin workspace follows the Training Program Templates interaction pattern and uses category-specific Meal Catalogue selectors.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy, Alembic, PostgreSQL, Pydantic, pytest, React 19, TypeScript, Vite, Vitest, i18next.

## Global Constraints

- Do not modify Food Catalogue, Meal Catalogue, or nutrition planner/engine behavior.
- Programs contain exactly seven days and no calorie, nutrient, ingredient-quantity, or fitness-goal fields.
- Diet styles are `economy`, `balanced_iranian`, `high_protein_gym`, `quick_easy`, and `premium_varied`.
- Every slot references an existing verified Meal Catalogue meal of the matching category.
- Breakfast, lunch, snack, and dinner are required every day.
- Post-workout is controlled globally with per-day overrides and remains optional.
- Do not seed weekly programs.
- Preserve unrelated work in the current dirty checkout and stage only feature-specific changes.

---

### Task 1: Backend domain and migration

**Files:**
- Modify: `backend/app/nutrition/enums.py`
- Modify: `backend/app/nutrition/models.py`
- Create: `backend/alembic/versions/20260812_64_add_nutrition_program_catalogue.py`
- Create: `backend/tests/nutrition/test_program_catalogue.py`

**Interfaces:**
- Produces: `NutritionDietStyle`, `NutritionProgram`, `NutritionProgramDay`, and `NutritionProgramSlot`.
- Produces database constraints for seven day numbers, unique program days, and unique day slots.

- [ ] **Step 1: Write failing model and migration tests**

Add tests that instantiate a seven-day relational program and assert slot meal relationships, enum values, and archive fields. Assert Alembic metadata reaches `20260812_64` through the existing fixture.

- [ ] **Step 2: Run the tests and verify RED**

Run: `uv run pytest tests/nutrition/test_program_catalogue.py -q`

Expected: collection/import failure because the new domain types do not exist.

- [ ] **Step 3: Implement enums, models, and migration**

Add the five diet-style values. Create `nutrition_programs`, `nutrition_program_days`, and `nutrition_program_slots` with UUID primary keys, cascading program/day ownership, `RESTRICT` meal references, timestamps, active/archive fields, and explicit unique/check constraints. The migration creates no program rows.

- [ ] **Step 4: Run model tests and static checks**

Run: `uv run pytest tests/nutrition/test_program_catalogue.py -q`

Run: `uv run ruff check app/nutrition/enums.py app/nutrition/models.py tests/nutrition/test_program_catalogue.py alembic/versions/20260812_64_add_nutrition_program_catalogue.py`

### Task 2: Backend schemas, service, and admin API

**Files:**
- Modify: `backend/app/nutrition/schemas.py`
- Create: `backend/app/nutrition/program_catalogue.py`
- Modify: `backend/app/nutrition/router.py`
- Modify: `backend/tests/nutrition/test_program_catalogue.py`

**Interfaces:**
- Consumes: models from Task 1 and existing `NutritionCatalogueMeal` records.
- Produces: `NutritionProgramWrite`, detail/list responses, `list_programs`, `get_program`, `create_program`, `update_program`, `archive_program`, and `restore_program`.
- Produces: `/api/v1/nutrition/admin/programs` CRUD/filter endpoints.

- [ ] **Step 1: Write failing API behavior tests**

Cover anonymous/member rejection, successful create/read/update, diet-style filtering, exact seven-day validation, verified meal enforcement, category enforcement, global/per-day post-workout rules, archive visibility, and restore.

- [ ] **Step 2: Run the API tests and verify RED**

Run: `uv run pytest tests/nutrition/test_program_catalogue.py -q`

Expected: 404 responses for the missing routes and import failures for missing schemas.

- [ ] **Step 3: Implement schemas and service**

Use Pydantic `extra="forbid"`, exact seven-day validation, unique slots, and deterministic response ordering. Validate all linked meals in one query, require `verified`, require category equality, and replace child collections transactionally on update.

- [ ] **Step 4: Implement protected routes**

Add list/detail/create/update/delete/restore routes under the nutrition admin prefix. Require `AdminUser`; require trusted origin for every mutation; translate domain validation errors to 422 and missing records to 404.

- [ ] **Step 5: Run backend focused verification**

Run: `uv run pytest tests/nutrition/test_program_catalogue.py tests/nutrition/test_meal_catalogue.py tests/admin/test_training_template_api.py -q`

Run: `uv run ruff check app/nutrition tests/nutrition/test_program_catalogue.py alembic/versions/20260812_64_add_nutrition_program_catalogue.py`

Run: `uv run mypy app`

### Task 3: Frontend API, catalogue page, and editor

**Files:**
- Modify: `frontend/src/features/admin/types.ts`
- Modify: `frontend/src/features/admin/api.ts`
- Modify: `frontend/src/features/admin/api.test.ts`
- Create: `frontend/src/features/admin/AdminNutritionProgramsPage.tsx`
- Create: `frontend/src/features/admin/AdminNutritionProgramsPage.test.tsx`
- Create: `frontend/src/features/admin/AdminNutritionProgramEditorPage.tsx`
- Create: `frontend/src/features/admin/AdminNutritionProgramEditorPage.test.tsx`
- Modify: `frontend/src/features/admin/admin.css`

**Interfaces:**
- Consumes: backend program endpoints and existing Meal Catalogue endpoint.
- Produces: typed list/detail/create/update/archive/restore API helpers and two admin pages.

- [ ] **Step 1: Write failing API and page tests**

Assert exact request paths and methods, diet/lifecycle filters, localized list rendering, seven day sections, category-specific meal loading, global/per-day post-workout behavior, save payload shape, archive, and restore.

- [ ] **Step 2: Run frontend tests and verify RED**

Run: `npm run test -- --run src/features/admin/api.test.ts src/features/admin/AdminNutritionProgramsPage.test.tsx src/features/admin/AdminNutritionProgramEditorPage.test.tsx`

Expected: module/import failures for the missing pages and API helpers.

- [ ] **Step 3: Implement types and API helpers**

Mirror the backend enum and response/write shapes. Encode filters with `URLSearchParams`; use `DELETE` for archive and `POST` for restore.

- [ ] **Step 4: Implement catalogue page**

Reuse the admin page shell, add diet-style and lifecycle filters, show program state and seven-day meal summaries, and expose create/edit/archive/restore actions.

- [ ] **Step 5: Implement weekly editor**

Render bilingual identity fields and seven accessible day cards. Load verified meals by category, use select controls for the four required slots, and show post-workout selection only when both global and daily controls are enabled.

- [ ] **Step 6: Add responsive styles and run focused checks**

Use existing admin design tokens. Render a weekly rail at desktop widths and stacked cards on mobile without horizontal page overflow.

Run: `npm run test -- --run src/features/admin/api.test.ts src/features/admin/AdminNutritionProgramsPage.test.tsx src/features/admin/AdminNutritionProgramEditorPage.test.tsx`

Run: `npm run lint`

### Task 4: Routes, navigation, translations, and full verification

**Files:**
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/shared/AuthenticatedHeader.tsx`
- Modify: `frontend/src/i18n/en.ts`
- Modify: `frontend/src/i18n/fa.ts`
- Modify: relevant existing route/header tests if required by their public behavior

**Interfaces:**
- Consumes: pages from Task 3.
- Produces: three protected admin routes and a localized admin navigation entry.

- [ ] **Step 1: Write failing route/navigation assertions**

Extend existing behavior tests so an administrator can open the catalogue and editor routes and sees the localized Nutrition Program Catalogue navigation entry.

- [ ] **Step 2: Run the affected tests and verify RED**

Run the exact modified Vitest files with `npm run test -- --run`.

- [ ] **Step 3: Add lazy routes, navigation, and translations**

Add list/new/edit routes within `AdminRoute`, the active contextual header item, and complete Persian/English strings for diet styles, lifecycle, days, slots, validation, loading, errors, and actions.

- [ ] **Step 4: Run complete verification**

Run from `backend/`: `uv run alembic upgrade head`, `uv run pytest`, `uv run ruff check`, and `uv run mypy app`.

Run from `frontend/`: `npm run test`, `npm run lint`, and `npm run build`.

- [ ] **Step 5: Review scope and Git diff**

Confirm no weekly program seeds, planner changes, Food Catalogue changes, Meal Catalogue behavior changes, secrets, or unrelated WIP hunks are staged.

- [ ] **Step 6: Commit and push focused implementation**

Commit message: `feat(nutrition): add admin nutrition program catalogue`

Push the current branch only after all verification succeeds.
