# Fitician Mobile Visual Parity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the current Fitician native UI into a compact, cinematic, media-first mobile expression of the existing web product.

**Architecture:** Existing screens retain query, mutation, cache, routing, and domain ownership. New focused presentation primitives provide the shared visual language, then each feature adopts them without changing business behavior.

**Tech Stack:** Expo SDK 57, React Native 0.86, Expo Router, TypeScript, Vitest, Jest, `react-native-svg`, existing MaterialCommunityIcons.

**Spec:** `docs/superpowers/specs/2026-09-09-mobile-visual-parity-design.md`

## Global Constraints

- Preserve canvas `#020607`, aqua `#50dfce`, ink `#e8f4f1`, Vazirmatn, Lalezar, and Sora.
- Add only `react-native-svg` as a direct UI dependency and install it through Expo's version resolver.
- Do not change backend behavior, API contracts, persisted models, auth security, workout/nutrition/body-analysis algorithms, or capability routing.
- Preserve offline/stale states, query caching, workout history/PDF/replacement/cycle behavior, specialist approval, and onboarding drafts.
- Bundle no promotional video; add only one optimized existing web poster.
- Preserve unrelated worktree changes and stage only explicit task files.
- Phone acceptance widths are 360, 390, and 430 px with 48 dp minimum targets.

---

### Task 1: Shared cinematic visual primitives

**Files:**
- Modify: `mobile/package.json`
- Modify: `package-lock.json`
- Modify: `mobile/ui/tokens.ts`
- Modify: `mobile/ui/icons.ts`
- Modify: `mobile/ui/components/index.ts`
- Create: `mobile/ui/components/CinematicSurface.tsx`
- Create: `mobile/ui/components/MetricRing.tsx`
- Create: `mobile/ui/components/MetricStrip.tsx`
- Create: `mobile/ui/components/ScreenHeader.tsx`
- Create: `mobile/ui/components/StateSkeleton.tsx`
- Test: `mobile/ui/visualPrimitives.test.ts`

**Interfaces:**
- Produces: `CinematicSurface`, `MetricRing`, `MetricStrip`, `ScreenHeader`, and `StateSkeleton` exports.
- Produces: semantic media, overlay, divider, and atmospheric color tokens used by later tasks.

- [ ] **Step 1: Write failing primitive contract tests**

```ts
expect(await read("components/MetricRing.tsx")).toMatch(/Circle/);
expect(await read("components/StateSkeleton.tsx")).not.toMatch(/progress=\{0\.[0-9]+\}/);
expect(await read("components/index.ts")).toMatch(/MetricRing/);
```

- [ ] **Step 2: Run the focused test and confirm RED**

Run: `npm test -- ui/visualPrimitives.test.ts`
Expected: FAIL because the new modules do not exist.

- [ ] **Step 3: Install SVG and implement primitives**

Run: `npx expo install react-native-svg`

Implement `MetricRing` with two SVG circles, clamped progress, accessible percentage, and a rotated aqua stroke. Implement the remaining primitives as focused StyleSheet-based components using only token values and layered Views.

- [ ] **Step 4: Verify Task 1**

Run: `npm test -- ui/visualPrimitives.test.ts ui/tokens.test.ts ui/icons.test.ts`
Run: `npm run typecheck`
Run: `../frontend/node_modules/.bin/oxlint ui/tokens.ts ui/icons.ts ui/components/*.tsx ui/visualPrimitives.test.ts`
Expected: all commands exit 0.

- [ ] **Step 5: Commit and push**

```bash
git add -- package-lock.json mobile/package.json mobile/ui/tokens.ts mobile/ui/icons.ts mobile/ui/components mobile/ui/visualPrimitives.test.ts
git commit -m "feat(mobile): add cinematic visual primitives"
git push origin main
```

### Task 2: Compact media-first Home

**Files:**
- Modify: `mobile/home/MemberHomeScreen.tsx`
- Modify: `mobile/home/WorkoutTodayCard.tsx`
- Modify: `mobile/home/NutritionSummaryCard.tsx`
- Modify: `mobile/home/QuickActionCard.tsx`
- Modify: `mobile/home/homeModel.test.ts`
- Create: `mobile/home/homePresentation.nativeContract.test.ts`

