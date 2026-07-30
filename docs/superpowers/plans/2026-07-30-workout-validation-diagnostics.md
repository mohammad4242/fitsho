# Workout Validation Diagnostics Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Log the exact safe semantic-validation problems for initial and repaired AI workout plans.

**Architecture:** The workout generation service will emit one warning at each semantic-validation failure point, where both the model ID and validation phase are known. The warning message will contain compact JSON problem payloads for normal Docker log visibility, while the same values will be attached as structured `LogRecord` fields for tests and log processors.

**Tech Stack:** Python 3.12, standard-library `logging`, pytest, pytest `caplog`

## Global Constraints

- Do not log user profiles, prompts, full model responses, or authentication data.
- Preserve the existing API response and database failure code.
- Preserve unrelated frontend changes in the worktree.

---

### Task 1: Log Exact Semantic Validation Problems

**Files:**
- Modify: `backend/app/workouts/service.py`
- Test: `backend/tests/workouts/test_service.py`

**Interfaces:**
- Consumes: `WorkoutPlanValidationError.problems` and `ValidationProblem.to_repair_payload()`
- Produces: `_log_validation_failure(model_id: str, phase: str, error: WorkoutPlanValidationError) -> None`

- [ ] **Step 1: Write the failing test**

Add a service test that submits the same duplicate-exercise response for the initial and
repair attempts, captures warnings from `app.workouts.service`, and verifies two records:

```python
def test_invalid_initial_and_repair_responses_log_exact_problems(
    db: Session,
    caplog: pytest.LogCaptureFixture,
) -> None:
    user = _user_with_profile(db)
    exercises = _seed_candidates(db)
    invalid = _response([exercises[0].id, exercises[0].id])
    provider = FakeWorkoutPlanModelProvider([invalid, invalid])

    with caplog.at_level("WARNING", logger="app.workouts.service"):
        with pytest.raises(WorkoutGenerationFailedError):
            asyncio.run(_service(db, provider).generate(user.id))

    records = [
        record
        for record in caplog.records
        if record.getMessage().startswith("workout_plan_validation_failed")
    ]
    assert [record.__dict__["validation_phase"] for record in records] == [
        "initial",
        "repair",
    ]
    assert all(
        record.__dict__["workout_model_id"] == "fake-model" for record in records
    )
    assert all(
        {
            "code": "duplicate_exercise",
            "message": "An exercise may not appear more than once in the same day.",
            "day_number": 1,
            "exercise_id": str(exercises[0].id),
        }
        in record.__dict__["validation_problems"]
        for record in records
    )
    assert all('"code":"duplicate_exercise"' in record.getMessage() for record in records)
```

- [ ] **Step 2: Run the test to verify RED**

Run:

```bash
cd backend
TEST_DATABASE_URL=postgresql+psycopg://fitsho:fitsho@localhost:5432/fitsho_test \
  .venv/bin/pytest tests/workouts/test_service.py::test_invalid_initial_and_repair_responses_log_exact_problems -q
```

Expected: FAIL because no validation warning records exist.

- [ ] **Step 3: Implement the minimal logging**

In `backend/app/workouts/service.py`, add:

```python
import logging

logger = logging.getLogger(__name__)
```

Add a module helper:

```python
def _log_validation_failure(
    model_id: str,
    phase: str,
    error: WorkoutPlanValidationError,
) -> None:
    problems = [problem.to_repair_payload() for problem in error.problems]
    logger.warning(
        "workout_plan_validation_failed model_id=%s phase=%s problems=%s",
        model_id,
        phase,
        json.dumps(problems, ensure_ascii=False, separators=(",", ":")),
        extra={
            "workout_model_id": model_id,
            "validation_phase": phase,
            "validation_problems": problems,
        },
    )
```

Call it immediately when `initial_error` is caught. Wrap repaired-plan validation so a
`WorkoutPlanValidationError` logs phase `repair` before it is re-raised:

```python
except WorkoutPlanValidationError as initial_error:
    _log_validation_failure(candidate.model_id, "initial", initial_error)
    ...
    repaired = await candidate.provider.generate_plan(repair_request)
    try:
        validator.validate(repaired.plan)
    except WorkoutPlanValidationError as repair_error:
        _log_validation_failure(candidate.model_id, "repair", repair_error)
        raise
```

- [ ] **Step 4: Run focused and full backend verification**

Run:

```bash
cd backend
TEST_DATABASE_URL=postgresql+psycopg://fitsho:fitsho@localhost:5432/fitsho_test \
  .venv/bin/pytest tests/workouts/test_service.py -q
.venv/bin/ruff check app/workouts/service.py tests/workouts/test_service.py
.venv/bin/mypy app
TEST_DATABASE_URL=postgresql+psycopg://fitsho:fitsho@localhost:5432/fitsho_test \
  .venv/bin/pytest -q
```

Expected: all commands exit successfully.

- [ ] **Step 5: Commit**

Stage only the backend implementation, backend test, and this plan:

```bash
git add backend/app/workouts/service.py \
  backend/tests/workouts/test_service.py \
  docs/superpowers/plans/2026-07-30-workout-validation-diagnostics.md
git commit -m "fix(workouts): log semantic validation causes"
git push origin feature/ai-model-admin-routing
```
