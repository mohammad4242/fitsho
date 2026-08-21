# Program Engine Prescription Modes

## Scope

Add explicit repetition-based and duration-based exercise prescriptions across
the catalog, Program Engine, persistence, API, coach review, PDF, frontend, and
tests. Existing rep-based exercises remain backward compatible. Injury,
equipment, day-count, recovery, volume, strength, and session-duration policy
are out of scope.

## Data model

Add `PrescriptionMode` with `reps` and `duration` values to exercise metadata.
`Exercise.prescription_mode` defaults to `reps`. Duration exercises also store
per-exercise `duration_min_seconds` and `duration_max_seconds`; these are null
for rep-based exercises. The catalog and candidate domain objects carry the
mode and duration metadata into `ProgrammedExercise`.

`ProgrammedExercise` keeps the existing rep fields as nullable compatibility
fields and adds nullable duration fields. Its invariant is:

- `reps`: valid rep range, no duration range, non-null RIR;
- `duration`: valid duration range, no rep range, null RIR.

Application validation and database checks enforce this invariant. Existing
persisted rep records remain valid.

## Catalog backfill

Backfill uses canonical imported identifiers, not display names:
`source = 'free-exercise-db'` with `source_id = '0464'` for
`fedb-0464-front-plank`, and `source_id = '0705'` for
`fedb-0705-side-plank`. The migration asserts the expected stable identifiers
and sets the duration metadata only for those rows. Import synchronization uses
the same source-id mapping so a later catalog sync preserves the metadata.

The initial duration range is stored on each canonical exercise as 20–40
seconds. This is exercise metadata, not a global formatter or global
prescription fallback. Future duration exercises must provide their own
metadata before being marked duration-based.

## Generation and output

Prescription generation returns a typed prescription. Repetition exercises use
the existing ruleset ranges and RIR behavior. Duration exercises use their
catalog duration range, existing rest policy, and null RIR. Session construction
and time-budget calculations keep their current behavior.

Persistence and API responses expose `prescription_mode`, nullable rep fields,
nullable duration fields, and nullable RIR. PDF and frontend formatters branch
on mode, showing either repetitions or seconds. Coach review accepts and
persists both modes while preserving the existing rep-based workflow.

## Validation and migration

The Alembic migration adds mode and duration metadata to `exercises`, adds
mode-aware fields to `workout_plan_exercises`, makes legacy rep/RIR columns
nullable, and adds checks for allowed modes, valid ranges, mode exclusivity,
and duration RIR nullability. The migration backfills existing workout rows as
rep-based so historical data remains compatible.

## Verification

Tests cover model invariants, migration constraints, prescription generation,
Front Plank and Side Plank end-to-end generation, Squat backward compatibility,
API serialization, PDF output, frontend formatting, and coach review. Existing
focused regression tests run before implementation and again after the change.
