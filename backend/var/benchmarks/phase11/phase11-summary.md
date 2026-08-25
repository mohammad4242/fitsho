# Phase 11 deterministic benchmark

Profiles tested: 375
Supported cells: 15/15

## Outcomes

- ENGINE_BUG: 0
- PASS: 0
- PASS_WITH_CONSTRAINTS: 208
- QUALITY_ISSUE: 143
- UNSATISFIED: 24

## Fallback

- Template attempts/successes: 286/163
- Total ranked template attempts: 731
- Attempt-depth distribution: {'0': 89, '1': 137, '2': 44, '3': 27, '4': 11, '5': 40, '6': 9, '7': 17, '8': 1}
- Successful attempt-depth distribution: {'1': 97, '2': 22, '3': 23, '4': 7, '5': 7, '6': 7}
- Recovered with alternative: 66
- Alternatives exhausted: 123
- Activations/successes: 188/188
- Overall generation success rate: 0.936
- Reasons: {'CORE_SLOT_UNRESOLVABLE': 65, 'DAYS_MISMATCH': 65, 'EXPERIENCE_LEVEL_MISMATCH': 65, 'INITIAL_TEMPLATE_REJECTED_UNFILLABLE': 114, 'RECOVERY_SPACING_INVALID': 4, 'REQUIRED_MOVEMENT_PATTERN_MISSING': 5, 'TEMPLATE_CORE_SLOT_UNRESOLVABLE': 102, 'TEMPLATE_DAY:1': 9, 'TEMPLATE_DAY:2': 26, 'TEMPLATE_DAY:3': 39, 'TEMPLATE_DAY:4': 18, 'TEMPLATE_DAY:5': 5, 'TEMPLATE_DAY:6': 17, 'TEMPLATE_PATTERN:hip_extension': 2, 'TEMPLATE_PATTERN:horizontal_pull': 9, 'TEMPLATE_PATTERN:horizontal_push': 3, 'TEMPLATE_PATTERN:squat': 85, 'TEMPLATE_PATTERN:vertical_pull': 3, 'TEMPLATE_SESSION_EXERCISE_COUNT_UNSATISFIED': 12}
- All attempt rejection categories: {'ADAPTATION_EXHAUSTED': 19, 'CORE_SLOT_UNRESOLVED': 175, 'DURATION_RECOVERY_HARD_IMPOSSIBILITY': 33, 'HARD_PRIORITY_MINIMUM_FAILURE': 2, 'VALIDATION_FAILURE': 5}

## Quality metrics

- Validation success rate: 0.936
- template_preservation: 163/163 (1.0)
- priority_target_satisfaction: 86/163 (0.5276)
- body_analysis_target_satisfaction: 0/0 (0.0)
- volume_fit: 2/351 (0.0057)
- muscle_level_volume_fit: 1572/3510 (44.79%)
- muscle_level_volume_constrained_or_outside: 1938
- duration_fit: 48/351 (0.1368)
- recovery_fit: 351/351 (1.0)

## Custom Audits

- Determinism (identical across repeats): 375/375
- Substitution Requests: 6526
- Substitution Successes: 5512
- Substitution Exact Group: 4205
- Substitution Exact Role: 4878
- Substitution Movement Family Fallback: 635
- Substitution No Valid Replacement: 1014
- Equipment Violations: 0
- Safety/Constraint Violations: 0
- Redundancy Violations: 0

## Top audit findings

- DURATION_OUTSIDE_POLICY: 269
- EXPLICIT_PRIORITY_PARTIAL: 77
- MISSING_MAJOR_MUSCLE_COVERAGE: 22

## Failure breakdowns

