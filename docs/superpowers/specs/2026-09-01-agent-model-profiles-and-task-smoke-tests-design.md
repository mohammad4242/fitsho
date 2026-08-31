# Agent Model Profiles and Real Task Smoke Tests

## Goal

Make the selected Agent Service runner useful from Admin AI Settings:

- show model and reasoning profiles that the installed CLI can actually use;
- allow only profiles that passed a real task-specific smoke test;
- test the full Admin -> Backend -> Agent Service -> CLI -> model path;
- cover workout generation, body-photo analysis, food-photo estimation, and food-price web search;
- keep tests private, non-persistent, and free of user data.

## Decisions

- Use a hybrid verified catalog.
- A profile becomes active for a task only after that exact profile passes that task's smoke test.
- Present model and reasoning level as one profile, such as `Codex / Luna / High`.
- Store a stable profile ID in Backend rather than raw CLI arguments.
- Use safe built-in fixtures and never the latest real user data.

## Profile Catalog

Agent Service owns the mapping from stable profile IDs to runner arguments. Each profile exposes:

- `profile_id`;
- agent and display name;
- model label and reasoning label;
- supported task capabilities;
- a fingerprint derived from runner version and argument mapping.

Antigravity candidates come from the real bounded `agy models` command. The current pinned CLI returns Gemini 3.7/3.6 Flash variants, Gemini 3.1 Pro variants, Claude Sonnet/Opus 4.6 Thinking, and GPT-OSS 120B.

Codex candidates come from a versioned policy based on official OpenAI model IDs and supported reasoning efforts. The initial families are GPT-5.6 Sol, Terra, and Luna. A candidate is not called active until the installed authenticated CLI passes the selected task test.

Claude candidates come from the installed CLI's verified model aliases and effort levels. They remain unavailable while Claude authentication is unavailable or their task test has not passed.

Discovery output is bounded, strictly parsed, and never treated as proof that generation works.

## Persistence

Backend adds `agent_profile_id` to each AI task configuration. The existing raw `agent_model_id` remains only for a safe compatibility transition and is not used for new selections.

Backend stores task verification records keyed by:

- `profile_id`;
- task type;
- profile fingerprint.

Each record contains status, safe error code, checked time, and duration. It contains no prompt, model response, image, credential, account data, or raw CLI output.

A runner version, profile mapping, or fixture revision change invalidates the old verification through the fingerprint. Saving an Agent Service task fails closed unless its profile has a current passing verification for that task.

## Real Task Tests

The Admin test action calls a Backend task-test endpoint. Backend uses the same provider factory, runner contract, prompt builder, response schema, and semantic validator as production, but does not create or update user records.

The four fixtures are:

1. a synthetic workout profile for workout-plan generation;
2. synthetic non-personal front/back body images for body-photo analysis;
3. a synthetic meal image for food-photo estimation;
4. a fixed Persian grocery query for food-price web search.

Success requires:

- Backend accepted the admin request;
- Agent Service accepted the profile and task;
- the selected CLI executed the mapped model/effort;
- the model returned the expected structured schema;
- existing task semantic validation accepted the result.

The response exposes only safe stages, request ID, duration, verification status, and safe error details.

## Admin UX

The selected-agent panel shows:

- selected runner and authentication state;
- candidate profiles available for verification;
- active profiles already verified for the selected task;
- model and effort in one readable label;
- a task-specific `Test selected agent/model` action;
- progress through Backend, Agent Service, runner, schema, and semantic validation;
- the last verified time and stale/failed state.

After a successful test, the profile becomes selectable and is selected automatically for the current task. Failed or stale profiles cannot be saved as active.

## Safety and Failure Handling

- Agent Service stays internal-only on port 9001.
- Browser communicates only with Backend.
- No shell invocation or arbitrary executable/model arguments are accepted.
- Only catalog profile IDs cross the public admin boundary.
- Fixtures are packaged application assets and contain no user data.
- Test requests have bounded timeouts, concurrency, output, and cleanup.
- Raw prompts, responses, URLs, credentials, tokens, stdout, and stderr are never returned or logged.
- Authentication, model-not-found, timeout, rate-limit, invalid-output, and semantic-validation failures remain distinct safe codes.

## Verification

- TDD for profile parsing, profile resolution, persistence, stale fingerprints, and task eligibility.
- Contract tests across Agent Service, Backend, and Frontend.
- Runner command tests prove exact model and effort arguments.
- Each task smoke harness is tested with deterministic fake providers before live use.
- Agent Service, Backend, and Frontend full checks run before deployment.
- Live acceptance uses authenticated profiles and records honest pass/fail results; an untested profile is never presented as active.
