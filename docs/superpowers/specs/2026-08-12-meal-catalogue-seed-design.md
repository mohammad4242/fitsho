# Meal Catalogue Seed Design

## Scope

Complete the existing normalized Meal Catalogue with 38 requested templates. First publish source-backed nutrition and palm portions for Sangak, Barbari, Taftoon, and Lavash. Do not change planner behavior or seed weekly Nutrition Programs.

## Bread evidence

The four bread identities remain in the existing Food Catalogue. Their energy, protein, carbohydrate, fat, fibre, and total sugar values per 100 g come from the Iranian glycemic-index study (DOI `10.5812/ijem.99793`). Potassium and the bread-specific minerals actually measured in Iranian studies come from the systematic review (DOI `10.1186/s41043-022-00327-9`). Each composition row stores its own source metadata. Unreported nutrients remain unavailable and are never written as zero.

The palm portion follows the Iranian Ministry of Health training package: one palm without fingers is approximately 30 g for Sangak, Barbari, and Taftoon; four Lavash palms are approximately 30 g, so one Lavash palm is represented as 7.5 g. These are display portions and do not replace canonical per-100-g composition.

## Meal identity and seeding

Add a required, unique, uppercase human-readable `code` to `nutrition_catalogue_meals`. Seeded codes are `BF01`–`BF08`, `LU01`–`LU13`, `DN01`–`DN08`, `SN01`–`SN08`, and `PW01`. Existing deterministic starter meals are reassigned to their matching requested codes so foreign-key references survive. Other existing/admin-created rows receive stable legacy codes during migration.

Admin create requires a code. Code is returned by list/detail responses, displayed in the catalogue/editor, and remains immutable during edit. Seed operations upsert by code, replace only seeded meal ingredients, and never delete custom catalogue meals.

All meal ingredients reference existing Food Catalogue IDs. Sangak is the default bread for bread-bearing templates, including the explicitly requested Abgoosht lunch. The existing verified `creamy-peanut-butter` Foundation Food is used for peanut-butter templates. Composite Iranian dishes are represented by their existing normalized food components rather than duplicated nutrition values.

## Verification and bounds

Each ingredient has reference, minimum, and maximum grams, required/optional status, and one functional role. Bounds describe adjustable meal structure only; calories and ingredient quantities are not copied into meal rows. A seeded meal becomes verified only when every referenced Food Catalogue item is verified.

Post-workout contains only `PW01` with egg and potato. No weekly Nutrition Program records are created and the nutrition planner/engine is unchanged.

## Migration and tests

One migration publishes the four breads and palm portions. A following migration adds/backfills the meal code constraint. Runtime seed data is idempotent and is exercised against a catalogue containing the required existing imported foods.

Backend tests cover bread nutrients/provenance/portions, meal code uniqueness and immutability, exact category counts and codes, ingredient bounds/roles/FKs, idempotency, and the single post-workout template. Frontend tests cover code display and create/edit behavior. Final checks include Alembic upgrade, backend tests/Ruff/mypy, frontend tests/lint/build, active-database seed counts, and grouped admin API verification.
