# Food Catalogue Admin Retirement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let admins retire catalogue foods through a confirmed soft-delete flow while preserving every historical database reference.

**Architecture:** Reuse `retire_catalogue_food` and `FoodVerificationStatus.RETIRED`; never delete `NutritionCatalogueFood` or its children. Preserve retired rows during the approved-food seed upsert, rely on existing `VERIFIED` filters for reads/planning/pricing, and add an admin-only frontend confirmation flow using the shared request client.

**Tech Stack:** FastAPI, SQLAlchemy, PostgreSQL, pytest, React 19, TypeScript, Vitest, Testing Library, CSS.

**Spec:** `docs/superpowers/specs/2026-09-02-food-catalogue-retire-design.md`

## Global Constraints

- Use `FoodVerificationStatus.RETIRED` for active-to-retired transitions.
- Never call `db.delete()`, `session.delete()`, or issue SQL DELETE for catalogue foods.
- Preserve aliases, compositions, portions, image paths, price data, meal references, recipes, and historical plans.
- Keep member catalogue responses limited to active `VERIFIED` foods.
- Do not add a migration, restore feature, hard delete, bulk delete, or planner/read-model policy.
- Preserve unrelated working-tree changes and stage only feature files plus the two required design records.

---

### Task 1: Record the approved design and plan

**Files:**
- Create: `docs/superpowers/specs/2026-09-02-food-catalogue-retire-design.md`
- Create: `docs/superpowers/plans/2026-09-02-food-catalogue-retire.md`

**Interfaces:**
- Produces the agreed domain, seed, API, UI, and verification boundaries for the implementation tasks.

- [x] **Step 1: Write and self-review the design record**

The design record states that the existing admin delete route is verified and the implementation changes only domain idempotency, seed preservation, frontend API/UI, styles, and regression tests.

- [ ] **Step 2: Commit the records**

Use commit message `docs(nutrition): define admin food retirement flow`, then push the current branch.

### Task 2: Add failing backend retirement and seed regressions

**Files:**
- Modify: `backend/tests/nutrition/test_food_catalogue.py`
- Modify: `backend/tests/nutrition/test_member_food_catalogue_api.py`

**Interfaces:**
- Consumes: existing `retire_catalogue_food`, `seed_base_iranian_food_catalogue`, admin route, and catalogue read routes.
- Produces: regression coverage for `RETIRED`, preserved child/history rows, route security, active-list filtering, and seed non-resurrection.

- [ ] **Step 1: Add the seed non-resurrection test**

Query `chicken-breast`, set its status to `FoodVerificationStatus.RETIRED`, commit, run `seed_base_iranian_food_catalogue(db)`, then assert the same row remains retired and its relation counts are unchanged.

- [ ] **Step 2: Add API soft-retirement and preservation tests**

Register an admin with `ProductMode.NUTRITION`, record aliases/compositions/portions, create or use existing price history/reference data, call `DELETE /api/v1/nutrition/admin/foods/chicken-breast` with `ORIGIN`, and assert 204, row existence, retired status, preserved children/history, missing active admin/member catalogue entries, and absent planner verified candidates. Also cover a second delete (204), member 403, missing/invalid origin 403, and unknown slug 404.

- [ ] **Step 3: Run the new tests before production edits**

Run from `backend/`: `uv run pytest tests/nutrition/test_food_catalogue.py tests/nutrition/test_member_food_catalogue_api.py -q`. The seed non-resurrection test must fail because the current seed overwrites `RETIRED`.

### Task 3: Implement backend retirement and seed preservation

**Files:**
- Modify: `backend/app/nutrition/food_catalogue.py`
- Verify: `backend/app/nutrition/router.py`, `backend/app/nutrition/catalogue_view.py`

**Interfaces:**
- Consumes: `NutritionCatalogueFood`, `FoodVerificationStatus`, and existing admin route.
- Produces: an idempotent `retire_catalogue_food(db, slug)` and a seed that never resurrects a retired row.

- [ ] **Step 1: Make retirement explicit and idempotent**

Keep the existing slug lookup and missing-food `ValueError`; assign `RETIRED` only when the current status is different, then commit. Do not load or mutate child relations and do not call deletion APIs.

- [ ] **Step 2: Preserve retired rows in the seed**

Capture whether an existing row is retired before relation replacement. For retired rows, preserve the status and skip clearing/reassigning roles, aliases, compositions, and portions. For new/active rows, keep the current scalar and relation upsert logic and computed verified/draft status.

