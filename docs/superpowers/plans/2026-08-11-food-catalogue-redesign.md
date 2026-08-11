# Food Catalogue Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add admin-managed catalogue food images and rebuild the Food Catalogue as a compact, reference-matched, mobile-first interface without changing nutrition or price-security behavior.

**Architecture:** Add one nullable database path and a dedicated admin upload endpoint that reuses scoped public-media validation. Keep the existing member/admin catalogue serializers separate, then add a typed multipart client and focused catalogue components/styles around the unchanged query, filtering, pagination, nutrition, price, and food-creation flows.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy, Alembic, PostgreSQL, pytest, React 19, TypeScript, Vite, Vitest, Testing Library, CSS.

## Global Constraints

- Work on the existing `nutrition` branch and preserve unrelated worktree changes.
- Store files below `backend/var/media/food-catalogue/`; store only `/media/food-catalogue/<generated-name>` in the database.
- Accept uploads only; never accept an external image URL.
- Delete a replaced managed image only after the new path commits successfully.
- Member catalogue responses must never contain a `price` key.
- Keep existing nutrition calculations, catalogue records, aliases, search, filtering, pagination, Add Food, and Edit Price behavior unchanged.
- Main cards show only Calories, Protein, Carbs, and Fat; all other existing data remains in More Details.
- Support Persian RTL, English LTR, mobile-first layout, keyboard focus, and missing/broken-image fallback.

---

### Task 1: Food image persistence and API

**Files:**
- Create: `backend/alembic/versions/20260811_61_add_catalogue_food_images.py`
- Modify: `backend/app/nutrition/models.py`
- Modify: `backend/app/nutrition/schemas.py`
- Modify: `backend/app/nutrition/catalogue_view.py`
- Modify: `backend/app/nutrition/router.py`
- Modify: `backend/app/admin/media.py`
- Test: `backend/tests/admin/test_media.py`
- Test: `backend/tests/nutrition/test_member_food_catalogue_api.py`

**Interfaces:**
- Produces: `NutritionCatalogueFood.image_path: str | None`.
- Produces: `FoodCatalogueItemResponse.image_url: str | None` and inherited admin field.
- Produces: `store_image_upload(upload: UploadFile, settings: Settings, subdirectory: str) -> StoredMedia`.
- Produces: `POST /api/v1/nutrition/admin/foods/{slug}/image` with multipart field `file`.

- [ ] **Step 1: Write failing backend tests**

```python
def test_food_image_upload_is_admin_only_and_exposed_without_price(client, db, tmp_path, monkeypatch):
    monkeypatch.setattr("app.config.get_settings", lambda: test_settings(tmp_path))
    response = client.post(
        "/api/v1/nutrition/admin/foods/chicken-breast/image",
        headers=ORIGIN,
        files={"file": ("chicken.png", PNG_BYTES, "image/png")},
    )
    assert response.status_code == 200
    assert response.json()["image_url"].startswith("/media/food-catalogue/")
    member = client.get("/api/v1/nutrition/food-catalogue?q=chicken").json()["items"][0]
    assert member["image_url"] == response.json()["image_url"]
    assert "price" not in member
```

Also cover nullable `image_url`, invalid signatures, replacement cleanup, missing food, missing trusted origin, and non-admin access.

- [ ] **Step 2: Run focused tests and confirm expected failures**

Run: `uv run pytest tests/admin/test_media.py tests/nutrition/test_member_food_catalogue_api.py -q`

Expected: failures because image-only storage, `image_path`, `image_url`, and the upload route do not exist.

- [ ] **Step 3: Add migration and model field**

```python
revision = "20260811_61"
down_revision = "20260811_60"

def upgrade() -> None:
    op.add_column("nutrition_catalogue_foods", sa.Column("image_path", sa.String(500)))

def downgrade() -> None:
    op.drop_column("nutrition_catalogue_foods", "image_path")
```

- [ ] **Step 4: Implement scoped image validation and lifecycle**

Add PNG/WebP signature detection only to `store_image_upload`, create and validate the `food-catalogue` child directory, return a public path containing the child directory, and keep `store_upload` exercise behavior unchanged.

- [ ] **Step 5: Implement serialization and admin route**

