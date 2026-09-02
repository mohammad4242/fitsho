# Food Catalogue Admin Retirement Design

## Goal

Allow an authenticated administrator to remove a food from the active Food Catalogue without deleting the `NutritionCatalogueFood` row or any historical references.

## Architecture

The existing `retire_catalogue_food(db, slug)` domain operation remains the single write path. It resolves the food, raises `ValueError("Food not found")` when the slug is absent, changes only `verification_status` to `FoodVerificationStatus.RETIRED`, and commits. Repeating the operation is safe and never calls `db.delete()`.

The existing admin route `DELETE /api/v1/nutrition/admin/foods/{slug}` already has the required admin and trusted-origin dependencies. Its contract will be covered by regression tests rather than duplicated. Member/admin catalogue reads and planner/price-update candidate queries already select only `VERIFIED` foods, so no read-model or planner changes are needed.

The catalogue seed will detect an existing retired row before rebuilding relations. It will update ordinary scalar seed metadata, preserve the retired status, and leave roles, aliases, compositions, and portions untouched for that row. New and active rows keep the current seed behavior and 72-row contract.

## Frontend flow

`FoodCataloguePage` will pass `onDelete` only for `AdminFoodCatalogueItem` cards. The action opens a `DeleteFoodDialog` built on `DialogFrame`; it displays the food name, explains active-catalogue/new-plan removal and historical preservation, and requires an explicit submit. Submit calls the shared `deleteCatalogueFood` API function, disables the submit button while pending, keeps the dialog open on failure, and reloads the current catalogue on success. If the deleted item was the only item on a page after page 1, the page moves back one page before reloading.

The delete action and dialog submit use explicit destructive selectors with the existing Fitsho dark/aqua visual language plus a restrained red border/text treatment. Existing price-button styling will no longer depend on `:last-child`.

## Verification

Backend tests cover soft retirement, idempotency, 404, admin authorization, trusted origin, active-catalogue disappearance for admin and member, planner/price candidate exclusion through existing filters, and preservation of aliases, compositions, portions, and historical price/reference data. Seed regression coverage proves a retired food is not resurrected and fresh seeding still returns 72 identities.

Frontend tests cover the delete API request, member/admin visibility, confirmation copy, cancel, successful reload, failure retention, and duplicate-request prevention. The focused Vitest suite, nutrition pytest suite, Ruff, frontend lint, and production build are required before completion.

## Scope exclusions

No restore/archive UI, hard delete, bulk action, migration, cascade change, planner change, price-service change, or member API contract change is included.
