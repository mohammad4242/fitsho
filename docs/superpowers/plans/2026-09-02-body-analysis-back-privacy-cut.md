# Body Analysis Back Privacy Cut Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Raise the privacy crop line for back-view body photos and keep the displayed line, upload output, camera output, and live guidance aligned.

**Architecture:** Keep the existing `0.16` ratio as the front/side default and add a view-aware helper returning `0.08` for `back`. Pass the selected view through the existing Ghost editor and camera paths; do not change backend contracts or storage behavior.

**Tech Stack:** React 19, TypeScript, Vitest, CSS, existing Ghost photo canvas and MediaPipe guidance code.

**Spec:** `docs/superpowers/specs/2026-09-02-body-analysis-back-privacy-cut-design.md`

## Global Constraints

- Back view uses a privacy cut ratio of `0.08`.
- Front and side views retain `GHOST_PRIVACY_CUT_RATIO = 0.16`.
- The change is limited to the privacy boundary and its directly coupled consumers.
- Backend/API/storage behavior and side-profile mirroring remain unchanged.
- Tests must be written and observed failing before production implementation.
- Preserve unrelated working-tree changes and stage only task files.

---

### Task 1: Add view-aware Ghost crop geometry

**Files:**
- Modify: `frontend/src/features/bodyPhotos/ghostPhotoEditor.ts`
- Test: `frontend/src/features/bodyPhotos/ghostPhotoEditor.test.ts`

**Interfaces:**
- Consumes: `BodyPhotoView` from `frontend/src/features/bodyPhotos/types.ts`.
- Produces: `GHOST_BACK_PRIVACY_CUT_RATIO`, `ghostPrivacyCutRatioForView(view)`, `ghostEditorOutputHeightForView(view)`, and optional `view` parameters on the existing render-plan and render functions.

- [ ] **Step 1: Write the failing test**

Add a back-view geometry assertion:

```ts
it("raises the back privacy boundary in the render plan", () => {
  expect(ghostPrivacyCutRatioForView("front")).toBe(GHOST_PRIVACY_CUT_RATIO);
  expect(ghostPrivacyCutRatioForView("back")).toBe(GHOST_BACK_PRIVACY_CUT_RATIO);
  expect(ghostEditorOutputHeightForView("back")).toBe(1656);

  expect(createGhostPhotoRenderPlan(
    1600,
    2400,
    GHOST_EDITOR_DEFAULT_TRANSFORM,
    "back",
  )).toMatchObject({
    canvasHeight: 1656,
    privacyCutPixels: 144,
    draw: { translateY: 756 },
  });
});
```

Update the render-runtime test to pass `"front"` before its runtime argument,
and assert that a back render creates a `1656`-pixel canvas.

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
cd frontend && npx vitest run src/features/bodyPhotos/ghostPhotoEditor.test.ts
```

Expected: FAIL because the view-aware exports and render-plan argument do not
exist yet, and the desired back canvas height is not produced.

- [ ] **Step 3: Write minimal implementation**

In `ghostPhotoEditor.ts`:

```ts
import type { BodyPhotoView } from "./types";

export const GHOST_BACK_PRIVACY_CUT_RATIO = 0.08;

export function ghostPrivacyCutRatioForView(view: BodyPhotoView): number {
  return view === "back" ? GHOST_BACK_PRIVACY_CUT_RATIO : GHOST_PRIVACY_CUT_RATIO;
}

export function ghostEditorOutputHeightForView(view: BodyPhotoView): number {
  return Math.round(GHOST_EDITOR_OUTPUT.height * (1 - ghostPrivacyCutRatioForView(view)));
}
```

Give `createGhostPhotoRenderPlan` and `renderGhostPhoto` a defaulted
`view: BodyPhotoView = "front"`, calculate `privacyCutPixels` from the selected
ratio, and use `ghostEditorOutputHeightForView(view)` for the canvas height.
Keep `GHOST_EDITOR_OUTPUT_HEIGHT` as the existing front/side compatibility
constant.

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
cd frontend && npx vitest run src/features/bodyPhotos/ghostPhotoEditor.test.ts
```

