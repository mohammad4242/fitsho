# Body Photo Neck and Upper-Back Crop Alignment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move the side-profile privacy boundary to `10%` and the back-view boundary to `6%`, with the visible line and encoded crop using the same geometry for male and female Ghost assets.

**Architecture:** Keep `frontend/src/features/bodyPhotos/ghostGeometry.ts` as the single source of truth for view-specific privacy ratios. Existing overlay, editor, and camera consumers already derive their boundary from `ghostPrivacyLineGeometry()` or `privacyCropSourceYForView()`, so the implementation changes only the two view constants and their regression expectations.

**Tech Stack:** React 19, TypeScript, Vitest, Testing Library, Vite.

**Spec:** `docs/superpowers/specs/2026-09-07-body-photo-neck-crop-alignment-design.md`

## Global Constraints

- The side-profile privacy anchor is `0.10`.
- The back-view privacy anchor is `0.06`.
- The visible line and encoded crop use the same selected view anchor.
- The ratios are view-specific and sex-independent.
- Preserve front-view geometry, Ghost artwork, transforms, side mirroring, validation, API, storage, and output format.
- Preserve unrelated dirty files, including `frontend/src/features/auth/api.test.ts` and existing untracked artifacts.

---

### Task 1: Update the shared privacy geometry and regressions

**Files:**
- Modify: `frontend/src/features/bodyPhotos/ghostGeometry.ts:4-6`
- Test: `frontend/src/features/bodyPhotos/ghostGeometry.test.ts`
- Test: `frontend/src/features/bodyPhotos/GhostOverlayGuide.test.tsx`
- Test: `frontend/src/features/bodyPhotos/ghostPhotoEditor.test.ts`
- Test: `frontend/src/features/bodyPhotos/GhostCameraCapture.test.tsx`

**Interfaces:**
- Consumes: `ghostPrivacyCutRatioForView(view)`, `ghostPrivacyLineGeometry(view, ghostScale, mirrored)`, `privacyCropSourceYForView(view, ghostScale, displaySize, sourceSize)`, and `createGhostPhotoRenderPlan(...)`.
- Produces: side overlays and captures whose boundary is `10%` at scale `1`, back overlays and captures whose boundary is `6%` at scale `1`, while front behavior remains unchanged.

- [ ] **Step 1: Write the failing tests**

  Update the geometry assertions so `ghostPrivacyCutRatioForView("side")` and
  `ghostPrivacyLineGeometry("side", 1).anchor.y` equal `0.10`, while the
  corresponding back values equal `0.06`. Keep front at `0.16`.

  In `GhostOverlayGuide.test.tsx`, render both `male` and `female` variants
  for side and back and assert the privacy line style is respectively
  `{ top: "10%" }` and `{ top: "6%" }`. Keep the existing scale assertions but
  update their expected transformed values: side scale `0.8` is `18%`, side
  scale `1.15` is `4%`, and the back default is `6%`.

  In `ghostPhotoEditor.test.ts`, update the view matrix expected source crops
  for a `1600x2400` source to `front: 384`, `side: 240`, and `back: 144`.
  Update render-plan expectations to `side: canvasHeight 1620,
  privacyCutPixels 180, sourceCropY 240, privacyLineDisplayY 180,
  draw.translateY 720` and `back: canvasHeight 1692, privacyCutPixels 108,
  sourceCropY 144, privacyLineDisplayY 108, draw.translateY 792`.

  In `GhostCameraCapture.test.tsx`, update the back capture expectation for
  the default Ghost scale to source Y `115` and output height `1805`. Add a
  side capture case using the existing `renderCamera` helper and the same
  five-second timer sequence; it must assert source Y `192` and output height
  `1728`.

- [ ] **Step 2: Run the focused tests and verify RED**

  Run from `frontend/`:

  ```bash
  npm run test -- --run \
    src/features/bodyPhotos/ghostGeometry.test.ts \
    src/features/bodyPhotos/GhostOverlayGuide.test.tsx \
    src/features/bodyPhotos/ghostPhotoEditor.test.ts \
    src/features/bodyPhotos/GhostCameraCapture.test.tsx
  ```

  Expected result: the updated side/back assertions fail because the current
  shared constants still use `0.08`; failures must be assertion failures, not
  test discovery or TypeScript errors.

- [ ] **Step 3: Implement the minimal geometry change**

  In `ghostGeometry.ts`, change only the view constants:

  ```ts
  export const GHOST_SIDE_PRIVACY_CUT_RATIO = 0.10;
  export const GHOST_BACK_PRIVACY_CUT_RATIO = 0.06;
  ```

  Do not add CSS offsets, sex-specific constants, asset changes, or new crop
  calculations. Existing consumers must continue using the shared helper.

- [ ] **Step 4: Run the focused tests and verify GREEN**

  Re-run the exact focused command from Step 2. Expected result: all selected
  Body Photos tests pass, including both male/female overlay cases and the
  editor/camera crop assertions.

- [ ] **Step 5: Inspect the actual render**

  Start the frontend dev server with `npm run dev`, open the Body Analysis
  photo flow, and inspect side and back views for both male and female profiles
  at Ghost scales `1.0`, `0.8`, and `1.15`. Confirm the line sits on the
  middle neck boundary in side view, above the upper-back/trapezius boundary
  in back view, and that the resulting preview/captured image starts at the
  same line. Stop the server after inspection.

- [ ] **Step 6: Run final scoped verification**

  From `frontend/`, run:

  ```bash
  npm run test -- --run
  npm run lint
  npm run build
  ```

  Also run from the repository root:

  ```bash
  git diff --check
  git status --short --branch --untracked-files=all
  ```

  Confirm the only tracked source changes are the shared geometry and its
  focused regression tests; the pre-existing auth test modification and
  untracked artifacts remain untouched.

- [ ] **Step 7: Commit and push the implementation**

  Before committing, stage only the implementation and test files listed in
  this task. Use:

  ```bash
  git add frontend/src/features/bodyPhotos/ghostGeometry.ts \
    frontend/src/features/bodyPhotos/ghostGeometry.test.ts \
    frontend/src/features/bodyPhotos/GhostOverlayGuide.test.tsx \
    frontend/src/features/bodyPhotos/ghostPhotoEditor.test.ts \
    frontend/src/features/bodyPhotos/GhostCameraCapture.test.tsx
  git commit -m "fix(bodyPhotos): align side and back privacy crops"
  git push origin main
  ```

  Verify the commit succeeded and `git rev-list --left-right --count
  HEAD...origin/main` reports `0 0`.
