# Full-page Member Backgrounds Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Render the supplied Fitsho media behind the whole authenticated viewport instead of inside header cards.

**Architecture:** `MemberHeaderMedia` stays the single decorative media component. Each route shell renders it first with `member-page-background`; CSS makes that layer fixed and raises navigation and content above it. Today and workout plan supply video plus a still fallback; the other member routes supply only a still.

**Tech Stack:** React, TypeScript, Vite, CSS, Vitest, Testing Library.

## Global Constraints

- Do not modify backend, database, API, routes, user data, or exercise demonstration media.
- Today uses `hero-strength.mp4` and `hero-strength-fallback.jpg`; workout plan uses `plan-focus.mp4` and `plan-focus-fallback.jpg`.
- Catalog/detail use `hero-strength-fallback.jpg`; profile/onboarding use `auth-training-accent.jpg`; admin list/new/edit use `app-training-accent.jpg`.
- Background video is muted, plays only while visible, and uses the still for reduced motion or playback failure.
- Background media is decorative. Existing forms, controls, and text remain readable above the dark veil.

---

### Task 1: Add fixed page-background behavior to the shared media layer

**Files:**
- Modify: `frontend/src/shared/MemberHeaderMedia.test.tsx`, `frontend/src/index.css`

**Interfaces:**
- Existing `MemberHeaderMedia({ imageSrc, videoSrc?, className? })` API remains unchanged.
- `className="member-page-background"` creates the fixed viewport layer for all route shells.

- [ ] **Step 1: Write the failing behavior test**

```tsx
import "../index.css";

it("fixes a full-page background layer to the viewport", () => {
  render(<MemberHeaderMedia imageSrc="/still.jpg" className="member-page-background" />);

  expect(getComputedStyle(screen.getByTestId("member-header-image").parentElement!).position)
    .toBe("fixed");
});
```

- [ ] **Step 2: Verify RED**

Run: `cd frontend && npm test -- --run src/shared/MemberHeaderMedia.test.tsx`

Expected: FAIL because the full-page class has no fixed positioning rule.

- [ ] **Step 3: Add the reusable fixed layer CSS**

```css
.member-page-background {
  position: fixed;
  z-index: 0;
  inset: 0;
  width: 100vw;
  height: 100svh;
}

.member-page-background .member-header-media__asset { object-fit: cover; }
```

Keep the existing media veil as the single readability overlay.

- [ ] **Step 4: Verify GREEN**

Run: `cd frontend && npm test -- --run src/shared/MemberHeaderMedia.test.tsx && npm run lint`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/shared/MemberHeaderMedia.test.tsx frontend/src/index.css
git commit -m "feat(frontend): support fixed member media backgrounds"
```

### Task 2: Move Today and workout video to the viewport background

**Files:**
- Modify: `frontend/src/pages/DashboardPage.tsx`, `frontend/src/pages/dashboard.css`, `frontend/src/pages/DashboardPage.test.tsx`
- Modify: `frontend/src/features/workouts/WorkoutPlanPage.tsx`, `frontend/src/features/workouts/workoutPlan.css`, `frontend/src/features/workouts/WorkoutPlanPage.test.tsx`

**Interfaces:**
- Today uses `MemberHeaderMedia` directly inside `.today-shell` with `heroStrengthVideo`, `heroStrengthFallback`, and `member-page-background`.
- Workout plan uses the equivalent root layer with `planFocusVideo` and `planFocusFallback`.

- [ ] **Step 1: Write the failing video-background tests**

```tsx
const background = await screen.findByTestId("member-header-video");
expect(background).toHaveAttribute("poster", expect.stringContaining("hero-strength-fallback"));
expect(background.parentElement).toHaveClass("member-page-background");
```

Use `plan-focus-fallback` for the workout assertion.

- [ ] **Step 2: Verify RED**

Run: `cd frontend && npm test -- --run src/pages/DashboardPage.test.tsx src/features/workouts/WorkoutPlanPage.test.tsx`

Expected: FAIL because the current components are nested inside header cards and Today has no background video.

- [ ] **Step 3: Render the two root video layers**

```tsx
<main className="today-shell">
  <MemberHeaderMedia
    imageSrc={heroStrengthFallback}
    videoSrc={heroStrengthVideo}
    className="member-page-background"
  />
  <AuthenticatedHeader />
  <section className="today-hero" aria-labelledby="today-title" />
</main>
```

Apply the same sibling order in `.workout-plan-shell`, then remove the old media children from `.today-hero` and `.workout-plan-hero`.

- [ ] **Step 4: Raise the existing content and make hero cards translucent**

```css
.today-shell > :not(.member-page-background),
.workout-plan-shell > :not(.member-page-background) {
  position: relative;
  z-index: 1;
}

