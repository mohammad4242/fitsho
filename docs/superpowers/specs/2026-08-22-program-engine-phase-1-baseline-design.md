# Program Engine Phase 1 Baseline

## Scope

Establish a tested characterization baseline for the deterministic workout
program engine before changing template-selection behavior.

This phase preserves the current selector contract and all downstream
personalization, safety, construction, repair, and validation behavior. It does
not implement the future separation of hard template filters, personalization
scoring, and constraints.

## Current deterministic flow

`generate_program()` currently follows this sequence:

1. Apply the ruleset-aware body-analysis influence policy to the incoming
   request.
2. Normalize the request. This classifies training status from experience,
   training age, and recent consistency; derives a deterministic seed; caps
   resistance days; and derives constraints.
3. Screen safety. Stop-and-refer, specialist review, or non-computable
   limitations return before exercise selection. Explicit limitations produce
   `CLEAR_WITH_MODIFICATIONS` and continue.
4. Filter exercise eligibility. The filter applies catalog state and metadata,
   blocked exercises and patterns, equipment, skill, caution, impact, loading,
   balance, overhead, range-of-motion, and resistance-training constraints.
5. Derive the previous-volume baseline and cardio reserve, then attempt a
   template reference. Current template selection is a hard filter on training
   days, mapped training level, goal compatibility, and resolvable core slots.
   Among matches, the selector scores explicit priority tags, body-analysis
   priorities, classic/no-priority preference, and long-session compatibility;
   ties are deterministic by template slug.
6. Adapt a selected template. Core and optional slots are resolved against the
   eligible catalog, safe substitutions and complementary roles are selected,
   required core work and targeted accessories are added when needed, and
   capacity is enforced. Template intent is then applied to prescribed days,
   preserving titles, intensity methods, and adaptation trace data.
7. Plan weekly volume, build or prescribe sessions, repair weekly volume, add
   cardio, repair session duration, and repair recovery weekdays.
8. Build metrics and the decision trace, construct the program, and validate all
   program invariants. A failed template attempt is recorded and the engine
   continues with dynamic split construction.
9. If no template succeeds, rank exact-day split candidates and try them in
   deterministic order. If those fail, rank availability-aware dynamic fallback
   splits and try the same construction/repair/validation path.
10. If all alternatives fail, return
    `UNSATISFIED_CONSTRAINT` with construction-recovery evidence rather than
    weakening constraints.

## Phase 1 test baseline

The baseline test suite will:

- retain the current selector's goal mapping and hard day/level/goal filters;
- retain deterministic score ordering and tie-breaking;
- retain template slot substitution and adaptation trace behavior;
- retain safety, equipment, priority allocation, body-analysis influence,
  volume, prescription, duration repair, validation, and dynamic fallback
  coverage;
- update only stale seed-library assertions to the current 55-template seed
  library and its current two-day full-body coverage contract; and
- add focused characterization coverage where the current template-selection
  contract is otherwise implicit.

No production selector redesign, sex scoring, First Month mapping, template
family expansion, schema change, or migration is in scope.

## Phase 2 risks

The current selector still treats goal as a hard template filter and also uses
goal-specific template fitness goals. Future work must intentionally separate
those concerns while preserving the downstream template adaptation and dynamic
fallback contracts. The current seed library contains both the original
general-purpose templates and newer goal-specific templates, so future tests
should distinguish library characterization from the desired selection policy.
