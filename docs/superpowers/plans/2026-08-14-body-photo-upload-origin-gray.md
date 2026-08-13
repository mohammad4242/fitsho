# Body Photo Upload Origin and Gray Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make phone uploads succeed from the active trusted LAN origin and use `#A0A3A1` for standardized backgrounds.

**Architecture:** Keep the security boundary intact by updating only the explicit trusted-origin configuration. Map the known 403 origin error at the existing API boundary, and change the single compositor color constant without altering segmentation or geometry.

**Tech Stack:** React, TypeScript, Vitest, FastAPI runtime settings

## Global Constraints

- The neutral background is exactly RGB `[160, 163, 161]` (`#A0A3A1`).
- Trusted-origin enforcement remains enabled.
- Body pixels, proportions, pose, and geometry must not be altered.
- Never commit `backend/.env`.

---

### Task 1: Actionable Origin Error and Approved Gray

**Files:**
- Modify: `frontend/src/features/bodyPhotos/processor.ts`
- Modify: `frontend/src/features/bodyPhotos/processor.test.ts`
- Modify: `frontend/src/features/bodyPhotos/BodyPhotoWizard.tsx`
- Modify: `frontend/src/features/bodyPhotos/BodyPhotoWizard.test.tsx`
- Modify: `frontend/src/i18n/fa.ts`
- Modify: `frontend/src/i18n/en.ts`

**Interfaces:**
- Consumes: `ApiError.status`, `ApiError.message`, and compositor background options.
- Produces: RGB `[160, 163, 161]` output and an actionable `untrustedOrigin` message.

- [ ] **Step 1: Write failing tests**

Assert that processing passes `[160, 163, 161]` to background normalization and that an
`ApiError(403, "Untrusted request origin")` renders the localized trusted-origin message.

- [ ] **Step 2: Verify RED**

Run `npm run test -- --run src/features/bodyPhotos/processor.test.ts src/features/bodyPhotos/BodyPhotoWizard.test.tsx` and confirm both new expectations fail.

- [ ] **Step 3: Implement minimal behavior**

Change `neutralGray` to `[160, 163, 161]`, map the exact 403 origin error in
`uploadErrorMessage`, and add Persian/English `untrustedOrigin` translations.

- [ ] **Step 4: Verify GREEN**

Run the focused tests, then `npm run build`, `npm run lint`, and the full frontend test suite.

### Task 2: Runtime Trusted Origin

**Files:**
- Modify locally only: `backend/.env`

**Interfaces:**
- Consumes: the current LAN URL `http://10.120.36.22:5173`.
- Produces: an explicit allowed origin for FastAPI mutation requests.

- [ ] **Step 1: Reproduce the rejected request**

Send a registration or session-create request with the active LAN Origin and confirm HTTP 403.

- [ ] **Step 2: Update local runtime configuration**

Add `http://10.120.36.22:5173` to `FRONTEND_ORIGINS` in ignored `backend/.env` without changing other values.

- [ ] **Step 3: Restart and verify**

Restart the backend, confirm the same Origin passes the security boundary, apply migrations, and verify Vite-to-API traffic.

### Task 3: Commit and Publish

**Files:**
- Commit only tracked source, tests, and documentation.

**Interfaces:**
- Consumes: verified Tasks 1 and 2.
- Produces: a focused commit on `main` pushed to `origin/main`.

- [ ] **Step 1: Review scope and secrets**

Run `git diff --check` and confirm `backend/.env` is not staged.

- [ ] **Step 2: Commit and push**

Commit with `fix(body-analysis): allow phone uploads and darken background`, then push `main`.
