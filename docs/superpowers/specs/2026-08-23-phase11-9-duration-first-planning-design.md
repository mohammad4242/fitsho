# Phase 11.9 Duration-First Planning Design

## Scope

Implement only roadmap goals 6 and 7: make requested workout duration a planning constraint before construction, and determine realistic exercise/set capacity before final sessions are built.

Out of scope: Phase 12, Home/Limited-Equipment robustness, unused-template cleanup, sex-based behavior, and unrelated refactoring.

## Duration Contract

`session_duration_minutes` remains the requested workout duration. General warm-up remains outside that duration. Planned cardio remains inside it and is reserved before resistance-work capacity is calculated.

The existing `SessionDurationPolicy` remains the sole source of requested-duration tolerance and core-preservation extension semantics.

## Shared Capacity Kernel

Add `duration_capacity.py` as the single deterministic planning abstraction. It will expose immutable session and weekly capacity assessments containing:

- requested workout minutes;
- allowed workout range;
- cardio reserve;
- resistance-work budget;
- target duration;
- expected exercise and working-set capacity;
- required/core and optional work costs;
- feasibility status: comfortable, tight, or infeasible;
- deterministic reason codes.

The kernel will reuse `prescription_for()`, `estimate_exercise_minutes()`, strength-role classification, warm-up rules, rest rules, and working-set caps. It will not duplicate prescription constants.

## Engine Flow

The flow becomes:

1. normalize and screen safety;
2. filter eligible resistance/cardio exercises;
3. determine cardio reserve;
4. build shared duration capacity context;
5. rank duration-aware templates;
6. rank duration-aware normal or availability-aware splits;
7. plan capacity-aware weekly volume;
8. build capacity-aware structural drafts;
9. prescribe final sessions;
10. repair volume, add cardio, and run late duration/recovery repair;
11. validate and emit diagnostics.

Exact requested supported resistance-day count remains mandatory.

## Template Feasibility

Extend `TemplateFeasibility`; do not add a parallel selector. For every template day, assess required/core cost and complete-template cost with the shared kernel.

Optional/accessory overage lowers feasibility and predicts trimming. It does not hard-reject the template. A template is hard-rejected for duration only when its safe required/core work cannot fit within legitimate capacity without weakening prescription minimums.

Duration feasibility participates in ranking before the stable slug tie-break. Existing goal/priority/body-analysis scoring stays separate.

## Split Feasibility

Normal split ranking and availability-aware dynamic fallback ranking will assess each focus through the same capacity kernel and its required `SlotSpec` work.

Short sessions prefer layouts whose required work fits. Longer sessions may select layouts with more useful capacity. Duration never changes requested resistance-day count or relaxes safety, equipment, recovery, or semantic compatibility.

## Capacity-Aware Volume

`plan_weekly_volume()` will receive the shared weekly capacity assessment. It retains current hard maxima and individualized recovery/history bounds, then allocates limited useful capacity in this order:

1. hard feasibility and required coverage;
2. explicit user priorities;
3. goal-appropriate useful stimulus;
4. clear Body Analysis lag;
5. mild Body Analysis lag;
6. optional accessory and variety work.

Targets reduced by real time pressure receive `DURATION_CAPACITY_LIMITED_VOLUME` in `VolumeTarget.constraint_reason_codes`. The planner will not apply a uniform duration percentage and will not add volume only to fill time.

## Exercise and Set Counts

Replace the unconditional five-exercise construction floor with a duration-aware feasible count derived from resistance-work budget, required slots, safe candidates, goal-specific prescription cost, and useful volume targets.

The ruleset's existing five-exercise value remains the normal quality target, not a universal hard floor. Reduced counts are allowed only when the shared capacity assessment proves the reduction intentional. The trace uses `DURATION_PLANNED_REDUCED_EXERCISE_COUNT`; thin-catalog failures retain separate eligibility/construction reasons.

## Prescription Protection

Duration pressure removes optional exercises first, then optional sets, then lower-priority volume. It does not change rep ranges, RIR rules, required warm-ups, physiological rest minimums, or per-exercise/per-muscle caps. Existing safe supersets may be reused without adding a new aggressive superset system.

## Validation and Diagnostics

Validation accepts fewer than five exercises only when the final session matches an explicit capacity plan and trace. It continues rejecting unexplained thin sessions.

The decision trace and aggregate diagnostics include planned resistance budget, planned exercise/set capacity, required work cost, estimated duration before and after late repair, repair severity (`not_needed`, `minor`, `major`), feasibility status, and unavoidable constraint reasons.

`repair_session_durations()` remains a final safety net. Major repair indicates planning failure unless the trace records a legitimate higher-priority constraint.

## Tests and Benchmark

Use red-green-refactor. Add final-program tests for the twenty requested duration, hierarchy, template, fallback, determinism, day-count, safety, equipment, long-session, repair-size, and Phase 11.7 retry cases.

Extend benchmark reporting only; do not modify the frozen Phase 11.6 population or thresholds. Preserve the saved current-HEAD baseline under `backend/var/benchmarks/phase11-9-baseline`, then run the same population after implementation with the requested duration subgroup and repair diagnostics.

Run all focused and full regression commands requested in the Phase 11.9 task. Do not commit or push.
