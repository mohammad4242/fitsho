# Fitsho Luna Max Master Roadmap
## Best-Program Selection + Supported-Profile Success-Rate Improvement

This document is the execution roadmap for Luna Max in:

`/home/mohammad/project/fitsho`

The roadmap is intentionally organized as **one master task with two hard-separated phases**:

- **PHASE A — Best Program Selection**
  - Make the engine select the **best fully constructed valid program**, not the first successful program.
  - Improve post-construction quality evidence, deterministic comparison, traceability, and auditing.
- **PHASE B — Success-Rate Repair**
  - Only after Phase A is complete and re-audited, fix the remaining dominant supported-profile failures.
  - Do not preemptively weaken scientific, safety, structural, or validation rules.

The primary architectural goal is:

> Build several realistic valid candidates, reject hard-invalid candidates, compare the surviving complete programs using real post-construction coaching quality, and return the best program rather than the first one that happens to succeed.

The product-quality goal is:

> Raise supported-profile generation success above 90%, preferably to at least 95%, without producing thin, repetitive, unsafe, semantically poor, or scientifically weaker programs.

---

# 0. EXECUTION CONTRACT FOR LUNA MAX

This roadmap is authorization for full execution.

Start at Stage 0 and continue through every applicable stage until completion.

Do **not** stop to ask for approval before editing files, running tests, committing, pushing, moving to the next stage, or applying changes already defined by this roadmap.

Ask the user **only if there is a real ambiguity that cannot be resolved from the repository, tests, current behavior, or this roadmap and that blocks a technically correct decision**.

Otherwise, make the best evidence-based technical decision and continue.

## Five mandatory stage-isolation rules

### Rule 1 — One stage means one problem

**Work on exactly one stage at a time. Do not implement changes that belong to a future stage, even if you notice an obvious future improvement while working on the current stage.**

If you discover a future-stage issue, record it in the stage report and continue only with the current stage.

### Rule 2 — Respect the declared file scope

**Only modify files explicitly listed for the current stage unless a compilation, import, type-check, or test dependency makes one additional file strictly necessary.**

If one additional file is required:

- make the smallest possible change;
- explain why it was strictly necessary;
- do not use it as an excuse to begin future-stage work.

### Rule 3 — Verification gate before progression

**Do not begin the next stage until the current stage's tests and verification gates pass.**

A failed verification is a problem in the current stage until proven otherwise.

If the failure is pre-existing and unrelated:

- collect evidence;
- do not “fix” unrelated code;
- report the failure separately;
- continue only when the current stage can be demonstrated correct.

### Rule 4 — Hard checkpoint between Phase A and Phase B

**After Stage 6, run the mandatory Phase A checkpoint audits before touching any Phase B code.**

The checkpoint must produce:

- current supported success rate;
- selected-vs-first-valid quality comparison;
- failure taxonomy;
- deterministic-repeat results;
- p50/p95 latency;
- candidate counts;
- warning/repair/substitution burden.

Use the checkpoint results to determine which Phase B stages are actually needed.

### Rule 5 — Never preemptively solve future failures

**Do not implement Stage 7, Stage 8, or Stage 9 fixes while working on Phase A.**

Likewise, inside Phase B:

- do not implement the count-policy repair while fixing semantic opener conflicts;
- do not implement beam search before proving a greedy required-slot dead-end;
- do not weaken any hard rule merely to increase the benchmark success percentage.

## Additional execution rules

- Work carefully and deliberately. Do not rush.
- Do not use subagents.
- Use TDD for each stage.
- Keep changes focused and deterministic.
- Do not touch unrelated user work or unrelated untracked files.
- Never run `git add -A` or `git add .`.
- Stage only the files belonging to the current stage.
- After each completed stage, create one focused Conventional Commit.
- Push the current branch if a remote is configured and push is available.
- Do not add fake exercises, fake evidence, fake quality scores, or fake benchmark exclusions.
- Do not weaken injury, safety, equipment, hard-volume, semantic-duplicate, recovery, prescription, required-slot, or exact-day rules to make the audit look better.
- If a real exercise-catalog gap is proven, report it precisely. Do not invent data to hide it.
- If a Phase B stage is not needed according to the measured failure taxonomy, skip that stage with evidence and continue to the next applicable stage.

## Stage report format

After every stage, report exactly:

```text
Changed:
Verified:
Git:
Next:
```

Under `Git:`:

- show the intended commit message;
- commit without requesting separate approval;
- push if available;
- report the real commit/push result.

---

# 1. CURRENT ARCHITECTURAL ASSESSMENT

The central architectural direction is correct:

> Candidate proposal, candidate construction, candidate validation, and final candidate selection must be separate concerns.

The current engine already contains useful foundations, but they are not consistently used for final selection.

## What is already conceptually correct

- Template and split pre-ranking is useful.
- Pre-construction ranking should propose or shortlist candidates, not determine the final winner.
- Templates and canonical splits should compete in one bounded primary pool after full construction.
- Dynamic fallback should remain fallback-only.
- Hard-invalid candidates must never enter quality competition.
- A simple weighted-average quality score is not sufficient.
- Template survival evidence is useful for feasibility/trace, but must not be the final decision-maker.
- Final selection must be deterministic and explainable.
- Final quality must be judged from the fully constructed program, not only from template/split metadata.

## Important differences between the earlier roadmap and the current repository

The implementation must follow the current repository, not assumptions from older plans.

Current known state:

- The lower session-duration bound has already been softened in recent work. Do not re-implement that change.
- `engine.py` still returns the first successful exact split and the first successful dynamic fallback.
- Templates are evaluated more deeply than splits, but:
  - they are still selected primarily through `candidate_survival_sort_key(...)`;
  - product-score-based pruning can stop evaluation early;
  - a successful template can prevent canonical splits from competing.
- Existing `coach_quality.py` is useful but not strong enough to be the final selector:
  - some volume semantics differ from validation semantics;
  - priority quality does not fully represent direct/effective/frequency requirements;
  - recovery is too binary for post-construction comparison;
  - non-full-body coverage is often not normalized into a comparable selection metric;
  - warnings are counted without enough semantic burden classification;
  - substitution accounting is template-centric.