- experience_level: {'advanced': {'PASS_WITH_CONSTRAINTS': 63, 'QUALITY_ISSUE': 28, 'UNSATISFIED': 9}, 'beginner': {'PASS_WITH_CONSTRAINTS': 35, 'QUALITY_ISSUE': 37, 'UNSATISFIED': 3}, 'first_month': {'PASS_WITH_CONSTRAINTS': 38, 'QUALITY_ISSUE': 34, 'UNSATISFIED': 3}, 'intermediate': {'PASS_WITH_CONSTRAINTS': 72, 'QUALITY_ISSUE': 44, 'UNSATISFIED': 9}}
- days: {'2': {'PASS_WITH_CONSTRAINTS': 12, 'QUALITY_ISSUE': 59, 'UNSATISFIED': 4}, '3': {'PASS_WITH_CONSTRAINTS': 35, 'QUALITY_ISSUE': 61, 'UNSATISFIED': 4}, '4': {'PASS_WITH_CONSTRAINTS': 75, 'QUALITY_ISSUE': 18, 'UNSATISFIED': 7}, '5': {'PASS_WITH_CONSTRAINTS': 45, 'QUALITY_ISSUE': 1, 'UNSATISFIED': 4}, '6': {'PASS_WITH_CONSTRAINTS': 41, 'QUALITY_ISSUE': 4, 'UNSATISFIED': 5}}
- goal: {'body_recomposition': {'PASS_WITH_CONSTRAINTS': 39, 'QUALITY_ISSUE': 21}, 'fat_loss': {'PASS_WITH_CONSTRAINTS': 32, 'QUALITY_ISSUE': 16, 'UNSATISFIED': 12}, 'general_fitness': {'PASS_WITH_CONSTRAINTS': 69, 'QUALITY_ISSUE': 55, 'UNSATISFIED': 11}, 'hypertrophy': {'PASS_WITH_CONSTRAINTS': 35, 'QUALITY_ISSUE': 24, 'UNSATISFIED': 1}, 'strength': {'PASS_WITH_CONSTRAINTS': 33, 'QUALITY_ISSUE': 27}}
- duration: {'120': {'PASS_WITH_CONSTRAINTS': 27, 'QUALITY_ISSUE': 18, 'UNSATISFIED': 15}, '30': {'PASS_WITH_CONSTRAINTS': 43, 'QUALITY_ISSUE': 25, 'UNSATISFIED': 7}, '45': {'PASS_WITH_CONSTRAINTS': 45, 'QUALITY_ISSUE': 13, 'UNSATISFIED': 2}, '60': {'PASS_WITH_CONSTRAINTS': 28, 'QUALITY_ISSUE': 32}, '75': {'PASS_WITH_CONSTRAINTS': 33, 'QUALITY_ISSUE': 27}, '90': {'PASS_WITH_CONSTRAINTS': 32, 'QUALITY_ISSUE': 28}}
- equipment: {'full_gym': {'PASS_WITH_CONSTRAINTS': 103, 'QUALITY_ISSUE': 85, 'UNSATISFIED': 7}, 'home_all': {'PASS_WITH_CONSTRAINTS': 11, 'QUALITY_ISSUE': 4}, 'home_band': {'PASS_WITH_CONSTRAINTS': 10, 'QUALITY_ISSUE': 5, 'UNSATISFIED': 15}, 'home_band_pullup': {'PASS_WITH_CONSTRAINTS': 23, 'QUALITY_ISSUE': 5, 'UNSATISFIED': 2}, 'home_bw': {'PASS_WITH_CONSTRAINTS': 15, 'QUALITY_ISSUE': 15}, 'home_db': {'PASS_WITH_CONSTRAINTS': 21, 'QUALITY_ISSUE': 9}, 'home_db_bench': {'PASS_WITH_CONSTRAINTS': 17, 'QUALITY_ISSUE': 13}, 'home_db_pullup': {'PASS_WITH_CONSTRAINTS': 8, 'QUALITY_ISSUE': 7}}
- limitations: {'': {'PASS_WITH_CONSTRAINTS': 185, 'QUALITY_ISSUE': 121, 'UNSATISFIED': 24}, 'knee': {'PASS_WITH_CONSTRAINTS': 10, 'QUALITY_ISSUE': 5}, 'lower_back': {'PASS_WITH_CONSTRAINTS': 7, 'QUALITY_ISSUE': 8}, 'shoulder': {'PASS_WITH_CONSTRAINTS': 6, 'QUALITY_ISSUE': 9}}

## Catalog snapshot

{'exercise_count': 407, 'template_count': 50, 'catalog_hash': 'eb50eb66c5dfc3e2650620aab02c305e6fd05e614fc0b9a269dfdfbd84d63ffd', 'template_hash': 'c2d1bb7c670e2605423896ddd64d7987ddc878660c4a3b8313736d0dbbc4ba13'}