**Interfaces:**
- Consumes: Task 1 visual primitives.
- Preserves: current profile, workout, nutrition plan, estimate, tracking queries and routes.

- [ ] **Step 1: Write failing Home presentation tests**

```ts
expect(source("NutritionSummaryCard.tsx")).toMatch(/MetricRing/);
expect(source("WorkoutTodayCard.tsx")).toMatch(/useWindowDimensions/);
expect(source("QuickActionCard.tsx")).toMatch(/scanLine/);
expect(source("WorkoutTodayCard.tsx")).not.toMatch(/progress=\{0\.36\}/);
```

- [ ] **Step 2: Run the Home tests and confirm RED**

Run: `npm test -- home/homeModel.test.ts home/homePresentation.nativeContract.test.ts`
Expected: FAIL on the missing responsive composition and real ring.

- [ ] **Step 3: Implement the Home composition**

Use a compact `ScreenHeader`, responsive two-zone workout hero, value-driven `MetricRing`, token-only styles, shaped skeletons, and image quick cards with corner markers plus one scan line. Keep one-column fallback below 350 px and retain all data/error/offline logic.

- [ ] **Step 4: Verify Task 2**

Run: `npm test -- home/*.test.ts exercises/exerciseMedia.test.ts ui/navigation.test.ts`
Run: `npm run typecheck`
Run: `../frontend/node_modules/.bin/oxlint home/*.ts home/*.tsx`
Expected: all commands exit 0.

- [ ] **Step 5: Commit and push**

```bash
git add -- mobile/home
git commit -m "feat(mobile): align member home with web dashboard"
git push origin main
```

### Task 3: Responsive media-first Workout

**Files:**
- Modify: `mobile/workouts/WorkoutPlansScreen.tsx`
- Modify: `mobile/workouts/WorkoutCyclePanel.tsx`
- Modify: `mobile/workouts/workoutMedia.nativeContract.test.ts`
- Create: `mobile/workouts/workoutPresentation.nativeContract.test.ts`

**Interfaces:**
- Consumes: `ScreenHeader`, `MetricStrip`, `CinematicSurface`, and shared icons.
- Preserves: generation, pending review, coach approval, history, PDF, replacement, cycle, and cached state logic.

- [ ] **Step 1: Write failing Workout presentation tests**

```ts
expect(source).toMatch(/ScreenHeader/);
expect(source).toMatch(/name="chevronDown"/);
expect(source).not.toMatch(/\{expanded \? "⌃" : "⌄"\}/);
expect(exerciseRowSource).not.toMatch(/label="راهنما"/);
```

- [ ] **Step 2: Run the Workout tests and confirm RED**

Run: `npm test -- workouts/workoutMedia.nativeContract.test.ts workouts/workoutPresentation.nativeContract.test.ts workouts/workoutModel.test.ts`
Expected: FAIL on text glyphs and crowded exercise action.

- [ ] **Step 3: Implement the Workout composition**

Merge title and metrics into a compact hero, make the first day media-dominant, replace glyphs with `AppIcon`, and make each exercise row a full-width press target without the redundant guide button. Keep warnings in a compact grouped rail and leave every state/action handler intact.

- [ ] **Step 4: Verify Task 3**

Run: `npm test -- workouts/*.test.ts exercises/*.test.ts`
Run: `npm run typecheck`
Run: `../frontend/node_modules/.bin/oxlint workouts/*.ts workouts/*.tsx`
Expected: all commands exit 0.

- [ ] **Step 5: Commit and push**

```bash
git add -- mobile/workouts
git commit -m "feat(mobile): refine responsive workout presentation"
git push origin main
```

### Task 4: Cinematic public entry and guided onboarding

**Files:**
- Copy: `frontend/src/assets/landing/hero-strength-fallback.jpg` to `mobile/assets/public-entry-hero.jpg`
- Modify: `mobile/app/(public)/index.tsx`
- Modify: `mobile/onboarding/PublicOnboardingScreen.tsx`
- Modify: `mobile/onboarding/OnboardingScreen.tsx`
- Modify: `mobile/onboarding/onboardingForms.ts`
- Modify: `mobile/onboarding/onboardingPresentation.nativeContract.test.ts`
- Create: `mobile/onboarding/onboardingQuestionFlow.test.ts`

