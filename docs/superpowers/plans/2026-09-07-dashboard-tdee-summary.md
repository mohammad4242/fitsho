# Dashboard TDEE Summary Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Show the estimated total daily calorie expenditure beside today's calorie goal in the dashboard nutrition card.

**Architecture:** Reuse the `NutritionEstimate` already loaded by `DashboardPage`. Derive TDEE from `targets.tdee` and render it as a compact secondary value in the existing calorie area. No new request, endpoint, calculation, persistence field, or shared component is needed.

**Tech Stack:** React 19, TypeScript, Vitest, Testing Library, CSS, Vite.

**Spec:** `docs/superpowers/specs/2026-09-07-dashboard-tdee-design.md`

## Global Constraints

- Preserve the existing calorie progress ring, tracked-calorie behavior, macro strip, links, and nutrition API.
- Use `targets.tdee.preferred`, falling back to `targets.tdee.minimum` when preferred is unavailable.
- Display `مصرف تقریبی روزانه` in Persian and `Estimated daily expenditure` in English.
- Hide the secondary value when TDEE is unavailable.
- Preserve unrelated working-tree changes and stage only the three implementation files.

### Task 1: Add dashboard regression coverage

**Files:**
- Modify: `frontend/src/pages/DashboardPage.test.tsx`
- Test: `frontend/src/pages/DashboardPage.test.tsx`

**Interfaces:**
- Consumes: Existing `nutritionApi.getCurrentNutritionEstimate` mock and dashboard rendering helpers.
- Produces: Failing and then passing assertions for TDEE visibility and absence.

- [ ] **Step 1: Write the failing visibility test**

Add one test with a combined product mode and an estimate containing `goal_calories.preferred = 2567` and `tdee.preferred = 2834`. Keep the existing protein, carbohydrate, and total-fat target fields so the dashboard renders normally. Assert that `۲٬۸۳۴` and `مصرف تقریبی روزانه` are visible after rendering.

```tsx
it("shows estimated daily expenditure beside the calorie goal", async () => {
  profile.productMode = "both";
  workoutApi.getActiveWorkoutPlan.mockResolvedValue(null);
  nutritionApi.getCurrentNutritionEstimate.mockResolvedValue({
    confidence: "high",
    targets: {
      goal_calories: { preferred: 2567 },
      tdee: { preferred: 2834 },
      protein: { preferred: 130 },
      carbohydrate: { preferred: 280 },
      total_fat: { preferred: 68 },
    },
  });

  render(<MemoryRouter><DashboardPage /></MemoryRouter>);

  expect(await screen.findByText("۲٬۸۳۴")).toBeInTheDocument();
  expect(screen.getByText("مصرف تقریبی روزانه")).toBeInTheDocument();
});
```

- [ ] **Step 2: Run the focused test and verify the correct failure**

Run from `frontend/`:

```bash
npm run test -- src/pages/DashboardPage.test.tsx
```

Expected: the dashboard test file runs, and the new test fails because the current dashboard does not render the TDEE value or label.

- [ ] **Step 3: Add the missing-data regression test**

Add a second test with the existing estimate shape but without `targets.tdee`. Assert the normal goal remains visible and `screen.queryByText("مصرف تقریبی روزانه")` is not in the document. This locks the no-clutter fallback behavior.

```tsx
it("hides estimated daily expenditure when TDEE is unavailable", async () => {
  profile.productMode = "both";
  workoutApi.getActiveWorkoutPlan.mockResolvedValue(null);
  nutritionApi.getCurrentNutritionEstimate.mockResolvedValue({
    confidence: "high",
    targets: {
      goal_calories: { preferred: 2567 },
      protein: { preferred: 130 },
      carbohydrate: { preferred: 280 },
      total_fat: { preferred: 68 },
    },
  });

  render(<MemoryRouter><DashboardPage /></MemoryRouter>);

  expect(await screen.findByText("۲٬۵۶۷")).toBeInTheDocument();
  expect(screen.queryByText("مصرف تقریبی روزانه")).not.toBeInTheDocument();
});
```

