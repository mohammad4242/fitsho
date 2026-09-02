# Food Price Final Reference Floor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Floor every final food-price candidate and derived reference price to the lower whole thousand toman without changing source evidence or pricing policy calculations.

**Architecture:** Keep exact `Decimal` values through observation normalization, trusted-evidence selection, median/outlier processing, source-spread checks, and price-jump checks. Apply one shared finalization helper only at the single-food candidate boundary and after the weekly update decision, then reuse that finalized value for override, reference, history, and review-candidate persistence.

**Tech Stack:** Python 3.12, Decimal, FastAPI, SQLAlchemy, PostgreSQL, pytest, Ruff.

**Spec:** `docs/superpowers/specs/2026-09-02-food-price-thousand-floor-design.md`

## Global Constraints

- Use `Decimal` only for flooring; do not use float conversion.
- Implement `floor(value / 1000) * 1000` with `ROUND_FLOOR` or an equivalent safe Decimal operation.
- Do not call the helper from `calculate_reference_price()` or `decide_reference_price()`.
- Keep `normal_price`, `promotional_price`, normalized quote evidence, source evidence, and policy inputs unchanged.
- Do not change median, outlier, median-band, source-disagreement, or price-jump logic.
- Use the same finalized candidate for the single-food response and optional override.
- Use the same finalized decision value for `NutritionFoodPriceReference`, `NutritionFoodPriceHistory`, and `NutritionFoodPriceReview.candidate_reference_price_toman`.
- Do not modify the frontend or add a database migration.
- Preserve unrelated WIP and stage only the files named by the current task.

## File Map

- `backend/app/nutrition/pricing.py`: owns the deterministic Decimal floor helper; existing decision functions stay unchanged.
- `backend/app/nutrition/router.py`: finalizes the trusted-evidence average returned by the admin single-food research endpoint.
- `backend/app/nutrition/price_update_service.py`: finalizes `decision.reference_price` immediately before derived persistence.
- `backend/tests/nutrition/test_food_pricing.py`: covers the helper, exact decision outputs, weekly persistence, quote preservation, and review candidates.
- `backend/tests/nutrition/test_single_food_price_research.py`: covers the non-integer trusted average and response/override consistency.

---

### Task 1: Add the Decimal thousand-toman floor helper

**Files:**
- Modify: `backend/app/nutrition/pricing.py`
- Test: `backend/tests/nutrition/test_food_pricing.py`

**Interfaces:**
- Produces `floor_price_to_thousand_toman(value: Decimal) -> Decimal`.
- Does not change the signatures or return values of `calculate_reference_price()` or `decide_reference_price()`.

- [ ] **Step 1: Write the failing helper test**

Add this test after the existing normalization tests in `backend/tests/nutrition/test_food_pricing.py`:

```python
@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (Decimal("235566"), Decimal("235000")),
        (Decimal("432345"), Decimal("432000")),
        (Decimal("432999"), Decimal("432000")),
        (Decimal("432000"), Decimal("432000")),
    ],
)
def test_floor_price_to_thousand_toman(value: Decimal, expected: Decimal) -> None:
    from app.nutrition.pricing import floor_price_to_thousand_toman

    assert floor_price_to_thousand_toman(value) == expected
```

- [ ] **Step 2: Run the helper test and verify the expected failure**

Run from `backend/`:

```bash
uv run pytest tests/nutrition/test_food_pricing.py::test_floor_price_to_thousand_toman -q
```

Expected result: collection fails because `floor_price_to_thousand_toman` does not yet exist.

- [ ] **Step 3: Implement the minimal helper**

Import `ROUND_FLOOR` beside `Decimal` and add this function in `backend/app/nutrition/pricing.py`:

```python
def floor_price_to_thousand_toman(value: Decimal) -> Decimal:
    return (value / Decimal("1000")).to_integral_value(rounding=ROUND_FLOOR) * Decimal("1000")
```

Do not add rounding, validation, or policy behavior to the function.

- [ ] **Step 4: Run helper and exact decision tests**

Run from `backend/`:

```bash
uv run pytest \
  tests/nutrition/test_food_pricing.py::test_floor_price_to_thousand_toman \
  tests/nutrition/test_food_pricing.py::test_reference_price_uses_mean_after_robust_outlier_rejection \
  tests/nutrition/test_food_pricing.py::test_reference_requires_three_distinct_sources \
  tests/nutrition/test_food_pricing.py::test_large_change_requires_review_and_preserves_previous_price \
  -q
```

