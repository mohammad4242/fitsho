# Training Template Supported Levels Design

## Goal

Replace 41 level-specific catalog rows with 17 shared canonical training templates. Each
template has one ID, one days/slots definition, and one non-empty `supported_levels` list.
Admin-created templates use the same model and Program Engine path.

## Data model

`TrainingProgramTemplate` owns:

- canonical metadata (`slug`, names, descriptions, days per week, goal, tags, rationale, source);
- `supported_levels`, containing unique values from `first_month`, `beginner`,
  `intermediate`, and `advanced`;
- ordered `TrainingProgramTemplateDay` rows;
- ordered `TrainingProgramTemplateSlot` rows through each day.

The scalar `training_level` column is removed. No level variant table or level-specific day or
slot content is introduced. `supported_levels` is persisted as a PostgreSQL JSON array because
it is a small bounded attribute set and matches existing JSON-backed template metadata.

## Canonical catalog

`CANONICAL_TEMPLATE_DEFINITIONS` remains the source of truth for T01-T17. Seed generation emits
exactly 17 templates rather than expanding one row per supported level. Each definition supplies:

- the union of approved supported levels;
- the shared day structure;
- the canonical movement slug declared by each movement definition;
- the shared baseline slot prescription fields declared by the canonical day/slot definition;
- normal straight-set intensity and existing core/accessory adaptation priority semantics.

Level-specific movement and prescription rendering is removed. Training level becomes eligibility
metadata only. Existing downstream personalization remains responsible for injury, equipment,
duration, priority, recovery, safety, and other adaptations.

## Migration

The Alembic migration is transactional:

1. Add nullable `supported_levels`.
2. Backfill every row with its current scalar level.
3. Group the managed T01-T17 rows by canonical catalog slug.
4. Keep one canonical row and union all group levels into `supported_levels`.
5. Repoint no external template references because days/slots are owned children and generated
   workout plans store snapshots rather than template foreign keys.
6. Delete redundant managed rows through existing cascades.
7. Rename keeper slugs from level-specific slugs to canonical slugs.
8. Make `supported_levels` non-null and remove `training_level` plus its constraint/index usage.

Before applying the migration to the live database, create and validate a PostgreSQL backup. After
the schema migration, run canonical seed synchronization so shared days/slots are rebuilt from the
approved definitions, not selected from a former level row.

The downgrade restores a scalar level using the first supported value. It is schema-safe but cannot
recreate the deleted duplicate rows, which is documented in the migration.

## Admin API

Admin template reads expose `supported_levels` and never expose scalar `training_level`.

- `GET /api/v1/admin/training-program-templates` accepts optional `days_per_week` and
  `training_level`; level filtering checks membership in `supported_levels`.
- `POST` creates one template with one or more supported levels.
- `PUT /{template_id}` replaces shared metadata, supported levels, days, and slots atomically.
- `DELETE /{template_id}` hard-deletes the template and owned days/slots after trusted-origin and
  Admin checks.

Writes reject empty lists, duplicates, and values outside the four supported training levels.
Exercise, template-shape, focus-tag, and prescription validation remains unchanged.

## Admin UI

The library renders each template once. Day and level filters are sent to the API. A template whose
levels contain both beginner and intermediate appears under either level with the same template ID.
Cards show all supported levels.

The editor uses four multi-select controls. Adding or removing a level only edits
`supported_levels`; it never clones days or slots. Existing shared days and slots stay visible once.
The editor supports create, update, and confirmed delete.

## Program Engine

The repository adapter expands each persisted shared template into one in-memory
`TemplateReference` per supported level. Every reference carries the same canonical slug and the
same shared days/slots. This keeps the established deterministic selector and personalization
pipeline unchanged while replacing database duplication with an adapter-level compatibility view.

The selector still requires exact day count and exact user-level compatibility. It then applies all
existing safety, equipment, duration, recovery, priority, substitution, and validation behavior.
Admin-created templates are loaded by the same active-template query and adapter.

## Verification

- Migration: 41 managed rows become 17 canonical rows with the expected level unions.
- Seed: exactly 17 managed templates, canonical slugs, no placeholders, idempotent synchronization.
- API: membership filtering, same ID across level filters, multi-level create/update, delete, and
  validation.
- Engine: shared templates expand to eligible references and Admin-created templates participate in
  normal selection.
- Frontend: one card per template, supported-level controls, shared content editing, delete flow.
- Regression: focused backend/frontend suites, backend Ruff and mypy, frontend lint and build.

