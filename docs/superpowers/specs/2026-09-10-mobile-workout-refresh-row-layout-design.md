# Mobile Workout Refresh and RTL Row Layout Design

## Goal

Make the native generated-workout page match the web for two behaviors: the update action
remains usable when another generated version is awaiting coach review, and exercise media
appears on the right with exercise information on the left in the Persian RTL layout.

## Scope

- Modify only the native workout plan screen and its focused native tests.
- Keep Backend, API contracts, query keys, generation persistence, coach review, history,
  replacement, navigation, and media rendering unchanged.
- Preserve the existing historical-plan rule: historical plans do not expose the update action.
- Preserve the existing pending-only display behavior used by the web page.

## Root Causes

1. `WorkoutPlansScreen` passes `canGenerate={pendingPlanId === null && selectedPlanId === null}`
   to `PlanView`. A pending review version therefore disables the update button even while the
   active plan is displayed. The web page only disables this action while generation is running
   or during cooldown.
2. `Screen` supplies `direction: "rtl"`. The exercise row and day summary place media first but
   use `flexDirection: "row-reverse"`, which reverses the already RTL visual order and puts
   media on the left. The web markup places media first in the RTL row, so native rows should use
   `flexDirection: "row"`.

## Design

### Update behavior

Remove the mobile-only `canGenerate` gate from `PlanView`. The update button is disabled only by
the existing `generationPending` state. `onGenerate` remains absent for historical plans and is
still present only for the active-plan view. The existing mutation and its active/history refetch
remain the single data path after generation.

### RTL layout

Change the `daySummary` and `exerciseRow` containers to `flexDirection: "row"`. Their existing
child order remains media, number/copy, and controls as appropriate. Because the parent screen is
RTL, media renders at the right edge and the copy occupies the left side. Internal Persian
label/value groups retain their current directional styles.

### Error and state behavior

No new fallback or retry behavior is introduced. Existing generation error notices, cooldown and
concurrency classification, pending review rendering, offline states, and refetch behavior remain
unchanged.

## Verification

- Add a native regression showing that an active plan's update button is enabled and starts the
  existing generation mutation when history contains a pending-review version.
- Add source-contract assertions for `row` direction on day summaries and exercise rows.
- Run focused native workout tests, mobile typecheck, mobile lint for the touched files, and the
  complete mobile Vitest/native Jest suites where the local environment supports them.
- Run `git diff --check`; inspect the final scoped diff before commit and push.
