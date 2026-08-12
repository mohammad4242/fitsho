# Nutrition Program Seeds and Meal-Count Adaptation Design

## Scope

Fitsho will seed exactly 25 active weekly Nutrition Program templates: five each for
Economy, Balanced Iranian, High-Protein Gym, Quick & Easy, and Premium / Varied.
Programs select existing verified Meal Catalogue records by their canonical UUIDs and never
copy meals, ingredient quantities, or nutrition values.

The existing Nutrition Program Catalogue, Meal Catalogue, weekly planner, nutrition profile,
tracking, food-photo estimation, and admin surfaces remain the source architecture. No parallel
catalogue, planner, or photo-estimation system will be introduced.

## Stored Program Structure

Each program has a stable code (`ECO01` through `PREM05`), bilingual name and description,
diet style, and seven ordered days. Saturday through Thursday contain breakfast, lunch, snack,
and dinner. Friday contains breakfast, a Free Meal, snack, and dinner.

`NutritionProgramSlot` gains an explicit slot kind. A catalogue-meal slot has a non-null
`meal_id`; a Free Meal slot has a null `meal_id`. Database constraints enforce this pairing.
Free Meal is therefore part of the ordered weekly structure without becoming a fake Meal
Catalogue record.

Every catalogue reference is seeded from a constant canonical code-to-UUID registry. Seed
validation fails on a missing UUID, code mismatch, category mismatch, non-verified meal, or
name mismatch. Seeding is deterministic and idempotent, updates the 25 owned seed programs,
and does not modify Food Catalogue or Meal Catalogue rows.

## Deterministic Frequency Adaptation

An adapter converts one stored weekly template into the user's requested daily slot structure.
It consumes the existing `MainMealCountBucket` and `SnackCountBucket`. The legacy numeric fields
are bucket-normalized today and are not treated as independent exact counts.

- Two main meals: lunch and dinner; Friday uses Free Meal and dinner.
- Three main meals: breakfast, lunch, and dinner; Friday uses breakfast, Free Meal, and dinner.
- Four-or-more: exactly four main meals with current bucket-only data: breakfast, lunch,
  deterministic extra main meal, and dinner. Friday replaces lunch with Free Meal.
- Breakfast is emitted at most once.
- The extra main meal is selected only from verified lunch/dinner meals already referenced by
  the chosen weekly program. It prefers a meal different from that day's lunch and dinner and
  uses stable code/UUID ordering as its deterministic tie-breaker.
- Zero, one, two, and three-or-more snack buckets emit exactly 0, 1, 2, and 3 snacks. Additional
  snacks come only from verified `SN*` meals present in the chosen program, avoid same-day
  duplicates where possible, and use stable ordering.
- `PW01` remains optional, training-day-only, and independent of main/snack counts.

The adapted meal set constrains planner template eligibility. The nutrition engine may alter
only existing ingredient amounts inside `min_grams` and `max_grams`. Frequency changes and
optional post-workout inclusion redistribute the unchanged daily target across emitted slots.
No arbitrary catalogue meals or ingredient combinations are introduced.

## Free Meal Tracking

The member weekly-plan UI labels the special slot `وعده آزاد` and shows this Persian guidance:

> لطفاً جهت محاسبه کالری روزانه از وعده آزاد عکس بگیرید و اطلاعات مهم وعده آزاد را اینجا وارد کنید.

It provides four editable numeric inputs: calories, protein, carbohydrate, and fat. The photo is
optional. Its action opens the existing nutrition tracking photo-estimation section with the
selected date and Free Meal return context. After the member confirms the AI estimate, the app
returns to the Free Meal slot and pre-fills all available macro values. The member may correct
them before saving.

Saving uses the existing nutrition tracking ledger with an explicit Free Meal association. The
four values contribute to actual totals for that date; they do not change planned daily targets.
If the photo estimator cannot provide a value, that input remains editable and must be completed
before the Free Meal is saved.

## Admin Experience

Admin list and editor surfaces show program code, bilingual program identity, diet style, all
seven days, slot type, and meal identity. Catalogue meal labels always render as
`meal_code — Persian meal name`, with the English name visible as secondary content. Free Meal
renders as `وعده آزاد`; raw UUIDs remain relationship values but are not primary labels.

The editor supports the special Free Meal slot only where the weekly structure permits it and
does not offer a fake meal option.

## Data Flow and Safety

Program selection supplies the adapter with one stored template and the nutrition profile's
meal-count buckets. The adapter returns ordered day slots plus unchanged daily target metadata.
The planner receives only the selected catalogue meal IDs and computes bounded portions. The
weekly-plan response preserves catalogue provenance and exposes special slots explicitly.

Existing exclusions, preferences, micronutrient targets and upper limits, budget checks,
ingredient bounds, ownership checks, photo consent, and private-media behavior remain active.
Invalid seed registry references fail loudly instead of falling back to fuzzy name matching.

## Verification

Backend tests cover exact seed counts and style distribution, the complete canonical UUID
registry, Gym/Economy constraints, Friday Free Meal shape, idempotency, special-slot database
constraints, all main/snack bucket adaptations, deterministic extra selection, optional PW01,
unchanged targets, bounded planner inputs, and no fake meal row.

Frontend tests cover admin labels and seven-day display, Free Meal labeling, four macro inputs,
optional photo navigation, confirmed-estimate return and prefill, same-day total aggregation,
and unchanged planned targets. Final verification runs backend tests, Ruff, `mypy app`, frontend
tests, lint, build, and Alembic head/upgrade checks.
