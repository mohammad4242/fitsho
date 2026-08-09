# Fitsho Food Catalogue Design

## Scope

Add a bilingual food-catalogue experience for authenticated members whose product mode is
`nutrition` or `both`. Training-only members must not see or access it. The page combines verified
nutrition composition with the latest accepted weekly price while keeping those domains separate in
persistence.

## User experience

- Rename the existing member navigation label from Nutrition Targets to Nutrition.
- Add a Food Catalogue destination with a distinctive food icon inside the Nutrition area.
- Keep the route at `/food-catalogue` and include an explicit back control to Nutrition.
- Display responsive food cards with Persian and English names, category, canonical serving basis,
  current weekly price, price date/status, calories, protein, carbohydrate, fat, and fibre per 100 g.
- Display `یافت نشد` / `Not found` when no accepted current price exists. Never display a guessed or
  review-only price.
- Open all available verified micronutrients and source metadata through a Details action.
- Support server-backed search, category filtering, and pagination.
- Apply RTL for Persian and LTR for English, with loading, empty, forbidden, and error states.

## Access control

- The catalogue API requires authentication and an eligible nutrition product mode (`nutrition` or
  `both`). The frontend hides the destination from training-only members, while the API independently
  returns `403` for them.
- Admin food and price mutations require the established admin dependency and trusted-origin check.
- All members see the same catalogue response; admin-only controls are added to the same page when
  `is_admin` is true.

## API and domain boundaries

- Add a dedicated read endpoint that joins verified catalogue identities and compositions with the
  latest accepted price reference. Do not couple composition models to pricing providers.
- Return explicit price status, canonical price unit, accepted timestamp, and nutritional basis.
- Reuse the existing admin food save endpoint for create/update behavior, strengthening validation
  where necessary so a newly visible food has bilingual names, category, canonical unit, source
  metadata, roles, and complete required macronutrients.
- Add an admin manual-price endpoint. It creates an audited fallback override rather than mutating
  immutable provider quotes or historical price records.

## Manual price override

- Store food, normalized price, canonical price unit, reason, administering user, creation time,
  expiry state, and the weekly update boundary that ends the override.
- A manual override is the current display/planner reference until the next successful scheduled or
  manual marketplace refresh accepts a replacement for that food.
- Expiration preserves both the override and all provider/history snapshots.
- Invalid, negative, unsupported-unit, or unaudited override requests are rejected.

## Data flow

1. The catalogue endpoint selects verified foods and their source-backed compositions.
2. It resolves an active manual override first; otherwise it uses the accepted current automated
   reference.
3. It emits `Not found` semantics when neither is usable.
4. Weekly ingestion continues to write immutable quotes and histories independently.
5. A newly accepted automated reference expires the active override for that food in the same
   transaction.

## Administration

- Admins use modals on the shared page to add a food or enter a fallback price.
- The add-food form includes identity, aliases, category, unit/basis, dietary roles/patterns, source
  details, and required macronutrients. It does not bypass verification requirements.
- The price form requires price, normalized unit, and reason and clearly states that the next
  successful weekly update replaces it.
- Routine pricing remains automatic; manual entry is exception-only.

## Validation and testing

- Backend tests cover authentication, product-mode authorization, catalogue joins, missing-price
  behavior, search/filter/pagination, admin-only mutations, trusted origins, complete food
  validation, override auditing, override precedence, and automatic expiry.
- Frontend tests cover navigation visibility by product mode, bilingual/RTL rendering, cards,
  details, missing price, back navigation, filters, pagination, and admin-only forms.
- Run Alembic migrations, Ruff, mypy, backend pytest, frontend lint, type/build, and Vitest.

## Compatibility

- Keep existing `/nutrition/foods`, nutrition planning, tracking, pricing history, and admin
  monitoring contracts intact.
- Do not expose provider credentials or raw provider payloads to members.
- Do not modify unrelated onboarding/profile work already present in the worktree.
