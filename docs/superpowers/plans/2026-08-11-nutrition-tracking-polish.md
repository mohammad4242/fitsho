# Nutrition Tracking Page Polish Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the adherence trend compact by default and turn off-plan meal logging into a polished, mobile-first Fitsho form without changing its data behavior.

**Architecture:** `NutritionTrackingPage` keeps ownership of all existing state and API functions, adding only local accordion state and semantic layout wrappers. Existing native controls remain the interaction boundary while page-scoped CSS supplies the dark/teal visual treatment and mobile behavior.

**Tech Stack:** React 19, TypeScript, Vitest, Testing Library, CSS

## Global Constraints

- Preserve nutrition calculations, API payloads, validation guards, date filtering, RTL/LTR behavior, and unrelated tracking sections.
- Keep real semantic select, input, and button elements; visually replace browser-default surfaces with Fitsho tokens.
- Keep the adherence heading and date selector visible while daily rows are collapsed by default.
- Add no dependency and no backend change.
- Respect reduced-motion preferences.

---

### Task 1: Controlled adherence accordion

**Files:**
- Modify: `frontend/src/features/nutrition/NutritionTrackingPage.tsx`
- Modify: `frontend/src/features/nutrition/NutritionWorkflowPages.test.tsx`
- Modify: `frontend/src/features/nutrition/nutritionEstimate.css`

**Interfaces:**
- Consumes: existing `rangeStart`, `setRangeStart`, `adherence`, and `history` state.
- Produces: local `adherenceOpen: boolean`, an `aria-expanded` toggle, and an animated body identified by `nutrition-adherence-content`.

- [ ] **Step 1: Write failing accordion tests**

Render `NutritionTrackingPage`, find the `Adherence trend` button, and assert it starts with
`aria-expanded="false"`. Assert the date input remains available and the content has
`aria-hidden="true"`. Click twice and assert the accessible state changes to true and back to
false. Change the date while closed and assert both `getNutritionAdherence(selected, today)` and
`getTrackingHistory(selected, today)` are called.

- [ ] **Step 2: Run the focused test to verify RED**

```bash
cd frontend && npm run test -- src/features/nutrition/NutritionWorkflowPages.test.tsx
```

Expected: FAIL because the heading is not an accordion button and the trend content has no closed
state.

- [ ] **Step 3: Implement the controlled accordion**

Add `const [adherenceOpen, setAdherenceOpen] = useState(false)`. Replace the trend section header
with a button carrying `aria-expanded` and `aria-controls`, keep the date label beside it, and wrap
the chart, weight note, and entry-history disclosure in a body whose open class, `aria-hidden`, and
`inert` state derive only from `adherenceOpen`.

- [ ] **Step 4: Add accordion styles**

Use a Fitsho surface card, a compact header grid, logical spacing, a CSS chevron, and a
`grid-template-rows` plus opacity transition. Add focus-visible treatment and a reduced-motion
override. Stack the date row beneath the button at narrow widths.

- [ ] **Step 5: Run the focused test to verify GREEN**

Run the Task 1 test command and confirm the accordion tests and existing workflow tests pass.

### Task 2: Off-plan meal form polish

**Files:**
- Modify: `frontend/src/features/nutrition/NutritionTrackingPage.tsx`
- Modify: `frontend/src/features/nutrition/NutritionWorkflowPages.test.tsx`
- Modify: `frontend/src/features/nutrition/nutritionEstimate.css`

**Interfaces:**
- Consumes: existing `foods`, `foodId`, `grams`, `calories`, `busy`, `addCatalogueFood`, and `addApproximation`.
- Produces: two semantic visual groups with unchanged accessible control names and unchanged API payloads.

- [ ] **Step 1: Write failing form behavior tests**

Open `Log food manually`, select `Lentils`, enter `175` grams, and activate `Add catalogue food`.
Assert `addCatalogueFoodEntry` receives exactly `{ entry_date: today, food_id: "food-2", grams:
175, note: null }`. Enter `430` calories and activate `Add estimate`; assert
`addQuickApproximation` receives the existing display name, date, calories, and null protein.
Assert the exact and approximate groups are exposed with distinct accessible labels.

- [ ] **Step 2: Run the focused test to verify RED**

Run the Task 1 test command. Expected: FAIL because the visual groups and polished form structure do
not exist, while existing API behavior remains characterized.

- [ ] **Step 3: Implement semantic form groups**

Replace the two generic quick rows with an exact catalogue group and a quick estimate group. Add
visible label text, dedicated field-shell spans, a select chevron, gram and calorie suffixes, and
explicit button types. Keep control values, change handlers, disabled conditions, and submission
functions unchanged.

- [ ] **Step 4: Add form styles**

Style the disclosure, group surfaces, labels, select, number inputs, suffixes, catalogue action, and
primary estimate action using existing Fitsho tokens. Remove native select appearance visually,
retain keyboard focus visibility, and add one-column mobile layout with touch targets of at least
2.75rem.

- [ ] **Step 5: Run focused tests to verify GREEN**

Run the Task 1 test command and confirm all workflow tests pass.

- [ ] **Step 6: Run full frontend verification**

```bash
cd frontend && npm run test
cd frontend && npm run lint
cd frontend && npm run build
```

Expected: zero test failures and exit code 0 for lint and build.

- [ ] **Step 7: Commit and push the focused implementation**

```bash
git add frontend/src/features/nutrition/NutritionTrackingPage.tsx frontend/src/features/nutrition/NutritionWorkflowPages.test.tsx frontend/src/features/nutrition/nutritionEstimate.css
git commit -m "feat(nutrition-tracking): polish adherence and off-plan entry"
git push origin nutrition
```

### Task 3: Mobile runtime verification

**Files:**
- No tracked changes expected.

**Interfaces:**
- Consumes: current Vite and backend processes.
- Produces: a served tracking page ready for manual testing.

- [ ] **Step 1: Confirm current services and source**

Verify frontend and backend status codes and confirm Vite serves the new tracking-page labels.

- [ ] **Step 2: Inspect at mobile width**

Use an authenticated browser session if available. At approximately 390px width, verify the closed
trend card, open transition, stacked field groups, visible focus/touch surfaces, RTL alignment, and
absence of horizontal overflow. If authentication is unavailable, report that limitation and rely
on responsive CSS plus automated behavior/build evidence.
