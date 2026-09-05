# Fitsho — Best Program Selection Roadmap

## Purpose

The current engine already has strong components for safety, eligibility, volume planning, recovery, template selection, split ranking, validation, final gating, and coach-quality metrics. The main architectural limitation is that not every generation path compares multiple **fully built, fully validated successful programs** before returning a result.

The goal of this roadmap is to change the final decision model from:

> Build candidates in rank order and return the first successful program.

into:

> Build a bounded set of promising candidates, reject anything that fails hard constraints, compare the surviving programs by actual post-construction coaching quality, and return the best one.

This must **not** lower safety or quality standards. The engine should become more permissive only where a rule is truly soft, while becoming stricter about final program quality.

---

# 1. Core Design Principle

The engine should operate in three clearly separated layers:

1. **Candidate proposal** — “Which templates/splits look promising before construction?”
2. **Program construction + validation** — “Can this candidate be turned into a safe, coherent, valid program?”
3. **Final coach selection** — “Among the valid programs, which one is best for this user?”

The current engine already implements most of layers 1 and 2. The new work is mainly to formalize layer 3 and make all candidate-generation paths feed into it.

The decision hierarchy must be:

1. Hard validity / safety
2. Structural completeness / coverage
3. No severe weak dimension
4. Volume fit
5. Priority-muscle satisfaction
6. Body-analysis satisfaction
7. Recovery quality
8. Warning / constraint burden
9. Repair burden
10. Substitution burden
11. Duration fit as a soft quality signal
12. Pre-construction rank / curated source as tie-breakers

A soft quality score must never compensate for a failed hard constraint.

---

# 2. Current Engine Behavior That Must Change

## 2.1 Template path

The template path is already more advanced than the ordinary split path.

Current behavior:

- `template_selector.py` ranks candidate templates before construction.
- `engine.py` can construct more than one template candidate.
- `template_survival.py` measures post-construction survival and repair cost.
- The engine selects among successful template candidates using a survival/product-score key.

Problem:

The final comparison is still dominated by template pre-construction score and repair count, not by the full actual quality of the final generated program.

Also, when a successful template is selected, the engine can return before canonical non-template splits have a chance to compete at final program quality level.

## 2.2 Exact split path

Current behavior in `engine.py`:

```python
for candidate in exact_day_splits:
    result = _program_for_split(...)
    if result.is_success:
        return result
```

Problem:

This is a first-success policy.

A valid rank-1 split can prevent a clearly better rank-2 or rank-3 program from ever being built and compared.

## 2.3 Dynamic fallback path

Dynamic splits are intentionally fallback structures and should remain fallbacks.

They should not normally compete equally with a valid high-quality canonical or professional template. They should be used when the primary candidate families do not produce a suitable final program, or under a deliberately defined quality threshold.

---

# 3. New Runtime File to Create

## Create

`backend/app/workouts/program_engine/program_selection.py`

This file must contain **final selection policy only**. It must not build exercises, calculate prescriptions, mutate programs, or replace split/template rankers.

Its job is:

> Receive fully constructed candidate results and deterministically choose the best valid program.

---

# 4. `program_selection.py` Responsibilities

## 4.1 Add an internal `ProgramCandidate` dataclass

Recommended fields:

```python
@dataclass(frozen=True, slots=True)
class ProgramCandidate:
    source: Literal["template", "exact_split", "dynamic_fallback"]
    identifier: str
    preconstruction_rank: int
    preconstruction_score: int | float | None
    result: ProgramGenerationResult
    repair_events: tuple[str, ...] = ()
```

Optional additional fields if they make trace generation simpler:

```python
source_metadata: Mapping[str, object]
```

Do not expose this through public API schemas unless necessary. It can remain an internal engine object.

## 4.2 Add a final-quality extraction helper

Example responsibility:

```python
def build_program_quality_view(candidate: ProgramCandidate) -> ProgramQualityView:
    ...
```

The helper should read existing final program metrics, especially:

- `program.aggregate_metrics["coach_quality"]`
- final gate status
- validation warnings
- repair events
- substitution information

Do not recalculate the entire coaching model in a second place.

The engine already computes coach-quality metrics. `program_selection.py` should consume them.