- `_post_construction_repair_events(...)` relies too much on trace-text/substrings instead of a stable allowlisted event contract.
- `CoachQualityMetricsResponse` in the Coach Review layer uses `extra="forbid"`. Internal metric expansion can therefore break or hide the public Coach Review projection unless the projection is explicitly filtered before response-schema validation.
- Best-program selection alone will probably improve **quality** much more than **success rate**.
- The remaining success-rate failures must be measured after Phase A before they are repaired.
- Old historical Phase 11 benchmark snapshots are not valid substitutes for a fresh current baseline.

## Current baseline facts that Luna must re-verify at Stage 0

Expected repository state from the planning pass:

- branch: `main`
- known planning-time HEAD: `0da6cbf`
- `origin/main` was aligned with that HEAD
- many user-owned untracked files exist and must not be touched
- a recent full Program Engine run reported `1286 passed`
- the most recent planning-time commit changed only the audit script; Luna must still rebuild the baseline from the current HEAD
- the most recent planning-time 100-profile audit reported approximately **49 successes out of 98 supported profiles**, i.e. roughly 50% supported success, not 90%
- dominant recent failure families included:
  - `SESSION_EXERCISE_COUNT_OUT_OF_RANGE`
  - `REQUIRED_SLOT_HARD_IMPOSSIBILITY`
  - `SEMANTIC_OPENER_CONFLICT`

These values are **not trusted as runtime truth** until Stage 0 re-runs the baseline.

---

# 2. LOCKED ARCHITECTURAL DECISIONS

These decisions define the architecture for Phase A.

## 2.1 Primary candidate pool

Chosen architecture:

**Unified bounded primary pool + separate dynamic fallback**

Primary pool:

- eligible templates;
- canonical exact-day splits.

Dynamic candidates:

- evaluated only if no valid primary candidate survives.

Do not put dynamic fallback into the same primary competition.

## 2.2 Selection strategy

Chosen architecture:

**Lexicographic max-min post-construction quality selection**

Do not use a single weighted average.

The selector should prefer a balanced program with no severe weak dimension over a program with a high average but one large coaching weakness.

Required example:

```text
Program A critical dimensions: 100, 70, 100, 100
Program B critical dimensions: 94, 94, 93, 100
```

Program B must win because its weakest applicable coaching dimension is much stronger.

## 2.3 Session-search policy

Chosen architecture:

**Bounded beam search only after a greedy dead-end is empirically proven**

Do not create `session_search.py` preemptively.

First prove that:

- a required slot had a valid safe candidate available;
- greedy selection or ordering consumed/blocked the viable solution;
- a bounded alternative ordering could have completed all required slots.

Only then implement bounded search.

---

# 3. FINAL TARGET ARCHITECTURE

```text
Request
  ↓
Normalization / Safety / Eligibility
  ↓
Immutable reusable request-level evidence
  ├── eligible catalog
  ├── rejected catalog evidence
  └── session capacity
  ↓
Pre-construction ranking
  ├── up to MAX_TEMPLATE_CANDIDATES eligible templates
  └── up to MAX_CANONICAL_CANDIDATES canonical exact-day splits
  ↓
Fully and independently construct every shortlisted primary candidate
  ↓
Repair / Prescription / Volume / Recovery
  ↓
Validation
  ↓
Final Gate
  ↓
Reject hard-invalid or evidence-incomplete candidates
  ↓
Lexicographic post-construction selection
  ↓
BEST PRIMARY PROGRAM

Only if no valid primary candidate survives:

Dynamic fallback ranking
  ↓
Evaluate first bounded batch
  ↓
If no valid candidate survives, evaluate second bounded batch
  ↓
Lexicographic post-construction selection
  ↓
BEST DYNAMIC FALLBACK
```

## Candidate-cap constants

Do not scatter magic numbers throughout the engine.

Use named constants, initially:

```text
MAX_TEMPLATE_CANDIDATES = 6
MAX_CANONICAL_CANDIDATES = 6
MAX_DYNAMIC_CANDIDATES = 12
DYNAMIC_BATCH_SIZE = 6
```

These are bounded defaults, not scientific truths.

With the initial caps:

- maximum constructed primary candidates: `12`
- maximum constructed dynamic candidates: `12`
- maximum constructed candidates in the worst-case request: `24`

The final performance audit must verify whether these bounds are acceptable.

## Construction rules

- Candidate construction remains sequential in this version.
- Candidate construction must be deterministic.
- Do not add parallel construction in this roadmap.
- Reuse immutable request-level calculations where safe:
  - normalization;
  - safety input;
  - eligibility;
  - rejected-candidate evidence;
  - session capacity.
- Candidate-local mutable state must never leak between candidates.
- No product-score pruning after a candidate has entered the Phase A shortlist.
- Exact duplicate candidate identifiers within the same family may be de-duplicated before construction.
- Do not compare raw template product scores against canonical split scores.

---

# 4. FINAL PROGRAM-SELECTION CONTRACT

## 4.1 New file

Create:

`backend/app/workouts/program_engine/program_selection.py`

Internal types:

- `CandidateSource`
  - `TEMPLATE`
  - `CANONICAL_SPLIT`
  - `DYNAMIC_FALLBACK`
- `ProgramCandidate`
- `ProgramQualityView`
- `CandidateComparison`
- `ProgramSelectionDecision`

## 4.2 `ProgramCandidate` minimum data

A candidate should carry at least:

- source;
- stable identifier;
- preconstruction rank;
- preconstruction score for trace only;
- `ProgramGenerationResult`;
- exact repair-event tokens;
- actual substitution count;
- limited source metadata;
- no user-identifying or medical data in selection trace metadata.

## 4.3 Admission into final comparison

A candidate is comparable only if all required validity/evidence conditions hold:

- `result.is_success` is true;
- `result.program` exists;
- validation has no hard error;
- final `final_quality_gate` trace/evidence exists;
- final gate is `accepted` or `accepted_with_constraints`;
- `coach_quality_v2` selection evidence is complete;
- no known hard constraint remains unresolved.

### Unknown warnings / reason codes

Do **not** blindly reject every unknown informational trace token.

Use a strict distinction:

- unknown **constraint-bearing final warning/reason** that could affect validity or selection admission:
  - exclude the candidate;
  - record `PROGRAM_SELECTION_UNKNOWN_CONSTRAINT`.
