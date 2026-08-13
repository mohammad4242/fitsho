# Nutrition Program Catalogue Menu Link Design

## Goal

Expose the existing Nutrition Program Catalogue in the desktop account menu for administrators.

## Design

- Add one link labeled with `header.adminNutritionPrograms` to the existing Administration group.
- Route the link to `/admin/nutrition-programs`.
- Close the account menu when the link is selected, matching adjacent admin links.
- Keep roles, routes, translations, and page behavior unchanged.

## Verification

- An authenticated-header test opens the account menu and verifies the link label and destination.
- The full frontend test suite, lint, and production build pass.
