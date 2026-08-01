# Workout Generation Method Implementation Plan

> **For agentic workers:** Execute this plan inline with test-first checkpoints.

**Goal:** Let each user persistently choose Fitsho Coach or AI for future workout-plan generation.

**Architecture:** Store a `workout_generation_method` preference on `user_profiles`, defaulting to `fitsho_coach`. The workout dependency resolves AI model candidates only when the profile requests AI. The service keeps the deterministic domain engine as the default path and uses the existing AI prompt/provider/validator path for AI requests; generated plans retain their provider, model, and method metadata.

**Tech Stack:** FastAPI, SQLAlchemy, Alembic, Pydantic, React/TypeScript, Vitest, pytest.

## Global Constraints

- Existing users must default to `fitsho_coach`.
- Changing the preference affects the next generation only.
- AI model selection remains controlled by admin routing settings.
- Do not silently fall back from AI to Fitsho Coach.
- Preserve existing profile and workout API compatibility apart from additive fields.

### Task 1: Persist the user generation preference

**Files:**
- Modify: `backend/app/profile/enums.py`, `backend/app/profile/models.py`, `backend/app/profile/schemas.py`, `backend/app/profile/service.py`, `backend/app/profile/router.py`
- Create: `backend/alembic/versions/20260801_12_add_workout_generation_method.py`
- Test: `backend/tests/profile/test_profile_api.py`

- [ ] Add the enum, nullable-free model column with server default `fitsho_coach`, additive create/update/response schema fields, and service mapping.
- [ ] Add migration and test create/read/update/default behavior.
- [ ] Run the focused profile tests.

### Task 2: Route generation through the selected provider

**Files:**
- Modify: `backend/app/workouts/dependencies.py`, `backend/app/workouts/service.py`, `backend/app/workouts/models.py`
- Test: `backend/tests/workouts/test_service.py`, `backend/tests/workouts/test_routing.py`

- [ ] Resolve the profile preference before constructing the service and load admin-selected AI candidates only for AI mode.
- [ ] Dispatch to the existing deterministic engine for `fitsho_coach`; adapt the existing prompt/provider/validator flow for AI mode.
- [ ] Include method/model in signatures and persist provider/model/generation method on plans and generation records.
- [ ] Test both branches and verify AI provider failures are returned without fallback.

### Task 3: Add the persisted choice to the workout page

**Files:**
- Modify: `frontend/src/features/profile/types.ts`, `frontend/src/features/profile/api.ts`, `frontend/src/features/workouts/WorkoutPlanPage.tsx`, `frontend/src/features/workouts/workoutPlan.css`, `frontend/src/i18n/fa.ts`, `frontend/src/i18n/en.ts`
- Test: `frontend/src/features/workouts/WorkoutPlanPage.test.tsx`, `frontend/src/features/profile/api.test.ts`

- [ ] Load the profile preference and render a two-option choice in the workout page.
- [ ] Persist changes with profile PATCH and keep the current plan unchanged until the next generation.
- [ ] Add request/error/loading tests and Persian/English copy.

### Task 4: Verify, migrate, and run

- [ ] Run backend focused/full tests, Ruff, mypy, frontend tests, lint, and build.
- [ ] Apply the migration to the active database.
- [ ] Restart backend/frontend, verify HTTP responses and the workout page URL.
- [ ] Commit and push only feature files; preserve unrelated worktree changes.
