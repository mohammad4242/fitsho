# Authenticated Home Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild only the authenticated Home page as a compact premium dashboard while preserving real data and behavior.

**Architecture:** Keep all orchestration and product-mode logic in `DashboardPage`. Add presentation-only quick actions within the page and use existing product assets and shared primitives. Limit styling to `dashboard.css` so unrelated routes remain unchanged.

**Tech Stack:** React 19, TypeScript, React Router, i18next, CSS, Vitest, Testing Library

## Global Constraints

- Redesign only the authenticated Home page.
- Preserve real workout, nutrition, auth, route, permission, product-mode, i18n, and bottom-navigation behavior.
- Do not render reference files or introduce sample values.
- Use `/body-progress` for body analysis and `/nutrition-tracking` for food-photo estimation.

---

### Task 1: Dashboard behavior contract

**Files:**
- Modify: `frontend/src/pages/DashboardPage.test.tsx`
- Modify: `frontend/src/App.test.tsx`

**Interfaces:**
- Consumes: `DashboardPage` and existing API mocks.
- Produces: assertions for section order, calorie ring, minimal quick actions, and route targets.

- [ ] **Step 1: Write failing tests**

Add assertions that workout precedes nutrition, nutrition precedes quick actions, the ring is always present when a calorie target exists, and both quick cards expose only their exact title and correct destination.

- [ ] **Step 2: Verify RED**

Run: `npm run test -- src/pages/DashboardPage.test.tsx`

Expected: failures for missing quick actions and missing ring without tracked calories.

### Task 2: Home composition and styling

**Files:**
- Modify: `frontend/src/pages/DashboardPage.tsx`
- Modify: `frontend/src/pages/dashboard.css`
- Test: `frontend/src/pages/DashboardPage.test.tsx`

**Interfaces:**
- Consumes: `WorkoutPlan`, nutrition responses, `ExerciseMedia`, `ProgressRing`, current profile and product mode.
- Produces: greeting, workout hero, nutrition summary, and `DashboardQuickAction` links.

- [ ] **Step 1: Implement minimal markup**

Retain effects and derived real data. Replace only the page composition, add the avatar initial, keep the workout CTA, render the nutrition ring against zero when no actual intake exists, and add capability-aware quick links.

- [ ] **Step 2: Implement responsive presentation**

Use page-scoped CSS for the compact dark-petrol hierarchy, workout media crop, calorie ring composition, two equal scan shortcuts, logical RTL properties, mobile breakpoints, focus, press, reduced-motion, and overflow safety.

- [ ] **Step 3: Verify GREEN**

Run: `npm run test -- src/pages/DashboardPage.test.tsx`

Expected: all dashboard tests pass.

### Task 3: Visual and repository verification

**Files:**
- Verify: `frontend/src/pages/DashboardPage.tsx`
- Verify: `frontend/src/pages/dashboard.css`

**Interfaces:**
- Consumes: built frontend and authenticated local runtime.
- Produces: responsive screenshots and executed checks.

- [ ] **Step 1: Run automated checks**

Run `npm run lint`, `npm run test`, and `npm run build` from `frontend/`.

- [ ] **Step 2: Run visual checks**

Inspect Persian Home at 360px, 390px, 430px, tablet, and desktop. Confirm no horizontal overflow, bottom-nav clearance, RTL, workout/nutrition/body/food links, and visual alignment with the references.

- [ ] **Step 3: Commit and push**

Stage only the two dashboard files, dashboard test, and these planning documents. Commit with `feat(home): redesign authenticated dashboard` and push `nutrition` without force.

- [ ] **Step 4: Start the app**

Start the existing development stack in a persistent terminal session and report the verified URL for user testing.
