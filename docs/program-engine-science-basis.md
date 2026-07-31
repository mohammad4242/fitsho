# Program Engine V1 Science Basis

This document maps evidence to configurable engineering heuristics. Fitsho does not present the
ruleset as diagnosis, treatment, or an absolute prescription for every adult.

## Resistance training structure and volume

The 2026 ACSM position-stand summary emphasizes consistent participation, individualization, training
major muscles at least twice weekly when practical, roughly 10 weekly sets per muscle for hypertrophy,
and simple programs over unnecessary complexity. V1 therefore starts hypertrophy near nine sets,
prefers roughly two exposures, and keeps status/recovery ceilings conservative.

- [ACSM 2026 resistance-training guideline update](https://acsm.org/resistance-training-guidelines-update-2026/)
- [ACSM current position stands](https://acsm.org/education-resources/pronouncements-scientific-communications/position-stands/)
- [Weekly volume dose-response review](https://pubmed.ncbi.nlm.nih.gov/27433992/)
- [2026 volume/frequency meta-regressions](https://pubmed.ncbi.nlm.nih.gov/41343037/)

The V1 ranges (novice 4–8 through advanced 10–16) are intentionally bounded product heuristics. They
are not direct claims that every person has the same minimum effective or maximum recoverable volume.
The 1.0 primary and 0.5 secondary credits are explicit accounting heuristics; the newer meta-regression
also distinguishes direct and fractional indirect sets, but Fitsho's exact coefficients remain
configurable rather than physiological facts.

## Split and frequency

Full-body and split routines can produce similar strength and hypertrophy when volume is equated. V1
therefore scores structures for adherence, time, frequency, and recovery instead of declaring one
split universally superior.

- [Split versus full-body systematic review and meta-analysis](https://pubmed.ncbi.nlm.nih.gov/38595233/)
- [Resistance-training frequency and strength meta-analysis](https://pubmed.ncbi.nlm.nih.gov/29470825/)

## Exercise order

Strength improvements tend to be largest for exercises performed early. V1 places goal-specific and
priority movements early and does not default to pre-exhaustion.

- [Exercise-order systematic review and meta-analysis](https://pubmed.ncbi.nlm.nih.gov/32077380/)

## RIR and failure

Systematic reviews do not support mandatory momentary failure for general outcomes, while failure can
increase acute fatigue. V1 uses RIR ranges and does not prescribe failure by default, especially for
novices, technical compounds, or users with limitations.

- [Proximity-to-failure systematic review](https://pubmed.ncbi.nlm.nih.gov/36334240/)
- [Failure versus non-failure meta-analysis](https://pubmed.ncbi.nlm.nih.gov/33555822/)

## Rest intervals

Longer rest preserves repetitions and load for strength; hypertrophy evidence supports flexibility but
does not justify compressing rest simply to fit more exercises. V1 uses 180 seconds for strength
compounds, 90–120 seconds for typical hypertrophy work, and 60 seconds for endurance work.

- [Rest interval review](https://pubmed.ncbi.nlm.nih.gov/19691365/)
- [2024 Bayesian rest-interval meta-analysis](https://pubmed.ncbi.nlm.nih.gov/39205815/)

## Cardio and concurrent training

WHO's long-term adult-health target is 150–300 minutes of moderate activity or its vigorous equivalent,
but also states that some activity is better than none. V1 treats that as a destination, not a first-week
dose: it starts with 10-minute moderate, low-impact sessions when an eligible modality exists and may
trim a time-constrained bout to no less than the configured 5-minute minimum.

- [WHO physical-activity guidance](https://www.who.int/europe/publications/i/item/9789240014886)
- [Concurrent aerobic/resistance hypertrophy review](https://pubmed.ncbi.nlm.nih.gov/35476184/)

V1 schedules cardio after resistance work and avoids vigorous cardio on lower-body days. The exact
interference effect depends on modality and context; the scheduling rule is a conservative adherence
and fatigue-management heuristic.

## Safety screening

The official PAR-Q+/ePARmed-X+ system informs the principle that concerning symptoms and unclear
limitations require escalation rather than speculative exercise selection. Fitsho does not reproduce
or diagnose from PAR-Q+; it implements a narrow red-flag gate and requires explicit computable
constraints for stable limitations.

- [Official PAR-Q+ and ePARmed-X+](https://eparmedx.com/)
- [Official PAR-Q+ forms](https://eparmedx.com/?page_id=79)

## Review policy

Evidence and product heuristics should be reviewed when the ruleset version changes. A numeric change
requires a rationale here, one ruleset edit, focused tests, golden-scenario review, and an explicit
migration/diff note. Runtime generation never needs internet access.
