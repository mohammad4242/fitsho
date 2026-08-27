# Luna Task C Report

## Scope

Implemented same-session canonical semantic redundancy handling only. Opener ordering, split topology, duration policy, weekly rebalance, safety mapping, recovery, and profile schema work were not changed.

## RED evidence

Before production edits:

```text
uv run pytest -q tests/workouts/program_engine/test_exercise_semantics.py::test_canonical_semantic_family_rejects_same_role_variants tests/workouts/program_engine/test_task_c_semantic_redundancy.py::test_validator_does_not_allow_template_or_repair_reason_to_bypass_semantics
4 failed
```

The failures demonstrated that distinct squat/hinge substitution groups were not canonicalized and that a deliberate template reason bypassed final semantic validation.

## GREEN evidence

Focused task checks:

```text
uv run pytest -q tests/workouts/program_engine/test_exercise_semantics.py tests/workouts/program_engine/test_task_c_semantic_redundancy.py
14 passed
```

Focused neighborhood checks:

```text
uv run pytest -q tests/workouts/program_engine/test_exercise_semantics.py tests/workouts/program_engine/test_task_c_semantic_redundancy.py tests/workouts/program_engine/test_selection_sessions.py tests/workouts/program_engine/test_prescription_validation.py tests/workouts/program_engine/test_coach_quality_regressions.py tests/workouts/program_engine/test_level_aware_template_sessions.py
125 passed
```

Full Program Engine replay:

```text
uv run pytest -q tests/workouts/program_engine
881 passed, 1 failed
```

The single failure is `test_batch2_profile_underfill_is_hard_volume_constrained[10-3-2-19]`: the strict same-session policy removes redundant optional work and the resulting honest constrained session is 17 minutes; the pre-existing assertion expects 19 minutes. No safety, equipment, day-count, recovery, or semantic invariant failure was observed.

Lint passed for all changed production and test files:

```text
uv run ruff check app/workouts/program_engine/exercise_semantics.py app/workouts/program_engine/template_sessions.py app/workouts/program_engine/validation.py tests/workouts/program_engine/test_exercise_semantics.py tests/workouts/program_engine/test_task_c_semantic_redundancy.py
All checks passed!
```

## Exact production-equivalent replay

`test_batch2_profiles_have_no_same_session_semantic_redundancy` replays deterministic construction for Batch2 profile shapes 2, 3, 6, and 9, asserting canonical family uniqueness in every generated day and a valid final validator report. All four cases passed.

## Implementation

- Added canonical family normalization in `exercise_semantics.py` for push-up, squat, and RDL/stiff-leg/deadlift role families, while retaining equipment, focus, body-position, and laterality distinctions where meaningful.
- Removed template and repair reason-code exemptions from final same-session semantic validation.
- Template duplicates now use a complementary candidate, omit optional work, or reject an unresolvable core slot honestly.
- Targeted template accessory filling no longer permits semantic duplicates merely to reach a count floor.
- Added regressions for Batch2 profiles, canonical role families, valid distinctions, template core rejection, and reason-code bypass prevention.

## Self-review

- No display-name, profile-number, ID, or user-name matching was added to production logic.
- Same exercise-family repeats across different sessions remain permitted.
- Required safety/equipment eligibility and deterministic ordering paths remain shared.
- Only task production files, task tests, and this report are intended for the commit.

## Concern

The existing profile-10 duration expectation conflicts with the new requirement that redundant optional work must not be retained to fill duration. It remains unchanged and is reported as the one full-suite failure.

## Git

Proposed commit message: `fix(program-engine): reject redundant exercise families`
