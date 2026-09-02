# Body Photo Ghost Upload Editor

Status: approved by the product owner on 2026-09-02.

## Goal

Give members a privacy-first editor for uploaded body photos. The editor reuses
the existing front, side, and back Ghost guides so a member can place a photo
approximately inside the guide before the existing local standardization and
upload pipeline runs.

The final uploaded asset is a clean, fixed composition. The Ghost is a visual
guide only and is never written into the image pixels.

## Product decisions

- Use the existing Ghost silhouettes and privacy-cut line for all three views.
- Open the editor after a file is selected from the upload control.
- Support touch and pointer drag, zoom, rotation, and reset.
- Treat a 15% framing tolerance around the Ghost safe envelope as a soft guide.
  Approximate placement is not rejected by the editor.
- Keep the existing body-photo processor as the final quality, view, landmark,
  and segmentation validation boundary.
- Crop the top privacy region using the existing 18% privacy-cut ratio before
  the clean output is processed.
- Keep the original selected file in browser memory only until the member
  confirms the edited result. Do not upload it or persist its transform.
- Keep the existing live-camera flow unchanged. Camera captures already use the
  Ghost overlay and privacy crop.
- Do not add a backend endpoint, database column, migration, face detection,
  or body-analysis rule.

## User flow

1. The member selects a JPEG, PNG, or WebP in the current front, side, or back
   upload step.
2. Fitsho opens a fixed portrait editor with the selected image below the
   matching Ghost guide.
3. The member drags the image, changes zoom, rotates it, or resets the edit.
   The guide remains fixed while the image moves beneath it.
4. The editor displays a non-blocking framing status. The member may confirm
   an approximate fit; the 15% tolerance is guidance rather than a brittle
   rejection rule.
5. On confirmation, a Canvas renderer creates a clean JPEG from the visible
   composition, excludes the Ghost pixels, removes the top privacy region, and
   passes that file into the existing `BodyPhotoProcessor`.
6. Existing processing feedback remains authoritative. If the standardized
   result lacks required landmarks, has the wrong view, or fails quality checks,
   the member receives the existing localized error and can edit or choose
   another photo.
7. Cancel returns to the upload control without uploading the source file.

## Component and module boundaries

### `GhostPhotoEditor`

Owns the editor interaction and accessible controls. It receives the source
file and view, renders the fixed guide, owns the draft transform, and returns a
new clean JPEG only after confirmation. It does not know about API sessions or
consent.

### Ghost guide presentation

Reuse `GhostOverlayGuide` and its existing semantic front/side/back SVG paths.
The overlay remains `pointer-events: none`, is fixed to the viewport, and is
never part of Canvas rendering.

### Transform/output utility

Keep transform math and Canvas rendering separate from React. The pure layer
clamps translation, scale, and rotation, exposes a deterministic CSS transform,
and renders a fixed portrait output with a neutral background. The renderer
accepts an injectable runtime seam so output behavior can be tested without a
real browser Canvas.

### `BodyPhotoWizard`

Owns the upload-to-editor transition. It passes confirmed editor output to the
existing `processFile` path, preserving the current processor, preview,
consent, session, and upload behavior. Camera files continue directly through
the current camera path.

## Transform contract

- Canonical editor viewport: portrait `2:3` at `1200 x 1800` logical output
  pixels before the privacy crop.
- Translation is measured in viewport pixels and clamped to a bounded range.
- Scale is clamped from `0.75` to `2.5` so the image cannot disappear or create
  an unusably small output.
- Rotation is clamped from `-15` to `+15` degrees.
- Pointer drag works with one active pointer. Zoom controls work on touch and
  pointer devices; keyboard-accessible buttons provide zoom, rotation, and
  reset alternatives.
- The editor uses `touch-action: none` only on the image stage and prevents
  page scrolling while an edit gesture is active.
- The soft tolerance is a framing aid around the fixed Ghost envelope; it does
  not run anatomical detection and never creates a hard editor rejection.

## Privacy and processing

The source file is represented by a revocable object URL while editing. The
confirmed output is a new JPEG rendered from the transformed image. The top
18% privacy region is excluded from that output, matching the existing live
camera capture behavior. The Ghost guide and UI labels are not drawn into the
Canvas. Existing client-side processing then normalizes the body image and
background before the normal private upload endpoint is called.

No face detection or automatic face tracking is introduced. The member remains
responsible for keeping the neck and shoulders below the privacy line; existing
landmark and quality validation remains the final safeguard.

## Error and lifecycle behavior

- Unsupported browser Canvas or image decoding returns the existing processing
  error and leaves the upload control available.
- Cancel, view changes, component unmount, and replacing a source revoke every
  object URL owned by the editor.
- Confirm disables duplicate submission while Canvas output is being produced.
- A processor rejection does not upload the unprocessed source and keeps the
  member on the current view with the localized correction message.
- Existing camera permission and secure-context fallbacks are unchanged.

## Test seams and acceptance

Test the pure transform/output seam with known image dimensions and assert:

- default transform is centered;
- translation, scale, rotation, clamping, reset, and 15% guide status are
  deterministic;
- output uses the fixed `1200 x 1800` composition before the top 18% crop, and
  the Ghost is not rendered into the output;
- the privacy crop excludes the top region.

Test the component seam for each view and assert:

- the correct Ghost guide is shown;
- drag, zoom, rotation, and reset controls update the draft composition;
- keyboard-accessible alternatives work;
- cancel does not call confirmation;
- confirmation returns a clean file and disables duplicate confirmation;
- source object URLs are released on replacement and unmount.

Test the wizard seam and assert:

- upload opens the editor before the processor or API is called;
- confirmed output enters the existing processor path;
- camera output keeps the existing direct path;
- processor errors preserve the existing localized behavior;
- front, side, and back uploads all use the matching guide.

Run the existing focused body-photo tests and the complete frontend lint,
test, and build checks after implementation.

## Out of scope

- Server-side transforms or new body-photo APIs.
- Persisting transform metadata.
- Embedding Ghost pixels in uploaded images.
- Automatic face or body alignment.
- Changing the live camera capture behavior.
- Changes to the body-analysis provider, normalized schema, review system, or
  workout engine.
