# Body Photo Privacy Flow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the user-cropped, pose-validated, gray-background Body Analysis photo pipeline without any face detection or crop evidence.

**Architecture:** MediaPipe Pose Landmarker and Image Segmenter run in the browser before upload. FastAPI keeps independent basic image validation and stores only the standardized derivative; AI preflight owns semantic ambiguity and preserves two-view analysis.

**Tech Stack:** React 19, TypeScript, MediaPipe Tasks Vision 0.10.35, Canvas, FastAPI, Pillow, SQLAlchemy, Alembic, Vitest, pytest

## Global Constraints

- Never detect, crop, upload, or require a face/head image.
- Never fabricate confidence, completeness, or view classification.
- Never reshape, beautify, sharpen, or generatively edit anatomy.
- Keep front, side, and back; permit analysis with two AI-approved views.
- Preserve all current non-medical inference restrictions.
- Do not delegate work to subagents.

---

### Task 1: Browser landmark and segmentation adapters

**Files:**
- Replace: `frontend/src/features/bodyPhotos/mediaPipePoseDetector.ts`
- Replace: `frontend/src/features/bodyPhotos/mediaPipePoseDetector.test.ts`
- Create: `frontend/src/features/bodyPhotos/mediaPipeBodySegmenter.ts`
- Create: `frontend/src/features/bodyPhotos/mediaPipeBodySegmenter.test.ts`
- Modify: `frontend/scripts/prepare-mediapipe-assets.mjs`
- Delete: `frontend/public/mediapipe/models/blaze_face_short_range.tflite`
- Add: `frontend/public/mediapipe/models/pose_landmarker_lite.task`
- Add: `frontend/public/mediapipe/models/selfie_segmenter.tflite`

**Interfaces:**
- Produces: `MediaPipePoseLandmarkDetector.detect(image): Promise<BodyLandmarkDetection>`
- Produces: `MediaPipeBodySegmenter.segment(image): Promise<BodySegmentationMask>`

- [ ] Write adapter tests using real MediaPipe result-shaped landmarks and masks; verify BlazeFace and FaceDetector are absent.
- [ ] Run `npm run test -- src/features/bodyPhotos/mediaPipePoseDetector.test.ts src/features/bodyPhotos/mediaPipeBodySegmenter.test.ts` and confirm RED.
- [ ] Implement the loaders, exact landmark mapping, mask copying, model assets, and cleanup.
- [ ] Re-run the focused tests and confirm GREEN.

### Task 2: Headless image processor

**Files:**
- Modify: `frontend/src/features/bodyPhotos/processor.ts`
- Replace: `frontend/src/features/bodyPhotos/processor.test.ts`

**Interfaces:**
- Consumes: real `BodyLandmarkDetection` and `BodySegmentationMask`
- Produces: `ProcessedBodyPhoto { file, previewUrl, validation }` with no crop evidence

- [ ] Write failing tests for valid front/side/back, missing shoulders, missing feet, multiple people, blur, lighting, 40 MP input, EXIF-normalized input, ambiguous view allowance, and gray-background compositing.
- [ ] Run `npm run test -- src/features/bodyPhotos/processor.test.ts` and confirm RED.
- [ ] Implement measurable landmark policy and full-frame neutral-gray encoding.
- [ ] Re-run the focused test and confirm GREEN.

### Task 3: Wizard contract and privacy UI

**Files:**
- Modify: `frontend/src/features/bodyPhotos/BodyPhotoWizard.tsx`
- Modify: `frontend/src/features/bodyPhotos/BodyPhotoWizard.test.tsx`
- Modify: `frontend/src/features/bodyPhotos/api.ts`
- Modify: `frontend/src/features/bodyPhotos/api.test.ts`
- Modify: `frontend/src/features/bodyPhotos/types.ts`
- Modify: `frontend/src/features/bodyPhotos/bodyPhotos.css`
- Modify: `frontend/src/i18n/fa.ts`
- Modify: `frontend/src/i18n/en.ts`

**Interfaces:**
- Upload: multipart `file` only, with no crop headers
- UI: exact prominent Persian crop instruction and retained-body checklist

- [ ] Write failing UI/API tests for the instruction, retained landmarks, actionable errors, no direct camera capture, and no crop headers.
- [ ] Run focused wizard/API tests and confirm RED.
- [ ] Implement the privacy callout, guide, copy, API contract, and response types.
- [ ] Re-run focused tests and confirm GREEN.

### Task 4: Backend upload contract and data model

**Files:**
- Modify: `backend/app/body_photos/image_validation.py`
- Modify: `backend/app/body_photos/models.py`
- Modify: `backend/app/body_photos/router.py`
- Modify: `backend/app/body_photos/schemas.py`
- Modify: `backend/app/body_photos/service.py`
- Modify: `backend/app/config.py`
- Create: `backend/alembic/versions/20260814_77_remove_body_photo_crop_evidence.py`
- Modify: `backend/tests/body_photos/test_session_api.py`
- Modify: `backend/tests/body_photos/test_storage.py`

**Interfaces:**
- `validate_and_normalize(upload, settings) -> NormalizedBodyPhoto`
- API errors: `{ "detail": { "code": <stable code> } }` for known validation failures

- [ ] Write failing tests for upload without evidence, 40 MP consistency, EXIF rotation, known validation codes, and removed DTO/model fields.
- [ ] Run focused backend tests and confirm RED.
- [ ] Remove crop parsing/constraints/configuration, implement basic validation codes, and add the migration.
- [ ] Re-run focused tests and confirm GREEN.

### Task 5: AI preflight and comparison cleanup

**Files:**
- Modify: `backend/app/body_analysis/service.py`
- Modify: `backend/app/body_analysis/comparison_service.py`
- Modify: `backend/app/body_analysis/comparison_schemas.py`
- Modify: `backend/tests/body_analysis/test_execution_and_reviews.py`
- Modify: `backend/tests/body_analysis/test_progress_comparison.py`
- Modify: `backend/tests/body_analysis/test_providers.py`
- Modify: `frontend/src/features/bodyPhotos/BodyAnalysisResultPage.test.tsx`

**Interfaces:**
- AI gets only stored standardized derivatives.
- Comparison input quality uses real analysis confidence and complete stored-view count, not crop confidence.

- [ ] Write failing tests for standardized prompt language, harmless clutter, two usable views, and no crop-quality dependency.
- [ ] Run focused analysis tests and confirm RED.
- [ ] Simplify preflight/prepare-images and comparison quality while preserving non-medical policy.
- [ ] Re-run focused tests and confirm GREEN.

### Task 6: Full verification, migration, Git, and runtime

**Files:** all changed files

- [ ] Run frontend Body Photos tests, full frontend tests, lint, and build.
- [ ] Run backend Body Photos/Analysis tests, full pytest, Ruff, format check, and `mypy app` from `backend/`.
- [ ] Run Alembic upgrade, downgrade one revision, and upgrade; inspect the resulting columns and current head.
- [ ] Search for FaceDetector, BlazeFace, crop evidence, dead fields, and unused dependencies.
- [ ] Review the diff for unrelated files and secrets.
- [ ] Commit with `feat(body-analysis): replace face cropping with private pose validation` and push `feature/body-photo-privacy`.
- [ ] Start the backend and Vite on LAN-accessible ports; verify `/openapi.json`, the Vite page, and a proxied `/api/v1/auth/me` response.
