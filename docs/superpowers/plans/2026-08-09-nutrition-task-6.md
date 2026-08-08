# Nutrition Task 6 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Execute inline with test-driven development. Do not delegate this repository task.

**Goal:** Build a deterministic, scientific, budget-aware seven-day Nutrition planner that persists immutable visible drafts and keeps unsuccessful generation outcomes separate.

**Architecture:** A pure planning policy/engine consumes immutable snapshots of the current estimate, verified catalogue, accepted prices, exclusions, safety decision, and meal structure. A persistence service stores either an auditable generation outcome or an immutable plan revision plus its required physician-review request. FastAPI exposes generation, latest draft, and history; the existing Nutrition frontend renders the visible draft and review state.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy, PostgreSQL, Alembic, pytest, React 19, TypeScript, Vitest.

## Global Constraints

- Only `SUCCESS` creates a plan revision and physician-review request.
- Generated plans are visible but never active before real physician approval.
- Planner inputs, prices, policies, foods, quantities, totals, warnings, and explanations are immutable snapshots.
- Use accepted current Fitsho database prices only; never fetch providers during generation.
- `STRICT` budget is a hard ceiling; `FLEXIBLE` uses a versioned overage cap.
- Missing required price coverage returns `LIVE_PRICE_UNAVAILABLE/INSUFFICIENT_PRICE_COVERAGE`.
- Allergy, medical, slot-role, upper-limit, and price requirements are hard filters.
- Micronutrient gaps are reported as dietary-reference gaps, never diagnoses.
- Do not start Task 7 editing or shopping-list behavior.

---

### Task 1: Pure deterministic planner policy

**Files:**
- Create: `backend/app/nutrition/planner_policy.py`
- Create: `backend/app/nutrition/planner_engine.py`
- Test: `backend/tests/nutrition/test_planner_engine.py`

**Produces:** Versioned slot distribution, price conversion, candidate filtering, scoring, portion bounds, budget validation, micronutrient repair, and structured outcomes.

- [ ] Write tests for exact slot counts, deterministic selection, allergies, role filtering, strict/flexible budgets, missing coverage, repetitions, micronutrient scoring/repair, UL enforcement, and immutable result values.
- [ ] Run the tests and confirm failures for missing interfaces.
- [ ] Implement the smallest deterministic policy/engine satisfying each contract.
- [ ] Run tests and refactor only while green.

### Task 2: Immutable persistence and lifecycle

**Files:**
- Modify: `backend/app/nutrition/enums.py`
- Modify: `backend/app/nutrition/models.py`
- Create: `backend/alembic/versions/20260809_42_add_weekly_nutrition_planner.py`
- Test: `backend/tests/nutrition/test_weekly_plan_service.py`

**Produces:** `NutritionPlanGeneration`, `NutritionWeeklyPlan`, immutable revisions, days, meals, foods, nutrient comparisons, and exact-revision physician review.

- [ ] Write failing persistence tests for failure/result separation, seven-day structure, snapshots, history, physician gate, and immutability.
- [ ] Add normalized tables, constraints, indexes, relationships, and policy seed.
- [ ] Implement service mapping engine results to persistence rows.
- [ ] Run migration and persistence tests.

### Task 3: Generation and read APIs

**Files:**
- Modify: `backend/app/nutrition/schemas.py`
- Modify: `backend/app/nutrition/router.py`
- Create: `backend/app/nutrition/plan_service.py`
- Test: `backend/tests/nutrition/test_weekly_plan_api.py`

**Produces:** `POST /api/v1/nutrition/plans`, `GET /plans/latest`, and `GET /plans/history`.

- [ ] Write failing API tests for success, safety block, price coverage, ownership, visibility, history, and no active state before approval.
- [ ] Implement schemas, exception mapping, endpoints, and deterministic explanations.
- [ ] Run API tests and related Nutrition regressions.

### Task 4: User-visible Nutrition draft

**Files:**
- Modify: `frontend/src/features/nutrition/api.ts`
- Modify: `frontend/src/features/nutrition/api.test.ts`
- Modify: `frontend/src/features/nutrition/NutritionEstimatePage.tsx`
- Modify: `frontend/src/features/nutrition/NutritionEstimatePage.test.tsx`
- Modify: `frontend/src/i18n/fa.ts`
- Modify: `frontend/src/i18n/en.ts`

**Produces:** Generation action, structured outcome, complete seven-day draft, costs, targets versus planned values, warnings, and pending-physician-review state.

- [ ] Write failing UI/API-client tests.
- [ ] Implement bilingual, RTL-safe loading/error/outcome/draft UI.
- [ ] Run focused frontend tests, build, and lint.

### Task 5: Verification and delivery

**Files:** Task 6 files only.

- [ ] Apply migrations on the isolated Task 6 database.
- [ ] Run full backend tests, Ruff, mypy, frontend tests, build, and lint.
- [ ] Fix only Task 6 regressions.
- [ ] Commit with a focused Conventional Commit message and push `nutrition`.
- [ ] Report changes, migration, verification, commit hash, and stop before Task 7.