- unknown **informational/observability-only trace token**:
  - do not use it in quality ranking;
  - record a diagnostic;
  - do not automatically turn an otherwise valid program into a hard failure.

If selection-critical quality evidence is missing:

- exclude the candidate;
- record `PROGRAM_SELECTION_EVIDENCE_MISSING`.

If all candidates are excluded for evidence problems:

- fail closed;
- do not return the first successful candidate as an emergency fallback.

## 4.4 Lexicographic comparison order

Hard validity is an admission condition, not a score.

Compare admitted candidates in this order:

1. coverage state:
   - satisfied;
   - proven constrained.
2. `critical_floor`:
   - weakest applicable critical coaching dimension.
3. sorted critical-dimension vector from weakest to strongest.
4. explicit user priority satisfaction, if applicable.
5. Body Analysis priority satisfaction, if applicable.
6. volume floor.
7. volume median.
8. coverage percentage.
9. recovery margin.
10. semantic degradation burden.
11. warning burden:
    - repairable burden;
    - soft burden.
12. repair burden:
    - structural;
    - workload;
    - scheduling;
    - total.
13. actual substitution burden.
14. duration fit.
15. curated-template preference only in a true quality tie.
16. preconstruction rank only within the same candidate family.
17. stable identifier as final deterministic tie-break.

## 4.5 Applicability rule

`not_applicable` must never be coerced to zero.

Applicability comes from the request and the actual policy contract.

For a given request, the same dimension-applicability rules must apply to all candidates.

Example:

If direct-volume minimum is not applicable to a particular priority muscle, do not compute:

```text
direct = 0
effective = 100
frequency = 100
priority = min(...) = 0
```

Instead, calculate the minimum only across the dimensions that are actually applicable.

---

# 5. FILES TO CREATE

## Always create

```text
backend/app/workouts/program_engine/program_selection.py
backend/app/workouts/program_engine/repair_observability.py
backend/app/workouts/program_engine/session_feasibility.py

backend/tests/workouts/program_engine/test_program_selection.py
backend/tests/workouts/program_engine/test_best_program_selection_integration.py
backend/tests/workouts/program_engine/test_session_feasibility.py

backend/scripts/program_engine_audit_support.py
backend/scripts/audit_supported_profile_catalog.py
backend/tests/workouts/program_engine/test_program_engine_audit_support.py
```

Important stage-isolation clarification:

`session_feasibility.py` is part of the master architecture, but its behavior-changing count-policy integration belongs to **Phase B / Stage 8**.

Do not wire the future Stage 8 behavior into Phase A.

## Create only if Stage 9 proves greedy dead-end

```text
backend/app/workouts/program_engine/session_search.py
backend/tests/workouts/program_engine/test_session_search.py
```

If the evidence does not prove greedy dead-end, do not create these two files.

---

# 6. FILES / FUNCTIONS THAT MAY BE MODIFIED

## Selection and orchestration

### `backend/app/workouts/program_engine/engine.py`

Target areas:

- `generate_program(...)`
- template-candidate loop
- exact-day split loop
- dynamic-fallback loop
- `_post_construction_repair_events(...)`
- `_finalize_program(...)`
- `_volume_range_metric(...)`
- success-result trace append helper(s)

Required Phase A behavior:

- successful template does not immediately return;
- successful exact split does not immediately return;
- successful dynamic fallback does not immediately return;
- product-score early pruning is removed after shortlist entry;
- templates and canonical splits share one primary post-construction pool;
- dynamic fallback remains separate;
- failure evidence from losing candidates is preserved for audit but is not incorrectly attached as if it were a failure of the winning successful candidate;
- final selection trace is appended only to the winner;
- `actual_constraint_volume` is added to volume evidence.

## Post-construction quality

### `backend/app/workouts/program_engine/coach_quality.py`

Target functions:

- `build_coach_quality_metrics(...)`
- `_target_satisfaction(...)`
- `_volume_fit(...)`
- recovery quality helper
- duration fit
- coverage normalization
- substitution extraction

Preserve existing public-compatible metrics where needed, and add an internal v2 contract:

```text
schema_version = coach_quality_v2

selection_quality:
  critical_dimensions
  coverage_percentage
  volume_floor
  volume_median
  explicit_priority_floor
  body_analysis_priority_floor
  recovery_margin
  duration_fit
  semantic_degradation
```

Rules:

- use `actual_constraint_volume` for validation-aligned volume quality;
- priority muscle quality should use the weakest **applicable** direct/effective/frequency ratio;
- keep explicit priority and Body Analysis priority separate;
- recovery quality should represent actual recovery margin, not only pass/fail;
- normalize comparable coverage evidence for non-full-body splits from the actual volume/coverage evidence already produced by the engine;
- preserve full-body hard coverage semantics;
- duration remains a soft quality tie-break;
- no average may hide one severely weak critical dimension.

## Repair observability

### `backend/app/workouts/program_engine/repair_observability.py`

Implement stable exact event collection.

Requirements:

- use explicit stage/reason-code allowlists;
- remove reliance on loose substring matching such as `ADDED` or `REPLACED`;
- categorize repair burden into:
  - structural;
  - workload;
  - scheduling.
- normal informational trace events are not repairs;
- actual template substitutions are tracked separately;
- candidate alternatives or substitution options are not counted as actual substitutions.

### `backend/app/workouts/program_engine/template_survival.py`

Preserve:

- `CandidateSurvival`;
- feasibility evidence;
- repair evidence;
- hard-reason classification.

`candidate_survival_sort_key(...)` may remain for template-local trace/analysis, but it must not select the final program winner.

Do not change safety classification merely for selection.

## Constraint classification

### `backend/app/workouts/program_engine/constraint_classification.py`

Requirements:

- every final constraint-bearing warning/reason code relevant to selection gets explicit classification;
- selection-critical unknown constraints fail closed;
- add new selection/constrained-session reason codes when introduced;
- `SESSION_EXERCISE_COUNT_OUT_OF_RANGE` remains hard after repair exhaustion unless Stage 8 has complete constrained-session evidence;
- valid constrained-session evidence is a soft/constraint state, not a hard failure.

## Recovery quality

