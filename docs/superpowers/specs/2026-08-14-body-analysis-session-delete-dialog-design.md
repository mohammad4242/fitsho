# Body Analysis Session Delete Dialog

## Goal

Let users delete incomplete uploads and submitted analyses from the Body Analysis history while
replacing the browser confirmation box with a clear, polished, accessible confirmation dialog.

## Session Cards

Every incomplete-upload card and submitted-analysis card has a destructive **Delete** action.
Analysis cards keep **View analysis** as their primary action. Incomplete cards keep **Continue
upload** as their primary action.

The existing owner-scoped `DELETE /api/v1/body-photo-sessions/{session_id}` endpoint handles both
categories. A successful deletion removes the session card from the current list without a page
reload.

## Confirmation Dialog

The page renders one custom modal dialog for the selected session. The dialog includes:

- a restrained red warning rail and trash icon;
- a category-specific title for deleting an analysis or incomplete upload;
- plain Persian-first copy explaining that stored photos and the session will be removed;
- the session date and current status for identification;
- a quiet **Cancel** action and a clearly destructive **Delete** action.

The backdrop dims and blurs the scanner page. Desktop uses a centered panel. At mobile width the
same component becomes a bottom sheet with safe-area spacing. Motion is limited to one short
entrance transition and is disabled by `prefers-reduced-motion`.

The dialog uses the existing Fitsho surface, line, aqua, muted, and danger tokens. It does not add
new fonts or a separate visual system.

## Interaction and Accessibility

- Opening delete stores the selected session and moves confirmation into a `role="dialog"` region
  with `aria-modal="true"` and labelled title/description.
- Cancel, backdrop click, and Escape close the dialog while no request is active.
- Confirm disables both dismissal and repeated deletion until the request finishes.
- Success closes the dialog and removes the card.
- Failure keeps the dialog open and shows a specific inline error; retry remains available.
- Focus returns to the delete button that opened the dialog after cancel or failure dismissal.

## Tests

Frontend tests cover delete controls for both categories, category-specific dialog copy, cancel,
successful deletion, failed deletion with retry, and Escape dismissal. Existing grouping, resume,
latest-analysis, lint, build, and full frontend tests must remain green.
