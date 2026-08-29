# Weekly Muscle Volume Design

## Scope

Correct the Weekly Muscle Volume implementation so that classified muscles use
training-age-aware direct-set ranges for weekly planning and hard enforcement.
Preserve direct frequency as a soft preference, effective-volume accounting,
secondary-set credit, session hard caps, safety, duration, and all unrelated
Program Engine behavior.

## Design

`weekly_direct_volume_range()` remains the source of truth for classified
muscles:

- Novice (`training_age_months <= 5`): large 6-10, small 4-6.
- Intermediate (`6 <= training_age_months <= 24`): large 10-24, small 6-20.
- Advanced (`training_age_months > 24`): large 12-30, small 8-20.

The existing muscle classification remains unchanged. Unclassified muscles
continue through their existing ruleset fallback.

Planner targets, hard maximums, clamps, and `VolumeTarget.maximum_hard` use the
classified weekly direct range. Legacy `maximum_sets` and
`secondary_muscle_maximum_sets` remain fallback values only.

Weekly hard validation, weekly repair simulations, and duration weekly-hard
checks use direct sets for classified muscles. Effective sets remain separately
calculated for secondary contribution, recovery, reporting, and observability.
The existing `secondary_set_credit = 0.5` is unchanged.

Session hard direct caps remain 12, 20, and 30 for novice, intermediate, and
advanced training ages respectively. Direct frequency remains a warning and
ranking preference, never a validation, repair, or duration hard block.

## Verification

Add boundary tests for training ages 0, 5, 6, 24, 25, and 60 across all
classified and unclassified muscles. Add direct-versus-effective weekly hard
cap regressions, soft-range warning coverage, session-cap regressions, and
direct-frequency soft-preference regressions. Run targeted Program Engine
tests, then the full Program Engine suite, plus scoped lint/type/diff checks.