### `backend/app/workouts/program_engine/recovery.py`

- add one shared helper that maps `RecoveryAssessment` into recovery-quality evidence;
- hard recovery conflict still rejects the candidate;
- repairable recovery conflict must not receive a perfect quality score;
- validation/final gate should continue using the existing authoritative recovery contract.

## Semantic opener — Phase B only

### `backend/app/workouts/program_engine/session_structure.py`

Only modify in Stage 7, if the Phase A checkpoint shows semantic opener remains a material supported-profile failure.

Target functions:

- `_semantic_order_rank(...)`
- `_is_required_semantic_opener(...)`
- `_semantic_ordering_errors(...)`

Desired behavior when both push-up and pull-up appear in the same session:

- only one is the required opener;
- the other exercise remains in the session if otherwise valid;
- opener selection order:
  1. true strength-primary requirement;
  2. explicit chest/back priority;
  3. original construction order;
  4. stable exercise identifier.
- the non-opener follows normal semantic ordering;
- semantic duplicate protection remains unchanged.

## Session-count feasibility — Phase B only

### `backend/app/workouts/program_engine/session_feasibility.py`

Create a single evidence source for justified constrained session counts.

Evidence should include at least:

- day index;
- actual MAIN count;
- preferred minimum;
- absolute hard minimum;
- required-slot satisfaction;
- number of candidate exercises examined;
- reasons additional candidates were rejected;
- duration-capacity blockers;
- hard-volume blockers;
- recovery blockers;
- semantic/coherence blockers;
- stable reason codes.

### Count policy target

Preserve the preferred count policy, but allow a lower count only with complete evidence.

- 30-minute session:
  - preserve current `3–4 MAIN` contract.
- 40/45-minute session:
  - preferred minimum remains current policy;
  - absolute minimum may be `3`, only with complete evidence.
- 60 minutes or longer:
  - preferred minimum remains current policy;
  - absolute minimum may be `4`, only with complete evidence.
- below the absolute minimum is always hard failure;
- Core, cardio, warm-up do not count as MAIN;
- if a safe, useful, non-redundant, feasible exercise can still be added, constrained-count evidence is invalid;
- accepted constrained-count program becomes `accepted_with_constraints` and is penalized in final quality selection;
- never add useless exercises or sets merely to fill time or count.

### Consumers that must use the centralized policy in Stage 8

```text
backend/app/workouts/program_engine/duration_policy.py
backend/app/workouts/program_engine/duration_capacity.py
backend/app/workouts/program_engine/session_builder.py
backend/app/workouts/program_engine/session_duration.py
backend/app/workouts/program_engine/validation.py
backend/app/workouts/program_engine/final_gate.py
```

Do not duplicate count logic across these files.

## Coach Review compatibility

### `backend/app/workout_reviews/coach_quality.py`

Before public response-schema validation:

- project/extract only public fields that the API schema defines;
- internal selection metrics must not cause the entire Coach Review projection to become `None`.

### `backend/app/workout_reviews/schemas.py`

Modify only if a public schema version or public field genuinely needs to change.

Internal `selection_quality` does not need to become public API data.

## Release versions — final release stage only

### `backend/app/workouts/program_engine/rulesets/resistance_training_v1.py`

Only after final acceptance:

```text
engine_version:
program_engine_v1 → program_engine_v2

ruleset version:
resistance_training_v5 → resistance_training_v6
```

Rename the corresponding targeted test:

```text
backend/tests/workouts/program_engine/test_ruleset_version_v5.py
→
backend/tests/workouts/program_engine/test_ruleset_version_v6.py
```

Do not migrate or rewrite old persisted programs.

New generation signature should invalidate only future generation reuse where appropriate.

## Files that should not be redesigned for selection

Do not rewrite these for Phase A:

```text
backend/app/workouts/program_engine/split_selector.py
backend/app/workouts/program_engine/template_selector.py
backend/app/workouts/program_engine/volume_planner.py
backend/app/workouts/program_engine/volume_repair.py
backend/app/workouts/program_engine/schemas.py
```

Only make a small direct change if a concrete test proves it is required.

---

# 7. MASTER EXECUTION ORDER

# PHASE A — BEST PROGRAM SELECTION

Phase A has one job:

> Make Fitsho construct and compare multiple valid primary candidates and select the best fully constructed program using reliable post-construction quality evidence.

Do not repair semantic opener, count policy, or greedy required-slot search during Phase A.

---

## Stage 0 — Freeze and baseline

Do not modify tracked files.

### Tasks

1. Read `AGENTS.md` completely.
2. Record:
   - `git status --short`
   - current branch
   - current HEAD
   - remotes
3. Preserve all current user-owned untracked files.
4. Run the current Program Engine test suite.
5. Run the current 100-profile audit with its existing seed.
6. Run the independent Phase 11.6 150-supported-profile benchmark if it is still valid/currently executable.
7. Run the current 200-profile evaluation.
8. Record p50 and p95 generation latency.
9. Record:
   - exercise count;
   - template count;
   - benchmark-input hash/fingerprint.
10. For every currently successful profile, capture:
    - first successful candidate;
    - source and identifier;
    - split;
    - current quality metrics;
    - warnings;
    - repairs;
    - runtime.
11. Store artifacts only under:

`backend/var/audits/best-program-selection/`

Do not commit audit artifacts.

### Gate

- If the current Program Engine baseline suite is not green, **do not begin Stage 1 implementation**.
- Treat this as a verification blocker, not as a request for routine approval.
- Separate baseline failures from later regressions with evidence and report the blocker precisely.

### Commit

None.

---

## Stage 1 — Pure deterministic program selector

### Files

```text
backend/app/workouts/program_engine/program_selection.py
backend/tests/workouts/program_engine/test_program_selection.py
```

### Order

1. Write failing selector tests first.
2. Implement only:
   - pure internal types;
   - admission;
   - quality-view normalization;
   - lexicographic comparison;
   - deterministic selection.
3. Do not modify `engine.py` yet.

### Required tests