Expected: PASS with the existing front geometry and the new back geometry.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/features/bodyPhotos/ghostPhotoEditor.ts frontend/src/features/bodyPhotos/ghostPhotoEditor.test.ts
git commit -m "fix(body-analysis): raise back Ghost privacy boundary"
git push origin main
```

### Task 2: Align overlay and capture consumers

**Files:**
- Modify: `frontend/src/features/bodyPhotos/GhostOverlayGuide.tsx`
- Modify: `frontend/src/features/bodyPhotos/GhostPhotoEditor.tsx`
- Modify: `frontend/src/features/bodyPhotos/GhostCameraCapture.tsx`
- Modify: `frontend/src/features/bodyPhotos/livePoseGuide.ts`
- Test: `frontend/src/features/bodyPhotos/GhostOverlayGuide.test.tsx`
- Test: `frontend/src/features/bodyPhotos/GhostPhotoEditor.test.tsx`
- Test: `frontend/src/features/bodyPhotos/GhostCameraCapture.test.tsx`
- Test: `frontend/src/features/bodyPhotos/livePoseGuide.test.ts`

**Interfaces:**
- Consumes: `ghostPrivacyCutRatioForView(view)` and `ghostEditorOutputHeightForView(view)` from Task 1.
- Produces: view-consistent visible line, upload renderer calls, camera crop, and live framing checks.

- [ ] **Step 1: Write the failing tests**

Add these focused assertions:

```tsx
it("places the back privacy line above the unchanged front line", () => {
  const back = render(<GhostOverlayGuide sex="female" view="back" />);
  expect(back.getByLabelText(/privacy cut/i)).toHaveStyle({ top: "8%" });
  back.unmount();

  const front = render(<GhostOverlayGuide sex="female" view="front" />);
  expect(front.getByLabelText(/privacy cut/i)).toHaveStyle({ top: "16%" });
});
```

Update the editor confirmation expectation to include the view argument and
add a back-view confirmation expectation with `"back"`.

Add a camera test with a `1920`-pixel-high video and `view="back"`; expect
`sourceY` to be `154`, output canvas height to be `1766`, and the crop draw call
to use those values.

Add a live-pose test where the highest valid shoulder landmark is at `y = 0.10`
for `view="back"`; expect no `body_out_of_frame` warning. This fails with the
old fixed `0.18` threshold and passes with the new back threshold.

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
cd frontend && npx vitest run \
  src/features/bodyPhotos/GhostOverlayGuide.test.tsx \
  src/features/bodyPhotos/GhostPhotoEditor.test.tsx \
  src/features/bodyPhotos/GhostCameraCapture.test.tsx \
  src/features/bodyPhotos/livePoseGuide.test.ts
```

Expected: FAIL because the UI, upload renderer, camera crop, and live guide
still use the fixed boundary or do not pass the view.

- [ ] **Step 3: Write minimal implementation**

Use `ghostPrivacyCutRatioForView(view)` for the overlay line style and camera
`sourceY`. Extend the `GhostPhotoRenderer` signature to
`(file, transform, view) => Promise<File>` and call it with the editor's view.
In `livePoseGuide.ts`, replace the module-level fixed ratio with the helper
selected inside `evaluateGuidance`.

- [ ] **Step 4: Run focused tests to verify they pass**

Run the same four-file Vitest command from Step 2. Expected: PASS with all
existing front/side tests unchanged.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/features/bodyPhotos/GhostOverlayGuide.tsx frontend/src/features/bodyPhotos/GhostPhotoEditor.tsx frontend/src/features/bodyPhotos/GhostCameraCapture.tsx frontend/src/features/bodyPhotos/livePoseGuide.ts frontend/src/features/bodyPhotos/GhostOverlayGuide.test.tsx frontend/src/features/bodyPhotos/GhostPhotoEditor.test.tsx frontend/src/features/bodyPhotos/GhostCameraCapture.test.tsx frontend/src/features/bodyPhotos/livePoseGuide.test.ts
git commit -m "fix(body-analysis): align back privacy crop consumers"
git push origin main
```

### Task 3: Run final verification

**Files:**
- Verify: all modified frontend body-photo files and the repository Git state.

**Interfaces:**
- Consumes: the completed implementation from Tasks 1 and 2.
- Produces: fresh test, lint, build, and remote synchronization evidence.

- [ ] **Step 1: Run focused and full checks**

Run:

```bash
cd frontend && npx vitest run src/features/bodyPhotos
cd frontend && npm run test
cd frontend && npm run lint
cd frontend && npm run build
```

Expected: every command exits `0`; the full test suite reports all files and
tests passing, lint reports no diagnostics, and the production build completes.

- [ ] **Step 2: Verify the final Git state**

Run:

```bash
git diff --check
git status --short --branch --untracked-files=no
git rev-parse HEAD origin/main
```

Expected: no whitespace errors, no tracked working-tree changes, and identical
local and remote commit IDs. Existing unrelated untracked files remain
untouched.

- [ ] **Step 3: Commit**

No third commit is needed when the verification-only task changes no files.
