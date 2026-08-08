# Nutrition Food Catalogue Design

## Scope

Task 4 adds a verified food catalogue and structured meal composition. It does
not implement prices, plan optimisation, shopping lists, or live external
provider calls.

## Data model

- `nutrition_foods` stores the canonical food identity, Persian and English
  names, verification state, source provenance, and deterministic role
  eligibility.
- `nutrition_food_compositions` stores a single nutrient value per food and
  canonical quantity basis, including unit/form, source, confidence, and an
  explicit missing-data state. Null means unavailable; it never means zero.
- `nutrition_meals` and `nutrition_meal_items` store a main-meal or snack
  composition with exact canonical quantities. Stored totals are recalculated
  deterministically from the item composition rows.

## Behaviour

Food roles are `main_protein`, `main_staple`, `snack`, and `flexible`. Main
meals require at least one eligible substantial component; snack meals allow
only snack or flexible foods. The first seed is deliberately small and uses
documented, verified foods common in Iran. USDA FoodData Central import is a
validated mapping path: imported composition preserves source identifiers,
units, and nutrients rather than becoming a requirement target.

## APIs and administration

Authenticated members can list verified foods and read meal totals. Admins can
create, update, verify, and retire foods and can create structured meals.
Import validation rejects non-positive canonical quantities, unsupported
units, duplicate nutrient rows, and values without provenance.

## Validation

Tests cover provenance, missing nutrient data, canonical conversion, role
eligibility, meal totals, seed idempotence, import validation, and admin/API
authorisation.
