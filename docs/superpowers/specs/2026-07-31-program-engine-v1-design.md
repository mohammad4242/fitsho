# Program Engine V1 Design

## Objective

Replace the current AI-first workout decision path and simplistic deterministic fallback with one
versioned deterministic program engine. Preserve the existing workout-plan endpoints, persistence
activation flow, and frontend response fields. AI providers remain available only for optional
natural-language explanation and never determine program structure or validity.

## Scope

V1 supports adults aged 18 or older seeking general fitness, fat loss, body recomposition,
hypertrophy or muscle gain, strength, and muscular endurance with one to six resistance sessions.
It supports gym, dumbbell-home, and bodyweight-home training. Red flags and ambiguous limitations
produce structured review or referral results instead of a program.

## Architecture

`app.workouts.program_engine` is a pure domain package. Its public entry point is:

```python
def generate_program(
    request: ProgramGenerationRequest,
    exercise_catalog: Sequence[ExerciseCandidate],
    ruleset: ProgramRuleset,
) -> ProgramGenerationResult:
    ...
```

The pipeline is explicit: normalization, safety screening, constraint derivation, training-status
classification, split selection, weekly-volume planning, eligibility filtering, exercise ranking,
session assembly, prescription, progression, whole-program validation, and explainability.

`WorkoutGenerationService` remains the application boundary. It loads the profile and catalog,
builds the domain request, invokes the engine, maps the result to existing ORM models, and activates
the plan transactionally. It performs no training decisions. The existing AI output schema remains
only as a compatibility adapter during migration and is not a second engine.

## Compatibility

`POST /api/v1/workout-plans/generate` continues to work without a request body. An optional typed
body can provide the richer programming context. Existing response fields remain unchanged; new
engine metadata is additive. Existing saved plans remain readable.

The frontend is unchanged. It may ignore additive response fields. Existing callers of
`WorkoutGenerationService.generate(user_id)` remain valid.

## Data and persistence

The existing `Exercise`, `WorkoutPlan`, `WorkoutDay`, and `WorkoutPlanExercise` models remain
authoritative. V1 adds only metadata used by actual decisions. Exercise metadata is conservative:
`needs_review`, inactive, non-programmable, or essential-metadata-incomplete exercises are excluded.

Each new plan stores the normalized request snapshot, engine and ruleset versions, seed, catalog
snapshot, assumptions, warnings, progression policy, validation report, aggregate metrics, and
decision trace. Selected exercise identity and relevant catalog metadata are snapshotted so later
catalog edits do not change historical decisions. Generation and activation remain atomic.

## Determinism

Stable sorting is the default. A persisted integer seed is used only for equal-ranked eligible
alternatives. Safety filters and higher-ranked choices never depend on randomness. Equal normalized
input, catalog snapshot, ruleset, and seed produce equal domain output.

## Safety and constraints

Safety status is one of `CLEAR`, `CLEAR_WITH_MODIFICATIONS`,
`REQUIRES_PROFESSIONAL_REVIEW`, or `STOP_AND_REFER`. A non-generating status returns structured
reason codes. Explicit hard constraints cover equipment, review state, difficulty, caution tags,
blocked exercises and patterns, ROM, impact, axial load, overhead movement, and balance/stability.
No unsafe fallback fills an unsatisfied slot.

## Training logic

The versioned ruleset contains all numeric ranges and scoring weights. Split candidates are scored
for frequency, recovery, duration, experience, goal, spacing, and simplicity. Weekly volume is
planned before exercise selection using direct sets and configurable 0.5 secondary-muscle credit.
Sessions are assembled from required movement and muscle slots, then prescribed by goal and exercise
role. Priority work is ordered early. Default progression is double progression with RIR and no
exact load when performance data is absent. Cardio is stored separately and coordinated with lower
body resistance sessions.

## Validation and errors

The independent validator repeats every hard eligibility check and verifies day count, duration,
volume, movement coverage, ordering, recovery spacing, cardio conflicts, prescriptions, reasons,
and safety status. Validation errors prevent persistence. Failures use structured codes including
`UNSATISFIED_CONSTRAINT`, `NO_SAFE_EXERCISE_FOR_PATTERN`,
`NO_AVAILABLE_EQUIPMENT_MATCH`, and `INSUFFICIENT_ELIGIBLE_EXERCISES`.

## Testing

Regression tests first capture the observed bad outputs: reviewed exercises entering candidates,
novice six/seven-day plans, missing one-day movement coverage, identical sessions, excessive or zero
muscle volume, repeated near-identical movements, goal-incoherent prescriptions, unsafe alternatives,
and mutable historical catalog data. Pure unit tests cover every stage. Integration tests prove
validation precedes persistence and the existing API contract remains compatible. Golden fixtures
assert domain properties rather than accepting snapshots blindly.

## Migration

The new engine replaces `DeterministicWorkoutPlanGenerator` behind the existing service. The
AI-provider loop is removed from workout decision-making after compatibility tests pass. No permanent
second engine or feature flag remains. Existing AI administration remains independent and can later
serve explanation features.
