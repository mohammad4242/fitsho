# Template Reference Engine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Use the curated Fitsho template library as the deterministic reference for safe, adaptable four- and five-day hypertrophy programs.

**Architecture:** The SQL-backed template module exposes immutable engine-reference DTOs. The pure program engine scores those references after catalog eligibility, builds sessions from the winning safe template, and falls back to its existing planner only when no reference is viable. Template slots declare their adaptation priority so time fitting is deterministic and explainable.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy, Alembic, Pydantic, pytest, React/TypeScript/Vitest.

## Global Constraints

- Keep template data original Fitsho programming; do not copy named coaches' programs.
- Preserve hard safety filtering and the existing free-form planner fallback.
- Do not add profile fields or third-party libraries.
- Seed exactly ten active templates for each of four and five weekly training days.
- Use test-first cycles and do not stage `backend/uv.lock`.

---

### Task 1: Add template adaptation metadata and library coverage

**Files:**
- Modify: `backend/app/training_templates/models.py`, `seed_data.py`, `service.py`
- Create: `backend/alembic/versions/20260802_16_add_template_adaptation_metadata.py`
- Modify: `backend/tests/training_templates/test_seed.py`

**Interfaces:**
- Produces `TemplateSlotPriority` and `superset_group` on a persisted slot.
- Produces ten four-day and ten five-day seed templates with level/focus/method labels.

- [ ] Write failing tests for the ten-template buckets, level/focus coverage, and valid superset pairs.
- [ ] Add the migration and typed model fields with backward-safe defaults.
- [ ] Expand seed helpers and four/five-day original templates to the configured slot bands.
- [ ] Run focused seed tests and commit `feat(training-templates): expand four and five day reference library`.

### Task 2: Convert database templates into engine references

**Files:**
- Create: `backend/app/training_templates/engine_reference.py`
- Modify: `backend/app/training_templates/service.py`
- Modify: `backend/tests/training_templates/test_engine_reference.py`

**Interfaces:**
- Produces `tuple[TemplateReference, ...]` via `load_template_references(db)`.
- References contain only immutable scalar data, catalog exercise IDs, day focuses, and ordered slots.

- [ ] Write a failing conversion test that preserves linked IDs, nullable placeholders, slot priority, and superset group.
- [ ] Add the DTO adapter without importing SQLAlchemy into `program_engine`.
- [ ] Run its test and commit `feat(training-templates): expose engine reference templates`.

### Task 3: Select and adapt a safe reference template

**Files:**
- Create: `backend/app/workouts/program_engine/template_selector.py`, `template_sessions.py`
- Modify: `backend/app/workouts/program_engine/schemas.py`, `engine.py`, `prescription.py`, `validation.py`
- Modify: `backend/tests/workouts/program_engine/test_template_reference.py`

**Interfaces:**
- `generate_program(..., reference_templates=())` remains backward compatible.
- A selected reference records `TEMPLATE_REFERENCE_SELECTED`, substitutions, and time-trim reasons in the decision trace.

- [ ] Write failing tests for deterministic selection, safe substitution, and short-session optional-first trimming.
- [ ] Define frozen template DTOs and score only level/day/goal/priority/time/eligible-core candidates.
- [ ] Build session drafts from the winner, use reference prescriptions, and validate reference-specific volume ranges.
- [ ] Keep no-template and no-viable-template requests on the existing path.
- [ ] Run focused program-engine tests and commit `feat(workouts): generate from safe template references`.

### Task 4: Route Fitsho coach generation through references

**Files:**
- Modify: `backend/app/workouts/service.py`
- Modify: `backend/tests/workouts/test_service.py`

**Interfaces:**
- Deterministic Fitsho-coach calls pass active references to `generate_program`.
- The generation signature includes a stable active-template revision hash.

- [ ] Write a failing service test that asserts reference templates are passed to deterministic generation.
- [ ] Load references in the service, hash their normalized contents, and pass them to the engine.
- [ ] Run service tests and commit `feat(workouts): use template library for fitsho coach`.

### Task 5: Verify, publish, and activate the library

**Files:**
- Modify only if verification identifies a defect.

- [ ] Run Alembic upgrade/check, full backend pytest, Ruff, mypy, frontend tests/lint/build.
- [ ] Seed the active 317-exercise database and assert ten four-day and ten five-day templates.
- [ ] Merge the verified branch into `main`, push `main`, remove only the merged feature worktree/branch, restart the local service, and verify the app endpoint.
