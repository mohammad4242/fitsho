# Training Template Library Design

## Goal

Create an admin-only, database-backed library of evidence-informed hypertrophy training templates for two through six weekly training days. The library is a curated reference and does not yet change the deterministic Fitsho program engine's selection behavior.

## Scope

- Seed at least five original, standard template structures for each of two, three, four, five, and six days per week.
- Show templates only through protected admin API and admin UI routes.
- Label every template with training level, focus tags, and intensity methods.
- Persist each template day and its ordered exercise slots.
- Link a slot to an existing exercise when its stable exercise slug resolves. Preserve unresolved choices as explicit placeholders with a requested exercise name and movement pattern.

## Data model

`training_program_templates` owns the template metadata: stable slug, bilingual name and description, days per week, training level, goal, focus tags, intensity methods, source attribution, and active state.

`training_program_template_days` owns an ordered day, bilingual title, and the direct target muscles. `training_program_template_slots` owns ordered prescription boundaries, target muscles, movement pattern, intensity method, and a nullable exercise foreign key. Nullable `exercise_id` is intentional: it means the catalog cannot yet satisfy that curated slot. A non-null exercise is a foreign-key-backed link, never copied exercise text.

## Data flow

The idempotent seed resolves catalog slugs during execution, writes templates and their days and slots, and leaves unavailable exercises unlinked. The admin service loads a complete template graph. The protected admin router serializes it for the React admin page. There is no public router, engine read path, or user navigation entry.

## Template policy

The 25 templates are original Fitsho structures, informed by resistance-training evidence and conventional coach programming patterns; they are not copied programs. They cover full-body, upper/lower, push-pull-legs, body-part rotation, priority blocks, and time-efficient superset or drop-set variants. Weekly frequency is a scheduling choice; volume, progression, safety, and final exercise eligibility continue to belong to the deterministic engine.

## Validation and safety

Database constraints limit `days_per_week` to 2 through 6 and slot set/rep/rest values to valid non-negative ranges. Pydantic response models expose only defined enums. Tests prove non-admin access is denied, every seeded days-per-week bucket has at least five templates, exercises resolve when present, placeholders stay nullable when absent, and public users have no route.

## Out of scope

- Editing templates in the browser.
- Automatic selection of templates by the training engine.
- Adding exercises that do not exist in the catalog.
- Medical or injury advice.
