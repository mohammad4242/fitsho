# Body Analysis Schema v2

## Goal

Replace the model response contract for body-photo analysis with a coach-oriented
visual assessment while preserving all persisted version 1 analysis results.

## Scope

- Accept a structured v2 model result with per-view quality, overall visual
  assessment, and exactly 13 body-area findings.
- Allow analysis when two of three views are usable; mark the result `partial`.
- Retain the current per-view rejection response when fewer than two views are
  usable.
- Store v2 results with `schema_version` `2.0`.
- Convert the v2 result to the existing workout-personalization contract so the
  workout engine continues to consume strengths, priorities, attention areas,
  uncertainty, severity, and training emphasis.
- Show the richer v2 assessment in the member result page.

## Model Response Contract

The provider response owns only model-observed data:

- `assessment_status`: `complete` or `partial`.
- `photo_quality`: usable state and concise Persian limitations for front, side,
  and back views.
- `overall_assessment`: development pattern, taper, upper/lower balance, and a
  concise Persian summary.
- `findings`: exactly one item for each required body area. Each item contains
  classification, numeric confidence, supporting views, Persian evidence,
  optional lag severity, and allowed training emphasis.

The backend, not the model, adds fixed product policy fields: the non-medical
flag, human coach and doctor review requirements, and the localized provisional
notice. Fixed Persian strings and JSON Schema `const` values are not sent to the
provider.

`not_assessable` is accepted only in v2 and maps to an uncertain legacy finding
with a visibility limitation. `visible_alignment_or_posture` remains the stable
API enum name.

## Execution Flow

1. The existing preflight assesses each submitted photo.
2. If zero or one views are usable, the request fails with view-specific retake
   reasons as it does today.
3. If two views are usable, analysis proceeds with those images, the result is
   `partial`, and unsupported body areas are `not_assessable`.
4. If all three are usable, analysis proceeds with `complete`.
5. Backend validation enforces all 13 unique areas, permitted view references,
   classification/severity/emphasis consistency, and a summary derived from the
   findings.
6. The normalized v2 result and a derived compatibility projection are persisted
   together. Existing v1 rows remain readable without migration.

## API and UI

The analysis endpoint returns a version-discriminated result. The frontend uses
the v2 data when present to render photo quality, overall visual assessment, and
per-area evidence. It retains its existing v1 rendering path for old results.

The workout engine continues to use the derived compatibility projection, rather
than branching on UI response fields.

## Error Handling

- Invalid model JSON, duplicate/missing areas, unsupported emphasis, or invalid
  view references fail as `invalid_output` with the existing admin-facing error.
- A v2 `partial` result is valid and does not demand an image retake.
- The server retains provider request IDs and costs for both preflight and
  analysis calls.

## Verification

- Backend schema and normalization tests for complete and partial responses,
  duplicate/missing areas, and v1 compatibility.
- API tests for version-discriminated results.
- Frontend tests for complete, partial, and historical v1 result rendering.
- A live, non-persisted provider call using the existing anonymized test photos.
