# Program Engine Caution Safety Design

## Scope

Fix only the Program Engine safety path for profile training cautions. Do not
change training-day count, equipment filtering, volume, duration, strength
programming, or split behavior.

## Root cause

`WorkoutGenerationService._to_program_request` derives blocked
`ExerciseCautionTag` values from persisted `TrainingCaution` values, but a
request-time `ProgramGenerationOverrides` object can overwrite those values
with its default empty `blocked_caution_tags`. This removes the profile safety
constraint before normalization and eligibility.

The catalog also contains exercises whose explicit caution tags do not fully
describe hazards represented by existing movement and muscle metadata. The
engine therefore needs a conservative effective-tag calculation for known
metadata patterns, while preserving the existing enums and tag vocabulary.

## Design

1. Preserve the profile-derived caution constraints when applying overrides.
   Explicit override constraints are merged with profile constraints instead of
   replacing them. Multiple active cautions produce the union of all mapped
   `ExerciseCautionTag` values.

2. Keep one canonical mapping from `TrainingCaution` to existing
   `ExerciseCautionTag` values for lower back, knee, shoulder, neck, wrist, and
   other. Add a small safety helper that derives conservative effective tags
   from existing candidate metadata for known risky movement/muscle/equipment
   combinations. Unknown or structurally incomplete exercise metadata remains
   ineligible through the existing required-metadata guard.

3. Apply effective safety tags in `filter_eligible_exercises`, before ranking,
   template resolution, session construction, or repair. Replacement ranking
   continues to consume the eligible set only.

4. Apply the same effective safety check in `validate_program` to the final
   `ProgrammedExercise` values. Any unsafe final exercise produces validation
   failure, making unsafe output impossible even if a future construction path
   bypasses the initial filter. Existing construction recovery remains the
   source of substitutions; no new repair architecture is introduced.

## Tests

Add typed metadata fixtures and tests covering:

- direct eligibility for wrist, neck, shoulder, knee, and lower-back cautions;
- shoulder plus neck and lower-back plus wrist intersections;
- a no-caution baseline retaining normal exercises;
- profile-to-request caution preservation when overrides are present;
- end-to-end `generate_program` output containing no effective caution conflict;
- final validation rejecting an unsafe programmed exercise.

Assertions use candidate metadata and IDs, not exercise names.

## Failure behavior

If filtering and existing construction recovery cannot produce a valid safe
program, return the existing generation/validation failure result. Never return
a program containing an exercise that conflicts with an active caution.
