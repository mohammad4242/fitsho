# Nutrition Tracking Entry Hub Design

## Goal

Make the web Nutrition Tracking page a food-logging-first reference while preserving every existing nutrition API, calculation, photo-analysis, editing, deletion, adherence, and persistence behavior.

## Scope

Only these web files are implementation targets:

- `frontend/src/features/nutrition/NutritionTrackingPage.tsx`
- `frontend/src/features/nutrition/nutritionEstimate.css`
- `frontend/src/features/nutrition/NutritionWorkflowPages.test.tsx`

Backend, API/types files, mobile, Android, and nutrition-domain behavior remain unchanged.

## Architecture

The page owns one controlled selection state:

```ts
type EntryMode = "manual" | "photo" | null;
const [entryMode, setEntryMode] = useState<EntryMode>(freeMealId ? "photo" : null);
```

Selecting the active method clears it; selecting the other method switches directly to that method. The existing manual and photo workflow JSX stays on this page and is rendered only for its selected mode.

## Page order

```text
header
entry hub
selected entry panel, if any
single workflow error/status message
daily logged-calorie summary
today's entries
adherence accordion
final daily check-in
bottom spacing
```

The four check-in buttons remain the final content section. Loading and workflow feedback are placed before the summary so they cannot appear after the check-in.

## Entry hub

The hub has a non-interactive centered root labeled `ثبت تغذیه` / `Nutrition tracking`, followed by equal semantic buttons for `ثبت دستی` / `Log manually` and `عکس وعده` / `Food photo`. Existing `AppIcon` icons (`catalogue` and `camera`) provide the method visuals. CSS pseudo-elements draw the subtle branch from the root to the two choices using Fitsho line tokens. Buttons expose `aria-expanded`, `aria-controls`, `type="button"`, selected styling, focus styling, and reduced-motion-safe transitions.

## Workflow preservation

Manual catalogue, quick approximation, recent-food shortcuts, photo consent/upload/preview/estimate/correction/confirmation, free-meal return navigation, source filtering, entry editing/deletion, planned-meal actions, adherence dates/history, and check-in values/functions are moved or wrapped only. Payloads and API calls remain byte-for-byte behaviorally equivalent.

## Responsive and accessibility behavior

The hub choices remain a readable two-column branch at narrow browser widths. Expanded panels use the full available width. Logical CSS properties, the page's `dir`, minimum interactive sizing, visible `:focus-visible`, labels, and `prefers-reduced-motion` are retained or added without global selectors.

## Verification

Focused tests cover initial collapse, manual/photo selection, mutual exclusion, toggling, unchanged catalogue payload, photo workflow, free-meal deep link, DOM ordering, final check-in placement, and the existing adherence accordion. Verification also includes the full frontend tests, lint, build, and visual inspection at approximately 390px, 768px, and desktop width.
