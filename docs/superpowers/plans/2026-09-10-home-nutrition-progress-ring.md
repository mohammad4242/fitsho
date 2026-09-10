# Home Nutrition Progress Ring Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the web Dashboard and native Fitician Home nutrition rings animate from 0 to the target-to-TDEE percentage, use the shared green/blue/red tone contract, and explain gain targets above estimated expenditure.

**Architecture:** Put the target-to-TDEE ratio, visual clamp, and exact tone boundaries in @fitician/core. Keep platform colors and rendering in each client: web ProgressRing receives an opt-in animation/color, while native Home passes a mapped color to its existing focus-animated MetricRing. No API or nutrition calculation changes.

**Tech Stack:** TypeScript 6, React 19, Vite/Vitest, React Native/Expo SDK 57, Jest/RNTL, CSS conic gradients, react-native-svg, npm workspaces.

**Spec:** docs/superpowers/specs/2026-09-10-home-nutrition-progress-ring-design.md

## Global Constraints

- Use goal-specific daily target energy_kcal / estimated daily expenditure (TDEE) as the canonical ratio for both gain and loss members.
- Use < 60% green, 60% <= progress < 90% blue, and >= 90% red; cap only the visual ring at 100%.
- Show a localized above-expenditure message when the target exceeds TDEE; show the target and TDEE values.
- Animate only the Home nutrition ring; keep other web ProgressRing and native MetricRing consumers unchanged by default.
- Preserve all existing API, storage, tracking, calculation, and unrelated worktree changes.
- Before every commit, stage only the exact files named by that task.

### Task 1: Add the shared nutrition progress contract

**Files:**
- Create: packages/fitician-core/src/nutrition-progress.ts
- Create: packages/fitician-core/src/nutrition-progress.test.ts
- Modify: packages/fitician-core/src/index.ts

**Interfaces:**
- Produces nutritionTargetToExpenditureRatio(targetCalories, estimatedDailyExpenditureCalories): number, returning a non-negative unbounded ratio so gain targets remain detectable.
- Produces clampNutritionProgress(progress): number, returning a finite value in [0, 1] for visual rendering.
- Produces nutritionProgressTone(progress): NutritionProgressTone, where NutritionProgressTone is "green" | "blue" | "red".

- [ ] **Step 1: Write the failing contract tests**

Add tests that assert invalid inputs resolve safely, gain/loss targets use the same ratio, over-target ratios are preserved, and exact tone boundaries are stable:

~~~ts
import { describe, expect, it } from "vitest";

import {
  clampNutritionProgress,
  nutritionTargetToExpenditureRatio,
  nutritionProgressTone,
} from "./nutrition-progress";

describe("nutritionTargetToExpenditureRatio", () => {
  it("calculates the daily target against estimated expenditure", () => {
    expect(nutritionTargetToExpenditureRatio(2_400, 3_000)).toBeCloseTo(0.8);
    expect(nutritionTargetToExpenditureRatio(3_000, 2_400)).toBeCloseTo(1.25);
  });

  it("rejects missing, non-positive, and non-finite inputs", () => {
    expect(nutritionTargetToExpenditureRatio(null, 2_000)).toBe(0);
    expect(nutritionTargetToExpenditureRatio(2_000, null)).toBe(0);
    expect(nutritionTargetToExpenditureRatio(500, 0)).toBe(0);
    expect(nutritionTargetToExpenditureRatio(Number.NaN, 2_000)).toBe(0);
  });
});

describe("clampNutritionProgress", () => {
  it("clamps only the visual value", () => {
    expect(clampNutritionProgress(-0.2)).toBe(0);
    expect(clampNutritionProgress(0.6)).toBe(0.6);
    expect(clampNutritionProgress(1.111)).toBe(1);
    expect(clampNutritionProgress(Number.NaN)).toBe(0);
  });
});

