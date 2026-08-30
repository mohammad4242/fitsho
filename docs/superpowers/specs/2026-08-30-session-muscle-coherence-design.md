# Session Muscle Coherence

## Goal

Fitsho must concentrate direct muscle work inside sessions that explicitly intend to train
that muscle. Weekly volume and user priority may deepen or reorder an intended exposure, but
must never authorize a new direct muscle group outside the session scope.

Secondary recruitment is not direct work. A chest exercise remains chest work when its
secondary muscles include shoulders or triceps.

## Confirmed creation paths

New direct exposure can currently enter through:

- dynamic required and optional slot selection in `session_builder.py`;
- template slot resolution, redundancy replacement, and targeted fill in
  `template_sessions.py`;
- exercise addition and set-placement ranking in `volume_repair.py`;
- set and exercise addition in `session_duration.py`;
- optional-isolation relocation in `recovery.py`;
- whole-exercise balancing in `weekly_distribution.py`.

Validation currently checks slot compatibility but does not enforce the template day's exact
direct target set. Template duration fill also widens the allowed set with muscles already
present, and hard priority volume repair can bypass the template target set.

## Authoritative policy

Add `session_coherence.py` with:

- `SessionMuscleRole`: `PRIMARY`, `SECONDARY`, `ACCESSORY`, `DISALLOWED`;
- an immutable `SessionCoherence` value containing allowed, primary, secondary, and accessory
  direct muscles;
- constructors for a dynamic focus, a template reference day, a session draft, and a workout
  day;
- deterministic role and placement ranking;
- compact trace and audit helpers.

For templates, `TemplateReferenceDay.focus` and propagated `template_target_muscles` are the
exact allowed direct set. `structure_focus` determines hierarchy but cannot enlarge the set.
For dynamic sessions, the resolved focus topology supplies both the exact allowed set and the
hierarchy. Broad Upper, Lower, and Full Body focuses remain broad.

The hierarchy is centralized. Large intended blocks precede grouped muscles, and grouped
muscles precede accessories. Examples: chest before triceps, back before biceps, shoulders
before traps, major lower muscles before calves, and chest/back before shoulders and arms in
Upper sessions.

## Integration invariants

1. Candidate construction rejects any non-supplemental exercise whose primary muscle is not
   allowed by the session policy.
2. Existing direct exposure on the highest-role intended day is preferred before opening a
   second intended exposure.
3. User priority only changes ranking inside the allowed set.
4. Duration repair extends primary blocks before secondary or accessory blocks.
5. Template substitution and redundancy replacement preserve the exact template-day scope.
6. Recovery repair may move direct work only to an intended day and may not create an
   out-of-scope exposure.
7. Validation rejects an out-of-scope direct primary muscle. Secondary recruitment does not
   participate in this check.
8. Weekly redistribution and its aggregate metric are removed. Unequal valid session counts
   are accepted.

## Observability

The final program trace records each session's intended direct muscles and role groups. Volume
and duration repair record compact accepted and rejected placement decisions with requested
muscle, candidate day, day role, status, and reason code. Rejected candidates are deduplicated
to avoid trace noise.

The aggregate audit reports direct groups, direct exercise counts per muscle, orphan direct
exposures, one-exercise non-primary blocks, focus preservation, post-construction out-of-scope
additions, and exercise counts per session.

## Failure behavior

If useful work cannot meet volume, exercise-count, or duration contracts inside the allowed
scope, repair stops with a constrained or unsatisfied reason. It does not broaden the session,
inflate rest, bypass safety, or exceed hard volume, duration, recovery, and equipment limits.

## Verification

Tests cover specialized templates, Body-Part, PPL, Upper/Lower, Full Body, priority placement,
lower hierarchy, duration and volume repair, redundancy replacement, direct-versus-secondary
semantics, and preservation of unequal session counts. Runtime audits cover Intermediate and
Advanced 4/5/6-day generation across 30/45/60/75/90 minutes plus the existing 20-profile
evaluation.
