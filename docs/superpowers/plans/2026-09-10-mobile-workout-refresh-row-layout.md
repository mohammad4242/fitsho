# Mobile Workout Refresh and RTL Row Layout Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the native generated-workout page keep its web-parity update action usable and place exercise media on the right with exercise details on the left in the Persian RTL layout.

**Architecture:** Keep the existing `WorkoutPlansScreen` query, mutation, cache, routing, media, coach-review, history, PDF, cycle, and replacement boundaries. Remove only the native pending-review generation gate and correct the two row containers that currently double-reverse the already RTL screen direction.

**Tech Stack:** Expo SDK 57, React Native 0.86, TypeScript, TanStack Query, Jest, Testing Library React Native, Vitest, and the existing Fitician token/icon/media components.

**Spec:** `docs/superpowers/specs/2026-09-10-mobile-workout-refresh-row-layout-design.md`

## Global Constraints

- Modify only `mobile/workouts/WorkoutPlansScreen.tsx` and its focused workout tests for the implementation.
- Keep Backend, API contracts, query keys, generation persistence, coach review, history, replacement, navigation, and media rendering unchanged.
- Keep historical plans without an update action.
- Keep pending-only display behavior consistent with the web page.
- Preserve Persian RTL typography, 48 dp touch targets, offline/error states, and all existing workout actions.
- Preserve unrelated dirty-worktree changes and stage only explicit task files.

---

### Task 1: Add red regressions for update gating and RTL row order

**Files:**
- Modify: `mobile/workouts/WorkoutPlansScreen.rntl.test.tsx`
- Modify: `mobile/workouts/workoutPresentation.nativeContract.test.ts`

**Interfaces:**
- The native render regression uses the existing `mockActivePlan`, `mockHistory`, `renderWorkoutPlans`, and `mockMutate` fixtures.
- The source contract regression inspects the existing `daySummary` and `exerciseRow` style blocks without importing a new layout abstraction.

- [ ] **Step 1: Write the failing native update test**

Add this test after the existing generation-control test in `WorkoutPlansScreen.rntl.test.tsx`:

```tsx
test("keeps the update action enabled when a pending review version exists", () => {
  const exercise = makeExercise("exercise-1", "شنا", "Push-up");
  mockActivePlan = makePlan("active", [makePlanExercise("plan-exercise-1", exercise, [])]);
  mockHistory = [makeHistoryVersion("pending-plan")];

  renderWorkoutPlans();

  const updateButton = screen.getByRole("button", { name: "به‌روزرسانی برنامه" });
  expect(updateButton.props.accessibilityState).toMatchObject({ disabled: false });

  fireEvent.press(updateButton);

  expect(mockMutate).toHaveBeenCalledTimes(1);
});
```

- [ ] **Step 2: Write the failing RTL source contract**

Add this test to `workoutPresentation.nativeContract.test.ts`:

```ts
it("keeps workout media first in the existing RTL row containers", async () => {
  const source = await readFile(new URL("./WorkoutPlansScreen.tsx", import.meta.url), "utf8");
  const daySummary = source.slice(source.indexOf("daySummary:"), source.indexOf("durationBadge:"));
  const exerciseRow = source.slice(source.indexOf("exerciseRow:"), source.indexOf("readOnlyAlternatives:"));

  expect(daySummary).toContain('flexDirection: "row"');
  expect(daySummary).not.toContain('flexDirection: "row-reverse"');
  expect(exerciseRow).toContain('flexDirection: "row"');
  expect(exerciseRow).not.toContain('flexDirection: "row-reverse"');
});
```

- [ ] **Step 3: Run the regressions and confirm the expected failures**

Run:

```bash
npm --prefix mobile run test:native -- WorkoutPlansScreen.rntl.test.tsx
npm --prefix mobile exec vitest run workouts/workoutPresentation.nativeContract.test.ts
```

Expected: the native test reports `disabled: true` instead of `false`, and the source contract reports `row-reverse` in both targeted style blocks. These failures prove the regressions exercise the current bugs.

### Task 2: Remove the pending gate and correct the native RTL rows

