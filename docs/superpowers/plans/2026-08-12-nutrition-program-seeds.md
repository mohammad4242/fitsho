# Nutrition Program Seeds and Meal-Count Adaptation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Seed 25 canonical weekly Nutrition Programs, select and adapt one deterministically from each user's profile, constrain planner portions to that program, and support trackable Friday Free Meals.

**Architecture:** Extend the existing Nutrition Program slot model with an explicit special-slot kind and nullable Meal Catalogue relationship. Add a canonical seed registry and a pure deterministic selector/adapter that produces a fixed seven-day meal schedule for the existing bounded planner. Reuse nutrition tracking and food-photo estimation for Free Meal actual-intake entry and macro prefill.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy, Alembic, PostgreSQL, Pydantic, Pytest, React 19, TypeScript, Vite, Vitest.

## Global Constraints

- Seed exactly 25 owned templates and exactly five per diet style.
- Use only the canonical Meal Catalogue UUIDs supplied by the product specification.
- Never modify, copy, or recreate Food Catalogue or Meal Catalogue rows.
- Free Meal is a special slot with no Meal Catalogue UUID.
- The engine may adjust only existing meal ingredient grams inside `min_grams` and `max_grams`.
- Meal frequency changes distribution, not the user's daily nutrition targets.
- Selection, adaptation, extra meals, extra snacks, and portion adjustment remain deterministic.
- Photo estimation is optional and reuses the existing tracking photo service.

---

### Task 1: Special Program Slots and Stable Program Codes

**Files:**
- Modify: `backend/app/nutrition/enums.py`
- Modify: `backend/app/nutrition/models.py`
- Modify: `backend/app/nutrition/schemas.py`
- Modify: `backend/app/nutrition/program_catalogue.py`
- Create: `backend/alembic/versions/20260812_66_add_program_special_slots.py`
- Test: `backend/tests/nutrition/test_program_catalogue.py`

**Interfaces:**
- Produces: `NutritionProgramSlotKind` with `catalogue_meal` and `free_meal`.
- Produces: `NutritionProgram.code: str`, `NutritionProgramSlot.kind`, nullable `meal_id`.
- Produces: slot write/response schemas with `kind` and optional `meal_id`/`meal`.

- [ ] Write API and model tests proving catalogue slots require a matching verified UUID, Free Meal requires `meal_id=None`, Friday replaces lunch, and program codes are unique.
- [ ] Run `pytest tests/nutrition/test_program_catalogue.py -q` from `backend/` and confirm the new tests fail for missing fields/constraints.
- [ ] Add the enum, ORM fields, Pydantic validation, response mapping, and Alembic check constraints.
- [ ] Run the focused test, `ruff check app/nutrition tests/nutrition/test_program_catalogue.py`, and `mypy app`.
- [ ] Commit with `feat(nutrition): support free meal program slots`.

### Task 2: Canonical 25-Program Seed Registry

**Files:**
- Create: `backend/app/nutrition/program_catalogue_seed_data.py`
- Create: `backend/app/nutrition/seed_program_catalogue.py`
- Modify: `backend/app/nutrition/program_catalogue.py`
- Test: `backend/tests/nutrition/test_program_catalogue_seed.py`

**Interfaces:**
- Produces: `CANONICAL_MEAL_REGISTRY: dict[str, CanonicalMeal]`.
- Produces: `SEED_PROGRAMS: tuple[ProgramSeed, ...]` with exact 25 seven-day matrices.
- Produces: `seed_program_catalogue(db: Session, *, commit: bool = True) -> list[NutritionProgram]`.

- [ ] Write seed tests for exact 25/5-per-style counts, complete UUID equality, names/categories/status validation, Gym and Economy rules, Friday Free Meal, idempotency, and absence of a fake meal.
- [ ] Run `pytest tests/nutrition/test_program_catalogue_seed.py -q` and confirm failure because the registry/seed does not exist.
- [ ] Encode the supplied canonical UUID registry and all 25 exact weekly matrices; resolve by exact code and UUID only.
- [ ] Implement idempotent upsert of owned program codes, rejecting any catalogue mismatch without modifying Meal Catalogue rows.
- [ ] Run focused tests, Ruff, and mypy.
- [ ] Commit with `feat(nutrition): seed 25 canonical weekly programs`.

