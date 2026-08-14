# Exercise Muscle Focus Taxonomy Design

## Goal

Extend the Exercise Library hierarchy to:

`Body Region -> Muscle Group -> Muscle Focus -> Exercises`

The existing `body_region`, `primary_muscle`, and `secondary_muscles` contracts remain intact. `muscle_focus` adds one controlled programming-oriented classification per exercise.

## Persistence and invariants

- Add a global `MuscleFocus` string enum and a nullable `exercises.muscle_focus` column.
- An exercise with a known `primary_muscle` must have exactly one compatible focus after migration.
- An exercise without a `primary_muscle` must have `muscle_focus = NULL`.
- Enforce controlled enum values and primary-muscle/focus compatibility in the database and application validation.
- Add an index on `(primary_muscle, muscle_focus)` for catalogue filtering.
- `all` is a UI/query state only and is never stored.

## Approved focus taxonomy

| Muscle group | Focuses |
| --- | --- |
| Chest | `general_chest`, `upper_chest`, `mid_chest`, `lower_chest` |
| Back | `general_back`, `lats`, `mid_back_rhomboids`, `upper_back` |
| Shoulders | `general_shoulders`, `front_delt`, `lateral_delt`, `rear_delt` |
| Biceps | `general_biceps`, `biceps_brachii`, `brachialis_brachioradialis` |
| Triceps | `general_triceps`, `triceps_long_head`, `triceps_lateral_medial_heads` |
| Traps | `upper_traps`, `mid_lower_traps` |
| Forearms | `general_forearms`, `forearm_flexors`, `forearm_extensors` |
| Neck | `neck_flexion`, `neck_lateral_extension` |
| Glutes | `glute_max`, `glute_medius_minimus` |
| Quadriceps | `general_quadriceps`, `rectus_femoris`, `vasti` |
| Hamstrings | `hamstrings_hip_extension`, `hamstrings_knee_flexion` |
| Adductors | `hip_adduction`, `adductor_mobility` |
| Calves | `general_calves`, `gastrocnemius`, `soleus` |
| Abs | `trunk_flexion`, `hip_flexion_posterior_tilt`, `anti_extension` |
| Obliques | `trunk_rotation`, `lateral_flexion`, `anti_rotation` |
| Lower back | `lumbar_erectors`, `thoracic_mobility` |

General focuses represent genuinely broad mechanics. They must not be used to hide uncertain classification.

## Classification and audit

The live catalogue currently contains 341 exercises: 317 Free Exercise DB imports, 24 training-template placeholders, and 23 special exercises with no primary muscle.

Classification precedence:

1. Exact source target metadata, including values such as `upper pectorals`, `anterior deltoid`, `posterior deltoid`, `rhomboids`, `upper back`, `gluteus medius`, and `forearm extensors`.
2. Source secondary muscles, movement pattern, exercise type, steps, instructions, form cues, and common mistakes.
3. Mechanically explicit variants such as incline/flat/decline presses, vertical/horizontal pulls, front/lateral/rear raises, overhead triceps work, hip hinges, leg curls, seated/standing calf raises, and rotation/anti-rotation core work.
4. Reliable exercise/anatomy references for any remaining ambiguity.

A checked-in audit manifest records the stable exercise identity, assigned focus, and classification basis. The importer uses the same deterministic classifier for future records and includes the focus in its current-record comparison so outdated imports are updated.

Before applying the data migration, generate and review a full-catalogue audit. Any exercise still lacking a confident focus is reported by stable ID with its relevant metadata. Implementation pauses for user direction instead of assigning a guessed value.

The 23 cardio, full-body, hip-flexor, abductor, or peroneal records whose existing `primary_muscle` is null remain intentionally outside the muscle hierarchy with a null focus. They remain accessible through existing special categories and admin filters.

Seven records previously assigned to `abs` are corrected to `obliques` because their primary mechanics are rotation, anti-rotation, or lateral flexion: `0230`, `0862`, `0407`, `0562`, `pallof-press`, `side-plank`, and `0777`. This user-approved data correction takes precedence over preserving those seven records in the old Abs `All` result; all other primary-muscle memberships remain unchanged.

## API and admin contracts

- Add optional `muscle_focus` filtering to public and protected admin exercise-list endpoints.
- Add `muscle_focus` to public summaries/details and protected admin create/edit schemas.
- Validate focus compatibility when admins create or edit an exercise.
- Extend the categories response with ordered bilingual focus definitions grouped by muscle.
- Existing requests and URLs without `muscle_focus` retain their current results, pagination, search, equipment, difficulty, label, status, and exercise-type behavior.
- Workout generation continues to consume `primary_muscle` and existing programming metadata; adding focus does not alter eligibility, ranking, or prescriptions.

## Import, seeds, and placeholders

- Add an explicit focus to every curated seed and training-template placeholder.
- Classify imported exercises from original `target`, `secondaryMuscles`, and mechanical metadata before considering normalized names.
- Persist the focus on import and update it on later idempotent runs.
- Report an unmapped/uncertain focus as a validation failure instead of silently defaulting.

## Exercise Library UI

- Selecting a muscle reveals a third selector containing `All` followed by that muscle's ordered focus categories.
- `All` omits `muscle_focus` from the URL and API request, preserving today's complete muscle-group result.
- A specific selection adds `muscle_focus=<value>` and resets pagination to page 1.
- Region or muscle changes clear stale focus values.
- The breadcrumb includes the selected focus; result headings use its localized name.
- Existing query parameters, detail return links, admin add/edit return context, search, filters, pagination, RTL/LTR behavior, and mobile layout remain intact.
- The admin create/edit form exposes a focus selector limited to the selected primary muscle and keeps the field editable.

## Migration

- Create the new column and constraints from the current Alembic head `20260814_77`.
- Backfill every exercise with a known primary muscle from the reviewed audit manifest.
- Verify zero known-primary exercises remain without focus before enabling the compatibility constraint.
- Downgrade removes the index, constraints, and column without changing existing muscle data.

## Verification

- Database model and migration upgrade/downgrade tests.
- Taxonomy compatibility and classifier unit tests.
- Seed and importer idempotency/classification tests.
- Public and admin API serialization/filter/security tests.
- Frontend API, query, selection, breadcrumb, admin form, RTL/LTR, pagination, and backward-compatibility tests.
- Full backend tests, Ruff, MyPy, full frontend tests, lint, and production build.
- Post-migration catalogue checks for total counts, per-muscle counts under `All`, per-focus totals, null invariants, and representative examples.
