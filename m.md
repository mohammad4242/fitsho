# Fitician Android Quality Upgrade — Luna Roadmap

> Execution owner: Luna. Work directly in the main session. Do not delegate without explicit user permission. Use `superpowers:executing-plans` when available. This request creates a roadmap only; it does not authorize implementing the roadmap or publishing an app.

**Goal:** Make the Android app feel as considered, complete, fast, and visually compelling as the website, with excellent native interactions and demonstrable quality on real phones.

**Architecture:** Improve the existing Expo / React Native app incrementally. Keep existing API adapters, state ownership, native navigation, secure storage, and Backend domain authority. Reuse and refine existing presentation components before creating new ones.

**Stack observed on 2026-09-09:** Expo 57, React Native 0.86, Expo Router, TanStack Query, React Native SVG, Reanimated, Vitest, Jest, React Native Testing Library, and Maestro. These are repository observations, not a claim that these are the newest available versions.

**Design references:** `docs/superpowers/specs/2026-09-09-mobile-visual-parity-design.md` and the current website. Read the earlier implementation plan at `docs/superpowers/plans/2026-09-09-mobile-visual-parity.md`; reconcile it with actual code rather than repeating completed tasks. Preserve `mobile.md` as the previous Android architecture roadmap.

## 1. Read this before editing

The user reports that Android quality is substantially below the website. This document is based on source inspection; no new handset or side-by-side visual audit was performed while writing it. Do not label suspected visual defects as runtime-confirmed bugs.

The repository already contains `CinematicSurface`, `MetricRing`, `MetricStrip`, `ScreenHeader`, `StateSkeleton`, native onboarding, media cards, native contract tests, and recent visual improvement commits. Creating another theme or adding these components again is not progress. Their presence does not prove the rendered experience is good.

At authoring time there was unrelated work in `mobile/package.json`, `mobile/tsconfig.json`, `package-lock.json`, `frontend/src/features/auth/api.test.ts`, and a deleted `mobile/expo-env.d.ts`, plus many untracked assets and local build files. Recheck Git before execution. Do not restore, stage, overwrite, or commit these changes as part of this roadmap without establishing ownership.

### Non-negotiable boundaries

- Preserve Fitician identity and `com.fitician.app`.
- Preserve the current stack. No framework rewrite, WebView replacement, UI framework migration, or blanket dependency upgrade.
- Preserve Backend authority for workouts, nutrition, prices, medical rules, and approvals. Admin remains web-only.
- Preserve auth transport, secure tokens, private media, encrypted offline storage, onboarding drafts, uploads, deletion, and capability checks.
- Body Analysis Ghost is a pose/position guide, never a body-shape target. Preserve privacy-line/crop geometry; do not introduce face/head detection or alter analysis algorithms.
- Default implementation scope is `mobile/`. Treat `frontend/` as a read-only reference. Backend, shared contracts, native security policy, and dependency changes require a concrete need and separate explicit scope.
- Do not ship fabricated metrics, fake progress percentages, fake activity, mock medical results, or decorative controls with no action.
- Preserve existing functionality even when moving it behind a sheet or secondary screen. Inventory every action before changing hierarchy.
- Important product or technology choices require user selection. Show up to three option names, mark one Recommended, and wait before implementing that choice. Routine spacing and component refinements can use the defaults below.
- A new session timer, workout logging model, new chart metric, new notification policy, or new offline write capability is a separate product feature, not an automatic part of visual polish.

## 2. Definition of quality

Use the current approved visual direction: deep petrol surfaces, restrained aqua emphasis, strong imagery, calm spacing, and Persian-first typography. Preserve existing palette and font assets: canvas `#020607`, raised surface `#101e1c`, text `#e8f4f1`, accent `#50dfce`, Vazirmatn for Persian body copy, Lalezar for short display headings, and Sora where supported for English/numeric display. Verify glyph coverage and mixed-script rendering on Android.

The website sets the minimum for information hierarchy, imagery, completeness, and clarity. Android composition must work with touch, system Back, keyboards, safe areas, and small screens. Do not copy desktop columns literally.

