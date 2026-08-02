# Volume-aware split engine design

## Scope

Refine the deterministic Fitsho coach for hypertrophy-focused beginner, intermediate, and appropriately recovered advanced users. The engine must treat the profile's available training days as a maximum, choose an appropriate split and actual number of resistance sessions, and repair volume allocation before final validation.

## Decisions

- `training_days_per_week` means the maximum number of days the user can train, not an exact session count.
- The engine may select fewer sessions when recovery, time, safety, or volume distribution makes that safer. Seven available days permit at most six resistance sessions; the remaining day may be rest or optional light cardio.
- Training status remains the declared experience level when recent consistency is unknown. It is reduced only by explicit, known training-history evidence.
- Each major muscle has four direct-volume values: `minimum_soft`, `target_sets`, `maximum_soft`, and `maximum_hard`.
- `maximum_soft` is `target_sets` plus a recovery/status allowance: one set for a beginner or poor recovery, two for an intermediate user with ordinary recovery, and three for an advanced user with good recovery. `maximum_hard` remains a non-negotiable safety ceiling.
- Direct sets control the formal volume budget. Indirect sets are calculated separately with the configured fractional credit and influence ranking, fatigue, and direct-accessory selection.

## Split library

The selector scores every compatible template at every feasible number of resistance sessions up to the profile cap. It does not select a template from one hardcoded day-count condition.

| Available maximum | Candidate templates | Default use |
| --- | --- | --- |
| 2 | Full Body A/B | compact, balanced exposure |
| 3 | Full Body A/B/C; Upper/Lower/Full | balanced hypertrophy and time efficiency |
| 4 | Upper/Lower; Full Body Four; PHUL; Body-Part Rotation | intermediate and advanced users |
| 5 | Push/Pull/Legs/Upper/Lower; Upper/Lower plus specialization | higher volume or a priority muscle |
| 6 | Push/Pull/Legs A/B; Upper/Lower A/B/C | advanced users with adequate recovery |

Five-day `Push/Pull/Legs/Upper/Lower` is a balanced candidate, not a universal default. It provides a second exposure for chest, back, shoulders, arms, quadriceps, hamstrings, glutes, calves, and trunk without assigning a universal body-part rule. The body-part rotation candidate is only scored as a preference for an advanced hypertrophy user with at least 60 minutes per session.

```text
Push: chest, anterior/lateral deltoids, triceps
Pull: lats and upper back, posterior deltoids, biceps
Legs: quadriceps, hamstrings, glutes, calves, trunk
Upper: chest, back, deltoids, direct arms only if needed
Lower: quadriceps, hamstrings, glutes, calves, trunk
```

The selector scores goal fit, frequency distribution, direct and indirect volume, recovery spacing, fatigue interference, session duration, priority muscles, available equipment, and user preference. Compound movements and larger target muscles are scheduled before smaller accessory work, unless a priority muscle or safety constraint requires another order.

## Five-day example

Example input: intermediate hypertrophy user, gym access, 60 to 75 minutes per session, no injury, no single priority muscle.

```text
Day 1: Push  — horizontal press, incline press, vertical press or lateral raise, triceps
Day 2: Pull  — vertical pull, row, rear deltoid, biceps
Day 3: Legs A — knee dominant movement, hip hinge, leg curl, calves, trunk
Day 4: Upper — chest press, row, vertical pull, lateral/rear deltoid, direct arms only if required
Day 5: Lower B — hip dominant movement, knee dominant movement, hamstring accessory, calves, trunk
```

The two lower days are separated, chest and back receive two planned exposures, and arm isolation is determined after indirect volume from pressing and pulling is counted. A chest-priority user receives chest first on Push, a second chest slot on Upper when the volume budget allows it, and lower-value accessory work is reduced first. A back-priority user changes the ordering and optional slots without changing safety or the weekly hard ceiling.

## Set allocation and repair

1. Build movement slots from the chosen split and eligible catalog.
2. Allocate each muscle's integer direct-set budget across its appearances exactly. For example, a target of ten sets across three appearances becomes `4 + 3 + 3`, never `4 + 4 + 4` due to repeated ceiling rounding.
3. Fit the prescriptions into the session time budget.
4. Repair deterministically before validation, in this order:
   - reduce hard excess from later non-priority work while preserving minimum working sets;
   - remove a redundant direct exposure only when another exposure of that muscle remains;
   - rebuild exercise order and session-time estimates.
5. Preserve priority-muscle volume unless no valid safe plan remains.

## Validator behavior

- Values below `minimum_soft` or above `maximum_soft` produce structured warnings and an explanation.
- A value above `maximum_hard`, a session-duration violation, a safety violation, or a movement/equipment conflict fails validation.
- The validation report exposes direct sets, fractional indirect sets, soft-range warnings, hard failures, and repair decisions. Effective exposure is available to later ranking rules but is not yet a separate persisted metric.

## Future approved physique-assessment boundary

Future body-image analysis is advisory only. The workflow is strictly:

```text
body photos -> model preliminary observations -> human coach approval or edit
-> structured approved priorities and limitations -> deterministic engine
```

Only the approved structured result may affect `priority_muscles`, volume targets, exercise order, or split scoring. A raw model assessment cannot change a program, diagnose a condition, or override safety constraints. The current engine already consumes `priority_muscles`, so this future workflow requires an approval record and UI/API integration rather than a new training-rule path.

## Tests

- Four-day generation does not exceed a shoulder hard maximum through duplicate ceiling rounding.
- Six-day generation does not exceed a back hard maximum.
- Seven available days produce at most six resistance sessions and can choose fewer based on recovery.
- Exact allocation distributes ten sets as `4 + 3 + 3`.
- Soft-range deviation produces a warning; hard-ceiling breach produces a structured validation error.
- Unknown recent history does not downgrade an otherwise advanced profile; explicit insufficient consistency does.
- Existing safety, equipment, time-budget, direct/indirect volume, and complete-generation integration tests remain green.

## Non-goals

- This version does not diagnose injuries, prescribe rehabilitation, or guarantee a particular bodybuilding methodology.
- It does not add a new persisted training-history field. The engine first distinguishes unknown history from explicitly recorded history.

## Evidence basis

- Split and full-body routines show similar hypertrophy and strength outcomes when volume is equated: https://pubmed.ncbi.nlm.nih.gov/38595233/
- Weekly volume and frequency should be assessed separately, and fractional indirect-set accounting is supported by the 2026 meta-regression: https://pubmed.ncbi.nlm.nih.gov/41343037/
- Exercise order should generally prioritize larger/multi-joint movements before smaller/single-joint work: https://pubmed.ncbi.nlm.nih.gov/11828249/