- hard-invalid candidate never wins;
- balanced candidate beats a high-average candidate with one severe weak dimension;
- N/A is not converted to zero;
- selection-critical unknown constraint excludes the candidate;
- informational unknown trace token does not automatically create a hard failure;
- fewer warnings wins only after stronger quality dimensions tie;
- fewer repairs wins only after stronger quality dimensions tie;
- fewer actual substitutions wins only after stronger quality dimensions tie;
- duration is a soft late tie-break;
- template preference applies only in a true quality tie;
- result is independent of input list order;
- stable identifier resolves the final deterministic tie.

### Gate

- new unit tests;
- Ruff;
- mypy for the new file;
- `git diff --check`.

### Commit

`feat(program-engine): add deterministic best-program selector`

---

## Stage 2 — Coach Quality v2 + exact repair evidence

### Files

```text
backend/app/workouts/program_engine/coach_quality.py
backend/app/workouts/program_engine/repair_observability.py
backend/app/workouts/program_engine/recovery.py
backend/app/workouts/program_engine/constraint_classification.py
backend/app/workouts/program_engine/engine.py
backend/app/workout_reviews/coach_quality.py

backend/tests/workouts/program_engine/test_coach_quality_regressions.py
backend/tests/workouts/program_engine/test_validation_quality.py
backend/tests/workouts/program_engine/test_recovery_exposure_load.py
backend/tests/workouts/program_engine/test_constraint_classification.py
backend/tests/workout_reviews/test_coach_quality_projection.py
```

### Order

1. Add failing direct-vs-effective volume mismatch test.
2. Add direct/effective/frequency priority applicability tests.
3. Add recovery-margin test.
4. Add non-full-body coverage-quality test.
5. Add exact repair-code collection tests.
6. Add internal-extra-metrics public Coach Review projection test.
7. Add `actual_constraint_volume` in `_volume_range_metric(...)`.
8. Build `coach_quality_v2`.
9. Replace substring-based repair parsing with explicit event collection.
10. Keep public Coach Review projection backward-compatible.

### Gate

- quality/recovery/classification/review tests;
- full Program Engine suite;
- Ruff;
- mypy;
- diff check.

### Commit

`feat(program-engine): add robust post-construction quality evidence`

---

## Stage 3 — Remove first-success behavior from canonical splits

### Files

```text
backend/app/workouts/program_engine/engine.py
backend/tests/workouts/program_engine/test_best_program_selection_integration.py
backend/tests/workouts/program_engine/test_post_construction_feasibility.py
backend/tests/workouts/program_engine/test_selection_sessions.py
```

### Order

1. Add an integration test where:
   - canonical split #1 succeeds;
   - canonical split #2 also succeeds;
   - split #2 has better final quality;
   - current code incorrectly returns #1.
2. Prove the test fails before implementation.
3. Collect successful exact splits instead of returning immediately.
4. Fully construct all shortlisted canonical exact-day splits.
5. Select the best admitted canonical candidate with `program_selection`.
6. Add `SPLIT_FALLBACK_AFTER_CONSTRUCTION_FAILURE` only when a previous candidate actually failed.
7. When a later split is evaluated only for quality comparison after an earlier success, use:
   - `SPLIT_CANDIDATE_EVALUATED_FOR_QUALITY`.
8. Do not copy previous candidate failures into the later successful candidate as though they belong to it.

### Gate

- new integration tests;
- split/session tests;
- full Program Engine suite;
- deterministic repeated test.

### Commit

`feat(program-engine): select the best valid canonical program`

---

## Stage 4 — Unified template + canonical primary pool

### Files

```text
backend/app/workouts/program_engine/engine.py
backend/app/workouts/program_engine/template_survival.py
backend/tests/workouts/program_engine/test_best_program_selection_integration.py
backend/tests/workouts/program_engine/test_template_reference.py
backend/tests/workouts/program_engine/test_professional_topology_integration.py
backend/tests/workouts/program_engine/test_post_construction_feasibility.py
```

### Order

1. Add a test where:
   - template succeeds;
   - canonical succeeds;
   - canonical has better final quality;
   - canonical must win.
2. Add a true-quality-tie test where the curated template wins.
3. Add a case where:
   - template has lower preconstruction/product score;
   - template produces better final quality;
   - final quality wins.
4. Remove template final return before canonical evaluation.
5. Remove product-score early pruning after shortlist entry.
6. Fully construct up to `MAX_TEMPLATE_CANDIDATES`.
7. Fully construct up to `MAX_CANONICAL_CANDIDATES`.
8. Put admitted template and canonical candidates into one primary pool.
9. Keep survival key in trace/diagnostics only.
10. Never compare raw template product score with canonical score.
11. Select and return the best primary candidate.

### Gate

- template/professional-topology tests;
- integration selection tests;
- full Program Engine suite;
- repeated selection under different input orders.

### Commit

`feat(program-engine): compare templates and canonical programs by final quality`

---

## Stage 5 — Best dynamic fallback + final selection trace

### Files

```text
backend/app/workouts/program_engine/engine.py
backend/app/workouts/program_engine/program_selection.py
backend/tests/workouts/program_engine/test_best_program_selection_integration.py
backend/tests/workouts/program_engine/test_template_selection_trace.py
backend/tests/workouts/program_engine/test_golden_scenarios.py
```

### Order

1. Prove that when a valid primary candidate exists, dynamic fallback is not executed.
2. Prove that when all primary candidates fail, multiple dynamic candidates are constructed.
3. Evaluate the first `DYNAMIC_BATCH_SIZE` dynamic candidates.
4. If none are admitted, evaluate at most the next batch, bounded by `MAX_DYNAMIC_CANDIDATES`.
5. Select the best admitted dynamic candidate, not the first successful dynamic candidate.
6. Add a stable final selection trace schema.

### Required trace fields

- `schema_version`
- selection phase
- selection strategy
- proposed candidate count
- evaluated candidate count
- successful candidate count
- admitted candidate count
- evidence-rejected count
- first-valid identifier
- selected identifier
- selected source
- selected preconstruction rank
- `selected_different_from_first_valid`
- summarized quality key
- warning burden
- repair burden
- substitution burden
- failure reason codes for rejected candidates

### Trace must not include

- complete losing programs;
- user identity;
- medical details;
- complete losing exercise lists;
- unserializable objects.

### Gate

- deterministic trace;
- JSON serialization;
- dynamic integration tests;
- full Program Engine suite.

### Commit

