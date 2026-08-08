# Nutrition Task 6: Weekly Planner

The weekly planner is deterministic and reads only Fitsho's verified food catalogue and accepted,
fresh price references. It never calls a marketplace during a user request.

## Flow

1. Load the current safety decision, Nutrition profile, scientific estimate, exclusions, and meal
   structure.
2. Filter catalogue candidates by verification, mandatory composition data, dietary pattern,
   allergy/exclusion terms, slot role, positive price, and the versioned 168-hour freshness limit.
3. Rank compatible candidates using versioned micronutrient, preference, and cost weights.
4. Build exactly seven days with the selected main-meal and snack counts.
5. Apply a bounded micronutrient repair pass and revalidate calories, macros, applicable total-intake
   limits, budget, and slot roles.
6. Persist either a structured generation failure or an immutable, visible plan revision with price,
   input, policy, food, nutrient, and repair snapshots.
7. Every successful revision receives a pending physician-review record. It is not active or marked
   approved until a later authorized physician workflow approves that exact revision.

## API

- `POST /api/v1/nutrition/plans`
- `GET /api/v1/nutrition/plans/latest`
- `GET /api/v1/nutrition/plans/active`
- `GET /api/v1/nutrition/plans/history`
- `GET /api/v1/nutrition/plans/{plan_id}`

Generation outcomes are separate from plan lifecycle states: `success`, `failed`, `safety_blocked`,
`infeasible`, `target_infeasible`, and `live_price_unavailable`.

`live_price_unavailable` with `INSUFFICIENT_PRICE_COVERAGE` means no safe plan was created. The
planner does not fabricate or silently estimate a live price.
