# Side Pose Validation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Accept valid headless side photos with one visible body side and reject only credible, distinct multiple-person detections.

**Architecture:** Preserve the existing browser-side MediaPipe pipeline. Return all real pose candidates from the detector, select credible and distinct candidates in the processor, then apply view-aware landmark requirements to the selected primary pose before segmentation and AI preflight.

**Tech Stack:** React 19, TypeScript, MediaPipe Tasks Vision, Vitest

## Global Constraints

- Front and back continue to require both sides of every required body group.
- Side requires one visible shoulder, elbow, hip, knee, ankle, and foot.
- Hidden far-side landmarks must not fail visibility or frame checks.
- Only a credible, materially sized, spatially distinct second pose causes deterministic rejection.
- Ambiguous cases continue to semantic AI preflight.
- No face/head detection, fabricated confidence, or generative image editing.

---

### Task 1: Real Pose Candidate Selection

**Files:**
- Modify: `frontend/src/features/bodyPhotos/processor.ts`
- Modify: `frontend/src/features/bodyPhotos/mediaPipePoseDetector.ts`
- Test: `frontend/src/features/bodyPhotos/mediaPipePoseDetector.test.ts`
- Test: `frontend/src/features/bodyPhotos/processor.test.ts`

**Interfaces:**
- Produces: `BodyLandmarkDetection = { poses: NormalizedBodyLandmark[][] }`
- Produces: processor-side primary pose selection and clear multiple-person rejection.

- [ ] **Step 1: Write failing detector contract tests**

Change detector assertions to require every real MediaPipe candidate without inventing scores:

```ts
expect(result.poses).toEqual([primary, secondary]);
```

- [ ] **Step 2: Write failing processor tests**

Add cases that accept overlapping duplicate candidates and weak secondary candidates, and reject
two credible candidates whose body boxes are spatially distinct and at least 25% of the primary
body-box area.

- [ ] **Step 3: Run tests and verify RED**

Run:

```bash
npm run test -- --run src/features/bodyPhotos/mediaPipePoseDetector.test.ts src/features/bodyPhotos/processor.test.ts
```

Expected: FAIL because the detector still exposes `personCount/landmarks` and every second pose
is rejected.

- [ ] **Step 4: Implement candidate selection**

Update the detector to return raw `poses`. In the processor:

```ts
const credible = poses.filter(isCrediblePose).sort((a, b) => poseArea(b) - poseArea(a));
const distinct = suppressOverlappingPoses(credible);
if (distinct.length > 1 && poseArea(distinct[1]!) >= poseArea(distinct[0]!) * 0.25) {
  throw new BodyPhotoProcessingError("multiple_people_detected");
}
```

`isCrediblePose` must require 33 real landmarks, a visible shoulder, hip, elbow, and at least two
of knee/ankle/foot at the existing `0.55` threshold. `suppressOverlappingPoses` must treat body
boxes with intersection-over-union of at least `0.6` as duplicate detections.

- [ ] **Step 5: Run focused tests and verify GREEN**

Run the focused command from Step 3. Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/features/bodyPhotos/processor.ts \
  frontend/src/features/bodyPhotos/processor.test.ts \
  frontend/src/features/bodyPhotos/mediaPipePoseDetector.ts \
  frontend/src/features/bodyPhotos/mediaPipePoseDetector.test.ts
git commit -m "fix(body-analysis): filter duplicate pose detections"
```

### Task 2: View-Aware Side Landmark Validation

**Files:**
- Modify: `frontend/src/features/bodyPhotos/processor.ts`
- Test: `frontend/src/features/bodyPhotos/processor.test.ts`

**Interfaces:**
- Consumes: primary `NormalizedBodyLandmark[]` selected by Task 1.
- Produces: side-aware visibility, frame checks, and `minimumLandmarkVisibility`.

- [ ] **Step 1: Write failing side-view tests**

Add tests where the far-side shoulder, elbow, hip, knee, ankle, and foot have visibility `0.1`
and coordinates outside the frame while the near-side landmarks remain valid. The side photo must
pass. Add one test where both elbows have visibility `0.1`; it must fail with
`arms_not_visible`.

- [ ] **Step 2: Run tests and verify RED**

Run:

```bash
npm run test -- --run src/features/bodyPhotos/processor.test.ts
```

Expected: FAIL because side validation currently requires both landmarks and frame-checks hidden
far-side points.

- [ ] **Step 3: Implement group selection**

For side views, select the highest-visibility landmark in each required group and validate only
those selected points. For front/back, retain all landmarks in each group. Exclude wrists from the
side requirements. Compute frame checks and minimum visibility from exactly the required selected
points.

- [ ] **Step 4: Run focused tests and verify GREEN**

Run the focused command from Step 2. Expected: all tests pass.

- [ ] **Step 5: Run complete verification**

```bash
npm run test -- --run
npm run lint
npm run build
git diff --check
```

Expected: all frontend tests pass, lint exits zero, build exits zero, and no whitespace errors.

- [ ] **Step 6: Commit and push**

```bash
git add frontend/src/features/bodyPhotos/processor.ts \
  frontend/src/features/bodyPhotos/processor.test.ts
git commit -m "fix(body-analysis): validate one visible side of body"
git push origin main
```

### Task 3: Runtime Verification

**Files:**
- No tracked file changes.

**Interfaces:**
- Consumes: frontend assets built from Tasks 1 and 2.
- Produces: runtime evidence that the active app serves the new validator.

- [ ] **Step 1: Rebuild/restart the active frontend service if HMR is not serving the new source**

Check the Vite-served `processor.ts` for the new side-view selector and confirm frontend port
`5173` and backend port `8001` are listening.

- [ ] **Step 2: Verify Git and runtime**

Confirm local `main` equals `origin/main`, the login page returns `200`, and unrelated workspace
files remain untouched.
