# Personalized Workout Plan Generator Design

## Goal

Fitsho will generate one personalized weekly resistance-training schedule for an
authenticated user and repeat it for the user's selected four-, six-, or eight-week
plan duration. The backend, not the model, owns eligibility, reuse, validation,
persistence, concurrency, and failure recovery.

The first production provider is OpenCode Zen with `gpt-5.4-mini`. The integration uses
the current Zen Responses endpoint:

```text
https://opencode.ai/zen/v1/responses
```

Changing to another Zen GPT model that uses the Responses protocol, such as
`gpt-5.6-terra`, is configuration-only. Gemini or Claude require a separate adapter
behind the same provider interface.

## Boundaries

The feature includes:

- exercise programming metadata and full administrator editing;
- structured profile cautions and plan-duration preference;
- deterministic candidate filtering and generation signatures;
- time-budget and semantic validation;
- Zen generation with one optional repair;
- historical plan storage and atomic activation;
- authenticated plan APIs and a bilingual workout-plan page;
- read-only curated alternatives;
- disabled placeholders for PDF, body-photo analysis, end-of-cycle feedback, and coach
  chat.

The feature excludes workout execution tracking, progression history, recorded loads,
PDF creation, image upload or analysis, stored feedback, chatbot behavior, nutrition,
medical diagnosis, rehabilitation, queues, Redis, and Celery.

## Existing Architecture

The repository is a FastAPI modular monolith using synchronous SQLAlchemy sessions,
Alembic, PostgreSQL, Pydantic, React, TypeScript, React Router, i18next, Vitest, pytest,
Ruff, and strict mypy.

Relevant existing boundaries:

- `app.profile` owns completed fitness profiles and workout preferences.
- `app.exercises` owns the catalog, equipment relations, alternatives, and seed data.
- `app.admin` owns administrator authorization, media storage, and exercise creation.
- the frontend uses a shared cookie-authenticated API client and nested authentication,
  completed-profile, and administrator route guards.

The new `app.workouts` module may read profile and exercise data but does not move their
ownership. The new `app.ai` module has no database dependency.

## Exercise Programming Metadata

Add the following controlled fields:

```text
movement_pattern
exercise_type
is_programmable
exercise_caution_tags
```

`movement_pattern` and `exercise_type` are non-null string enums. Caution tags use the
normalized `exercise_caution_tags(exercise_id, caution_tag)` association table.
`is_programmable=false` keeps an exercise visible while excluding it from automatic
generation.

The migration assigns `other/other` and `is_programmable=false` to unknown existing
records. All committed seed exercises receive explicit metadata and become programmable.
Runtime name parsing is forbidden.

Current seed classifications:

| Exercise | Pattern | Type | Caution tags |
|---|---|---|---|
| Dumbbell Bench Press | horizontal_push | compound | shoulder_internal_rotation |
| Barbell Bent-Over Row | horizontal_pull | compound | lower_back_loading |
| Dumbbell Lateral Raise | shoulder_abduction | isolation | none |
| Smith Machine Shoulder Press | vertical_push | compound | overhead_position |
| Rear Delt Fly | horizontal_pull | isolation | lower_back_loading |
| Dumbbell Curl | elbow_flexion | isolation | none |
| Hammer Curl | elbow_flexion | isolation | none |
| Cable Curl | elbow_flexion | isolation | none |
| Barbell Curl | elbow_flexion | isolation | wrist_loading |
| Overhead Dumbbell Extension | elbow_extension | isolation | overhead_position |
| Glute Bridge | hip_extension | compound | none |
| Goblet Squat | squat | compound | deep_knee_flexion, wrist_loading |
| Leg Press | squat | compound | deep_knee_flexion |
| Leg Extension | knee_extension | isolation | none |
| Dumbbell Lunge | lunge | compound | deep_knee_flexion, balance_demand |
| Romanian Deadlift | hip_hinge | compound | lower_back_loading |
| Standing Calf Raise | calf_raise | isolation | balance_demand |

The administrator create and edit contracts require all programming metadata. New forms
default to `is_programmable=false`. Editing preserves the exercise UUID so workout
foreign keys remain valid.

## Structured Profile Preferences

Add:

```text
training_cautions:
  lower_back, knee, shoulder, neck, wrist, other

plan_duration_weeks:
  4, 6, 8
```

Cautions use `user_profile_training_cautions(user_id, caution)`. “None” is a frontend
sentinel serialized as an empty list and is never stored as a row. Existing users receive
an empty caution set and a four-week duration.

The free-text limitation field remains. Before provider use it is Unicode-normalized,
trimmed, internal whitespace is collapsed, control characters are removed, and the
result is limited to 500 characters.

