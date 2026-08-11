# Authenticated Home Redesign

## Scope

Redesign only the authenticated dashboard composition. Preserve authentication, product-mode gates, data requests, route targets, i18n, workout generation, and the shared application shell.

## Composition

The page uses a compact single-column mobile composition: profile greeting, today workout hero, daily nutrition card, then two equal quick actions. Wider screens retain the same priority in a centered two-column layout, with workout and nutrition as the dominant cards and quick actions as a smaller paired row.

## Visual system

- Canvas: existing near-black Fitsho canvas.
- Surfaces: existing dark petrol tokens with low-contrast borders.
- Accent: existing Aqua token for progress, active states, and scan details.
- Typography: existing Fitsho/Sora type system; data remains visually distinct with tabular numerals.
- Signature: subtle scan brackets and a single scan line on the body and food shortcuts.

## Functional boundaries

- Workout content comes only from the active workout plan and its first exercise media.
- Nutrition values come only from the current weekly plan, scientific estimate, and daily tracking summary.
- Body analysis routes to the existing `/body-progress` flow.
- Food analysis routes to `/nutrition-tracking` and remains visible only when nutrition capability is available.
- The existing bottom navigation remains unchanged; dashboard spacing accounts for its safe area.

## States

Existing loading, empty, ready, pending, and error behaviors stay intact. Missing values render existing empty-state labels or an em dash. No concept-image values are introduced.

## Responsive and accessibility

The design targets 360px, 390px, and 430px first. Quick actions remain side by side at supported mobile widths and stack only when necessary. Links retain visible focus, images have localized alternative text, the calorie ring remains an accessible progressbar, and logical CSS properties preserve RTL/LTR behavior.

## Verification

Cover real workout media, calorie progress and macros, product-mode fetching, all four Home destinations, RTL direction, overflow, mobile/tablet/desktop screenshots, frontend lint, relevant tests, and production build.
