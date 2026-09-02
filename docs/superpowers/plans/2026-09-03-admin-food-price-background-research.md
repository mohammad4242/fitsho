# Admin Food Price Background Research Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Allow an admin to start food-price research from the catalogue without opening a dialog, while showing per-card progress, the applied price, or the returned failure reason.

**Architecture:** Keep the existing synchronous research endpoint and call it from the catalogue page with `apply=true`. `FoodCataloguePage` owns a slug-keyed research-state map, `FoodCard`/`PriceTicket` render that state, and a successful response updates only the matching admin card locally; the manual price-edit dialog remains unchanged.

**Tech Stack:** React 19, TypeScript, Vitest, Testing Library, existing FastAPI nutrition price-research endpoint.

**Spec:** `docs/superpowers/specs/2026-09-03-admin-food-price-background-research-design.md`

## Global Constraints

- Do not add a Backend queue, worker, polling loop, or endpoint.
- Call `researchFoodPrice(slug, true)` so the existing Backend applies and persists only its validated candidate price.
- Do not open `PriceOverrideDialog` from the «استعلام قیمت» action.
- Keep the «ویرایش قیمت» manual workflow unchanged.
- Show independent state per food slug; a failed inquiry must preserve any previously displayed price.
- Do not invent or calculate a price in the UI; use `candidate_reference_price_toman` from the Backend response.
- Preserve unrelated dirty and untracked files; stage only the listed files.

### Task 1: Add failing catalogue interaction tests

**Files:**
- Modify: `frontend/src/features/nutrition/FoodCataloguePage.test.tsx:375-444`

**Interfaces:**
- Consumes: existing `api.researchFoodPrice` mock and admin catalogue fixture.
- Produces: regression coverage for the pending, success, no-price, and HTTP-error UI states.

- [ ] **Step 1: Replace the old dialog-and-manual-save test with the desired pending behavior**

  Keep the existing successful response fixture but make the research promise externally resolvable. After clicking `استعلام قیمت سینه مرغ`, assert all of the following before resolving it:

  ```tsx
  expect(api.researchFoodPrice).toHaveBeenCalledWith("chicken-breast", true);
  expect(screen.getByText("در حال استعلام…")).toBeVisible();
  expect(screen.getByRole("button", { name: "در حال استعلام قیمت سینه مرغ" })).toBeDisabled();
  expect(screen.queryByRole("dialog", { name: "ویرایش قیمت سینه مرغ" })).not.toBeInTheDocument();
  ```

  Resolve the promise and wait for the pending text to disappear.

- [ ] **Step 2: Add the successful automatic-apply assertions**

  In the success test, assert the returned price appears on the catalogue card as `۳۸۵٬۰۰۰ تومان`, `api.saveFoodPriceOverride` is never called, and the initial admin catalogue request remains the only catalogue load. This proves the response updates the card without reopening the old editor or forcing a page reload.

- [ ] **Step 3: Add failure assertions**

  Add one test for a `failed` response with `message: "Agent Service در دسترس نیست"` and one for a rejected request with `new Error("اتصال به سرویس برقرار نشد")`. For each, assert the reason is visible with `role="alert"`, the prior `یافت نشد` state remains visible, and the inquiry button becomes enabled again.

- [ ] **Step 4: Run the focused test and verify RED**

  Run:

  ```bash
  cd frontend && npm run test -- --run src/features/nutrition/FoodCataloguePage.test.tsx
  ```

  Expected: FAIL because the current click still opens `PriceOverrideDialog`, calls `researchFoodPrice` without `true`, and has no card-level pending/error state.

### Task 2: Implement per-card background research

**Files:**
- Modify: `frontend/src/features/nutrition/FoodCataloguePage.tsx:1-163,220-269`
- Modify: `frontend/src/features/nutrition/foodCatalogue.css:356-405`

**Interfaces:**
- Consumes: `api.researchFoodPrice(slug, true)` and `SingleFoodPriceResearchResponse`.
- Produces: `PriceResearchState`, a page-level `researchPrice(food)` handler, and card rendering that keeps the catalogue visible.