`feat(program-engine): select and trace the best dynamic fallback`

---

## Stage 6 — Unified reproducible audit tooling

### Files

```text
backend/scripts/program_engine_audit_support.py
backend/scripts/audit_supported_profile_catalog.py
backend/scripts/generate_100_profiles_audit_report.py
backend/scripts/generate_200_profiles_eval.py
backend/tests/workouts/program_engine/test_program_engine_audit_support.py
```

### Order

1. Centralize success-denominator logic.
2. Determine supported status only from production compatibility rules.
3. Keep unsupported profiles in a separate negative cohort.
4. Do not remove catalog-gap failures from the supported denominator.
5. Add a deterministic 200-supported-profile audit.
6. Give every profile a stable fingerprint.
7. Report:
   - selected vs first-valid;
   - candidate counts;
   - source;
   - critical quality floor;
   - coverage;
   - volume;
   - explicit priority;
   - Body Analysis priority;
   - recovery;
   - duration;
   - warnings;
   - repairs;
   - substitutions;
   - runtime;
   - failure taxonomy.
8. Make existing 100- and 200-profile scripts share the common helper.
9. JSON is the source of truth.
10. PDF/HTML are presentation only.

### Gate

- denominator test;
- unsupported separation test;
- deterministic fingerprint test;
- catalog-gap-supported-failure test;
- small smoke run without tracked artifacts.

### Commit

`feat(program-engine): add reproducible best-program audit metrics`

---

# PHASE A MANDATORY CHECKPOINT

This checkpoint is mandatory.

Do not touch Stage 7, Stage 8, or Stage 9 implementation before it is complete.

## Run

At minimum:

- frozen 100-profile baseline cohort;
- independent 150 supported holdout;
- deterministic 200 supported-profile audit;
- at least three repeated deterministic runs where practical.

## Produce

### Selection-quality results

For every profile with more than one valid candidate:

- first-valid identifier;
- selected identifier;
- whether selection changed;
- first-valid quality key;
- selected quality key;
- whether selected quality is >= first-valid quality;
- selected source;
- candidate counts.

### Success results

Report:

- supported attempted;
- supported success;
- supported failure;
- success percentage;
- unsupported negative cohort separately.

### Failure taxonomy

Count remaining failures by exact root cause / reason family.

At minimum isolate:

- semantic opener;
- session count;
- required slot;
- safety/equipment;
- hard volume;
- recovery;
- prescription;
- catalog gap;
- unknown/evidence issues.

### Performance

Record:

- p50 latency;
- p95 latency;
- proposed candidates;
- evaluated candidates;
- successful candidates;
- admitted candidates;
- trace size;
- memory if reliably measurable.

### Determinism

Verify the same inputs produce the same:

- selected source;
- selected identifier;
- final quality key;
- decision trace ordering;
- program output where deterministic output is expected.

## Phase A acceptance

Phase A passes when:

- canonical split path no longer returns first success;
- templates and canonical splits compete in one primary pool;
- dynamic fallback remains separate;
- dynamic path selects best admitted fallback, not first success;
- hard-invalid candidate never wins;
- selected candidate quality is never worse than first-valid for all multi-valid test profiles;
- selection is deterministic;
- trace explains why the winner was chosen;
- Program Engine tests pass;
- no hard-safety/validity regression appears.

## Decision rule for Phase B

Do not execute a Phase B repair merely because it exists in this roadmap.

Use the measured failure taxonomy.

A Phase B stage is applicable only if its target failure remains a **material contributor** to supported-profile failures.

For this roadmap, treat a failure family as material if either:

- it accounts for at least 2 supported failures in the checkpoint cohort; or
- fixing it is required to cross the >90% acceptance threshold; or
- it represents a systematic correctness defect even if numerically small.

If a Phase B stage is not applicable:

- do not implement it;
- report why it was skipped;
- continue to the next applicable stage.

---

# PHASE B — SUCCESS-RATE REPAIR

Phase B has one job:

> Repair the measured dominant supported-profile failures without weakening real coaching, scientific, safety, structural, or validation rules.

After each Phase B stage:

- re-run the smallest relevant regression audit;
- report how the failure taxonomy changed;
- do not start solving a later Phase B failure inside the current stage.

---

## Stage 7 — Semantic opener repair
### Execute only if semantic opener remains material after the Phase A checkpoint

Target failure:

`SEMANTIC_OPENER_CONFLICT`

### Files

```text
backend/app/workouts/program_engine/session_structure.py
backend/tests/workouts/program_engine/test_task_d_session_openers.py
backend/tests/workouts/program_engine/test_session_structure.py
backend/tests/workouts/program_engine/test_stage9_home_limited_equipment.py
```

### Order

1. Reproduce a real push-up + pull-up failure with a fixed profile.
2. Add a failing test proving:
   - both exercises are allowed;
   - only one needs to be the required opener.
3. Implement deterministic opener choice:
   1. true strength-primary;
   2. explicit chest/back priority;
   3. original construction order;
   4. stable exercise identifier.
4. Keep the other exercise if otherwise valid.
5. Keep semantic duplicate protection unchanged.
6. Test bodyweight profiles:
   - without caution;
   - with supported caution.
7. Verify success did not increase by creating unsafe or duplicated programming.

### Gate

- opener tests;
- semantic-duplicate tests;
- home-limited tests;
- full Program Engine suite;
- 100-profile audit;
- updated failure taxonomy.

### Commit

`fix(program-engine): resolve dual semantic opener conflicts deterministically`

### After-stage decision

Re-run the supported audit.

If supported success is now already >90% and the remaining count failures are not systematic correctness defects, Stage 8 may be skipped with evidence.

---

## Stage 8 — Evidence-based session-count feasibility
### Execute only if count failures remain material after Stage 7 / latest audit

Target failure:

`SESSION_EXERCISE_COUNT_OUT_OF_RANGE`

This stage changes a behavior proxy, so it must be isolated from Stage 7.

### Files

