# Admin training-template slot save design

## Scope

Fix the per-exercise admin training-template save flow without changing backend
safety or compatibility validation. The change covers the slot edit modal only;
the full-program editor and Add Exercise flow retain their current behavior.

## Diagnosis

The current frontend can select an active, programmable catalog exercise whose
`movement_pattern` is `other`. The slot mapper sends that value in the PATCH
payload. The backend compatibility evaluator intentionally treats `other` as
hard-incompatible and returns a 422 `TemplateWriteError` validation response.
The local Docker backend also needs to run the checked-out image because the
stale image currently returns 404 for the slot PATCH route.

## Design

- Give the shared exercise picker an optional filter and enable it only from
  `AdminTrainingTemplateSlotEditModal` to hide exercises with incomplete
  movement metadata. Existing picker consumers remain unchanged.
- Catch `ApiError` in slot save/delete handlers and render backend validation
  messages in the modal alert instead of discarding them.
- Represent slot numeric drafts as either an integer or an empty string. The
  numeric input preserves an empty editing state, removes leading zeros, and
  clamps to the existing backend ranges on blur and payload creation.
- When a primary replacement is selected, set `sets` to 3. Opening an existing
  slot initializes from its persisted sets value.

## Verification

Add focused frontend tests for replacement autofill, replacement sets default,
empty/leading-zero/range behavior, persisted payloads, and displayed API
validation details. Run the relevant frontend tests, frontend lint/build, and
the focused backend admin slot tests.
