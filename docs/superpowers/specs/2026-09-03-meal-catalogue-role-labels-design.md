# Meal Catalogue Role Labels

## Goal

In the meal catalogue, ingredient functional roles must render as user-facing labels instead of unresolved i18next keys such as `mealCatalogue.roles.carbohydrate`.

## Scope

- Keep the backend role contract unchanged.
- Add the role keys used by the meal catalogue API to both Persian and English `mealCatalogue.roles` translations.
- Use concise labels: protein, carbohydrate, fat, fibre, and micronutrients.
- Preserve existing compatibility labels for legacy role values such as `primary_protein`.

## Implementation

Update the frontend meal-catalogue translation dictionaries. The existing page lookup remains the single rendering path; known API role values will resolve through the dictionaries, while unknown values will continue to use the raw role as a fallback.

## Verification

Add a focused `MealCataloguePage` regression test with API role values `protein`, `carbohydrate`, `fat`, `fibre`, and `micronutrient_source`. Assert that the Persian labels are visible and unresolved translation-key strings are absent. Run the focused Vitest test, then frontend lint and build if the focused check passes.
