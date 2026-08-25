# Phase 11 deterministic benchmark

Profiles tested: 375
Supported cells: 15/15

## Outcomes

- ENGINE_BUG: 0
- PASS: 0
- PASS_WITH_CONSTRAINTS: 322
- QUALITY_ISSUE: 29
- UNSATISFIED: 24

## Fallback

- Template attempts/successes: 286/157
- Total ranked template attempts: 706
- Attempt-depth distribution: {'0': 89, '1': 140, '2': 45, '3': 25, '4': 12, '5': 36, '6': 25, '7': 1, '8': 2}
- Successful attempt-depth distribution: {'1': 97, '2': 22, '3': 20, '4': 8, '5': 3, '6': 6, '7': 1}
- Recovered with alternative: 60
- Alternatives exhausted: 129
- Activations/successes: 194/194
- Overall generation success rate: 0.936
- Reasons: {'CORE_SLOT_UNRESOLVABLE': 65, 'DAYS_MISMATCH': 65, 'EXPERIENCE_LEVEL_MISMATCH': 65, 'INITIAL_TEMPLATE_REJECTED_UNFILLABLE': 111, 'MUSCLE_DIRECT_FREQUENCY_EXCEEDED': 1, 'RECOVERY_SPACING_INVALID': 7, 'REQUIRED_MOVEMENT_PATTERN_MISSING': 5, 'TEMPLATE_CORE_SLOT_UNRESOLVABLE': 95, 'TEMPLATE_DAY:1': 10, 'TEMPLATE_DAY:2': 27, 'TEMPLATE_DAY:3': 33, 'TEMPLATE_DAY:4': 15, 'TEMPLATE_DAY:5': 9, 'TEMPLATE_DAY:6': 17, 'TEMPLATE_PATTERN:hip_extension': 2, 'TEMPLATE_PATTERN:horizontal_pull': 12, 'TEMPLATE_PATTERN:horizontal_push': 4, 'TEMPLATE_PATTERN:squat': 76, 'TEMPLATE_PATTERN:vertical_pull': 1, 'TEMPLATE_PRIORITY_HARD_MINIMUM_UNSATISFIED:glutes': 2, 'TEMPLATE_PRIORITY_HARD_MINIMUM_UNSATISFIED:hamstrings': 2, 'TEMPLATE_SESSION_EXERCISE_COUNT_UNSATISFIED': 16, 'WEEKLY_MUSCLE_VOLUME_EXCEEDED': 1}
- All attempt rejection categories: {'ADAPTATION_EXHAUSTED': 21, 'CORE_SLOT_UNRESOLVED': 171, 'DURATION_RECOVERY_HARD_IMPOSSIBILITY': 34, 'HARD_PRIORITY_MINIMUM_FAILURE': 6, 'VALIDATION_FAILURE': 6}

## Quality metrics

- Validation success rate: 0.936
- template_preservation: 157/157 (1.0)
- priority_target_satisfaction: 40/90 (0.4444)
- body_analysis_target_satisfaction: 0/0 (0.0)
- volume_fit: 3/351 (0.0085)
- muscle_level_volume_fit: 1630/3510 (46.44%)
- muscle_level_volume_constrained_or_outside: 1880
- duration_fit: 50/351 (0.1425)
- recovery_fit: 351/351 (1.0)

## Custom Audits

- Determinism (identical across repeats): 375/375
- Substitution Requests: 6490
- Substitution Successes: 5363
- Substitution Exact Group: 4026
- Substitution Exact Role: 4752
- Substitution Movement Family Fallback: 624
- Substitution No Valid Replacement: 1127
- Equipment Violations: 0
- Safety/Constraint Violations: 0
- Redundancy Violations: 0

## Top audit findings

- EXPLICIT_PRIORITY_PARTIAL: 50
- MISSING_MAJOR_MUSCLE_COVERAGE: 29

## Failure breakdowns

