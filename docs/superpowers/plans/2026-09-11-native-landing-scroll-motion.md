# Native Landing Scroll Motion Implementation Plan

## Step 1: Freeze the motion contract

- Add pure tests for chapter ranges and ordered process steps.
- Extend the native source contract to reject per-frame React state.
- Run focused tests and confirm the new assertions fail for the current code.

## Step 2: Move scroll work to the UI thread

- Add a small `landingScrollMotion` module for worklet-safe progress helpers.
- Replace `scrollOffset` React state with a Reanimated shared value and scroll
  handler.
- Convert landing scene, process, body, SVG, and scan styles to derived animated
  styles or animated props.
- Disable Android overscroll on the landing ScrollView.

## Step 3: Restore the unrelated question layout

- Restore the frame-based public-question height and its existing regression
  expectation.
- Keep this restoration isolated from landing motion behavior.

## Step 4: Verify and deliver

- Run focused motion, landing RNTL, onboarding RNTL, and presentation tests.
- Run mobile typecheck and `git diff --check`.
- Inspect the exact staged diff, commit only intended files, and push `main`.
- Report automated evidence separately from physical-device verification.