- [ ] **Step 3: Run backend red-green checks**

Run the focused pytest command and Ruff command requested by the user. Confirm all focused tests pass and Ruff reports no errors.

- [ ] **Step 4: Commit the backend change**

Use commit message `feat(nutrition): retire catalogue foods without deleting history`, then push the current branch.

### Task 4: Add failing frontend API and confirmation-flow tests

**Files:**
- Modify: `frontend/src/features/nutrition/api.test.ts`
- Modify: `frontend/src/features/nutrition/FoodCataloguePage.test.tsx`

**Interfaces:**
- Consumes: existing `FoodCataloguePage`, shared `request`, and mocked nutrition API module.
- Produces: tests for `deleteCatalogueFood(slug): Promise<void>` and the admin-only confirmed delete UX.

- [ ] **Step 1: Add the API request test**

Mock a 204 response, call `deleteCatalogueFood("chicken-breast")`, and assert the exact path, `method: "DELETE"`, and `credentials: "include"`.

- [ ] **Step 2: Add component behavior tests**

Cover member absence, admin button, confirmation name/copy, cancel without API call, success call plus catalogue refetch, failure with dialog and card retained, and disabled pending submit.

- [ ] **Step 3: Run the frontend tests before implementation edits**

Run from `frontend/`: `npm test -- --run src/features/nutrition/FoodCataloguePage.test.tsx src/features/nutrition/api.test.ts`. The new API import and UI behavior tests must fail because the function and UI do not yet exist.

### Task 5: Implement frontend API, dialog, pagination, and styles

**Files:**
- Modify: `frontend/src/features/nutrition/api.ts`
- Modify: `frontend/src/features/nutrition/FoodCataloguePage.tsx`
- Modify: `frontend/src/features/nutrition/foodCatalogue.css`

**Interfaces:**
- Consumes: `request`, `AdminFoodCatalogueItem`, existing `DialogFrame`, and current page/reload state.
- Produces: `deleteCatalogueFood`, admin-only `حذف`/`Delete` buttons, `DeleteFoodDialog`, and explicit destructive selectors.

- [ ] **Step 1: Add the shared API function**

```ts
export function deleteCatalogueFood(slug: string): Promise<void> {
  return request(`${nutritionPath}/admin/foods/${slug}`, { method: "DELETE" });
}
```

- [ ] **Step 2: Wire the admin card action**

Add `deleteFood` state, pass `onDelete` only through `isAdminFood(food)`, and render the new button with Persian/English text and food-specific `aria-label`.

- [ ] **Step 3: Implement the confirmation dialog**

Use local `deleting` and `error` state. Submit once, disable the destructive button while pending, show `در حال حذف…`/`Deleting…`, keep the dialog open on rejection with the requested error copy, and call a success callback that closes and reloads.

- [ ] **Step 4: Handle the last item on a page**

After a successful delete, if `page > 1` and the current response contains exactly one item, decrement page; otherwise increment `reload`. Do not use a browser reload.

- [ ] **Step 5: Add explicit destructive styles**

Create `.food-card-delete` and a dialog destructive action class with restrained red text/border/background. Replace the existing price `:last-child` selector with a price-specific class so button order cannot change its appearance.

- [ ] **Step 6: Run frontend checks**

Run the focused Vitest suite, `npm run lint`, and `npm run build` from `frontend/`.

- [ ] **Step 7: Commit the frontend change**

Use commit message `feat(nutrition): add confirmed admin food retirement`, then push the current branch.

### Task 6: Complete verification and handoff

**Files:**
- Verify only: all changed files and existing planner/price filters.

**Interfaces:**
- Consumes: committed backend/frontend implementation and test fixtures.
- Produces: command-backed evidence for every requested acceptance criterion.

- [ ] **Step 1: Run the focused and nutrition backend suites**

Run the two requested focused files and then `uv run pytest tests/nutrition` from `backend/`.

- [ ] **Step 2: Run frontend focused tests, lint, and build**

Run the requested focused Vitest command, `npm run lint`, and `npm run build` from `frontend/`.

- [ ] **Step 3: Inspect final scope**

Run `git diff --check`, inspect `git status --short --branch`, and confirm no unrelated file is staged, no migration was added, and no delete operation exists for `NutritionCatalogueFood`.

- [ ] **Step 4: Report exact results**

Report changed files, endpoint, soft-delete status, backend authorization/origin/404/preservation results, seed regression, frontend dialog/API results, pytest/Vitest/Ruff/lint/build results, and any live runtime checks that were not available.