describe("nutritionProgressTone", () => {
  it("uses green below 60, blue from 60 to below 90, and red from 90 onward", () => {
    expect(nutritionProgressTone(0.599)).toBe("green");
    expect(nutritionProgressTone(0.6)).toBe("blue");
    expect(nutritionProgressTone(0.899)).toBe("blue");
    expect(nutritionProgressTone(0.9)).toBe("red");
    expect(nutritionProgressTone(1.2)).toBe("red");
  });
});
~~~

- [ ] **Step 2: Run the contract tests and verify the expected failure**

Run from the repository root:

~~~bash
npm run test --workspace @fitician/core -- src/nutrition-progress.test.ts
~~~

Expected: FAIL because the new module and exports do not exist yet.

- [ ] **Step 3: Implement the smallest shared contract**

Implement the three functions with finite-number checks. nutritionTargetToExpenditureRatio returns 0 for a missing/non-positive target or TDEE, otherwise returns target / TDEE without an upper clamp. nutritionProgressTone compares the non-negative ratio to 0.6 and 0.9.

Export the runtime functions and NutritionProgressTone from packages/fitician-core/src/index.ts.

- [ ] **Step 4: Run the contract tests and build the core package**

~~~bash
npm run test --workspace @fitician/core -- src/nutrition-progress.test.ts
npm run build:core
~~~

Expected: all new core tests PASS and TypeScript emits the ignored packages/fitician-core/dist artifacts without errors.

- [ ] **Step 5: Commit the shared contract**

~~~bash
git add packages/fitician-core/src/nutrition-progress.ts packages/fitician-core/src/nutrition-progress.test.ts packages/fitician-core/src/index.ts
git commit -m "feat(core): add nutrition progress tone contract"
git push origin main
~~~

### Task 2: Add opt-in animated and colored web ring support

**Files:**
- Modify: frontend/src/shared/ProgressRing.tsx
- Modify: frontend/src/shared/ProgressRing.test.tsx
- Modify: frontend/src/pages/dashboard.css

**Interfaces:**
- Extends ProgressRing with color?: string and animateOnMount?: boolean.
- Default behavior remains static with the existing aqua color.
- An animated instance starts its CSS progress custom property at 0deg, schedules the final clamped angle on the next animation frame, and uses the existing 900 ms easing duration.

- [ ] **Step 1: Write failing web component tests**

Extend ProgressRing.test.tsx with tests for the new opt-in behavior:

~~~tsx
it("keeps the default ring static and aqua-compatible", () => {
  render(<ProgressRing value={1200} max={2400} />);

  const ring = screen.getByRole("progressbar");
  expect(ring).not.toHaveClass("fitsho-progress-ring--mount-animated");
  expect(ring.style.getPropertyValue("--ring-color")).toBe("var(--fitsho-aqua)");
});

it("starts an opted-in ring at zero before the first animation frame", () => {
  let frame: FrameRequestCallback | undefined;
  vi.stubGlobal("requestAnimationFrame", (callback: FrameRequestCallback) => {
    frame = callback;
    return 1;
  });
  vi.stubGlobal("cancelAnimationFrame", vi.fn());

  render(
    <ProgressRing
      animateOnMount
      color="var(--fitsho-blue)"
      value={1200}
      max={2400}
    />,
  );

  const ring = screen.getByRole("progressbar");
  expect(ring).toHaveClass("fitsho-progress-ring--mount-animated");
  expect(ring.style.getPropertyValue("--ring-progress")).toBe("0deg");
  expect(ring.style.getPropertyValue("--ring-color")).toBe("var(--fitsho-blue)");

  frame?.(0);
  expect(ring.style.getPropertyValue("--ring-progress")).toBe("180deg");

  vi.unstubAllGlobals();
});
~~~

- [ ] **Step 2: Run the focused web component tests and verify failure**

~~~bash
npm run test --workspace frontend -- src/shared/ProgressRing.test.tsx
~~~

Expected: FAIL because the props, class, custom color, and mount animation are not implemented.

- [ ] **Step 3: Implement the opt-in ring behavior**

