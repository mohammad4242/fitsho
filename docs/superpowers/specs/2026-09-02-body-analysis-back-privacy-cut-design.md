# Body Analysis Back Privacy Cut Design

## Goal

Raise the privacy crop boundary for back-view body photos so the shoulder and
trapezius area remains visible while the existing front and side behavior stays
unchanged.

## Root Cause

The visible privacy line and the upload/camera crops share a default cut ratio
of `0.16`. The back Ghost asset begins at roughly `0.09` of the source height,
so the current boundary removes part of the shoulders and upper back.

## Design

- Keep `GHOST_PRIVACY_CUT_RATIO = 0.16` as the unchanged front/side default.
- Add a back-only ratio of `0.08`, high enough to preserve the shoulder area.
- Centralize view selection in `ghostPrivacyCutRatioForView(view)`.
- Use the selected ratio for the visible Ghost privacy line, upload editor
  output dimensions, and camera capture crop.
- Use the same selected ratio in live-pose framing guidance so its warning does
  not contradict the displayed line.
- Preserve the existing output format, Ghost transforms, side-profile mirror,
  backend API, storage behavior, and all non-back-view behavior.

## Verification

- Unit-test the back render plan and output height.
- Unit-test back versus front overlay line positions.
- Unit-test upload renderer view propagation.
- Unit-test back camera crop dimensions and source offset.
- Unit-test the back live-pose boundary.
- Run the focused body-photo tests, then the full frontend test, lint, and build
  commands.
