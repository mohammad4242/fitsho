# Body Ghost top privacy-cut design

## Goal

In web and Android Body Analysis, the visible privacy line and the encoded photo crop must touch the upper visible edge of the headless Ghost for front, side, and back views for male and female assets.

## Geometry

- The six Ghost JPEGs are byte-identical between web and Android.
- Each asset receives a deterministic `visibleTopRatio`, measured from the first image row whose luminance reaches 16/255.
- Asset scale, vertical calibration, and visible-top metadata live in `@fitician/core`.
- A shared pure helper composes the asset calibration with the user Ghost scale and returns the final privacy-line geometry.
- The visible line, editor render plan, native renderer, encoded crop, and pose bounds continue consuming that same geometry. No consumer may keep an independent crop ratio.
- Neutral profiles continue using male artwork geometry.

## Rendering

- Web and Android consume the shared asset calibration instead of maintaining CSS/mobile copies.
- Moving or resizing the Ghost moves the line with the same transform.
- The Ghost remains a pose and position guide. This change adds no face detection, body-shape validation, API change, storage change, or analysis-model change.

## Verification

- Start with failing table tests for all six sex/view combinations.
- Verify line and encoded crop use the same computed Y coordinate at minimum, default, and maximum Ghost scale.
- Run focused core, web Body Photo, and Android Body Analysis tests, then typecheck/build checks.
- Inspect a rendered front, side, and back example for both sexes when a runnable browser/device surface is available; do not claim physical-device success without a handset run.
