# Mobile Exercise Library Discovery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make mobile Exercise Library discovery a visible web-aligned region → muscle → focus flow without changing API or exercise presentation contracts.

**Architecture:** Keep one `CatalogSelection` state and add a local `showAll` mode. Render one discovery panel directly below search; derive `canLoadExercises` and `advancedFilterCount` from the existing state, and leave the secondary filters in the existing Sheet.

**Tech Stack:** React Native, Expo, TanStack Query v5, TypeScript, Jest React Native Testing Library, Vitest, Fitician design tokens.

**Spec:** `docs/superpowers/specs/2026-09-09-mobile-exercise-library-discovery-design.md`

## Global Constraints

- This is a mobile presentation/state-flow task; do not change backend, API endpoints, field names, pagination, schemas, web catalog, cards, media, details, or routing.
- Continue using `CatalogSelection`, `BodyRegion`, `MuscleGroup`, `MuscleFocus`, `ExerciseLabel`, `ExerciseType`, `ExerciseFilters`, `createExerciseApi()`, and `exerciseCopy`.
- Use `enabled: canLoadExercises` so the initial screen does not fetch the full catalogue.
- “همه حرکات” explicitly enables full-catalogue mode; “پاک کردن فیلترها” returns to guided discovery.
- Use existing `fiticianTokens`, RTL text/layout, wrapped mobile selectors, and compact quick-chip visual height with accessible hit slop.
- Preserve unrelated WIP and stage only the files belonging to this task.

---

### Task 1: Lock the visible staged discovery contract in tests

**Files:**
- Modify: `mobile/exercises/ExerciseCatalogScreen.rntl.test.tsx`
- Modify: `mobile/exercises/exerciseCatalogPresentation.test.ts`

**Interfaces:**
- Consumes: current screen test harness, category fixture, exercise fixture, and mocked `useQuery`.
- Produces: failing tests that describe direct region discovery, staged reveal, explicit loading modes, special filter payloads, search, secondary Sheet access, and no header/Sheet duplication.

- [ ] **Step 1: Replace Sheet-first interactions with direct discovery assertions**

Update the fixture to include all three API body regions, upper-body muscles, and
at least three chest focus categories. Make the mocked exercise query return no
data while `enabled` is false, and add helpers that read the latest list query
options from `mockUseQuery.mock.calls`.

- [ ] **Step 2: Add failing behavior tests**

Cover these named behaviors: visible body regions without opening a Sheet;
guided initial state without a result count/cards; region revealing muscles;
region then chest revealing focus; changing region clearing old muscle/focus;
cardio and mobility shortcut payloads clearing guided state; explicit all-mode
loading; search enabling results directly; opening “فیلترهای بیشتر” and
selecting equipment/difficulty; no prominent header filter action; and no
duplicated primary selectors inside the Sheet. Keep search and removable
active-filter coverage.

- [ ] **Step 3: Update source-contract assertions**

Assert that the screen contains `enabled: canLoadExercises`, places the
discovery stages before the Sheet, and does not use the old header action or
the old Sheet-contained primary stages.

- [ ] **Step 4: Run the focused native tests and confirm expected failures**

Run `npm --prefix mobile exec jest -- --config jest.config.cjs --runInBand exercises/ExerciseCatalogScreen.rntl.test.tsx`.
Expected: failures identify the missing direct stages, explicit query gate,
and new state transitions rather than fixture or syntax errors.

- [ ] **Step 5: Commit the failing contract tests**

```bash
git add mobile/exercises/ExerciseCatalogScreen.rntl.test.tsx mobile/exercises/exerciseCatalogPresentation.test.ts
git commit -m "test(mobile): define staged exercise library discovery"
```

### Task 2: Implement state-gated discovery panel and secondary filters

**Files:**
- Modify: `mobile/exercises/ExerciseCatalogScreen.tsx`
- Modify: `mobile/exercises/exerciseCopy.ts`