```text
backend/app/workouts/program_engine/session_feasibility.py
backend/app/workouts/program_engine/duration_policy.py
backend/app/workouts/program_engine/duration_capacity.py
backend/app/workouts/program_engine/session_builder.py
backend/app/workouts/program_engine/session_duration.py
backend/app/workouts/program_engine/validation.py
backend/app/workouts/program_engine/final_gate.py
backend/app/workouts/program_engine/constraint_classification.py

backend/tests/workouts/program_engine/test_session_feasibility.py
backend/tests/workouts/program_engine/test_session_exercise_count_policy.py
backend/tests/workouts/program_engine/test_duration_capacity.py
backend/tests/workouts/program_engine/test_main_training_duration_invariant.py
backend/tests/workouts/program_engine/test_task_i_final_gate.py
```

### Order

1. Reproduce current count failures with frozen profiles.
2. Prove under-preferred count without evidence is rejected.
3. Prove under-preferred count with complete evidence can be accepted with constraints.
4. Prove one remaining safe/useful/non-redundant feasible exercise invalidates constrained-count evidence.
5. Prove Core/cardio/warm-up do not count as MAIN.
6. Prove hard volume, recovery, duration maximum, and prescription remain enforced.
7. Build centralized feasibility policy/evidence.
8. Connect all count-policy consumers to the centralized evidence.
9. Remove duplicate count logic.
10. Penalize constrained-count programs in final quality selection.
11. Preserve the 30-minute `3–4 MAIN` contract.
12. Never add junk work merely to satisfy a number.

### Gate

- count/duration/final-gate tests;
- zero unexplained thin programs;
- full Program Engine suite;
- 100-profile audit;
- 150-supported holdout;
- updated failure taxonomy.

### Commit

`fix(program-engine): allow only evidenced constrained session counts`

---

## Stage 9 — Required-slot catalog-gap vs greedy-dead-end diagnosis
### Execute only if `REQUIRED_SLOT_HARD_IMPOSSIBILITY` remains material

Primary files:

```text
backend/scripts/audit_supported_profile_catalog.py
backend/app/workouts/program_engine/session_builder.py
```

For every remaining `REQUIRED_SLOT_HARD_IMPOSSIBILITY`, determine:

- Did a slot-compatible exercise exist at session start?
- Was it consumed or semantic-blocked by an earlier greedy choice?
- Did hard volume truly block it?
- Did duration maximum truly block it?
- Did recovery truly block it?
- Did injury/equipment truly block it?
- Could an alternative ordering have filled all required slots?

### Case A — Greedy dead-end is proven

Only then create:

```text
backend/app/workouts/program_engine/session_search.py
backend/tests/workouts/program_engine/test_session_search.py
```

Bounded required-slot search:

- beam width: `8`
- max branch factor per required slot: `4`
- deterministic ordering
- ranking order:
  1. hard compatibility
  2. `SessionCoherence.placement_rank()`
  3. semantic diversity
  4. volume/duration headroom
  5. stable exercise slug
- optional exercises only after all required slots are completed
- if bounded search cannot solve it, return the same hard failure

Commit only if implemented:

`fix(program-engine): backtrack required slots when greedy selection blocks viability`

### Case B — Real catalog gap is proven

Do not:

- invent exercises;
- weaken safety;
- weaken equipment requirements;
- weaken slot requirements;
- remove the failure from the supported denominator.

Instead:

- report exact profile/slot/equipment/catalog gaps;
- preserve them as supported failures;
- continue all remaining applicable verification stages.

If fixing the catalog requires a genuinely ambiguous product/data decision that cannot be derived from the repository, ask one precise question. Otherwise do not stop for approval.

---

## Stage 10 — Final quality, success, determinism, and performance evaluation

Do not bump versions before this stage passes.

### Tests

From `backend/` run:

```text
uv run pytest tests/workouts/program_engine -q
uv run pytest tests/workout_reviews -q
uv run pytest -q
uv run ruff check app tests scripts
uv run ruff format --check app tests scripts
uv run mypy app
git diff --check
```

If full backend has an unrelated pre-existing failure:

- do not fix unrelated code;
- separate it with evidence;
- do not falsely claim full release verification passed.

### Final benchmark matrix

Run:

- frozen 100-profile baseline cohort;
- Phase 11.6 independent 150 supported holdout; if the historical runner itself is stale, preserve the intended frozen supported holdout/cohort semantics and explicitly report the replacement/current execution path rather than silently skipping it;
- new deterministic 200 supported profile audit;
- unsupported/red-flag negative cohort;
- three independent deterministic runs;
- generate 30 stratified baseline-vs-new program pairs for later human blind Coach review.

Important:

Luna should **prepare the 30 paired artifacts** required for later blind review.

Do not block implementation completion on Luna pretending to perform a human blind review.

### Supported success thresholds

For 150 supported profiles:

- >90% means at least `136` successful;
- preferred 95% target means at least `143`.

For 200 supported profiles:

- >90% means at least `181` successful;
- preferred 95% target means at least `190`.

### Success definition

A supported profile counts as successful only if:

- program exists;
- validation is valid;
- final gate accepts it;
- final selection evidence is complete.

Catalog gaps remain supported failures.

### Negative cohort

Safety/red-flag/unsupported rejection correctness must be 100%.

### Quality acceptance

For every multi-valid profile:

- selected quality key must not be worse than first-valid;
- hard violations = 0;
- p10 critical quality floor must not regress;
- median critical quality floor must not regress;
- explicit priority quality must not materially regress;
- Body Analysis priority quality must not materially regress;
- volume floor must not regress;
- coverage must not regress;
- hard recovery conflicts = 0;
- unexplained thin programs = 0;
- semantic duplicates = 0;
- unexplained repetition must not increase;
- duration fit may be worse only when a more important coaching dimension is demonstrably better;
- repairs/substitutions must remain explainable and traceable.

### Human-review artifact requirements

Generate 30 stratified pairs containing enough information for a later blind review of:

- weekly structure;
- goal fit;
- priority muscles;
- Body Analysis influence;
- volume;
- recovery;
- variety;
- repetition;
- duration;
- prescription quality.

Do not label which side is baseline/new in the blind-review payload.

Also include the review rubric and acceptance target from the original roadmap:

- weekly structure
- goal fit
- priority-muscle fit
- Body Analysis influence
- volume
- recovery
- variety
- repetition
- duration
- prescription quality

For the later **human** blind review, the new engine should be clearly better or equal in a clear majority of pairs and must have zero safety failures.

