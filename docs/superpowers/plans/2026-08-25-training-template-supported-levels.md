# Training Template Supported Levels Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Consolidate the 41 level-specific catalog rows into 17 shared templates with multi-level eligibility, full Admin CRUD, and unchanged downstream personalization.

**Architecture:** Persist one non-empty `supported_levels` JSON list on each `TrainingProgramTemplate`; days and slots remain shared children. Canonical seeding emits 17 rows. The repository adapter exposes one engine reference per supported level so established exact-level selection and personalization code remains stable.

**Tech Stack:** Python 3.12, FastAPI, Pydantic, SQLAlchemy, Alembic, PostgreSQL, React 19, TypeScript, Vite, Vitest.

**Spec:** `docs/superpowers/specs/2026-08-25-training-template-supported-levels-design.md`

## Global Constraints

- Persist no level-specific template, day, slot, or variant rows.
- `supported_levels` contains one to four unique values from `first_month`, `beginner`, `intermediate`, and `advanced`.
- T01-T17 seed synchronization produces exactly 17 managed `TrainingProgramTemplate` rows.
- New Admin templates use the same API, persistence, adapter, and Program Engine path.
- Preserve all existing safety, injury, equipment, duration, recovery, priority, substitution, and validation logic.
- Preserve unrelated worktree files and stage only task files.
- Back up and validate the live PostgreSQL database before applying the migration.

---

### Task 1: Persistence contract and migration

**Files:**
- Create: `backend/alembic/versions/20260825_108_add_template_supported_levels.py`
- Modify: `backend/app/training_templates/models.py`
- Modify: `backend/tests/training_templates/test_seed.py`
- Modify: `backend/tests/training_templates/test_canonical_catalog_replacement.py`

**Interfaces:**
- Produces: `TrainingProgramTemplate.supported_levels: list[str]` containing enum values
- Removes: `TrainingProgramTemplate.training_level`
- Migration input: current level-suffixed managed rows such as `t01-2-day-full-body-ab-beginner`
- Migration output: canonical rows such as `t01-2-day-full-body-ab`

- [ ] **Step 1: Write failing persistence tests**

Assert the model and seeded rows expose non-empty unique `supported_levels`, no scalar
`training_level`, and exactly 17 canonical managed rows.

- [ ] **Step 2: Run tests to verify failure**

Run: `cd backend && uv run pytest tests/training_templates/test_seed.py tests/training_templates/test_canonical_catalog_replacement.py -q`

Expected: failures showing 41 rows and the missing `supported_levels` field.

- [ ] **Step 3: Add migration and ORM field**

Add a JSON `supported_levels` column, consolidate managed rows by the exact 17 canonical prefixes,
union their scalar levels in enum order, rename keepers to canonical slugs, delete duplicates, make
the new field non-null, then drop `training_level`. Map the ORM field as:

```python
supported_levels: Mapped[list[str]] = mapped_column(JSON, nullable=False)
```

Use an explicit model validator/service boundary to persist enum values as strings.

- [ ] **Step 4: Verify migration and focused tests**

Run:

```bash
cd backend
uv run alembic upgrade head
uv run pytest tests/training_templates/test_seed.py tests/training_templates/test_canonical_catalog_replacement.py -q
uv run ruff check app/training_templates/models.py alembic/versions/20260825_108_add_template_supported_levels.py tests/training_templates
```

Expected: migration reaches `20260825_108`; persistence tests pass.

- [ ] **Step 5: Commit and push**

```bash
git add backend/alembic/versions/20260825_108_add_template_supported_levels.py backend/app/training_templates/models.py backend/tests/training_templates/test_seed.py backend/tests/training_templates/test_canonical_catalog_replacement.py
git commit -m "refactor(training-templates): persist shared supported levels"
git push origin main
```

---

### Task 2: Canonical seed consolidation

**Files:**
- Modify: `backend/app/training_templates/seed_data.py`
- Modify: `backend/app/training_templates/service.py`
- Modify: `backend/tests/training_templates/test_seed.py`
- Modify: `backend/tests/training_templates/test_canonical_catalog_replacement.py`

**Interfaces:**
- Produces: `TRAINING_PROGRAM_TEMPLATE_SEEDS` with exactly 17 entries
- Produces: each seed’s `supported_levels: tuple[ExperienceLevel, ...]`
- Consumes: canonical movement slug and shared day/slot fields from `CANONICAL_TEMPLATE_DEFINITIONS`

