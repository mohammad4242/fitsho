# Program Engine Issue 4: Exact Training-Day Construction

## Root cause

`rank_split_candidates` scores shorter splits highly for novice and recovery-
limited profiles. `generate_program` then accepts the first constructible split,
even when it has fewer days than the normalized request. The final validation
only compares schedule length with the selected split, so the silent reduction
is not rejected.

## Design

The engine will treat the normalized resistance-day count as a hard construction
invariant. `generate_program` will send only split candidates with exactly that
day count through template fallback and dynamic construction. Shorter candidates
will not be used as successful fallback alternatives.

Both template and dynamic construction will verify the final day count before
returning success. Independent program validation will also report a requested
day-count mismatch. If every exact-day candidate fails, generation returns an
explicit unsatisfied-constraint result with day-count reason codes and the
construction trace; it never returns an N-1-day success.

Preferred weekdays remain selected by the existing deterministic selector and
may be rearranged only by the existing recovery spacing repair. Recovery keeps
the number of days and no empty or placeholder day is synthesized.

No injury, equipment, volume, session-duration, strength, classification, or
exercise-selection rules are changed.

## Verification

Regression tests will cover successful generation for 2–6 days, the real five-
day scenario, template and session repair day preservation, preferred weekdays,
non-empty final days, explicit impossible exact-day failure, and an end-to-end
`generate_program` path. Existing tests that assert intentional day reduction
will be updated because that behavior is the bug being fixed.
