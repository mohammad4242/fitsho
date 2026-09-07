# Workout Plan Status and Session Average

## Goal

Make the four-item summary at the top of the workout page show the real current-plan status and one rounded average session duration.

## Scope

- Keep the existing four-column summary layout.
- Replace the hard-coded `active` label with a compact status icon and label:
  - `active` when the displayed plan is active and has no pending coach review.
  - `pending` when the displayed plan is pending review or its coach review is pending.
  - `inactive` for historical, superseded, failed, or otherwise non-active plans.
- When there is no active plan but a pending plan is available, use that pending plan for the summary and show `pending`.
- Calculate session duration from every day in the displayed plan with `Math.round(sum / count)` and show it as `N minutes per session`.
- Keep the existing detailed coach-review banners and pending-plan section unchanged.
- Add only the Persian and English labels required by the compact status.

## Architecture and data flow

The change is frontend-only. `WorkoutPlanPage` already receives the full active plan, selected historical plan, and pending plan from the existing API calls. The summary will select `plan ?? pendingPlan`; status will be derived from that plan's persisted `status`, `coach_review.state`, and historical-selection state. No backend endpoint, schema, migration, or new persistence is required.

The status icon will use existing `AppIcon` glyphs: `zap` for active, `clock` for pending, and `lock` for inactive. Existing CSS variables and the current four-column responsive layout will be reused so the card remains compact.

## Error and empty-state behavior

If no active or pending plan is available, the summary remains hidden as it is today. If a displayed plan has no session durations, the summary remains hidden rather than showing a made-up duration. Existing loading, error, generation, and review behavior is preserved.

## Verification

- Add page tests for the rounded average and removal of the min/max range.
- Add page tests for active, pending-coach, inactive historical, and pending-only statuses.
- Run the focused workout page test file, frontend lint, and frontend production build.
