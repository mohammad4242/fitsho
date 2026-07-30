# AI Generation Reliability Design

## Goal

Make model health checks trustworthy, prevent deterministic presentation fields from
causing otherwise valid workout plans to fail, and show recent generation failures to
administrators.

## Model Health Check

The admin model test will continue to exercise the model's configured Zen API kind and
structured-output support. Its request will use the real `WorkoutPlanModelOutput` schema
and explicitly request `{"days":[]}`, so the provider parser and the requested schema
share the same contract.

Zen responses that contain an error envelope will be treated as provider errors even
when Zen incorrectly returns HTTP 200. A successful test clears the model error and the
admin UI displays a green Persian message saying that the connection succeeded. A
failed test displays the safe provider error.

## Deterministic Workout Normalization

The backend, not the model, is authoritative for calculated exercise and session
durations. Model-provided duration estimates will not cause semantic rejection. The
existing deterministic session-limit check remains active.

Exercise order is also normalized before persistence: compound movements are placed
before core and isolation movements while preserving relative order inside each group.
The backend will no longer reject an otherwise valid plan only because the model placed
a compound movement after a smaller movement. Safety, equipment, prescription,
candidate, balance, duplication, and session-limit validation remain unchanged.

## Persisted Diagnostics

`workout_plan_generations` receives a nullable JSON column named
`validation_diagnostics`. Each entry contains:

- model ID
- phase: `initial` or `repair`
- complete safe validator problem payloads

Problem payloads contain only rule code, safe message, day number, and exercise ID when
available. Profiles, prompts, model responses, credentials, and user identity are not
included.

Diagnostics are preserved for both successful and failed generation attempts, but the
admin history endpoint returns recent failed attempts only.

## Admin API and UI

Add an admin-only endpoint:

`GET /api/v1/admin/ai-generation-failures?limit=20`

It returns the generation ID, model ID, timestamps, safe error code/message, and
validation diagnostics. It does not expose the generating user.

The AI model admin page adds a recent-failures section. Each item shows the model, time,
error, phase, validator code, day number, and exercise ID. Provider failures without
semantic diagnostics still show their safe error code and message.

## Migration

Add one Alembic migration after the current head. Upgrade adds the nullable JSON column;
downgrade removes it.

## Verification

- Provider tests cover HTTP 200 error envelopes.
- Admin model tests cover a schema-compatible successful health check and failure state.
- Validator/service tests cover backend-derived durations, normalized compound order,
  and persisted initial/repair diagnostics.
- Admin API tests cover authorization, recent failure output, and absence of user data.
- Frontend tests cover failure history and the green successful-connection message.
- Backend lint, focused mypy, full pytest, frontend lint, tests, and production build run
  before delivery.
