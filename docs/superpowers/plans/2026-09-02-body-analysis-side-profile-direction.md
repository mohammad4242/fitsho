# Body Analysis Side-Profile Ghost Direction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let Body Analysis users toggle the side-profile Ghost between right and left while leaving the uploaded photo and backend contracts unchanged.

**Architecture:** `BodyPhotoWizard` owns one `right | left` selection for the side step and passes it to the guided camera and upload framing editor. `GhostOverlayGuide` mirrors only its side asset when the selection is `left`; all other views and photo-processing paths retain their existing behavior.

**Tech Stack:** React 19, TypeScript, react-i18next, Vitest, Testing Library, CSS.

**Spec:** `docs/superpowers/specs/2026-09-02-body-analysis-side-profile-direction-design.md`

## Global Constraints

- The default side-profile direction is `right`.
- Selecting `left` applies only `scaleX(-1)` to the existing side Ghost and preserves the current uniform Ghost scale.
- The selected direction is local UI state; do not change the uploaded file, processor, `view: "side"`, API payloads, storage, or analysis behavior.
- Render the direction control only on the `side` capture step.
- Preserve front and back Ghost, camera, upload, privacy, consent, and live-pose behavior.
- Add Persian and English labels with accessible pressed-state semantics.

---

### Task 1: Add the shared side-profile type and Ghost mirroring

**Files:**
- Modify: `frontend/src/features/bodyPhotos/types.ts`
- Modify: `frontend/src/features/bodyPhotos/GhostOverlayGuide.tsx`
- Test: `frontend/src/features/bodyPhotos/GhostOverlayGuide.test.tsx`

**Interfaces:**
- Produces `BodyPhotoSide = "right" | "left"` for the capture components.
- `GhostOverlayGuide` accepts optional `sideProfile?: BodyPhotoSide`; omitted means `right`.

- [ ] **Step 1: Write the failing rendering regression**

Add this test after the existing Ghost scale test:

```tsx
it("mirrors only the side Ghost for a left profile", () => {
  const { container } = render(
    <GhostOverlayGuide sex="female" view="side" sideProfile="left" scale={0.95} />,
  );
  const frame = container.querySelector<HTMLElement>(".ghost-overlay__asset-frame");

  expect(frame).toHaveStyle({ transform: "scaleX(-1) scale(0.95)" });
});
```

- [ ] **Step 2: Run the focused test and verify it fails**

Run from `frontend/`:

```bash
npm run test -- src/features/bodyPhotos/GhostOverlayGuide.test.tsx
```

Expected: FAIL because `GhostOverlayGuide` does not yet accept or apply `sideProfile`.

- [ ] **Step 3: Add the type and minimal mirror implementation**

In `types.ts`, add:

```ts
export type BodyPhotoSide = "right" | "left";
```

In `GhostOverlayGuide.tsx`, import `BodyPhotoSide`, add `sideProfile = "right"` to the props, and use:

```tsx
const ghostTransform = view === "side" && sideProfile === "left"
  ? `scaleX(-1) scale(${scale})`
  : `scale(${scale})`;
```

Set `style={{ transform: ghostTransform }}` on `.ghost-overlay__asset-frame`.

- [ ] **Step 4: Run the focused test and verify it passes**

```bash
npm run test -- src/features/bodyPhotos/GhostOverlayGuide.test.tsx
```

Expected: PASS, including the existing default-scale and asset-selection tests.

- [ ] **Step 5: Commit the verified Ghost rendering unit**

```bash
git add frontend/src/features/bodyPhotos/types.ts frontend/src/features/bodyPhotos/GhostOverlayGuide.tsx frontend/src/features/bodyPhotos/GhostOverlayGuide.test.tsx
git commit -m "feat(body-analysis): mirror Ghost for left side profiles"
git push origin main
```

### Task 2: Pass the direction through camera and upload editor

**Files:**
- Modify: `frontend/src/features/bodyPhotos/GhostPhotoEditor.tsx`
- Modify: `frontend/src/features/bodyPhotos/GhostCameraCapture.tsx`
- Test: `frontend/src/features/bodyPhotos/GhostPhotoEditor.test.tsx`
- Test: `frontend/src/features/bodyPhotos/GhostCameraCapture.test.tsx`

**Interfaces:**
- Both capture components accept optional `sideProfile?: BodyPhotoSide`.
- Both pass the value unchanged to `GhostOverlayGuide`.
- Their image files, camera canvas, renderer transform, and callbacks remain unchanged.

- [ ] **Step 1: Write failing passthrough tests**

