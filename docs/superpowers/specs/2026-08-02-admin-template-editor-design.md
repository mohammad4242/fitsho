# Admin Training Template Editor Design

## Goal

Allow an administrator to create and edit the Fitsho training-program reference library without changing the deterministic engine or the global exercise catalog accidentally.

## User flow

The existing two-to-six-day library remains a read-only overview. Each template has an **Edit program** action. The editor is a dedicated admin route with a full-form save action. The last card in every day-count view has an **Add new program** action; it passes the selected day count and, when selected, training level into a new editor.

The editor can change program metadata, add/remove/reorder days and slots, change a slot's display title, and choose the linked exercise through an in-page search of the existing admin exercise library. Selecting an exercise fills safe defaults from its metadata; the administrator can then set programming fields. The per-slot display title is deliberately separate from the catalog exercise name, so changing a program does not silently rename that exercise everywhere else.

## Backend contract

Admin-only endpoints provide a single write payload for a complete template and its ordered days and slots:

- `POST /api/v1/admin/training-program-templates`
- `PUT /api/v1/admin/training-program-templates/{template_id}`

The service validates template day count, unique/ordered day and slot data, ranges already enforced by database constraints, and that every linked exercise exists and is active. It replaces child days/slots in one database transaction, so a partial edit can never reach the engine. Slugs are generated from the program name only when creating a template; editing preserves the established stable slug.

## Safety and scope

The editor edits only training-template records. It does not alter the selected exercise catalog record, its media, or its safety metadata. Existing catalogue placeholders remain selectable and visibly flagged for review; their non-programmable status remains enforced by the engine.

## Testing

Backend API tests cover create, full update, deleted slot removal, exercise-link validation, and authorization. Frontend tests cover opening the editor, search-and-select, removing a movement, and creating a program with the current day/level defaults.
