# Program Engine Strength Role Design

## Scope

Fix only Strength-goal exercise ranking, session ordering, and prescription. Existing caution, equipment, day-count, template recovery, volume, duration, prescription-mode, split, and progression systems remain unchanged.

## Root cause

`prescription_for()` currently maps every non-isolation Strength exercise to the same low-repetition `strength_compound` rule. The ranker also gives a broad compound bonus without distinguishing a primary strength lift from a secondary compound or an accessory. As a result, eligible bodyweight compounds and isolation-support movements can be treated like the main lift.

## Design

Add an internal deterministic `StrengthExerciseRole` classifier with three roles:

- `PRIMARY_STRENGTH`
- `SECONDARY_COMPOUND`
- `ACCESSORY`

The classifier uses only stable exercise metadata and request context: exercise type, movement pattern, equipment, difficulty, skill/stability demand, fatigue/setup cost, training status, and goal. It must not inspect display names. A primary role requires a strong positive strength-suitability signal; ambiguous candidates fall back to `SECONDARY_COMPOUND` for compounds and `ACCESSORY` otherwise. Caution/equipment filtering remains upstream and is never bypassed.

Strength ranking receives role-aware ruleset weights. A suitable primary candidate ranks above a secondary compound or accessory when all are eligible, while the existing beginner demand penalties remain active. Session ordering uses the same role classifier so primary work appears first, then secondary compounds, then accessories/trunk work.

Prescription rules remain in the ruleset rather than global constants. Strength role selects the base rule, then the existing goal/status and exercise prescription-mode handling continues to apply. Role-specific modifiers are bounded and conservative; they may reduce or adjust a base rule for beginner status or demanding exercise characteristics, but an uncertain exercise never receives the primary-strength rule. The existing RIR/progression architecture is preserved.

The role is internal only. No public API, database, catalog schema, or persisted exercise metadata is changed.

## Observability

Role decisions add internal reason codes to ranking/prescription traces. Conservative fallback records a warning reason when metadata is insufficient or contradictory. Existing safety and equipment rejection reason codes remain authoritative.

## Tests

Add direct tests for deterministic classification, conservative fallback, role-aware ranking, and role-aware prescription. Add beginner and advanced cases, safety/equipment fallback cases, and an end-to-end Advanced Strength generation regression proving that a suitable primary compound precedes Push-Up/accessories and that accessory prescriptions do not use the primary low-rep/long-rest rule.