## 4.3 Add `program_candidate_sort_key(...)`

Use a **lexicographic key**, not a single weighted score.

Recommended conceptual ordering:

```text
A. candidate is final-gate accepted
B. coverage is complete / satisfactory
C. maximize the worst major coaching dimension
D. maximize volume fit
E. maximize explicit priority satisfaction
F. maximize body-analysis priority satisfaction
G. maximize recovery fit
H. minimize warning/constraint count
I. minimize repair count
J. minimize substitution count
K. maximize preferred duration fit
L. prefer curated/template source when final quality is effectively tied
M. prefer higher pre-construction rank/score as final tie-breaker
N. deterministic identifier tie-break
```

### Why “worst major dimension” matters

The engine should prefer a balanced program over one with a very strong average but one obvious weakness.

Example:

Program A:

- volume: 100
- priority: 70
- body-analysis: 100
- recovery: 100

Program B:

- volume: 94
- priority: 94
- body-analysis: 93
- recovery: 100

A simple average can overvalue Program A.

A coach-quality selector should usually prefer Program B because its weakest important dimension is much stronger.

Recommended major dimensions for worst-dimension comparison:

- volume fit
- priority target satisfaction, when applicable
- body-analysis target satisfaction, when applicable
- recovery fit
- coverage fit if numeric/compatible

Ignore “not applicable” dimensions instead of treating them as zero.

## 4.4 Add `select_best_program(...)`

Recommended interface:

```python
def select_best_program(
    candidates: Sequence[ProgramCandidate],
) -> ProgramCandidate | None:
    ...
```

Rules:

- Ignore/reject any candidate whose `result.is_success` is false.
- Require a non-null program.
- Require final gate acceptance evidence already produced by engine construction.
- Never allow soft score to override a rejected final gate.
- Selection must be deterministic.

## 4.5 Add selection decision trace builder

The selected program should contain a trace entry similar to:

```text
stage: final_program_selection
strategy: post_construction_coach_quality
candidate_count: X
successful_candidate_count: Y
selected_source: template | exact_split | dynamic_fallback
selected_identifier: ...
selected_key: ...
comparison: [...]
reason_codes:
  - POST_CONSTRUCTION_PROGRAMS_COMPARED
  - BEST_VALID_PROGRAM_SELECTED
```

For each compared candidate, record only concise stable metrics:

- source
- identifier
- preconstruction rank
- final gate status
- volume fit
- priority fit
- body-analysis fit
- recovery fit
- coverage status
- duration fit
- warning count
- repair count
- substitution count
- final sort key or normalized comparison tuple

This trace is important for debugging and 100/200-profile audits.

---

# 5. `engine.py` — Main Orchestration Changes

## File to modify

`backend/app/workouts/program_engine/engine.py`

This is the main implementation file for the architectural change.

---

## 5.1 Import final selection functions

Add imports from:

`app.workouts.program_engine.program_selection`

Expected imports:

```python
ProgramCandidate
select_best_program
```

Optional helper:

```python
program_selection_trace
```

---

## 5.2 Add a common collection of successful primary candidates

Inside `generate_program(...)`, after eligibility/preparation and before candidate construction loops, introduce something equivalent to:

```python
successful_candidates: list[ProgramCandidate] = []
```

This collection should contain **fully constructed successful programs** from:

- professional/reference templates
- canonical exact-day splits

Dynamic fallbacks should normally be evaluated later only if necessary.

---

# 6. Template Candidate Flow Changes

## Current components to preserve

Keep:

- `select_template_reference_result(...)`
- `build_template_sessions(...)`
- `_reference_program(...)`
- template feasibility checks
- template survival evidence
- repair event collection

Do not weaken template core-slot eligibility or safety constraints.

## Change

Do not finalize the entire engine result immediately after choosing the best successful template.

Instead, each successful template should be converted into a `ProgramCandidate` and added to `successful_candidates`.

Recommended fields:

```text
source = "template"
identifier = ranking.template.slug
preconstruction_rank = ranking.rank
preconstruction_score = ranking.score.total
result = reference_result
repair_events = _post_construction_repair_events(reference_result)
```

---

## 6.1 Remove unsafe early pruning based only on template product score

