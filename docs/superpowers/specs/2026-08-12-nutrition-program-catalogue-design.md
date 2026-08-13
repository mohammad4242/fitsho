# Nutrition Program Catalogue Design

## Scope

Add an admin-only catalogue of seven-day nutrition program structures. Programs group by diet style and reference verified Meal Catalogue meals. This work does not change the Food Catalogue, Meal Catalogue, seeded data, or nutrition planner/engine behavior.

## Domain model

`NutritionProgram` stores bilingual identity, one of five diet styles, a global post-workout switch, and an active/archived lifecycle. It has exactly seven ordered `NutritionProgramDay` records. Each day stores whether post-workout is enabled for that day and owns `NutritionProgramSlot` records.

Every day contains one breakfast, lunch, snack, and dinner slot. A post-workout slot exists only when the program-level switch and that day's override are both enabled. Each slot stores only its slot category and an existing Meal Catalogue `meal_id`; it stores no calories, nutrients, ingredient quantities, or fitness goal.

Diet styles are:

- `economy`
- `balanced_iranian`
- `high_protein_gym`
- `quick_easy`
- `premium_varied`

## Validation

Writes must contain exactly seven days numbered 1 through 7 and no duplicate slots. Each meal must exist, have `verified` status, and match the assigned slot category. Disabling post-workout globally rejects post-workout slots and normalizes all day overrides to disabled. Enabling it requires a post-workout meal only for individually enabled days.

Fitness goals remain absent from this catalogue and continue to belong to the existing profile/planning domains.

## Lifecycle and API

Admin routes live under `/api/v1/nutrition/admin/programs`:

- list, filter by diet style and lifecycle
- read one program
- create a program
- replace a program
- archive with `DELETE`
- restore with `POST /{program_id}/restore`

All routes require administrator access. Mutations retain the existing trusted-origin protection. Archived programs are hidden by default but can be listed explicitly and restored.

## Admin UI

Routes follow Training Program Templates conventions:

- `/admin/nutrition-programs`
- `/admin/nutrition-programs/new`
- `/admin/nutrition-programs/:programId/edit`

The catalogue page filters by the five diet styles and lifecycle. The editor provides bilingual identity fields, a global post-workout control, seven day sections, fixed meal slots, and per-day post-workout controls. Meal pickers show only verified meals from the matching Meal Catalogue category. Archive and restore actions are explicit.

The UI reuses Fitsho admin tokens and components. Its signature structure is a seven-column weekly rail on wide screens that becomes seven stacked day cards on mobile, keeping RTL and LTR layouts usable.

## Testing

Backend tests cover authorization, diet-style filtering, the seven-day contract, verified/category-matched meal references, conditional post-workout behavior, CRUD, archive, and restore. Frontend tests cover API contracts, filtering, creation/editing, meal assignment, post-workout controls, archive/restore, navigation, translations, and responsive-safe rendering. Final verification includes backend tests, Ruff, mypy, Alembic upgrade, frontend tests, lint, and build.