| Area | Observable acceptance condition |
| --- | --- |
| First viewport | The screen purpose, current status, and primary action are evident without scrolling through a large decorative header. |
| Hierarchy | One dominant primary action per task region; secondary controls remain discoverable; no repeating wall of identical cards. |
| Typography | Persian joins correctly; mixed units and numbers read correctly; titles, values, labels, and helper text have distinct roles. |
| Layout | No clipped controls or horizontal page overflow at 360, 390, and 430 dp; 320 dp is a stress check. Expanded 600+ dp layouts remain readable. |
| Accessibility | At least 48 dp touch targets; readable contrast on actual surfaces; TalkBack labels, focus, modal boundaries, and 200% text scaling work. |
| Feedback | Every action exposes pressed/loading/success/error feedback; duplicate submissions are prevented where relevant. |
| Data states | Loading, empty, partial error, full error, stale/offline, permission denied, and retry are distinct wherever applicable. |
| Media | Stable aspect ratios, correct cropping, sharp suitable sources, usable fallback, and no jumping layout while loading. |
| Motion | Short purposeful transitions using existing motion tokens; reduced-motion support; no permanent decorative animation. |
| Trust | Pending clinical/coach approval and uncertainty remain visible; missing values never masquerade as zero. |

Visual rubric: score hierarchy, typography/RTL, layout, media, interaction feedback, and state clarity from 0 to 4. 0 = broken; 1 = major problems; 2 = usable with clear issues; 3 = polished with minor issues; 4 = consistent and convincing. Each core screen must score at least 3 in every category, with no blocking defect. Record reasons and evidence; do not self-award a score solely because a test passed. Final aesthetic acceptance belongs to the user.

## 3. Execution protocol for every phase

1. Read the phase, relevant source, existing tests, and earlier evidence. State the step title and exact intended files.
2. Choose one bounded task within the phase. Record its file allowlist and expected visible outcome before editing.
3. For behavior changes, add a failing behavioral test and confirm the relevant failure. For presentation-only work, use existing checks plus actual screenshots; do not manufacture source-string tests to prove appearance.
4. Implement the smallest coherent change. Extract focused presentation components only when they simplify that screen; retain existing query/mutation ownership unless separately justified.
5. Run focused checks and inspect the rendered result. Capture the same account, data, viewport, font scale, route, and state before/after.
6. Review the actual diff for regressions, unrelated changes, secrets, and hidden feature removal. Record results honestly.
7. Show the proposed Conventional Commit message before committing. Stage only exact owned files, commit, then push the current branch to its verified remote. Never hardcode `main`, force-push, or include unrelated WIP.
8. Update phase evidence. Stop before the next important step unless the user has explicitly authorized autonomous execution.

Use progress states `not-started`, `in-progress`, `implemented-awaiting-device-check`, `verified`, and `blocked`. Missing runtime evidence must not become a green checkbox. If a device is unavailable, complete safe independent preparation, then report the unmet gate; do not claim release quality.

Keep reports and temporary artifacts under `mobile/artifacts/quality/`. Commit only sanitized text evidence as needed; do not commit private screenshots, tokens, personal body photos, build outputs, or local tooling. Use synthetic accounts for capture. Never disable production screenshot/privacy protections to collect evidence.

## 4. Phase 0 — Establish the actual gap

**Read:** `mobile/app/`, `mobile/ui/`, `mobile/home/`, `mobile/workouts/`, `mobile/nutrition/`, `mobile/bodyAnalysis/`, `mobile/profile/`, `frontend/src/App.tsx`, and the paired web files below.

**Create:** `mobile/artifacts/quality/baseline.md`, `mobile/artifacts/quality/parity-matrix.md`, and a local capture directory under the same root.

- [ ] Record branch, commit, dirty paths, installed/build versions, app ID, build profile, and available Android devices. Confirm the installed APK belongs to the checkout being reviewed.
- [ ] Record baseline test failures separately from newly introduced failures. Inspect package scripts before running commands.
- [ ] Open the website and Android app with equivalent synthetic profiles: training only, nutrition only, combined, new user, and pending review.
- [ ] Capture primary screens and their applicable error/loading/empty states. Record web viewport CSS width and native logical dp; compare composition, not raw screenshot pixel dimensions.
- [ ] Inventory all routes, visible actions, permissions, and data dependencies. Classify gaps as visual, interaction, missing existing capability, reliability, or performance.
- [ ] Give each defect an ID, reproduction steps, expected result, evidence path, severity, affected file, and planned phase. Prioritize blockers and daily user journeys.

