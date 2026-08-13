# Exercise Admin Full Edit Design

## Goal

Give administrators full editing access to exercise content through the existing protected editor, while keeping the Exercise Library unchanged for normal users.

## Design

- Extract the identity, targeting, programming, guidance, media metadata, and active-state inputs from the create page into one shared full exercise form component.
- Use the shared component from both the create and edit pages.
- Keep the existing admin-only API routes, request schemas, validation, and permission checks.
- Preserve the existing library return URL after saving an edit.
- Render the exercise-card Edit action with white text in all interaction states.

## Validation and errors

- Both pages use `validateAdminExercise` before sending a request.
- The edit page maps API validation and duplicate-slug failures to the same field and alert behavior as the create page.
- Existing media remains visible on edit; replacing the primary media remains optional.

## Tests

- Frontend tests prove the edit form loads and changes names, equipment, difficulty, instructions, and safety notes.
- Styling tests prove the Edit action is white.
- Existing backend tests confirm the protected API already persists all exercise fields and remains admin-only.