**Interfaces:**
- Consumes: Task 1 tests and existing API/category/query helpers.
- Produces: `showAll`, `canLoadExercises`, `advancedFilterCount`, direct
  `RegionOption`/wrapped category selectors, compact quick filters, and a
  Sheet containing only secondary filter controls.

- [ ] **Step 1: Add copy constants required by the new hierarchy**

Add only reusable strings needed for the discovery prompt, muscle prompt, focus
description, all-focus label, results title, search placeholder, and
“فیلترهای بیشتر”. Keep the existing category and filter vocabulary.

- [ ] **Step 2: Add explicit mode derivation and query gating**

Initialize `showAll` to false. Derive `hasSearch`, `hasSpecialFilter`,
`hasGuidedSelection`, `canLoadExercises`, and `advancedFilterCount`. Pass
`enabled: canLoadExercises` to the exercise `useQuery`, and keep category
loading independent. Build filters from the same `selection` object.

- [ ] **Step 3: Update selection transitions**

Implement explicit all-mode reset; make clear return to initial guided state;
make body region/special shortcuts clear the mutually exclusive path and
`showAll`; keep muscle/focus/content type transitions and active-filter removal
consistent with the new mode.

- [ ] **Step 4: Render the single discovery panel**

Place it immediately below search. Render compact quick chips, category state,
stage 01 region cards, conditional wrapped stage 02 muscle options, conditional
wrapped stage 03 focus options and content switcher, then the small advanced
filter trigger. Do not use a primary horizontal ScrollView.

- [ ] **Step 5: Reduce the Sheet to secondary filters**

Remove body region, muscle, and focus stages from the Sheet. Keep equipment,
difficulty, exercise type, clear, and result actions. Use wrapped advanced
choices where needed and show the computed advanced count on the trigger.

- [ ] **Step 6: Render the correct empty/result state**

Render active removable chips below the discovery panel. When the query is not
enabled, render only the contextual guided prompt; when enabled, render the
existing result heading and `ExerciseResults`. Preserve card/media/detail code.

- [ ] **Step 7: Run focused tests and typecheck**

Run `npm --prefix mobile exec jest -- --config jest.config.cjs --runInBand exercises/ExerciseCatalogScreen.rntl.test.tsx` and `npm --prefix mobile run typecheck`.
Expected: the new catalog tests pass and TypeScript reports no errors.

- [ ] **Step 8: Commit the implementation**

```bash
git add mobile/exercises/ExerciseCatalogScreen.tsx mobile/exercises/exerciseCopy.ts
git commit -m "feat(mobile): align exercise library discovery with web catalog"
```

### Task 3: Run the complete mobile verification gates

**Files:**
- Inspect: `mobile/exercises/ExerciseCatalogScreen.tsx`
- Inspect: `mobile/exercises/ExerciseCatalogScreen.rntl.test.tsx`
- Inspect: `mobile/exercises/exerciseCatalogPresentation.test.ts`

**Interfaces:**
- Consumes: completed Task 2 implementation and focused tests.
- Produces: verified mobile catalog behavior and a clean, scoped final diff.

- [ ] **Step 1: Run the required typecheck**

Run `npm --prefix mobile run typecheck` and record the actual result.

- [ ] **Step 2: Run the required native suite**

Run `npm --prefix mobile run test:native` and fix only failures caused by this
catalog change.

- [ ] **Step 3: Run the required mobile Vitest suite**

Run `npm --prefix mobile test` and fix only failures caused by this catalog
change.

- [ ] **Step 4: Inspect the final source hierarchy and diff**

Use `git diff --check`, inspect the final screen around search/panel/stages/
results/Sheet, and verify that no backend, web, card, detail, routing, or
unrelated WIP file is staged.

- [ ] **Step 5: Commit and push the verified final state**

Show the proposed Conventional Commit message, stage only the implementation
and directly affected tests, run `git diff --cached --check`, commit, and push
the current branch to its configured remote without rewriting history.
