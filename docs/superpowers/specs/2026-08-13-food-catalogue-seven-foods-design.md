# Seven Food Catalogue Foods Design

## Scope

Add exactly the requested seven canonical foods to the existing Food Catalogue seed. Four
already exist and will be completed in place. Add dried barberries and low-moisture whole-milk
mozzarella. Rename the existing raw 90/10 ground-beef identity from `beef` to `ground-beef`
without changing its database identity or breaking meal references.

No spices, seasonings, prepared recipes, or unrelated foods are included.

## Sources and measurement basis

- USDA FoodData Central Foundation Foods supplies creamy peanut butter, unsalted canned tomato
  paste, raw green beans, and dry wheat flour.
- USDA FoodData Central SR Legacy supplies low-moisture whole-milk mozzarella and raw ground beef
  with 90% lean meat and 10% fat.
- Czech Food Composition Database record 0945 supplies dried `Berberis vulgaris` barberries.
- Every composition value is stored per 100 g edible portion with its source name, direct source
  reference, food/database ID where available, data version, access date, and high confidence.
- Unsupported nutrients remain absent. Zero is stored only when the source explicitly reports
  zero.
- Measurement bases are `raw` for green beans and ground beef, `dry` for wheat flour and dried
  barberries, and `as_purchased` for peanut butter, tomato paste, and mozzarella.
- No household portion is added without a defensible gram-weight source.

## Data preservation

An Alembic migration renames the existing `beef` catalogue row to `ground-beef` in place and
updates its names and aliases safely. Existing foreign keys continue to reference the same UUID.
The downgrade reverses the canonical slug and names. The seed also retires an obsolete duplicate
`beef` row if one is encountered after the canonical row already exists.

## Verification

Tests cover the exact seven slugs, uniqueness, names, measurement bases, source IDs, source
metadata on every composition, required primary nutrients, preservation of unavailable values,
and the rule that incomplete primary data cannot be marked verified. A migration test verifies
that the ground-beef rename preserves row identity and meal references. Relevant backend tests,
Ruff, formatting, MyPy, and a clean migration upgrade are run before commit and push.
