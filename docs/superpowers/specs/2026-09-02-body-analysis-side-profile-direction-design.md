# Body Analysis Side-Profile Ghost Direction

## Scope

Add a two-state side-profile control to the Body Analysis photo capture step.
The default state remains right profile. Selecting the left profile horizontally
mirrors the existing side Ghost in both the guided camera and upload framing
editor. The uploaded photo, browser processing, backend view value, storage, and
analysis contracts remain unchanged.

## Design

`BodyPhotoWizard` owns a `right | left` side-profile direction state so the
selection survives switching between upload and guided camera. It renders the
control only for the `side` step and passes the direction to
`GhostPhotoEditor` and `GhostCameraCapture`.

`GhostOverlayGuide` receives the direction and applies a horizontal flip to its
existing asset frame while preserving the current uniform Ghost scale. The
default prop value is `right`, keeping all existing callers and views unchanged.

The visible control reports the current selection and uses an accessible pressed
state. Translations are added for Persian and English labels.

## Error handling and boundaries

There is no new failure path or network request. Direction changes are local UI
state only. Existing upload, camera, privacy crop, pose guidance, processing,
and consent behavior is retained exactly as-is.

## Verification

Add focused regression coverage that verifies:

- the side Ghost remains unflipped by default;
- selecting left applies `scaleX(-1)` while preserving Ghost scale;
- the wizard exposes the control only on the side step and forwards the
  selected direction to the Ghost consumers;
- front and back capture behavior is unchanged.

Run the focused Body Photos Vitest files, then the frontend lint and build.