**Gate:** A concrete comparison matrix exists. At least Home, workout, nutrition, catalogue, Body Analysis, onboarding, and profile have evidence or explicit unavailable-evidence entries. Unavailable evidence blocks visual acceptance, not truthful documentation.

## 5. Phase 1 — Validate one visual direction with Home

**Modify:** `mobile/home/MemberHomeScreen.tsx`, `mobile/home/WorkoutTodayCard.tsx`, `mobile/home/NutritionSummaryCard.tsx`, `mobile/home/QuickActionCard.tsx`; adjust `mobile/ui/tokens.ts` only when required by the existing direction.

**Reference:** `frontend/src/pages/DashboardPage.tsx`, `frontend/src/pages/dashboard.css`.

**Tests:** existing `mobile/home/*.test.ts`; add `mobile/home/MemberHomeScreen.rntl.test.tsx` for rendered behavior when changing it.

- [ ] Produce a small annotated composition using current data: compact greeting/profile access, today's primary task, real nutrition status, and secondary quick actions.
- [ ] Refine the current Home implementation at 360 and 430 dp. Keep imagery connected to the action it explains. Avoid oversized empty areas and competing headings.
- [ ] Preserve product-mode visibility, workout availability, pending approval, calorie target/consumption semantics, and partial data errors.
- [ ] Check long Persian names, large values, missing targets, no plan, offline cache, and failed media. Never expose account email unnecessarily as display copy.
- [ ] Capture before/after and score the rubric. Obtain user acceptance of this representative screen before applying a materially different visual direction across the app.

**Gate:** Home works in all three product modes; its primary action works; rendered evidence supports the visual score. A palette change by itself does not pass.

## 6. Phase 2 — Make the shared foundation consistent

**Modify as needed:** `mobile/ui/tokens.ts`, `mobile/ui/fontManifest.ts`, `mobile/ui/rtl.ts`, `mobile/ui/accessibility.ts`, `mobile/ui/layoutMetrics.ts`, `mobile/ui/layout/Screen.tsx`, existing files under `mobile/ui/components/`, `mobile/app/(member)/member/(tabs)/_layout.tsx`, and `mobile/ui/navigation/BackBehaviorProvider.tsx`.

**Tests:** existing `mobile/ui/*.test.ts`, `mobile/ui/components.rntl.test.tsx`, `mobile/ui/navigation/RouteGuards.rntl.test.tsx`.

- [ ] Carry only the approved Home refinements into shared tokens and primitives. Audit usages before changing a global token.
- [ ] Standardize headings, body/label sizes, spacing, corner radii, icon weights, media ratios, and button states. Extend current primitives; do not add parallel versions.
- [ ] Verify safe-area ownership so tab/header/content padding is not doubled. Test gesture navigation, three-button navigation, keyboard opening, and focused inputs.
- [ ] Verify tabs preserve expected state and Back dismisses sheet/keyboard before leaving the task. Preserve role and capability guards and deep links.
- [ ] Audit mixed Persian/English text and directional icons. Avoid blanket mirroring of numbers, media controls, charts, or logos.
- [ ] Validate reduced motion, TalkBack traversal, modal focus restoration, visible error text, and 200% text scaling.

**Gate:** Representative Home, form, list, and modal screens pass layout/accessibility checks without regressions. Controls remain reachable above the keyboard and system bars.

## 7. Phase 3 — Give workout and exercise flows premium usability

**Modify:** `mobile/workouts/WorkoutPlansScreen.tsx`, `mobile/workouts/WorkoutCyclePanel.tsx`, `mobile/exercises/ExerciseCatalogScreen.tsx`, `mobile/exercises/ExerciseDetailScreen.tsx`, `mobile/exercises/ExerciseMedia.tsx`.

