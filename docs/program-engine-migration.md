# Program Engine V1 Migration

## Strategy

The audited service/repository/ORM path was salvageable, so V1 replaces the decision core inside
`WorkoutGenerationService`; it does not add a competing endpoint or permanent second generator. The
legacy deterministic fallback was removed. AI administration and provider diagnostics remain isolated
from program decisions.

## Database migration

Revision `20260731_13` adds:

- Engine, ruleset, seed, goal, training-status, and safety-status fields.
- Normalized profile, catalog, validation, metrics, progression, assumptions, warnings, and trace data.
- Previous-program link, regeneration reason, and structured difference summary.
- Day focus, weekday, and separately stored cardio.
- Per-exercise snapshot, reason codes, substitutions, warm-up sets, load guidance, and progression rule.
- A larger candidate-count check to accommodate the audited catalog.

Existing rows receive explicit `legacy` defaults and remain readable. The downgrade removes only V1
columns and restores the old candidate-count constraint.

## Rollout

1. Back up the database using the deployment platform's normal process.
2. Deploy code and run `alembic upgrade head` before serving traffic.
3. Run the curated seed so the 17 reviewed exercises have `needs_review=false`.
4. Confirm `/active` still reads legacy plans.
5. Generate a preview profile for bodyweight, gym, and constrained cases.
6. Monitor structured generation error codes, never sensitive limitation text.

No feature flag is required because there is one generation path and the public endpoint is compatible.
Rollback means deploying the previous application and applying the reversible downgrade only after
confirming no V1 program must remain readable by that application.

## Reproducibility and catalog edits

New plans retain a relevant catalog snapshot and prescriptions. API responses prefer the snapshot, so
editing exercise names, media, or taxonomy later does not rewrite historical output. A future generation
uses the new catalog hash and becomes a new program version.

## Regeneration

When an active plan expires or its normalized input/catalog signature changes, the replacement stores:

- `previous_program_id`
- `regeneration_reason`
- whether signature, ruleset, or catalog changed

The previous active plan is superseded only in the same transaction that activates a validator-approved
replacement. A failed replacement leaves the previous active plan unchanged.
