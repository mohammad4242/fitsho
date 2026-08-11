# Panel-Driven Authenticated UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Recompose Fitsho's authenticated frontend around the real-data density and hierarchy of `Panel.png` without changing backend behavior.

**Architecture:** Existing routes and page modules remain. Shared visual primitives are extended, while each page composes existing API responses into a panel-mapped hierarchy. Product-mode and role gates continue to live in the current shell/context code.

**Tech Stack:** React 19, TypeScript, React Router, i18next, CSS tokens/primitives, Vitest, Testing Library, Vite.

## Global Constraints

- Do not bundle, render, or copy `Panel.png` into the product.
- Do not add backend fields, fake metrics, unsupported workout tracking, recovery scores, or medical claims.
- Preserve authentication, guards, routes, API contracts, product modes, permissions, and RTL/LTR localization.
- Keep public landing and public onboarding out of scope.
- Preserve unrelated working-tree changes and stage only authenticated UI work.

---

### Task 1: Foundation and shell

**Files:** `frontend/src/styles/tokens.css`, `frontend/src/styles/primitives.css`, `frontend/src/shared/AppShell.tsx`, `frontend/src/shared/AppShell.test.tsx`, `frontend/src/shared/AuthenticatedHeader.tsx`, `frontend/src/shared/authenticatedHeader.css`, `frontend/src/App.test.tsx`.

- [ ] Add failing tests for capability-aware five-destination navigation, secondary-route activation, contextual mobile headers, and accessible ring values.
- [ ] Run focused tests and confirm the new assertions fail for the intended structural reason.
- [ ] Tighten tokens, connected metric/data primitives, header proportions, safe areas, and desktop containment.
- [ ] Run shell/design-system tests, lint, and a 360/390/430 visual check; commit.

### Task 2: Dashboard

**Files:** `frontend/src/pages/DashboardPage.tsx`, `frontend/src/pages/dashboard.css`, `frontend/src/pages/DashboardPage.test.tsx`.

- [ ] Add failing tests proving the hero uses the first real exercise media and nutrition falls back from weekly-plan targets to the current estimate without inventing values.
- [ ] Load workout, estimate, daily tracking, and weekly-plan data through existing APIs.
- [ ] Build the media-led workout hero, real calorie ring/macro strip, and compact truthful progress summary.
- [ ] Run focused tests and compare at 360/390/430 and desktop; commit.

### Task 3: Nutrition overview

**Files:** `frontend/src/features/nutrition/NutritionEstimatePage.tsx`, `frontend/src/features/nutrition/nutritionEstimate.css`, `frontend/src/features/nutrition/NutritionEstimatePage.test.tsx`.

- [ ] Add failing tests for daily tracking integration, real ring values, meal rows, and compact physician state.
- [ ] Combine estimate, latest plan, and current tracking into one daily instrument panel.
- [ ] Render real meal rows from the current plan day and keep scientific/provenance content under details.
- [ ] Run focused tests and visual checks in RTL/LTR; commit.

### Task 4: Meal photo tracking

**Files:** `frontend/src/features/nutrition/NutritionTrackingPage.tsx`, `frontend/src/features/nutrition/nutritionEstimate.css`, `frontend/src/features/nutrition/NutritionWorkflowPages.test.tsx`.

- [ ] Add failing tests for selected-image preview, analyzing state, estimate labeling, confidence, correction/removal, and confirmation.
- [ ] Add a local object-URL preview lifecycle without sending or storing extra data.
- [ ] Recompose the photo flow as media stage, state, detected-item editor, and confirmation action while preserving consent/disclosure.
- [ ] Run focused tests and visual checks; commit.

### Task 5: Workout plan and exercises

**Files:** `frontend/src/features/workouts/WorkoutPlanPage.tsx`, `frontend/src/features/workouts/workoutPlan.css`, `frontend/src/features/workouts/WorkoutPlanPage.test.tsx`.

- [ ] Add failing tests that all day rows precede exercise details and the focused day is collapsed by default.
- [ ] Build a real-media next-workout hero plus compact upcoming-day rows.
- [ ] Keep exercise details dense and on-demand; retain alternatives and all metadata.
- [ ] Move review/stale/provenance/settings/history below the schedule and run focused/visual checks; commit.

### Task 6: Catalogue and body intelligence

**Files:** catalogue and body-photo page/components/CSS plus their existing tests.

- [ ] Add failing tests for five-macro catalogue density, visual-first body ordering, and weight chart rendering only with at least two real points.
- [ ] Tighten catalogue rows/dialog without changing member/admin response boundaries.
- [ ] Recompose body analysis around the region map and compact callouts; retain the full report below.
- [ ] Build the truthful progress chart/session fallback using existing adherence and body-session APIs.
- [ ] Run focused tests and visual checks; commit.

### Task 7: More and profile

**Files:** `frontend/src/pages/MorePage.tsx`, `frontend/src/pages/more.css`, `frontend/src/features/profile/ProfilePage.tsx`, `frontend/src/features/profile/profile.css`, existing tests.

- [ ] Add failing tests for compact authorization-aware groups and profile read/edit states.
- [ ] Keep More as dense grouped rows with separated logout.
- [ ] Add a real-data profile summary and explicit edit affordance while preserving the current editor and onboarding behavior.
- [ ] Run focused tests and visual checks; commit.

### Task 8: Final verification and polish

- [ ] Run `npm run lint`, `npm run test`, and `npm run build` from `frontend/`.
- [ ] Render Dashboard, Workout, Nutrition, Photo, Catalogue, Body Analysis, Progress, More, and Profile in Persian and English.
- [ ] Inspect 360, 390, 430, 768, and desktop screenshots for density, hierarchy, safe areas, and overflow against `Panel.png`.
- [ ] Fix every visual regression, re-run the full gate, remove QA fixtures, commit, and push `nutrition`.
