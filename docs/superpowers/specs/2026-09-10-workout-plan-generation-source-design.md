# Workout-plan generation source summary

## Scope

Expose the persisted generation provenance of the displayed workout plan and use it only in the second cell of the existing four-cell summary strip on web and React Native. The plan-duration badge and the other three cells remain unchanged.

## Design

`WorkoutPlanResponse` will expose a required nullable `generation_source` field with the public values `internal_engine`, `ai`, or `null`. The router response mapper will normalize `WorkoutPlan.generation_method`. Direct `ai` and `deterministic_domain` values map directly. For `coach_review`, the mapper follows `previous_program_id` until it finds the original recognized source, while returning `null` for unknown or unsafe legacy chains.

The OpenAPI contract is regenerated and the manually maintained core `WorkoutPlan` type is kept consistent. Mobile continues to derive its plan type from the generated schema.

The web and native summary strips will read only the displayed plan's `generation_source`. They will use dedicated translation keys for the heading and source labels, and render an em dash for `null`. The generation-method controls remain responsible only for future generation requests.

## Verification

Focused backend API tests will cover deterministic, AI, and coach-reviewed provenance. Web and native tests will cover both sources and the profile-preference regression case. The native contract will continue to assert exactly four context cells. OpenAPI consistency, core build, focused tests, and mobile typechecking will be run before handoff.

## Non-goals

No database migration, generation algorithm change, coach-review behavior change, duration-badge change, summary-strip redesign, or unrelated refactor.
