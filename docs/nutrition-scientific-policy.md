# Nutrition scientific and micronutrient policy

## Versioned calculation policy

`nutrition-science-v1` and `mifflin-net-met-v1` use the Mifflin-St Jeor equations for BMR, explicit
non-exercise activity multipliers, and net MET exercise energy. Goal energy remains bounded by BMR.
Macro hard minima are checked together against available calories; an infeasible combination returns
`TARGET_INFEASIBLE` rather than lowering a minimum silently. Protein uses the documented reference-
mass adjustment when actual mass exceeds the BMI-25 reference mass.

WHO guidance supplies the enabled policy semantics for free sugar, saturated fat, trans fat, and
general healthy-diet limits. Human micronutrient targets do not come from food-composition data.

Official references:

- WHO healthy diet: https://www.who.int/news-room/fact-sheets/detail/healthy-diet
- WHO free sugars guideline: https://www.who.int/publications/i/item/9789241549028
- NASEM Dietary Reference Intakes: https://nap.nationalacademies.org/collection/57/dietary-reference-intakes
- NASEM sodium and potassium DRI: https://nap.nationalacademies.org/catalog/25353/dietary-reference-intakes-for-sodium-and-potassium
- NIH ODS professional fact sheets: https://ods.od.nih.gov/factsheets/list-all/

## Micronutrient registry and semantics

`micronutrient-dri-v1` stores source organization, URL, access date, age, sex, life stage, dietary
modifier, reference kind, unit/form, aggregation window, and UL scope for every row. Supported core
targets include zinc, calcium, potassium, magnesium, iron, vitamin C, vitamin D, vitamin B12,
folate, and sodium.

- RDA is a planning target, not a diagnosis.
- AI is shown as AI and never relabeled RDA.
- EAR is never used as an individual's hard minimum.
- UL applies only to its recorded scope; supplemental-only limits are not applied to food intake.
- Sodium uses 1,500 mg AI and 2,300 mg CDRR; no sodium toxicity UL is fabricated.
- Potassium has an AI and no fabricated healthy-population UL.
- Folate uses dietary folate equivalents; vitamin D retains `1 mcg = 40 IU` metadata.
- Missing food-composition data remains unavailable, never zero.

NIH ODS nutrient pages used by the source registry are persisted in migration
`20260808_38_add_micronutrient_policy.py` and include Calcium, Iron, Magnesium, Zinc, Vitamin C,
Vitamin D, Vitamin B12, Folate, and Potassium.

## Adequacy, optimization, and repair

The planner scores only verified compatible candidates. Micronutrient adequacy has a versioned
weight of `4`; preference `1`; cost `0.25`. A nutrient is optimization-eligible only when at least
80% of required composition data is available. The repair pass is deterministic, limited to three
iterations, adds bounded 50 g portions, prevents oscillation, and revalidates calories, macros,
budget, role eligibility, allergies, and applicable upper limits after every accepted change.

Low dietary intake is reported as a dietary gap with data confidence. It is never described as a
deficiency or medical diagnosis. Medical policy overrides take precedence over healthy-population
targets.