## Candidate Selection

`WorkoutCandidateSelector` is deterministic and performs no model calls.

Initial query:

```text
is_active = true
is_programmable = true
```

Available equipment:

```text
home/bodyweight_only:
  bodyweight

home/dumbbells_available:
  bodyweight, dumbbell

gym:
  bodyweight, dumbbell, barbell, cable, machine,
  resistance_band, bench, pull_up_bar
```

`other` is never assumed. An exercise is eligible only when all required equipment is a
subset of available equipment.

Difficulty rules:

```text
beginner:
  beginner

intermediate:
  beginner, intermediate

advanced:
  beginner, intermediate, advanced
```

Strict caution exclusions:

```text
lower_back:
  lower_back_loading, spinal_flexion
knee:
  deep_knee_flexion
shoulder:
  overhead_position, shoulder_internal_rotation, shoulder_external_rotation
neck:
  neck_loading
wrist:
  wrist_loading
other:
  other
```

After filtering, candidates are ordered by movement-pattern round-robin. Within each
pattern, compounds precede core, isolation, mobility, and other types; difficulty
distance and UUID break ties. The default cap is 80.

The selector rejects before provider use when there are fewer than
`max(3, min(6, training_days_per_week + 1))` candidates or fewer than two movement
patterns for a multi-day plan. This does not add seed exercises. Adding or removing
eligible administrator-managed exercises automatically changes future candidate sets.

The provider representation contains only:

```json
{
  "id": "exercise-uuid",
  "primary_muscle": "chest",
  "secondary_muscles": ["triceps"],
  "movement_pattern": "horizontal_push",
  "exercise_type": "compound",
  "equipment": ["dumbbell", "bench"],
  "difficulty": "intermediate",
  "caution_tags": []
}
```

## Generation Signature and Freshness

Canonical JSON is serialized with sorted keys, stable enum values, sorted collections,
and compact separators, then SHA-256 hashed.

Candidate hash includes every field sent for each candidate, ordered by UUID.

Generation signature includes:

- fitness goal;
- sex;
- current weight bucketed into fixed five-kilogram ranges;
- experience;
- training days;
- location and home setup;
- session duration;
- plan duration;
- structured cautions;
- normalized limitation note;
- candidate hash;
- catalog programming version;
- model ID;
- prompt version;
- generation policy version.

It excludes user ID, email, display name, exact birth date, natural age changes, height,
authentication data, and unrelated profile fields.

Reuse requires both:

```text
active_plan.signature == current_signature
current_time < activated_at + duration_weeks * 7 days
```

Changing display name, age, or height alone does not regenerate. Changing goal, sex,
five-kilogram weight bucket, experience, days, location, equipment, session time,
duration, cautions, limitation note, candidates, model, prompt, catalog version, or
policy makes the plan stale.

An expired or stale plan remains active and readable until a validated replacement is
activated.

## Time Budget

Central version-one policy:

```text
session minutes:       30  45  60  75  90
maximum exercises:      3   4   6   7   8
warm-up minutes:        5
set execution seconds: 45
transition seconds:    90
sets:                  2..5
repetitions:           5..20
rest seconds:          45, 60, 75, 90, 120, 150, 180
RIR:                   1, 2, 3, 4
```

Exercise seconds:

```text
transition_seconds
+ sets * set_execution_seconds
+ (sets - 1) * rest_seconds
```

Exercise minutes are rounded up. Backend day duration is warm-up plus exercise minutes.
It must not exceed the user limit. Model exercise/day estimates may differ from backend
calculations by at most two minutes; persisted estimates are backend calculations.

## Model Request and Provider

The service depends on:

```python
class WorkoutPlanModelProvider(Protocol):
    async def generate_plan(
        self,
        request: WorkoutGenerationModelRequest,
    ) -> WorkoutGenerationModelResponse: ...
```

`WorkoutGenerationModelRequest` contains a sanitized profile, generation policy,
allowed exercises, and an optional tuple of repair errors.

`OpenCodeZenWorkoutPlanProvider` owns HTTP only. It uses one application-lifespan
`httpx.AsyncClient`, explicit timeout, bearer authentication, `store=false`, and the
Responses API `text.format` strict JSON Schema. The API key is a Pydantic `SecretStr`.

The system prompt is versioned in `prompt_builder.py`. User text is nested as a JSON
string value and cannot become a system/developer instruction.

The initial request sends age calculated at call time, sex, height, current weight,
goal, experience, schedule, location/setup, duration, cautions, and sanitized limitation
context. It never sends user identity, birth date, cookies, or authentication data.

