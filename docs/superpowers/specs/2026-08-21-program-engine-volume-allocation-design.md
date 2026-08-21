# Program Engine Volume Allocation Design

## Scope

Fix excessive working-set dumping in the Program Engine. Injury/caution,
equipment, training-day, template-recovery, prescription, strength, and
session-duration policies remain unchanged.

## Root cause

`prescribe_sessions` can assign all direct target sets to one appearance when a
muscle has only one selected exercise. `volume_repair._select_addition_candidate`
and its fallback then repeatedly increment that same exercise. The existing
guard limits direct sets for a muscle in a session, but has no per-exercise
working-set policy, so a single exercise can reach 5–6 sets.

## Design

Add a centralized ruleset policy for maximum working sets per exercise per
session. The policy uses the existing training status, goal, exercise type,
priority status, and weekly muscle exposure. Normal contexts remain at four
sets; explicit advanced/strength/priority/single-exposure contexts may reach
the ruleset's bounded five-set ceiling. The existing per-muscle session and
weekly hard maximums remain authoritative.

Apply the policy in initial direct-set assignment, set redistribution, new
exercise additions, and ordinary set additions. A candidate cannot receive a
new set when its context cap is reached.

When volume is under target, repair order becomes:

1. Add a compatible second catalog exercise for the needed muscle/pattern.
2. Prefer an eligible week/session with lower current direct exposure.
3. Add a set to an existing exercise only when its context cap and session
   duration permit it.
4. If only the soft target remains and no safe compatible option exists, stop
   and emit `VOLUME_REPAIR_SOFT_TARGET_REDUCED`.

Hard safety, equipment, session, per-muscle, and weekly constraints are never
relaxed. Existing reason-code tracing is extended for cap application,
redistribution, and soft-target reduction.

## Validation and tests

Final validation will reject any exercise above its context-specific cap while
retaining all existing volume and session checks. Tests will cover direct cap
policy, multi-candidate distribution, multi-day distribution, priority
volume, limited-catalog soft reduction, weekly hard maximums, effective-volume
accounting, session duration, named regression exercises, and end-to-end
`generate_program` output.
