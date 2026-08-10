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

`GET /food-catalogue` returns verified foods only. Accepted member prices include
`reference_price_irr`, an `IRR_PER_*` unit, source, observation time, and acceptance time. Deprecated
Toman fields remain temporarily for older clients. Missing fresh prices return `status=not_found`.

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
