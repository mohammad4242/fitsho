# Deterministic Workout Fallback Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Generate and persist a valid local workout plan whenever every AI provider fails.

**Architecture:** A focused `DeterministicWorkoutPlanGenerator` converts the existing filtered candidates and policy into the existing AI output schema. The service invokes it only after provider attempts fail, validates it with `WorkoutPlanValidator`, and persists it through the unchanged plan builder.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy, Pydantic, pytest.

## Global Constraints

- AI remains the primary path.
- Use only eligible candidates and policy-approved prescriptions.
- The existing semantic validator is mandatory.
- Mark local plans with `fitsho-deterministic-v1`.

---

### Task 1: Deterministic generator

**Files:**
- Create: `backend/app/workouts/deterministic_generator.py`
- Create: `backend/tests/workouts/test_deterministic_generator.py`

**Interfaces:**
- Produces: `DeterministicWorkoutPlanGenerator.generate(profile, candidates, policy) -> WorkoutPlanModelOutput`

- [ ] Write tests proving deterministic, candidate-only, distinct multi-day, time-budget-valid output.
- [ ] Run tests and confirm they fail because the generator is absent.
- [ ] Implement balanced candidate ordering, day rotation, goal prescriptions, and estimated durations.
- [ ] Validate generated fixtures with `WorkoutPlanValidator` and run ruff/mypy.
- [ ] Commit with `feat(workouts): add deterministic plan generator`.

### Task 2: Service fallback

**Files:**
- Modify: `backend/app/workouts/service.py`
- Modify: `backend/app/workouts/dependencies.py`
- Modify: `backend/app/config.py`
- Test: `backend/tests/workouts/test_service.py`

**Interfaces:**
- Consumes: `DeterministicWorkoutPlanGenerator.generate(...)`
- Produces: AI-first generation with local fallback model ID `fitsho-deterministic-v1`.

- [ ] Write a service test where all providers fail and a valid active local plan is persisted.
- [ ] Run the test and confirm existing behavior raises `WorkoutGenerationFailedError`.
- [ ] Add `workout_deterministic_fallback_enabled: bool = True` and invoke the generator after exhausted providers.
- [ ] Preserve provider-first behavior and support disabling fallback in tests/settings.
- [ ] Run workout tests, ruff, and mypy; commit with `feat(workouts): fallback to deterministic plans`.

### Task 3: Delivery

**Files:** No source changes expected.

- [ ] Run full backend and frontend verification.
- [ ] Restart preview, confirm API key is present, cooldown is zero, and the migration is current.
- [ ] Push the branch and report the test URL.