**Interfaces:**
- Consumes: Task 1 primitives and existing secure public draft handoff.
- Produces: UI-local question progress only; controller and persisted draft shapes remain unchanged.

- [ ] **Step 1: Write failing public/onboarding tests**

```ts
expect(publicSource).toMatch(/public-entry-hero\.jpg/);
expect(publicSource).toMatch(/Media/);
expect(onboardingSource).toMatch(/questionIndex/);
expect(onboardingSource).toMatch(/StateSkeleton/);
```

- [ ] **Step 2: Run focused onboarding tests and confirm RED**

Run: `npm test -- onboarding/onboardingPresentation.nativeContract.test.ts onboarding/onboardingQuestionFlow.test.ts onboarding/publicOnboardingDraftStore.test.ts onboarding/publicOnboardingHandoff.test.ts`
Expected: FAIL on missing poster and question flow.

- [ ] **Step 3: Implement entry and question flow**

Add the optimized existing poster with a dark scrim and overlaid CTA hierarchy. Split each large native onboarding stage into local questions or tightly related groups, validate before advancing, persist only through the existing controller, and preserve all current fields and resume behavior.

- [ ] **Step 4: Verify Task 4**

Run: `npm test -- auth/*.test.ts onboarding/*.test.ts ui/navigation.test.ts`
Run: `npm run typecheck`
Run: `../frontend/node_modules/.bin/oxlint app/'(public)'/*.tsx onboarding/*.ts onboarding/*.tsx`
Expected: all commands exit 0.

- [ ] **Step 5: Commit and push**

```bash
git add -- mobile/assets/public-entry-hero.jpg mobile/app/'(public)'/index.tsx mobile/onboarding
git commit -m "feat(mobile): add cinematic guided onboarding"
git push origin main
```

### Task 5: Exercise discovery hierarchy

**Files:**
- Modify: `mobile/exercises/ExerciseCatalogScreen.tsx`
- Modify: `mobile/exercises/ExerciseDetailScreen.tsx`
- Modify: `mobile/exercises/ExerciseMedia.tsx`
- Modify: `mobile/exercises/exercisePresentation.nativeContract.test.ts`
- Create: `mobile/exercises/exerciseCatalogPresentation.test.ts`

**Interfaces:**
- Consumes: existing `Sheet`, media resolution, cache, and Task 1 primitives.
- Preserves: catalogue query parameters, pagination, gender presentation, detail route, and offline video cache.

- [ ] **Step 1: Write failing catalogue hierarchy tests**

```ts
expect(source).toMatch(/Sheet/);
expect(source.indexOf("نتایج")).toBeLessThan(source.indexOf("فیلترهای پیشرفته"));
expect(source).toMatch(/activeFilter/);
```

- [ ] **Step 2: Run exercise tests and confirm RED**

Run: `npm test -- exercises/exerciseCatalogPresentation.test.ts exercises/exercisePresentation.nativeContract.test.ts exercises/exerciseMedia.test.ts`
Expected: FAIL because advanced filters are inline before results.

- [ ] **Step 3: Implement discovery hierarchy**

Move advanced filters into the existing Sheet, keep search and primary category controls above the media grid, display removable active-filter chips, and preserve all query values. Tighten detail grouping without changing media download behavior.

- [ ] **Step 4: Verify Task 5**

Run: `npm test -- exercises/*.test.ts video/*.test.ts`
Run: `npm run typecheck`
Run: `../frontend/node_modules/.bin/oxlint exercises/*.ts exercises/*.tsx`
Expected: all commands exit 0.

- [ ] **Step 5: Commit and push**

```bash
git add -- mobile/exercises
git commit -m "feat(mobile): prioritize media in exercise discovery"
git push origin main
```

### Task 6: Nutrition, Body Analysis, Auth, and Profile cohesion

