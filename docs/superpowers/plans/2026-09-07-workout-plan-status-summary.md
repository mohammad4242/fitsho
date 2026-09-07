# Workout Plan Status Summary Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Show the real workout-plan status and the rounded average duration of all sessions in the displayed plan in the existing four-item workout summary.

**Architecture:** Keep this change frontend-only in `WorkoutPlanPage`. Select the active or pending plan already loaded by the page, derive one of three compact statuses from persisted plan/review fields and historical selection, and calculate the duration average from the selected plan's day durations. Reuse `AppIcon`, existing responsive summary layout, and the current review banners.

**Tech Stack:** React 19, TypeScript, react-i18next, Vitest, Testing Library, CSS.

**Spec:** `docs/superpowers/specs/2026-09-07-workout-plan-status-design.md`

## Global Constraints

- Keep the existing four-column summary layout.
- Use `plan ?? pendingPlan` for the summary when a pending-only plan is available.
- Show `pending` for `pending_review` or `pending_coach_review`.
- Show `inactive` for historical or non-active plans other than a pending-only plan.
- Calculate duration as `Math.round(sum / count)` over every displayed plan day.
- Do not add backend routes, database fields, migrations, or new persistence.
- Preserve existing coach-review banners, pending-plan rendering, and unrelated worktree changes.

---

### Task 1: Add regression coverage for summary status and average duration

**Files:**
- Modify: `frontend/src/features/workouts/WorkoutPlanPage.test.tsx`

**Interfaces:**
- Consumes: Existing `WorkoutPlanPage` props, API mocks, `pendingVersion`, and `pendingPlan` fixtures.
- Produces: UI regression coverage for active, pending, inactive, pending-only, and rounded-average summary states.

- [ ] **Step 1: Write the failing tests**

Add tests next to the existing `shows plan context without cinematic background media` test:

```tsx
it("shows the rounded average duration for every session instead of a range", async () => {
  const averagePlan: WorkoutPlan = {
    ...plan,
    days: [
      { ...plan.days[0]!, day_number: 1, estimated_duration_minutes: 44 },
      { ...plan.days[0]!, day_number: 2, estimated_duration_minutes: 45 },
    ],
  };
  api.getActiveWorkoutPlan.mockResolvedValue(averagePlan);

  render(<MemoryRouter><WorkoutPlanPage planDurationWeeks={4} /></MemoryRouter>);

  expect(await screen.findByText("۴۵ دقیقه برای هر جلسه")).toBeInTheDocument();
  expect(screen.queryByText("۴۴ تا ۴۵ دقیقه")).not.toBeInTheDocument();
});

it("shows the active compact plan status", async () => {
  api.getActiveWorkoutPlan.mockResolvedValue(plan);

  render(<MemoryRouter><WorkoutPlanPage planDurationWeeks={4} /></MemoryRouter>);

  const status = await screen.findByText("فعال");
  expect(status.closest("strong")).toHaveClass("workout-plan-context__status--active");
});

it("shows pending when coach approval is still pending", async () => {
  api.getActiveWorkoutPlan.mockResolvedValue({
    ...plan,
    coach_review: {
      state: "pending_coach_review",
      coach_display_name: null,
      coach_note: null,
      approved_at: null,
    },
  });

  render(<MemoryRouter><WorkoutPlanPage planDurationWeeks={4} /></MemoryRouter>);

  const status = await screen.findByText("در انتظار مربی");
  expect(status.closest("strong")).toHaveClass("workout-plan-context__status--pending");
});

it("shows inactive when an archived version is selected", async () => {
  api.getActiveWorkoutPlan.mockResolvedValue(plan);
  api.getWorkoutPlanHistory.mockResolvedValue([
    {
      id: plan.id,
      status: "active",
      created_at: plan.created_at,
      activated_at: plan.activated_at,
      is_active: true,
      coach_review: { state: "none", coach_display_name: null, coach_note: null, approved_at: null },
    },
    {
      ...pendingVersion,
      id: "018f0000-0000-7000-8000-000000000098",
      status: "superseded",
      is_active: false,
      coach_review: { state: "initial_generated", coach_display_name: null, coach_note: null, approved_at: null },
    },
  ]);
  api.getWorkoutPlan.mockResolvedValue({ ...plan, id: "018f0000-0000-7000-8000-000000000098", status: "superseded" });
  const user = userEvent.setup();

  render(<MemoryRouter><WorkoutPlanPage planDurationWeeks={4} /></MemoryRouter>);

  await user.click(await screen.findByRole("button", { name: /نسخه اولیه/ }));
  const status = await screen.findByText("غیرفعال");
  expect(status.closest("strong")).toHaveClass("workout-plan-context__status--inactive");
});

it("shows pending status and summary data for a pending-only plan", async () => {
  api.getActiveWorkoutPlan.mockResolvedValue(null);
  api.getWorkoutPlanHistory.mockResolvedValue([pendingVersion]);
  api.getWorkoutPlan.mockResolvedValue(pendingPlan);

  render(<MemoryRouter><WorkoutPlanPage planDurationWeeks={4} /></MemoryRouter>);

  expect(await screen.findByText("در انتظار مربی")).toBeInTheDocument();
  expect(screen.getByText("۴۵ دقیقه برای هر جلسه")).toBeInTheDocument();
});
```

