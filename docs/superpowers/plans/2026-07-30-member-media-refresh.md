# Member Media Refresh Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace low-quality authenticated-page backgrounds with the supplied Fitsho media without changing user flows or APIs.

**Architecture:** A small reusable media-header component owns video visibility, reduced-motion fallback, and decorative image semantics. Each member page imports a designated asset and renders the shared component only in its header layer; page content stays above the overlay.

**Tech Stack:** React, TypeScript, Vite, CSS, Vitest, Testing Library.

## Global Constraints

- Do not modify backend, database, APIs, routes, or exercise media behavior.
- Use only the media already tracked under `frontend/src/assets/landing/`.
- Video is muted, non-looping only when visible, and replaced with a still for reduced motion or playback failure.
- Text, controls, and forms remain readable above a dark overlay.

---

### Task 1: Add an accessible reusable member-header media layer

**Files:**
- Create: `frontend/src/shared/MemberHeaderMedia.tsx`, `frontend/src/shared/MemberHeaderMedia.test.tsx`
- Modify: `frontend/src/index.css`

**Interfaces:**
- `MemberHeaderMedia({ imageSrc, videoSrc?, className? })` renders a decorative image or muted video background.
- Member pages use the component without owning playback state.

- [ ] **Step 1: Write failing fallback tests**

```tsx
it("uses the still image when reduced motion is requested", () => {
  render(<MemberHeaderMedia imageSrc="/still.jpg" videoSrc="/motion.mp4" />);
  expect(screen.getByTestId("member-header-image")).toHaveAttribute("src", "/still.jpg");
});

it("shows the video only after it becomes visible", async () => {
  render(<MemberHeaderMedia imageSrc="/still.jpg" videoSrc="/motion.mp4" />);
  expect(await screen.findByTestId("member-header-video")).toHaveAttribute("muted");
});
```

- [ ] **Step 2: Verify RED**

Run: `cd frontend && npm test -- --run src/shared/MemberHeaderMedia.test.tsx`

Expected: FAIL because the component does not exist.

- [ ] **Step 3: Implement the component and shared CSS**

```tsx
export function MemberHeaderMedia({ imageSrc, videoSrc, className }: MemberHeaderMediaProps) {
  // Observe its own container. Render the image for reduced motion or a video error.
  // Render <video muted playsInline preload="metadata"> only when videoSrc is supplied.
}
```

Add `.member-header-media`, `.member-header-media__veil`, and content stacking rules to `index.css`.

- [ ] **Step 4: Verify GREEN**

Run: `cd frontend && npm test -- --run src/shared/MemberHeaderMedia.test.tsx && npm run lint`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/shared/MemberHeaderMedia.tsx frontend/src/shared/MemberHeaderMedia.test.tsx frontend/src/index.css
git commit -m "feat(frontend): add member header media layer"
```

### Task 2: Refresh Today and workout-plan headers

**Files:**
- Modify: `frontend/src/pages/DashboardPage.tsx`, `frontend/src/pages/dashboard.css`
- Modify: `frontend/src/features/workouts/WorkoutPlanPage.tsx`, `frontend/src/features/workouts/workoutPlan.css`
- Test: `frontend/src/pages/DashboardPage.test.tsx`, `frontend/src/features/workouts/WorkoutPlanPage.test.tsx`

**Interfaces:**
- Today uses the supplied stills for hero and story chapters.
- Workout plan passes `plan-focus.mp4` and `plan-focus-fallback.jpg` to `MemberHeaderMedia`.

- [ ] **Step 1: Write failing page tests**

```tsx
expect(screen.getByTestId("member-header-video")).toBeInTheDocument();
expect(screen.getByTestId("member-header-image")).toHaveAttribute(
  "src", expect.stringContaining("progress-drive-fallback"),
);
```

- [ ] **Step 2: Verify RED**

Run: `cd frontend && npm test -- --run src/pages/DashboardPage.test.tsx src/features/workouts/WorkoutPlanPage.test.tsx`

Expected: FAIL because the old hero assets and non-media workout header remain.

- [ ] **Step 3: Use the assigned assets and preserve content layout**

- Replace `brand/hero-*` imports on Today with the assigned supplied stills.
- Add `MemberHeaderMedia` as the first child of the workout-plan hero and put text/duration above it.
- Add page-scoped crop and overlay CSS; do not alter exercise-card media.

- [ ] **Step 4: Verify GREEN**

Run: `cd frontend && npm test -- --run src/pages/DashboardPage.test.tsx src/features/workouts/WorkoutPlanPage.test.tsx`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/DashboardPage.tsx frontend/src/pages/dashboard.css frontend/src/features/workouts/WorkoutPlanPage.tsx frontend/src/features/workouts/workoutPlan.css frontend/src/pages/DashboardPage.test.tsx frontend/src/features/workouts/WorkoutPlanPage.test.tsx
git commit -m "feat(frontend): refresh today and workout media"
```

