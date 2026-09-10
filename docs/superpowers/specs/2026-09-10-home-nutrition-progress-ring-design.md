# Home Nutrition Progress Ring Design

## Goal

Make the nutrition card on the web Dashboard and native Fitician Home show the
member's daily calorie target relative to estimated daily expenditure (TDEE).
The ring starts visually at 0 when Home is entered, fills to the real percentage,
and uses the requested green/blue/red progress tones.

## Scope

- Change only the Home nutrition ring presentation and its focused tests.
- Reuse the existing weekly-plan, estimate, and daily-tracking requests.
- Do not change nutrition calculations, target generation, API contracts, storage,
  or tracking behavior.
- Preserve unrelated worktree changes.

## User-facing behavior

The canonical metric is:

```text
daily calorie percentage = daily target energy_kcal / estimated daily expenditure energy_kcal * 100
```

The target already reflects the member's selected goal. The same formula therefore
works for both weight-gain and weight-loss members, without using logged food:

- A gain member with a 3,000 kcal target and a 2,400 kcal TDEE has a 125% ratio,
  a visually capped 100% red ring, and a message showing the target's 600 kcal
  difference above estimated expenditure.
- A loss member with an 1,800 kcal target and a 2,400 kcal TDEE sees 75%.
- Logged calories do not change the ring or its percentage. The target and TDEE
  remain visible as the two calorie metrics.

Tone boundaries are deterministic:

- `0 <= percentage < 60`: green (`success` token).
- `60 <= percentage < 90`: blue (`blue` token).
- `percentage >= 90`: red (`danger`/`coral` token).

The colors describe the fill level, not whether a gain or loss goal is medically
successful. The ring is labeled as daily calorie progress so this interpretation
is explicit.

When no valid target or TDEE is available, the existing empty/loading behavior
remains unchanged and the ring resolves to 0 when a target is present.

## Animation

- Web Dashboard: add an opt-in mount animation to the shared `ProgressRing`; only
  the Dashboard Home nutrition instance enables it. The arc starts at 0 and fills
  to the computed visual percentage over the existing 900 ms native duration.
  Other `ProgressRing` consumers remain static.
- Native Home: retain the existing `MetricRing animateOnFocus` path and apply the
  same 900 ms duration. The ring resets when the Home screen receives focus.
- A data refresh while Home remains open updates the ring to the new value without
  changing API or query behavior.
- Web reduced-motion preferences disable the visual transition while retaining the
  final value and accessibility state.

## Architecture and data flow

`@fitician/core` owns the platform-neutral progress-tone contract so web and native
cannot drift at the 60% and 90% boundaries. It returns a semantic tone only; each
client maps that tone to its existing design tokens.

The web Dashboard passes the target as the ring value, TDEE as its maximum, the
selected tone, and the mount-animation flag to `ProgressRing`. The native
`homeModel` derives the target and TDEE from the existing plan and estimate
responses; tracking remains available for macro/status details but cannot affect
the calorie progress. `NutritionSummaryCard` maps the summary progress to the
shared tone and passes the matching native color to `MetricRing`.

Visual percentages are clamped to 0–100. Accessibility exposes the target as the
real value and TDEE as the maximum, while the above-expenditure message makes a
capped gain-target state understandable.

## Planned files

- Create `packages/fitician-core/src/nutrition-progress.ts` and its unit test.
- Modify `packages/fitician-core/src/index.ts` to export the progress contract.
- Modify `frontend/src/shared/ProgressRing.tsx` and
  `frontend/src/shared/ProgressRing.test.tsx` for opt-in mount animation and
  configurable ring color.
- Modify `frontend/src/pages/DashboardPage.tsx`,
  `frontend/src/pages/dashboard.css`, and `frontend/src/pages/DashboardPage.test.tsx`
  for the Home tone, animation, and over-target copy.
- Modify `mobile/home/NutritionSummaryCard.tsx`, `mobile/home/homeModel.ts`,
  `mobile/home/homeCards.rntl.test.tsx`, and the relevant Home/model tests for the
  native tone and over-target state.
- Modify `mobile/ui/components/MetricRing.tsx` and its focused test only if needed
  to prove the Home color reaches the rendered progress circle without changing the
  default shared-ring behavior.

## Acceptance criteria

1. Both Home nutrition rings use the same target-to-TDEE percentage for gain and
   loss targets, independent of logged food.
2. Each ring starts from 0 on Home entry and fills to the final visual percentage.
3. Exact tone boundaries are covered by tests: 59.9% green, 60% blue, 89.9% blue,
   and 90% red.
4. A target above TDEE caps the ring at 100%, stays red, and exposes a localized
   above-expenditure message while showing the target and TDEE values.
5. Existing non-Home rings and nutrition API/storage/calculation behavior are
   unchanged.
6. Focused core, web, and native tests pass, followed by web/mobile typechecks and
   lint/build checks that are available in the current workspace.
