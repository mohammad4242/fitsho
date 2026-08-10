# Nutrition API

All routes use `/api/v1/nutrition`. Mutating browser requests require a trusted frontend origin and
an authenticated session unless the route is explicitly an admin or physician route.

## User resources

- `PUT|GET /safety`, `POST /safety/evaluate`
- `PUT|GET /profile`, `PUT|GET /structured-exercise`
- `POST /estimates`, `GET /estimates/current`, `GET /physician-review-requirement`
- `POST /plans`, `GET /plans/latest`, `GET /plans/active`, `GET /plans/history`
- `GET /plans/{id}`, `GET /plans/{id}/shopping-list`
- Plan meal lock, feedback, remove/replace previews and confirmations, and partial regeneration under
  `/plans/{id}`
- Tracking check-ins, quick/catalogue entries, recent foods, exact edits, planned-meal adjustments,
  day/history views, deletion, adherence, and adaptive preferences under `/tracking`, `/adherence`,
  and `/adaptive-preferences`
- Food-photo estimate, confirmation, deletion, access grant, and signed file access under
  `/tracking/photo-estimates`
- Lab upload/list/delete, access grant, signed file access, and physician requests under `/labs` and
  `/lab-requests`
- Supplement catalogue and the current user's order list/acknowledgement under `/supplements` and
  `/supplement-orders`

## Physician and admin resources

Physician routes expose server-side access verification, the review queue, claim, exact plan
revision, structured food edits, plan action, lab request/review, and supplement-order
list/create/update/transition under `/physician`. `GET /physician/reviews?view=pending|claimed|approved`
returns separate queue views scoped to the authenticated physician. Pending cases may be claimed;
claimed cases expose the clinical editing workspace; approved cases are historical, read-only
snapshots. The response includes a safe member display name and never exposes private physician
notes. User-visible and internal physician notes are separate; internal notes never appear in
member plan responses. The physician role is checked independently of administrator status. Admin
routes manage canonical foods/meals and supplements.

`GET /food-catalogue` returns verified foods only and is member-safe: it never serializes a
catalogue `price` field. It includes bilingual identity, aliases/search results, category, complete
available nutrient composition, provenance, and household display portions. Price data is available
only through `GET /admin/food-catalogue`, which uses the same search, category, and pagination
semantics and adds the accepted/not-found price view for administrators.

Food composition remains canonical per 100 g in storage, planner inputs, tracking, and snapshots.
`portions` are source-backed display metadata with an exact gram conversion; clients rescale a
nutrient as `per_100g * portion_grams / 100` and always label the selected basis. If no defensible
portion exists, clients use the explicit 100 g fallback. Portion provenance is required and missing
nutrients remain missing rather than becoming zero.

Only foods with all five required primary nutrients (energy, protein, carbohydrate, total fat, and
fibre) may be `verified` and appear in the public catalogue. Incomplete identities remain `draft`.

### USDA Foundation Foods import

The curated base-food expansion uses the official FoodData Central Foundation Foods JSON release,
version `foundation-2026-04`. Download and extract the April 2026 JSON archive from the
[USDA dataset page](https://fdc.nal.usda.gov/download-datasets/), then run from `backend/`:

```bash
uv run python -m app.nutrition.usda_foundation_import <foundation-foods.json>
```

The import is idempotent and keeps the FDC record ID, release version, access date, nutrient-level
source, and canonical 100 g basis. It imports only the explicitly curated Iranian-relevant base-food
vocabulary, never variable prepared dishes. A mapped record missing any required primary nutrient
is stored as `draft`; optional nutrients absent from USDA remain absent. The downloaded source file
is intentionally not committed and no FoodData Central API key is required for this workflow.

Price operations are admin-only:

- `GET /admin/monitoring` returns counts, provider health, coverage warnings, review reasons, broken
  mappings, and recent manual/scheduled/catch-up runs. It never returns credential values.
- `POST /admin/prices/refresh` starts the same database-backed workflow as the weekly scheduler.
  Browser calls require a trusted origin.

## Important outcomes

`POST /plans` returns a generation result. Only `success` contains a plan. Safety, target
infeasibility, and `live_price_unavailable` remain generation outcomes, not plan lifecycle states.
`INSUFFICIENT_PRICE_COVERAGE` means no plan was created. Private file endpoints require an access
grant token bound to the current actor and resource. Rate-limited uploads return 429 with
`Retry-After`. Food-photo creation supports `Idempotency-Key` and explicit
`X-Fitsho-Food-Photo-Consent`.

FastAPI's runtime OpenAPI document is available at `/openapi.json` and interactive documentation at
`/docs` in environments where API documentation is exposed.
