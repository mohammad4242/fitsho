# AI model structured-output check

## Goal

Make the admin model test distinguish a model that is merely reachable from a model that can accept and return the structured JSON contract Fitsho relies on for workout generation.

## Scope

The existing `Test model` action will run two checks in order:

1. Availability: the current `Reply only: OK` request.
2. Structured output: a small non-personal request using the model's configured API kind and the same structured-output mechanism as workout generation.

The structured check will require the JSON object `{"status":"ok"}`. It will use the matching provider mechanism:

- `chat_completions`: `response_format.json_schema`
- `responses`: `text.format.json_schema`
- `messages`: a required tool input
- `gemini`: `responseMimeType` and `responseJsonSchema`

No profile data, exercise catalogue, workout prompt, generated program, or user identifier is sent by either test.

## Result handling

The test succeeds only if both checks succeed. A structured-output failure is stored as a normal failed `AiModelTestRun`, with a safe error message that identifies the JSON-contract stage. Existing history and green/red event rendering remain unchanged.

## Non-goals

- Do not alter the payload, schema, retry policy, or fallback behavior of real workout generation.
- Do not claim that a successful compact contract check guarantees provider capacity, rate-limit availability, or semantic correctness of a full workout plan.

## Verification

Provider tests will assert the compact payload for all four API kinds and verify malformed structured responses fail. Admin API tests will confirm the stored success/failure history. Frontend tests will continue to show the resulting events.
