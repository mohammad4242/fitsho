# Android Home Workout Card

## Scope

Restore the first workout card on the Fitician Android Home screen to a horizontal layout.
No API, navigation, workout selection, or media behavior changes are included.

## Presentation

- Keep the card horizontal on phone widths.
- Show the first exercise media on the right side.
- Show the workout copy on the left side.
- Use the current workout day's real Persian title, such as `سینه + جلو بازو` or `بالاتنه`.
- Preserve the day number, estimated duration, plan status, and workout action.
- Preserve the existing empty, loading, offline, stale, and error states.

## Data Flow

`MemberHomeScreen` continues to select the current day through `currentWorkoutDay` and passes it to
`WorkoutTodayCard`. The card continues to use the first exercise's existing media fields and the
day's `title_fa`, with `title_en` and `تمرین امروز` as fallbacks.

## Verification

- Add a focused component test that proves the phone layout is horizontal and the media is on the
  right in RTL presentation.
- Prove the real Persian workout-day title is rendered.
- Run the focused Home tests, mobile typecheck, and mobile lint.
