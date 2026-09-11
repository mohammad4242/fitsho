# Food photo analysis queue

## Goal

Uploading a food photo must finish after the private image is stored and the
analysis request is queued. The web app and Android app must remain usable while
the AI call runs. The result must survive navigation and process restarts, and
the user must be able to find it later.

## Chosen architecture

Use PostgreSQL as a durable queue and run a dedicated `food-photo-worker`
process. Do not introduce Redis, Celery, or an in-process background task for
this flow.

`NutritionFoodPhotoEstimate` remains the user-facing resource. A new
`NutritionFoodPhotoAnalysisJob` stores one durable job for each estimate. The
job stores an immutable snapshot of the food-photo AI task configuration so a
queued request is auditable even if an administrator changes the task later.

The job has a lease. Workers claim queued jobs with `FOR UPDATE SKIP LOCKED`,
set `locked_at` and `locked_by`, and reclaim processing jobs whose lease has
expired. A worker crash therefore leaves a recoverable job instead of a lost
request.

## State model

The estimate status is one of `queued`, `analyzing`, `estimated`, `confirmed`,
`failed`, `deleted`, or `expired`.

The job status is one of `queued`, `processing`, `completed`, or `failed`.
Transient provider failures are retried with bounded exponential backoff. After
the retry limit, the estimate is `failed` with a safe error code. Provider
responses and credentials are never written to the API response, job payload,
notification, or logs.

Deleting an estimate removes its job and private image. A worker must check the
estimate under a row lock before persisting a result; a deleted estimate cannot
be resurrected by a late provider response. Existing retention cleanup remains
the authority for eventual private image deletion.

## Request and API flow

`POST /api/v1/nutrition/tracking/photo-estimates` keeps consent, validation,
rate-limit, idempotency, normalization, and private storage in the request
transaction. It creates the estimate and job atomically and returns `202` with
the estimate in `queued` state. Replaying an idempotency key returns the current
state of the same estimate.

The worker reads the stored image through the existing private `ImageInput`
contract (`storage_scope="food"`, `storage_key=<private key>`), calls the
configured provider, validates the strict `FoodPhotoOutput`, maps catalogue
items, and commits the result as `estimated`. A successful completion enqueues
one durable notification outbox event using the estimate ID as its
deduplication key. A terminal failure stores only a safe error code/message and
enqueues a failure notification.

Add authenticated owner-scoped endpoints:

* `GET /tracking/photo-estimates/{id}` returns the current state for polling.
* `GET /tracking/photo-estimates` returns recent non-deleted estimates for
  history and re-entry.

Correction, confirmation, free-meal preview, and private-file access continue
to require an `estimated` or `confirmed` resource as appropriate. Queued and
analyzing resources return a stable not-ready conflict code.

## Client behavior

The web upload waits only for the `202` upload response. It displays queued or
analyzing state in the photo panel, polls the current estimate while active,
refreshes history on completion, and leaves daily tracking controls usable.
On page entry it loads history, so leaving and returning does not lose the
record.

Android uses the existing upload manager only for the multipart request. Once
the queued response arrives, upload progress ends and the analysis continues
on the server. The nutrition screen polls active estimates, loads history on
entry, shows completion or failure, and routes the existing notification event
to nutrition. Cancelling an upload does not attempt to cancel a server job.

Add a `nutrition_updates` notification preference. Completion and terminal
failure events contain only the event type and estimate ID; Android opens the
nutrition screen. Web persistence and polling provide the same result without
requiring browser push support.

## Verification

Backend tests cover atomic enqueue and `202`, idempotent replay, owner-scoped
get/list, claim and stale-lease recovery, retry and terminal failure, result
persistence, deletion race protection, and notification enqueueing. Frontend
and Android tests cover immediate return from upload, active polling, history
re-entry, completion/failure rendering, and continued interaction with other
tracking controls.

Run focused backend, web, and mobile tests, then the applicable lint/type/build
checks. Apply the migration and run an integration smoke check with the
dedicated worker process before release handoff.