- [ ] **Step 1: Write failing seed tests**

Assert each canonical slug appears once, T01 contains first-month/beginner/intermediate, all supported
levels are unique, slots use real active programmable exercises, and two seed runs are idempotent.

- [ ] **Step 2: Run tests to verify failure**

Run: `cd backend && uv run pytest tests/training_templates/test_seed.py tests/training_templates/test_canonical_catalog_replacement.py -q`

Expected: failures from level expansion and level-suffixed slugs.

- [ ] **Step 3: Replace level expansion with shared rendering**

Remove `_expand_definition`, `slugs_by_level`, and level-driven `_prescription`. Build one seed per
definition using the movement’s canonical slug and the canonical shared slot values. Preserve
straight-set methods and current adaptation priorities.

- [ ] **Step 4: Update seed synchronization**

Match managed rows by canonical slug, write `supported_levels`, replace owned days/slots, deactivate
obsolete managed rows, and return `templates=17`. Preserve unrelated Admin-created templates.

- [ ] **Step 5: Verify seed behavior**

Run:

```bash
cd backend
uv run pytest tests/training_templates/test_seed.py tests/training_templates/test_canonical_catalog_replacement.py -q
uv run ruff check app/training_templates tests/training_templates
```

Expected: all focused tests pass with 17 managed templates and zero placeholders.

- [ ] **Step 6: Commit and push**

```bash
git add backend/app/training_templates/seed_data.py backend/app/training_templates/service.py backend/tests/training_templates
git commit -m "refactor(training-templates): seed seventeen shared templates"
git push origin main
```

---

### Task 3: Admin API and engine adapter

**Files:**
- Modify: `backend/app/admin/schemas.py`
- Modify: `backend/app/admin/router.py`
- Modify: `backend/app/training_templates/admin_service.py`
- Modify: `backend/app/training_templates/service.py`
- Modify: `backend/app/training_templates/engine_reference.py`
- Modify: `backend/app/workouts/program_engine/schemas.py`
- Modify: `backend/tests/admin/test_training_template_api.py`
- Modify: `backend/tests/workouts/program_engine/test_template_reference.py`

**Interfaces:**
- `list_training_program_templates(db, days_per_week=None, training_level=None)` filters level membership.
- `delete_training_program_template(db, template_id) -> bool` hard-deletes one template.
- Admin read/write schemas expose `supported_levels: list[ExperienceLevel]`.
- `load_template_references(db)` returns one `TemplateReference` per supported level with shared content.

- [ ] **Step 1: Write failing API and adapter tests**

Cover same canonical ID in beginner/intermediate filtered responses, multi-level create/update, empty
and duplicate level rejection, hard delete with cascades, and engine references for every supported
level. Include an Admin-created template in adapter selection coverage.

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
cd backend
uv run pytest tests/admin/test_training_template_api.py tests/workouts/program_engine/test_template_reference.py -q
```

Expected: failures from scalar level schemas and missing delete route.

- [ ] **Step 3: Implement Admin contract and delete**

Replace scalar level fields with bounded unique lists, add optional level query filtering, serialize
all supported levels, and add trusted-origin `DELETE /training-program-templates/{template_id}`.
Keep template replacement atomic and retain current exercise and shape validation.

- [ ] **Step 4: Implement engine compatibility adapter**

Load each active shared template once, then emit one immutable reference per supported level. Keep
the existing `TemplateReference.training_level` field so selectors need no safety-sensitive rewrite.
Use the canonical slug for every reference so diagnostics identify the same template.

- [ ] **Step 5: Verify backend integration**

Run:

```bash
cd backend
uv run pytest tests/admin/test_training_template_api.py tests/workouts/program_engine/test_template_reference.py tests/workouts/program_engine/test_template_selector_baseline.py -q
uv run ruff check app/admin app/training_templates tests/admin/test_training_template_api.py tests/workouts/program_engine/test_template_reference.py
uv run mypy app/admin app/training_templates
```

Expected: focused tests, Ruff, and mypy pass.

- [ ] **Step 6: Commit and push**

```bash
git add backend/app/admin backend/app/training_templates backend/app/workouts/program_engine/schemas.py backend/tests/admin/test_training_template_api.py backend/tests/workouts/program_engine/test_template_reference.py
git commit -m "feat(training-templates): support shared multi-level templates"
git push origin main
```

---

### Task 4: Admin UI multi-level editing and deletion

**Files:**
- Modify: `frontend/src/features/admin/types.ts`
- Modify: `frontend/src/features/admin/api.ts`
- Modify: `frontend/src/features/admin/AdminTrainingTemplatesPage.tsx`
- Modify: `frontend/src/features/admin/AdminTrainingTemplateEditorPage.tsx`
- Modify: `frontend/src/features/admin/AdminTrainingTemplatesPage.test.tsx`
- Modify: `frontend/src/features/admin/AdminTrainingTemplateEditorPage.test.tsx`
- Modify: `frontend/src/features/admin/admin.css`
- Modify: `frontend/src/i18n/fa.ts`
- Modify: `frontend/src/i18n/en.ts`

**Interfaces:**
- `AdminTrainingProgramTemplate.supported_levels: ExperienceLevel[]`
- `AdminTrainingProgramTemplateWrite.supported_levels: ExperienceLevel[]`
- `getAdminTrainingProgramTemplates(days, level?)` sends both filters.
- `deleteAdminTrainingProgramTemplate(templateId)` calls the trusted Admin DELETE endpoint.

- [ ] **Step 1: Write failing component and API tests**

Cover one card across two level filters with the same ID, all level badges, multi-select editing
without day/slot cloning, multi-level creation, removal of one level, and confirmed deletion.

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
cd frontend
npm run test -- src/features/admin/AdminTrainingTemplatesPage.test.tsx src/features/admin/AdminTrainingTemplateEditorPage.test.tsx src/features/admin/api.test.ts
```