```python
@router.post("/admin/foods/{slug}/image", dependencies=[Depends(require_trusted_origin)])
def upload_catalogue_food_image(
    slug: str,
    db: DatabaseSession,
    admin: AdminUser,
    settings: AppSettings,
    file: Annotated[UploadFile, File()],
) -> FoodCatalogueImageResponse:
    food = db.scalar(select(NutritionCatalogueFood).where(NutritionCatalogueFood.slug == slug))
    if food is None or food.verification_status == FoodVerificationStatus.RETIRED:
        raise HTTPException(status_code=404, detail="Food not found")
    stored = store_image_upload(file, settings, "food-catalogue")
    previous_path = food.image_path
    try:
        food.image_path = stored.public_path
        db.commit()
    except Exception:
        db.rollback()
        discard_media(stored)
        raise
    discard_managed_media_path(previous_path, settings, "food-catalogue")
    return FoodCatalogueImageResponse(image_url=stored.public_path)
```

Persist the new path, roll back and delete the new file on failure, then delete the old managed file after commit. Do not accept image paths in `CatalogueFoodWrite`.

- [ ] **Step 6: Run focused backend tests**

Run: `uv run pytest tests/admin/test_media.py tests/nutrition/test_member_food_catalogue_api.py -q`

Expected: pass.

- [ ] **Step 7: Commit**

```bash
git add backend/alembic/versions/20260811_61_add_catalogue_food_images.py backend/app/admin/media.py backend/app/nutrition/models.py backend/app/nutrition/schemas.py backend/app/nutrition/catalogue_view.py backend/app/nutrition/router.py backend/tests/admin/test_media.py backend/tests/nutrition/test_member_food_catalogue_api.py
git commit -m "feat(nutrition): add catalogue food image uploads"
```

### Task 2: Typed admin image workflow

**Files:**
- Modify: `frontend/src/features/nutrition/api.ts`
- Modify: `frontend/src/features/nutrition/FoodCataloguePage.tsx`
- Test: `frontend/src/features/nutrition/api.test.ts`
- Test: `frontend/src/features/nutrition/FoodCataloguePage.test.tsx`

**Interfaces:**
- Consumes: `image_url: string | null` and `POST /admin/foods/{slug}/image` from Task 1.
- Produces: `uploadCatalogueFoodImage(slug: string, file: File): Promise<{ image_url: string }>`.
- Produces: admin-only `FoodImageDialog` with preview, replace action, error state, and reload callback.

- [ ] **Step 1: Write failing frontend API and UI tests**

```tsx
expect(await screen.findByRole("img", { name: "سینه مرغ" })).toHaveAttribute(
  "src",
  "/media/food-catalogue/chicken.png",
);
expect(screen.queryByRole("button", { name: /بارگذاری تصویر/ })).not.toBeInTheDocument();
```

For admins, select a `File`, submit the dialog, assert `uploadCatalogueFoodImage` receives the slug/file, and assert catalogue reload. Test missing and broken image fallback.

- [ ] **Step 2: Run frontend tests and confirm expected failures**

Run: `npm run test -- src/features/nutrition/api.test.ts src/features/nutrition/FoodCataloguePage.test.tsx`

Expected: failures because `image_url`, upload client, fallback, and admin image controls do not exist.

- [ ] **Step 3: Implement typed multipart upload**

```typescript
export function uploadCatalogueFoodImage(slug: string, file: File) {
  const body = new FormData();
  body.append("file", file);
  return request<{ image_url: string }>(`${nutritionPath}/admin/foods/${slug}/image`, {
    method: "POST",
    body,
  });
}
```

Ensure the shared request layer does not force a JSON content type for `FormData`.

- [ ] **Step 4: Implement image rendering and admin dialog**

Add `image_url` to `FoodCatalogueItem`. Render a semantic image only when present, switch to the local fallback on `onError`, and expose upload/replace controls only when `user.is_admin` is true.

- [ ] **Step 5: Run focused frontend tests**

Run: `npm run test -- src/features/nutrition/api.test.ts src/features/nutrition/FoodCataloguePage.test.tsx`