**Reference:** `frontend/src/features/workouts/WorkoutPlanPage.tsx`, `frontend/src/features/exercises/ExerciseCatalogPage.tsx`, `frontend/src/features/exercises/ExerciseDetailPage.tsx`.

**Tests:** existing workout/exercise suites; add `mobile/workouts/WorkoutPlansScreen.rntl.test.tsx` and `mobile/exercises/ExerciseCatalogScreen.rntl.test.tsx` for changed interactions.

- [ ] Build a clear plan overview and discoverable day selection. Exercise names, sets/reps/rest, equipment, and meaningful warnings must remain legible on narrow screens.
- [ ] Preserve active/pending/historical plan distinctions, generation errors, cycle feedback, history, replacements, and PDF actions. Never make a pending plan executable through a styling change.
- [ ] Make search/results the catalogue focus. Keep advanced filters in the existing sheet pattern with visible active filters, individual removal, and reset.
- [ ] Check long results, empty search, pagination, slow media, alternate media presentation, detail navigation, and returning to the previous list position.
- [ ] Detail prioritizes usable media, instructions, technique cues, and safety. Preserve offline video behavior and clear cache/download state.
- [ ] Ensure only eligible visible media plays and video stops on background/navigation. Use the existing cache and list machinery; measure before replacing it.

**Gate:** A user can open the correct workout, inspect an exercise, return, change a filter, and obtain the existing PDF without confusion or lost state. Tests cover pending-plan restrictions and action routing; device evidence covers scrolling and media.

## 8. Phase 4 — Make nutrition understandable at a glance

**Modify:** `mobile/nutrition/NutritionFoundationScreen.tsx`, `NutritionSummaryCard.tsx`, `NutritionPlanSection.tsx`, `NutritionTrackingSection.tsx`, `NutritionCatalogueSection.tsx`, `NutritionShoppingList.tsx`, `NutritionClinicalSection.tsx`, and `NutritionAdherenceSection.tsx` in the same directory.

**Reference:** `frontend/src/features/nutrition/NutritionTrackingPage.tsx`, `NutritionEstimatePage.tsx`, `MealCataloguePage.tsx`, `NutritionLabsPage.tsx`, and `NutritionSupplementsPage.tsx` in the same web feature directory. Confirm active routes in `frontend/src/App.tsx` before treating a catalogue page as a parity requirement.

**Tests:** existing nutrition suites; add `mobile/nutrition/NutritionTrackingSection.rntl.test.tsx` for changed entry interactions.

- [ ] Place real calorie/target status and macros before secondary tools. Distinguish estimate, approved plan, consumed amount, and remaining amount.
- [ ] Make day selection, meal inspection, portion entry, existing replacement, shopping list, and tracking confirmation easy to find and operate.
- [ ] Use actual food media when available and intentional fallbacks otherwise. Preserve scientific details, clinical warnings, approval state, budget, currency units, and uncertainty.
- [ ] Check Persian decimal input, unit labels, save failure, retry, duplicate taps, stale data, and day changes. Preserve current date semantics; raise any timezone defect separately before altering domain behavior.
- [ ] Keep laboratory and supplement tools discoverable without dominating the daily tracking screen. Do not remove them to simplify a screenshot.

**Gate:** Users can understand today's status and record an existing supported food action. The screen never presents unapproved recommendations as approved or missing values as zero.

## 9. Phase 5 — Make Body Analysis clear and trustworthy

**Modify:** `mobile/bodyAnalysis/BodyAnalysisOverviewCard.tsx`, `BodyAnalysisWizard.tsx`, `BodyAnalysisRequirements.tsx`, `BodyPhotoCapture.tsx`, `GhostOverlayGuide.tsx`, `BodyAnalysisResultScreen.tsx`, and `BodyAnalysisHistoryScreen.tsx` in the same directory.

**Reference:** `frontend/src/features/bodyPhotos/BodyProgressPage.tsx`, `frontend/src/features/bodyPhotos/BodyAnalysisResultPage.tsx`.

**Tests:** existing body-analysis privacy/flow suites; add `mobile/bodyAnalysis/BodyAnalysisWizard.rntl.test.tsx` for changed controls and state presentation.

