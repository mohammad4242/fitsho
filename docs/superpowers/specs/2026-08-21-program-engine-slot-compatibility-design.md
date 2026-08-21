# Program Engine Slot Compatibility

## Scope

Fix only exercise classification, catalog metadata correctness, and candidate-to-slot semantic matching. Injury/equipment eligibility, day count, volume, strength prescription, duration targeting, and recovery remain unchanged.

## Root cause

The Free Exercise DB classifier falls back from an unresolved movement pattern to a pattern inferred from `primary_muscle`. That can classify a multi-joint movement as a lower-body pattern when its source target is a lower-body muscle. Dynamic session construction then accepts candidates when their pattern is in the slot pattern set and their primary muscle matches. Template substitution and targeted accessories use the same partial check. Consequently, primary-muscle overlap can outweigh movement semantics.

## Design

Add one internal semantic compatibility policy. It receives a candidate, the slot's allowed movement patterns and target muscle(s), and the day focus. It returns a boolean plus deterministic reason codes. The policy is evaluated after existing safety/equipment eligibility and before ranking.

The policy will:

- require a known, allowed movement pattern;
- require a target-muscle match for muscle-specific slots, while never treating secondary-muscle overlap alone as sufficient;
- reject full-body or otherwise multi-pattern candidates from specialized slots unless the slot explicitly allows them;
- reject candidates whose movement pattern conflicts with the focus even when a muscle overlaps;
- remain permissive for genuinely compatible compounds and full-body layouts;
- fail closed for incomplete or `OTHER` semantic metadata.

`SlotSpec` remains internal. Its adapter passes explicit compatibility context to the shared policy without changing public API or catalog schemas. The same policy is used by dynamic required/optional slots, supplement matching, template substitutions, template resolvability checks, and targeted template accessories.

Rejected candidates receive stable reason codes such as `SLOT_MOVEMENT_PATTERN_MISMATCH`, `SLOT_SEMANTIC_MISMATCH`, and `SLOT_FULL_BODY_INCOMPATIBLE_WITH_SPECIALIZED_FOCUS`. Existing hard safety/equipment reason codes remain authoritative and are not replaced.

## Metadata correction

Use the canonical Free Exercise DB source identifier (`free-exercise-db:0028`) for the existing Barbell Clean And Press record. Correct its persisted programming metadata and importer classification using existing enums and labels, marking its multi-joint/full-body nature and overhead movement semantics. The classifier change is category-based and applies to ambiguous multi-pattern source records; it is not a special runtime name check. Existing valid metadata for other exercises remains unchanged.

## Data flow

1. Existing normalization and hard eligibility produce the safe/equipment-compatible catalog.
2. Slot compatibility filters candidates for the current slot/focus.
3. Existing rankers score only compatible candidates.
4. Existing session/template construction and repair consume those candidates.
5. Existing final validation remains unchanged except for preserving the new trace reason codes.

## Testing

Add explicit metadata fixtures and tests for:

- direct compatibility and movement-pattern mismatch;
- secondary-muscle-only and incomplete/`OTHER` metadata rejection;
- compatible compound acceptance;
- full-body specialized-slot rejection and explicit full-body-slot acceptance;
- safety/equipment filtering before semantic matching;
- template and dynamic slot paths;
- end-to-end `generate_program` lower-body output without the incompatible metadata fixture;
- canonical metadata correction for source identifier `0028`.

Run focused program-engine tests, backend lint/typecheck, and the related workout regression suite. Preserve and report the known unrelated day-count regression if it remains present.
