# Nutrition food-data provenance

The approved base catalogue contains 65 food identities commonly used in Iran.
Identity, planner role, nutrient composition, market pricing, and prepared meals
remain separate relational records joined by canonical food ID.

Composition snapshot `sr-legacy-2018-04` uses USDA FoodData Central SR Legacy,
downloaded from the official dataset page on 2026-08-09. Values are stored per
100 g edible portion and retain the source FDC ID. The selected measurement basis
is explicit for every identity: `raw`, `dry`, or `as_purchased`. Missing nutrient
values are absent, never zero.

Four regional breads (Sangak, Barbari, Lavash, and Taftoon) remain catalogue
identities in `draft` state because the USDA snapshot is not an authoritative
composition match for those Iranian products. They cannot enter planning until a
documented regional source is reviewed and attached.

Legacy cooked basmati rice and grilled chicken records are retired so new plans
cannot mix cooked and raw quantity bases. Historical plan snapshots and foreign
keys remain intact. Plain yogurt is retained as the approved canonical identity
and its composition/provenance is replaced by the versioned as-purchased source.

Prepared foods and meals remain in `nutrition_catalogue_meals` and
`nutrition_catalogue_meal_items`; they do not share identity rows with the raw,
dry, and as-purchased ingredient catalogue.
