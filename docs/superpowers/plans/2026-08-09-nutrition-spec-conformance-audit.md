# Nutrition Specification Conformance Audit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close confirmed gaps between `fitsho-nutrition-core-spec-final.md` and the current Nutrition implementation without rerunning Tasks 0–2 or breaking existing data.

**Architecture:** Preserve legacy database columns and API input compatibility while removing obsolete Cooking behavior from current clients and planner inputs. Add missing lifecycle, tracking, photo-correction, access-control, and presentation behavior through existing Nutrition services and routes, using immutable revisions and current ownership patterns.

**Tech Stack:** FastAPI, SQLAlchemy 2, Alembic, PostgreSQL, Pydantic, React 19, TypeScript, React Router, Vitest.

## Global Constraints

- The updated Nutrition specification is the source of truth.
- Cooking and food preparation remain outside Nutrition.
- Existing stored values and historical snapshots remain readable.
- Unresolved food-preference text must not affect planner scoring.
- Every successful Nutrition plan requires exact-revision physician approval before activation.
- Pending drafts remain visible but cannot become adherence baselines.
- OpenRouter remains limited to consented food-photo estimation.
- Existing unrelated worktree changes must not be staged or rewritten.

---

### Task 1: Complete Task 2A compatibility cleanup

**Files:**
- Create: `backend/alembic/versions/20260809_56_resolve_nutrition_food_preferences.py`
- Modify: `backend/app/nutrition/models.py`
- Modify: `backend/app/nutrition/schemas.py`
- Modify: `backend/app/nutrition/service.py`
- Modify: `backend/app/nutrition/plan_service.py`
- Modify: `frontend/src/features/nutrition/types.ts`
- Modify: `frontend/src/features/nutrition/NutritionOnboardingFlow.tsx`
- Test: `backend/tests/nutrition/test_nutrition_scope_cleanup.py`
- Test: `frontend/src/features/nutrition/NutritionOnboardingFlow.test.tsx`

- [x] Add failing tests proving legacy Cooking values are ignored, only liked/disliked ordinary preferences are current, and unresolved text does not score.
- [x] Add nullable canonical food references to preference rows and deterministic alias resolution.
- [x] Preserve deprecated database/API compatibility while removing current-client Cooking payloads and dead Cooking UI.
- [x] Route planner preferences only through resolved canonical food IDs.
- [x] Run focused backend/frontend checks, commit, and push.

### Task 2: Complete physician lifecycle and laboratory workflow

**Files:**
- Create: `backend/alembic/versions/20260809_57_complete_nutrition_review_lifecycle.py`
- Modify: `backend/app/nutrition/clinical_service.py`
- Modify: `backend/app/nutrition/plan_editing.py`
- Modify: `backend/app/nutrition/router.py`
- Modify: `backend/app/nutrition/schemas.py`
- Test: `backend/tests/nutrition/test_clinical_review_api.py`

- [x] Add failing tests for assignment isolation, exact-revision approval, effective-date activation, atomic supersession, lab review, and same-session physician revision rebind.
- [x] Prevent one physician from taking over another physician's review.
- [x] Add structured physician food/quantity editing with complete deterministic revalidation and immutable revision history.
- [x] Add laboratory metadata/review endpoints for the assigned physician and explicit request transitions.
- [x] Persist explicit approval metadata and activation-safe audit events.
- [x] Run focused checks, commit, and push.

### Task 3: Complete tracking and photo correction contracts

**Files:**
- Modify: `backend/app/nutrition/tracking_service.py`
- Modify: `backend/app/nutrition/food_photo_service.py`
- Modify: `backend/app/nutrition/router.py`
- Modify: `backend/app/nutrition/schemas.py`
- Test: `backend/tests/nutrition/test_tracking_api.py`
- Test: `backend/tests/nutrition/test_food_photo_estimation.py`

- [x] Add failing tests for edit-own-entry, recent foods, planned-meal adjustment, and resolved photo-item corrections.
- [x] Add ownership-safe entry editing and recent-food APIs.
- [x] Add photo item remove/replace/quantity correction before confirmation.
- [x] Preserve allergen warning semantics for truthful actual intake.
- [x] Run focused checks, commit, and push.

### Task 4: Complete coordinated Nutrition frontend behavior

**Files:**
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/features/profile/ProfileRouteGuards.tsx`
- Modify: `frontend/src/features/nutrition/NutritionTrackingPage.tsx`
- Modify: `frontend/src/features/nutrition/NutritionLabsPage.tsx`
- Modify: `frontend/src/features/nutrition/NutritionSupplementsPage.tsx`
- Modify: `frontend/src/features/nutrition/PhysicianNutritionReviewPage.tsx`
- Modify: `frontend/src/features/nutrition/WeeklyNutritionPlan.tsx`
- Modify: `frontend/src/features/nutrition/api.ts`
- Test: matching Vitest files for each workflow

- [x] Add route, correction, history, laboratory, supplement, and physician-workspace tests.
- [x] Guard every Nutrition member route by product capability and the physician route by server-confirmed role behavior.
- [x] Add back navigation, loading/error/empty states, photo correction, tracking history filters, laboratory metadata/delete, supplement history, and physician review details.
- [x] Replace invalid feedback values and expose only specification-approved actions.
- [x] Run frontend tests, lint, build, commit, and push.

### Task 5: Correct member catalogue currency and provenance presentation

**Files:**
- Modify: `backend/app/nutrition/catalogue_view.py`
- Modify: `backend/app/nutrition/schemas.py`
- Modify: `frontend/src/features/nutrition/FoodCataloguePage.tsx`
- Modify: `frontend/src/features/nutrition/api.ts`
- Test: member catalogue backend/frontend tests

- [x] Add failing tests that current member-facing money is expressed in IRR and missing prices remain unavailable.
- [x] Keep legacy Toman storage fields for compatibility but expose an exact IRR reference in the member read model.
- [x] Render weekly prices in IRR with source and observation/acceptance date.
- [x] Run focused checks, commit, and push.

### Task 6: Final conformance verification and documentation

**Files:**
- Modify: `docs/nutrition-implementation-design.md`
- Modify: `docs/nutrition-api.md`
- Modify: `docs/nutrition-migrations.md`
- Modify: `docs/nutrition-medical-review.md`
- Modify: `docs/nutrition-security-privacy.md`

- [x] Recheck every Section 48 task and Section 49 acceptance scenario against executable code/tests.
- [x] Run Alembic one-head, current upgrade, and fresh-zero migration checks.
- [x] Run full backend tests, ruff, mypy, frontend tests, lint, and build.
- [x] Recreate the local backend, verify OpenAPI and frontend routes, review the complete diff, commit, push, and report remaining external-only limitations truthfully.
