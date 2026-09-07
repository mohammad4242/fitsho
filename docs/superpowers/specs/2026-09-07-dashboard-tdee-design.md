# Dashboard TDEE Summary Design

## Goal

Show the member's estimated total daily calorie expenditure beside today's calorie goal in the dashboard nutrition card.

## Scope

- Read `nutritionEstimate.targets.tdee.preferred`, falling back to `minimum` when the preferred value is unavailable.
- Render the value with the user-facing label `مصرف تقریبی روزانه` in Persian and `Estimated daily expenditure` in English.
- Keep the existing calorie progress ring, tracked-calorie behavior, macro strip, links, and nutrition API unchanged.
- Hide the secondary value when the estimate does not contain a usable TDEE value.
- Change only the dashboard component, its focused stylesheet, and its regression test.

## UI

The existing calorie area remains the primary content. A compact two-value row places `کالری هدف` and `مصرف تقریبی روزانه` side by side, with the existing progress ring retained at the end of the row. The secondary value uses the same number formatter and kcal unit as the existing target presentation. Responsive layout may stack the values only when the existing card width requires it.

## Data flow

`DashboardPage` already receives the current `NutritionEstimate`. It will derive a `tdeeTarget` from that response and render it without introducing a new request, type, endpoint, persistence field, or calculation.

## Verification

- Add a focused dashboard test proving a mocked TDEE value is visible beside the target.
- Add a focused dashboard test proving the secondary value is absent when TDEE is unavailable.
- Run the focused dashboard test, frontend lint, frontend build, and `git diff --check`.

