# Mobile nutrition weekly-plan web parity

## Goal

Align the native Android weekly nutrition-plan area with the current web
`WeeklyNutritionPlan` hierarchy at phone widths while preserving native API,
offline, PDF, history, and meal-editing behavior.

## Scope

Change only the native nutrition plan presentation and its focused tests:

- `mobile/nutrition/NutritionPlanSection.tsx`
- `mobile/nutrition/NutritionShoppingList.tsx`
- `mobile/nutrition/nutritionPlanApi.ts` only for the existing partial-regenerate
  endpoint needed by the web-equivalent day action
- `mobile/nutrition/NutritionPlanSection.rntl.test.tsx`
- `mobile/nutrition/nutritionPlanPresentation.test.ts`

The web UI, backend, database, shared response schema, global
`DisclosureCard`, RTL helpers, tokens, and unrelated mobile screens remain
unchanged.

## Component structure

`NutritionPlanSection` remains responsible for the existing active/latest,
bundle, selected-history, feedback, connectivity, generation, and history
queries. It passes the already-loaded history state into `NutritionPlanCard` so
history is rendered in the first disclosure without another request.

When a bundle requires a choice, the order is:

1. bundle comparison/choice
2. selected weekly plan
3. rebuild/new-plan action and its result state

`NutritionPlanCard` becomes a presentation stack rather than an enclosing
status/stat card:

1. weekly eyebrow and role-aware title
2. local physician-review card or historical/reference notice
3. three wrapping metadata chips
4. physician notes and plan warnings
5. closed `برنامه تغذیه` disclosure
6. closed `هدف در برابر مقدار برنامه` disclosure
7. closed `لیست خرید دقیق` disclosure
8. web-style PDF CTA

The first disclosure contains the budget ledger, ordered week-day selector,
selected-day summary and meals, and revision history. The second contains
`Object.values(currentPlan.nutrients)` with localized name, planned value/unit,
status, and the web's reference/confidence/difference details. The shopping
component owns the third disclosure and remains absent for historical plans,
matching the web reference behavior.

## Data and behavior

- Lifecycle labels, budget labels, nutrient labels, nutrient status labels,
  date formatting, and money formatting remain derived from the existing plan
  response and helpers.
- The physician card has amber pending and green approved visual states, with
  approval date when available. Historical plans retain a non-active notice.
- Metadata reads `revision`, `lifecycle_status`, `price_snapshot.references`,
  and `input_snapshot.main_meals_per_day` / `snacks_per_day`.
- Ledger values remain weekly cost, weekly budget, and budget status. At native
  phone widths the three rows are stacked.
- The day selector keeps Saturday through Friday array order and uses an
  explicit scroll/layout arrangement with RTL text so native RTL does not
  reverse the logical web order.
- Existing meal thumbnails, prepared-recipe summaries, lock, feedback,
  removal, meal replacement, food replacement, dialogs/sheets, errors, and
  history selection remain wired to the existing APIs.
- The existing backend partial-regenerate endpoint is exposed through the
  native plan API and used only for the selected day's unlocked-meal action.
- PDF storage remains `ExpoNutritionPlanPdfStore`: one tappable CTA downloads
  when needed, opens a stored file when present, and preserves loading,
  offline, and error states.

## Visual translation

Local styles reproduce the web's dark petrol surfaces, aqua accents, subtle
lines, amber review state, green approval state, rounded disclosure headers,
compact pills, stacked phone ledger rows, narrow nutrient cards, and large
turquoise PDF CTA. Layout uses flexible widths, wrapping, shrinkable text, and
only the day selector may scroll horizontally.

All Persian text uses RTL direction, automatic/native paragraph alignment, and
Persian writing direction. Disclosure titles stay on the logical right and
chevrons on the logical left; physician and PDF icons stay on the right.

## Test plan

The focused native tests will first assert the new hierarchy and collapsed
states, then interactionally open each disclosure and verify its content.
They will also cover pending/approved physician states, metadata, history
selection, RTL styles, PDF loading/action/error behavior, offline/loading/error
states, and the existing meal editing controls. Source-contract assertions
will reject the removed status-first hierarchy and old shopping/PDF copy.

Verification gates, in order:

1. focused presentation Vitest test
2. focused native RNTL test
3. mobile TypeScript check
4. broader relevant mobile nutrition/native tests
5. `git diff --check` and a manual phone-width review at 360, 390, and 412 dp

Automated checks and physical-device visual evidence will be reported
separately.
