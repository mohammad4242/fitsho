# Program Engine V1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace AI workout decisions and the simplistic deterministic fallback with one safe,
deterministic, explainable resistance-and-cardio programming pipeline.

**Architecture:** Pure typed stages under `app/workouts/program_engine` consume a normalized request,
catalog candidates, and a versioned ruleset. `WorkoutGenerationService` remains the database/API
adapter and persists only validator-approved domain output through the existing activation flow.

**Tech Stack:** Python 3.12, FastAPI, Pydantic, SQLAlchemy, Alembic, PostgreSQL, pytest.

## Global Constraints

- Preserve existing endpoint paths and existing frontend response fields.
- No LLM or uncontrolled randomness may determine training decisions.
- All numeric rules and scoring weights live in one versioned ruleset.
- No inactive, non-programmable, reviewed, unsafe, blocked, or metadata-incomplete exercise may be selected.
- Invalid programs are never activated or returned as successful.
- Do not change frontend code unless additive backend fields break compilation.
- Do not add a dependency unless the standard library and current dependencies cannot satisfy the requirement.

---

### Task 1: Bad-output regression boundary

**Files:**
- Modify: `backend/app/workouts/candidate_selector.py`
- Modify: `backend/app/exercises/service.py`
- Modify: `backend/tests/workouts/test_candidate_selector.py`
- Create: `backend/tests/workouts/test_bad_output_regressions.py`

**Interfaces:**
- Produces: reviewed-exercise exclusion and executable regressions for the audited outputs.

- [ ] Write failing tests proving `needs_review` candidates are excluded, curated seed records clear
  review state, and current fallback accepts novice seven-day, missing-pattern, and excessive-repeat
  outputs.
- [ ] Run the focused tests and record the expected failures.
- [ ] Add the minimal candidate/seed safety corrections; keep bad-output tests red until the new engine replaces the fallback.
- [ ] Run candidate and seed tests, then commit `fix(workouts): exclude unreviewed exercise metadata`.

### Task 2: Typed domain contract, normalization, safety, and ruleset

**Files:**
- Create: `backend/app/workouts/program_engine/enums.py`
- Create: `backend/app/workouts/program_engine/schemas.py`
- Create: `backend/app/workouts/program_engine/rulesets/resistance_training_v1.py`
- Create: `backend/app/workouts/program_engine/normalization.py`
- Create: `backend/app/workouts/program_engine/safety.py`
- Create: `backend/app/workouts/program_engine/constraints.py`
- Create: `backend/tests/workouts/program_engine/test_normalization_safety.py`

**Interfaces:**
- Produces: `ProgramGenerationRequest`, `ExerciseCandidate`, `ProgramRuleset`,
  `NormalizedProgramRequest`, `SafetyAssessment`, and `DerivedConstraints`.

- [ ] Write failing table-driven tests for goal aliases, impossible values, conservative experience
  classification, red flags, ambiguous limitations, and computable constraints.
- [ ] Run the focused tests and confirm missing imports/behavior fail.
- [ ] Implement immutable Pydantic/dataclass contracts and pure normalization/safety stages.
- [ ] Run tests, ruff, and mypy; commit `feat(workouts): add typed program safety domain`.

### Task 3: Split selection and weekly volume planning

**Files:**
- Create: `backend/app/workouts/program_engine/training_status.py`
- Create: `backend/app/workouts/program_engine/split_selector.py`
- Create: `backend/app/workouts/program_engine/volume_planner.py`
- Create: `backend/tests/workouts/program_engine/test_split_volume.py`

**Interfaces:**
- Produces: `classify_training_status(...)`, `select_split(...)`, and `plan_weekly_volume(...)`.

- [ ] Write failing tests for realistic 1/2-day full-body structures, novice recovery limits, maximum
  six resistance days, hypertrophy frequency, priority-muscle volume, poor-recovery reductions, and
  previous-volume jump limits.
- [ ] Run focused tests and confirm expected failures.
- [ ] Implement candidate split scoring and direct/fractional volume targets using ruleset values only.
- [ ] Run tests, ruff, and mypy; commit `feat(workouts): plan coherent splits and weekly volume`.

### Task 4: Eligibility, ranking, and session assembly

**Files:**
- Create: `backend/app/workouts/program_engine/eligibility.py`
- Create: `backend/app/workouts/program_engine/exercise_ranker.py`
- Create: `backend/app/workouts/program_engine/session_builder.py`
- Create: `backend/tests/workouts/program_engine/test_selection_sessions.py`

**Interfaces:**
- Produces: `filter_eligible_exercises(...)`, `rank_exercises(...)`, and `build_sessions(...)` with
  structured selection and rejection reason codes.

