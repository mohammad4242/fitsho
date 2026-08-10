# Mobile Layout Stability Implementation Plan

## Goal

Remove the structural mobile overflow shown in the supplied screenshots while preserving the current visual design, routes, product capabilities, and desktop behavior.

## Step 1: Lock mobile navigation behavior with tests

Files:

- `frontend/src/shared/AppShell.test.tsx`
- `frontend/src/shared/AppShell.tsx`

Work:

1. Add failing tests for `both`, `training`, and `nutrition` product modes.
2. For `both`, assert four direct destinations plus an accessible More button.
3. Assert Food catalogue and Profile are hidden until More opens, then become links.
4. Assert modes with four or fewer destinations use direct links without More.
5. Implement capability-aware primary and overflow destination grouping.
6. Close More after selecting a destination and expose `aria-expanded` and `aria-controls`.

Check:

```bash
cd frontend
npm run test -- --run src/shared/AppShell.test.tsx
```

Commit:

```text
fix(mobile-navigation): keep member tabs in one row
```

## Step 2: Stabilize shared mobile layout

Files:

- `frontend/src/index.css`
- `frontend/src/shared/AppShell.test.tsx`

Work:

1. Constrain the document, root, app shell, and direct content to the viewport width.
2. Add `min-width: 0` at shared layout boundaries and prevent horizontal document scrolling.
3. Change mobile bottom navigation to a single five-control row.
4. Add the compact More popover above the fixed navigation.
5. Reserve one navigation-row height plus safe-area inset below page content.
6. Hide desktop authenticated navigation globally at the mobile breakpoint.
7. Keep the brand and account-menu button visible and keep the menu inside the viewport.
8. Cover the mobile visual viewport with fixed member media using `100dvh` plus the existing fallback.

Check:

```bash
cd frontend
npm run test -- --run src/shared/AppShell.test.tsx src/shared/MemberHeaderMedia.test.tsx
npm run lint
```

Commit:

```text
fix(mobile-layout): constrain shared member surfaces
```

## Step 3: Remove page-level overflow

Files:

- `frontend/src/pages/dashboard.css`
- `frontend/src/features/workouts/workoutPlan.css`

Work:

1. Remove redundant Today-only mobile-header behavior now handled by shared CSS.
2. Keep Today hero, story chapters, and action cards within the available width.
3. Make workout hero, guidance, generation-method choices, empty state, schedule, and tools fluid on narrow screens.
4. Allow long Persian headings and labels to wrap without forcing document width.
5. Preserve current colors, typography, video assignments, and desktop layout.

Check:

```bash
cd frontend
npm run test -- --run src/pages/DashboardPage.test.tsx src/features/workouts/WorkoutPlanPage.test.tsx
npm run lint
```

Commit:

```text
fix(mobile-layout): contain dashboard and workout cards
```

## Step 4: Full verification

Files:

- No planned source changes

Work:

1. Run the complete frontend suite and production build.
2. Start the current frontend/backend runtime without changing ports or environment files.
3. Verify authenticated Today and Workout Plan at 360 px and 412 px widths.
4. Confirm no horizontal scrolling, full-viewport background media, one-row bottom navigation, usable More links, and unobscured final controls.
5. Confirm desktop navigation and layout remain intact.

Check:

```bash
cd frontend
npm run test -- --run
npm run lint
npm run build
```

Completion criteria:

- `document.documentElement.scrollWidth === document.documentElement.clientWidth` at both mobile widths.
- Bottom navigation remains one row.
- The fixed media covers the visible page width and dynamic viewport height.
- Today and Workout Plan content stays readable and tappable above the navigation.
- Existing unrelated workspace changes remain unstaged.
