# Exercise Content Classification Design

## Goal

Classify the existing `exercises` catalogue records as either normal exercises
or educational guides without creating a second catalogue or replacing any
existing record or media.

## Data model and migration

Add the existing-module `StrEnum` pattern as `ExerciseContentType` with:

- `exercise`
- `guide`

Add a non-null `content_type` column to `exercises` using the current
non-native SQLAlchemy enum/check-constraint pattern. Its Python and database
defaults are `exercise`. The migration explicitly backfills existing rows to
`exercise`, so IDs, slugs, titles, anatomy, media rows, relationships, and
metadata remain unchanged. Add an index only if it supports the catalogue
query pattern used by the existing schema.

## Backend contracts

Extend the shared exercise summary/detail schemas and admin schemas with
`content_type`. Add the field to public and admin filters. Public catalogue
queries default to `exercise` to preserve the current library behavior; guide
requests explicitly filter for `guide`. Admin writes accept both values and
update the existing row in place. Changing type does not upload, replace, or
delete media.

## Admin flow

Reuse the existing exercise edit form and multipart PATCH contract. Add a
two-state control labelled `حرکت | راهنما`, initialize it from the persisted
value, and include `content_type` in the existing payload. The same control is
available on create because the form contract is shared, while the required
classification behavior is verified for edit in both directions.

## Member library flow

At the selected-muscle stage, place a native-looking segmented switch below
the existing target-muscle heading/description and above its focus cards. The
URL stores the selected content type and defaults to `exercise`.

- `exercise`: keep the current focus cards, filters, result cards, and links;
  requests include `content_type=exercise`.
- `guide`: hide the focus-card layer and show a simple result list for the
  selected primary muscle with `content_type=guide`; guides are never mixed
  into exercise results.

The existing card/detail/media components are reused, with only the visible
copy adjusted where it says “exercise” so guide content remains understandable.
The control follows current RTL, typography, spacing, colors, and responsive
rules.

## Workout safety

Audit all backend catalogue-to-workout paths. Candidate selection, automatic
exercise selection, generated-plan eligibility, and training-template writes
must require `content_type=exercise` in domain queries/validation. Frontend
filtering is not used as the safety boundary. Existing guide conversion does
not delete the row or its media; it simply makes the row ineligible for future
workout selection.

## Verification

Add focused tests for:

- migration/model defaults and allowed values;
- public and admin filtering and response fields;
- in-place admin type changes with media and relationships preserved;
- workout candidate/template safety against guide rows;
- member switch behavior, URL state, separate guide results, and preserved
  exercise focus behavior;
- admin form loading and saving both content types.

Run focused backend/frontend tests first, then the relevant lint/type/build
checks and the full suites where practical. Preserve all unrelated worktree
changes and stage only task files.
