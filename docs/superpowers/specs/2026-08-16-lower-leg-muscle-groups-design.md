# Lower-leg exercise-library muscle groups

## Goal

Add two independent lower-body primary-muscle groups to the exercise library:

- `abductors` — بیرون پا / Abductors
- `legs` — کل پا / Legs

They must be selectable and filterable in the member library and admin exercise
editor, and must be accepted by the backend taxonomy and database constraints.

## Design

The existing `MuscleGroup` enum remains the single source of truth for the
stable values. The two values are added to the lower-body region. Both groups
have no focus subcategories, so their exercises store a null `muscle_focus`,
matching the existing quadriceps/adductors behavior.

The public categories endpoint continues to return the ordered lower-body
category list. The existing exercise and admin filters accept the new enum
values automatically through their shared schemas and query paths. The admin
form's local region map and both language dictionaries are updated so the UI
can create, edit, display, and link exercises using these values.

## Database migration

The database stores controlled values through PostgreSQL check constraints. A
new Alembic revision after the current head drops and recreates the primary and
secondary muscle value constraints with `abductors` and `legs` included. It
does not rewrite exercise rows, media rows, or videos. Downgrade restores the
previous constraint values.

## Data flow

1. Admin/member UI sends `body_region=lower_body` and one of the new primary
   muscle values.
2. Pydantic validates the enum and null focus compatibility.
3. Service filtering applies the selected primary muscle to `exercises`.
4. The database accepts the value under the migrated check constraints.
5. The categories response supplies bilingual labels to the member library.

## Verification

- Backend taxonomy/API tests cover ordering, membership, and focus behavior.
- Database tests cover storing both values and rejecting invalid controlled
  values after migration.
- Frontend tests cover type/category data, admin validation, and selecting the
  two lower-body buttons.
- Run focused backend/frontend tests, then backend lint/typecheck and frontend
  lint/build. Verify Alembic upgrade/current against the test database.
