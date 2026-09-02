# Food Price Final Reference Floor Design

## Goal

Ensure every food-price candidate or derived reference price exposed or persisted by
the Backend is floored to the lower whole thousand toman. A value such as
`385666.666...` becomes `385000`; this is floor, not nearest-thousand rounding.

## Scope and data flow

Add a small deterministic `Decimal` helper in `app.nutrition.pricing` using
`ROUND_FLOOR`. The helper is a finalization utility only and is not called by
`calculate_reference_price` or `decide_reference_price`.

The single-food admin research endpoint will compute its exact trusted-evidence
average first, then pass that average through the helper. The resulting
`candidate_price` will be used consistently for the response and optional
override application.

The weekly update service will call the helper only after
`decide_reference_price` returns. When a decision has a reference price, the
floored value will be used for accepted `NutritionFoodPriceReference`, accepted
`NutritionFoodPriceHistory`, and review candidate persistence. Quote evidence and
all inputs to policy evaluation remain unchanged.

## Invariants

- `normal_price`, `promotional_price`, normalized quote evidence, and raw source
  evidence retain their source-derived values.
- Median, outlier, source-disagreement, and price-jump calculations continue to
  consume the exact `Decimal` values and are not modified.
- The same finalized value is used by the single-food response and its optional
  override.
- No frontend change or database migration is needed.

## Verification

Add direct helper cases for `235566`, `432345`, `432999`, and `432000`. Preserve
the existing exact decision-engine assertions. Add a single-food research case
with a non-integer trusted average and assert a `235000` candidate. Extend the
weekly persistence coverage to assert reference and history values are exact
multiples of `1000`, while existing quote evidence assertions remain unchanged.