Current template logic may stop evaluating remaining templates when their pre-construction product score cannot beat the current survival-adjusted key.

That pruning assumption becomes invalid once final selection depends on **actual generated coach quality**.

A lower pre-construction template score can still produce a better final program after real construction, volume repair, substitutions, recovery handling, and personalization.

### First implementation recommendation

For correctness, remove this pruning for the candidate set that is allowed to compete.

Evaluate all eligible template candidates, or introduce a safe explicit cap only after benchmark evidence.

Do not optimize latency before correctness is measured.

---

# 7. Exact Split Flow Changes

## Current behavior to replace

In `engine.py`, the exact split loop currently returns on first success.

Replace:

```python
if result.is_success:
    return result
```

with the conceptual behavior:

```python
if result.is_success:
    successful_candidates.append(
        ProgramCandidate(...)
    )
    continue
```

Recommended candidate metadata:

```text
source = "exact_split"
identifier = split type + stable day-focus signature
preconstruction_rank = attempt_index + 1
preconstruction_score = split.score
result = result
repair_events = _post_construction_repair_events(result)
```

All promising exact-day canonical candidates should have a chance to compete at final post-construction quality level.

---

# 8. Correct Split Attempt Trace Semantics

The current engine can mark later exact splits with:

`SPLIT_FALLBACK_AFTER_CONSTRUCTION_FAILURE`

This is no longer always correct.

After best-program comparison is introduced, a later split may be evaluated even though the previous split succeeded.

Update the logic so:

- Use `SPLIT_FALLBACK_AFTER_CONSTRUCTION_FAILURE` only when a previous relevant attempt actually failed.
- Use a new stable reason for successful-alternative comparison, for example:

`SPLIT_ALTERNATIVE_EVALUATED_FOR_QUALITY`

or

`SPLIT_CANDIDATE_EVALUATED_POST_CONSTRUCTION`

Do not mislabel quality comparison as failure recovery.

---

# 9. When to Select Among Primary Candidates

After:

- all eligible template candidates have been evaluated, and
- the bounded canonical exact-day split candidate set has been evaluated,

call:

```python
selected = select_best_program(successful_candidates)
```

If a selected primary candidate exists and passes the final selection policy, return that program with the new final selection trace appended.

---

# 10. Dynamic Fallback Policy

## Keep dynamic fallback as fallback

Do not immediately merge dynamic fallback candidates into the same unrestricted competition pool as curated templates and canonical splits.

Recommended runtime policy:

```text
1. Evaluate templates + canonical exact splits.
2. If one or more valid primary candidates exist:
      choose the best primary program.
3. If no valid primary candidate exists:
      evaluate dynamic fallback candidates.
4. Compare successful dynamic candidates with each other.
5. Return the best dynamic program.
```

### Optional future extension

After benchmarks, a rule could allow dynamic candidates to compete when the best primary candidate is valid but clearly poor on a defined coach-quality threshold.

Do **not** implement this threshold in the first version unless there is benchmark evidence.

Reason:

Dynamic fallback is intended as availability-aware recovery, not the normal preferred topology when a strong professional/canonical structure is available.

---

# 11. Dynamic Fallback Loop Changes

In `engine.py`, the dynamic fallback loop currently returns on first success.

Change it to:

```text
dynamic_successful_candidates = []

for fallback_split in dynamic_splits:
    build full program
    if success:
        append ProgramCandidate(source="dynamic_fallback", ...)
    else:
        keep failure trace

selected_dynamic = select_best_program(dynamic_successful_candidates)
return selected_dynamic if present
```

This ensures that even fallback generation chooses the best fallback, not the first fallback that happens to pass.

---

# 12. `coach_quality.py` — Keep as Metric Producer

## File

`backend/app/workouts/program_engine/coach_quality.py`

## Current role to preserve

This file already calculates useful post-construction metrics such as:

- template preservation
- explicit priority target satisfaction
- body-analysis target satisfaction
- volume fit
- duration fit
- coverage fit
- recovery fit
- substitution count
- constraint count
- hard validation status

Do not move candidate-selection policy into this file.

Architectural separation:

```text
coach_quality.py
    answers: "How good is this completed program?"

program_selection.py
    answers: "Which completed program should win?"
```

## Recommended small improvements