.today-hero, .workout-plan-hero { background: rgb(10 31 30 / 22%); }
```

Remove obsolete image-positioning rules while preserving existing controls, mobile breakpoints, and exercise-card media styles.

- [ ] **Step 5: Verify GREEN**

Run: `cd frontend && npm test -- --run src/pages/DashboardPage.test.tsx src/features/workouts/WorkoutPlanPage.test.tsx && npm run lint`

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/pages/DashboardPage.tsx frontend/src/pages/dashboard.css frontend/src/pages/DashboardPage.test.tsx frontend/src/features/workouts/WorkoutPlanPage.tsx frontend/src/features/workouts/workoutPlan.css frontend/src/features/workouts/WorkoutPlanPage.test.tsx
git commit -m "feat(frontend): use full page workout media"
```

### Task 3: Move static member media to page roots

**Files:**
- Modify: `frontend/src/features/exercises/ExerciseCatalogPage.tsx`, `frontend/src/features/exercises/ExerciseDetailPage.tsx`, `frontend/src/features/exercises/exercises.css`, `frontend/src/features/exercises/ExerciseCatalogPage.test.tsx`, `frontend/src/features/exercises/ExerciseDetailPage.test.tsx`
- Modify: `frontend/src/features/profile/ProfilePage.tsx`, `frontend/src/features/profile/profile.css`, `frontend/src/features/profile/ProfilePage.test.tsx`
- Modify: `frontend/src/features/admin/AdminExercisesPage.tsx`, `frontend/src/features/admin/AdminExerciseNewPage.tsx`, `frontend/src/features/admin/AdminExerciseEditPage.tsx`, `frontend/src/features/admin/admin.css`, `frontend/src/features/admin/AdminExercisesPage.test.tsx`

**Interfaces:**
- Each listed shell contains exactly one root `MemberHeaderMedia` with `className="member-page-background"`.
- Header cards no longer contain a media component.

- [ ] **Step 1: Write the failing static-background assertions**

```tsx
const background = await screen.findByTestId("member-header-image");
expect(background).toHaveAttribute("src", expect.stringContaining("hero-strength-fallback"));
expect(background.parentElement).toHaveClass("member-page-background");
```

Use `auth-training-accent` in the profile test and `app-training-accent` in the admin-list test.

- [ ] **Step 2: Verify RED**

Run: `cd frontend && npm test -- --run src/features/exercises/ExerciseCatalogPage.test.tsx src/features/exercises/ExerciseDetailPage.test.tsx src/features/profile/ProfilePage.test.tsx src/features/admin/AdminExercisesPage.test.tsx`

Expected: FAIL because the current static media remains in the header cards.

- [ ] **Step 3: Render static media first in every route shell**

```tsx
<MemberHeaderMedia
  imageSrc={heroStrengthFallback}
  className="member-page-background"
/>
```

Apply this same pattern to exercise detail, profile, admin list, admin new, and admin edit. Do not change onboarding: its existing `AuthShell` already uses `auth-training-accent.jpg` as the registration-transition background.

- [ ] **Step 4: Stack route content above the photo and remove obsolete hero media**

```css
.exercise-catalog-shell > :not(.member-page-background),
.profile-page-shell > :not(.member-page-background),
.admin-page > :not(.member-page-background) {
  position: relative;
  z-index: 1;
}
```

Use translucent dark header surfaces, remove `.exercise-detail-hero`, and keep form inputs, fieldsets, and exercise media panels opaque.

- [ ] **Step 5: Verify GREEN**

Run: `cd frontend && npm test -- --run src/features/exercises/ExerciseCatalogPage.test.tsx src/features/exercises/ExerciseDetailPage.test.tsx src/features/profile/ProfilePage.test.tsx src/features/admin/AdminExercisesPage.test.tsx src/features/profile/OnboardingPage.test.tsx src/features/admin/AdminExerciseNewPage.test.tsx src/features/admin/AdminExerciseEditPage.test.tsx && npm run lint`

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/features/exercises frontend/src/features/profile frontend/src/features/admin
git commit -m "feat(frontend): use full page static media"
```

### Task 4: Verify the complete frontend and local preview

**Files:** No production source files expected.

- [ ] **Step 1: Run the complete checks**

```bash
cd frontend
npm run lint
npm test -- --run
npm run build
```

Expected: lint has no errors, all tests pass, and the production build completes.

- [ ] **Step 2: Check the preview and worktree**

```bash
curl -fsS -o /dev/null -w '5174=%{http_code}\n' http://127.0.0.1:5174/
git diff --check
git status --short --branch
```

Expected: `5174=200`, no whitespace errors, and only intentional branch commits.