**Files:**
- Modify: `mobile/workouts/WorkoutPlansScreen.tsx:238-248, 425-542, 1069-1076, 1519-1528`

**Interfaces:**
- `PlanView` no longer accepts `canGenerate`.
- The existing `onGenerate` callback remains optional, so historical plans still omit the update action.
- The existing `generationPending` state remains the only update-button disable condition.

- [ ] **Step 1: Remove the mobile-only generation gate**

Delete `canGenerate={pendingPlanId === null && selectedPlanId === null}` from the active `PlanView` call. Remove `canGenerate` from the `PlanView` props type and parameter destructuring. Change the update button from:

```tsx
disabled={!canGenerate || generationPending}
```

to:

```tsx
disabled={generationPending}
```

Do not change `onGenerate={selectedPlanId === null ? startGeneration : undefined}` or the mutation's refetch handlers.

- [ ] **Step 2: Correct the two RTL row directions**

Change only these style values:

```tsx
daySummary: {
  // existing properties remain unchanged
  flexDirection: "row",
},

exerciseRow: {
  // existing properties remain unchanged
  flexDirection: "row",
},
```

Do not change `exerciseStatsRow`, `exerciseStat`, action rows, context strip, or unrelated cycle-panel layout directions.

- [ ] **Step 3: Run focused tests and verify green**

Run:

```bash
npm --prefix mobile run test:native -- WorkoutPlansScreen.rntl.test.tsx
npm --prefix mobile exec vitest run workouts/workoutPresentation.nativeContract.test.ts workouts/workoutMedia.nativeContract.test.ts workouts/workoutModel.test.ts workouts/workoutApi.test.ts
```

Expected: all selected native and Vitest tests pass, including the new update-enabled and RTL-row regressions.

- [ ] **Step 4: Inspect the scoped diff and commit**

Run:

```bash
git diff --check
git diff -- mobile/workouts/WorkoutPlansScreen.tsx mobile/workouts/WorkoutPlansScreen.rntl.test.tsx mobile/workouts/workoutPresentation.nativeContract.test.ts
```

Proposed commit:

```bash
git add -- mobile/workouts/WorkoutPlansScreen.tsx mobile/workouts/WorkoutPlansScreen.rntl.test.tsx mobile/workouts/workoutPresentation.nativeContract.test.ts
git commit -m "fix(mobile-workouts): align refresh gating and RTL media rows"
git push origin main
```

### Task 3: Run mobile verification and confirm release boundary

**Files:**
- Verify: `mobile/workouts/WorkoutPlansScreen.tsx`
- Verify: `mobile/workouts/WorkoutPlansScreen.rntl.test.tsx`
- Verify: `mobile/workouts/workoutPresentation.nativeContract.test.ts`

**Interfaces:**
- No additional production changes are planned.
- Automated checks prove the update callback is reachable and the native style contract matches the web direction; physical Android rendering remains a separate device check.

- [ ] **Step 1: Run the complete mobile Vitest suite**

Run:

```bash
npm --prefix mobile test
```

Record the exact pass/fail count and separate failures unrelated to the touched workout files.

- [ ] **Step 2: Run the complete native Jest suite**

Run:

```bash
npm --prefix mobile run test:native
```

Record the exact pass/fail count and stop to investigate any failure caused by the touched screen or tests.

- [ ] **Step 3: Run typecheck and focused lint**

Run:

```bash
npm run typecheck:mobile
./node_modules/.bin/oxlint mobile/workouts/WorkoutPlansScreen.tsx mobile/workouts/WorkoutPlansScreen.rntl.test.tsx mobile/workouts/workoutPresentation.nativeContract.test.ts
git diff --check
```

Expected: all commands exit zero. If the environment blocks a command, report that command and its exact error instead of claiming device or release success.

- [ ] **Step 4: Verify Git scope and pushed commit**

Run:

```bash
git status --short --branch
git show --stat --oneline HEAD
git log -1 --format='%H%n%s'
```

Confirm the implementation commit contains only the three scoped workout files and that unrelated WIP remains unchanged. Report that automated verification does not replace physical Android visual testing.
