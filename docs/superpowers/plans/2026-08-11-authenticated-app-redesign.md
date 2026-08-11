# Authenticated App Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver a cohesive premium dark-mode member experience without changing Fitsho backend contracts or product behavior.

**Architecture:** Keep feature data and actions inside their existing pages. Make `AppShell` the single member-level header and capability-aware navigation owner, add a focused More destination, and extend the current CSS token/primitives system for consistent responsive presentation.

**Tech Stack:** React 19, TypeScript 6, React Router 7, i18next, CSS, Vitest, Testing Library, Vite.

## Global Constraints

- Branch is `nutrition`; preserve all unrelated working-tree changes.
- Do not change backend APIs, database schema, authentication, roles, product modes, or business logic.
- Do not create fake metrics, unsupported features, medical claims, or member-visible catalogue prices.
- Keep Persian RTL and English LTR complete and accessible.
- Verify 360, 390, 430, tablet, and desktop layouts with no horizontal overflow.
- Use existing local fonts and dependencies; add no package.

---

## File Map

- `frontend/src/shared/AppShell.tsx`: member shell, shared header, and capability-aware navigation.
- `frontend/src/shared/AuthenticatedHeader.tsx`: compact utility header and existing role-aware access.
- `frontend/src/pages/MorePage.tsx`: account, product, professional, admin, language, and logout hub.
- `frontend/src/styles/tokens.css`: dark palette, spacing, radius, shadow, and content tokens.
- `frontend/src/styles/primitives.css`: shared cards, buttons, inputs, badges, statuses, metrics, rows.
- Existing feature CSS files: feature-specific responsive composition.
- Existing page components: hierarchy-only markup changes around current data and actions.

### Task 1: Unified authenticated shell and navigation

