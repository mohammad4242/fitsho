# Nutrition Tasks 7-13 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete the approved Iranian food-data foundation and implement Nutrition Tasks 7 through 13 without coupling tracking, clinical review, supplements, or UI to external price/AI providers.

**Architecture:** Extend the existing FastAPI nutrition module with focused domain services and normalized append-only records. The nutrition planner continues to use immutable catalogue, composition, and accepted-price snapshots; plan edits create revisions; tracking records facts; physician workflows control approval/activation; supplements remain physician-owned. React routes consume those APIs through the existing authenticated client and i18n system.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2, Alembic, PostgreSQL, Pydantic 2, pytest, React 19, TypeScript, Vite, Vitest.

## Global Constraints

- Preserve all unrelated dirty work and existing workout/body-analysis behavior.
- Use `Decimal`/SQL `Numeric` or integer IRR; never binary floating point for canonical nutrition or money calculations.
- OpenRouter is allowed only for consented food-photo estimation in Task 9.
- Pending physician-review drafts remain visible but never become adherence baselines.
- Plan-defining changes create immutable revisions and require review; consumption facts do not mutate plans.
- Never fabricate composition values, prices, physician approval, diagnoses, or supplement prescriptions.
- Composition basis is raw, dry, or as-purchased per canonical food, as selected by the user.

---

### Foundation: Approved Iranian Catalogue Completion

**Files:**
- Create: `backend/app/nutrition/catalogue_seed_data.py`
- Create: `backend/alembic/versions/20260809_43_complete_iranian_food_catalogue.py`
- Modify: `backend/app/nutrition/enums.py`
- Modify: `backend/app/nutrition/models.py`
- Modify: `backend/app/nutrition/food_catalogue.py`
- Modify: `backend/app/nutrition/schemas.py`
- Test: `backend/tests/nutrition/test_food_catalogue.py`
- Test: `backend/tests/nutrition/test_food_catalogue_api.py`

**Interfaces:**
- Produces: versioned canonical-food identity, aliases, measurement basis, verified composition rows, roles, deterministic provider search metadata, and a distinct prepared-meal catalogue.
- Preserves: price mappings/quotes/references and historical plan snapshots in separate tables.

- [ ] Write tests proving the old cooked rice/chicken records are retired, raw/as-purchased basis is explicit, food aliases are deterministic, and missing nutrients remain absent rather than zero.
- [ ] Run `pytest tests/nutrition/test_food_catalogue.py tests/nutrition/test_food_catalogue_api.py -q` and observe expected failures for the new contract.
- [ ] Add the backward-compatible schema and curated official-source snapshot; only mark rows verified when the source mapping and mandatory macros are complete.
- [ ] Run scoped tests, migration upgrade/downgrade/upgrade, Ruff, and mypy.
- [ ] Commit as `feat(nutrition): complete approved Iranian food catalogue` and push `nutrition`.

### Task 7: Shopping, Revisions, and Review Foundation

**Files:**
- Create: `backend/app/nutrition/plan_editing.py`
- Create: `backend/app/nutrition/review_service.py`
- Create: `backend/app/nutrition/laboratory_service.py`
- Create: `backend/app/nutrition/supplement_service.py`
- Create: `backend/alembic/versions/20260809_44_add_nutrition_plan_editing.py`
- Modify: `backend/app/nutrition/models.py`
- Modify: `backend/app/nutrition/enums.py`
- Modify: `backend/app/nutrition/schemas.py`
- Modify: `backend/app/nutrition/router.py`
- Test: `backend/tests/nutrition/test_plan_editing.py`
- Test: `backend/tests/nutrition/test_plan_editing_api.py`

**Interfaces:**
- Produces: `build_shopping_list`, preview/confirm edit commands with expected revision, lock/feedback metadata, one-current-review-lineage enforcement, and minimal secure lab/supplement lifecycle foundations required by Task 7.
- Consumes: immutable Task 6 plan rows and accepted price snapshots.

