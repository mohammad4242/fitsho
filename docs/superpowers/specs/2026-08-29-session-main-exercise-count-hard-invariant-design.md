# Session Main Exercise Count Hard Invariant

## Scope

Make the number of main resistance exercises a hard invariant across the complete Workout
Program Engine pipeline without weakening safety, equipment, injury, duration, volume, template,
or set-count policies.

## Required policy

| Session duration | Minimum MAIN | Maximum MAIN |
| --- | ---: | ---: |
| 30 minutes | 3 | 4 |
| 45, 60, 75, 90 minutes | 5 | 9 |

`ExerciseType.CORE` is never MAIN, regardless of its muscle metadata. Core and other
supplemental work remain in the session and continue to contribute to total duration.

## Canonical concepts

The engine will use one canonical classifier and count policy for these distinct values:

- total exercise count;
- main resistance exercise count;
- core/supplemental exercise count;
- total duration cost.

The canonical classifier is based on structured exercise type and muscle metadata. It must work
with both engine programmed exercises and nested response/persistence wrappers. It must not use
exercise names or session titles.

## Current execution path

1. Request normalization and safety filtering.
2. Session capacity and template/split selection.
3. Session construction and prescription.
4. Weekly-volume repair.
5. Session-duration repair.
6. Recovery/structure finalization.
7. Weekly redistribution.
8. Duration repair certification.
9. Validation.
10. Final Gate.
11. Response and E2E/report rendering.

Exercise membership can change during construction, weekly-volume repair, session-duration
repair, and weekly redistribution. Therefore every mutator must preserve the invariant where it
can, while validation and Final Gate must independently reject any remaining violation.

## Confirmed root causes

1. `main_exercise_count` excludes supplemental muscles but does not exclude
   `ExerciseType.CORE`; malformed or unexpected core muscle metadata can satisfy the MAIN floor.
2. The duration-aware count policy has a short-session floor but no short-session maximum, so a
   30-minute session with five MAIN exercises can pass count validation.
3. Validation converts under-floor counts into warnings when duration/useful-workload evidence is
   present. This permits an invalid 45+ minute session to remain eligible for Final Gate.
4. Final Gate treats `SESSION_EXERCISE_COUNT_OUT_OF_RANGE` as a waivable duration outcome and can
   accept it as `accepted_with_constraints`; it does not independently enforce per-day bounds.
5. Weekly distribution and parts of volume/duration repair use total list length where MAIN count
   is required, so Core/supplemental exercises can hide a broken invariant or influence movement.
6. Report and benchmark code uses `len(day.exercises)` as the displayed constraint count, which
   misreports sessions containing Core/supplemental work.
7. Recent main-training-duration commits hardened minute bounds, but their invariant is distinct
   from exercise count and did not close the count evidence waiver.

## Enforcement design

- A canonical duration-to-count-bounds policy is the only source of minimum and maximum MAIN
  counts.
- Builders and duration repair use the policy for capacity, fill, and trim decisions.
- Volume repair and weekly redistribution use canonical MAIN counts and refuse moves/additions
  that violate the bounds. Safety- or hard-volume-driven inability to meet the minimum remains a
  failed/rejected generation, not a relaxed count rule.
- Validation always emits `SESSION_EXERCISE_COUNT_OUT_OF_RANGE` as an error for a bound violation.
- Final Gate recomputes the invariant immediately before acceptance. Count violations are not
  duration constraints and cannot be justified by evidence.
- API/report projections expose MAIN, supplemental/Core, and total counts from the canonical
  helper. Core remains included in total duration calculations.

## Non-goals

- No changes to minimum set count or general weekly-volume targets.
- No artificial rest inflation, duplicate exercises, Core deletion, or safety relaxation.
- No unrelated template, injury, equipment, or catalog refactor.

## Verification

Tests must cover the complete requested duration/count matrix, Core metadata edge cases, Core
duration cost, each downstream mutator, the evidence-waiver regression, and an engine-level
post-mutation failure before output. Existing Program Engine and report tests must remain green.
