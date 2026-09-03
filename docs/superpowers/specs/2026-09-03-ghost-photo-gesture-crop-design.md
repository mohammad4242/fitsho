# Ghost photo gestures and crop alignment

## Goal

Keep the Ghost guide centered and fixed while allowing the uploaded photo to be
dragged, pinch-zoomed, and rotated in the front, side, and back editors. The
privacy crop line must move with Ghost scaling and the confirmed image must use
that exact same line.

## Design

- Keep two independent pieces of state:
  - `photoTransform`: user-photo translation, scale, and rotation.
  - `ghostScale`: centered Ghost-guide scale only.
- Apply `photoTransform` to the uploaded image preview and to the canvas render.
- Apply only `ghostScale` to the Ghost asset frame. The Ghost has no drag or
  rotation path.
- Derive the privacy line from the centered Ghost geometry with one shared
  function. Reuse it for the overlay, camera crop, and uploaded-photo render.
- Keep the existing body-photo API, storage, processor, view names, and side
  profile contracts unchanged.

## Verification

- Unit tests cover Ghost immobility, photo gestures, scale-dependent privacy
  geometry, and all three views.
- Component tests cover the upload editor and guided camera independently.
- Frontend lint, build, and the complete Vitest suite are required.
