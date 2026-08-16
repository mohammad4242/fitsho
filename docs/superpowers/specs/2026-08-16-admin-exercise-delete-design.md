# Admin exercise deletion design

## Goal

Allow administrators to delete an exercise from the exercise library from the existing card action area, directly below the edit action.

## Behavior

- Add `DELETE /api/v1/admin/exercises/{exercise_id}`.
- Require administrator authentication and the same trusted-origin protection as other state-changing exercise admin routes.
- Delete the exercise and its cascading catalogue relationships and media-asset rows.
- Delete the exercise's locally managed media files after the database deletion succeeds.
- If a workout plan still references the exercise, keep the record and return HTTP 409 with a user-safe message.
- Return 204 on success and 404 when the exercise does not exist.
- In the admin catalog, show a delete action under edit, ask for confirmation, remove the card after success, and show the API error without losing the current filters.

## Testing

- Backend API tests cover auth/admin/origin guards, successful deletion, 404, and 409 for a referenced exercise.
- Frontend tests cover the delete action, confirmation, successful removal, and an error response.
- Run focused tests first, then backend lint/typecheck and frontend test/lint/build.

## Scope

No changes to workout-plan history, public catalog behavior, soft-delete status, or unrelated admin libraries.
