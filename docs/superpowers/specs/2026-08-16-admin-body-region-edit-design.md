# Admin body-region editing

## Scope

Allow admins to change an exercise body region during editing, including exercises marked `needs_review`.

## Design

- Keep body-region membership validation for the primary muscle.
- Enable the existing body-region selector in the edit form.
- When the body region changes, clear the primary muscle and muscle focus so the next selections are valid for the new region.
- Reuse the existing API payload and validation; no new endpoint or data model is needed.

## Verification

- Add an admin edit regression test that changes body region and then selects a valid primary muscle.
- Run the focused admin tests, backend admin API tests, frontend lint, and frontend build.