Add the optional props, keep aria-valuenow, aria-valuemax, and the final text based on the real input, and use a mount-only state/effect to change --ring-progress from 0deg to the clamped final angle. Add --ring-color with the aqua fallback. Do not change callers that omit the new props.

In dashboard.css, register the angle custom property, add a 900 ms transition for .fitsho-progress-ring--mount-animated, use var(--ring-color, var(--fitsho-aqua)) in the nutrition card conic gradient, and disable that transition under prefers-reduced-motion: reduce.

- [ ] **Step 4: Run the focused web component tests**

~~~bash
npm run test --workspace frontend -- src/shared/ProgressRing.test.tsx
~~~

Expected: all focused component tests PASS.

- [ ] **Step 5: Commit web ring support**

~~~bash
git add frontend/src/shared/ProgressRing.tsx frontend/src/shared/ProgressRing.test.tsx frontend/src/pages/dashboard.css
git commit -m "feat(web-home): add animated colored progress ring"
git push origin main
~~~

### Task 3: Connect the web Dashboard Home nutrition card

**Files:**
- Modify: frontend/src/pages/DashboardPage.tsx
- Modify: frontend/src/pages/DashboardPage.test.tsx
- Modify: frontend/src/pages/dashboard.css

**Interfaces:**
- Consumes nutritionTargetToExpenditureRatio and nutritionProgressTone from @fitician/core.
- Maps green to var(--fitsho-success), blue to var(--fitsho-blue), and red to var(--fitsho-danger).
- Shows the target and TDEE metrics and adds an above-expenditure paragraph only when the target exceeds TDEE.

- [ ] **Step 1: Write failing Dashboard tests**

Add a test with a 1,800 kcal target and 3,000 kcal TDEE that asserts the exact 60% boundary selects the blue CSS token and enables mount animation. Add a gain-target test with a 3,000 kcal target and 2,400 kcal TDEE that asserts the ring is capped by its existing 100% display, uses the red token, and shows the localized ۶۰۰ کیلوکالری بالاتر از مصرف تقریبی روزانه message regardless of tracked calories.

Use the existing profile.productMode = "both", nutrition API mocks, and MemoryRouter setup; do not change the API mock contract.

- [ ] **Step 2: Run the focused Dashboard tests and verify failure**

~~~bash
npm run test --workspace frontend -- src/pages/DashboardPage.test.tsx
~~~

Expected: FAIL because the Dashboard does not yet pass a nutrition tone/animation or render the over-target copy.

- [ ] **Step 3: Implement Dashboard wiring and copy**

Calculate the unbounded ratio from target calories and TDEE, derive the shared tone, pass the mapped CSS color and animateOnMount to the Home ProgressRing, and render the localized above-expenditure message when the target difference is positive. Leave the estimate/plan/tracking requests and all non-nutrition cards unchanged.

Add a compact .command-card__overage style that remains readable in both RTL Persian and LTR English layouts and uses the existing danger/coral token only as the informational over-target emphasis.

- [ ] **Step 4: Run the focused Dashboard and ring tests**

~~~bash
npm run test --workspace frontend -- src/shared/ProgressRing.test.tsx src/pages/DashboardPage.test.tsx
~~~

Expected: all focused web tests PASS.

- [ ] **Step 5: Commit the Dashboard integration**

~~~bash
git add frontend/src/pages/DashboardPage.tsx frontend/src/pages/DashboardPage.test.tsx frontend/src/pages/dashboard.css
git commit -m "feat(web-home): show goal-relative nutrition progress"
git push origin main
~~~

### Task 4: Connect the native Fitician Home nutrition card

**Files:**
- Modify: mobile/home/homeModel.ts
- Modify: mobile/home/homeModel.test.ts
- Modify: mobile/home/NutritionSummaryCard.tsx
- Modify: mobile/home/homeCards.rntl.test.tsx

