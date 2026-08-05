# Task 3 scientific energy and nutrient-target engine design

Status: approved interactively on 2026-08-05. This document authorizes only
Task 3 of `fitsho-nutrition-implementation-spec.md`. It does not authorize food
catalogue, meal planning, shopping lists, prices, tracking, photo estimation,
supplements, or later-task work.

## Goals and boundaries

Build a deterministic, versioned engine that estimates adult energy needs and
nutrition targets from the single Fitsho profile. AI does not choose formulas,
limits, confidence, or targets. The engine reports estimates and uncertainty;
it does not describe predicted values as measurements and does not generate a
meal plan.

The engine supports `NUTRITION` and `BOTH`. `TRAINING` members do not receive a
nutrition estimate or nutrition UI in this task. Safety outcomes from Task 2
remain authoritative.

## Approved scientific sources

- Mifflin--St Jeor for resting energy expenditure.
- WHO Healthy diet guidance dated 2026-01-26 for carbohydrate, fibre, free
  sugar, total fat, saturated fat, trans fat, and sodium.
- National Academies Dietary Reference Intakes for the general protein and
  carbohydrate floors and energy-estimation context.
- 2024 Adult Compendium for structured exercise at ages 19--59.
- 2024 Older Adult Compendium for structured exercise at ages 60 and older.
- Morton et al. and the approved higher-than-RDA evidence for fitness-oriented
  protein targets.
- ESPEN's pragmatic adjusted-body-weight method when BMI is above 25.

All source identifiers and URLs are part of the versioned policy manifest.
The first immutable identifiers are `nutrition-science-v1` for the complete
policy and `mifflin-net-met-v1` for the energy formula family.

## Inputs

The immutable input snapshot contains:

- product mode;
- birth date and calculation date;
- age in completed years;
- height in centimetres;
- current weight and measurement timestamp;
- profile sex and optional metabolic equation basis;
- primary goal;
- daily non-exercise activity;
- explicit structured-exercise status;
- exercise type, days, minutes, intensity, and source when exercise exists;
- latest safety decision and policy version;
- reliable body-composition data when available, without making it mandatory;
- active workout-plan identifier and revision when it supplies exercise data.

The metabolic equation basis is `female_coefficient`, `male_coefficient`, or
unset. For profile sex `female` or `male`, the corresponding basis is the
default. For `other` and `prefer_not_to_say`, the UI asks an optional separate
calculation question. Skipping it returns a range spanning both coefficients.

## Structured-exercise rules

Daily movement outside deliberate exercise remains the existing typed activity
enum. The approved non-exercise multipliers are:

| Daily activity | Multiplier |
| --- | ---: |
| sedentary | 1.20 |
| light | 1.30 |
| moderate | 1.40 |
| very active | 1.50 |

Nutrition-only members first answer whether they currently train. An explicit
no means structured-exercise energy is zero and skips every exercise detail.
If yes, exercise type, days per week, minutes per session, and usual intensity
are required. Exercise types are resistance, endurance, mixed, and other;
intensities are light, moderate, and vigorous.

For `BOTH`, the resolver uses the active Fitsho workout plan when it contains
complete reliable duration and effort data. Otherwise it reuses training days,
session duration, and the newly stored required usual intensity from the
training profile. Fitsho training is classified as resistance unless the active
plan explicitly records a mixed prescription. Missing required information
blocks the estimate; the resolver never invents exercise or intensity.

The structured source is one of `user_reported`, `training_profile`, or
`active_fitsho_plan`. Nutrition-only exercise answers are stored independently
from daily activity. Combined-mode training data remains canonical in the
training profile or workout plan and is copied only into an immutable estimate
snapshot, avoiding a second mutable source of truth.

## Energy formulas

For weight `W` in kilograms, height `H` in centimetres, and age `A` in years:

```text
female_coefficient_bmr = 10W + 6.25H - 5A - 161
male_coefficient_bmr   = 10W + 6.25H - 5A + 5
```

If the basis is unset, both values form the BMR range. Otherwise the selected
value is both ends of the range. BMR is rounded to the nearest 1 kcal internally
and displayed to the nearest 10 kcal.

```text
non_exercise_energy = bmr * approved_daily_activity_multiplier
```

For ages 19--59, standard Compendium MET values use a baseline of
`1.0 kcal/kg/hour`. For ages 60 and older, `MET60+` values use the Older Adult
Compendium baseline of `0.810 kcal/kg/hour`. The engine adds only net exercise:

