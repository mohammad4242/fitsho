# Lower Back Exercise Taxonomy Design

## Goal

Expose the existing `lower_back` muscle group in the exercise library under the
upper-body category `پشت و زیر بغل`, with the Persian label `پایین پشت`.

## Scope

- Move `lower_back` from the API's core category list to the upper-body list.
- Keep the stable value `lower_back` for database rows, filters, API payloads,
  and frontend types.
- Keep its existing focus taxonomy (`lumbar_erectors` and `thoracic_mobility`).
- Preserve existing exercises and media. The active database already stores
  the existing lower-back exercises as `body_region=upper_body`.
- Update backend taxonomy/router tests and frontend category fixtures/tests.

## Acceptance criteria

- `/api/v1/exercise-categories` returns `lower_back` under `upper_body` with
  `name_fa=پایین پشت` and does not return it under `core`.
- The library can filter `body_region=upper_body&primary_muscle=lower_back`.
- Existing lower-back focus options remain available.
- No exercise or media rows are deleted or rewritten.