- [ ] **Step 4: Run both focused tests**

Run the same focused command and confirm the new visibility test is still red before production code is changed, while the missing-data test reflects the existing behavior.

### Task 2: Render TDEE in the existing dashboard calorie area

**Files:**
- Modify: `frontend/src/pages/DashboardPage.tsx`
- Modify: `frontend/src/pages/dashboard.css`

**Interfaces:**
- Consumes: `nutritionEstimate?.targets.tdee` from the existing current-estimate request.
- Produces: A secondary calorie metric rendered only when TDEE has a usable preferred or minimum value.

- [ ] **Step 1: Derive the TDEE value from the existing estimate**

Immediately beside the existing `estimated` target derivation, add:

```tsx
const tdeeTarget = estimated?.tdee?.preferred ?? estimated?.tdee?.minimum ?? null;
```

Do not add a request or alter the `NutritionEstimate` type.

- [ ] **Step 2: Add the compact secondary metric**

Inside `.command-card__calories`, wrap the existing calorie value block in `.command-card__calorie-values`. Keep its tracked-calorie number and progress ring unchanged. Render this conditional block after the existing value block:

```tsx
{tdeeTarget !== null && (
  <div>
    <strong>{format(tdeeTarget)}</strong>
    <span>{english ? "Estimated daily expenditure" : "مصرف تقریبی روزانه"}</span>
  </div>
)}
```

- [ ] **Step 3: Add only the required layout styles**

Replace the current direct-child calorie selectors with selectors for `.command-card__calorie-values`. Use a compact horizontal flex row, a subtle inline divider between the two values, and the existing number/label typography. Keep `min-width: 0` so the existing card can shrink safely.

```css
.command-card__calorie-values {
  display: flex;
  align-items: flex-start;
  gap: 1rem;
  min-width: 0;
}

.command-card__calorie-values > div {
  display: grid;
  min-width: 0;
}

.command-card__calorie-values > div + div {
  border-inline-start: 1px solid var(--fitsho-line);
  padding-inline-start: 1rem;
}
```

Keep the existing font size, muted label color, progress ring, and metric strip rules aligned with the new wrapper. Do not introduce a new card, badge, animation, or page-level layout change.

- [ ] **Step 4: Run the focused dashboard suite**

Run from `frontend/`:

```bash
npm run test -- src/pages/DashboardPage.test.tsx
```

Expected: all dashboard tests pass, including the TDEE visibility and missing-data regressions.

### Task 3: Verify and commit the implementation

**Files:**
- Verify: `frontend/src/pages/DashboardPage.tsx`
- Verify: `frontend/src/pages/dashboard.css`
- Verify: `frontend/src/pages/DashboardPage.test.tsx`

- [ ] **Step 1: Run frontend lint**

Run from `frontend/`:

```bash
npm run lint
```

Expected: exit code 0 with no new lint findings.

- [ ] **Step 2: Run the production build**

Run from `frontend/`:

```bash
npm run build
```

Expected: exit code 0 and a completed Vite production build.

- [ ] **Step 3: Check the scoped diff**

Run from the repository root:

```bash
git diff --check -- frontend/src/pages/DashboardPage.tsx frontend/src/pages/dashboard.css frontend/src/pages/DashboardPage.test.tsx
git diff -- frontend/src/pages/DashboardPage.tsx frontend/src/pages/dashboard.css frontend/src/pages/DashboardPage.test.tsx
```

Confirm the diff contains only the TDEE derivation, compact secondary metric, focused styles, and regression tests.

- [ ] **Step 4: Commit only the implementation files**

Run from the repository root:

```bash
git add frontend/src/pages/DashboardPage.tsx frontend/src/pages/dashboard.css frontend/src/pages/DashboardPage.test.tsx
git commit -m "feat: show TDEE beside dashboard calorie goal"
```

- [ ] **Step 5: Push the current branch**

Run from the repository root:

```bash
git push origin main
```

Confirm the branch is synchronized after the push without staging or modifying unrelated user files.