- [ ] **Step 1: Add the minimal slug-keyed state and handler**

  Define:

  ```tsx
  type PriceResearchState =
    | { status: "researching" }
    | { status: "error"; message: string };
  ```

  Store `Record<string, PriceResearchState>` in `FoodCataloguePage`. The handler must ignore a second click while the same slug is `researching`, set that slug to `researching`, and call:

  ```tsx
  void api.researchFoodPrice(food.slug, true)
  ```

- [ ] **Step 2: Handle valid success and preserve the existing data shape**

  For a response with `status === "success"`, a non-empty `candidate_reference_price_toman`, and a supported `canonical_unit`, update only the matching admin item in `data` with:

  ```tsx
  price: {
    status: "accepted",
    reference_price_toman: result.candidate_reference_price_toman,
    canonical_unit: result.canonical_unit,
    reference_unit: mappedIrrReferenceUnit,
    source: "manual_override",
  }
  ```

  Clear the slug state after this local update. If the response lacks a usable candidate or unit, store an error state instead of displaying a fabricated price.

- [ ] **Step 3: Handle returned and thrown failures**

  Use `result.message` for `failed`/`no_quotes`, with a Persian/English fallback when it is empty. For a rejected promise, use the non-empty `Error.message` and otherwise use the same localized connection fallback. Store the message only under the failed slug; do not change its existing price.

- [ ] **Step 4: Render state on the card and remove auto-research dialog wiring**

  Pass the slug state into `FoodCard` and `PriceTicket`. While researching, render `در حال استعلام…`/`Price inquiry in progress…`, keep the page and card visible, and disable only that card's button. On error, render the message in a small `role="alert"` element and keep retry available. Change the card callback to call the page handler directly and remove `priceFood.autoResearch` usage for this action; retain `PriceOverrideDialog` for the manual `ویرایش قیمت` button.

- [ ] **Step 5: Preserve existing accepted-price compatibility**

  Let `PriceTicket` prefer `reference_price_toman` when present and otherwise retain its current IRR-to-Toman fallback. Add only the focused research/error styles needed for readable status text in the existing ticket layout.

- [ ] **Step 6: Run the focused test and verify GREEN**

  Run:

  ```bash
  cd frontend && npm run test -- --run src/features/nutrition/FoodCataloguePage.test.tsx
  ```

  Expected: PASS, including the existing manual edit, delete, image, member-visibility, and accepted-price tests.

### Task 3: Review, verify, and deliver the frontend change

**Files:**
- Review: `frontend/src/features/nutrition/FoodCataloguePage.tsx`
- Review: `frontend/src/features/nutrition/FoodCataloguePage.test.tsx`
- Review: `frontend/src/features/nutrition/foodCatalogue.css`

**Interfaces:**
- Consumes: the green focused regression suite from Task 2.
- Produces: verified frontend behavior with no unrelated staged files.

- [ ] **Step 1: Run the nutrition frontend tests**

  ```bash
  cd frontend && npm run test -- --run src/features/nutrition
  ```

- [ ] **Step 2: Run frontend lint and production build**

  ```bash
  cd frontend && npm run lint
  cd frontend && npm run build
  ```

- [ ] **Step 3: Inspect the diff and stage only the feature files**

  ```bash
  git diff -- frontend/src/features/nutrition/FoodCataloguePage.tsx frontend/src/features/nutrition/FoodCataloguePage.test.tsx frontend/src/features/nutrition/foodCatalogue.css
  git add -- frontend/src/features/nutrition/FoodCataloguePage.tsx frontend/src/features/nutrition/FoodCataloguePage.test.tsx frontend/src/features/nutrition/foodCatalogue.css
  git diff --cached --check
  ```

- [ ] **Step 4: Commit and push**

  ```bash
  git commit -m "feat(nutrition): run admin food price inquiry in background"
  git push origin main
  ```
