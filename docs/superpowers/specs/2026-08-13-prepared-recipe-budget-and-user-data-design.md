# Prepared Recipe Budget and User Data Design

## Scope

Keep the existing Prepared Recipe calculator, bounded ingredients, ratios, immutable revisions,
and proportional cooked-yield calculation. Apply focused changes to weekly-plan budgeting and the
normal-user response/UI.

The effective cooked-yield factors remain:

- LU07 Ghormeh Sabzi: 1.45
- LU08 Gheimeh: 1.45
- LU11 Abgoosht: 2.00

## Budget and variant selection

Food costs continue to come from the current weekly Food Catalogue price snapshots. Calories do
not determine ingredient prices or allocate a fixed price to a Recipe.

The planner passes a finite maximum cost to every Prepared Recipe optimization. The value comes
from the remaining strict or flexible weekly budget after already selected meal costs. Recipe
candidate quantities continue to use only the existing ingredient minimums, maximums, and ratio
constraints.

Planning uses two passes:

1. Build the same scheduled meals and select nutrition-aware Prepared Recipe variants under a
   finite remaining-budget cap.
2. If the week exceeds its allowed budget, retry Prepared Recipe choices with cheaper valid
   candidates before rejecting the plan. A replacement is accepted only when ingredient bounds,
   ratios, nutrient upper limits, and weekly nutrition feasibility remain valid.

Simple meals keep their current portioning and selection behavior. Strict and flexible weekly
budget policies keep their existing final limits and outcome codes.

## Immutable data and public response

The stored `recipe_snapshot` remains the immutable source of a generated Prepared Recipe result.
It retains the selected ingredient quantities, ingredient-level costs, price references,
calculation version, revision identity, Recipe verification state, provenance, data gaps, cooked
yield, nutrients, and total cost.

The normal-user weekly-plan API does not return the raw snapshot. It returns a separate typed
Prepared Recipe summary containing only:

- kcal and available macros per 100 g
- total prepared-meal cost per 100 g
- public status: `estimated` for a draft Recipe or `verified` for a verified Recipe

Ingredient quantities, ingredient-level nutrients, individual Food Catalogue prices, price
reference IDs, provenance, and data gaps remain hidden from normal users. Existing admin Recipe
responses keep the full internal review data.

## Draft policy and UI

Draft Prepared Recipes remain eligible for normal weekly plans. They are never represented as
verified. Their stored snapshot keeps the draft status and internal evidence, while the public
summary maps draft to `estimated`.

The Persian user UI renders only `تخمینی` for an estimated Prepared Recipe. It renders no status
label for a verified Prepared Recipe. No other draft or verification wording is shown to normal
users.

The Weekly Nutrition Plan shows each Prepared Recipe's kcal per 100 g, every available macro per
100 g, and prepared-meal cost per 100 g from the immutable public summary. It does not reconstruct
these values from current catalogue data.

## Validation

Backend tests cover finite budget propagation, budget-dependent and cheaper valid selection,
ingredient bounds and ratios, immutable snapshot data, public kcal/macros/cost summaries, public
privacy, draft-to-estimated mapping, verified status, unchanged simple meals, and preserved cooked
yields.

Frontend tests cover Recipe nutrition/cost display, the exact Persian `تخمینی` label, no label for
verified Recipes, and absence of ingredient quantities and individual prices. Run focused and full
backend tests, Ruff, mypy, focused and full frontend tests, frontend lint, and production build.
