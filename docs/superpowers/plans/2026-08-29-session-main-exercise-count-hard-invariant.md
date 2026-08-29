# Session Main Exercise Count Hard Invariant Implementation Plan

> Execute each task with a fresh Luna implementer. The lead reviews every diff and targeted test
> result before committing and pushing that task. A failed review returns to the same Luna.

**Goal:** Enforce 30-minute sessions at 3–4 MAIN exercises and 45/60/75/90-minute sessions at
5–9 MAIN exercises throughout generation, mutation, validation, Final Gate, and reporting.

**Architecture:** Centralize structured MAIN classification and duration-aware count bounds.
Construction and mutation stages consume that policy; validator and Final Gate independently
enforce it. Reports consume server-derived canonical count breakdowns.

**Tech stack:** Python 3.12, FastAPI, dataclasses, pytest, Ruff, mypy.

---

## Task 1: Canonical MAIN classification and count policy

**Files:**
- Modify: `backend/app/workouts/program_engine/supplemental_policy.py`
- Modify: `backend/app/workouts/program_engine/duration_policy.py`
- Test: `backend/tests/workouts/program_engine/test_session_exercise_count_policy.py`

**Acceptance:**
- Add tests first for the full duration/count matrix as pure policy cases.
- A structured `ExerciseType.CORE` item is never MAIN even with a non-supplemental muscle.
- Canonical helpers expose MAIN, supplemental/Core, and total counts without name matching.
- Existing Core duration-cost behavior is locked by a regression test.
- No set, volume, safety, or eligibility policy changes.

## Task 2: Construction and duration-repair enforcement

**Files:**
- Modify: `backend/app/workouts/program_engine/session_builder.py`
- Modify: `backend/app/workouts/program_engine/template_sessions.py`
- Modify: `backend/app/workouts/program_engine/session_duration.py`
- Modify only if required: `backend/app/workouts/program_engine/duration_capacity.py`
- Test: focused builder/template/duration-repair tests under
  `backend/tests/workouts/program_engine/`

**Acceptance:**
- Tests reproduce a 30-minute fifth-MAIN path and a 45+ under-five path before implementation.
- Builders and repairs use canonical bounds, never Core or total list length as MAIN count.
- 30-minute generation does not build/retain more than four MAIN exercises.
- 45+ repair attempts safe eligible MAIN work to five; inability remains invalid for later reject.
- Core is retained and its duration cost remains included.
- No duplicate fill, artificial rest, or relaxed safety/equipment rules.

## Task 3: Downstream mutation guards

**Files:**
- Modify: `backend/app/workouts/program_engine/weekly_distribution.py`
- Modify: `backend/app/workouts/program_engine/volume_repair.py`
- Test: `backend/tests/workouts/program_engine/test_task_h2_distribution.py`
- Test: focused volume-repair tests under `backend/tests/workouts/program_engine/`

**Acceptance:**
- Tests first prove total-count/Core conflation and a move/add/remove count violation.
- Distribution metrics and donor/recipient checks use canonical MAIN counts.
- Redistribution cannot lower a donor below its duration floor or raise a recipient above its
  duration ceiling.
- Volume repair cannot add above the ceiling; unavoidable hard-volume/safety underfill is left for
  hard rejection rather than weakening either invariant.
- Mutation determinism and unrelated volume behavior remain unchanged.

## Task 4: Validator hard-error matrix

**Files:**
- Modify: `backend/app/workouts/program_engine/validation.py`
- Test: `backend/tests/workouts/program_engine/test_prescription_validation.py`
- Test: `backend/tests/workouts/program_engine/test_session_exercise_count_policy.py`

**Acceptance:**
- Tests first cover every required 30/45/60/75/90 boundary and Core case.
- Any out-of-range MAIN count is an error, never a warning.
- Duration/useful-workload/hard-volume evidence cannot waive count validation.
- Tests isolate count semantics from unrelated volume and duration failures.

## Task 5: Final Gate and engine-level last-line enforcement

**Files:**
- Modify: `backend/app/workouts/program_engine/final_gate.py`
- Modify only if required: `backend/app/workouts/program_engine/engine.py`
- Test: `backend/tests/workouts/program_engine/test_task_i_final_gate.py`
- Test: a focused engine integration test under `backend/tests/workouts/program_engine/`

**Acceptance:**
- A failing regression recreates the confirmed 60-minute/four-MAIN exact-evidence bypass.
- `SESSION_EXERCISE_COUNT_OUT_OF_RANGE` is never accepted as a duration constraint.
- Final Gate independently recomputes duration-aware MAIN bounds immediately before acceptance.
- An engine-level test injects or produces an invalid downstream mutation and proves no program is
  returned, covering the final rebuild/redistribution-to-output boundary.
- Valid constrained duration outcomes unrelated to exercise count remain supported.

## Task 6: Canonical API and E2E/report counts

**Files:**
- Modify: `backend/app/workouts/schemas.py`
- Modify: the response projection in `backend/app/workouts/`
- Modify: `backend/scripts/generate_e2e_report.py`
- Modify: `backend/scripts/generate_e2e_report_batch2.py`
- Modify: `backend/tests/workouts/program_engine/phase11_benchmark.py`
- Modify: `backend/stage3_benchmark.py`
- Test: `backend/tests/workouts/program_engine/test_task_j_report.py`
- Test: focused response-schema tests if required

**Acceptance:**
- Tests first show that total list length misreports MAIN count with Core present.
- Response/report records expose MAIN, Core/supplemental, and total counts from the canonical helper.
- The constraint-facing legacy `exercise_count`, if retained, means MAIN and is explicit.
- Persian report output labels the three concepts unambiguously.
- Untracked legacy report scripts and unrelated artifacts remain untouched.

## Task 7: Integrated regression verification

**Owner:** Lead reviewer; implementation fixes return to the owning Luna task.

**Acceptance:**
- Review every changed file and test for bypasses, dirty special cases, and duplicated semantics.
- Run the deterministic matrix, final-gate regressions, mutation integration tests, complete Program
  Engine suite, report tests, Ruff, and mypy.
- Confirm a clean tracked worktree, focused commits, pushed current branch, and matching remote HEAD.
