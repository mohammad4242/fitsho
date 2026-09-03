# Collapsible Admin Meal Catalogue

## Goal

Keep the admin nutrition meal catalogue compact by showing each meal's image and
name first, and revealing its ingredients and actions only when the meal is opened.

## Scope

- Change only the admin meal catalogue presentation.
- Keep the existing category tabs, image upload dialog, edit links, API calls, and
  `AdminMealCatalogueItem` contract.
- Do not change backend, routes, or catalogue data.

## Design

Each meal card will use the native HTML `<details>` and `<summary>` disclosure
pattern. The summary will contain the localized thumbnail, meal name, code/category,
and verification status. The details section will contain the current ingredient
list, edit/image actions, and reference note.

Cards will not include the `open` attribute, so every card starts collapsed. The
native disclosure behavior will handle click and keyboard interaction without a new
React state or persistence model. Changing category will continue to load the same
API response and render its cards collapsed.

## Accessibility and styling

- Preserve localized accessible image and action labels.
- Use the native disclosure control for keyboard and screen-reader semantics.
- Style the summary as the card header, hide the browser marker only if needed for
  the existing visual language, and retain a clear open/closed affordance.
- Keep the current responsive ingredient layout and image dialog behavior.

## Verification

Update `AdminMealCataloguePage.test.tsx` to verify that:

1. The meal name, image, category metadata, and status are visible initially.
2. Ingredient details and card actions are not visible before opening.
3. Clicking the meal summary reveals the ingredients and existing actions.
4. Existing category switching and image replacement behavior remain intact.

Run the focused frontend test, frontend lint, frontend build, and `git diff --check`.