- experience_level: {'advanced': {'PASS_WITH_CONSTRAINTS': 85, 'QUALITY_ISSUE': 6, 'UNSATISFIED': 9}, 'beginner': {'PASS_WITH_CONSTRAINTS': 63, 'QUALITY_ISSUE': 9, 'UNSATISFIED': 3}, 'first_month': {'PASS_WITH_CONSTRAINTS': 63, 'QUALITY_ISSUE': 9, 'UNSATISFIED': 3}, 'intermediate': {'PASS_WITH_CONSTRAINTS': 111, 'QUALITY_ISSUE': 5, 'UNSATISFIED': 9}}
- days: {'2': {'PASS_WITH_CONSTRAINTS': 64, 'QUALITY_ISSUE': 8, 'UNSATISFIED': 3}, '3': {'PASS_WITH_CONSTRAINTS': 87, 'QUALITY_ISSUE': 9, 'UNSATISFIED': 4}, '4': {'PASS_WITH_CONSTRAINTS': 85, 'QUALITY_ISSUE': 9, 'UNSATISFIED': 6}, '5': {'PASS_WITH_CONSTRAINTS': 42, 'QUALITY_ISSUE': 2, 'UNSATISFIED': 6}, '6': {'PASS_WITH_CONSTRAINTS': 44, 'QUALITY_ISSUE': 1, 'UNSATISFIED': 5}}
- goal: {'body_recomposition': {'PASS_WITH_CONSTRAINTS': 56, 'QUALITY_ISSUE': 4}, 'fat_loss': {'PASS_WITH_CONSTRAINTS': 48, 'UNSATISFIED': 12}, 'general_fitness': {'PASS_WITH_CONSTRAINTS': 104, 'QUALITY_ISSUE': 22, 'UNSATISFIED': 9}, 'hypertrophy': {'PASS_WITH_CONSTRAINTS': 54, 'QUALITY_ISSUE': 3, 'UNSATISFIED': 3}, 'strength': {'PASS_WITH_CONSTRAINTS': 60}}
- duration: {'120': {'PASS_WITH_CONSTRAINTS': 45, 'UNSATISFIED': 15}, '30': {'PASS_WITH_CONSTRAINTS': 59, 'QUALITY_ISSUE': 9, 'UNSATISFIED': 7}, '45': {'PASS_WITH_CONSTRAINTS': 53, 'QUALITY_ISSUE': 7}, '60': {'PASS_WITH_CONSTRAINTS': 60}, '75': {'PASS_WITH_CONSTRAINTS': 45, 'QUALITY_ISSUE': 13, 'UNSATISFIED': 2}, '90': {'PASS_WITH_CONSTRAINTS': 60}}
- equipment: {'full_gym': {'PASS_WITH_CONSTRAINTS': 179, 'QUALITY_ISSUE': 9, 'UNSATISFIED': 7}, 'home_all': {'PASS_WITH_CONSTRAINTS': 15}, 'home_band': {'PASS_WITH_CONSTRAINTS': 8, 'QUALITY_ISSUE': 7, 'UNSATISFIED': 15}, 'home_band_pullup': {'PASS_WITH_CONSTRAINTS': 30}, 'home_bw': {'PASS_WITH_CONSTRAINTS': 15, 'QUALITY_ISSUE': 13, 'UNSATISFIED': 2}, 'home_db': {'PASS_WITH_CONSTRAINTS': 30}, 'home_db_bench': {'PASS_WITH_CONSTRAINTS': 30}, 'home_db_pullup': {'PASS_WITH_CONSTRAINTS': 15}}
- limitations: {'': {'PASS_WITH_CONSTRAINTS': 285, 'QUALITY_ISSUE': 14, 'UNSATISFIED': 16}, 'knee': {'PASS_WITH_CONSTRAINTS': 15}, 'lower_back': {'PASS_WITH_CONSTRAINTS': 15}, 'shoulder': {'PASS_WITH_CONSTRAINTS': 7, 'QUALITY_ISSUE': 6, 'UNSATISFIED': 2}, 'wrist': {'QUALITY_ISSUE': 9, 'UNSATISFIED': 6}}

## Catalog snapshot

{'exercise_count': 407, 'template_count': 49, 'template_slugs': ('five-day-advanced-arm-specialization', 'five-day-advanced-leg-specialization', 'five-day-back-specialization', 'five-day-chest-specialization', 'five-day-classic-body-part', 'five-day-ppl-fat-loss-advanced', 'five-day-ppl-upper-lower', 'five-day-quad-priority', 'five-day-shoulder-priority', 'five-day-strength-advanced', 'five-day-strength-intermediate', 'four-day-advanced-chest-specialization', 'four-day-advanced-posterior-chain', 'four-day-arms-priority', 'four-day-back-priority', 'four-day-beginner-body-part-foundation', 'four-day-chest-priority', 'four-day-classic-body-part', 'four-day-first-month-upper-lower', 'four-day-phul', 'four-day-quad-hamstring-split', 'four-day-shoulder-priority', 'four-day-upper-lower-fat-loss-advanced', 'four-day-upper-lower-fat-loss-intermediate', 'four-day-upper-lower-general-fitness-intermediate', 'four-day-upper-lower-strength-advanced', 'four-day-upper-lower-strength-intermediate', 'six-day-back-priority', 'six-day-chest-back-legs-shoulders-arms-legs', 'six-day-chest-priority', 'six-day-ppl-twice', 'six-day-ppl-volume', 'six-day-push-pull-legs-strength', 'three-day-back-priority', 'three-day-chest-priority', 'three-day-first-month-full-body', 'three-day-full-body-drop-set', 'three-day-full-body-fat-loss-intermediate', 'three-day-full-body-foundation', 'three-day-full-body-general-fitness-intermediate', 'three-day-full-body-strength-beginner', 'three-day-full-body-strength-intermediate', 'three-day-push-pull-legs', 'two-day-first-month-full-body', 'two-day-full-body-foundation', 'two-day-full-body-hypertrophy', 'two-day-full-body-strength-beginner', 'two-day-upper-lower-foundation', 'two-day-upper-lower-strength-hypertrophy'), 'catalog_hash': 'eb50eb66c5dfc3e2650620aab02c305e6fd05e614fc0b9a269dfdfbd84d63ffd', 'template_hash': '825fc74864ebd9cef7e994907e68cc26fd597a826a7c0cd729ad413af85ada6e', 'template_seed_hash': '16fbf9c1c0fd62c8205d11aa0436ccc1ccddf8d5997cc9f2c02fcd83b309df6a'}
