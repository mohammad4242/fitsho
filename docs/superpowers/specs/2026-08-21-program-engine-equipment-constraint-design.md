# Program Engine Equipment Constraint Design

## Scope

Fix only Program Engine equipment safety for exercise selection and final
program output. Preserve day count, volume, duration, strength programming,
split logic, caution behavior, and public APIs.

## Root cause

The profile-to-available-equipment mapping already represents the intended Home
setups: bodyweight-only provides bodyweight, dumbbells provides bodyweight and
dumbbell, and Gym uses the project's complete gym set. The hard subset check is
also present in the selector. However, imported bodyweight vertical-pull
exercises, including Pull-Up variants and Bench Pull-Up, have incomplete
equipment metadata and are stored as bodyweight-only. They therefore pass the
subset check for Home users.

## Design

1. Keep the existing Profile equipment mapping and hard subset filtering.
2. Correct the narrow catalog metadata gap:
   - bodyweight vertical-pull exercises require `PULL_UP_BAR`;
   - Bench Pull-Up additionally requires `BENCH`;
   - preserve all explicit source equipment and represent multi-equipment
     requirements as multiple catalog rows.
   Apply this both to future imports and existing catalog rows through a
   focused data migration.
3. Add a conservative effective-equipment rule in the Program Engine for
   bodyweight vertical-pull candidates missing the bar metadata, so stale or
   synthetic metadata cannot make them Home-eligible before migration catches
   up. Empty equipment remains ineligible through required-metadata checks.
4. Use the same effective requirements in eligibility and final validation.
   Existing replacement/fallback paths continue to draw only from the eligible
   pool; if final validation still finds an unavailable exercise, generation
   fails safely rather than returning an unsafe program.

## Tests

- Direct eligibility: Home bodyweight, Home dumbbells, multi-equipment, Gym,
  and a no-equipment-caution baseline.
- Direct final validation for an unavailable effective requirement.
- End-to-end `generate_program` with explicit equipment metadata, including a
  regression for Pull-Up/Bench Pull-Up style Home leakage.
- Legacy catalog selector equipment filtering.
- Import metadata regression for vertical-pull and Bench Pull-Up requirements.

Assertions use equipment metadata and movement metadata, not exercise names,
except where a narrowly scoped importer fixture identifies the source record.