Expected: pass.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/features/nutrition/api.ts frontend/src/features/nutrition/api.test.ts frontend/src/features/nutrition/FoodCataloguePage.tsx frontend/src/features/nutrition/FoodCataloguePage.test.tsx
git commit -m "feat(nutrition): add admin food image controls"
```

### Task 3: Reference-matched catalogue cards and chips

**Files:**
- Modify: `frontend/src/features/nutrition/FoodCataloguePage.tsx`
- Modify: `frontend/src/features/nutrition/foodCatalogue.css`
- Test: `frontend/src/features/nutrition/FoodCataloguePage.test.tsx`

**Interfaces:**
- Consumes: existing catalogue query and page response plus Task 2 image fields.
- Produces: scrollable category chip controls and compact `FoodCard` summary.
- Preserves: `FoodDetails`, `AddFoodDialog`, `PriceOverrideDialog`, and pagination behavior.

- [ ] **Step 1: Write failing card and category behavior tests**

```tsx
expect(screen.getByRole("button", { name: "همه گروه‌ها" })).toHaveAttribute("aria-pressed", "true");
expect(screen.getByText("کالری")).toBeVisible();
expect(screen.queryByText("فیبر")).not.toBeInTheDocument();
await user.click(screen.getByRole("button", { name: "جزئیات بیشتر" }));
expect(screen.getByText("فیبر")).toBeVisible();
```

Select a category chip and assert the next request retains query, resets page to 1, and sends the category. Assert only Protein, Carbs, and Fat appear on the card.

- [ ] **Step 2: Run the card tests and confirm expected failures**

Run: `npm run test -- src/features/nutrition/FoodCataloguePage.test.tsx`

Expected: failures because the select and five-macro strip still exist.

- [ ] **Step 3: Implement compact semantic markup**

Split the calorie from the three-item macro definition, move fibre out of the card, keep it in details, and replace the category select with `aria-pressed` buttons inside a named horizontal navigation region.

- [ ] **Step 4: Implement the visual system**

Use the existing Fitsho tokens with dark translucent cards, circular 88–112px image wells, turquoise calories, quiet dividers, compact admin actions, single-column mobile cards, optional two-column wide layout, `overflow-x: auto` chips, RTL-safe logical properties, focus-visible rings, and reduced-motion support.

- [ ] **Step 5: Run focused frontend tests**

Run: `npm run test -- src/features/nutrition/FoodCataloguePage.test.tsx`

Expected: pass.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/features/nutrition/FoodCataloguePage.tsx frontend/src/features/nutrition/FoodCataloguePage.test.tsx frontend/src/features/nutrition/foodCatalogue.css
git commit -m "feat(nutrition): redesign food catalogue cards"
```

### Task 4: Migration, full verification, and runtime review

**Files:**
- Modify only if verification finds a catalogue-scoped defect.

**Interfaces:**
- Consumes: all Task 1–3 behavior.
- Produces: verified database schema, automated checks, and RTL/LTR visual evidence.

- [ ] **Step 1: Apply the migration**

Run from `backend/`: `uv run alembic upgrade head`

Expected: database reaches `20260811_61`.

- [ ] **Step 2: Run backend verification**

Run: `uv run pytest tests/admin/test_media.py tests/nutrition/test_food_catalogue.py tests/nutrition/test_food_catalogue_api.py tests/nutrition/test_member_food_catalogue_api.py -q`

Run: `uv run ruff check app/admin/media.py app/nutrition tests/admin/test_media.py tests/nutrition/test_member_food_catalogue_api.py alembic/versions/20260811_61_add_catalogue_food_images.py`

Run: `uv run mypy`

- [ ] **Step 3: Run frontend verification**

Run: `npm run test -- src/features/nutrition/api.test.ts src/features/nutrition/FoodCataloguePage.test.tsx`

Run: `npm run lint`

Run: `npm run build`

- [ ] **Step 4: Run full test suites**

Run from `backend/`: `uv run pytest -q`

Run from `frontend/`: `npm run test`

- [ ] **Step 5: Perform runtime RTL and LTR checks**

Start the configured local stack, inspect `/food-catalogue` at a narrow mobile viewport and desktop viewport, upload and replace one admin image, verify the fallback, category chips, More Details, Add Food, Edit Price, pagination, RTL/LTR layout, and confirm the member network response contains no price key.

- [ ] **Step 6: Commit any verification-only correction**

If a catalogue-scoped defect required a change, stage only the exact files shown by
`git diff --name-only` for that correction and commit them with
`fix(nutrition): resolve catalogue verification defects`. If no correction was required,
do not create an empty commit.

- [ ] **Step 7: Push**

Run: `git push origin nutrition`

Expected: `origin/nutrition` includes every focused Food Catalogue commit without force-push.
