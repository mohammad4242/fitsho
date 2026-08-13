# Prepared Recipe Calculation Design

## Scope

Add an optional Prepared Recipe calculation layer to the existing
Food Catalogue -> Meal Catalogue -> Program -> Weekly Plan pipeline. Catalogue meals use either
`simple` or `prepared_recipe`. Existing meals default to `simple` and keep their current behavior.
Only LU07 Ghormeh Sabzi, LU08 Gheimeh, and LU11 Abgoosht initially use Prepared Recipe. Rice,
bread, side herbs, salad, and other independently adjustable sides remain ordinary meal items.

## Immutable recipe revisions

A meal owns one Prepared Recipe identity and points to one current immutable revision. Editing a
recipe creates the next revision instead of mutating an old revision. A revision stores its version,
verification status, calculation version, provenance, explicit cooked-yield configuration,
ingredients, ratio constraints, and calculated preview metadata. Previous revisions remain
queryable so historical plans can be reproduced.

Recipe ingredients are normalized rows referencing `nutrition_catalogue_foods.id`. Each row stores
reference, minimum, and maximum grams plus required/optional status. Ratio constraints are separate
normalized rows with generic left/right ingredient references, minimum ratio, and maximum ratio.
The calculator has no dish-specific branches.

Missing nutritionally meaningful ingredients are not fake Food Catalogue rows and are not recipe
ingredients. A separate recipe data-gap row records the intended ingredient label and a message such
as `Onion does not exist in Food Catalogue`. Data gaps are visible in the admin editor and force the
recipe revision to remain `draft`. Spices and seasonings are neither Food Catalogue calculation items
nor data gaps.

## Yield and calculation

The initial yield strategy is an explicit reference-batch final cooked mass. A revision records the
reference input mass, final cooked yield grams, yield method, source name, source reference, and
notes. The interface is versioned so later strategies can add retention factors or measured
ingredient-specific mass changes without changing recipe ownership or planner contracts.

For a candidate ingredient vector, the generic calculator:

1. validates ingredient bounds and ratio constraints;
2. resolves every Food Catalogue composition and effective price;
3. aggregates every nutrient code present in the ingredients;
4. aggregates ingredient cost in IRR;
5. applies the configured cooked-yield model; and
6. returns cooked-food nutrients and cost per 100 g.

Missing nutrient codes remain absent rather than becoming zero. Calculation is deterministic and
uses `Decimal`. Draft recipes may be previewed, but only structurally valid verified revisions are
eligible for verified meals and automatic planning. Missing yield is always invalid.

## Planner integration and snapshots

The planner receives Prepared Recipe as a composite adjustable item plus the meal's ordinary side
items. It optimizes ingredient quantities only inside ingredient bounds and generic ratio
constraints, then exposes the resulting cooked-food grams to the member. Internal ingredient grams
remain in calculation and audit snapshots.

Every generated plan snapshots the recipe identity and revision, calculation version, selected raw
ingredient quantities, Food Catalogue composition provenance, effective-price references and
values, yield inputs/output, calculated per-100-g values, selected cooked-food grams, nutrients, and
cost. Existing weekly-plan meal and nutrient totals remain the output path. Historical plan display
uses snapshots and does not recalculate from current recipes or prices.

## Validation

Reject unknown Food Catalogue IDs, duplicate ingredients, invalid bounds, non-positive required
quantities, missing yield, self-referential ratios, contradictory ratio cycles, ratios with
impossible bound intersections, a Prepared Recipe meal without a structurally valid revision, and a verified recipe
whose required foods are not verified. A revision with any data gap cannot be verified. Switching a
meal back to `simple` preserves recipe history but removes it from active calculation.

## Initial catalogue data

LU07, LU08, and LU11 move only their composite stew ingredients into Prepared Recipe. The existing
ground-beef entry is not reused for stew meat. A distinct source-backed raw beef chuck/stew-meat Food
Catalogue identity is added from USDA FoodData Central before it is referenced. Existing catalogue
foods are reused without duplication. Any required ingredient or cooked-yield value that cannot be
supported is recorded as a visible data gap and keeps that recipe revision draft; no value is
invented.

The methodology follows published recipe-calculation guidance that cooking weight change must be
included and an Iranian mixed-dish study that calculated recipes from raw ingredients with a yield
factor. The study describes the method but does not publish defensible final cooked weights for all
three requested dishes, so unsupported initial yield values remain draft data rather than verified
facts.

Sources:

- https://doi.org/10.1006/jfca.2000.0922
- https://doi.org/10.34171/mjiri.34.129
- https://fdc.nal.usda.gov/food-details/2646174/nutrients

## Admin UI and API

The Meal Catalogue editor adds `Calculate as prepared recipe`. In Prepared Recipe mode it shows
recipe revision/status/source fields, Food Catalogue ingredient selection, bounds, required status,
generic ratio controls, cooked yield, visible data gaps, and a live server-calculated preview for all
available nutrients and estimated cost per 100 g. Editing creates a new immutable revision. In
Simple mode the current item editor, payload, totals, and planner behavior remain unchanged.

## Tests and verification

Backend tests cover model constraints, validation, calculator determinism, all-nutrient aggregation,
cooked yield, per-100-g output, effective-price changes, immutable revisions, plan snapshots,
simple-mode compatibility, the three initial mode assignments, side-food separation, and adding a
future recipe without calculator changes. API tests cover safe mode switching and draft/verified
rules. Frontend tests cover the mode control, conditional editor, food selection, bounds, ratios,
yield, gaps, live preview, and payloads. Complete backend tests, Ruff, formatting check, MyPy,
frontend tests, Oxlint, and production build run before completion.
