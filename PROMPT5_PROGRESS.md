# Prompt 5 Final Closeout

## Benchmark population

- Profiles: 375
- Canonical expected profiles: 375
- Supported matrix cells: 15/15
- Generation rate: 93.60%
- Determinism: 375/375

## Active template library

- Active templates: 49
- Expected active templates: 49
- Catalog hash: eb50eb66c5dfc3e2650620aab02c305e6fd05e614fc0b9a269dfdfbd84d63ffd
- Template hash: 825fc74864ebd9cef7e994907e68cc26fd597a826a7c0cd729ad413af85ada6e
- Template seed hash: 16fbf9c1c0fd62c8205d11aa0436ccc1ccddf8d5997cc9f2c02fcd83b309df6a
- Expected template seed hash: 16fbf9c1c0fd62c8205d11aa0436ccc1ccddf8d5997cc9f2c02fcd83b309df6a

Exact active slugs:

- five-day-advanced-arm-specialization
- five-day-advanced-leg-specialization
- five-day-back-specialization
- five-day-chest-specialization
- five-day-classic-body-part
- five-day-ppl-fat-loss-advanced
- five-day-ppl-upper-lower
- five-day-quad-priority
- five-day-shoulder-priority
- five-day-strength-advanced
- five-day-strength-intermediate
- four-day-advanced-chest-specialization
- four-day-advanced-posterior-chain
- four-day-arms-priority
- four-day-back-priority
- four-day-beginner-body-part-foundation
- four-day-chest-priority
- four-day-classic-body-part
- four-day-first-month-upper-lower
- four-day-phul
- four-day-quad-hamstring-split
- four-day-shoulder-priority
- four-day-upper-lower-fat-loss-advanced
- four-day-upper-lower-fat-loss-intermediate
- four-day-upper-lower-general-fitness-intermediate
- four-day-upper-lower-strength-advanced
- four-day-upper-lower-strength-intermediate
- six-day-back-priority
- six-day-chest-back-legs-shoulders-arms-legs
- six-day-chest-priority
- six-day-ppl-twice
- six-day-ppl-volume
- six-day-push-pull-legs-strength
- three-day-back-priority
- three-day-chest-priority
- three-day-first-month-full-body
- three-day-full-body-drop-set
- three-day-full-body-fat-loss-intermediate
- three-day-full-body-foundation
- three-day-full-body-general-fitness-intermediate
- three-day-full-body-strength-beginner
- three-day-full-body-strength-intermediate
- three-day-push-pull-legs
- two-day-first-month-full-body
- two-day-full-body-foundation
- two-day-full-body-hypertrophy
- two-day-full-body-strength-beginner
- two-day-upper-lower-foundation
- two-day-upper-lower-strength-hypertrophy

## Categories

- PASS: 0
- PASS_WITH_CONSTRAINTS: 322
- QUALITY_ISSUE: 29
- UNSATISFIED: 24
- ENGINE_BUG: 0

## Hard acceptance metrics

- Equipment violations: 0
- Safety/constraint hard violations: 0
- Redundancy violations: 0

## Quality-code audit

- EXPLICIT_PRIORITY_PARTIAL: 50 (B=50)
  - preferred priority target is partial because hard limits or the eligible direct catalog constrain further allocation
- MISSING_MAJOR_MUSCLE_COVERAGE: 29 (B=29)
  - hard volume, session-feasibility, or catalog constraints prevented minimum coverage

Resolved false-positive audit rules:

- DURATION_OUTSIDE_POLICY: 0 final (C; cardio is excluded from the canonical resistance-duration policy).
- SEMANTIC_SLOT_MISMATCH_SELECTED: 0 final degradations (C for optional supplemental tail work).

## Semantic substitution audit

- successful_valid_substitutions: 5363
- recovered_intermediate_attempts: 164
- legitimate_no_valid_replacements: 1097
- final_semantic_degradations: 0
- explained_final_semantic_degradations: 0
- unexplained_final_semantic_failures: 0
- raw substitution requests: 6490
- raw substitution successes: 5363
- exact group: 4026
- exact semantic role: 4752
- movement-family fallback: 624
- raw no-valid-replacement: 1127
- no-valid partition: 1097 legitimate display cases + 30 failed repair attempts later recovered
- recovered intermediate partition: 30 repair attempts + 134 rejected template attempts

## Limitation and priority coverage

