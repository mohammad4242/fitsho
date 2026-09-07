# Body Photo Neck and Upper-Back Crop Alignment Design

## Goal

Align the head-separating privacy line with the neck for side-profile photos
and move it above the neck/upper-back boundary for back-view photos, while
making the encoded crop use the exact same boundary. The alignment must hold
for both male and female Ghost assets.

## Scope

- Move the side-profile privacy anchor from `0.08` to `0.10`.
- Move the back-view privacy anchor from `0.08` to `0.06`.
- Keep the ratios view-specific and sex-independent because both Ghost variants
  consume the same normalized stage geometry.
- Preserve the existing front-view ratio, Ghost asset files, transforms, side
  mirroring, pose validation, API contracts, storage behavior, and output
  format.

## Architecture

`frontend/src/features/bodyPhotos/ghostGeometry.ts` remains the single source
of truth. `ghostPrivacyLineGeometry()` will derive the visible line from the
selected view ratio and Ghost scale. Existing consumers will continue to use
that geometry for:

- the visible `GhostOverlayGuide` privacy line;
- the photo editor's source-pixel crop and render-plan height;
- camera capture's crop boundary; and
- live pose framing guidance.

No CSS-only offset or sex-specific duplicate crop rule will be added, so the
visible line and encoded image boundary cannot drift apart.

## Verification

- Update the geometry and overlay assertions for side `10%` and back `6%`.
- Cover both male and female side/back Ghost overlays.
- Assert that the editor render plan and source crop use the same side/back
  anchors.
- Run the focused Body Photos tests, frontend lint, and frontend build.
- Inspect the rendered side and back views for both sex variants at default and
  scaled Ghost sizes.

## Non-goals

- Do not alter Ghost artwork or its per-variant CSS transforms.
- Do not change body-photo validation, analysis, API, persistence, or backend
  behavior.
- Do not change front-view privacy geometry.
