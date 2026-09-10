# Mobile workout single-player video previews

## Goal

Restore real exercise-video presentation in native workout rows without creating one Android
video player per exercise.

## Scope

- Generate a deterministic lightweight poster from every managed exercise video.
- Keep posters as derived media files beside their source videos; do not add database rows or a
  second media catalogue.
- Show the poster in every native workout row.
- Mount at most one inline workout-row video player at a time.
- Release the active player when another preview starts, its day closes, the plan changes, or the
  route loses focus.
- Preserve the full exercise-detail video experience, gender-aware media selection, workout data,
  and original video files.

## Backend design

The poster path is derived from a managed video path by replacing its extension with
`.poster.webp`. A media helper extracts a bounded 640-pixel WebP frame atomically with FFmpeg.
Admin uploads and both exercise import paths create the poster after publishing a video. A
repeatable CLI backfills missing posters for the existing media tree and reports created, reused,
and failed counts.

Poster generation never overwrites an existing valid poster. Failed poster generation leaves the
source video intact and is surfaced to the caller or backfill report.

## Native design

`ExerciseMedia` derives the poster URL for managed videos. Deferred workout rows render that image
without constructing a video player. `PlanView` owns the active preview identity and passes it
through each day and exercise row. Pressing a row poster activates that row and mounts its player;
pressing a different poster unmounts the previous player first. The existing details action keeps
opening the exercise detail route.

The leading day preview participates in the same single-player state. Non-video media continues to
render directly.

## Failure behavior

- Missing or failed poster: show the existing branded unavailable-media fallback.
- Failed active video: return that row to its poster when possible.
- Closing a day or changing plan: clear the active preview.
- Poster backfill failure: report the exact file and continue processing other videos.

## Verification

- Backend unit tests cover deterministic paths, atomic extraction, reuse, and failure isolation.
- Native tests prove inactive rows use posters and no video view, only the selected row mounts a
  video view, switching releases the previous view, and route blur releases the active player.
- Focused backend tests, native Jest tests, mobile typecheck, Ruff, and Git scope checks pass.
- The active runtime media tree is backfilled and representative poster URLs return WebP content.
- Physical-device RAM behavior remains a required final smoke check because host tests cannot
  measure handset decoder and GPU memory.
