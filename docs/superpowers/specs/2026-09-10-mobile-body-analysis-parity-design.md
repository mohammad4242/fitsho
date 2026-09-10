# Mobile Body Analysis Web-Parity Design

## Goal

Make the Android Body Analysis capture flow behave like the web flow:

1. Starting a new session opens the current-measurements step.
2. The user confirms height, weight, shoulder circumference, waist circumference,
   and hip circumference before a secure photo session is created.
3. Gallery selection opens a touch editor. The photo can be pinch-scaled and
   dragged under a fixed Ghost guide, while Ghost size remains independently
   adjustable.
4. The same editor remains active after a gallery photo is selected, so the
   user can change the photo framing or Ghost size before confirming it.
5. The confirmed output is a private JPEG with the selected framing rendered and
   the privacy crop applied before upload.
6. The privacy line is generated from one shared geometry contract and is
   positioned at the Ghost neck for front, side, and back guides in both male and
   female variants. The line is the top of the uploaded visible region; shoulders,
   torso, legs, and feet remain below it.

## Scope and boundaries

- Modify only the mobile Body Analysis feature and the shared Ghost geometry or
  editor contract when required by both native rendering and web parity.
- Keep the existing opaque authenticated transport, body-photo session API,
  consent flow, resumable draft store, and private media rules.
- Do not add face detection, automatic face cropping, body-shape rejection, or
  server-side image processing.
- Preserve unrelated working-tree changes.

## Design

### Wizard and measurements

BodyAnalysisWizard keeps BodyAnalysisRequirements as the first phase for new
sessions. The requirements screen reads the current profile, validates the same
shared fields and ranges as web, saves only changed values through the existing
profile PATCH endpoint, and creates the body-photo session only after explicit
confirmation. Resumed sessions continue directly at their first missing view.

### Native capture/editor

BodyPhotoCapture owns the per-view editing state:

- the original local picker/camera URI remains private and local until
  confirmation;
- the preview renders the source image below a non-interactive Ghost overlay;
- one-finger movement updates normalized photo translation;
- two-finger movement updates photo scale and translation;
- accessible zoom controls mirror the web controls for users who cannot pinch;
- Ghost scale controls remain enabled while the preview is visible;
- retake clears all derived files and returns to source selection.

A small pure gesture model converts touch points into normalized GhostTransform
limits. This keeps gesture math testable without a device.

### Native output and privacy

The existing react-native-nitro-image dependency is used as the native pixel
renderer. It loads the local source, applies the selected scale/translation and
rotation into a fixed editor canvas, paints the same neutral background used by
web, crops at the shared privacy line, and saves a JPEG in the app cache.
expo-image-manipulator remains the fallback for the existing camera-only crop
path or unsupported native renderer failures. No source URI or raw bytes are
persisted in the resumable draft.

The uploaded BodyPhotoCapturedAsset always carries privacyCropApplied: true,
has a non-empty existing local file, and contains only the final JPEG bytes.
Derived files are replaced and deleted when the user changes framing, retakes,
confirms, exits, or the component unmounts.

### Ghost geometry

The shared geometry exposes a view-aware neck anchor and applies Ghost scale
around the center. Mirroring affects only the side guide horizontally; the
privacy line stays horizontal and at the same vertical neck anchor. Native
overlay, native output, web overlay, web output, and crop-plan tests all consume
the same helper. Golden tests cover six guide combinations (front/side/back ×
male/female), scaled Ghosts, and left-side mirroring.

### Error handling

- Picker cancellation is silent.
- Invalid format, invalid dimensions, decode/render failure, and upload failure
  have separate user-visible messages.
- An upload or session failure does not discard the original local selection
  until the user retakes or exits.
- API errors retain their status-aware messages; successful uploads do not start
  analysis until all three views, consent, and submission succeed.

## Verification

- Pure tests: measurements, gesture transform/clamping, Ghost neck geometry,
  output/crop plan, and file validation.
- Native rendering tests mock only the native image bridge and verify the exact
  render sequence and privacy boundary.
- React Native tests verify the web-parity hierarchy, post-selection Ghost
  controls, pinch/drag state changes, confirmation, and upload failure recovery.
- Run focused mobile tests, core tests, mobile typecheck, lint/build-equivalent
  checks available in the repository, then perform an Android APK/runtime check
  if the local native toolchain and device/emulator are available.
