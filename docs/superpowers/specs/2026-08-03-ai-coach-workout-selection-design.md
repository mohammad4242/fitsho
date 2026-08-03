# AI Coach workout selection design

## Goal

Replace the legacy Zen model-routing panel and AI workout-generation path with
the OpenRouter task configuration for `workout_plan_generation`.

Fitsho keeps ownership of exercise safety and program construction. The AI
coach only selects and explains one safe Fitsho candidate program.

## User-facing behavior

The saved `workout_generation_method` remains the user's explicit choice.

- **Fitsho Coach** uses the current deterministic program engine and returns a
  single personalized plan. It never includes AI-coach explanations.
- **AI Coach** first produces two or three eligible candidate programs from
  the active training-template library. OpenRouter receives the user context
  and those candidates, chooses exactly one candidate, and returns a Persian
  program-level explanation plus optional Persian notes for individual days.

Exercises remain Fitsho catalog exercises in both paths. AI Coach does not
edit exercises, prescriptions, order, or safety rules.

## Candidate selection and materialization

A deterministic candidate selector will rank active template-library programs
using the user's training days, session time, experience, goal, training
location/equipment, physical limitations, and applicable body-analysis
influences. It selects up to three distinct, fully eligible candidates.

Each candidate is materialized by backend code using catalog-safe exercise
links/substitutions and is validated before it can be sent to the model. If
fewer than two candidates are eligible, AI Coach is unavailable rather than
silently using an unsafe or irrelevant program.

The current deterministic Fitsho Coach program engine is unchanged.

## OpenRouter contract

`workout_plan_generation` is the only configuration used by AI Coach:

- encrypted OpenRouter credential;
- primary and fallback model IDs;
- temperature, token maximum, timeout, cost ceiling, and routing restrictions.

The request contains a minimized profile summary, applicable structured body
analysis influences, and immutable candidate identifiers and schedules. Raw
body photos are never included.

The structured response contains:

- one `selected_candidate_id`, restricted to the supplied candidates;
- a required Persian program explanation;
- zero or more optional Persian day explanations keyed to supplied day
  numbers.

The backend rejects any unknown candidate/day, invalid output, or unavailable
configuration. Provider failures retain the existing safe failure behavior and
never activate a partially generated plan.

## Persistence and API

The selected candidate source and AI-coach explanation are persisted with the
generated workout plan. Optional day explanations are persisted with their
corresponding workout days. API responses expose these fields only when the
plan was produced through AI Coach.

An Alembic migration removes the obsolete legacy model-routing tables and their
dependent test-run records. The legacy `/admin/ai-models` API and frontend
route are deleted. OpenCode Zen settings/code used by the exercise importer are
outside this change and stay intact.

## Admin AI settings UI

The single AI settings page remains the control surface. It receives a focused
mobile-first redesign:

- an accessible back button to the admin area;
- recognizable inline SVG icons for task navigation and provider state;
- clear task tabs for all four tasks;
- separate cards for connection/credential, model route, and generation
  limits;
- visible saved, error, catalog-stale, and disabled states;
- keyboard focus and reduced-motion support.

The page has no link to a legacy models screen.

## Workout-plan UI

AI Coach plans render an `AI Coach` program card before the schedule and an
optional `AI Coach` note within each applicable day. Fitsho Coach plans omit
both cards entirely. Existing exercise cards, media, alternatives, and detail
links are preserved.

## Testing

Tests will cover:

- deterministic candidate eligibility, ordering, and distinctness;
- Fitsho Coach retaining its direct deterministic plan path;
- AI Coach accepting only a supplied candidate and preserving its exercises;
- profile/body-analysis context without raw photos;
- invalid provider selection/output and unavailable task configuration;
- persisted program/day explanations and conditional API/UI rendering;
- removal of the legacy admin models route and API;
- the AI settings back control, task navigation, and key feedback states.

Backend tests run with the project test database. Frontend tests and the
production build validate the UI contract.