### Task 3: Profile-Based Selection and Meal-Count Adapter

**Files:**
- Create: `backend/app/nutrition/program_selection.py`
- Create: `backend/app/nutrition/program_adaptation.py`
- Test: `backend/tests/nutrition/test_program_selection.py`
- Test: `backend/tests/nutrition/test_program_adaptation.py`

**Interfaces:**
- Produces: `select_program(programs, profile, fitness_goal, structured_exercise, user_id) -> NutritionProgram`.
- Produces: `adapt_program(program, main_bucket, snack_bucket, training_day_indexes, include_post_workout) -> AdaptedWeek`.
- Produces: immutable `AdaptedSlot(kind, role, meal_id, category)` and `AdaptedDay(day_index, slots)`.

- [ ] Write failing selector tests: muscle/recomposition plus resistance training prefers Gym; economical/strict profiles prefer Economy; simple/no-cooking profiles prefer Quick; flexible/high-variety profiles prefer Premium; balanced is fallback; variant tie-breaking is stable.
- [ ] Write failing adapter tests for exact 2/3/4 main meal shapes, no duplicate breakfast, approved extra LU/DN only, Friday Free Meal, 0/1/2/3 snacks, deterministic no-duplicate additions, and independent training-day PW01.
- [ ] Implement the pure selector and adapter with stable code/UUID ordering and no random state.
- [ ] Run both focused tests, Ruff, and mypy.
- [ ] Commit with `feat(nutrition): adapt programs to member meal frequency`.

### Task 4: Constrain the Existing Planner to the Adapted Program

**Files:**
- Modify: `backend/app/nutrition/planner_engine.py`
- Modify: `backend/app/nutrition/plan_service.py`
- Modify: `backend/app/nutrition/models.py`
- Modify: `backend/app/nutrition/schemas.py`
- Create: `backend/alembic/versions/20260812_67_link_plans_to_nutrition_programs.py`
- Test: `backend/tests/nutrition/test_planner_engine.py`
- Test: `backend/tests/nutrition/test_weekly_plan_api.py`

**Interfaces:**
- Extends: `PlannerInput.template_schedule: tuple[PlannerDaySchedule, ...]`.
- Produces: `NutritionWeeklyPlan.program_id` and program code in the immutable input snapshot.
- Extends: weekly plan meals to represent Free Meal without foods/catalogue UUID.

- [ ] Write failing planner tests proving exact scheduled templates are used, ingredient grams remain bounded, daily target inputs are unchanged across meal counts/PW01, and Free Meal is excluded from portion optimization.
- [ ] Write failing service/API tests proving automatic program selection, program provenance, correct meal/snack counts, and no out-of-program template IDs.
- [ ] Modify the existing planner day builder to consume the adapted schedule while retaining its nutrient, upper-limit, exclusion, preference, and budget checks.
- [ ] Persist program provenance and special weekly-plan meals; redistribute target shares across optimized non-Free-Meal slots without changing total daily targets.
- [ ] Run focused planner/weekly API tests, Ruff, and mypy.
- [ ] Commit with `feat(nutrition): constrain plans to selected weekly programs`.

### Task 5: Free Meal Tracking and Photo-Prefill Contract

**Files:**
- Modify: `backend/app/nutrition/schemas.py`
- Modify: `backend/app/nutrition/router.py`
- Modify: `backend/app/nutrition/tracking_service.py`
- Modify: `backend/app/nutrition/food_photo_service.py`
- Test: `backend/tests/nutrition/test_tracking_api.py`
- Test: `backend/tests/nutrition/test_food_photo_estimation.py`

**Interfaces:**
- Produces: `FreeMealTrackingInput(entry_date, planned_meal_id, calories, protein_g, carbohydrate_g, fat_g)`.
- Produces: `PUT /tracking/free-meals/{planned_meal_id}` returning the daily summary.
- Extends: photo confirmation with optional Free Meal preview context returning macro totals without creating normal tracking entries; default behavior remains unchanged.

