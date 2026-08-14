# Owner Video Importer Design

## Goal

Import owner-provided MP4 exercise demonstrations from `exercise-import/raw/` without
changing the originals. Identify each movement with Codex image analysis, reuse Fitsho's
exercise catalogue and media architecture, and make dry-run and apply executions safe,
idempotent, resumable, and reviewable.

The implementation must not import the full set of 272 videos while it is being built or
tested.

## Existing architecture to reuse

- Keep `Exercise`, its controlled taxonomy enums, normalized association rows, and
  `ExerciseMediaAsset` as the catalogue source of truth.
- Reuse the existing `ffprobe` configuration, media signature checks, SHA-256 utilities,
  atomic file publication pattern, `settings.media_root`, and `/media` public-path convention.
- Keep the Free Exercise DB importer unchanged. The owner-video importer is a separate CLI
  workflow beside it, sharing reusable helpers where their contracts match.
- Store accepted files on disk rather than in PostgreSQL.

## Schema changes

- Add nullable `source` and `source_id` columns to `ExerciseMediaAsset`.
- Add a unique constraint on `(source, source_id)` so the SHA-256 identity of one original
  owner video cannot be attached twice.
- Owner assets use `source="owner-video"` and the lowercase SHA-256 digest of the original
  MP4 as `source_id`.
- Add `unspecified` to `MediaPresentation`. Codex selects `male` or `female` when sufficiently
  confident and the importer uses `unspecified` when that classification is uncertain.
- Existing assets remain valid because the new provenance fields are nullable.

## Processing pipeline

The importer discovers MP4 files in a stable filename order and applies `--limit` after that
ordering. Each file is processed independently:

1. Stream the original file into SHA-256 without modifying, renaming, or deleting it.
2. Skip the file as `duplicate_videos` when an `ExerciseMediaAsset` already has the owner
   source and digest.
3. Validate the source with `ffprobe`, including a positive duration and a usable video stream.
4. Create a muted MP4 in the resumable work directory. First attempt video stream copy with
   `-map 0:v:0 -c:v copy -an`; if the container cannot be produced safely, fall back to H.264
   video encoding with no audio stream.
5. Validate the muted output with `ffprobe` and require zero audio streams.
6. Extract five JPEG frames near 10%, 30%, 50%, 70%, and 90% of the duration.
7. Run Codex analysis using those frames, the allowed Fitsho taxonomy values, and a compact
   snapshot of active exercises and their aliases, equipment, targeting, and programming data.
8. Parse and validate the structured result before opening any database write transaction.
9. In `--apply` mode, publish the accepted muted file under
   `var/media/owner-video/<digest-prefix>/<digest>.mp4` and persist one database transaction
   for that video.

Work and analysis cache files are keyed by the original digest and kept below a gitignored
workspace directory. A cache entry includes an analysis-schema version and prompt version;
stale or invalid cache entries are ignored and regenerated. `--dry-run` may create this cache
and the requested report, but it never writes to the database or accepted media storage.

## Codex invocation

Python invokes the locally authenticated Codex CLI as a subprocess. The command uses:

- `codex exec`
- one `--image` argument for each extracted frame
- `--output-schema` with the importer's JSON Schema
- `--output-last-message` for the final JSON document
- `--ephemeral`
- `--sandbox read-only`
- a fixed prompt that prohibits file changes and requires analysis only

The subprocess receives no database credentials. Its working directory contains only the
analysis inputs needed for the current video. The executable and model are configurable, while
safe defaults use `codex` and the locally configured Codex model.

## Structured analysis contract

The strict JSON result contains:

- source digest echoed from the request
- identified English and Persian names
- visible exercise text and aliases
- identification confidence and review reasons
- `male`, `female`, or `unspecified` presentation with confidence
- every required Fitsho taxonomy field
- English and Persian instructions and safety notes within current model constraints
- secondary muscles, equipment, cautions, descriptions, cues, mistakes, and breathing data
- match decision, match confidence, and an optional existing exercise UUID

