# Nutrition Page Reference UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Align the existing Fitsho nutrition page with the calorie, doctor-supervision, and weekly-plan CTA elements in `taghziye.jpg` without changing nutrition APIs or calculations.

**Architecture:** A focused animation hook owns one normalized request-animation-frame timeline. `NutritionEstimatePage` consumes that value for both the calorie number and existing `ProgressRing`, then renders a data-backed doctor section and compact CTA with page-scoped styles.

**Tech Stack:** React 19, TypeScript, React Router, Vitest, Testing Library, CSS

## Global Constraints

- Preserve existing nutrition logic, API behavior, RTL/LTR support, responsive behavior, and unrelated page areas.
- Use the existing `energyTarget` derivation; never hardcode nutrition values.
- The number and ring must share one timeline and finish at the exact target and 100%.
- Use existing Fitsho tokens and routes; add no dependency and no backend request.
- Respect reduced-motion preferences by rendering the final state immediately.

---

### Task 1: Synchronized progress hook

**Files:**
- Create: `frontend/src/features/nutrition/useSynchronizedProgress.ts`
- Create: `frontend/src/features/nutrition/useSynchronizedProgress.test.tsx`

**Interfaces:**
- Produces: `useSynchronizedProgress(durationMs?: number): number`, returning a normalized value in `[0, 1]`.
- Consumes: browser `requestAnimationFrame`, `cancelAnimationFrame`, `performance.now`, and `matchMedia`.

- [ ] **Step 1: Write the failing hook tests**

Create a small harness that renders the returned value. Stub animation frames so the test can run the start frame and completion frame independently. Assert an initial value of `0`, a final value of `1`, cancellation on unmount, and immediate `1` when reduced motion is active.

- [ ] **Step 2: Run tests to verify RED**

Run:

```bash
cd frontend && npm run test -- src/features/nutrition/useSynchronizedProgress.test.tsx
```

Expected: FAIL because `useSynchronizedProgress` does not exist.

- [ ] **Step 3: Implement the hook**

Use one effect and one animation-frame chain. Capture the first callback timestamp as the start, apply an ease-out curve to elapsed progress, clamp the result, set exactly `1` at completion, and cancel the queued frame during cleanup. Return `1` immediately when `prefers-reduced-motion: reduce` matches.

- [ ] **Step 4: Run tests to verify GREEN**

Run the Task 1 test command and confirm all hook tests pass.

- [ ] **Step 5: Commit and push Task 1**

```bash
git add frontend/src/features/nutrition/useSynchronizedProgress.ts frontend/src/features/nutrition/useSynchronizedProgress.test.tsx
git commit -m "feat(nutrition): add synchronized target animation"
git push origin nutrition
```

### Task 2: Nutrition page composition

**Files:**
- Modify: `frontend/src/features/nutrition/NutritionEstimatePage.tsx`
- Modify: `frontend/src/features/nutrition/NutritionEstimatePage.test.tsx`
- Modify: `frontend/src/features/nutrition/nutritionEstimate.css`

**Interfaces:**
- Consumes: `useSynchronizedProgress(durationMs?: number): number` from Task 1.
- Consumes: existing `WeeklyPlan.review_status`, `WeeklyPlan.physician_approved`, `WeeklyPlan.lifecycle_status`, and `WeeklyPlan.physician_user_visible_notes`.
- Produces: the calorie goal display, `DoctorSupervision` page section, and compact empty-plan CTA.

- [ ] **Step 1: Write failing page tests**

Add tests which would fail if the calorie target were hardcoded, number and ring used different timelines, pending review were inferred without a plan, doctor links used wrong routes, or the removed CTA copy returned. Assert:

```text
کالری هدف
تحت نظر پزشک
مکمل‌های من -> /nutrition-supplements
آزمایشات من -> /nutrition-labs
تأیید برنامه غذایی
راهنمایی‌های پزشک
ساخت برنامه تغذیه هفتگی
```

Control frames and assert the real fixture target starts at zero and ends at `۲٬۱۰۰`, while the progressbar ends with `aria-valuenow="2100"`, `aria-valuemax="2100"`, and visible `100%`. With `weeklyPlan`, assert the red pending text appears; without it, assert the neutral state and no pending claim.

- [ ] **Step 2: Run focused page tests to verify RED**

Run:

```bash
cd frontend && npm run test -- src/features/nutrition/NutritionEstimatePage.test.tsx
```

Expected: FAIL on the new calorie label, supervision section, synchronized final ring, and compact CTA assertions.

- [ ] **Step 3: Implement the page behavior**

Call the hook once inside `EstimateContent`. Render `energyTarget * animationProgress` as the goal number and pass the same product to `ProgressRing`. Always describe it as the calorie goal, while leaving tracked macro behavior unchanged.

Add `DoctorSupervision` below `EstimateContent`. Use existing links for supplements and labs. Derive approval copy and pending styling only from an existing plan. Derive guidance availability from `physician_user_visible_notes`; do not create a new route or API call.

Simplify the empty `PlanArea` default state to one button. Keep the existing busy label and render outcome-specific feedback only after a generation attempt.

- [ ] **Step 4: Add scoped responsive styling**

Compact the calorie panel and ring without changing shared `ProgressRing` defaults. Style the supervision section as a Fitsho surface with a doctor header, two-column item grid, clear red status dot, keyboard-visible link states, and one-column mobile fallback. Style the empty-plan section as a single compact full-width CTA inspired by the reference.

- [ ] **Step 5: Run focused page tests to verify GREEN**

Run the Task 2 test command and confirm all nutrition page tests pass.

- [ ] **Step 6: Run frontend verification**

```bash
cd frontend && npm run test
cd frontend && npm run lint
cd frontend && npm run build
```

Expected: zero test failures, lint exit code 0, build exit code 0.

- [ ] **Step 7: Review the final diff and commit**

Confirm only the nutrition page, its focused test/style files, and the hook files are staged. Commit:

```bash
git commit -m "feat(nutrition): align target and doctor supervision UI"
git push origin nutrition
```

### Task 3: Local runtime handoff

**Files:**
- No tracked file changes expected.

**Interfaces:**
- Consumes: the repository's current Vite proxy and backend runtime configuration.
- Produces: reachable local frontend and backend processes for manual user testing.

- [ ] **Step 1: Inspect current runtime configuration**

Check the active Compose services, frontend proxy target, configured frontend origin, and occupied ports without changing user configuration.

- [ ] **Step 2: Start missing services in persistent sessions**

Use the existing project commands and current ports. Do not use detached `nohup`. Keep service sessions alive for the user.

- [ ] **Step 3: Smoke-test reachability**

Request the frontend root and backend health endpoint, then report the exact usable URL and any login/runtime prerequisite.
