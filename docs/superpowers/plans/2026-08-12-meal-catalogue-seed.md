# Meal Catalogue Seed Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Publish source-backed Iranian breads and seed the existing Meal Catalogue with the 38 requested coded templates.

**Architecture:** Extend the existing Food Catalogue seed metadata so each bread composition retains its own provenance and palm portion. Add an immutable unique meal code across the existing model/API/UI, then make the existing Meal Catalogue seeder idempotently upsert the requested templates by code without deleting custom meals.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy, Alembic, PostgreSQL, Pydantic, pytest, React 19, TypeScript, Vitest.

## Global Constraints

- Preserve the existing normalized Food Catalogue and Meal Catalogue tables.
- Every meal item references an existing `nutrition_catalogue_foods.id`.
- Never duplicate nutrition values inside meal templates.
- Never write unsupported nutrient values as zero.
- Sangak is the default bread in bread-bearing seeded meals.
- Seed exactly 8 breakfasts, 13 lunches, 8 dinners, 8 snacks, and 1 post-workout meal.
- Post-workout contains only `PW01` and remains optional later.
- Do not modify the nutrition planner/engine or seed Nutrition Programs.
- Preserve unrelated dirty-worktree changes and stage only task files.

---

### Task 1: Source-backed Iranian breads

**Files:**
- Modify: `backend/app/nutrition/catalogue_seed_data.py`
- Modify: `backend/app/nutrition/food_catalogue.py`
- Create: `backend/alembic/versions/20260812_65_verify_iranian_breads.py`
- Modify: `backend/tests/nutrition/test_food_catalogue.py`

**Interfaces:**
- Produces: per-food/per-nutrient seed provenance and a `palm` portion for each Iranian bread.
- Produces: four verified bread rows with source-backed primary nutrients.

- [ ] **Step 1: Write failing bread catalogue tests**

Assert literal per-100-g macro values for all four bread slugs, source metadata on representative composition rows, absence of unsupported values, and palm grams of 30/30/30/7.5.

- [ ] **Step 2: Run RED**

Run: `cd backend && uv run pytest tests/nutrition/test_food_catalogue.py -q`

Expected: failures because breads are draft and have no compositions or portions.

- [ ] **Step 3: Implement seed metadata and migration**

Add bread-specific composition records and palm portions. Update the seeder to use bread-specific source metadata while retaining the current USDA behavior for all other foods. The migration updates only the four existing bread identities, compositions, portions, and verification state.

- [ ] **Step 4: Run GREEN and checks**

Run: `cd backend && uv run pytest tests/nutrition/test_food_catalogue.py -q`

Run: `cd backend && uv run ruff check app/nutrition/catalogue_seed_data.py app/nutrition/food_catalogue.py tests/nutrition/test_food_catalogue.py alembic/versions/20260812_65_verify_iranian_breads.py`

- [ ] **Step 5: Commit and push**

Commit: `feat(nutrition): verify source-backed Iranian breads`

### Task 2: Stable meal codes

**Files:**
- Modify: `backend/app/nutrition/models.py`
- Modify: `backend/app/nutrition/schemas.py`
- Modify: `backend/app/nutrition/meal_catalogue.py`
- Create: `backend/alembic/versions/20260812_66_add_meal_catalogue_codes.py`
- Modify: `backend/tests/nutrition/test_meal_catalogue.py`
- Modify: `frontend/src/features/admin/types.ts`
- Modify: `frontend/src/features/admin/AdminMealCataloguePage.tsx`
- Modify: `frontend/src/features/admin/AdminMealCatalogueEditorPage.tsx`
- Modify: relevant meal catalogue frontend tests and translations

**Interfaces:**
- Produces: required unique `NutritionCatalogueMeal.code` and API `code` field.
- Produces: create-time code assignment and edit-time code immutability.

- [ ] **Step 1: Write failing backend and frontend code-contract tests**

Assert unique uppercase code validation, response serialization, duplicate rejection, immutable update behavior, catalogue display, and disabled edit field.

- [ ] **Step 2: Run RED**

Run focused backend `test_meal_catalogue.py` and frontend meal catalogue tests; expect missing `code` failures.

- [ ] **Step 3: Implement schema/model/API/UI and migration**

Add and backfill the column, unique constraint, Pydantic validation, service immutability check, TypeScript fields, localized labels, and code display/input.

- [ ] **Step 4: Run GREEN and checks**

Run focused backend/frontend tests, Ruff, and frontend lint.

- [ ] **Step 5: Commit and push**

Commit: `feat(nutrition): add stable meal catalogue codes`

### Task 3: Complete 38-meal seed

**Files:**
- Modify: `backend/app/nutrition/meal_catalogue.py`
- Modify: `backend/app/nutrition/seed_catalogue.py`
- Modify: `backend/tests/nutrition/test_meal_catalogue.py`

**Interfaces:**
- Consumes: verified Food Catalogue rows and immutable meal codes.
- Produces: idempotent `seed_meal_catalogue(db)` with exact requested category/code counts.

- [ ] **Step 1: Write failing seed behavior tests**

Assert the literal code sets, exact category counts, exact `PW01` ingredients, Sangak on bread-bearing templates, unique food links, complete bounds/roles, verified status, and idempotency without deleting a custom meal.

- [ ] **Step 2: Run RED**

Run: `cd backend && uv run pytest tests/nutrition/test_meal_catalogue.py -q`

Expected: only the five legacy seed rows exist.

- [ ] **Step 3: Implement the seed definitions and upsert**

Define all 38 bilingual templates with existing slugs and explicit bounds/roles. Upsert by code with deterministic UUIDs, preserve legacy matching IDs, and extend the catalogue seed command to seed foods before meals.

- [ ] **Step 4: Run GREEN and backend focused checks**

Run meal, food, program-catalogue, and weekly-plan tests plus Ruff and `mypy app`.

- [ ] **Step 5: Commit and push**

Commit: `feat(nutrition): seed complete meal catalogue`

### Task 4: Full and runtime verification

**Files:**
- No intended source changes.

**Interfaces:**
- Validates migration, complete application regression suite, and active admin grouping.

- [ ] **Step 1: Run full backend verification**

Run from `backend/`: `uv run alembic upgrade head`, `uv run pytest`, `uv run ruff check`, and `uv run mypy app`.

- [ ] **Step 2: Run full frontend verification**

Run from `frontend/`: `npm run test`, `npm run lint`, and `npm run build`.

- [ ] **Step 3: Seed and inspect the active database**

Run the catalogue seed command, assert 38 requested codes grouped 8/13/8/8/1, and confirm all meal item `food_id` values resolve.

- [ ] **Step 4: Verify the running admin surface**

Rebuild/apply migrations if needed, confirm OpenAPI code fields and authenticated grouped admin responses, and keep the mobile Vite listener available.

- [ ] **Step 5: Review Git scope and push final state**

Confirm task commits are pushed and unrelated WIP remains unstaged.