- limitation ROM: 30
- limitation axial-load: 15
- limitation balance: 15
- limitation impact: 15
- limitation knee: 15
- limitation lower_back: 15
- limitation overhead: 15
- limitation shoulder: 15
- limitation wrist: 15
- priority back: 15
- priority chest: 15
- priority glutes: 15
- priority hamstrings: 15
- priority quadriceps: 15
- priority shoulders: 15

## Exact UNSAT classification

- 0594444d-4c4f-5470-a816-91edd525d240: legitimate catalog limitation | NO_AVAILABLE_EQUIPMENT_MATCH, NO_ELIGIBLE_EXERCISES
- 5fa5050b-df58-5f71-8df9-13102b1b302c: legitimate catalog limitation | NO_AVAILABLE_EQUIPMENT_MATCH, NO_ELIGIBLE_EXERCISES
- 357aabf6-74e9-5cc6-8e36-12ccaeae0dd2: legitimate catalog limitation | NO_AVAILABLE_EQUIPMENT_MATCH, NO_ELIGIBLE_EXERCISES
- 33ebee9f-281d-542a-a6d3-ed1a28da7b32: legitimate catalog limitation | NO_AVAILABLE_EQUIPMENT_MATCH, NO_ELIGIBLE_EXERCISES
- e29c6bea-e664-5eb3-acb4-bdc0a6606de0: legitimate catalog limitation | NO_AVAILABLE_EQUIPMENT_MATCH, NO_ELIGIBLE_EXERCISES
- 1610f4eb-e2fc-54a1-a569-99f968e4be3b: legitimate catalog limitation | NO_AVAILABLE_EQUIPMENT_MATCH, NO_ELIGIBLE_EXERCISES
- b21a04e4-2e81-5bd7-b93b-5b066681eb71: legitimate catalog limitation | NO_AVAILABLE_EQUIPMENT_MATCH, NO_ELIGIBLE_EXERCISES
- b8d2f0f3-fbf8-586d-a9ce-e60d182b0aec: legitimate catalog limitation | NO_AVAILABLE_EQUIPMENT_MATCH, NO_ELIGIBLE_EXERCISES
- 16cec08f-6883-57bc-b9ba-491dd2613fee: legitimate catalog limitation | NO_AVAILABLE_EQUIPMENT_MATCH, NO_ELIGIBLE_EXERCISES
- 6e0d4ff7-5c3f-5ad6-bedf-e5a543143920: legitimate constraint limitation | UNSATISFIED_CONSTRAINT, PROGRAM_CONSTRUCTION_ALTERNATIVES_EXHAUSTED, EXACT_DAY_SPLIT_ALTERNATIVES_EXHAUSTED, REQUESTED_TRAINING_DAYS_UNSATISFIED, SESSION_CONSTRUCTION_FAILED_REQUIRED_SLOT, REQUIRED_SLOT_HARD_IMPOSSIBILITY, REQUIRED_SESSION_SLOT_UNAVAILABLE:upper, REQUIRED_PATTERN_UNAVAILABLE:horizontal_push,vertical_push, SLOT_MOVEMENT_PATTERN_MISMATCH, REQUIRED_SESSION_SLOT_UNAVAILABLE:chest_triceps, REQUIRED_PATTERN_UNAVAILABLE:horizontal_push, REQUIRED_TARGET_MUSCLE_UNAVAILABLE:chest, MUSCLE_DIRECT_FREQUENCY_EXCEEDED, RECOVERY_SPACING_INVALID
- 549775a4-cf8f-5589-868c-6224c64c624e: legitimate constraint limitation | UNSATISFIED_CONSTRAINT, PROGRAM_CONSTRUCTION_ALTERNATIVES_EXHAUSTED, EXACT_DAY_SPLIT_ALTERNATIVES_EXHAUSTED, REQUESTED_TRAINING_DAYS_UNSATISFIED, SESSION_CONSTRUCTION_FAILED_REQUIRED_SLOT, REQUIRED_SLOT_HARD_IMPOSSIBILITY, REQUIRED_SESSION_SLOT_UNAVAILABLE:back_biceps, REQUIRED_PATTERN_UNAVAILABLE:horizontal_pull,vertical_pull, REQUIRED_TARGET_MUSCLE_UNAVAILABLE:back, SLOT_MOVEMENT_PATTERN_MISMATCH, REQUIRED_SESSION_SLOT_UNAVAILABLE:pull
- a8333d2c-2d7b-5524-a4b2-2cb55d41dc81: legitimate catalog limitation | NO_AVAILABLE_EQUIPMENT_MATCH, NO_ELIGIBLE_EXERCISES
- b3ddafab-f07c-5c48-ab06-fc7e1e7a6d30: legitimate constraint limitation | UNSATISFIED_CONSTRAINT, PROGRAM_CONSTRUCTION_ALTERNATIVES_EXHAUSTED, EXACT_DAY_SPLIT_ALTERNATIVES_EXHAUSTED, REQUESTED_TRAINING_DAYS_UNSATISFIED, SESSION_CONSTRUCTION_FAILED_REQUIRED_SLOT, REQUIRED_SLOT_HARD_IMPOSSIBILITY, REQUIRED_SESSION_SLOT_UNAVAILABLE:upper, REQUIRED_PATTERN_UNAVAILABLE:horizontal_push,vertical_push, SLOT_MOVEMENT_PATTERN_MISMATCH, REQUIRED_SESSION_SLOT_UNAVAILABLE:push, REQUIRED_SESSION_SLOT_UNAVAILABLE:chest_triceps, REQUIRED_PATTERN_UNAVAILABLE:horizontal_push, REQUIRED_TARGET_MUSCLE_UNAVAILABLE:chest
- 6cce0108-9907-5744-84d5-c20630751908: legitimate catalog limitation | NO_AVAILABLE_EQUIPMENT_MATCH, NO_ELIGIBLE_EXERCISES
- 1dacf4fa-f978-5383-aa85-8c8db2a60003: legitimate constraint limitation | UNSATISFIED_CONSTRAINT, PROGRAM_CONSTRUCTION_ALTERNATIVES_EXHAUSTED, EXACT_DAY_SPLIT_ALTERNATIVES_EXHAUSTED, REQUESTED_TRAINING_DAYS_UNSATISFIED, SESSION_CONSTRUCTION_FAILED_REQUIRED_SLOT, REQUIRED_SLOT_HARD_IMPOSSIBILITY, REQUIRED_SESSION_SLOT_UNAVAILABLE:upper, REQUIRED_PATTERN_UNAVAILABLE:horizontal_push,vertical_push, SLOT_MOVEMENT_PATTERN_MISMATCH, REQUIRED_SESSION_SLOT_UNAVAILABLE:push, REQUIRED_SESSION_SLOT_UNAVAILABLE:chest_triceps, REQUIRED_PATTERN_UNAVAILABLE:horizontal_push, REQUIRED_TARGET_MUSCLE_UNAVAILABLE:chest
- 04303910-405c-5d1c-bb07-54585c9d91f9: legitimate catalog limitation | NO_AVAILABLE_EQUIPMENT_MATCH, NO_ELIGIBLE_EXERCISES
- 0d03727f-3745-5a9f-bd85-29b032125438: legitimate catalog limitation | NO_AVAILABLE_EQUIPMENT_MATCH, NO_ELIGIBLE_EXERCISES
- 5be7ad71-f209-5200-a8a4-a4cab597c5e8: legitimate constraint limitation | UNSATISFIED_CONSTRAINT, PROGRAM_CONSTRUCTION_ALTERNATIVES_EXHAUSTED, EXACT_DAY_SPLIT_ALTERNATIVES_EXHAUSTED, REQUESTED_TRAINING_DAYS_UNSATISFIED, SESSION_CONSTRUCTION_FAILED_REQUIRED_SLOT, REQUIRED_SLOT_HARD_IMPOSSIBILITY, REQUIRED_SESSION_SLOT_UNAVAILABLE:upper, REQUIRED_PATTERN_UNAVAILABLE:horizontal_push,vertical_push, SLOT_MOVEMENT_PATTERN_MISMATCH, REQUIRED_SESSION_SLOT_UNAVAILABLE:chest_triceps, REQUIRED_PATTERN_UNAVAILABLE:horizontal_push, REQUIRED_TARGET_MUSCLE_UNAVAILABLE:chest, MUSCLE_DIRECT_FREQUENCY_EXCEEDED, RECOVERY_SPACING_INVALID
- d82df9e8-8a28-5cc5-b4fa-97601a6a6656: legitimate constraint limitation | UNSATISFIED_CONSTRAINT, PROGRAM_CONSTRUCTION_ALTERNATIVES_EXHAUSTED, EXACT_DAY_SPLIT_ALTERNATIVES_EXHAUSTED, REQUESTED_TRAINING_DAYS_UNSATISFIED, SESSION_CONSTRUCTION_FAILED_REQUIRED_SLOT, REQUIRED_SLOT_HARD_IMPOSSIBILITY, REQUIRED_SESSION_SLOT_UNAVAILABLE:back_biceps, REQUIRED_PATTERN_UNAVAILABLE:horizontal_pull,vertical_pull, REQUIRED_TARGET_MUSCLE_UNAVAILABLE:back, SLOT_MOVEMENT_PATTERN_MISMATCH, REQUIRED_SESSION_SLOT_UNAVAILABLE:pull
- 541f57c9-9d32-5d33-bea2-89e23716a1e2: legitimate catalog limitation | NO_AVAILABLE_EQUIPMENT_MATCH, NO_ELIGIBLE_EXERCISES
- 91c27672-c2b7-59b2-8988-ef961dc371a1: legitimate constraint limitation | UNSATISFIED_CONSTRAINT, PROGRAM_CONSTRUCTION_ALTERNATIVES_EXHAUSTED, EXACT_DAY_SPLIT_ALTERNATIVES_EXHAUSTED, REQUESTED_TRAINING_DAYS_UNSATISFIED, SESSION_CONSTRUCTION_FAILED_REQUIRED_SLOT, REQUIRED_SLOT_HARD_IMPOSSIBILITY, REQUIRED_SESSION_SLOT_UNAVAILABLE:upper, REQUIRED_PATTERN_UNAVAILABLE:horizontal_push,vertical_push, SLOT_MOVEMENT_PATTERN_MISMATCH, REQUIRED_SESSION_SLOT_UNAVAILABLE:push, REQUIRED_SESSION_SLOT_UNAVAILABLE:chest_triceps, REQUIRED_PATTERN_UNAVAILABLE:horizontal_push, REQUIRED_TARGET_MUSCLE_UNAVAILABLE:chest
- b18b11f3-21b6-5931-97a3-3c79f3434e3d: legitimate constraint limitation | UNSATISFIED_CONSTRAINT, PROGRAM_CONSTRUCTION_ALTERNATIVES_EXHAUSTED, EXACT_DAY_SPLIT_ALTERNATIVES_EXHAUSTED, REQUESTED_TRAINING_DAYS_UNSATISFIED, RECOVERY_SPACING_INVALID, SESSION_DURATION_EXCEEDED, SESSION_DURATION_OVER_TARGET, SESSION_DURATION_TARGET_UNSATISFIED, REQUIRED_MOVEMENT_PATTERN_MISSING
- a8cf560d-0084-5260-bc80-6838e96d500d: legitimate catalog limitation | NO_AVAILABLE_EQUIPMENT_MATCH, NO_ELIGIBLE_EXERCISES
- 4fe44e83-55b5-54b8-8a7d-b9c244316fad: legitimate constraint limitation | UNSATISFIED_CONSTRAINT, PROGRAM_CONSTRUCTION_ALTERNATIVES_EXHAUSTED, EXACT_DAY_SPLIT_ALTERNATIVES_EXHAUSTED, REQUESTED_TRAINING_DAYS_UNSATISFIED, SESSION_CONSTRUCTION_FAILED_REQUIRED_SLOT, REQUIRED_SLOT_HARD_IMPOSSIBILITY, REQUIRED_SESSION_SLOT_UNAVAILABLE:upper, REQUIRED_PATTERN_UNAVAILABLE:horizontal_push,vertical_push, SLOT_MOVEMENT_PATTERN_MISMATCH, REQUIRED_SESSION_SLOT_UNAVAILABLE:chest_triceps, REQUIRED_PATTERN_UNAVAILABLE:horizontal_push, REQUIRED_TARGET_MUSCLE_UNAVAILABLE:chest, REQUIRED_SESSION_SLOT_UNAVAILABLE:push

## Consistency checks

- Profile records equal aggregate: True
- Category totals equal profiles: True
- UNSAT classifications equal UNSAT: True
- Determinism denominator equals profiles: True
- Template count and slugs match seed intent: True
- Substitution requests equal successes plus no-valid: True

## Test verification

- Fresh benchmark: 375 profiles; strict verifier READY
- Focused benchmark tests: 34 passed
- Program Engine tests: 827 passed
- Full backend pytest: 2261 passed, 1 live test skipped
- Ruff affected files: passed
- mypy affected files: passed
- git diff --check: passed

## Final verdict

READY FOR PROMPT 6
