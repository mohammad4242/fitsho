# Food Catalogue Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a nutrition-mode member catalogue showing verified nutrients and this week's accepted price, with audited admin-only food creation and temporary price overrides.

**Architecture:** Add an authenticated catalogue read model that joins existing catalogue composition with an effective-price resolver. Store manual overrides in a separate audited table, prefer them in the resolver and planner, and expire them on the next successful marketplace refresh without changing immutable quotes or history. Add one shared React page whose mutation controls render only for admins.

**Tech Stack:** FastAPI, SQLAlchemy 2, Alembic, PostgreSQL, Pydantic, React 19, TypeScript, React Router, i18next, Vitest.

## Global Constraints

- Route is `/food-catalogue` and is available only to authenticated `nutrition` and `both` modes.
- Training-only access is rejected by the API as well as hidden in the UI.
- Nutrition composition and price persistence remain separate.
- Missing or non-accepted current price renders `یافت نشد` / `Not found`; no estimate is fabricated.
- Manual pricing is audited fallback-only and expires at the next successful marketplace refresh.
- Existing nutrition, tracking, planning, and monitoring contracts remain backward compatible.
- Do not modify unrelated onboarding/profile work already present in the worktree.

---

### Task 1: Audited manual price override domain

**Files:**
- Create: `backend/alembic/versions/20260809_55_add_food_price_overrides.py`
- Modify: `backend/app/nutrition/models.py`
- Modify: `backend/app/nutrition/price_update_service.py`
- Test: `backend/tests/nutrition/test_food_price_overrides.py`

**Interfaces:**
- Produces: `NutritionFoodPriceOverride` with `food_id`, `reference_price_toman`, `canonical_unit`, `reason`, `created_by_user_id`, `created_at`, `active`, `expired_at`, and `expired_by_run_id`.
- Produces: `EffectivePrice` and `effective_prices(db, food_ids, now)` returning active overrides before accepted automatic references.
- Consumes: successful `NutritionFoodPriceUpdateRun` completion to expire active overrides.

- [ ] **Step 1: Write failing persistence and resolver tests**

```python
def test_active_override_precedes_accepted_automatic_reference(db):
    effective = effective_prices(db, [food.id], datetime.now(UTC))[food.id]
    assert effective.source == "manual_override"
    assert effective.reference_price_toman == Decimal("450000")

def test_successful_market_refresh_expires_active_override(db):
    run_price_update(db, providers=three_valid_providers)
    db.refresh(override)
    assert override.active is False
    assert override.expired_by_run_id is not None
```

- [ ] **Step 2: Run tests and confirm missing model/resolver failures**

Run: `uv run pytest tests/nutrition/test_food_price_overrides.py -q`

- [ ] **Step 3: Add migration, model, resolver, and transactional expiry**

Use a partial unique index for one active override per food and check constraints for positive prices and supported units `TOMAN_PER_KG`, `TOMAN_PER_LITER`, and `TOMAN_PER_UNIT`. Expire overrides only after a non-skipped refresh finishes without provider failure; preserve override rows permanently.

- [ ] **Step 4: Run focused checks**

Run: `uv run alembic upgrade head && uv run pytest tests/nutrition/test_food_price_overrides.py tests/nutrition/test_food_pricing.py -q && uv run ruff check app/nutrition tests/nutrition/test_food_price_overrides.py && uv run mypy app/nutrition`

- [ ] **Step 5: Commit**

```bash
git commit -m "feat(nutrition): add audited temporary price overrides"
```

### Task 2: Member catalogue and admin mutation API

**Files:**
- Create: `backend/app/nutrition/catalogue_view.py`
- Modify: `backend/app/nutrition/schemas.py`
- Modify: `backend/app/nutrition/router.py`
- Modify: `backend/app/nutrition/food_catalogue.py`
- Modify: `backend/app/nutrition/plan_service.py`
- Test: `backend/tests/nutrition/test_member_food_catalogue_api.py`
- Test: `backend/tests/nutrition/test_food_catalogue_api.py`

**Interfaces:**
- Produces: `GET /api/v1/nutrition/food-catalogue?q=&category=&page=&page_size=`.
- Produces: `POST /api/v1/nutrition/admin/foods/{slug}/price-override` with `{reference_price_toman, canonical_unit, reason}`.
- Reuses: `POST /api/v1/nutrition/admin/foods` for validated food create/update.

- [ ] **Step 1: Write failing access and response tests**

```python
def test_training_member_cannot_read_food_catalogue(client):
    response = client.get("/api/v1/nutrition/food-catalogue")
    assert response.status_code == 403

def test_nutrition_member_sees_macros_and_missing_price(client):
    item = client.get("/api/v1/nutrition/food-catalogue").json()["items"][0]
    assert set(item["macros"]) == {"energy_kcal", "protein_g", "carbohydrate_g", "total_fat_g", "fiber_g"}
    assert item["price"]["status"] in {"accepted", "not_found"}
```

