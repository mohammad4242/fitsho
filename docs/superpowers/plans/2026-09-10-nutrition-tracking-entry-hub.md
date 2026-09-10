# Nutrition Tracking Entry Hub Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reorder and polish the web Nutrition Tracking page around a collapsed, mutually exclusive manual/photo entry hub without changing nutrition behavior.

**Architecture:** Keep the existing page and workflows in `NutritionTrackingPage.tsx`. Replace the photo boolean and native manual `<details>` with one `EntryMode` state, render one selected panel inline, and use page-scoped CSS for the branch hub and responsive layout.

**Tech Stack:** React 19, TypeScript, React Testing Library, Vitest, existing Fitsho CSS tokens and `AppIcon`.

**Spec:** `docs/superpowers/specs/2026-09-10-nutrition-tracking-entry-hub-design.md`

## Global Constraints

- Only modify `frontend/src/features/nutrition/NutritionTrackingPage.tsx`, `frontend/src/features/nutrition/nutritionEstimate.css`, and `frontend/src/features/nutrition/NutritionWorkflowPages.test.tsx` for implementation.
- Do not modify backend, mobile/Android, API/type contracts, nutrition calculations, photo behavior, persistence, or API payloads.
- Normal visits start with `entryMode === null`; `freeMealId` starts with `entryMode === "photo"`.
- Only one entry panel can be rendered at a time, and the selected method uses a semantic button with `type="button"`, `aria-expanded`, and `aria-controls`.
- The check-in section is the final content section; no error or status content is rendered after it.
- Use existing Fitsho tokens and icons; add no dependency and no global CSS side effects.
- Preserve RTL/LTR, focus visibility, minimum useful target sizing, no horizontal overflow, and reduced-motion behavior.

---

### Task 1: Add failing interaction and ordering tests

**Files:**
- Modify: `frontend/src/features/nutrition/NutritionWorkflowPages.test.tsx`

**Interfaces:**
- Consumes: Existing mocked nutrition API fixtures and `NutritionTrackingPage`.
- Produces: Regression coverage for the controlled entry hub and page order.

- [ ] **Step 1: Add a normal-load collapse test**

Render `NutritionTrackingPage` in `MemoryRouter`, wait for `Logged calories`, then assert both `Log manually` and `Food photo` buttons exist, both have `aria-expanded="false"`, and neither `nutrition-manual-entry-panel` nor `nutrition-photo-entry-panel` exists.

- [ ] **Step 2: Add mutual-exclusion and toggle tests**

Click the manual selector and assert only the manual panel exists and its button is expanded. Click the photo selector and assert only the photo panel exists and the manual panel is absent. Click the active photo selector again and assert both panels are absent and both buttons are collapsed.

- [ ] **Step 3: Add ordering and final check-in assertions**

Use `container.querySelector` for `.nutrition-entry-hub`, `.nutrition-daily-panel`, `.nutrition-adherence-card`, and `.nutrition-checkin`, then assert the hub precedes the daily panel and the check-in follows the adherence card.

- [ ] **Step 4: Update existing manual/photo tests to select through the new buttons**

Replace the old manual `<details>` trigger query with the `Log manually` method selector. Keep the existing exact catalogue payload assertion unchanged. Keep photo tests using the photo selector except the free-meal test, which must verify the photo panel is initially available from its query parameter.

- [ ] **Step 5: Run the focused test and verify RED**

Run:

```bash
cd frontend
npm run test -- src/features/nutrition/NutritionWorkflowPages.test.tsx
```

Expected: the new hub/panel assertions fail because the current page has no controlled manual selector, no entry hub, and the daily summary currently precedes the photo workflow.

### Task 2: Implement the controlled page structure

**Files:**
- Modify: `frontend/src/features/nutrition/NutritionTrackingPage.tsx`

**Interfaces:**
- Consumes: Existing API functions, local state, `freeMealId`, and `AppIcon`.
- Produces: `EntryMode`-controlled hub, one inline workflow panel, and the required DOM order.

- [ ] **Step 1: Replace `photoOpen` with `EntryMode`**

Import `AppIcon`, declare `type EntryMode = "manual" | "photo" | null`, initialize it with `freeMealId ? "photo" : null`, and add a toggle handler that sets the active mode to `null` or switches to the requested mode.

- [ ] **Step 2: Add the entry hub directly after the page header**

Render the root label `ثبت تغذیه` / `Nutrition tracking`, then semantic manual and photo buttons in DOM order. Each button uses the existing `catalogue` or `camera` icon, its exact title/supporting copy, selected styling, `aria-expanded`, and the matching panel id.