**Files:**
- Modify: `frontend/src/shared/AppShell.test.tsx`
- Modify: `frontend/src/shared/AppShell.tsx`
- Modify: `frontend/src/shared/AuthenticatedHeader.tsx`
- Modify: `frontend/src/shared/authenticatedHeader.css`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/index.css`
- Create: `frontend/src/pages/MorePage.tsx`
- Create: `frontend/src/pages/more.css`
- Create: `frontend/src/pages/MorePage.test.tsx`

**Interfaces:**
- Consumes: `useOptionalProfile()`, `useAuth()`, existing role verification calls, `LanguageSwitcher`.
- Produces: `/more`, capability-aware primary navigation, and one shared member header.

- [ ] **Step 1: Add failing shell navigation tests**

```tsx
expect(screen.getByRole("link", { name: "امروز" })).toHaveAttribute("href", "/dashboard");
expect(screen.getByRole("link", { name: "برنامه" })).toHaveAttribute("href", "/workout-plan");
expect(screen.getByRole("link", { name: "تغذیه" })).toHaveAttribute("href", "/nutrition-estimate");
expect(screen.getByRole("link", { name: "پیشرفت" })).toHaveAttribute("href", "/body-progress");
expect(screen.getByRole("link", { name: "بیشتر" })).toHaveAttribute("href", "/more");
```

- [ ] **Step 2: Run the focused test and confirm the missing direct More route fails**

Run: `npm run test -- src/shared/AppShell.test.tsx`

- [ ] **Step 3: Implement the shared header, direct navigation, route, and More page**

Use `productMode` to omit unsupported Workout, Nutrition, or Progress items. Keep More visible in every mode. Move the member `AuthenticatedHeader` into `AppShell`; leave admin/professional routes outside the shell unchanged.

- [ ] **Step 4: Add and pass More-page role and logout tests**

Run: `npm run test -- src/shared/AppShell.test.tsx src/pages/MorePage.test.tsx`

- [ ] **Step 5: Commit and push**

```bash
git commit -m "feat(authenticated-shell): unify capability-aware member navigation"
git push origin nutrition
```

### Task 2: Shared visual foundation and dashboard

**Files:**
- Modify: `frontend/src/styles/designSystem.test.ts`
- Modify: `frontend/src/styles/tokens.css`
- Modify: `frontend/src/styles/primitives.css`
- Modify: `frontend/src/pages/DashboardPage.test.tsx`
- Modify: `frontend/src/pages/DashboardPage.tsx`
- Modify: `frontend/src/pages/dashboard.css`

**Interfaces:**
- Consumes: existing workout-plan state, weekly-nutrition state, profile, and product mode.
- Produces: shared metric/card/row styles and a capability-aware Today hierarchy.

- [ ] **Step 1: Add failing token and dashboard hierarchy tests**

```ts
expect(tokens).toContain("--fitsho-surface-interactive");
expect(tokens).toContain("--fitsho-shadow-focus");
```

```tsx
expect(screen.getByRole("heading", { name: /امروز/ })).toBeInTheDocument();
expect(screen.getByRole("navigation", { name: /اقدام/ })).toBeInTheDocument();
```

- [ ] **Step 2: Run focused tests and confirm the new tokens/hierarchy are absent**

Run: `npm run test -- src/styles/designSystem.test.ts src/pages/DashboardPage.test.tsx`

- [ ] **Step 3: Extend tokens/primitives and reshape the dashboard around its existing state**

Keep the primary capability dominant, preserve loading/error/empty states, and never render numeric nutrition or recovery values that are not returned by current dashboard requests.

- [ ] **Step 4: Run focused tests and commit**

Run: `npm run test -- src/styles/designSystem.test.ts src/pages/DashboardPage.test.tsx`

```bash
git commit -m "feat(dashboard): strengthen authenticated daily overview hierarchy"
git push origin nutrition
```

### Task 3: Workout, nutrition, and food catalogue surfaces

**Files:**
- Modify: `frontend/src/features/workouts/WorkoutPlanPage.test.tsx`
- Modify: `frontend/src/features/workouts/WorkoutPlanPage.tsx`
- Modify: `frontend/src/features/workouts/workoutPlan.css`
- Modify: `frontend/src/features/nutrition/NutritionEstimatePage.test.tsx`
- Modify: `frontend/src/features/nutrition/NutritionEstimatePage.tsx`
- Modify: `frontend/src/features/nutrition/nutritionEstimate.css`
- Modify: `frontend/src/features/nutrition/FoodCataloguePage.test.tsx`
- Modify: `frontend/src/features/nutrition/FoodCataloguePage.tsx`
- Modify: `frontend/src/features/nutrition/foodCatalogue.css`

**Interfaces:**
- Consumes: existing workout plans, generation controls, nutrition estimates, weekly plans, catalogue filters, portions, sources, and admin-only price data.
- Produces: responsive week/day hierarchy, macro-first targets, and compact trustworthy catalogue results.

- [ ] **Step 1: Add failing semantic tests for week summary, nutrition actions, and catalogue results**

```tsx
expect(screen.getByRole("region", { name: /خلاصه برنامه/ })).toBeInTheDocument();
expect(screen.getByRole("navigation", { name: /ابزارهای تغذیه/ })).toBeInTheDocument();
expect(screen.getByRole("list", { name: /مواد غذایی/ })).toBeInTheDocument();
```

- [ ] **Step 2: Run focused tests and confirm the new regions fail**

Run: `npm run test -- src/features/workouts/WorkoutPlanPage.test.tsx src/features/nutrition/NutritionEstimatePage.test.tsx src/features/nutrition/FoodCataloguePage.test.tsx`

- [ ] **Step 3: Add semantic wrappers and responsive styles without altering data operations**

Preserve every mutation, error state, historical version, physician state, portion calculation, provenance link, pagination rule, and member/admin field boundary.

- [ ] **Step 4: Run all focused feature tests and commit**

Run: `npm run test -- src/features/workouts src/features/nutrition`

```bash
git commit -m "feat(member-areas): polish workout nutrition and catalogue workflows"
git push origin nutrition
```

### Task 4: Body analysis, progress, More, and profile polish

**Files:**
- Modify: `frontend/src/features/bodyPhotos/BodyProgressPage.test.tsx`
- Modify: `frontend/src/features/bodyPhotos/BodyProgressPage.tsx`
- Modify: `frontend/src/features/bodyPhotos/BodyAnalysisResultPage.test.tsx`
- Modify: `frontend/src/features/bodyPhotos/BodyAnalysisResultPage.tsx`
- Modify: `frontend/src/features/bodyPhotos/bodyPhotos.css`
- Modify: `frontend/src/features/profile/ProfilePage.test.tsx`
- Modify: `frontend/src/features/profile/ProfilePage.tsx`
- Modify: `frontend/src/features/profile/profile.css`
- Modify: `frontend/src/pages/MorePage.tsx`
- Modify: `frontend/src/pages/more.css`

**Interfaces:**
- Consumes: stored photo sessions, analyses, comparisons, specialist reviews, profile fields, and role destinations.
- Produces: body-map-led analysis, clearer real progress history, grouped account/profile surfaces.

- [ ] **Step 1: Add failing landmarks for session history and grouped profile content**

```tsx
expect(screen.getByRole("list", { name: /تاریخچه/ })).toBeInTheDocument();
expect(screen.getByRole("region", { name: /اطلاعات شخصی/ })).toBeInTheDocument();
```

- [ ] **Step 2: Run focused tests and confirm the landmarks fail**

Run: `npm run test -- src/features/bodyPhotos/BodyProgressPage.test.tsx src/features/profile/ProfilePage.test.tsx`

- [ ] **Step 3: Implement visual grouping while preserving all current forms and provider states**

Keep optional-analysis copy, confidence limits, validation issues, previous/current comparison, medical disclaimers, and profile save behavior unchanged.

- [ ] **Step 4: Run body/profile tests and commit**

Run: `npm run test -- src/features/bodyPhotos src/features/profile`

```bash
git commit -m "feat(progress-profile): refine body insights and account organization"
git push origin nutrition
```

### Task 5: Responsive and final verification pass

**Files:**
- Modify: only files with a reproduced responsive, localization, or accessibility defect.

**Interfaces:**
- Consumes: the completed member experience.
- Produces: verified mobile, desktop, RTL, LTR, navigation, tests, lint, and production bundle.

- [ ] **Step 1: Run full automated verification**

```bash
npm run test
npm run lint
npm run build
git diff --check
```

- [ ] **Step 2: Start the real frontend and backend-compatible runtime**

Use the repository's configured Vite proxy and active backend port. Do not alter `.env` or commit runtime data.

- [ ] **Step 3: Inspect Persian and English authenticated routes**

Check dashboard, workout, nutrition, food catalogue, body analysis/progress, More, and profile at 360, 390, 430, 768, and desktop widths. Verify capability navigation and no horizontal overflow.

- [ ] **Step 4: Reproduce any defect with a failing test before fixing it**

Run the focused regression test red, implement the minimal fix, then rerun it green.

- [ ] **Step 5: Rerun full verification, commit, and push**

```bash
git commit -m "fix(authenticated-app): complete responsive accessibility polish"
git push origin nutrition
```
