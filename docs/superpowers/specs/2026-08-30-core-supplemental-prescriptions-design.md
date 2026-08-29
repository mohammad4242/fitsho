# Core and Supplemental Prescription Sections

## Scope

Allow two working sets for exercises classified as Core/supplemental while keeping
the existing three-set minimum for ordinary resistance exercises. The existing
supplemental classification remains the only source of truth:

- `FOREARMS`
- `ABS`
- `OBLIQUES`
- `LOWER_BACK`
- `NECK`
- `ExerciseType.CORE`

Calves, biceps, triceps, and other unrelated muscles remain ordinary work unless
they are explicitly classified as `ExerciseType.CORE`.

## Engine behavior

`supplemental_policy.py` will expose the shared context-aware minimum used by
prescription and validation. Core/supplemental exercises accept 2, 3, or 4
working sets. Ordinary resistance exercises retain the ruleset minimum of 3 and
the current maximum/exception behavior, including authorized strength 5-set and
existing FST-7 7-set paths.

`prescribe_sessions()` will use the contextual minimum when applying allocated
sets, untracked fallback sets, per-muscle remaining-set limits, and duration
trimming. This prevents a valid two-set Core item from being rounded up to three.
The resistance-session duration semantics and supplemental exercise-count limit
remain unchanged.

The shared session-structure policy will classify `ExerciseType.CORE` together
with the five supplemental muscles for tail ordering, title exclusion, main-count
behavior, and supplemental-limit validation. Main movements remain before the
Core/supplemental tail.

## API and persistence

No database column or migration is required. The persisted exercise snapshot and
live exercise metadata already contain the fields needed for classification.

`WorkoutPlanExerciseResponse` will add a backward-compatible `section` field with
the values `main` and `core`. The router derives it through the shared classifier
while preserving the existing flat `exercises` array and global order indexes.
Missing legacy metadata defaults safely to `main`.

## Frontend behavior

The workout page will group response items by `section`, never by exercise names.
Main items render first. When Core items exist, they render afterward in a separate
block with the exact visible heading `Core`. Existing exercise controls, ordering,
superset behavior, and legacy responses without the field remain compatible.

## Verification

Targeted regressions will cover:

- two-set ABS, OBLIQUES, LOWER_BACK, FOREARMS, NECK, and `ExerciseType.CORE`;
- one-set rejection and ordinary chest/back/legs minimums;
- allocation not rounding Core work up to three sets;
- Core-last ordering and existing supplemental ordering rules;
- response section metadata and persistence serialization;
- frontend Core heading and main-before-Core rendering.

The affected backend Program Engine tests, workout API tests, frontend workout
tests, lint/type checks, and build will be run before handoff.