- [ ] **Step 2: Run API tests and confirm route failures**

Run: `uv run pytest tests/nutrition/test_member_food_catalogue_api.py -q`

- [ ] **Step 3: Implement eligibility dependency and paginated read model**

Query verified foods with aliases/compositions, apply normalized bilingual search and category filtering, resolve effective prices in one batch, and return macro plus full-nutrient source details without provider raw payloads.

- [ ] **Step 4: Implement admin price override endpoint and strengthen food validation**

Require `AdminUser` and `require_trusted_origin`; reject blank reasons, unsupported units, non-positive prices, incomplete required macros, or unverified source metadata. Record the acting user ID in the override row.

- [ ] **Step 5: Route planner prices through `effective_prices`**

Replace direct current-reference selection in `_planner_foods` while preserving price snapshots and adding `source: automatic | manual_override` to new snapshots only.

- [ ] **Step 6: Run focused checks**

Run: `uv run pytest tests/nutrition/test_member_food_catalogue_api.py tests/nutrition/test_food_catalogue_api.py tests/nutrition/test_weekly_plan_api.py -q && uv run ruff check app/nutrition tests/nutrition && uv run mypy app/nutrition`

- [ ] **Step 7: Commit**

```bash
git commit -m "feat(nutrition): expose mode-protected food catalogue API"
```

### Task 3: Shared member catalogue page and admin controls

**Files:**
- Create: `frontend/src/features/nutrition/FoodCataloguePage.tsx`
- Create: `frontend/src/features/nutrition/FoodCataloguePage.test.tsx`
- Create: `frontend/src/features/nutrition/foodCatalogue.css`
- Modify: `frontend/src/features/nutrition/api.ts`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/shared/AppShell.tsx`
- Modify: `frontend/src/shared/AuthenticatedHeader.tsx`
- Modify: `frontend/src/i18n/fa.ts`
- Modify: `frontend/src/i18n/en.ts`

**Interfaces:**
- Consumes: catalogue read and admin mutation endpoints from Task 2.
- Produces: nutrition-capability route `/food-catalogue`, card/detail UI, and admin modals.

- [ ] **Step 1: Write failing navigation, page, and permission tests**

```tsx
expect(screen.getByRole("link", { name: "کاتالوگ مواد غذایی" })).toBeVisible();
expect(screen.getByText("یافت نشد")).toBeVisible();
expect(screen.queryByRole("button", { name: "افزودن ماده غذایی" })).not.toBeInTheDocument();
```

Also assert training mode has no catalogue navigation, English copy is English/LTR, details show micronutrients, and admins see both mutation buttons.

- [ ] **Step 2: Run Vitest and confirm component/route failures**

Run: `npm run test -- FoodCataloguePage.test.tsx`

- [ ] **Step 3: Add typed API contracts and nutrition-capability route guard**

Add `FoodCatalogueResponse`, `FoodCatalogueItem`, `FoodPriceView`, query serialization, add-food mutation, and price-override mutation. Route guards redirect training-only members to `/dashboard` while the backend remains authoritative.

- [ ] **Step 4: Build responsive catalogue cards and detail panel**

Render bilingual name, category, price/date/unit, five primary nutrient values per 100 g, server-backed search/category controls, pagination, a back link to `/nutrition-estimate`, and accessible loading/error/empty states.

- [ ] **Step 5: Add admin-only add-food and price modals**

Use labelled fields, client-side validation matching API constraints, explicit success/error feedback, refresh the current page after save, and explain automatic override expiry.

- [ ] **Step 6: Rename navigation and add catalogue icon destination**

Change `header.nutritionTargets` copy to `تغذیه` / `Nutrition`; add the Food Catalogue link only when `hasNutrition` is true in desktop, drawer, and AppShell navigation.

- [ ] **Step 7: Run frontend checks**

Run: `npm run test -- FoodCataloguePage.test.tsx && npm run lint && npm run build`

- [ ] **Step 8: Commit**

```bash
git commit -m "feat(nutrition): add member food catalogue experience"
```

### Task 4: Regression, runtime, and delivery

**Files:**
- Modify: `docs/nutrition-pricing.md`

**Interfaces:**
- Verifies: database migration, API access, planner override behavior, UI permissions, and runtime health.

- [ ] **Step 1: Document catalogue and override operations**

Document member eligibility, missing-price semantics, admin audit fields, override expiration, and the automatic weekly workflow.

- [ ] **Step 2: Run complete verification**

```bash
cd backend
uv run alembic upgrade head
uv run ruff check .
uv run mypy app
uv run pytest -q
cd ../frontend
npm run lint
npm run test -- --run
npm run build
```

- [ ] **Step 3: Start/recreate the existing Compose backend and verify OpenAPI**

Run: `docker compose up -d --no-deps backend && curl -fsS http://localhost:8001/openapi.json`

- [ ] **Step 4: Commit documentation and push the dedicated branch**

```bash
git commit -m "docs(nutrition): document member food catalogue operations"
git push origin nutrition
```