Only add small stable helpers if needed for selection, for example:

```python
metric_percentage(metric: Mapping[str, object]) -> float | None
```

or expose a normalized typed quality view.

Avoid duplicating the final selection policy here.

---

# 13. `template_survival.py` — Preserve, but Demote from Final Authority

## File

`backend/app/workouts/program_engine/template_survival.py`

Preserve:

- `CandidateSurvival`
- `assess_candidate_survival(...)`
- repair cost tracking
- repair event tracking
- hard reason tracking

These are valuable signals.

However:

`candidate_survival_sort_key(...)` should no longer be the final authority for choosing the overall winning program.

Repair cost should become one quality component in `program_selection.py`, below hard validity and actual final coach-quality dimensions.

A program that required a small legitimate repair but ends with clearly better volume, priority, coverage, and recovery should be able to beat a weaker unmodified candidate.

---

# 14. `template_selector.py` — Keep as Pre-Construction Ranker

## File

`backend/app/workouts/program_engine/template_selector.py`

Keep current responsibilities:

- hard template eligibility
- level/day compatibility
- core-slot resolvability
- pre-construction template scoring
- template feasibility estimation

Do not turn this file into the final selection layer.

Recommended conceptual rename in comments/traces only:

> template ranking = pre-construction ranking

not:

> final program quality decision

No major logic rewrite should be required for the first version.

---

# 15. `split_selector.py` — Keep as Candidate Ranker / Shortlist Builder

## File

`backend/app/workouts/program_engine/split_selector.py`

Keep:

- `rank_split_candidates(...)`
- `score_split_candidates(...)`
- candidate topology scoring
- availability-aware screening
- priority affinity
- duration/capacity pre-checks
- dynamic-layout ranking

This file should answer:

> “Which split structures should be attempted first?”

It should not answer:

> “Which fully built program is definitely best?”

The pre-construction rank remains useful as:

- evaluation order
- bounded-search prioritization
- final tie-breaker

but not as the primary final winner criterion.

---

# 16. `final_gate.py` — Do Not Weaken for Best-Program Selection

## File

`backend/app/workouts/program_engine/final_gate.py`

The best-program feature should not weaken or bypass the final gate.

The final gate remains the entrance requirement for final comparison.

Any candidate rejected by hard safety/validation/coverage/recovery/day-count constraints must not enter the final comparison pool.

If the separate under-duration-soft change is implemented, that should be handled consistently in duration policy/validation/final gate as its own bounded behavior change. The best-program selector must consume the final gate result, not redefine it.

---

# 17. Schemas — Avoid Unnecessary Public API Changes

## File to inspect

`backend/app/workouts/program_engine/schemas.py`

The new `ProgramCandidate` and quality selection types should preferably remain internal dataclasses inside `program_selection.py`.

Only modify `schemas.py` if there is a concrete need to expose a new persistent/public structure.

Do not enlarge the public engine schema unnecessarily.

---

# 18. New Unit Test File

## Create

`backend/tests/workouts/program_engine/test_program_selection.py`

This should unit-test final selection independently of full engine construction.

Required cases:

### Test 1 — invalid candidate can never win

Candidate A:

- high soft quality
- final result invalid/rejected

Candidate B:

- valid
- lower soft quality

Expected: Candidate B always wins.

### Test 2 — balanced candidate beats high-average candidate with one major weakness

Candidate A:

- volume 100
- priority 70
- body analysis 100
- recovery 100

Candidate B:

- volume 94
- priority 94
- body analysis 93
- recovery 100

Expected: Candidate B wins.

### Test 3 — fewer warnings wins when major quality is tied

### Test 4 — fewer repairs wins when quality is tied

### Test 5 — fewer substitutions wins when quality is tied

### Test 6 — better duration fit is only a soft tie-breaker

A slightly shorter valid program must be able to beat a worse program that perfectly fills the preferred duration.

### Test 7 — curated/template candidate wins true quality tie

If final quality is effectively equal, prefer the curated professional/template source over a generic split.

### Test 8 — deterministic tie-break

Same input must always select the same candidate.

---

# 19. New Integration Test File

## Create

`backend/tests/workouts/program_engine/test_best_program_selection_integration.py`

Required integration cases:

### Integration A — second exact split beats first successful exact split

Set up a request/catalog where:

- rank-1 exact split succeeds
- rank-2 exact split also succeeds
- rank-2 has materially better final coach quality

Expected:

The engine must return rank-2.

This is the most important regression test for removing first-success behavior.

### Integration B — professional template competes with canonical split

Both succeed.

Expected:

- actual final coach quality decides first
- curated source is only a tie-breaker

### Integration C — first template success is not automatically final winner

Two template candidates succeed.

A lower pre-construction-score template produces better final program quality.

Expected: lower pre-score but higher final-quality template wins.

### Integration D — dynamic fallback remains fallback

A strong primary candidate exists.

Expected: dynamic fallback is not needed.

### Integration E — best dynamic fallback is selected when all primary candidates fail

At least two dynamic candidates succeed.

Expected: choose the better final dynamic candidate, not the first successful one.

### Integration F — hard failure never enters comparison

Safety/volume/recovery invalid candidate must not win regardless of metrics.

---

# 20. Existing Tests to Review and Update

Search the test suite for assumptions that encode first-success behavior or specific first-ranked split/template identity.

Focus especially on tests referencing:

- `if result.is_success: return`
- exact selected split type
- first template selection
- fallback-after-failure reason codes
- post-construction template survival
- professional topology integration

Likely files to review include:

```text
backend/tests/workouts/program_engine/test_post_construction_feasibility.py
backend/tests/workouts/program_engine/test_professional_topology_integration.py
backend/tests/workouts/program_engine/test_template_reference.py
backend/tests/workouts/program_engine/test_golden_scenarios.py
backend/tests/workouts/program_engine/test_regression_profiles.py
backend/tests/workouts/program_engine/test_workout_engine_reference_profiles.py
```

Do not change assertions merely to make tests pass. Update only tests whose expected behavior intentionally changes from first-success to best-final-quality.

---

# 21. Audit / Evaluation Reporting Changes

## Files to modify after core implementation is stable

```text
backend/scripts/generate_100_profiles_audit_report.py
backend/scripts/generate_200_profiles_eval.py
```

Add observability fields such as:

```text
selection_strategy
primary_candidates_evaluated
primary_candidates_successful
dynamic_candidates_evaluated
dynamic_candidates_successful
selected_candidate_source
selected_candidate_identifier
selected_candidate_preconstruction_rank
selected_candidate_preconstruction_score
selected_candidate_repair_count
selected_candidate_warning_count
selected_candidate_substitution_count
selected_candidate_volume_fit
selected_candidate_priority_fit
selected_candidate_body_analysis_fit
selected_candidate_recovery_fit
selected_candidate_duration_fit
```

Also record a compact top-N comparison when useful.

This is necessary to answer:

> Why did the engine choose this program instead of the other valid ones?

---

# 22. Search Bound / Performance Policy

Comparing more candidates improves final choice but increases runtime.

The first implementation should prioritize correctness and measurement.

Recommended staged strategy:

## Phase 1

- evaluate all eligible template candidates
- evaluate all canonical exact-day splits for the requested day count
- compare all successful primary candidates
- only evaluate dynamic fallbacks when primary candidates fail

Measure runtime.

## Phase 2, only if needed

If latency is excessive, introduce a benchmark-backed bounded search policy.

Examples:

- top 3–5 canonical exact splits
- top N eligible templates
- stop only when a mathematically safe upper bound proves remaining candidates cannot win

Do not restore unsafe pruning based only on pre-construction score.

---

# 23. Recommended Final Selection Ordering in More Detail

The exact tuple should be reviewed in Plan Mode before implementation, but the recommended structure is conceptually:

```python
(
    hard_validity,
    coverage_quality,
    worst_major_quality_dimension,
    volume_fit,
    priority_fit,
    body_analysis_fit,
    recovery_fit,
    -constraint_count,
    -repair_count,
    -substitution_count,
    duration_fit,
    curated_source_preference,
    preconstruction_score,
    -preconstruction_rank,
    deterministic_identifier,
)
```

Notes:

