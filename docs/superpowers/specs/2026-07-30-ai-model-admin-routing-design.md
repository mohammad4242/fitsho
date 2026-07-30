# AI model administration and routing

## Goal

Let an administrator select the OpenCode Zen model used for workout generation
without restarting the backend. The administrator can use the curated Zen
catalogue, add a custom model ID, or enable automatic fallback across free
models.

## Scope

- Store the Zen model catalogue in the application database.
- Seed known Zen models with their documented API type and free/paid status.
- Provide a manual administrator-triggered Zen sync that updates built-in
  records and leaves custom records untouched.
- Support the four documented Zen request formats: Responses, Chat
  Completions, Messages, and Gemini.
- Provide one global routing setting: manual selection or automatic free-model
  fallback.
- Add an administrator UI for catalogue management, custom model entry,
  ordering, model testing, synchronization, and last-error visibility.

## Non-goals

- Managing API keys in the browser or database.
- Automatic scheduled catalogue synchronization.
- Automatic selection of paid models.
- Removing or redacting any existing workout-generation payload fields.

## Data model

`ai_models` represents built-in and custom choices. It stores a unique model
ID, display name, API kind, billing class (`free` or `paid`), enabled state,
priority, custom flag, last synchronization timestamp, and the latest health
check/error details.

`ai_routing_settings` is a singleton global setting. It stores the mode
(`manual` or `automatic`) and the selected manual model. The selected model
must be enabled. In automatic mode, enabled free models are ordered by their
administrator-controlled priority.

## Zen synchronization

An authenticated administrator action fetches the current Zen model-ID list.
The server creates or updates only built-in records that have a maintained,
documented metadata mapping, including API kind and free/paid classification.
An ID that Zen returns but the mapping does not know is added as disabled and
requires the administrator to set its API kind and billing class before it can
be selected. A built-in model absent from the current catalogue is disabled;
custom records are never changed. The sync response reports its time and any
models requiring classification.

## Provider routing

Every workout-generation request reads the current routing setting from the
database, so the next request observes an administrator change without a
backend restart.

In manual mode, the provider uses the selected model. In automatic mode, it
tries enabled free models in priority order. It stops at the first semantically
valid plan. A provider error, timeout, refusal, malformed response, or failed
semantic validation advances to the next candidate. If all candidates fail,
the existing safe temporary-unavailable response is returned.

The provider layer has a dedicated serializer/parser for every Zen API kind.
The current generation payload remains intact for all adapters. The Zen API key
continues to be read only from backend environment configuration.

## Administrator UI

The Admin area gains an AI Models page with Free, Paid, and Custom views. Each
model shows its name, ID, API kind, state, priority, classification-needed
state, and most recent test/error status. An administrator can:

- synchronize Zen models on demand;
- enable or disable a model;
- set the routing mode and the manual model;
- reorder eligible free models for automatic routing;
- add and edit a custom model name, ID, API kind, billing class, and state;
- run a small model health check.

Disabled models cannot be selected for manual routing or automatic fallback.

## Security and observability

All new routes require the existing administrator guard. No endpoint returns
the Zen API key. Generation records retain the chosen model and, in automatic
mode, the model that ultimately produced the response. Model health checks and
fallback attempts retain concise operational error details for administrators;
user-facing errors remain safe and generic.

## Verification

Backend tests cover authorization, catalogue synchronization, custom-model
validation, the singleton routing settings, all four API adapters, manual
routing, priority fallback, and all-candidates-failed behavior. Frontend tests
cover the routing-mode selection, manual selector, priority ordering, custom
form, synchronization state, and error display.
