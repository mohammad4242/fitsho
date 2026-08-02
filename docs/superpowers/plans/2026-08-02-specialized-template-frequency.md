# Specialized Template Frequency Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Keep direct training for every muscle to at most two weekly sessions while enforcing movement floors only on specialized body-part sessions in four- to six-day hypertrophy templates.

**Architecture:** The ruleset owns the direct-frequency cap. Template seed data remains the editable library; body-part templates declare core slots that meet the floors. Final validation counts unique days containing direct work for each primary muscle and rejects a third exposure.

**Tech Stack:** Python 3.12, SQLAlchemy seed data, FastAPI backend, pytest.

## Global Constraints

- Count direct primary-muscle work only; indirect compound involvement is not an exposure.
- Apply movement floors only to four- to six-day templates tagged `body_part_rotation`.
- A specialized large-muscle session has at least three direct movements; a specialized small-muscle session has at least two.
- Direct work for a muscle appears on at most two weekly sessions.
- Preserve safety, equipment, session-duration, and public API contracts.
- Do not add dependencies.

---

### Task 1: Add deterministic direct-exposure validation

**Files:**
- Modify: `backend/app/workouts/program_engine/rulesets/resistance_training_v1.py`
- Modify: `backend/app/workouts/program_engine/validation.py`
- Test: `backend/tests/workouts/program_engine/test_validation.py`

**Interface:** Add `maximum_direct_sessions_per_muscle_per_week = 2` to `ProgramRuleset`. `validate_program` returns `MUSCLE_DIRECT_FREQUENCY_EXCEEDED` and `direct_session_frequency_by_muscle`.

- [ ] Write a test with chest as the primary muscle on three different days.
- [ ] Run `cd backend && uv run pytest tests/workouts/program_engine/test_validation.py -k direct_frequency -v`; verify the new assertion fails.
- [ ] Count unique `day_index` values per `primary_muscle` in `validate_program` and return the error and metric.
- [ ] Re-run the focused test and commit `feat(workouts): cap direct muscle frequency`.

### Task 2: Bring specialized templates to the agreed floors

**Files:**
- Modify: `backend/app/training_templates/seed_data.py`
- Test: `backend/tests/training_templates/test_seed.py`

**Interface:** The test inspects four- to six-day `body_part_rotation` seeds. A large main body part has at least three direct core slots; an explicitly programmed small body part has at least two. Priority templates have no third direct exposure for their priority muscle.

- [ ] Write the movement-floor test and verify it fails against the current seed library.
- [ ] Upgrade body-part sessions with missing core direct movements; keep minimum movements core so time fitting cannot remove them.
- [ ] Replace a third chest/back exposure in six-day priority rotations with complementary work rather than raising weekly chest/back volume.
- [ ] Re-run the seed tests and commit `feat(training-templates): enforce specialized movement floors`.

### Task 3: Verify template generation

**Files:**
- Test: `backend/tests/workouts/program_engine/test_template_sessions.py` or the existing template integration test.

**Interface:** A generated template-reference program has `direct_session_frequency_by_muscle` no greater than two and passes final validation.

- [ ] Write a template-generation assertion for the direct-frequency metric.
- [ ] Run focused program-engine template tests.
- [ ] Run `cd backend && uv run ruff check && uv run mypy && uv run pytest`.
- [ ] Commit any integration coverage and push `main`.
