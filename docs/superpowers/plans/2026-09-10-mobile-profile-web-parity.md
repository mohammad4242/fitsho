# Mobile Profile Web-Parity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Redesign the native Profile screen around the Web account hierarchy while preserving native behavior and contracts.

**Architecture:** Keep all new presentation primitives inside `mobile/profile/ProfileScreen.tsx`. Reuse existing tokens and shared form primitives, replace only the profile screen's segmented navigation and choice styling, and add the supported-sex rule only in `mobile/profile/profileModel.ts`.

**Tech Stack:** React Native, Expo Router, TypeScript, Jest/RNTL, Vitest.

**Spec:** `docs/superpowers/specs/2026-09-10-mobile-profile-web-parity-design.md`

## Global Constraints

- Do not modify `frontend/*`, `backend/*`, or `packages/fitician-core/src/profile.ts`.
- Keep `body_recomposition` as the internal value and show `ریکامپ` on the Android Profile screen.
- Keep only `female`/`زن` and `male`/`مرد` as native Profile sex choices.
- Preserve profile loading, saving, photo lifecycle, route guards, back behavior, status refresh, and API contracts.
- Use profile-local styles/components and existing Fitician tokens.
- Preserve unrelated working-tree files and stage only the bounded feature files.

---

### Task 1: Native-only sex validation and presentation regression tests

**Files:**
- Modify: `mobile/profile/profileModel.ts`
- Test: `mobile/profile/profileModel.test.ts`
- Test: `mobile/profile/ProfileScreen.rntl.test.tsx`
- Test: `mobile/profile/profilePresentation.nativeContract.test.ts`

**Interfaces:**
- Consumes the existing core `validateStep` result and `ProfileFormValues`.
- Produces a mobile-only validation result that flags unsupported persisted sex values without changing them.

- [ ] Write tests for legacy sex validation and all requested Profile labels/behaviors.
- [ ] Run the focused Vitest/Jest tests and confirm the new assertions fail for the current UI.
- [ ] Implement the smallest native-only sex validation wrapper and supported option constants.
- [ ] Run focused model and screen tests until the validation assertions pass.

### Task 2: Compact account surface, progress, measurements, and personal groups

**Files:**
- Modify: `mobile/profile/ProfileScreen.tsx`

**Interfaces:**
- `ProfileSectionProgress` receives the dynamic section list, current section, disabled state, and section callback.
- `ProfileOverviewCard`, `ProfileMeasurements`, and `PersonalSection` retain their current external props and API calls.

- [ ] Add the local progress component and replace the global `SegmentedControl` presentation.
- [ ] Tighten the title, summary hierarchy, stat grid, measurement cards, and photo-control spacing.
- [ ] Split Personal into `مشخصات فردی` and `بدن و هدف`, with compact two-column measurements and local choice styles.
- [ ] Apply `ریکامپ`, supported sex choices, RTL/LTR, token-based spacing, and training/nutrition group headings.
- [ ] Run focused RNTL tests and TypeScript typecheck.

### Task 3: Photo-control visual polish and final verification

**Files:**
- Modify only if needed: `mobile/profile/ProfilePhotoControl.tsx`

- [ ] Confirm photo upload, replacement, deletion, and callback code is unchanged; adjust only compact presentation if the new screen needs it.
- [ ] Run profile model tests, Profile RNTL tests, native contract tests, mobile typecheck, mobile lint/static checks, and `git diff --check`.
- [ ] Inspect the final source/layout assumptions at 390px and verify no forbidden copy or horizontal-overflow-prone fixed layout remains.
- [ ] Commit the bounded implementation with a specific Conventional Commit and push the configured branch.