```text
adult_net_session_kcal = max(MET - 1, 0) * 1.0 * W * hours
older_net_session_kcal = max(MET60+ - 1, 0) * 0.810 * W * hours
weekly_exercise_kcal   = net_session_kcal * days_per_week
daily_exercise_kcal    = weekly_exercise_kcal / 7
tdee                   = non_exercise_energy + daily_exercise_kcal
```

This deliberately prevents resting energy from being counted once inside the
activity multiplier and again inside gross exercise MET energy.

Mifflin's source population was ages 19--78. Age 18 and ages above 78 are
supported only with a lower-confidence reason. The engine never supports an
under-18 calculation.

## Goal-adjusted calories

| Goal and exercise state | Preferred adjustment | Allowed range |
| --- | ---: | ---: |
| maintain weight | 0% | 0% |
| lose weight or fat loss | -15% | -10% to -20% |
| gain weight, no structured exercise | +5% | +5% |
| gain weight, structured exercise | +10% | +5% to +15% |
| build muscle with resistance exercise | +5% | +5% to +10% |
| body recomposition with resistance exercise | 0% | 0% to -5% |

An automatic calorie target is clamped so it is not below the corresponding
estimated BMR boundary. Requiring a lower target is not automated. Nutrition-
only members who explicitly do not train cannot use `build_muscle` or
`body_recomposition`; the API returns `GOAL_RESELECTION_REQUIRED`. The legacy
`improve_fitness` goal also requires reselection instead of a silent mapping.

## Protein calculation weight and targets

For BMI at or below 25, protein calculation weight equals current weight. Above
BMI 25:

```text
reference_weight = 25 * height_metres^2
calculation_weight = reference_weight + 0.33 * (actual_weight - reference_weight)
```

| State | Preferred protein |
| --- | ---: |
| general hard minimum | 0.8 g/kg calculation weight |
| no training, maintenance or gain | 1.0 g/kg |
| no training, energy deficit | 1.2 g/kg |
| endurance exercise | 1.4 g/kg |
| resistance or mixed exercise | 1.6 g/kg |
| resistance or mixed exercise with deficit | 1.8 g/kg |

The automatic ceiling is 2.2 g/kg calculation weight. Kidney/manual-policy
states never use this ordinary policy. Protein grams are rounded to the nearest
1 g. The result retains separate minimum and preferred values; later planners
must not disguise a preferred-target miss as meeting the minimum.

## Macronutrient and diet-quality targets

| Metric | Approved target |
| --- | --- |
| carbohydrate | 45--75% of energy and at least 130 g/day |
| total fat | hard range 15--30% of energy; preferred 20--30% |
| fibre | hard minimum 25 g/day; preferred max(25 g, 14 g/1000 kcal) |
| free sugar | less than 10% of energy; preferred at most 5% |
| added sugar | informational subset when reliable; never added to free sugar |
| saturated fat | less than 10% of energy |
| trans fat | less than 1% of energy and industrial trans fat avoided |
| sodium | less than 2,000 mg/day |

Energy conversion uses 4 kcal/g for protein and carbohydrate and 9 kcal/g for
fat. Macro and fibre values are rounded to 1 g, energy to 10 kcal for display,
and sodium to 10 mg. Internal Decimal calculations are retained until output
rounding. If approved protein, carbohydrate, and fat constraints cannot coexist
inside the calorie range, the engine returns a structured
`NUTRIENT_TARGET_CONFLICT`; it does not alter a hard WHO limit silently.

## Confidence and explanation

Every estimate and target has `high`, `medium`, or `low` confidence plus stable
reason codes. Confidence considers equation age coverage, metabolic-basis
selection, weight recency, activity source, exercise completeness, and whether
the MET value was measured or estimated. Required missing input blocks an
estimate rather than producing a low-confidence default.

Each target row includes policy version, formula version, source identifiers,
applicable population, input snapshot reference, rounding rule, unit, minimum,
preferred value or range, maximum, confidence, and explanation codes. Persian
and English prose is rendered from stable codes in the frontend, not persisted
as the scientific truth.

## Persistence design

Add the following relational concepts:

- `NutritionPolicyVersion`: immutable policy identifier, effective time,
  description, and source manifest.
- `NutritionStructuredExercise`: current nutrition-only exercise answers and
  their confirmation/source metadata.
- `NutritionEstimate`: append-only user-owned revision with safety decision,
  policy/formula versions, input snapshot, input signature, overall confidence,
  status, and timestamps.
- `NutritionEstimateTarget`: typed child rows for BMR, non-exercise energy,
  exercise energy, TDEE, calories, protein, carbohydrate, fat, fibre, sugars,
  saturated fat, trans fat, and sodium.