In `GhostPhotoEditor.test.tsx`, allow the helper to accept a side and add:

```tsx
it("shows the left side Ghost without changing photo framing", () => {
  const { container } = render(
    <GhostPhotoEditor
      file={sourceFile}
      view="side"
      sideProfile="left"
      onConfirm={vi.fn()}
      onCancel={vi.fn()}
      renderPhoto={renderPhoto}
    />,
  );

  expect(container.querySelector(".ghost-overlay__asset-frame")).toHaveStyle({
    transform: "scaleX(-1) scale(1)",
  });
});
```

In `GhostCameraCapture.test.tsx`, extend `renderCamera` with an optional `sideProfile` parameter and add:

```tsx
it("shows the left side Ghost in guided camera mode", () => {
  const { container, unmount } = renderCamera(vi.fn().mockResolvedValue(undefined), "left", "side");

  expect(container.querySelector(".ghost-overlay__asset-frame")).toHaveStyle({
    transform: "scaleX(-1) scale(1)",
  });
  unmount();
});
```

The helper signature should become:

```tsx
function renderCamera(
  onFileCaptured = vi.fn().mockResolvedValue(undefined),
  sideProfile: BodyPhotoSide = "right",
  view: "front" | "side" | "back" = "front",
) {
  const onFallback = vi.fn<(reason: CameraFallbackReason) => void>();
  const rendered = render(
    <GhostCameraCapture
      view={view}
      sideProfile={sideProfile}
      onFileCaptured={onFileCaptured}
      onFallback={onFallback}
      onClose={vi.fn()}
      livePoseGuideFactory={livePoseGuideFactory}
    />,
  );
  return { ...rendered, onFallback, onFileCaptured };
}
```

- [ ] **Step 2: Run the two focused tests and verify they fail**

```bash
npm run test -- src/features/bodyPhotos/GhostPhotoEditor.test.tsx src/features/bodyPhotos/GhostCameraCapture.test.tsx
```

Expected: FAIL because the components do not yet expose or forward the new prop.

- [ ] **Step 3: Add the optional prop and forward it**

Import `BodyPhotoSide` in both components, add `sideProfile?: BodyPhotoSide` to each prop type and function destructuring, then pass:

```tsx
<GhostOverlayGuide sex={sex} scale={ghostScale} sideProfile={sideProfile} view={view} />
```

Do not alter `captureFrame`, `renderPhoto(file, transform)`, or any API-facing callback.

- [ ] **Step 4: Run the focused tests and verify they pass**

```bash
npm run test -- src/features/bodyPhotos/GhostPhotoEditor.test.tsx src/features/bodyPhotos/GhostCameraCapture.test.tsx
```

Expected: PASS, including existing camera crop/mirroring and editor transform tests.

- [ ] **Step 5: Commit the verified passthrough**

```bash
git add frontend/src/features/bodyPhotos/GhostPhotoEditor.tsx frontend/src/features/bodyPhotos/GhostCameraCapture.tsx frontend/src/features/bodyPhotos/GhostPhotoEditor.test.tsx frontend/src/features/bodyPhotos/GhostCameraCapture.test.tsx
git commit -m "feat(body-analysis): pass side profile to Ghost capture flows"
git push origin main
```

### Task 3: Add the side-profile control to the wizard

**Files:**
- Modify: `frontend/src/features/bodyPhotos/BodyPhotoWizard.tsx`
- Modify: `frontend/src/i18n/fa.ts`
- Modify: `frontend/src/i18n/en.ts`
- Test: `frontend/src/features/bodyPhotos/BodyPhotoWizard.test.tsx`

**Interfaces:**
- `BodyPhotoWizard` owns `sideProfile` initialized to `"right"`.
- The control is rendered only when `view === "side"`; its `aria-pressed` value is true only for `left`.
- The current side label is shown as `نیمرخ راست` / `Right profile` or `نیمرخ چپ` / `Left profile`.

- [ ] **Step 1: Write the failing wizard interaction test**

Update the test mock for `GhostPhotoEditor` to accept `sideProfile?: "right" | "left"` and render it in a test output, then add:

