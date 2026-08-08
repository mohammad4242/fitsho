# Nutrition Food Catalogue Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the verified food catalogue and structured meal-composition foundation required by Task 4.

**Architecture:** A canonical food record owns verified composition rows and provenance. Meals reference foods through exact gram-based quantities and calculate totals deterministically; no pricing, planning, or live provider is included.

**Tech Stack:** FastAPI, SQLAlchemy, Alembic, PostgreSQL, Pydantic, pytest.

## Global Constraints

- Preserve unrelated worktree changes and stage only Task 4 files.
- A missing nutrient is stored as unavailable, never zero.
- Canonical quantity is grams; only verified unit conversions may be imported.
- USDA FoodData Central is composition provenance, not a source of human requirement targets.
- Do not implement Task 5 prices or meal-plan optimisation.

---

### Task 1: Catalogue schema, seed, and importer

**Files:**
- Create: `backend/alembic/versions/20260808_40_add_food_catalogue.py`
- Create: `backend/app/nutrition/food_catalogue.py`
- Create: `backend/tests/nutrition/test_food_catalogue.py`
- Modify: `backend/app/nutrition/models.py`
- Modify: `backend/app/nutrition/enums.py`

- [ ] **Step 1: Write failing tests**

```python
def test_import_rejects_unknown_unit_and_keeps_missing_nutrients_unavailable():
    with pytest.raises(FoodImportValidationError):
        import_food_rows([{"quantity_unit": "cup"}])
```

- [ ] **Step 2: Run the focused test and confirm failure**

Run: `uv run pytest tests/nutrition/test_food_catalogue.py -q`

- [ ] **Step 3: Implement models and validation**

```python
def grams_for(quantity: Decimal, unit: FoodQuantityUnit) -> Decimal:
    return quantity if unit is FoodQuantityUnit.GRAM else quantity * conversion_factor(unit)
```

- [ ] **Step 4: Add idempotent verified Iranian seed foods and a provenance-preserving USDA mapping import path**

- [ ] **Step 5: Run focused tests and migration**

- [ ] **Step 6: Commit after Task 4 is complete**

### Task 2: Structured meals, API, and admin CRUD

**Files:**
- Create: `backend/app/nutrition/food_catalogue_service.py`
- Create: `backend/tests/nutrition/test_food_catalogue_api.py`
- Modify: `backend/app/nutrition/router.py`
- Modify: `backend/app/nutrition/schemas.py`
- Modify: `backend/app/admin/router.py`

- [ ] **Step 1: Write failing API tests**

```python
def test_main_meal_requires_a_main_eligible_food(client: TestClient):
    response = client.post("/api/v1/nutrition/meals", json={"slot_role": "main_meal", "items": []})
    assert response.status_code == 422
```

- [ ] **Step 2: Run the focused test and confirm failure**

- [ ] **Step 3: Implement deterministic role validation and meal totals**

```python
total = sum(item.grams * composition.value_per_100g / Decimal("100") for item in items)
```

- [ ] **Step 4: Add member read APIs and admin food CRUD APIs**

- [ ] **Step 5: Run focused tests**

### Task 3: Documentation, verification, and delivery

**Files:**
- Modify: `docs/nutrition-implementation-design.md`

- [ ] **Step 1: Document provenance, missing-data, taxonomy, and Task 5 boundary**
- [ ] **Step 2: Run `ruff check`, `mypy`, backend tests, frontend checks if contracts change, and a fresh migration**
- [ ] **Step 3: Commit and push the focused Task 4 change**

## Execution Handoff

Inline execution is selected: implement in this session, run every validation, commit, push, report, and stop after Task 4.
