# Physician Nutrition Workspace Design

## Scope

Complete the existing physician nutrition workspace without creating a parallel clinical system.
The feature adds discoverable navigation, explicit queue views, and a clearer review workspace while
preserving the current physician authorization, audit trail, immutable plan revisions, laboratory
privacy, supplement workflow, and member-facing behavior.

## Access and navigation

`AuthenticatedHeader` checks `/api/v1/nutrition/physician/access` alongside the existing coach check.
An authorized physician sees `Physician workspace` / `پنل پزشک` in both account and desktop
navigation. The protected route remains `/physician/nutrition`; admin status alone does not grant
access. A user may independently hold physician and coach roles and see both workspaces.

## Queue behavior

The existing physician review endpoint gains an explicit view parameter:

- `pending`: unclaimed and changes-requested reviews available to the shared physician queue.
- `claimed`: reviews assigned to the current physician and still actionable, including waiting for
  laboratory information.
- `approved`: reviews approved by the current physician, returned as read-only history.

The backend remains responsible for ownership and status filtering. Approved reviews are never
claimable or editable. Queue rows include enough member and plan context for useful labels without
exposing laboratory contents or private notes.

## Workspace

The page follows the coach workspace information hierarchy: queue tabs and counts, a selected case
workspace, and a compact status/priority rail. Pending work can be claimed. Claimed work exposes the
existing clinical tools:

- inspect the exact immutable plan revision and nutrient validation;
- change food quantities and replace foods from the canonical catalogue;
- view and review authorized laboratory documents and request additional tests;
- create, edit, activate, complete, discontinue, or cancel supplement orders;
- record a member-visible note and a separate private physician note;
- approve, request changes, or reject the exact revision.

Approved cases remain visible but all mutating controls are disabled or omitted. The interface is
bilingual, RTL/LTR aware, keyboard accessible, responsive, and uses Fitsho's existing visual tokens.

## Data and safety

No new clinical tables are required. The implementation reuses `NutritionPlanPhysicianReview`,
`NutritionWeeklyPlan`, lab access controls, supplement orders, and audit events. Private physician
notes remain backend-only. Every mutation continues to validate physician role, case ownership,
exact revision, lifecycle transition, and hard nutrition invariants.

## Failure handling

One queue request failure does not erase an already selected case. Claim conflicts are shown as a
case-level error and the queue is refreshed. Failed edits retain the last trusted plan response.
Unauthorized users continue to be redirected by `PhysicianRoute`.

## Verification

Backend tests cover view filtering, physician ownership, approved history, read-only lifecycle, and
authorization. Frontend tests cover navigation visibility, queue tabs, claim/open behavior, approved
read-only rendering, and the existing plan, lab, supplement, and note actions. Full backend and
frontend suites, lint, type checks, build, migration state, and local runtime routes are verified
before push.