- [ ] Present concise preparation instructions, view order, privacy explanation, and a clear next action at each capture step.
- [ ] Keep Ghost geometry and visible crop boundaries consistent with the existing processing contract. Styling must not change the image sent to analysis.
- [ ] Make permission denial recoverable and show a usable retake/preview path. Preserve drafts and interruption recovery.
- [ ] Show actual known processing stages without invented completion percentages or promised completion times.
- [ ] Prioritize meaningful results, then explanations and history. Keep uncertainty, unavailable measurements, resumable sessions, and deletion controls explicit.
- [ ] Verify capture-to-preview-to-upload and result/history navigation using synthetic or consented test material. Check image/network evidence without persisting sensitive payloads in reports.

**Gate:** Native capture and resume are verified; no privacy regression; incomplete/failed analysis is never styled as a completed result. Camera-specific acceptance requires a real supported phone.

## 10. Phase 6 — Complete first-use, profile, and specialist polish

**Modify:** `mobile/app/(public)/index.tsx`, `mobile/auth/AuthScaffold.tsx`, `mobile/auth/authStyles.ts`, relevant routes under `mobile/app/(auth)/auth/`, `mobile/onboarding/PublicOnboardingScreen.tsx`, `mobile/onboarding/OnboardingScreen.tsx`, `mobile/profile/ProfileScreen.tsx`, `mobile/profile/ProfilePhotoControl.tsx`, `mobile/accountDeletion/AccountDeletionScreen.tsx`, `mobile/coach/CoachWorkoutReviewScreen.tsx`, `mobile/physician/PhysicianNutritionReviewScreen.tsx`.

**Reference:** corresponding auth, public onboarding, profile, account deletion, coach review, and physician review pages under `frontend/src/features/`.

**Tests:** existing auth/onboarding/profile/accountDeletion/coach/physician suites and relevant native route tests. Add native interaction tests only for changed behaviors.

- [ ] Public entry uses the existing optimized brand imagery and clear CTAs. Avoid a heavy promotional video dependency.
- [ ] Auth fields remain readable above the keyboard; validation stays inline; password/OTP actions and provider configuration failures are actionable.
- [ ] All successful auth paths preserve onboarding draft hydration. Question progress reflects the real flow; back/restart does not erase answers.
- [ ] Profile sections clearly group personal details, goals, health-related settings, and account actions. Private photo preview/save/error/deletion stays usable.
- [ ] Destructive actions retain confirmation and readable consequences. Do not surface implementation jargon or internal server messages.
- [ ] Specialist screens keep review evidence, edits, approval/rejection, and status readable on phones; preserve role boundaries.

**Gate:** New-user and returning-user flows complete; drafts survive restart; profile editing and existing specialist actions pass focused checks. No controls are decorative or routed to a dead end.

## 11. Phase 7 — Reliability, performance, and final visual regression

**Inspect/modify only for measured issues:** `mobile/platform/performance.ts`, `mobile/platform/performanceMeasuredCommit.tsx`, `mobile/platform/queryDefaults.ts`, `mobile/platform/connectivity.ts`, `mobile/platform/backgroundSync.ts`, `mobile/video/publicExerciseVideoCache.ts`, `mobile/video/publicExerciseVideoStore.ts`, `mobile/ui/requestState.ts`, and the affected screen.

**Read:** `docs/mobile-performance.md`, `docs/mobile-accessibility.md`, `docs/mobile-e2e.md`, `docs/mobile-release.md`, `docs/mobile-eas.md`, `mobile/device-matrix.json`, and `mobile/platform/performance.ts`.

**Extend:** relevant flows under `mobile/.maestro/`; record results in `mobile/artifacts/quality/final-report.md`.

