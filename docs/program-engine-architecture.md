# Fitsho Program Engine V1 Architecture

## Scope

Program Engine V1 generates resistance and coordinated cardio programs for adults. It is not a
diagnostic, rehabilitation, pregnancy/postpartum, acute-injury, or medical-exercise-prescription
system. Unsupported or ambiguous safety inputs return a structured review status.

## Audited architecture before V1

The audit baseline was commit `be1541c`. The complete runtime path was:

1. `POST /api/v1/workout-plans/generate` in `app/workouts/router.py` authenticated the user.
2. `WorkoutGenerationService.generate` loaded `UserProfile` and the latest body measurement.
3. `WorkoutCandidateSelector` queried exercises and filtered activity, programmability, equipment,
   difficulty, and a small caution map.
4. `prompt_builder.py` sent profile, candidates, and a time policy to an AI provider.
5. The provider chose the split, exercises, order, sets, reps, RIR, and rest.
6. `normalizer.py` reordered a limited subset of exercises.
7. `validator.py` checked IDs, duplicates, basic prescriptions, and approximate duration.
8. `repository.activate_plan` persisted the plan, superseded the previous active plan, and completed
   the generation record in one transaction.
9. React consumed the existing day/exercise response fields from the same API routes.

The preview branch also had `deterministic_generator.py`. It rotated a sorted candidate list and used
one broad prescription. It was a fallback, not a domain model.

## Reproduced defects and root causes

| Reproduced output | Root code path | Classification | Violated invariant |
|---|---|---|---|
| Novice with poor recovery could receive six or seven resistance days | Day count passed directly through service/provider; validator only checked equality | Incorrect domain rule; missing validation | Novice recovery must constrain frequency; max six resistance days |
| Three-day plans could be P/P/L with one weekly exposure | AI owned split choice; no frequency scoring | Architecture/coupling; missing validation | Split must be scored for frequency and recoverability |
| A one-day plan passed without pulling or trunk work | Validator had no goal-aware weekly movement coverage | Missing validation | Required movement coverage |
| A 30-minute plan could contain unrealistic work | Approximate slot policy did not include all ramp-up/cardio costs | Incorrect domain rule | Session duration ceiling |
| Five days could repeat the same movements or become identical | Fallback rotated candidates without weekly slot planning | Incorrect scoring; excessive pseudo-variety | Duplicate and weekly-coherence rules |
| Fat-loss output contained 28 resistance slots with one prescription and no cardio | No weekly volume plan or cardio stage | Missing domain rule | Resistance quality, cardio separation, recoverability |
| Shoulder caution could leave no coherent plan only after assembly | Safety constraints were partial and late | Missing hard constraint | Safety before selection |
| `needs_review=true` exercises entered the candidate set | Candidate SQL omitted `needs_review=false` | Missing hard constraint; data quality | Review-pending exercises are ineligible |
| All 317 local records were marked programmable while all required review | Import policy allowed programmable and review-pending simultaneously | Data quality; incorrect profile interpretation | Incomplete metadata cannot silently program |
| 23 exercises lacked primary muscle; 98 used `movement_pattern=other`; 44 used `exercise_type=other` | Imported catalog metadata was incomplete | Missing exercise metadata | Required programming metadata |
| Identical requests could depend on provider output | No persisted deterministic seed controlled decisions | Excessive randomness; coupling | Reproducibility |
| Historical API rendering joined live exercise fields | Only exercise IDs and prescriptions were saved | Faulty persistence behavior | Historical program immutability |
| Invalid plan prevention depended on the legacy semantic validator | Validation was coupled to AI output schema | Architecture/coupling problem | Independent whole-program validation |

The local audit found 25 generation attempts: 23 failed and two succeeded. Representative failures
are encoded in `test_bad_output_regressions.py`; property-level scenarios live under
`tests/workouts/program_engine/`.

## Architecture after V1

The existing API, service, repository, ORM entities, activation transaction, and frontend response
shape remain. The workout-decision path is now one pure domain pipeline:

```text
API / persisted profile / optional typed evidence
  -> WorkoutGenerationService (I/O adapter)
  -> ProgramGenerationRequest
  -> normalization
  -> safety
  -> constraints
  -> training status
  -> split selection
  -> weekly volume plan
  -> exercise eligibility
  -> exercise ranking
  -> session assembly
  -> prescription + cardio + progression
  -> independent validation
  -> ORM mapping + atomic activation
```

Pure stages live in `app/workouts/program_engine`. They do not import FastAPI, SQLAlchemy, network
clients, global state, or AI providers. `generate_program(request, catalog, ruleset)` is the domain
boundary. The application service owns queries, snapshots, signatures, persistence, and stale-plan
checks.

## Determinism and explainability

- A supplied seed is used as-is; otherwise SHA-256 of normalized input derives a signed 63-bit seed.
- Every ranking tie uses a stable hash of seed and exercise ID.
- Hard filters run before scoring.
- Split, volume, exercise, cardio, and safety decisions emit reason codes.
- Validator output contains errors, warnings, assumptions, metrics, and the decision trace.
- Any validation error produces a failed generation attempt and no `WorkoutPlan` row.

## Compatibility boundary

Existing operations remain:

- `GET /api/v1/workout-plans/active`
- `POST /api/v1/workout-plans/generate`
- `GET /api/v1/workout-plans/{plan_id}`

The generate body remains optional. New evidence fields are additive. Existing day/exercise response
fields remain; engine metadata is additive. AI model administration and provider diagnostics remain
available, but no AI provider is injected into or called by workout generation.

## Structured failure boundary

Safety review and constraint failures return HTTP 422 with a stable code. Core domain codes include:

- `PROGRAM_REJECTED_SAFETY_STATUS`
- `NO_SAFE_EXERCISE_FOR_PATTERN`
- `NO_AVAILABLE_EQUIPMENT_MATCH`
- `INSUFFICIENT_ELIGIBLE_EXERCISES`
- `PROGRAM_VALIDATION_FAILED`

The engine does not select an ineligible fallback to fill a slot.
