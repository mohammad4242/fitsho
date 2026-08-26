# Admin exercise picker: show all exercises for a muscle

## Scope

Fix the Admin training-template exercise picker so selecting `همه حرکات این عضله`
opens the exercise list for the selected primary muscle without requiring a
muscle-focus selection.

## Existing behavior

The API already treats an omitted `muscle_focus` as a query for all exercises
with the selected `primary_muscle`. The picker currently uses `null` both for
"focus has not been selected" and "all focuses", so it remains on the focus
screen after the all-exercises button is clicked.

## Design

- Keep `selectedFocus: MuscleFocus | null` unchanged for API compatibility.
- Add an explicit local `focusSelectionComplete` state.
- Enter the focus screen only when the selected muscle has focus categories and
  `focusSelectionComplete` is false.
- Selecting a specific focus or all exercises sets `focusSelectionComplete` to
  true. The all-exercises path keeps `selectedFocus` as `null`, so the existing
  database/API query remains broad for the selected muscle.
- Returning to the muscle, region, or library root clears the completion state.
- Keep the behavior for muscles without focus subdivisions unchanged.

## Verification

Add a picker regression test that selects Upper Body → Chest → All Chest
Exercises, verifies the request contains `primary_muscle=chest` without a
`muscle_focus`, and verifies the exercise list is rendered. Run the focused
picker tests, Admin frontend tests, typecheck, and build.
