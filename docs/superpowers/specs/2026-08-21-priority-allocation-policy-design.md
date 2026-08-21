# Priority Muscle Allocation Policy

## Scope

This change addresses only the distribution and measurable emphasis of
`priority_muscles` in the Program Engine. Safety and equipment eligibility,
day-count construction, set caps, session-duration policy, exercise
classification, strength programming, and fallback architecture remain the
existing authorities.

## Current failure

Priority currently increases a muscle's weekly volume target and gives some
split candidates a fixed priority bonus. The selected split can therefore
place priority work in a small number of specialized days. Weekly volume repair
then sees only an aggregate deficit and may add work to the first compatible
day, so the target is satisfied without a reliable frequency or recovery-aware
distribution.

For a six-day advanced hypertrophy request with hamstrings and quadriceps as
priorities, the current split score favors six-day body-part rotation over the
twice-weekly push/pull/legs split. Its focus sequence gives the two priority
muscles only a small number of direct lower-body opportunities.

## Design

Add an internal `priority_allocation.py` policy module. It has no API or
catalog-schema surface and operates only on normalized requests, split plans,
volume targets, and already eligible/programmed exercises.

The policy will:

1. Order priority muscles by their canonical enum value, making all tie breaks
   deterministic and treating multiple priorities fairly.
2. Derive a preferred exposure count from training days and the existing
   `maximum_direct_sessions_per_muscle_per_week`. Recovery-limited requests use
   the conservative one-exposure preference; otherwise the policy seeks a
   second exposure when the schedule and focus layout allow it.
3. Score split candidates by priority-focus coverage, evenness of priority
   exposure, and recovery spacing. Existing goal, experience, complexity, and
   safety-related selection rules remain in force. A split receives priority
   credit only for a focus that can legitimately train that muscle; the policy
   does not make a candidate eligible.
4. Provide deterministic day-order scores for volume repair. A day that has no
   current exposure for the most under-served priority is preferred, subject to
   existing focus matching, duration, volume, set-cap, safety, and equipment
   checks. Existing repair code remains responsible for deciding whether a
   candidate or set can actually be added.

The policy derives all limits from the ruleset and normalized request. It does
not special-case a user's name, a six-day request, or a particular muscle
combination.

## Volume behavior

The existing priority volume increase and hard maximums remain authoritative.
The planner will preserve the current target calculation while exposing the
policy's ordered priority set and frequency intent through reason codes and
metrics. Explicit priorities continue to receive more target volume than the
same request without them when capacity allows.

During repair, priority deficits are resolved in deterministic priority order,
with the next eligible day selected by exposure deficit and recovery spacing.
The existing per-exercise and per-session caps prevent set dumping. If the
catalog, duration, safety, equipment, or hard-volume limits prevent the soft
target from being reached, the target is reduced with an explicit constraint
reason instead of creating artificial volume.

Reason codes use the existing uppercase convention:

- `PRIORITY_VOLUME_INCREASED`
- `PRIORITY_FREQUENCY_INCREASED`
- `PRIORITY_VOLUME_REDISTRIBUTED`
- `PRIORITY_TARGET_PARTIALLY_SATISFIED`
- `PRIORITY_TARGET_CONSTRAINED`

Existing reason codes are retained for backward compatibility with current
traces and tests.

## Validation and observability

Final metrics will include a `priority_metrics` mapping keyed by muscle value.
Each entry reports planned target, direct sets, effective sets, exposure count,
exposure day indexes, and whether exposure is distributed across the preferred
frequency. Validation emits a warning/reason code when a priority receives
only partial soft-target emphasis, but does not turn a soft target into a new
hard constraint.

The final validation still enforces the existing safety, equipment, day-count,
set-cap, duration, volume-hard-limit, recovery, and semantic slot checks. The
new policy is advisory for selection and allocation; it cannot override those
hard constraints.

## Test plan

Add focused tests for:

- deterministic priority ordering and preferred exposure calculation;
- priority-aware split ranking for five- and six-day requests;
- one priority receiving greater direct/effective emphasis than the baseline;
- fair distribution for hamstrings plus quadriceps and for three priorities;
- repair choosing multiple valid days without exceeding existing caps;
- constrained catalogs emitting partial/constrained priority reason codes;
- safety and equipment rejection remaining effective during priority repair;
- preservation of day count, duration range, hard volume maximums, and exercise
  classification;
- an end-to-end advanced, muscle-gain, six-day request with hamstrings and
  quadriceps priorities.

Existing unrelated regressions remain outside this change and will be reported
without being broadened into this task.