- [ ] Write failing tests for exact aggregation, no package counts, edit previews, confirmation, stale conflicts, IN_REVIEW blocking, review invalidation, locks, feedback, and ownership.
- [ ] Run the scoped tests and confirm missing endpoints/services fail.
- [ ] Implement deterministic aggregation and revision cloning/revalidation inside one transaction.
- [ ] Run scoped and all nutrition tests, migration checks, Ruff, and mypy.
- [ ] Commit as `feat(nutrition): add task 7 plan editing and shopping` and push.

### Task 8: Consumption Tracking

**Files:**
- Create: `backend/app/nutrition/tracking_service.py`
- Create: `backend/alembic/versions/20260809_45_add_nutrition_tracking.py`
- Create: `frontend/src/features/nutrition/DailyTrackingPage.tsx`
- Modify: nutrition models, enums, schemas, router, API/types, routes, i18n, and nutrition CSS.
- Test: `backend/tests/nutrition/test_tracking.py`
- Test: `backend/tests/nutrition/test_tracking_api.py`
- Test: `frontend/src/features/nutrition/DailyTrackingPage.test.tsx`

**Interfaces:**
- Produces: quick check-ins, plan-pinned approximate entries, manual catalogue entries, quick approximations, corrections, daily summaries, recent foods, and history.
- Enforces: only the active approved revision can prefill `ON_PLAN`/`MOSTLY_ON_PLAN`.

- [ ] Write failing domain/API/frontend tests for all four states, no implicit eating, active-baseline pinning, pending-draft manual logging, allergy warnings, confidence, edit/delete, and insufficient data.
- [ ] Run the scoped tests and confirm failures are caused by missing tracking behavior.
- [ ] Implement normalized day/check-in/entry models, deterministic totals, APIs, and RTL UI.
- [ ] Run backend/frontend scoped suites, migrations, Ruff, mypy, frontend lint/build.
- [ ] Commit as `feat(nutrition): add task 8 low friction tracking` and push.

### Task 9: Food Photo Estimation

**Files:**
- Create: `backend/app/nutrition/photo_estimation.py`
- Create: `backend/app/nutrition/photo_provider.py`
- Create: `backend/alembic/versions/20260809_46_add_food_photo_estimation.py`
- Create: `frontend/src/features/nutrition/FoodPhotoEstimator.tsx`
- Modify: admin AI config, nutrition models/schemas/router, app lifecycle, config, API/types, i18n, and `.env.example`.
- Test: provider/schema/service/API/frontend photo tests using fixtures and mocked HTTP only.

**Interfaces:**
- Produces: consented temporary upload, strict structured estimate, deterministic catalogue mapping, confirmation/edit/delete, cost usage metadata, and fail-closed feature configuration.
- Enforces: unconfirmed estimates never enter consumption history and no medical/profile PII is sent.

- [ ] Write failing tests for upload validation, consent, malformed output, unresolved mapping, confirmation, allergy warning, deletion, disabled provider, secret masking, and model capability validation.
- [ ] Run scoped tests and confirm expected failures.
- [ ] Reuse encrypted admin credentials and official OpenRouter multimodal request patterns; calculate nutrition only from catalogue mappings.
- [ ] Run scoped/full affected checks and migrations.
- [ ] Commit as `feat(nutrition): add task 9 photo food estimation` and push.

### Task 10: Adherence and Adaptive Planning

**Files:**
- Create: `backend/app/nutrition/adherence_service.py`
- Create: `frontend/src/features/nutrition/NutritionHistoryPage.tsx`
- Modify: tracking models/schemas/router, planner input snapshot, API/types/routes/i18n/styles.
- Test: `backend/tests/nutrition/test_adherence.py`
- Test: `frontend/src/features/nutrition/NutritionHistoryPage.test.tsx`

**Interfaces:**
- Produces: visible metric components, versioned optional composite, chart series, filters, confidence/completeness, feedback-derived adaptation suggestions, and confirmed target-update requests.

