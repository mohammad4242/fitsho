# Body Photo Privacy Flow Design

## Goal

Replace automatic head cropping with an on-device, privacy-first pipeline that accepts a user-cropped headless photo, validates real body landmarks, normalizes its background, and sends only the standardized derivative to Fitsho and the AI provider.

## Architecture

The browser decodes and EXIF-normalizes the selected JPEG, PNG, or WebP. It measures lighting and sharpness, runs MediaPipe Pose Landmarker for up to two people, checks required shoulders, arms, torso/hips, knees, ankles, and feet, then runs MediaPipe Image Segmenter and composites the unchanged foreground pixels onto neutral gray. It never detects, crops, or reasons about the face or head.

View classification remains conservative. Deterministic logic rejects a clearly contradictory view, but an ambiguous result is uploaded and left to the existing semantic AI preflight. The existing three-view wizard remains required for submission; the AI pipeline may continue with two usable views after preflight.

The backend validates only measurable file properties: supported content, signature, byte size, EXIF-normalized geometry, pixel count, portrait geometry, and decodability. It stores only the standardized derivative. Crop headers, hashes, crop geometry, crop confidence, and crop-specific database fields are removed through one migration.

## Deterministic validation contract

The browser returns actual landmark visibility/confidence derived from the MediaPipe result. Missing landmarks map to specific errors:

- both shoulders: `shoulders_not_visible`
- hips/torso: `torso_not_visible`
- knees, ankles, or feet: `legs_or_feet_not_visible`
- any material body boundary outside the frame: `body_out_of_frame`
- two detected poses: `multiple_people_detected`
- insufficient sharpness: `image_too_blurry`
- insufficient or excessive light: `insufficient_lighting`
- clear requested-view contradiction: `unexpected_body_view`

No confidence, completeness, or view value is synthesized. A detector failure is actionable and blocks upload because the privacy-preserving derivative cannot be produced safely.

## Background normalization

The segmenter supplies a real person mask. The browser draws the source image once at its normalized aspect ratio, then replaces only background pixels with `#B7BAB8`. No crop, geometry transform, generative fill, beautification, sharpening, or anatomy-changing filter is applied. The output is a high-quality JPEG capped to 1200 pixels wide while preserving the full image aspect ratio.

## User interface

Above the upload controls, show the prominent Persian instruction exactly:

> لطفاً حتماً قبل از ارسال عکس، عکس را کراپ کرده و چهره را حذف کنید

A compact body-coverage guide visually groups the required retained areas: shoulders and arms, waist and hips, legs and knees, ankles and feet. Camera capture is removed because the product requires the user to crop on the phone before selecting the image. Preview copy states that the selected headless image is processed locally and only the gray-background derivative is uploaded.

## AI boundary

The preflight prompt receives standardized headless images and handles semantic ambiguity: requested view, clothing obstruction, clutter that materially obscures the body, and uncertain framing. It must not reject harmless clutter. It accepts at least two usable views and reports view-specific actionable reasons. The physique prompt keeps the current non-medical restrictions and must not infer identity, age, health, diagnosis, or body-fat percentage.

## Data migration

Drop `crop_confidence`, `client_crop_confirmed`, `server_geometry_checked`, `crop_original_height`, `crop_top`, `crop_bottom`, `processed_sha256`, and `crop_evidence_sha256` plus their crop constraints. Existing standardized files and photo identity remain intact. Downgrade restores nullable-compatible legacy columns with safe defaults but cannot reconstruct historical crop evidence.

## Testing

Frontend tests cover real-result adapters and processor policy for valid front/side/back headless portraits, shoulders retained, missing shoulders, missing legs/feet, blur, lighting, high-resolution input, EXIF-normalized input, harmless clutter, multiple people, exact neutral-gray compositing, no FaceDetector/BlazeFace path, and no crop evidence headers. Backend tests cover the simplified upload contract, high-resolution and EXIF JPEG handling, normalized-only storage, migration shape, AI preflight with two usable views, and removal of crop-based comparison inputs.

