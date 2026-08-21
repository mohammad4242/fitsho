# Program Engine Session Duration Target Design

## Scope

Make `session_duration_minutes` a target for every successful workout day. The
accepted duration is exactly `requested - 10` through `requested + 10` minutes.
This change is limited to duration policy, session repair, estimation, and final
validation. Injury, equipment, day-count, volume policy, strength, and
prescription-mode behavior remain unchanged.

## Root cause

The engine currently uses duration as a rough capacity and validates only the
upper bound. A five-minute ruleset tolerance is duplicated in cardio and volume
repair. Nothing repairs a session that is materially shorter than the request,
so valid programs can be returned at 27–64 minutes for a 75–90 minute target.

## Central policy

Add one internal duration policy derived from the normalized request:

```text
requested = request.session_duration_minutes
minimum = requested - 10
maximum = requested + 10
```

All duration-fit decisions, cardio capacity, repair guards, and final
validation use this policy. The existing estimator remains authoritative and
continues to use exercise sets, reps or seconds, rest, warmups, transitions,
and cardio where supported. No estimated duration is changed artificially.

## Repair

After normal prescription and volume repair, repair each existing session
without changing the number of days:

1. Underfilled: complete already planned work where allowed, then spread safe
   compatible sets across existing exercises, then add eligible focus-compatible
   candidates through the existing candidate path.
2. Overfilled: reduce optional/accessory work, then soft-volume sets, then remove
   the lowest-priority exercise while preserving required, main, priority, and
   hard-minimum work.
3. Recompute the real estimate after every change.

The repair uses existing eligibility, equipment checks, per-exercise set caps,
weekly hard maxima, exercise-count limits, and session constraints. It never
adds unrelated work, dumps sets onto one exercise, creates cardio only to fill
time, or changes day count. If no safe repair exists, generation fails
explicitly.

## Integration and observability

Run the shared repair in both dynamic and template generation after volume repair
and around the existing cardio step. Final validation checks both bounds for
every day before success. Duration trace entries use the existing trace style
with these concepts:

- `SESSION_DURATION_UNDERFILLED`
- `SESSION_DURATION_OVERFILLED`
- `SESSION_DURATION_REPAIR_APPLIED`
- `SESSION_DURATION_TARGET_SATISFIED`
- `SESSION_DURATION_TARGET_UNSATISFIED`

The last state is a construction/validation failure, never a successful
out-of-range program.

## Verification

Tests cover the central bounds, 30/45/60/75/90/120 minute end-to-end targets,
underfill and overfill repair, no set dumping, safety/equipment preservation,
priority preservation, unchanged day count, and explicit failure when the
constraints are genuinely unsatisfiable.
