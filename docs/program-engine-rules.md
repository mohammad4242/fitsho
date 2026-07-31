# Program Engine V1 Rules

The executable source of truth is
`backend/app/workouts/program_engine/rulesets/resistance_training_v1.py`. Values are conservative
programming heuristics, not medical laws.

## Priority order

1. Safety
2. Hard constraints
3. Coherence
4. Goal relevance
5. Recoverability
6. Progression potential
7. Adherence
8. Time efficiency
9. Preferences
10. Variety

## V1 numeric rules

| Rule | V1 value | Runtime use |
|---|---:|---|
| Maximum resistance days | 6 | Split selection |
| Minimum recovery gap | 2 days for recovery-sensitive adjacent focuses | Split scoring/validator |
| Training-age thresholds | 6/18/48 months | Conservative status classification |
| Recent consistency floor | 4 weeks | Conservative status classification |
| Session duration tolerance | 5 minutes | Validator |
| General warm-up | 5 minutes | Duration model |
| Primary set credit | 1.0 | Volume metrics |
| Secondary set credit | 0.5 | Fractional volume metrics |
| Novice weekly range | 4–8 direct sets/muscle | Volume planning/ceiling |
| Early intermediate range | 6–10 | Volume planning/ceiling |
| Intermediate range | 8–12 | Volume planning/ceiling |
| Advanced range | 10–16 | Volume planning/ceiling |
| Hypertrophy/muscle-gain starting target | 9 | Goal baseline before modifiers |
| Priority-muscle bonus | 2 sets | Bounded by status ceiling |
| Poor-recovery reduction | 2 sets per signal | Sleep, stress, job, recovery history |
| Prior-volume increase ceiling | 20% | Avoids large unjustified jumps |
| Per-session muscle ceiling | 6 direct sets | Validator and prescription |
| Exercises/session ceiling | 8 | Session assembly |
| Cardio starter dose | 10 minutes; minimum 5 when time-constrained | Gradual prescription |

When time, prior exposure, and a generic status floor conflict, V1 prefers a smaller feasible program
and emits `PLANNED_VOLUME_REDUCED_DURING_SESSION_FIT`. It never shortens essential heavy-lift rest to
hide a duration overrun.

## Split rules

- Every supported day count produces typed candidate structures before scoring.
- Scores use only `split_weights` and `split_complexity` from the V1 ruleset.
- Goal specificity, simplicity, recovery, short sessions, priority muscles, and twice-weekly exposure
  influence ranking; stable type ordering resolves exact ties.
- One day: full body.
- Two days: full body A/B with at least three days between defaults.
- Three days: full body A/B/C and upper/lower/full are candidates; novices prefer the simpler option.
- Four days: upper/lower and short full-body sessions are candidates.
- Five days: upper/lower plus specialization and P/P/L/upper/lower are candidates.
- Six days: P/P/L twice and upper/lower repeated are candidates; experience and recovery decide.
- Seven available days: six resistance days maximum.
- Novice plus poor recovery/high physical job: three resistance days maximum.

## Eligibility rules

An exercise is rejected before scoring if inactive, non-programmable, review-pending, metadata
incomplete, blocked by ID/pattern/tag, too difficult, equipment-incompatible, above impact/axial-load/
balance limits, overhead-disallowed, or incompatible with explicit ROM constraints.

Cardio candidates require a cardio label, name, equipment, and impact metadata; resistance candidates
require primary muscle and a non-`other` movement pattern.

## Ordering and prescription

- Priority muscles are moved first, followed by major compound patterns, accessories, and trunk work.
- Same-session substitution-group duplicates are prevented.
- Short full-body sessions rotate push, pull, knee, hinge, and trunk slots across the week.
- Cross-day repeats require `CORE_MOVEMENT_REPEATED_FOR_PROGRESSION`.
- Strength compounds: 3–6 reps, RIR 2–3, 180-second default rest.
- Hypertrophy compounds: 6–12 reps; isolation: 10–20; RIR 2–3.
- General fitness: 6–15 reps, RIR 2–3.
- Muscular endurance: 12–25 reps, RIR 3, 60-second rest.
- The first compound gets two ramp-up sets, or three for strength.
- Ramp-up sets never count as working volume.
- Without reliable strength data, load guidance uses RIR and contains no exact weight.

## Progression and autoregulation

Default progression is double progression. Reaching the top of the range across all working sets,
inside target RIR with acceptable technique, must occur in two relevant sessions before load rises.
Upper-body guidance is 2.5–5%; lower-body guidance is 5–10%, always respecting the smallest available
increment. Load and volume are not increased together by default.

The persisted deload policy requires multiple fatigue signals, keeps movement patterns, suggests
30–50% less volume and optionally 5–10% less load, and never replaces a safety referral.
