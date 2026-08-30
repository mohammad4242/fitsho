# Professional Template Survival Design

## Status

Approved by the task specification on 2026-08-30. This design implements the six requested
architectural changes without weakening injury, equipment, hard volume, exact-day, or hard
duration contracts.

## Considered approaches

1. Full generic optimizer and shared evaluator
2. Bounded exact-candidate repair pipeline — selected
3. Local validator relaxations

The selected approach reuses current construction, prescription, volume, duration, recovery,
validation, and Final Gate functions. It adds typed evidence and bounded repair around them rather
than creating a second engine or changing topology scores.

## Constraint contract

Every relevant reason code has a stable class:

- `hard`: safety, blocked caution, unavailable mandatory equipment, exact requested day count,
  required structure, hard weekly/session volume, unresolved hard duration, and unsafe direct-high
  recovery.
- `repairable`: duration underfill/overfill before exhaustion, count mismatch, meaningful direct
  recovery conflicts, weekday conflicts, and adaptable optional/accessory work.
- `soft`: preferred/acceptable volume drift, secondary-only overlap, and quality preferences.

Unknown codes are never silently promoted to hard. Classification is observability only unless a
specific evaluator explicitly consumes it.

## Recovery contract

Recovery uses a typed per-muscle exposure vector:

- direct sets;
- secondary effective sets, retaining the ruleset's `0.5` accounting credit;
- source: direct, secondary-only, or mixed;
- load: light, moderate, or high;
- fatigue evidence, including primary-strength and axial-load signals.

Insufficient direct-high to direct-high spacing is hard. Direct-high/moderate and
direct-moderate/moderate are repairable when dose is meaningful. Direct/secondary-only is allowed
unless the indirect dose is substantial. Secondary/secondary cannot independently hard-reject a
program.

Recovery repair is deterministic and bounded:

1. rearrange weekdays;
2. reorder compatible day instances while preserving the same semantic topology multiset;
3. move removable isolation/accessory work to a compatible day;
4. reduce non-essential work within prescription and volume rules;
5. use a lower-fatigue compatible substitution when available;
6. reject only when the remaining assessment is hard.

Every conflict records muscle, day pair, sources, loads, direct/secondary dose, actual/required gap,
attempts, and final outcome.

## Duration and count contract

Main Training remains a hard invariant and continues to exclude general warm-up, anatomical Core,
and cardio.

| Request | Hard range |
|---:|---:|
| 30 | 20–40 |
| 45 | 35–55 |
| 60 | 50–70 |
| 75 | 60–85 |
| 90 | 65–100 |

The 30-minute MAIN count remains 3–4. Longer supported sessions retain the default hard minimum of
five MAIN exercises. Construction and duration repair must try a safe, target-compatible,
non-duplicate, non-near-equivalent useful exercise before count rejection. No-candidate outcomes
remain failures; no junk exception is introduced.

Duration repair order is useful set, useful exercise/accessory, safe superset, semantic
redistribution, then failure. Overfill removes or reduces the lowest-preservation work first.

## Template intent contract

Template identity is semantic, not slug-based. Required topology, day focus, target muscles,
mandatory roles, specialization, and priority intent are locked. Exact optional exercises,
accessory placement, compatible substitutions, and minor set/count composition are adaptable.

The trace records the original and final day intent, retained required slots, adaptations, and any
blocked proposal. A Body-Part, PPL, or Arnold-style structure cannot be accepted after being
transformed into a different topology.

## Exact post-construction feasibility

Each ranked template candidate is run through the real shared production lifecycle before it is
committed as the output. The result is classified as:

- `comfortably_feasible`;
- `repairable`;
- `tight`;
- `provably_infeasible`.

Repair cost is derived from actual deterministic adaptations, not an estimate. Hard-invalid
candidates are filtered. Among survivors, product score remains the primary preference and repair
cost is a tie-breaker, so a higher-preference professional template with a small repair beats a
generic Upper/Lower candidate without bypassing safety. The winning trace explains both survival
and selection.

## Integration flow

The engine flow remains:

`rank → build → prescribe → volume → bounded duration/recovery repair → redistribution → canonical
validation → Final Gate → candidate result → select winner/fallback`.

Late mutations trigger re-evaluation. A certification pass cannot discard a valid repair merely
because the state changed.

## Versioning

This changes generated behavior and therefore bumps the ruleset policy version. Engine version is
unchanged unless the current service compatibility tests prove a serialized engine contract change.

## Verification

Verification includes:

- exact duration boundary tests;
- direct/secondary recovery matrix and genuine unsafe negatives;
- topology-preserving adaptation and count repair tests;
- exact post-construction feasibility ordering tests;
- real production catalog/templates for Intermediate and Advanced, 4/5/6 days, and all five
  durations;
- the 180-case forced-template audit and 30 Competition cases;
- a separate matching-priority specialization audit;
- full Program Engine regression, Ruff, mypy, deterministic repeat checks, and diff review.
