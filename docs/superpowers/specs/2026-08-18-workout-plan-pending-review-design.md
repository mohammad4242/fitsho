# Workout Plan `pending_review` Status

## Scope

Implement roadmap task 0.1 only: introduce an explicit pre-approval
`pending_review` status for workout plans.

## Design

- Add `PENDING_REVIEW = "pending_review"` to the existing backend
  `WorkoutPlanStatus` enum.
- Preserve all existing status values and current generation, activation, and
  coach-approval behavior.
- Keep the repository's non-native SQL string plus check-constraint convention.
  The migration will widen the status column as needed and replace the status
  check constraint with the expanded allowed-value set.
- Add `pending_review` to the frontend `WorkoutPlanStatus` union.

## Testing

- Add focused backend coverage proving the enum value is accepted by the
  persisted workout-plan status constraint.
- Add focused frontend type coverage only if an existing test boundary requires
  runtime verification; otherwise the strict TypeScript build validates the
  union update.
- Run focused backend tests, frontend tests/build, and migration checks relevant
  to the changed files.

## Explicit non-goals

This task does not change generation persistence, generation-record status,
`activate_plan()`, coach approval behavior, active-plan selection, or any later
roadmap task.