### Task 3: Add image headers to catalog, profile, onboarding, and admin

**Files:**
- Modify: `frontend/src/features/exercises/ExerciseCatalogPage.tsx`, `frontend/src/features/exercises/ExerciseDetailPage.tsx`, `frontend/src/features/exercises/exercises.css`
- Modify: `frontend/src/features/profile/ProfilePage.tsx`, `frontend/src/features/profile/OnboardingPage.tsx`, `frontend/src/features/profile/profile.css`
- Modify: `frontend/src/features/admin/AdminExercisesPage.tsx`, `frontend/src/features/admin/AdminExerciseNewPage.tsx`, `frontend/src/features/admin/AdminExerciseEditPage.tsx`, `frontend/src/features/admin/admin.css`
- Test: `frontend/src/features/exercises/ExerciseCatalogPage.test.tsx`, `frontend/src/features/exercises/ExerciseDetailPage.test.tsx`, `frontend/src/features/profile/ProfilePage.test.tsx`, `frontend/src/features/admin/AdminExercisesPage.test.tsx`

**Interfaces:**
- Static image headers use `MemberHeaderMedia` with `imageSrc` only.
- Forms remain outside the image layer and retain their existing labels and controls.

- [ ] **Step 1: Write failing rendering tests**

```tsx
expect(await screen.findByTestId("member-header-image")).toHaveAttribute(
  "src", expect.stringContaining("auth-training-accent"),
);
```

- [ ] **Step 2: Verify RED**

Run: `cd frontend && npm test -- --run src/features/exercises/ExerciseCatalogPage.test.tsx src/features/exercises/ExerciseDetailPage.test.tsx src/features/profile/ProfilePage.test.tsx src/features/admin/AdminExercisesPage.test.tsx`

Expected: FAIL because the member pages have no shared media header.

- [ ] **Step 3: Render static media headers**

- Catalog/detail: `hero-strength-fallback.jpg`.
- Profile/onboarding: `auth-training-accent.jpg`.
- Admin list/new/edit: `app-training-accent.jpg`.
- Add only page-scoped CSS that stacks content above the overlay and responds at 680px.

- [ ] **Step 4: Verify GREEN**

Run: `cd frontend && npm test -- --run src/features/exercises/ExerciseCatalogPage.test.tsx src/features/exercises/ExerciseDetailPage.test.tsx src/features/profile/ProfilePage.test.tsx src/features/admin/AdminExercisesPage.test.tsx`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/features/exercises frontend/src/features/profile frontend/src/features/admin
git commit -m "feat(frontend): add media to member page headers"
```

### Task 4: Run full frontend verification

**Files:** No production source files expected.

- [ ] **Step 1: Run complete checks**

```bash
cd frontend
npm run lint
npm test -- --run
npm run build
```

Expected: lint has no errors, all tests pass, and Vite production build completes.

- [ ] **Step 2: Commit verification-only design correction if required**

```bash
git diff --check
git status --short
```

Expected: no uncommitted source changes other than intentional verification corrections.