**Interfaces:**
- homeModel.nutritionSummary uses the shared unbounded nutritionTargetToExpenditureRatio, preserving gain-target information while MetricRing clamps its visual arc.
- NutritionSummaryCard maps the shared tone to fiticianTokens.colors.success, .blue, or .danger and keeps animateOnFocus with duration 900.
- Existing MetricRing default color and animation behavior for non-Home consumers remain unchanged.

- [ ] **Step 1: Write failing native/model tests**

Add a homeModel.test.ts case asserting a 3,000 kcal gain target with a 2,400 kcal TDEE returns 1.25, and a 1,800 kcal loss target with a 2,400 kcal TDEE returns 0.75 regardless of tracked calories.

Extend homeCards.rntl.test.tsx to assert the Home card's rendered progress circle receives the success color below 60%, the blue color at 60%, and the danger color at 90% or above. Add a gain-target fixture and assert ۶۰۰ کالری بالاتر از مصرف تقریبی روزانه is rendered while the metric ring's accessibility value remains capped at now: 100.

- [ ] **Step 2: Run the focused native/model tests and verify failure**

~~~bash
npm run test --workspace @fitician/mobile -- home/homeModel.test.ts
npm run test:native --workspace @fitician/mobile -- home/homeCards.rntl.test.tsx
~~~

Expected: the model test fails because the ratio is currently based on tracked intake, and the component assertions fail because the Home card always uses the default aqua color and has no above-expenditure copy.

- [ ] **Step 3: Implement native Home wiring**

Replace the local tracked-intake ratio calculation in homeModel.ts with nutritionTargetToExpenditureRatio. In NutritionSummaryCard.tsx, derive the shared tone, map it to the existing native tokens, pass color, keep animateOnFocus, and render the Persian above-expenditure message only for a positive target/TDEE difference.

Do not edit the concurrently modified files under mobile/nutrition/; this task is limited to mobile/home/.

- [ ] **Step 4: Run the focused native/model tests**

~~~bash
npm run test --workspace @fitician/mobile -- home/homeModel.test.ts
npm run test:native --workspace @fitician/mobile -- home/homeCards.rntl.test.tsx
~~~

Expected: all focused native Home tests PASS.

- [ ] **Step 5: Commit native Home integration**

~~~bash
git add mobile/home/homeModel.ts mobile/home/homeModel.test.ts mobile/home/NutritionSummaryCard.tsx mobile/home/homeCards.rntl.test.tsx
git commit -m "feat(android-home): show colored nutrition progress"
git push origin main
~~~

### Task 5: Run final scoped verification and review the diff

**Files:**
- Review only the files changed by Tasks 1–4.

- [ ] **Step 1: Rebuild the shared core and run focused web/core tests**

~~~bash
npm run build:core
npm run test --workspace @fitician/core -- src/nutrition-progress.test.ts
npm run test --workspace frontend -- src/shared/ProgressRing.test.tsx src/pages/DashboardPage.test.tsx
~~~

Expected: core build and all focused web/core tests PASS.

- [ ] **Step 2: Run scoped frontend checks**

~~~bash
npm run lint --workspace frontend
npm run build --workspace frontend
~~~

Expected: frontend lint and production build PASS. Any unrelated pre-existing failure is reported separately with its exact command output.

- [ ] **Step 3: Run scoped mobile checks**

~~~bash
npm run test --workspace @fitician/mobile -- home/homeModel.test.ts home/homePresentation.test.ts
npm run test:native --workspace @fitician/mobile -- home/homeCards.rntl.test.tsx
npm run typecheck:mobile
~~~

Expected: model/presentation tests, native Home test, and mobile typecheck PASS.

- [ ] **Step 4: Check formatting, scope, and repository state**

~~~bash
git diff --check HEAD~5..HEAD
git diff --stat HEAD~5..HEAD
git status --short --branch
~~~

Confirm that the three feature commits contain only the planned core/web/mobile files and that the pre-existing dirty WIP remains unstaged and uncommitted.

- [ ] **Step 5: Report the verified handoff**

Report the three commits, focused test results, frontend/mobile static checks, and explicitly distinguish automated verification from unavailable physical Android device visual verification.