- `hard_validity` should effectively be mandatory, not merely weighted.
- N/A priority/body-analysis metrics must not be converted to zero.
- Coverage may need normalization from status to an ordinal value.
- Duration should remain below core physiological/structural quality dimensions.
- Curated-source preference must be a tie-breaker, not a quality override.

---

# 24. Optional Better Design: Typed `ProgramQualityView`

If Plan Mode concludes the raw `coach_quality` dictionary is too fragile for selection logic, create a small internal typed representation in `program_selection.py`:

```python
@dataclass(frozen=True, slots=True)
class ProgramQualityView:
    volume_fit: float | None
    priority_fit: float | None
    body_analysis_fit: float | None
    recovery_fit: float | None
    duration_fit: float | None
    coverage_rank: int
    warning_count: int
    repair_count: int
    substitution_count: int
```

This would make selection policy easier to test and prevent repeated dictionary parsing.

Do not create a second source of truth for metrics. It should only normalize already-computed engine metrics.

---

# 25. Relationship to the >90% Success Goal

This architectural change primarily improves **quality of successful programs**, not raw success rate by itself.

The engine already tries later split candidates when earlier ones fail, so replacing first-success with best-success will not alone eliminate most construction failures.

The >90% success target should be achieved by combining this selection redesign with constraint corrections that do not reduce program quality.

Most important complementary work:

1. Make under-preferred duration soft rather than a hard failure.
2. Do not add sets/exercises only to fill a clock target.
3. Preserve hard minimum exercise-count guardrails for now.
4. Preserve safety, injury, equipment, semantic duplicate, hard volume, required slots, and recovery constraints.
5. Centralize hard/repairable/soft constraint semantics so validation, repair, recovery, and final gate do not disagree.
6. Improve capacity estimation per focus/session if failure audits show pre-construction feasibility is still inaccurate.

The intended combined result is:

> Higher construction success without lowering hard standards, plus stricter competition among successful programs.

In other words:

> **More freedom to construct; more rigor when selecting.**

---

# 26. Implementation Order

Use this sequence to reduce risk.

## Stage 0 — Baseline

Before changing final selection:

- freeze the current 100-profile audit seed/profile set
- save current success/failure distribution
- save current selected split/template distribution
- save coach-quality metrics for successful programs
- record runtime

This gives a true before/after comparison.

## Stage 1 — Add selection policy unit only

Create:

```text
backend/app/workouts/program_engine/program_selection.py
backend/tests/workouts/program_engine/test_program_selection.py
```

Implement and test selection ranking using synthetic candidate results.

Do not change `engine.py` yet.

## Stage 2 — Integrate exact split comparison

Modify `engine.py` so exact-day splits no longer return on first success.

Collect all successful exact split programs and choose the best using `program_selection.py`.

Run engine tests.

This is the smallest real end-to-end proof of the new architecture.

## Stage 3 — Integrate template candidates into the same primary selection layer

Remove template final-return behavior.

Convert successful templates to `ProgramCandidate` objects.

Allow templates and canonical exact splits to compete on post-construction quality.

Remove product-score-only early pruning that can hide a better final-quality program.

Run template/professional topology tests.

## Stage 4 — Fix trace semantics

Correct failure/fallback reason codes that became inaccurate after evaluating successful alternatives.

Add final selection decision trace.

## Stage 5 — Improve dynamic fallback selection

Keep dynamic fallback as fallback.

When needed, evaluate multiple dynamic successful candidates and select the best instead of returning the first success.

## Stage 6 — Add full integration tests

Create:

`backend/tests/workouts/program_engine/test_best_program_selection_integration.py`

Cover exact splits, templates, dynamic fallbacks, hard failures, and tie behavior.

## Stage 7 — Audit/report observability

Modify:

```text
backend/scripts/generate_100_profiles_audit_report.py
backend/scripts/generate_200_profiles_eval.py
```

Expose candidate comparison/selection metrics.

## Stage 8 — Benchmark

Run:

- program-engine unit/integration tests
- frozen 100-profile audit
- 200-profile stratified evaluation
- runtime comparison

Compare:

- supported-profile success rate
- unsafe program count
- hard validation failures
- average/median coach-quality dimensions
- selected program quality vs first-success baseline
- warning/repair/substitution counts
- runtime cost

---

# 27. Acceptance Criteria

The redesign is accepted only if all of the following are true.