Expected result: all tests pass, including the unchanged exact decision values.

- [ ] **Step 5: Commit and push the helper**

```bash
git add backend/app/nutrition/pricing.py backend/tests/nutrition/test_food_pricing.py
git commit -m "feat(nutrition): add Decimal thousand-toman floor helper"
git push origin main
```

### Task 2: Floor the single-food research candidate

**Files:**
- Modify: `backend/app/nutrition/router.py`
- Test: `backend/tests/nutrition/test_single_food_price_research.py`

**Interfaces:**
- Consumes the exact trusted average already selected by `median_band_indices()`.
- Produces one floored `candidate_price` reused by the response and `create_price_override()`.

- [ ] **Step 1: Make the endpoint regression test assert the required non-integer result**

In `test_research_single_food_success_and_apply`, replace the three test prices with `235000`, `236000`, and `236000`; update the first quote assertion to `"235000"`; and add these assertions after the candidate non-null assertion and after the applied response status assertion:

```python
assert data["candidate_reference_price_toman"] == "235000"
assert applied_data["candidate_reference_price_toman"] == "235000"
```

The trusted average is `235666.666...`, so the current nearest-integer implementation must fail the new candidate assertion with `"235667"`.

- [ ] **Step 2: Run the endpoint regression test and verify the expected failure**

Run from `backend/`:

```bash
uv run pytest tests/nutrition/test_single_food_price_research.py::test_research_single_food_success_and_apply -q
```

Expected result: the test fails on the candidate value because the endpoint still uses `round()`.

- [ ] **Step 3: Replace endpoint rounding with the shared helper**

Import `floor_price_to_thousand_toman` from `app.nutrition.pricing`. Replace the existing nested `Decimal(int(round(...)))` expression with:

```python
average_price = sum(
    (e.normalized_normal_price_toman for e in trusted), Decimal()
) / Decimal(len(trusted))
candidate_price = floor_price_to_thousand_toman(average_price)
```

Leave quote serialization and `median_band_indices()` unchanged. Keep `candidate_price` as the value sent to both `FoodPriceOverrideInput` and `SingleFoodPriceResearchResponse`.

- [ ] **Step 4: Run the endpoint regression test and its focused file**

Run from `backend/`:

```bash
uv run pytest \
  tests/nutrition/test_single_food_price_research.py::test_research_single_food_success_and_apply \
  tests/nutrition/test_single_food_price_research.py \
  -q
```

Expected result: the focused endpoint and all single-food research tests pass.

- [ ] **Step 5: Commit and push the endpoint change**

```bash
git add backend/app/nutrition/router.py backend/tests/nutrition/test_single_food_price_research.py
git commit -m "fix(nutrition): floor single-food price research candidates"
git push origin main
```

### Task 3: Floor weekly reference, history, and review candidates after decision

**Files:**
- Modify: `backend/app/nutrition/price_update_service.py`
- Test: `backend/tests/nutrition/test_food_pricing.py`

**Interfaces:**
- Consumes the unchanged `ReferencePriceDecision` returned by `decide_reference_price()`.
- Produces `final_reference_price: Decimal | None` only after the decision and before any derived reference/history/review persistence.
- Leaves quote columns, raw evidence, and accepted/rejected quote IDs unchanged.

- [ ] **Step 1: Add failing persistence and review-candidate assertions**

In `test_agent_coherent_three_sources_persist_distinct_providers_and_accept_reference`, change only the derived persistence expectation and add these assertions:

```python
assert reference.reference_price_toman == Decimal("197000")
assert history is not None
assert history.reference_price_toman == Decimal("197000")
assert reference.reference_price_toman % Decimal("1000") == 0
assert history.reference_price_toman % Decimal("1000") == 0
assert sorted(item.normal_price_irr for item in quotes) == [
    Decimal("1900000"),
    Decimal("1980000"),
    Decimal("2050000"),
]
```

The source values remain exact and their mean is `197666.666...`; the current service must fail the new `197000` assertions.

In `test_agent_five_disagreeing_sources_create_review_and_preserve_previous_reference`, set the previous reference to `Decimal("180500")`, keep the previous reference assertion at `Decimal("180500")`, and add:

```python
assert review.candidate_reference_price_toman == Decimal("180000")
```