Python validates the document with Pydantic, verifies that every enum is allowed, verifies that
the echoed digest matches, and rejects existing exercise IDs that were not in the supplied
catalogue snapshot.

An existing match is accepted only when Codex marks it as confident and deterministic catalogue
evidence corroborates it. Corroboration uses normalized names or aliases plus compatible
taxonomy and equipment. Confidence alone is insufficient. No fuzzy guess may attach media to an
existing exercise.

## Database behavior

### Confirmed existing exercise

- Do not create another `Exercise`.
- Append an `ExerciseMediaAsset` with role `video`, the classified presentation, owner
  provenance, and the next `sort_order` for that exercise, presentation, and role.
- Do not overwrite the exercise's primary legacy media fields or existing media assets.

### Confirmed new exercise

- Create one complete `Exercise` using only the validated structured result.
- Set owner-video provenance on the exercise and digest as its source identity.
- Set `needs_review=false` and `is_programmable=true` only when identification and required
  programming metadata are confident.
- Attach the muted video as its first normalized media asset with `sort_order=0` and mirror it
  into the required legacy primary-media fields.

### Uncertain identification or match

- Never attach the video to a possibly matching existing exercise.
- Create a new review exercise from the validated metadata.
- Set `needs_review=true` and `is_programmable=false`.
- Preserve uncertainty reasons and Codex confidence data in source metadata.
- Attach the muted video and include the record in the final review details.

## Transactions, interruption, and failures

- Process and commit one video at a time so completed items survive a later interruption.
- Stage media before the database write and publish it atomically.
- If the database transaction fails, remove newly published media for that item and roll back all
  exercise and asset rows for it.
- Existing destination files are reused only after validating their muted-video properties.
- A process interruption may leave digest-keyed work files, which are safe to reuse or replace on
  the next run.
- Invalid videos, failed media commands, Codex failures, invalid JSON, and database failures are
  recorded under `failed`; processing then continues with the next file when safe.
- Write the final JSON report through a temporary sibling file and atomic replacement.

## CLI contract

The module accepts exactly one execution mode:

- `--dry-run`: analyze and report without database or accepted-media writes.
- `--apply`: persist accepted records and media.

Both modes accept:

- `--source-root`, defaulting to `../exercise-import/raw` when run from `backend/`
- `--limit N`, requiring a positive integer
- `--report PATH`, requiring an explicit report destination for auditable runs

The report contains these required counters:

- `total`
- `processed`
- `matched_existing`
- `created_new`
- `duplicate_videos`
- `needs_review`
- `failed`

It also contains per-file results, review reasons, failure messages, source digests, exercise IDs,
and media paths without secrets or raw Codex credentials.

## Tests

- Generate a small audio-and-video fixture with ffmpeg, mute it, and prove with ffprobe that the
  output has a video stream and no audio stream.
- Prove original input bytes remain unchanged.
- Test digest duplicate detection and the database uniqueness constraint.
- Test idempotent reruns without duplicate exercises, assets, or media files.
- Test confirmed existing matching and next `sort_order` selection.
- Test complete new exercise creation and first media asset behavior.
- Test uncertain identification, uncertain matching, and `unspecified` presentation behavior.
- Test strict JSON, enum, digest, catalogue-ID, and deterministic match validation before writes.
- Test database rollback and newly published file cleanup after a forced failure.
- Test per-file failure isolation and continuation.
- Test `--dry-run`, `--apply`, positive `--limit`, required `--report`, report counters, and atomic
  report writing.
- Test the Codex command arguments with an injected subprocess runner; automated tests never call
  the real Codex service.
- Use generated temporary fixtures only; never process the 272 owner videos in the test suite.

## Required configuration

- `ffprobe` and `ffmpeg` executables available locally.
- A locally installed and authenticated Codex CLI.
- Optional settings for the Codex executable, Codex model, subprocess timeout, ffmpeg executable,
  frame count, and confidence thresholds. Defaults remain conservative and local-development
  friendly.
