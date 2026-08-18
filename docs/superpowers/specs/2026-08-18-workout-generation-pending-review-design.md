# Workout Generation Pending Review Persistence

## Scope

Implement roadmap task 0.2 only: a successfully generated workout plan is
persisted as `pending_review` and is not activated.

## Design

- Leave `activate_plan()` unchanged for the later coach-approval lifecycle.
- Add one repository persistence operation shared by deterministic and AI
  generation paths.
- The operation persists the new plan with `WorkoutPlanStatus.PENDING_REVIEW`,
  leaves `activated_at` null, marks its generation record `SUCCEEDED`, and
  calls `ensure_pending_review()` for the source plan.
- The operation does not query, modify, or supersede an existing active plan.

## Testing

- Update focused generation tests to assert the pending plan status, successful
  generation record, pending review, and null activation timestamp.
- Add focused coverage proving an existing active plan remains active while a
  new generated plan is pending review.
- Preserve existing validation, safety, and failed-generation behavior.

## Explicit non-goals

This task does not implement coach approval activation, change `activate_plan()`,
alter workout cycles, feedback, replacement logic, or program-engine behavior.