One repair is allowed only for parseable structural or semantic output failures. It
contains the original profile, policy, candidates, required schema, and concise errors.
It does not include the previous raw output and cannot expand candidates.

## Validation

Pydantic models use `extra="forbid"` and bounded fields. All nullable note properties
remain required in strict JSON Schema.

Semantic validation checks:

- exact day count and sequential unique day numbers;
- candidate membership and current active/programmable status;
- current equipment, difficulty, and caution compatibility;
- unique exercise IDs per day;
- policy bounds for count, sets, repetitions, rest, and RIR;
- deterministic duration;
- compounds before isolation work;
- no isolation-only day when an eligible compound exists;
- no identical ordered exercise-ID days;
- weekly upper push, upper pull, knee-dominant, hip-dominant, and core coverage when
  those groups exist and the available slot budget permits;
- no primary muscle above 50% of selections when at least three eligible primary muscle
  groups exist;
- no URLs, HTML, Markdown fences, unsupported keys, or medical-treatment language in
  titles or notes.

Before activation, the service rereads the profile and candidate set. A changed
signature aborts activation and preserves the previous plan.

## Persistence and Concurrency

Tables:

- `workout_plans`
- `workout_days`
- `workout_plan_exercises`
- `workout_plan_generations`

The schema includes the requested audit fields, foreign keys, ranges, unique day/order
constraints, and timestamps. Plan rows never duplicate exercise names, media, or
instructions.

PostgreSQL partial unique indexes enforce:

```text
one workout_plans row with status = active per user
one workout_plan_generations row with status = generating per user
```

Generation flow:

1. read profile, active plan, policy, and candidates;
2. compute freshness and reuse if valid;
3. enforce cooldown;
4. insert and commit a generating record;
5. call Zen without an open transaction;
6. parse and validate, with at most one repair;
7. reread profile/catalog and reject mid-flight changes;
8. update the old active row to superseded and flush;
9. insert the new active plan and children;
10. complete the generation record and commit.

Any activation error rolls back, restoring the old active plan. A separate short
transaction marks the generation failed.

Generation records store only technical metadata, safe error codes, request ID, counts,
token usage, and latency. Raw prompts/responses are never stored.

## API

```text
GET  /api/v1/workout-plans/active
POST /api/v1/workout-plans/generate
GET  /api/v1/workout-plans/{plan_id}
```

All use existing authentication and completed-profile dependencies. Generate also uses
trusted-origin protection and accepts no user ID or body.

Responses include `stale`, safe stale reasons, expiry, duration, days, exercise catalog
summaries, and active profile-compatible curated alternatives. Generate additionally
returns `reused`.

Errors:

```text
404  no active plan or non-owned plan
409  generation already in progress
422  insufficient eligible exercises
429  per-user cooldown, with Retry-After
502  malformed/unavailable provider
503  provider configuration or rate limit
504  provider timeout
```

## Frontend

Add `/workout-plan` inside the existing completed-profile guard and add bilingual
navigation.

The page displays:

1. a bilingual “Before you start” panel;
2. duration and freshness;
3. the weekly day schedule;
4. exercise media, names, prescription, localized notes, and detail links;
5. read-only curated alternatives;
6. disabled “Coming soon” cards for PDF, body-photo/end-of-cycle feedback, and coach
   chat.

Fixed guidance covers controlled technique, warm-up, gradual load increases only after
prescribed repetitions are completed with good form, recovery, and stopping on sharp or
unusual pain. It does not provide diagnosis or treatment.

The old plan remains visible during regeneration and after failure. No completion
checkboxes, uploads, execution tracking, or editable prescriptions are added.

## Privacy and Operations

Environment configuration:

```text
OPENCODE_ZEN_API_KEY
OPENCODE_ZEN_BASE_URL=https://opencode.ai/zen/v1
OPENCODE_ZEN_MODEL=gpt-5.4-mini
OPENCODE_ZEN_TIMEOUT_SECONDS=30
WORKOUT_PROMPT_VERSION=v1
WORKOUT_POLICY_VERSION=v1
WORKOUT_CATALOG_PROGRAMMING_VERSION=v1
WORKOUT_MAX_REPAIR_ATTEMPTS=1
WORKOUT_GENERATION_COOLDOWN_SECONDS=300
WORKOUT_MAX_CANDIDATES=80
WORKOUT_MAX_REQUEST_BYTES=262144
WORKOUT_WARMUP_MINUTES=5
```

`.env.example` uses a placeholder key. Secrets are excluded from repr, logs,
serialization, React, and persisted snapshots.

Zen/OpenAI request-retention behavior is a documented limitation. Automated tests never
call Zen. The optional synthetic live test requires `ZEN_LIVE_TEST=true`.
