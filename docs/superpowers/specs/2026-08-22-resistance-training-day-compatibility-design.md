# Resistance-training day compatibility

## Scope

Phase 2 defines the official compatibility policy for resistance-training
sessions per week and the four profile experience levels. It does not change
goal filtering, template scoring, safety, equipment, or fallback behavior.

## Design

`app.profile.training_compatibility` owns one immutable, data-driven matrix.
Each experience level maps each supported day count from 2 through 6 to
`recommended`, `allowed`, or `unsupported`. The module also exposes a lookup
helper and a validator so profile, service, and engine code share the same
source of truth.

Profile create validates the complete pair. Profile updates validate the
effective pair after merging with the stored profile, including updates made
inside a workout-cycle transaction. The profile response exposes the resolved
status for UI use.

Deterministic generation validates the effective profile/request pair before
generation. The engine repeats the check defensively for official day counts
and rejects an unsupported pair with a dedicated generation error. A request
that exceeds the selected ruleset maximum is also rejected explicitly instead
of being capped, preserving the requested resistance-session count.

Lower-level engine fixtures that intentionally exercise one-day behavior remain
available for backward-compatible unit coverage; profile and service contracts
remain 2 through 6.

## Verification

Tests cover the complete 4 x 5 matrix, profile create/update boundaries,
deterministic status lookup, explicit engine rejection, exact valid day counts,
and preservation of existing generation behavior.