Core ownership, revision, enum, unit, and numeric constraints are relational.
The immutable input snapshot and ordered explanation metadata use JSON because
they are audit evidence, not mutable query-owned profile fields. A unique
`(user_id, revision)` constraint and an input-signature index make repeated
calculation deterministic and traceable.

Training intensity is added as a nullable profile column for migration safety.
New training and combined onboarding requires it. Existing training-only users
remain dashboard-ready; a combined nutrition estimate asks for it if missing.

## API and errors

Authenticated endpoints:

- `PUT /api/v1/nutrition/structured-exercise`
- `GET /api/v1/nutrition/structured-exercise`
- `POST /api/v1/nutrition/estimates`
- `GET /api/v1/nutrition/estimates/current`

Mutations require the existing trusted-origin protection. Estimate creation is
idempotent for an unchanged input signature and policy version; it returns the
existing latest revision rather than creating duplicate history.
The signature is SHA-256 over canonical JSON containing the approved input
snapshot and all formula/policy versions. `PUT structured-exercise` is available
only to nutrition-only members; combined members receive the resolved training
source from `GET` but cannot create a duplicate mutable exercise profile.
`GET estimates/current` reports whether its signature is stale against current
profile data, and the UI requests `POST estimates` when recalculation is needed.

Stable domain errors include `SHARED_PROFILE_REQUIRED`,
`SAFETY_SCREEN_REQUIRED`, `STRUCTURED_EXERCISE_REQUIRED`,
`METABOLIC_BASIS_REQUIRED` only when a single value is explicitly requested,
`GOAL_RESELECTION_REQUIRED`, `NUTRIENT_TARGET_CONFLICT`,
`PHYSICIAN_REVIEW_REQUIRED`, and `NUTRITION_ESTIMATE_BLOCKED`.

`AUTOMATIC_DRAFT_REQUIRES_PHYSICIAN_REVIEW` may produce an inactive estimate
marked for review. `PHYSICIAN_MANUAL_PLAN_REQUIRED` and
`UNSUPPORTED_OR_HARD_BLOCKED` do not receive ordinary targets.

## Frontend behavior

The bilingual guided training flow adds a required usual-intensity question.
Nutrition-only members see exercise type, days, duration, and intensity only
after saying they train. Selecting no training skips them all.

Nutrition and combined members receive a dashboard link to a daily-needs page.
The page creates or loads the current estimate and shows, in Persian or English:

- estimated basal metabolism;
- estimated daily energy expenditure;
- calorie target range;
- protein minimum and preferred target;
- carbohydrate and fat ranges;
- fibre, free-sugar, saturated-fat, trans-fat, and sodium limits;
- confidence and plain-language explanation codes.

RTL and LTR follow the selected language. The UI never labels the estimates as
measurements and never exposes a nutrition card to training-only members.

## Test strategy

Implementation follows red-green-refactor. Focused tests cover:

- published-formula examples and rounding;
- both Mifflin coefficients and coefficient-range fallback;
- activity multipliers and adult/older-adult net MET math;
- proof that resting exercise energy is not double counted;
- explicit no-training behavior;
- combined-mode source priority and missing-intensity rejection;
- adjusted weight at, below, and above BMI 25;
- every goal and protein branch;
- WHO macro and diet-quality limits;
- medical review and blocked outcomes;
- immutable revision and idempotent signature behavior;
- ownership, authentication, trusted origin, and structured API errors;
- bilingual conditional questions and estimate presentation;
- migration upgrade, backend lint/typecheck/tests, and frontend lint/tests/build.

No Task 4 food or meal model is introduced by these tests or implementation.

## References

- https://pubmed.ncbi.nlm.nih.gov/2305711/
- https://www.who.int/news-room/fact-sheets/detail/healthy-diet
- https://nap.nationalacademies.org/collection/57/dietary-reference-intakes
- https://nap.nationalacademies.org/resource/26818/DRIs_for_Energy_Highlights.pdf
- https://pmc.ncbi.nlm.nih.gov/articles/PMC10818145/
- https://pmc.ncbi.nlm.nih.gov/articles/PMC10818108/
- https://pubmed.ncbi.nlm.nih.gov/28698222/
- https://pubmed.ncbi.nlm.nih.gov/31794597/
- https://www.espen.org/files/ESPEN-Guidelines/European_guideline_on_obesity_care_in_patients_with_gastrointestinal_and_liver_diseases_Joint_ESPEN_UEG%20guideline.pdf