- [ ] Write failing tests for every hard filter, stable ranking, reproducible tie-breaking,
  substitutions, missing-safe-pattern failures, priority order, duplicate-pattern control, and time trimming.
- [ ] Run focused tests and confirm expected failures.
- [ ] Implement hard filters before scoring and deterministic slot filling from planned volume.
- [ ] Run tests, ruff, and mypy; commit `feat(workouts): select safe explainable exercises`.

### Task 5: Prescription, cardio, progression, and independent validation

**Files:**
- Create: `backend/app/workouts/program_engine/prescription.py`
- Create: `backend/app/workouts/program_engine/cardio.py`
- Create: `backend/app/workouts/program_engine/progression.py`
- Create: `backend/app/workouts/program_engine/validation.py`
- Create: `backend/app/workouts/program_engine/engine.py`
- Create: `backend/tests/workouts/program_engine/test_prescription_validation.py`

**Interfaces:**
- Produces: `generate_program(request, catalog, ruleset) -> ProgramGenerationResult`.

- [ ] Write failing tests for goal-specific reps/RIR/rest, no exact load without strength data,
  warm-up exclusion, low-impact cardio, lower-body scheduling conflicts, double progression, excessive
  failure rejection, duration ceilings, weekly volume invariants, and structured unsatisfied results.
- [ ] Run focused tests and confirm expected failures.
- [ ] Implement the remaining stages and orchestrate them in the required order.
- [ ] Run all pure-engine tests, ruff, and mypy; commit `feat(workouts): complete deterministic program pipeline`.

### Task 6: Golden scenarios

**Files:**
- Create: `backend/tests/workouts/program_engine/golden_fixtures.py`
- Create: `backend/tests/workouts/program_engine/test_golden_scenarios.py`
- Modify: `backend/tests/workouts/test_bad_output_regressions.py`

**Interfaces:**
- Consumes: `generate_program` and V1 ruleset.
- Produces: required property-level golden coverage and green audited regressions.

- [ ] Add all requested novice, intermediate, advanced, equipment, limitation, recovery, short-session,
  impossible, and red-flag fixtures with hand-derived property assertions.
- [ ] Run tests and fix only the smallest responsible pipeline stage for each failure.
- [ ] Confirm audited bad-output tests now pass without weakened assertions.
- [ ] Commit `test(workouts): cover program engine golden scenarios`.

### Task 7: Persistence and API integration

**Files:**
- Create: `backend/alembic/versions/20260731_13_add_program_engine_snapshots.py`
- Modify: `backend/app/workouts/models.py`
- Modify: `backend/app/workouts/schemas.py`
- Modify: `backend/app/workouts/service.py`
- Modify: `backend/app/workouts/dependencies.py`
- Modify: `backend/app/workouts/router.py`
- Modify: `backend/app/workouts/repository.py`
- Modify: `backend/tests/database/test_workout_models.py`
- Modify: `backend/tests/workouts/test_service.py`
- Modify: `backend/tests/workouts/test_workout_plan_api.py`

**Interfaces:**
- Existing `generate(user_id)` remains valid; optional `ProgramGenerationRequest` overrides are additive.
- New plans persist engine/ruleset/seed/catalog snapshots, validation, metrics, trace, and progression.

- [ ] Write failing model, service, API, historical-snapshot, and validation-before-persistence tests.
- [ ] Run focused integration tests and confirm expected failures.
- [ ] Add reversible columns and map pure domain output to existing ORM rows transactionally.
- [ ] Remove AI providers and deterministic fallback from workout decision-making while retaining AI administration.
- [ ] Run migration check and integration tests; commit `feat(workouts): integrate program engine persistence`.

### Task 8: Documentation, comparisons, and complete verification

**Files:**
- Create: `docs/program-engine-architecture.md`
- Create: `docs/program-engine-rules.md`
- Create: `docs/program-engine-science-basis.md`
- Create: `docs/program-engine-migration.md`
- Create: `docs/program-engine-examples.md`
- Modify: `docs/workout-plan-generator.md`

**Interfaces:**
- Produces: architecture, rules, sources, migration, normalized input/output, and old/new comparisons.

- [ ] Document authoritative rationale for every important ruleset range and clearly label heuristics.
- [ ] Add old/new comparisons and validation reports for audited scenarios.
- [ ] Run backend pytest, ruff check, ruff format check, mypy, Alembic check, frontend tests, lint, and build.
- [ ] Review the full diff for duplicate engines, placeholders, unexplained TODOs, secrets, and unrelated files.
- [ ] Commit `docs(workouts): document program engine v1` and push the branch.
