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
- Tracking check-ins, quick/catalogue entries, day/history views, deletion, adherence, and adaptive
  preferences under `/tracking`, `/adherence`, and `/adaptive-preferences`
- Food-photo estimate, confirmation, deletion, access grant, and signed file access under
  `/tracking/photo-estimates`
- Lab upload/list/delete, access grant, signed file access, and physician requests under `/labs` and
  `/lab-requests`
- Supplement catalogue and the current user's order list/acknowledgement under `/supplements` and
  `/supplement-orders`

## Physician and admin resources

Physician routes expose the review queue, claim, exact plan revision, plan action, lab request, and
supplement-order creation/transition under `/physician`. The physician role is checked independently
of administrator status. Admin routes manage canonical foods/meals, supplements, and monitoring.

## Important outcomes

`POST /plans` returns a generation result. Only `success` contains a plan. Safety, target
infeasibility, and `live_price_unavailable` remain generation outcomes, not plan lifecycle states.
`INSUFFICIENT_PRICE_COVERAGE` means no plan was created. Private file endpoints require an access
grant token bound to the current actor and resource. Rate-limited uploads return 429 with
`Retry-After`. Food-photo creation supports `Idempotency-Key` and explicit
`X-Fitsho-Food-Photo-Consent`.

FastAPI's runtime OpenAPI document is available at `/openapi.json` and interactive documentation at
`/docs` in environments where API documentation is exposed.