- [ ] **Step 2: Run the focused test file to verify the new tests fail**

Run:

```bash
cd frontend && npm run test -- src/features/workouts/WorkoutPlanPage.test.tsx
```

Expected: the existing tests pass, while the new assertions fail because the summary currently hard-codes `active`, renders a min/max range, and hides the pending-only summary.

- [ ] **Step 3: Commit the verified implementation after the red test run**

Do not commit an intentionally failing test-only state. The tests become part of the implementation commit after the minimal code makes them pass:

```bash
git add frontend/src/features/workouts/WorkoutPlanPage.test.tsx frontend/src/features/workouts/WorkoutPlanPage.tsx frontend/src/features/workouts/workoutPlan.css frontend/src/i18n/fa.ts frontend/src/i18n/en.ts
git commit -m "feat(ui): show workout plan status and session average"
```

### Task 2: Implement compact status and rounded session average

**Files:**
- Modify: `frontend/src/features/workouts/WorkoutPlanPage.tsx`
- Modify: `frontend/src/features/workouts/workoutPlan.css`
- Modify: `frontend/src/i18n/fa.ts`
- Modify: `frontend/src/i18n/en.ts`
- Test: `frontend/src/features/workouts/WorkoutPlanPage.test.tsx`

**Interfaces:**
- Consumes: `WorkoutPlan.status`, `WorkoutPlan.coach_review.state`, `isViewingHistorical`, `plan`, and `pendingPlan`.
- Produces: A four-item summary whose first item has a status-specific icon/label and whose fourth item displays the rounded average duration.

- [ ] **Step 1: Add the minimal status and average derivation**

Import `IconName` as a type and define the local status union/maps near the existing page types:

```tsx
type WorkoutPlanSummaryStatus = "active" | "pending" | "inactive";

const workoutPlanStatusIcons: Record<WorkoutPlanSummaryStatus, IconName> = {
  active: "zap",
  pending: "clock",
  inactive: "lock",
};

function getWorkoutPlanSummaryStatus(plan: WorkoutPlan, historical: boolean): WorkoutPlanSummaryStatus {
  if (historical) return "inactive";
  if (plan.status === "pending_review" || plan.coach_review?.state === "pending_coach_review") return "pending";
  return plan.status === "active" ? "active" : "inactive";
}
```

Inside `WorkoutPlanPage`, derive the summary from `plan ?? pendingPlan`, map the compact label key (`active`, `pendingCoach`, or `inactive`), and calculate:

```tsx
const summaryPlan = plan ?? pendingPlan;
const sessionDurations = summaryPlan?.days.map((day) => day.estimated_duration_minutes) ?? [];
const averageSession = sessionDurations.length > 0
  ? Math.round(sessionDurations.reduce((total, duration) => total + duration, 0) / sessionDurations.length)
  : null;
```

Render the context when `summaryPlan !== null && averageSession !== null`. Keep cycle and training-day values based on `summaryPlan`; replace the first cell with a status class, existing `AppIcon`, and the mapped translated label; replace the range branch with `perSession` using `averageSession`.

- [ ] **Step 2: Add only the compact styles and translations**

Add Persian labels `pendingCoach: "در انتظار مربی"` and `inactive: "غیرفعال"`, English labels `pendingCoach: "Waiting for coach"` and `inactive: "Inactive"`, and make `contextLabel` generic (`خلاصه برنامه` / `Plan summary`).

Add a small inline-flex status style in `workoutPlan.css` using existing theme variables. Give active/pending/inactive status icons and text distinct existing theme colors, keep the current font sizes, and preserve the four-column/mobile layout. The icon must remain decorative (`aria-hidden` through `AppIcon`).

- [ ] **Step 3: Run the focused tests to verify the implementation passes**

Run:

```bash
cd frontend && npm run test -- src/features/workouts/WorkoutPlanPage.test.tsx
```

Expected: all tests in `WorkoutPlanPage.test.tsx` pass, including the new status and average assertions.

### Task 3: Run frontend quality gates and push the implementation

**Files:**
- Verify: `frontend/src/features/workouts/WorkoutPlanPage.tsx`
- Verify: `frontend/src/features/workouts/workoutPlan.css`
- Verify: `frontend/src/i18n/fa.ts`
- Verify: `frontend/src/i18n/en.ts`
- Verify: `frontend/src/features/workouts/WorkoutPlanPage.test.tsx`

**Interfaces:**
- Consumes: The passing focused workout page implementation.
- Produces: Fresh lint/build evidence and a pushed implementation commit.

- [ ] **Step 1: Run frontend lint**

Run:

```bash
cd frontend && npm run lint
```

Expected: exit code 0 with no lint errors.

- [ ] **Step 2: Run the frontend production build**

Run:

```bash
cd frontend && npm run build
```

Expected: exit code 0 and a successful Vite production build.

- [ ] **Step 3: Inspect the scoped diff**

Run:

```bash
git diff --check
git diff --stat
git status --short
```

Confirm only the five workout UI/test files are staged for the implementation commit; preserve the pre-existing auth test modification and untracked user assets/reports.

- [ ] **Step 4: Push the implementation commit**

Run:

```bash
git push origin main
```

Expected: `origin/main` advances to the implementation commit without force-pushing or altering unrelated work.
