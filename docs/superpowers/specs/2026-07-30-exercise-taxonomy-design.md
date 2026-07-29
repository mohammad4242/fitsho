# Exercise taxonomy: full-body, cardio, and smaller upper-body muscles

## Goal

Import all 317 Free Exercise DB records without inventing anatomical classifications. Keep the exercise library easy to browse and keep all imported exercises eligible for programme generation.

## Taxonomy

The library will use independent dimensions instead of one overloaded category.

- **Body region:** existing regions remain. An exercise may have no body region when the source does not support one.
- **Primary muscle:** existing groups remain; add only `forearms` and `neck`. Both belong to the upper-body category and are visually secondary to the larger upper-body groups.
- **Exercise type:** keep the existing `compound`, `isolation`, `core`, `mobility`, and `other` values. Stretching stays `mobility`; do not add a second stretch type.
- **Labels:** add a many-to-many exercise-label relation with the fixed values `full_body` and `cardio`. Labels are not muscles and are independently filterable.

`primary_muscle` and `body_region` become nullable. An empty value means the source does not support a reliable Fitsho enum mapping; it is never a guessed classification.

## Import policy

The importer remains idempotent on `(source, source_id)` and preserves all source metadata.

- Map `forearms` and `forearm extensors` to `forearms`; map `neck flexors` and `sternocleidomastoid` to `neck`.
- Add the `cardio` label only when the source clearly identifies cardiovascular work. Add `full_body` only when the source clearly identifies full-body work.
- Keep stretching records as `mobility`, even where the source incorrectly uses `bodyPart=cardio`.
- For `hip flexors`, `abductors`, and `peroneals`, retain the raw source value, leave the primary muscle empty, set `needs_review=true`, and include the value in the import report's unmapped-enum list.
- Records with missing reliable body region are imported with a null body region, not a fabricated one.
- Every imported record remains `is_programmable=true` and `needs_review=true`.
- Existing media copying, missing-media reporting, translations, source identifiers, and dry-run behaviour remain unchanged.

This imports the remaining 33 source records while preserving the distinction between a known mapping and an unresolved source value.

## API and admin

- Include nullable `body_region` and `primary_muscle`, plus `labels`, in exercise summaries and details.
- Add filtering by one or more labels and exercise type.
- Return dedicated catalog sections for `full_body`, `cardio`, and `mobility` without treating labels as muscle groups.
- In the admin form, primary muscle and body region are optional; labels are selectable fixed chips. Validation permits empty anatomy only when the record is marked for review.

## Library UI

- Keep the current body-region navigation for anatomical browsing.
- Show separate entry points and filters for «تمام\u200cبدن», «هوازی», and «کشش و موبیلیتی».
- Display forearms and neck as visually smaller items within upper body, not as top-level sections.
- Exercises with unresolved anatomy remain searchable and discoverable through type and labels, but are not falsely listed under a muscle filter.

## Programme generation

All records are eligible for programme generation. The candidate and validation logic must tolerate null anatomy.

Cardio-labelled records must not displace a required compound or isolation strength movement. They may be selected only for an explicit conditioning/cardio block when that part of the programme request is supported. Mobility retains its existing warm-up/cool-down role.

## Data migration and rollback

One Alembic migration will:

1. relax the `exercises.body_region` and `exercises.primary_muscle` null constraints;
2. update their enum check constraints for `forearms` and `neck`;
3. create `exercise_labels` and its exercise association table with uniqueness and cascade deletion;
4. add indexes for label filtering.

Downgrade removes the label relation and restores the prior constraints only after unresolved rows are removed or given explicit replacement values. The importer can recreate all records from the local source dataset and media files.

## Verification

- Migration upgrade and downgrade tests.
- Import tests for forearms, neck, cardio/full-body labels, null anatomy, and the 33 previously skipped records.
- Preserve tests for mapping, duplicate prevention, dry run, missing media, invalid records, and media re-copying.
- API/admin/UI tests for labels and nullable anatomy.
- Workout-selector tests proving cardio does not replace strength work.
- Full backend test suite, frontend test suite, frontend production build, import dry run, full idempotent import, and report inspection.