- [ ] Write failing tests for exact/approximate weighting, insufficient-data semantics, transparent component totals, filters, no causal weight claims, and no automatic target mutation.
- [ ] Run failures, implement deterministic metric aggregation and accessible CSS/SVG chart presentation, then rerun.
- [ ] Run full affected backend/frontend checks.
- [ ] Commit as `feat(nutrition): add task 10 adherence and adaptive history` and push.

### Task 11: Laboratory and Physician Review

**Files:**
- Create: `backend/app/nutrition/physician_router.py`
- Create: `backend/app/nutrition/laboratory_storage.py`
- Create: `backend/alembic/versions/20260809_47_add_physician_nutrition_workflow.py`
- Create: `frontend/src/features/nutrition/LaboratoryPage.tsx`
- Create: `frontend/src/features/physician/PhysicianNutritionPanel.tsx`
- Modify: specialist roles, nutrition review service/models/schemas/router, app routing, API/types/i18n/styles.
- Test: physician authorization, upload ownership/type/size, state matrix, concurrency, same-session edit, activation dates, supersession, notes, audit, and frontend visibility/badges.

**Interfaces:**
- Produces: explicit physician role authorization, private lab records/requests, review queues, state transitions, structured edits, exact-revision approval, effective-date activation, notifications, notes, and audit events.

- [ ] Write failing tests for every state transition and access boundary before production code.
- [ ] Implement storage under a private root with authenticated streaming, immutable revisions, expected-revision checks, and atomic activation.
- [ ] Implement user laboratory UI and RTL physician workspace.
- [ ] Run migration and all affected backend/frontend checks.
- [ ] Commit as `feat(nutrition): add task 11 physician review workflow` and push.

### Task 12: Physician Supplements

**Files:**
- Create: `backend/alembic/versions/20260809_48_add_physician_supplements.py`
- Create: `frontend/src/features/physician/PhysicianSupplements.tsx`
- Create: `frontend/src/features/nutrition/UserSupplements.tsx`
- Modify: supplement service/models/enums/schemas/physician/admin routers, API/types/i18n/styles.
- Test: supplement domain/API/admin/physician/user frontend tests.

**Interfaces:**
- Produces: verified catalogue, physician-owned orders, lifecycle/audit, lab/gap links, deterministic hard safety checks, separate food/supplement/combined exposure, and user-visible history.

- [ ] Write failing tests for physician-only authority, lifecycle, immutable audit, upper-limit hard blocks, allergen/condition/medication warnings, links, contribution separation, and user read-only dose/frequency.
- [ ] Implement the smallest normalized catalogue/order/check/audit model satisfying those contracts.
- [ ] Run migration and all affected checks.
- [ ] Commit as `feat(nutrition): add task 12 physician supplement workflow` and push.

### Task 13: Coordinated Nutrition Frontend

**Files:**
- Create: `frontend/src/features/nutrition/NutritionDashboardPage.tsx`
- Create: focused shopping/edit/review/lab/supplement components under `frontend/src/features/nutrition/`.
- Modify: `frontend/src/App.tsx`, dashboard, AppShell, nutrition API/types/styles, profile completion mapping, and both locale files.
- Test: coordinated Nutrition route/component tests, RTL/i18n/accessibility states.

**Interfaces:**
- Produces: one capability-aware Nutrition experience that exposes all Tasks 3-12 functionality without hiding pending drafts or falsely showing approval.

- [ ] Write failing route/component tests for pending/approved/review/lab/error/empty/loading states and every required action surface.
- [ ] Implement coordinated responsive UI using existing visual tokens and authenticated routing.
- [ ] Run all frontend tests/lint/build plus backend regression, migrations, and diff review.
- [ ] Commit as `feat(nutrition): complete task 13 coordinated frontend` and push.

## Self-Review

- Spec coverage: catalogue separation and all explicit Task 7-13 deliverables map to a section above.
- No placeholders: every stage names concrete contracts, files, checks, and a commit.
- Type consistency: immutable `plan_revision_id` is the shared concurrency/baseline key; catalogue `food_id` is shared by composition, pricing, plans, tracking, and photo mapping; physician orders remain independent from dietary adequacy.