```tsx
it("toggles the side Ghost from right to left and keeps the selection for upload editing", async () => {
  const user = userEvent.setup();
  const processor: BodyPhotoProcessor = {
    process: vi.fn().mockImplementation((_, selectedView) => processed(selectedView)),
  };
  renderWizard(processor);

  await uploadPhoto(user, "front");
  await user.click(screen.getByRole("checkbox", { name: /body-photo privacy and processing terms/i }));
  await user.click(screen.getByRole("button", { name: /confirm and upload front/i }));

  const toggle = await screen.findByRole("button", { name: /side profile: right profile/i });
  expect(toggle).toHaveAttribute("aria-pressed", "false");
  await user.click(toggle);
  expect(toggle).toHaveAttribute("aria-pressed", "true");
  expect(toggle).toHaveTextContent("Left profile");

  await user.upload(screen.getByLabelText(/side photo upload/i), file);
  expect(await screen.findByTestId("ghost-side-profile")).toHaveTextContent("left");
});
```

Also assert that the control is absent in the initial front step with:

```tsx
expect(screen.queryByRole("button", { name: /side profile/i })).not.toBeInTheDocument();
```

- [ ] **Step 2: Run the wizard test and verify it fails**

```bash
npm run test -- src/features/bodyPhotos/BodyPhotoWizard.test.tsx
```

Expected: FAIL because the side-profile control and prop wiring do not yet exist.

- [ ] **Step 3: Add translations and local wizard state**

Add this shape under `bodyPhotos` in both locale files:

```ts
sideProfile: {
  right: "Right profile",
  left: "Left profile",
  toggleLabel: "Side profile: {{side}}",
},
```

Use Persian equivalents `نیمرخ راست`, `نیمرخ چپ`, and `جهت نیمرخ: {{side}}` in `fa.ts`.

In `BodyPhotoWizard.tsx`, import `BodyPhotoSide`, add:

```tsx
const [sideProfile, setSideProfile] = useState<BodyPhotoSide>("right");
```

Render the control before the editor/camera conditional:

```tsx
{view === "side" && (
  <button
    className="secondary-button"
    type="button"
    aria-label={t("bodyPhotos.sideProfile.toggleLabel", {
      side: t(`bodyPhotos.sideProfile.${sideProfile}`),
    })}
    aria-pressed={sideProfile === "left"}
    onClick={() => setSideProfile((current) => current === "right" ? "left" : "right")}
    disabled={busy || sessionLoading}
  >
    {t(`bodyPhotos.sideProfile.${sideProfile}`)}
  </button>
)}
```

Pass `sideProfile={sideProfile}` to both `GhostPhotoEditor` and `GhostCameraCapture`.
Do not add any side value to `uploadBodyPhoto`, `processor.process`, or session models.

- [ ] **Step 4: Run the wizard test and verify it passes**

```bash
npm run test -- src/features/bodyPhotos/BodyPhotoWizard.test.tsx
```

Expected: PASS, including the existing three-view workflow and upload contract assertions.

- [ ] **Step 5: Commit the verified user control**

```bash
git add frontend/src/features/bodyPhotos/BodyPhotoWizard.tsx frontend/src/features/bodyPhotos/BodyPhotoWizard.test.tsx frontend/src/i18n/fa.ts frontend/src/i18n/en.ts
git commit -m "feat(body-analysis): add side-profile Ghost toggle"
git push origin main
```

### Task 4: Run final scoped verification

**Files:**
- Verify: `frontend/src/features/bodyPhotos/GhostOverlayGuide.test.tsx`
- Verify: `frontend/src/features/bodyPhotos/GhostPhotoEditor.test.tsx`
- Verify: `frontend/src/features/bodyPhotos/GhostCameraCapture.test.tsx`
- Verify: `frontend/src/features/bodyPhotos/BodyPhotoWizard.test.tsx`

- [ ] **Step 1: Run the full Body Photos focused suite**

```bash
npm run test -- src/features/bodyPhotos/GhostOverlayGuide.test.tsx src/features/bodyPhotos/GhostPhotoEditor.test.tsx src/features/bodyPhotos/GhostCameraCapture.test.tsx src/features/bodyPhotos/BodyPhotoWizard.test.tsx
```

Expected: PASS with no snapshot or API-contract regressions.

- [ ] **Step 2: Run frontend lint**

```bash
npm run lint
```

Expected: exit 0.

- [ ] **Step 3: Run frontend production build**

```bash
npm run build
```

Expected: exit 0 with TypeScript and Vite compilation successful.

- [ ] **Step 4: Confirm only scoped tracked files changed**

```bash
git status --short
git diff HEAD~3..HEAD --stat
```

Expected: only the design/plan documents and the four implementation/test/locale groups described above are in the new commits; pre-existing untracked workspace files remain untouched.

- [ ] **Step 5: Report exact verification and final implementation commit**

Report the actual command results, implementation commit SHA, and that the remote push succeeded. Do not claim any backend or live-device verification because this change is frontend-only.