- [ ] Write failing tests for ownership/date validation, four macro persistence, idempotent update, same-day aggregation, unchanged planned targets, and Free Meal-only planned meal association.
- [ ] Write failing tests for optional photo preview totals and backward-compatible normal photo confirmation.
- [ ] Implement one Free Meal consumption entry using existing tracking tables and a dedicated source enum; calculate photo macro preview from resolved catalogue foods without double logging.
- [ ] Run focused tracking/photo tests, Ruff, and mypy.
- [ ] Commit with `feat(nutrition): track free meal macros and photo estimates`.

### Task 6: Admin Program Labels and Special Slot Editing

**Files:**
- Modify: `frontend/src/features/admin/types.ts`
- Modify: `frontend/src/features/admin/AdminNutritionProgramsPage.tsx`
- Modify: `frontend/src/features/admin/AdminNutritionProgramEditorPage.tsx`
- Modify: `frontend/src/features/admin/AdminNutritionProgramsPage.test.tsx`
- Modify: `frontend/src/features/admin/AdminNutritionProgramEditorPage.test.tsx`
- Modify: `frontend/src/i18n/fa.ts`
- Modify: `frontend/src/i18n/en.ts`

**Interfaces:**
- Catalogue labels: `meal_code — Persian meal name`; English name remains secondary.
- Free Meal label: `وعده آزاد`.

- [ ] Add failing UI tests for program code, seven days, slot type, exact bilingual meal labels, no primary UUID, and Free Meal display/editor serialization.
- [ ] Run the two focused Vitest files and confirm expected failures.
- [ ] Update TypeScript contracts and admin list/editor rendering while preserving existing filters and lifecycle actions.
- [ ] Run focused tests, `npm run lint`, and `npm run build`.
- [ ] Commit with `feat(admin): show coded meals and free slots in nutrition programs`.

### Task 7: Member Free Meal UI and Automatic Photo Return

**Files:**
- Modify: `frontend/src/features/nutrition/types.ts`
- Modify: `frontend/src/features/nutrition/api.ts`
- Modify: `frontend/src/features/nutrition/WeeklyNutritionPlan.tsx`
- Modify: `frontend/src/features/nutrition/NutritionTrackingPage.tsx`
- Modify: `frontend/src/features/nutrition/NutritionEstimatePage.test.tsx`
- Modify: `frontend/src/features/nutrition/NutritionWorkflowPages.test.tsx`
- Modify: `frontend/src/features/nutrition/nutritionEstimate.css`

**Interfaces:**
- Free Meal card owns four editable macro inputs and optional photo link.
- Navigation state/query carries `entryDate`, `plannedMealId`, and return location.
- Confirmed photo preview returns to the same day, pre-fills available macros, and does not double-log intake.

- [ ] Add failing UI/API tests for Persian guidance, four inputs, validation, save/total refresh, optional photo navigation, AI confirmation return/prefill, and unchanged planned target display.
- [ ] Run focused Vitest files and confirm expected failures.
- [ ] Implement the Free Meal card, API calls, navigation context, preview-only photo confirmation, and responsive styles.
- [ ] Run focused tests, lint, and build.
- [ ] Commit with `feat(nutrition): add free meal macro tracking flow`.

### Task 8: Full Verification and Runtime Seed

**Files:**
- Verify only; change files only for discovered regressions.

**Interfaces:**
- Runtime command: `cd backend && python -m app.nutrition.seed_program_catalogue`.

- [ ] Run `pytest`, `ruff check`, and `mypy app` from `backend/`.
- [ ] Run `npm run test`, `npm run lint`, and `npm run build` from `frontend/`.
- [ ] Run `alembic heads`, `alembic upgrade head`, seed the active database, and query exact counts/style distribution plus canonical UUID integrity.
- [ ] Review `git diff --check`, changed-file scope, and secret/untracked-file safety.
- [ ] Commit only any necessary verification fixes with a behavior-specific Conventional Commit message.
- [ ] Push the current branch and hand off exact member/admin test steps.
