# Stage 6: Session Composition and Supersets

## Scope

Add visible, persisted, deterministic supersets as a duration-pressure repair. Preserve the
existing template-selection architecture, workout schema compatibility, core-preservation
policy, prescription ranges, and exact resistance-day count.

## Additive contract

`superset_group: string | null` is added to:

- `ProgrammedExercise`
- `workout_plan_exercises` as a nullable `VARCHAR(32)` column
- workout-plan persistence and API response projection
- frontend workout exercise types and workout-plan rendering

Existing rows remain `NULL`. Existing API consumers can ignore the additive field. No existing
field changes meaning.

## Engine flow

Template-provided `TemplateReferenceSlot.superset_group` survives exercise resolution only when
the resolved pair passes the same safety policy as engine-created pairs. Unsafe or incomplete
template groups are cleared and receive a stable internal reason code.

Engine-created groups are considered only while an overfilled session remains above the normal
`requested + 10` workout ceiling after:

1. optional filler removal
2. redundant accessory removal
3. low-priority accessory set reduction
4. non-priority work reduction

Safe supersets are attempted before additional rest reduction and before the exceptional
core-preservation extension. Underfilled or already valid sessions are never supersetted merely
to consume time.

## Pair safety policy

A group contains exactly two adjacent exercises. Selection is deterministic by preservation
priority, exercise order, and exercise UUID.

Allowed curated categories:

- chest accessory with back accessory
- biceps isolation with triceps isolation
- non-competing isolation exercises with disjoint primary muscles
- core with a low-interference upper-body isolation exercise

The pair is rejected when either exercise:

- is a primary Strength movement
- is a heavy lower-body compound
- creates Squat plus Hinge competition
- shares the same primary muscle
- has incompatible equipment transitions
- violates existing safety, limitation, eligibility, or range-of-motion constraints

Template metadata does not override these rules.

## Duration accounting

Pairing preserves prescribed reps, RIR, and role-specific rest bounds. The second exercise stores
a deterministic reduced incremental duration based on overlapped inter-set rest; no rest value is
inflated or reduced outside its Stage 5 range. A stable reason code records the time saving.

The normal workout target remains `requested - 10` through `requested + 10`, excluding general
warm-up. A high-quality 52-minute resistance session remains valid for a 60-minute request.

## API and UI

The API returns `superset_group` for each exercise. The workout UI renders adjacent members as one
visually connected group with localized `Superset` / `سوپرست` labeling and a short instruction to
perform the pair consecutively, then take the displayed rest. Normal users do not see engine
reason codes.

If only one member reaches the API or ordering is not adjacent, the UI renders ordinary straight
sets instead of an incomplete superset.

## Validation

Final validation rejects malformed superset structure as an invalid prescription:

- group size other than two
- non-adjacent members
- primary Strength member
- semantically unsafe pair

The validator remains deterministic and emits stable reason codes.

## Tests

Focused tests cover:

- template group propagation through persistence and API
- safe curated pair duration savings
- primary Strength exclusion
- heavy lower and Squat/Hinge exclusion
- unsafe equipment-transition exclusion
- deterministic pair order and identifier
- already-valid 52-minute session receives no artificial pairing or rest inflation
- malformed groups fail validation
- Persian and English UI labels render only for complete adjacent pairs
- migration upgrade and current Alembic head

Relevant duration, template-reference, safety, API, frontend, golden, and full engine regressions
run before the Stage 6 commit.