Expected: type/runtime failures from scalar `training_level` and missing delete integration.

- [ ] **Step 3: Update types and API client**

Replace scalar fields with `supported_levels`, pass optional level filter, and implement the DELETE
request using the existing API client and trusted origin behavior.

- [ ] **Step 4: Update library and editor**

Render each API template once, show all supported levels, and fetch filtered results from the server.
Replace the level select with four checkboxes/toggles bound only to `supported_levels`. Add a
confirmation-controlled delete action for existing templates.

- [ ] **Step 5: Add Persian-first copy and focused styling**

Add concise bilingual labels for supported levels, required selection, and deletion confirmation.
Keep the current responsive Admin design system and mobile behavior.

- [ ] **Step 6: Verify frontend integration**

Run:

```bash
cd frontend
npm run test -- src/features/admin/AdminTrainingTemplatesPage.test.tsx src/features/admin/AdminTrainingTemplateEditorPage.test.tsx src/features/admin/api.test.ts
npm run lint
npm run build
```

Expected: focused tests, lint, and production build pass.

- [ ] **Step 7: Commit and push**

```bash
git add frontend/src/features/admin frontend/src/i18n/fa.ts frontend/src/i18n/en.ts
git commit -m "feat(admin): manage shared training template levels"
git push origin main
```

---

### Task 5: Live migration and final regression verification

**Files:**
- Runtime artifact: `backend/var/backups/training-templates-supported-levels-<timestamp>.dump`
- No source changes expected.

**Interfaces:**
- Live database must report 17 managed canonical rows after migration and seed synchronization.
- Authorized Admin API must return the same template ID under every supported level filter.

- [ ] **Step 1: Create and validate database backup**

Run `pg_dump` in custom format into `backend/var/backups/`, then verify it with `file` and
`pg_restore -l` before schema mutation.

- [ ] **Step 2: Apply migration and canonical seed**

Run:

```bash
cd backend
uv run alembic upgrade head
uv run python -m app.training_templates.seed
```

Expected: Alembic reaches `20260825_108`; seed reports 17 templates and zero placeholders.

- [ ] **Step 3: Verify live database and API contract**

Query managed/template/day/slot counts and supported-level unions. Verify the authorized API returns
HTTP 200 and identical canonical IDs for a template selected through two supported levels. Remove
any temporary auth session created for verification.

- [ ] **Step 4: Run backend regression checks**

Run:

```bash
cd backend
uv run pytest tests/training_templates tests/admin/test_training_template_api.py tests/workouts/program_engine -q
uv run ruff check
uv run mypy
```

Expected: all commands pass.

- [ ] **Step 5: Run frontend regression checks**

Run:

```bash
cd frontend
npm run test
npm run lint
npm run build
```

Expected: all commands pass.

- [ ] **Step 6: Verify Git and remote state**

Run `git status --short --branch`, `git log -4 --oneline`, `git fetch origin`, and verify local HEAD
equals `origin/main`. Do not stage unrelated files.