Luna must prepare the evidence and paired artifacts, but must not pretend that an automated self-review is a human blind review.

### Performance

Record:

- candidates proposed;
- candidates evaluated;
- candidates successful;
- candidates admitted;
- p50 latency;
- p95 latency;
- trace size;
- memory usage if reliably measurable.

Performance gate:

- p50 should not exceed 2× baseline;
- p95 should not exceed 3× baseline.

If performance exceeds this:

1. first optimize immutable request-level caching/reuse;
2. remove repeated calculations;
3. preserve candidate caps, safety, and quality;
4. do not add parallel construction in this roadmap.

---

## Stage 11 — Version bump and release commit

Execute only if:

- relevant tests pass;
- full Program Engine suite is green;
- hard violations are zero;
- supported success is >90%;
- preferred 95% is reached, or the remaining gap is fully explained by documented real catalog gaps;
- final quality has not regressed;
- three-run determinism passes;
- no unexplained thin program remains.

### Changes

```text
program_engine_v1 → program_engine_v2
resistance_training_v5 → resistance_training_v6
```

Rename:

```text
backend/tests/workouts/program_engine/test_ruleset_version_v5.py
→
backend/tests/workouts/program_engine/test_ruleset_version_v6.py
```

Verify:

- new generation signature is produced;
- old stored programs remain readable;
- no database migration is required;
- stale old-policy cached programs are not incorrectly reused for new generation requests.

### Commit

`feat(program-engine): release best-program selection engine v2`

Push the current branch if available.

If supported success is still <=90%, do not perform the version bump and do not falsely claim release completion.

Instead, finish with a precise unresolved-failure report.

---

# 8. REQUIRED TEST MATRIX

## Final selection

Must prove:

- hard-invalid candidate cannot win because of soft quality;
- balanced candidate beats high-average candidate with one severe weakness;
- N/A is not zero;
- selection is independent of candidate input order;
- template and canonical compete on real final quality;
- curated source is tie-break only;
- dynamic fallback does not enter primary competition;
- dynamic first-success behavior is gone;
- incomplete selection-critical evidence fails closed;
- unknown selection-critical constraint fails closed;
- informational unknown trace does not incorrectly reject a valid candidate.

## Quality

Must prove:

- direct/effective volume semantics align with validation;
- priority uses applicable direct/effective/frequency evidence;
- explicit priority and Body Analysis priority remain separate;
- repairable recovery does not score as perfect;
- non-full-body coverage is measurable;
- duration cannot compensate for weak volume/priority/recovery;
- actual substitution is distinct from a substitution option;
- repair collection is not dependent on free-text substring parsing.

## Hard safety / validity contracts

Must preserve:

- injury/caution restrictions;
- equipment restrictions;
- inactive/review-pending exercise restrictions;
- hard weekly/session volume;
- valid prescription;
- required slots;
- semantic duplicate prevention;
- hard recovery conflicts;
- exact requested resistance-training days;
- full-body hard coverage;
- superset safety;
- Core/supplemental MAIN-count semantics.

None may be weakened merely to turn benchmark failures green.

## Supported-profile diversity

Audit matrix should include:

- gym;
- home bodyweight;
- home dumbbell;
- 2–6 training days;
- 30, 40/45, 60, 75, 90, 120-minute sessions;
- first-month through advanced;
- all supported goals;
- explicit priorities;
- Body Analysis priorities;
- supported cautions;
- recovery-limited profiles;
- equipment-limited profiles.

---

# 9. MAJOR RISKS TO WATCH

- nondeterminism from `set` / `frozenset` iteration;
- candidate mutation through shared state;
- oversized decision trace;
- raw-score comparison across incompatible candidate families;
- template winning only because it is curated;
- one weak coaching dimension hidden by an average;
- informational trace counted as repair;
- substitution option counted as actual substitution;
- effective volume used where direct constraint is authoritative;
- `accepted_with_constraints` without complete evidence;
- thin programs accepted only to increase success rate;
- benchmark denominator changed to make results look better;
- historical benchmark reported as current result;
- Coach Review projection broken by internal metric expansion;
- stale cached program reused after engine-policy change;
- latency explosion from candidate construction;
- tests rewritten to match a bug instead of fixing behavior;
- Phase B fixes leaking into Phase A;
- count-policy changes leaking into semantic-opener work;
- beam search added without proof of greedy dead-end.

---

# 10. TRUE COMPLETION CRITERIA

The master roadmap is complete only when every applicable condition is satisfied:

- exact split no longer returns first success;
- templates and canonical splits compete in a unified primary pool;
- dynamic fallback remains separate;
- best admitted dynamic fallback is selected;
- hard-invalid candidate never enters final quality competition;
- selection is deterministic;
- trace explains the winning decision;
- selected quality is never worse than first-valid across multi-valid evaluation profiles;
- no unsafe program is generated;
- no invalid program is generated;
- no semantic duplicate regression appears;
- no hard-volume violation appears;
- no unexplained thin program appears;
- supported success rate exceeds 90%;
- preferred target is at least 95%;
- remaining catalog gaps, if any, are explicitly documented rather than hidden;
- Program Engine tests pass;
- Coach Review compatibility tests pass;
- Ruff passes;
- mypy passes;
- independent audits pass;
- deterministic repeated runs pass;
- focused commits exist for completed stages;
- pushes are completed when remote push is available.

If a real catalog gap is the only remaining blocker to 95%, do not weaken scientific or safety rules.

Report the exact profile / slot / equipment / catalog gap and finish every other applicable verification step.

---

# Final instruction to Luna Max

Execute this roadmap from Stage 0 through the last applicable stage.

**DO NOT OPTIMIZE A FUTURE STAGE WHILE WORKING ON THE CURRENT STAGE.**

**One stage = one problem = one implementation scope = one verification gate.**

Finish the current stage, verify it, commit it, and only then move forward.

Keep PHASE A and PHASE B strictly separated by the mandatory checkpoint.

Use measured evidence from the checkpoint to decide which Phase B stages are applicable.

Do not ask for routine approvals.

Only ask a question if a genuine ambiguity blocks a technically correct decision and cannot be resolved from the repository, tests, or this roadmap.

Otherwise, continue carefully until the roadmap is complete.
