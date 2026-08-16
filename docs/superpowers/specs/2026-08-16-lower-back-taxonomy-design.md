# Lower Back Exercise Taxonomy Design

## Goal

Expose `lower_back` in the exercise library as a focus under the upper-body
category `پشت و زیر بغل`, with the Persian label `پایین پشت`.

## Scope

- Add `lower_back` to the `back` focus categories and remove it as a standalone
  catalog category.
- Keep the stable value `lower_back` as the focus value in filters, API
  payloads, and frontend types.
- Migrate existing primary lower-back exercises to `primary_muscle=back` and
  `muscle_focus=lower_back`.
- Preserve existing exercises and media. The active database already stores
  the existing lower-back exercises as `body_region=upper_body`.
- Update backend taxonomy/router tests and frontend category fixtures/tests.

## Acceptance criteria

- `/api/v1/exercise-categories` returns `lower_back` in
  `muscle_focuses.back` with `name_fa=پایین پشت`.
- The library can filter
  `body_region=upper_body&primary_muscle=back&muscle_focus=lower_back`.
- Existing lower-back exercises remain available through that filter.
- No exercise or media rows are deleted or rewritten.