- [ ] **Step 3: Move the photo workflow behind `entryMode === "photo"`**

Keep the current photo consent, preview, upload restrictions, estimate, correction, removal, resolution, confirmation, free-meal navigation, and busy/error logic unchanged. Render the existing photo panel only when photo mode is selected and give it the controlled panel id.

- [ ] **Step 4: Move the manual workflow behind `entryMode === "manual"`**

Replace the native `<details>` wrapper with the controlled manual panel. Keep the two existing fieldsets and their handlers/payloads unchanged. Move the existing recent-food buttons inside this panel.

- [ ] **Step 5: Reorder the remaining sections**

Place one error/status message after the active panel and before the daily summary, then render the unchanged daily summary, today's entries, adherence accordion, and check-in in that order. Do not render any content after check-in.

- [ ] **Step 6: Run the focused tests and verify GREEN**

Run:

```bash
cd frontend
npm run test -- src/features/nutrition/NutritionWorkflowPages.test.tsx
```

Expected: all focused nutrition workflow tests pass, including unchanged exact catalogue and photo payload assertions.

### Task 3: Add page-scoped visual and responsive styling

**Files:**
- Modify: `frontend/src/features/nutrition/nutritionEstimate.css`

**Interfaces:**
- Consumes: New hub, choice, panel, feedback, and existing tracking class names.
- Produces: Dark Fitsho hub styling, subtle branch connectors, selected/focus states, full-width panels, and narrow-width layout.

- [ ] **Step 1: Replace obsolete tracking trigger styles**

Remove the old `.nutrition-photo-entry` and manual-summary styling from the tracking block. Keep photo workflow detail styles and existing shared nutrition styles used by other pages.

- [ ] **Step 2: Style the hub and connectors**

Use `.nutrition-entry-hub`, `.nutrition-entry-root`, `.nutrition-entry-branches`, `.nutrition-entry-choice`, `.nutrition-entry-choice.is-active`, `.nutrition-entry-choice__icon`, `.nutrition-entry-choice__copy`, and `.nutrition-entry-panel`. Use pseudo-elements for the root stem, horizontal branch, and two branch stems with `var(--fitsho-line)`/`var(--fitsho-line-strong)`.

- [ ] **Step 3: Style manual, photo, summary, entries, adherence, and final check-in in hierarchy**

Keep existing token-based surfaces and field styles, ensure the expanded panel fills the available content width, make the recent-food group read as part of manual logging, and keep the check-in visually quiet while preserving its active state.

- [ ] **Step 4: Add responsive and reduced-motion rules**

At narrow widths keep the two choices readable in two columns, prevent text overflow, retain full-width panels, keep controls at least roughly 44px high, and disable hub transitions under `prefers-reduced-motion: reduce`.

- [ ] **Step 5: Run focused tests, lint, and build**

Run:

```bash
cd frontend
npm run test -- src/features/nutrition/NutritionWorkflowPages.test.tsx
npm run lint
npm run build
```

Expected: focused tests, lint, and production build exit successfully.

### Task 4: Complete repository verification and visual inspection

**Files:**
- Inspect only: implementation diff and generated runtime output; no additional source files unless a scoped regression requires it.

**Interfaces:**
- Consumes: The verified implementation from Tasks 1–3.
- Produces: Final evidence for behavior, responsive layout, scope, and Git state.

- [ ] **Step 1: Run the full frontend test suite**

Run `cd frontend && npm run test`. Record focused failures separately from unrelated pre-existing failures if any.

- [ ] **Step 2: Inspect the rendered page at three widths**

Use the available local browser/screenshot path at approximately 390px, 768px, and desktop width. Confirm Persian RTL layout, initial collapse, branch lines, one active panel, no horizontal overflow, summary after entry UI, and check-in as the final content section.

- [ ] **Step 3: Audit the diff and scope**

Run `git diff --check`, inspect the three implementation files plus the design/plan artifacts, confirm no backend/mobile/API/type files changed, and confirm existing unrelated work remains unstaged.

- [ ] **Step 4: Commit and push the verified implementation**

Proposed commit:

```bash
git add frontend/src/features/nutrition/NutritionTrackingPage.tsx frontend/src/features/nutrition/nutritionEstimate.css frontend/src/features/nutrition/NutritionWorkflowPages.test.tsx
git commit -m "feat(nutrition-tracking): add food entry decision hub"
git push origin main
```