- [ ] Exercise airplane mode, slow connection, failed request, background/foreground, expired session, denied permissions, process restart, and repeated taps. Use the existing offline contract; do not silently queue unsupported writes.
- [ ] Profile representative list/media flows and transitions on low/mid-range hardware. Fix measured causes of jank or memory growth rather than adding memoization everywhere.
- [ ] Preserve current performance budgets: cold start 3000 ms, transition 300 ms, list render 250 ms, image processing 1500 ms, peak memory 200 MB, battery drain 8%/hour, video cache lookup 150 ms, upload 30000 ms. Read the live registry again before execution and report drift.
- [ ] Retain p95 and per-sample evidence required by the existing performance policy. Report network conditions and device/build profile; local JS timings alone do not prove native frame quality or process memory.
- [ ] Run existing device coverage for API 24, 29, 33, and 36, including physical low/mid-range tiers. Record actual hardware separately from emulator profiles.
- [ ] For the documented launch cohort, record at least 100 clean launches per representative device tier and the required crash-free threshold. Report observed counts; do not imply this establishes production reliability statistically.
- [ ] Repeat the visual rubric and same-state comparisons for every primary route, including sheets, keyboard, large text, and failure states.

**Gate:** No known blocking crash, privacy issue, lost-data regression, unusable control, or failing core journey. Unmet performance/device/visual criteria remain explicit blockers; never weaken budgets to declare success.

## 12. Verification commands and evidence limits

Run from the repository root unless indicated. These commands are based on scripts present when this roadmap was written; recheck package scripts and local tools first.

```bash
npm run build:core
npm run typecheck:mobile
npm run test --workspace @fitician/mobile
npm run test:native --workspace @fitician/mobile
npm run test:mobile:foundation
npm run validate:mobile
git diff --check
```

For one focused native suite:

```bash
npm run test:native --workspace @fitician/mobile -- --runTestsByPath home/MemberHomeScreen.rntl.test.tsx
```

Use that focused command only after the planned test file exists. For focused Vitest runs, invoke the installed Vitest binary from `mobile/` with explicit test paths; the existing `npm test` script already supplies many directory globs, so appending one path may still run the full suite. Run installed Oxlint against exact changed TypeScript files using the repository configuration; do not install a new lint tool to satisfy this document.

Run additional core/contract/frontend/backend checks only if those areas are explicitly brought into scope. Record unrelated baseline failures without hiding them or repairing them opportunistically.

Run the applicable Maestro flows with controlled synthetic accounts, using `docs/mobile-e2e.md` for required environment/setup. Flow YAML validation is not evidence that a device journey ran. RNTL tests prove rendered interaction contracts, not final Android visual quality. Source-text assertions can guard a narrow invariant but cannot prove usable composition.

Inspect `mobile/scripts/release-build-plan.mjs` and the release docs before using build scripts. Record the command that actually built the artifact, exit status, artifact path/hash, signing/profile, installed version, and launch result. A build plan, Metro bundle, or successful compilation does not prove physical-device success.

## 13. Final handoff and release boundary

Deliver a reproducible internal APK through the project's existing build workflow, with sanitized test credentials supplied outside Git when needed. Do not change signing credentials, publish to a store, send messages, or distribute private data without authorization.

The final report must include:

- [ ] Exact commit/build identity and reproducible build/install steps.
- [ ] Per-screen before/after evidence and visual rubric with remaining defects.
- [ ] Feature/action parity matrix showing all existing user actions retained or explicitly approved for change.
- [ ] Automated check results and independent device evidence clearly separated.
- [ ] Measured performance and accessibility coverage, with unavailable checks named.
- [ ] A short Persian phone-test handoff: install/open, sign in, inspect Home, open workout/exercise, record supported nutrition action, test Body Analysis, edit profile, disconnect/reconnect, reopen app.
- [ ] User acceptance of visual quality before declaring the quality upgrade finished.

Use this concise terminal report after each verified task:

```text
Changed: <visible outcome and main files>
Verified: <checks and device evidence; name missing evidence>
Git: <proposed message before commit; actual commit/push result afterward>
Next: <next single task or specific blocker>
```

## 14. Start instruction for Luna

Read `AGENTS.md`, this file, the earlier visual design/plan, and current Git status. Start with Phase 0 only. Produce the real gap inventory before editing UI. Preserve existing work. Do not rebuild already-present components, choose a new stack, or mark visual quality complete from automated tests. Follow the phases in order, work in small verified commits, and stop between important steps unless the user explicitly authorizes autonomous execution.
