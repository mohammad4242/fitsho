# Imported exercise programming metadata

## Goal

Every valid Free Exercise DB record receives programming metadata during import.
All imported records are enabled for workout-plan generation by default. Existing
imported records are corrected when the importer runs again.

## Classification

The importer derives metadata from the source name, target muscle, instructions,
steps, form cues, and common mistakes.

- Movement pattern uses explicit exercise-name and movement keywords first. Known
  examples include push, pull, row, squat, hinge, lunge, curl, extension, raise,
  shrug, crunch, rotation, plank, stretch, and calf raise. A record without a
  reliable match uses `other`.
- Exercise type is `mobility` for explicit stretches, `core` for trunk exercises,
  `isolation` for single-joint patterns, `compound` for recognised multi-joint
  patterns, and `other` only when classification is not reliable.
- Caution tags are only added for explicit mechanical characteristics: spinal
  flexion, lower-back loading, deep knee flexion, overhead position, shoulder
  rotation, wrist loading, neck loading, or balance demand. No injury or medical
  claim is inferred from a video.
- `is_programmable` is `true` for every valid imported record as requested.
- `needs_review` remains `true` because translations and source safety metadata
  still require human review.

## Existing and future records

The importer applies the same classifier before saving a new record and while
checking an existing record. A classifier change therefore updates existing
records rather than skipping them as current. The five currently imported
records receive the following results on the next import:

| Source ID | Pattern | Type | Cautions |
| --- | --- | --- | --- |
| 0489 | hip_hinge | compound | lower_back_loading |
| drv-45-degree-bycicle-twisting-crunch | spinal_flexion | core | spinal_flexion, neck_loading |
| drv-45-degree-bycicle-twisting-crunch-1 | spinal_flexion | core | spinal_flexion, neck_loading |
| drv-stretching-all-fours-squad-stretch | other | mobility | none |
| 0970 | vertical_pull | compound | overhead_position |

## Idempotency and tests

The import-current comparison includes programming metadata and caution tags.
The importer synchronizes caution-tag rows without duplicates. Tests cover the
five classifications, a conservative unmatched record, update of an existing
import, and programmable defaults.
