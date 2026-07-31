# AI Model Availability Test and History Design

## Goal

Replace the current production-schema model test with a lightweight availability
check, and retain a complete admin-visible history of every model-test result.

## Availability Test

The existing **Test model** control will make one minimal request through the
model's configured Zen API kind. It will not send the workout-plan schema,
exercise catalogue, profile data, or a tool definition.

Each API kind receives its smallest supported request with a short instruction
equivalent to `Reply only: OK` and an output limit of one token. A non-error
provider response counts as available; its response content is not stored.

This test deliberately verifies API access and model availability only. Workout
generation continues to use its existing structured JSON request and validates
full plan compatibility independently.

## Persistence

Add an append-only `ai_model_test_runs` table. Each row contains:

- test-run ID
- model ID
- outcome: `succeeded` or `failed`
- safe provider error code and message when failed
- creation timestamp

It contains no API key, prompt body, raw provider response, user information,
exercise data, or workout-generation payload.

The existing `AiModel.last_checked_at`, `last_error_code`, and
`last_error_message` fields remain the latest-status summary on each catalogue
row. Every attempt is additionally retained in the new table.

## Admin API and UI

Add an admin-only endpoint returning the most recent test runs, newest first,
with a bounded `limit` parameter. The existing AI event card will include both
workout-generation failures and model-test runs.

Model-test successes appear in green with the Persian message
`با موفقیت متصل شد`. Model-test failures appear in red with their safe error
code and message. Each test item shows model name/ID and timestamp. Existing
workout-generation failure diagnostics remain unchanged and visually distinct
by event type.

## Error Handling

All provider failures use the existing safe error mapping. A Zen HTTP 200 error
envelope still counts as a failed availability test. Database persistence failure
returns a safe admin error rather than reporting a false test result.

## Verification

- provider tests cover the minimal request shape for every API kind
- service/API tests cover successful and failed run persistence, ordering, and
  admin authorization
- frontend tests cover green success and red failure history entries
- backend lint, type checks, full tests, frontend lint, tests, and build run
  before delivery