**Files:**
- Modify: `mobile/nutrition/NutritionFoundationScreen.tsx`
- Modify: `mobile/nutrition/NutritionSummaryCard.tsx`
- Modify: `mobile/bodyAnalysis/BodyAnalysisRequirements.tsx`
- Modify: `mobile/bodyAnalysis/BodyAnalysisResultScreen.tsx`
- Modify: `mobile/bodyAnalysis/BodyAnalysisHistoryScreen.tsx`
- Modify: `mobile/auth/AuthScaffold.tsx`
- Modify: `mobile/auth/authStyles.ts`
- Modify: `mobile/profile/ProfileScreen.tsx`
- Create: `mobile/ui/memberScreenParity.nativeContract.test.ts`

**Interfaces:**
- Consumes: Task 1 primitives.
- Preserves: every feature API call, mutation, validation, upload/crop rule, result threshold, and profile form field.

- [ ] **Step 1: Write failing cross-screen hierarchy tests**

```ts
expect(nutrition).toMatch(/ScreenHeader/);
expect(bodyResult).toMatch(/ScreenHeader/);
expect(auth).toMatch(/CinematicSurface/);
expect(profile).toMatch(/ScreenHeader/);
```

- [ ] **Step 2: Run focused parity tests and confirm RED**

Run: `npm test -- ui/memberScreenParity.nativeContract.test.ts nutrition/*.test.ts bodyAnalysis/*.test.ts auth/*.test.ts profile/*.test.ts`
Expected: FAIL on inconsistent top-level presentation.

- [ ] **Step 3: Apply shared hierarchy**

Use shared headers, surfaces, metric strips, and action rhythm. Keep nutrition's calorie/macros first, Body Analysis visualization first, auth media atmosphere restrained, and profile sections grouped. Do not edit domain/API/controller modules.

- [ ] **Step 4: Verify Task 6**

Run: `npm test -- nutrition/*.test.ts bodyAnalysis/*.test.ts auth/*.test.ts profile/*.test.ts ui/memberScreenParity.nativeContract.test.ts`
Run: `npm run typecheck`
Run: `find nutrition bodyAnalysis auth profile -type f \( -name '*.ts' -o -name '*.tsx' \) -print0 | xargs -0 ../frontend/node_modules/.bin/oxlint`
Expected: all commands exit 0.

- [ ] **Step 5: Commit and push**

```bash
git add -- mobile/nutrition mobile/bodyAnalysis mobile/auth mobile/profile mobile/ui/memberScreenParity.nativeContract.test.ts
git commit -m "feat(mobile): unify member screen visual hierarchy"
git push origin main
```

### Task 7: Full verification and Android visual handoff

**Files:**
- Modify only if verification exposes an in-scope regression.

**Interfaces:**
- Consumes: all prior tasks.
- Produces: evidence-bound final status and a phone verification handoff if no device is attached.

- [ ] **Step 1: Run complete automated verification**

Run: `npm test`
Run: `npm run test:native`
Run: `npm run typecheck`
Run: `find . \( -path './android' -o -path './modules' -o -path './node_modules' \) -prune -o \( -name '*.ts' -o -name '*.tsx' \) -print0 | xargs -0 -r -n 60 ../frontend/node_modules/.bin/oxlint --quiet`
Run: `npm run validate`
Run: `npm run audit:dependencies`
Run from repository root: `git diff --check a79fca43..HEAD`
Expected: test/typecheck/lint/validate/diff checks exit 0; dependency audit is reported exactly.

- [ ] **Step 2: Attempt native runtime evidence**

Run: `./var/mobile-android-sdk/platform-tools/adb devices -l`
If a device is present, run the Development Build and inspect the required routes at phone width. If no device is present, do not claim physical-device success and provide the existing APK/QR handoff.

- [ ] **Step 3: Review scope and repository state**

Run: `git status --short`
Run: `git log --oneline a79fca43..HEAD`
Run: `git diff --stat a79fca43..HEAD -- mobile`
Expected: only task files are committed; unrelated baseline WIP remains untouched.

- [ ] **Step 4: Commit any verification-only fix and push**

If Step 1 or Step 2 required a scoped code fix, commit only those explicit files with a behavior-specific Conventional Commit message and push `main`. Otherwise create no empty commit.
