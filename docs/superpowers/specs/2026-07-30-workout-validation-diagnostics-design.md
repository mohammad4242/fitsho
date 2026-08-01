# Workout Validation Diagnostics Design

## Goal

Make AI workout generation failures diagnosable from backend logs when a model response
fails semantic validation.

## Scope

Emit one structured warning for each failed validation phase:

- `initial`: the model's first plan response
- `repair`: the model's repaired plan response

Each event includes the model ID and the validator's complete problem payloads: code,
message, day number, and exercise ID when present. These values identify the exact
failed rule without logging the user profile, prompt, model response, or other personal
data.

## Implementation

Add a module logger to the workout generation service. Log validation failures at the
point where the model ID and validation phase are known. Keep the existing API response
and database failure code unchanged.

## Verification

Add focused tests using `caplog` for initial and repair validation failures. Verify that
the log contains the model ID, phase, and full problem payloads, and that generation
still returns the existing safe failure.
