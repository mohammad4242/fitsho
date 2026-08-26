# Admin Training Structure Family Filtering

## Scope

Improve the admin Training Program Library and add dedicated admin management for
database-backed TrainingProgramStructure records. Preserve existing training
program contents, level architecture, focus tags, program prescriptions, exercise
logic, and unrelated working-tree changes.

## Current implementation

The repository already has `TrainingProgramStructure` and
`TrainingProgramStructureDay` models, a migration that seeds the initial structures,
admin CRUD endpoints, and a library filter by `days_per_week` and `structure_id`.
The current structure model has no family or split subtype, the frontend has no
Structure CRUD screens, and the library renders all day-matched structures as one
flat control row.

The live database contains 16 active structures linked to 17 templates. The two
templates `t09-5-day-ppl-upper-lower` and `t11-5-day-ppl-upper-lower-priority`
intentionally share one structure. The remaining specialization structures have
different weekly day sequences, so no additional consolidation is safe from the
current audit.

## Data model and classification

Add two nullable string-backed enums to `TrainingProgramStructure`:

- `family`: `upper_lower` or `split`
- `split_type`: `ppl` or `body_part`

The valid combinations are:

- 2- and 3-day structures: both fields are null.
- 4- to 6-day Upper/Lower structures: `family=upper_lower` and `split_type` null.
- 4- to 6-day Split structures: `family=split` and a non-null split type.

The migration backfills existing rows from their actual day topology:

- 4-day Upper/Lower rows use `upper_lower`.
- PPL rows use `split` and `ppl`.
- Body-part or movement-group rows use `split` and `body_part`.

The migration does not delete or rewrite templates, template days, slots, focus
tags, or program content. It preserves the shared `t09`/`t11` relationship and
does not merge structures with genuinely different ordered day sequences.

Structure create/update validation applies the same conditional rules. A referenced
structure may have its names, descriptions, family, split type, or ordered day
labels edited, but changing `days_per_week` is rejected while templates reference
it. This prevents incompatible existing links without moving or rewriting programs.

## Backend API

Extend the structure response and write schemas with `family` and `split_type`.
The structure list service and endpoint accept an optional `family` query parameter
while retaining `days_per_week` and `include_inactive`.

Extend the admin training-template list endpoint with an optional `family` query
parameter. When present, the service joins `TrainingProgramStructure` and returns
active templates whose linked structure belongs to that family. The existing
`structure_id` filter remains the more precise filter. Without either filter, the
existing All Structures behavior remains unchanged.

Existing admin Structure endpoints remain the source of truth:

- list and detail
- create
- update
- activate
- deactivate
- delete protection for referenced structures

## Dedicated admin routes and screens

Add routes protected by the existing `AdminRoute`:

- `/admin/training-program-structures`
- `/admin/training-program-structures/new`
- `/admin/training-program-structures/:structureId/edit`

The Structure Library lists database records with day count, family/type, ordered
day sequence, active state, edit action, and activate/deactivate action. It uses
the current admin loading, error, status, RTL, and mobile patterns.

The Structure Editor supports bilingual names, slug, optional bilingual
descriptions, `days_per_week`, conditional family/type selection, and an ordered
repeater with one day definition per selected day. Family is not shown for 2- or
3-day structures. For 4- to 6-day structures it is required; Split additionally
requires PPL or Body-Part. Saving uses the existing CRUD endpoints and returns to
the edit screen or library according to current admin editor conventions.

## Training Program Library behavior

The page keeps four dependent state values: selected day count, selected family,
selected structure, and selected level.

- 2 and 3 days show All Structures and database-backed structures directly; no
  family control is rendered.
- 4, 5, and 6 days show All Structures plus exactly two category controls:
  Upper / Lower and Split.
- Selecting a family clears the selected structure, filters templates by that
  family, and reveals only structures for the selected day count and family.
- Selecting a structure filters to that structure.
- Selecting All Structures clears family and structure and removes both constraints.
- Changing day count clears family and structure, loads the new day options, and
  keeps the selected level.
- Changing family clears any incompatible structure.
- Level remains the final filter and retains All Levels, First Month, Beginner,
  Intermediate, and Advanced.

PPL is represented by `family=split` and `split_type=ppl`; it is never a third
top-level family. Body-Part structures use `family=split` and
`split_type=body_part`. Focus tags remain program metadata and do not create
structure categories.

Family/category disclosure uses the existing accessible accordion conventions:
localized labels, `aria-expanded`, `aria-controls`, visible selected state, and
collapsed rendering so both families do not create a tall flat wall of controls.
Structure names wrap inside their parent, with narrow-screen RTL and keyboard
focus support preserved.

## Error handling

List and library requests retain loading, retry, error, and empty states. Stale
requests are ignored when dependent filters change. Invalid conditional family
payloads and referenced day-count changes return localized save errors. A family
with no structures shows a localized empty state without rendering unrelated
structures.

## Verification

Backend tests cover:

- model/schema conditional classification rules
- structure create, update, activate, deactivate, and delete protection
- family and day filtering for structures
- family, structure, level, and All Structures template filtering
- rejection of day-count changes for referenced structures
- preservation of existing template links and content

Frontend tests cover:

- direct 2- and 3-day structure lists without a family control
- Upper / Lower and Split categories for 4-, 5-, and 6-day selections
- family-specific structures and PPL/body-part placement
- All Structures behavior
- day and family dependent-state resets
- level filtering and new database-backed structures
- accessible disclosure and selected states

Run the focused backend and frontend tests, frontend typecheck, frontend build,
lint, and `git diff --check`. Manually inspect the library and Structure Editor on
a narrow RTL viewport for overflow, clipping, wrapping, and expansion behavior.