This proves a review candidate is finalized while the previous stored reference remains preserved.

- [ ] **Step 2: Run the persistence and review tests and verify the expected failures**

Run from `backend/`:

```bash
uv run pytest \
  tests/nutrition/test_food_pricing.py::test_agent_coherent_three_sources_persist_distinct_providers_and_accept_reference \
  tests/nutrition/test_food_pricing.py::test_agent_five_disagreeing_sources_create_review_and_preserve_previous_reference \
  -q
```

Expected result: the tests fail because the service persists `decision.reference_price` without final flooring.

- [ ] **Step 3: Add finalization after the decision and use one value for derived persistence**

Import `floor_price_to_thousand_toman` from `app.nutrition.pricing`. Immediately after the `decision` expression, add:

```python
final_reference_price: Decimal | None = None
if decision is not None and decision.reference_price is not None:
    final_reference_price = floor_price_to_thousand_toman(decision.reference_price)
```

Change the accepted branch condition to require `final_reference_price is not None`, then use `final_reference_price` for:

```python
reference_price_toman=final_reference_price
```

in both `NutritionFoodPriceReference` and `NutritionFoodPriceHistory`, and for:

```python
candidate_reference_price_toman=final_reference_price
```

in `NutritionFoodPriceReview`. Do not replace `decision.reference_price` in the call to `decide_reference_price()` or in any validation logic.

- [ ] **Step 4: Run weekly persistence, review, quote-preservation, and all nutrition pricing tests**

Run from `backend/`:

```bash
uv run pytest \
  tests/nutrition/test_food_pricing.py::test_agent_coherent_three_sources_persist_distinct_providers_and_accept_reference \
  tests/nutrition/test_food_pricing.py::test_agent_five_disagreeing_sources_create_review_and_preserve_previous_reference \
  tests/nutrition/test_food_pricing.py::test_agent_promotional_price_is_persisted_but_normal_price_drives_reference \
  tests/nutrition/test_food_pricing.py \
  tests/nutrition/test_single_food_price_research.py \
  -q
```

Expected result: all listed tests pass; exact decision tests remain unchanged and quote evidence remains source-derived.

- [ ] **Step 5: Commit and push the weekly persistence change**

```bash
git add backend/app/nutrition/price_update_service.py backend/tests/nutrition/test_food_pricing.py
git commit -m "fix(nutrition): floor persisted food price references"
git push origin main
```

### Task 4: Run final scoped verification and inspect the boundary

**Files:**
- Verify: `backend/app/nutrition/pricing.py`
- Verify: `backend/app/nutrition/router.py`
- Verify: `backend/app/nutrition/price_update_service.py`
- Verify: `backend/tests/nutrition/test_food_pricing.py`
- Verify: `backend/tests/nutrition/test_single_food_price_research.py`

- [ ] **Step 1: Run the complete related test files**

Run from `backend/`:

```bash
uv run pytest tests/nutrition/test_food_pricing.py tests/nutrition/test_single_food_price_research.py -q
```

Expected result: exit code 0 with zero failed tests.

- [ ] **Step 2: Run related Ruff checks**

Run from `backend/`:

```bash
uv run ruff check \
  app/nutrition/pricing.py \
  app/nutrition/router.py \
  app/nutrition/price_update_service.py \
  tests/nutrition/test_food_pricing.py \
  tests/nutrition/test_single_food_price_research.py
```

Expected result: exit code 0 with no lint errors.

- [ ] **Step 3: Verify the final diff and invariants**

Run from the repository root:

```bash
git diff HEAD~3..HEAD --stat
git diff HEAD~3..HEAD -- backend/app/nutrition/pricing.py backend/app/nutrition/router.py backend/app/nutrition/price_update_service.py
rg -n "round\(|decision\.reference_price|floor_price_to_thousand_toman|reference_price_toman=|candidate_reference_price_toman=" backend/app/nutrition/pricing.py backend/app/nutrition/router.py backend/app/nutrition/price_update_service.py
git status --short --branch
```

Confirm from the diff that the decision functions and validation expressions are unchanged, `round()` is gone from the single-food candidate path, only final derived values use the helper, and no frontend or migration file changed.

- [ ] **Step 4: Commit only if a final verification-only adjustment is required**

No additional commit is expected when the three implementation commits are clean. If a directly related formatting or test correction is required, stage only the named task files and use a specific Conventional Commit message describing that correction before pushing `main`.
