# Coach Workout Review Design

Date: 2026-08-09
Status: Approved design

## Goal

Add a coach workspace where generated workout plans enter a shared review queue. The initial
generated plan remains active and usable while review is pending. A coach can claim the review,
edit the permitted workout prescription fields, add notes, and approve an immutable revised
version. After approval, the revised version becomes active while both the original and the
coach-approved versions remain available to the member.

## Scope

This feature covers workout-plan review only. It does not change physician approval for nutrition,
send push/SMS notifications, or introduce coach assignment by members or administrators.

Coaches may edit:

- exercise selection
- sets
- minimum and maximum repetitions
- rest duration
- exercise notes

Coaches may not directly mutate an existing plan, bypass workout safety validation, or alter the
member profile snapshot used to create the original plan.

## Lifecycle

1. A generated workout plan is activated immediately using the existing generation workflow.
2. A pending coach-review record is created for that plan.
3. The member sees and can use the plan with a `pending_coach_review` presentation state.
4. The plan appears in the shared coach queue.
5. The first coach to claim it obtains an exclusive, renewable 30-minute review lease.
6. The coach edits an independent draft derived from the original plan and may save it repeatedly.
7. Final approval reruns the existing workout-plan safety and structural validation.
8. In one database transaction, the approved draft becomes a new immutable active plan version,
   the former active plan becomes historical, and the review is marked approved.
9. The member sees the coach-approved version as active and can open both versions from history.

The original generated plan remains unchanged throughout this lifecycle.

## Data Model

### Workout plan versions

Existing `workout_plans`, `workout_days`, and `workout_plan_exercises` remain the immutable source
of plan content. A new plan created by coach approval points to its source through a nullable
existing `previous_program_id`. Existing provenance fields are preserved. Coach approval metadata
is resolved through the associated review record rather than duplicated on the plan.

The existing one-active-plan-per-user constraint remains authoritative. Historical versions use
the existing non-active status rather than being deleted.

### Coach reviews

A dedicated workout review table records:

- source plan and member
- review status: `pending`, `claimed`, `approved`, or `superseded`
- claiming coach
- lease acquisition and expiration times
- coach note
- editable draft payload
- optimistic concurrency revision
- created, updated, and approved timestamps
- resulting approved plan ID

Only one open review may exist for a source plan. The draft is not a member-visible workout plan
until approval succeeds.

If a later generated plan supersedes the source before coach approval, the open review becomes
`superseded` and can no longer be claimed, edited, or approved. Its audit data remains available.

### Roles

The existing specialist-role infrastructure is reused. Access requires the `coach` specialist
role. Nutrition physician authorization remains unchanged.

## Backend Boundaries

A workout-review service owns queue queries, claiming, lease renewal, draft validation, draft
saving, and transactional approval. Routers perform authentication and response translation only.
Workout generation creates the pending review through this service/repository boundary without
depending on coach UI concerns.

Member workout queries expose:

- the active plan
- coach-review presentation state
- immutable plan-version history
- coach approval metadata and notes when applicable

Coach endpoints expose:

- shared pending queue
- reviews claimed by the current coach
- approved review history
- claim/renew actions
- review detail and editable draft
- draft save
- approval

## Concurrency

Claiming uses a database transaction and row-level locking so only one coach can obtain a valid
lease. A lease lasts 30 minutes and is renewed by authenticated coach activity. An expired lease
may be claimed by another coach. Save and approve operations include the draft revision so stale
browser writes fail instead of overwriting newer work.

Approval locks the review, source plan, and current active plan. It fails safely if the lease is
invalid, the draft revision is stale, or the source relationship no longer matches. No partial
activation is permitted.

## Validation and Safety

Exercise IDs must reference active, programmable catalogue exercises that remain compatible with
the captured plan/profile constraints. Sets, repetitions, rest duration, ordering, and uniqueness
must satisfy the existing database and workout-domain rules. The completed draft runs through the
current structural and safety validator before approval.

Validation failure preserves the draft and current active plan and returns stable machine-readable
error codes. Coach editing cannot clear or override a plan-level safety block.

## Frontend

### Coach workspace

The protected `/coach/workouts` route contains three views:

- pending shared queue
- claimed by me
- approved

Review detail shows the member's relevant training goal, experience, constraints, and immutable
source plan. The editor supports the allowed exercise prescription fields, coach notes, draft save,
and final approval. Lease ownership and expiry are visible, and stale/conflicting edits prompt a
reload rather than silently overwriting data.

### Member workout page

The current active plan remains the primary view. Before coach approval it shows “Waiting for coach
approval.” After approval, the active version shows “Coach approved,” coach name, approval date,
and the coach note when present.

A plan-version section lists the initial generated version and subsequent coach-approved version.
Members may open any version read-only, but only the latest accepted plan is active.

All new member and coach UI text is available in Persian and English and follows the existing RTL
and LTR behavior.

## Failure Handling

- Queue failure does not deactivate or hide a valid generated plan.
- A failed draft save does not change the member plan.
- A failed validation or approval preserves the last active plan and coach draft.
- Expired or stolen leases return an explicit conflict and never accept edits.
- Missing/deactivated exercises block approval with field-level validation details.
- Duplicate generation/retry paths do not create duplicate open reviews.
- A newer generated plan closes the older open review and cannot be replaced by its stale draft.

## Testing

Backend tests cover role enforcement, queue visibility, idempotent review creation, exclusive claim,
lease expiry and renewal, optimistic concurrency, allowed edit validation, invalid exercise
rejection, immutable source plans, atomic approval, one-active-plan enforcement, and member version
history.

Frontend tests cover coach route protection, queue tabs, claim state, editor fields, draft save,
approval errors, pending/approved member labels, bilingual rendering, and read-only version history.

Migration tests verify existing workout plans remain valid and receive no fabricated coach approval
state. Existing workout generation, nutrition, body-analysis, and profile behavior must continue to
pass their current suites.

## Delivery Boundary

Implementation ends after the coach workout-review workflow, member version history, migrations,
tests, and documentation are complete. Nutrition review behavior and external notification channels
remain out of scope.
