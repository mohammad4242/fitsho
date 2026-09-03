# Body muscle highlighting visual-mask redesign

## Status

Approved direction: conservative contours. The selected region must stay inside
the visible anatomical boundary when the source artwork has a soft transition.

## Scope

Replace the current selected hit-region fill with an artwork-aligned visual mask
layer for the interactive Body Analysis map. Preserve the existing region
semantics, artwork choices, front/back behavior, keyboard interaction, and
selection insight.

## Architecture

The map has three independent layers inside one fixed-ratio frame:

1. The original `body1` artwork remains the base image.
2. A duplicate of that exact artwork is shown only when a region is selected.
   The duplicate is clipped by an anatomical SVG mask and colorized with a
   translucent turquoise treatment so the original shading remains visible.
3. The existing forgiving SVG hit areas remain on top, but have no visible fill,
   stroke, hover treatment, selected treatment, or geometry transform.

The artwork and both SVG layers use the same `853 0 853 1280` coordinate frame,
the same absolute frame, and the same aspect ratio. The visual layer never
receives pointer events; all interaction remains owned by the hit layer.

## Mask assets

Masks live under `frontend/src/assets/body-masks/` in four view-specific
directories:

- `male-front/`
- `male-back/`
- `female-front/`
- `female-back/`

Each logical region has one transparent SVG mask for each artwork/view where it
is available. The mask root uses the artwork dimensions and contains one or
more white paths for the logical region. Paths are hand-traced conservatively
against the exact final JPEG, including separate left/right paths where needed.

## Component and style changes

`bodyMapRegions.ts` owns the artwork-to-mask mapping. `BodyAreaMap.tsx` renders
the selected masked artwork separately from the hit SVG and exposes the
selected area on the visual layer for regression tests. `bodyPhotos.css`
keeps the two layers aligned and uses alpha masking plus controlled opacity and
blending; it does not use thick borders, polygon strokes, or hit-path scaling.

## Verification

`BodyAreaMap.test.tsx` will verify that selection creates a masked visual layer,
leaves the hit paths invisible and unselected, preserves the original artwork,
and resolves the correct mask for male/female front/back views. Existing
pointer, keyboard, view-switch, and insight assertions remain. The finished
map will also be visually inspected at responsive sizes for all four approved
artworks, with special review of shoulders, chest, arms, lats, quads,
hamstrings, glutes, and calves.