## Functional

- The engine no longer returns the first successful exact split by default.
- Multiple successful primary candidates can be compared.
- A lower pre-construction-ranked candidate can win when its final program is better.
- Dynamic fallback selects its best successful candidate when fallback is necessary.
- Final selection is deterministic.

## Quality

- Rejected hard-invalid candidates can never win.
- Safety and injury filtering are unchanged or stronger.
- Hard session/weekly volume limits are unchanged.
- Required slots and semantic redundancy protections remain enforced.
- Recovery safety remains enforced.
- Duration fit cannot override core program quality.
- Small legitimate repairs do not automatically disqualify an otherwise superior program.

## Observability

- Decision trace clearly explains which candidates were compared.
- The trace identifies the selected candidate and its source.
- Audit tools can report why the selected program won.

## Performance

- Runtime increase is measured.
- No premature optimization is added without benchmark evidence.

## Success-rate program goal

After complementary under-duration-soft work and final-selection redesign:

- target supported-profile generation success rate: **>90%**
- preferred target: **>=95%**
- unsafe output rate: **0%**
- unexplained thin/invalid program rate: **0%**
- no reduction in hard safety/volume/recovery standards

---

# 28. Files Summary

## New files

```text
backend/app/workouts/program_engine/program_selection.py
backend/tests/workouts/program_engine/test_program_selection.py
backend/tests/workouts/program_engine/test_best_program_selection_integration.py
```

## Main files to modify

```text
backend/app/workouts/program_engine/engine.py
backend/app/workouts/program_engine/coach_quality.py          # small helper/normalization only if needed
backend/app/workouts/program_engine/template_survival.py      # keep evidence; demote final authority
backend/app/workouts/program_engine/template_selector.py      # likely comments/trace only
backend/app/workouts/program_engine/split_selector.py         # likely no major behavior change
```

## Files to inspect but avoid changing unless required

```text
backend/app/workouts/program_engine/final_gate.py
backend/app/workouts/program_engine/schemas.py
backend/app/workouts/program_engine/validation.py
backend/app/workouts/program_engine/constraint_classification.py
```

The best-program selection feature must consume these contracts rather than duplicate them.

## Audit files to modify after core behavior is stable

```text
backend/scripts/generate_100_profiles_audit_report.py
backend/scripts/generate_200_profiles_eval.py
```

## Existing tests to review

```text
backend/tests/workouts/program_engine/test_post_construction_feasibility.py
backend/tests/workouts/program_engine/test_professional_topology_integration.py
backend/tests/workouts/program_engine/test_template_reference.py
backend/tests/workouts/program_engine/test_golden_scenarios.py
backend/tests/workouts/program_engine/test_regression_profiles.py
backend/tests/workouts/program_engine/test_workout_engine_reference_profiles.py
```

---

# 29. Non-Goals

Do not use this task as an excuse to rewrite unrelated engine subsystems.

Do not change:

- exercise safety rules
- injury filtering
- equipment eligibility
- movement/semantic duplicate rules
- volume science
- set prescription logic
- progression model
- recovery physiology
- template data
- user-facing API shape unless required

The scope is final candidate comparison and orchestration.

---

# 30. Final Target Architecture

```text
User Request
    ↓
Normalize + Safety + Eligibility
    ↓
Pre-construction candidate ranking
    ├── Professional / Reference Templates
    └── Canonical Exact-Day Splits
             ↓
       Full construction
             ↓
     Repair / Personalization
             ↓
        Validation
             ↓
        Final Gate
             ↓
   accepted candidates only
             ↓
     Program Selection
       ├── balanced quality
       ├── volume fit
       ├── priority fit
       ├── body-analysis fit
       ├── recovery
       ├── warning burden
       ├── repair burden
       ├── substitutions
       └── duration fit
             ↓
       BEST PRIMARY PROGRAM

If no primary program succeeds:

Dynamic exact-day fallbacks
             ↓
       Full construction
             ↓
        Final Gate
             ↓
      Program Selection
             ↓
       BEST FALLBACK PROGRAM
```

The engine should no longer think:

> “I found a program that passes; return it.”

It should think:

> “I found multiple programs that pass. Now choose the one a good coach would prefer.”

