# Unified Exercise Substitution Engine

Repository: `mohammad4242/fitsho`

Expected starting main:
`1f11d48d395e3903c5645cd590d114cbaaa941d2`

## Mission

Build ONE authoritative, deterministic, explainable exercise substitution system for Fitsho.

It must unify the current fragmented replacement logic and handle:

- missing/unavailable equipment
- home / limited equipment
- blocked exercises/patterns
- injury/limitation-derived structured constraints
- caution tags
- ROM
- overhead
- axial load
- impact
- balance/stability
- template replacements
- dynamic program replacements
- displayed exercise alternatives
- repair-path alternatives such as volume repair

Do not build a giant hardcoded exercise A→B matrix.

Use:
structured exercise semantics
+ existing hard eligibility
+ substitution policy
+ curated substitution groups
+ curated ExerciseAlternative knowledge
+ deterministic ranking.

---

# EXECUTION PROTOCOL

Work sequentially.

For EACH stage:

1. inspect CURRENT code first
2. implement only that stage
3. run focused tests
4. run relevant program-engine/backend tests
5. mypy affected backend
6. Ruff changed Python files
7. `git diff --check`
8. inspect final diff for unrelated changes
9. commit
10. push
11. verify remote commit
12. update `PROMPT4_PROGRESS.md`
13. continue to next stage

Do NOT repeatedly restate or summarize this file.

Create `PROMPT4_PROGRESS.md` containing only:

- current stage
- completed stages
- commit SHAs
- migrations
- important decisions
- tests/results
- known unresolved issue

Use this progress file to resume efficiently.

Do NOT commit this instruction file or progress file unless explicitly requested.

If working tree contains unrelated modifications overlapping files you need to edit, STOP and ask.

Only ask the user a question for a genuinely blocking product/safety ambiguity that cannot be resolved from code/tests.

---

# MODEL DELEGATION

SOL is the lead architect and final reviewer.

SOL MUST personally handle architecture-sensitive work.

LUNA HIGH should be used as a subagent for bounded/mechanical tasks whenever available.

Do not run conflicting Sol/Luna edits in parallel.

Luna must receive:
- exact task
- exact allowed file scope
- acceptance criteria
- tests to run

After Luna finishes:
SOL reviews the diff and tests before commit/push.

If Luna subagents/model routing are unavailable, Sol continues itself.

## SOL OWNERSHIP

Sol must own:

- repository architecture discovery
- semantic contract
- canonical equipment architecture
- substitution policy
- unified engine API
- ranking/tier semantics
- safety/eligibility boundaries
- strength substitution semantics
- integration architecture
- decisions caused by benchmark failures
- final review and SAFE/NOT SAFE verdict

## LUNA HIGH TASKS

Prefer Luna for:

- metadata audit tooling
- mechanical schema propagation after Sol defines contract
- frontend equipment multi-select implementation after backend contract exists
- straightforward caller migrations to an already-stable unified API
- regression test matrices
- benchmark harness additions
- metrics plumbing
- mechanical catalog corrections explicitly approved by Sol
- repetitive tests/refactors with narrow file scopes

Sol reviews everything Luna changes.

---

# GLOBAL INVARIANTS

DO NOT modify:

- sex scoring/behavior
- split selection semantics unless absolutely required by substitution integration
- Days × Experience compatibility
- volume architecture
- duration architecture
- recovery architecture
- supplemental architecture
- session structure/order semantics
- cardio semantics
- unrelated goal logic

Do not infer medical diagnoses from free text.

Do not weaken safety to reduce UNSAT.

Hard eligibility always wins.

A curated replacement NEVER bypasses eligibility.

---

# EXISTING REPOSITORY FACTS TO VERIFY

Before edits, confirm CURRENT main still has these concepts:

Exercise/catalog metadata:

- primary_muscle
- muscle_focus
- secondary_muscles
- movement_pattern
- exercise_type
- equipment
- caution_tags
- body_position
- stability_demand
- skill_demand
- impact_level
- axial_loading_level
- fatigue_cost
- setup_cost
- laterality
- substitution_group
- range_of_motion_profile
- ExerciseAlternative

Current ExerciseCandidate carries most of this but historically does not carry `muscle_focus`.

Current important code includes:

- `program_engine/eligibility.py`
- `program_engine/equipment.py`
- `program_engine/replacement_ranker.py`
- `program_engine/slot_compatibility.py`
- template session logic
- session builder
- volume repair
- exercise substitution groups
- profile/home-equipment mapping

Adapt to CURRENT code if repository changed.

---

# STAGE 0 — DISCOVERY
Owner: SOL

No production changes.

Search the entire repository for:

- `rank_replacement_exercises`
- `substitution_group`
- `ExerciseAlternative`
- `substitution_exercise_ids`
- `available_equipment`
- `_available_equipment`
- `effective_required_equipment`
- replacement/substitute/alternative logic

Trace:

Profile
→ equipment
→ ProgramGenerationRequest
→ constraints
→ eligibility
→ template/dynamic construction
→ replacements
→ repairs
→ validation/output.

Identify EVERY independent replacement implementation.

Record findings in `PROMPT4_PROGRESS.md`.

No commit required.

---

# STAGE 1 — CANONICAL EXERCISE SEMANTICS
Owner: SOL

Create:

`backend/app/workouts/program_engine/exercise_semantics.py`

Add immutable derived semantic representation such as:

`ExerciseRoleSignature`

Role should represent WHAT the exercise does:

- movement_pattern
- primary_muscle
- muscle_focus
- exercise_type
- secondary_muscles
- body_position
- laterality
- substitution_group

Do NOT put user safety/equipment constraints inside the role.

Add `muscle_focus` to `ExerciseCandidate`.

Propagate:

DB Exercise
→ WorkoutGenerationService
→ ExerciseCandidate.

Do not add persisted `movement_role` DB column.

Tests:

- muscle_focus propagates correctly
- role deterministic
- role independent of display/localized title
- known muscle-focus classifications preserved

Sol tests/reviews/commits/pushes.

---

# STAGE 2 — SUBSTITUTION METADATA AUDIT
Owner: LUNA HIGH
Reviewer: SOL

Create:

`backend/app/exercises/audit_substitution_metadata.py`

Audit programmable resistance catalog for:

- missing primary muscle
- missing required muscle_focus
- MovementPattern.OTHER
- ExerciseType.OTHER
- missing equipment
- Equipment.OTHER
- missing body_position
- missing stability/skill
- missing impact/axial metadata
- missing laterality
- missing/legacy substitution_group
- suspicious mixed semantic groups
- curated alternative coverage
- home-compatible role coverage
- roles with only one candidate

Output deterministic report.

Do NOT mass-fix catalog yet.

Add tests.

Sol reviews report and diff.

Commit/push.

---

# STAGE 3 — CANONICAL EQUIPMENT SOURCE
Owner: SOL
Frontend mechanical work may be delegated to LUNA after backend contract is defined.

Goal:
ONE authoritative user equipment inventory.

Add backward-compatible explicit inventory such as:

`available_equipment`

Legacy behavior:

`bodyweight_only`
→ `{BODYWEIGHT}`

`dumbbells_available`
→ `{BODYWEIGHT, DUMBBELL}`

Explicit inventory becomes canonical when present.

Keep `home_training_setup` for backward compatibility.

Gym behavior must remain backward-compatible.

Create/use ONE canonical equipment resolver.

All relevant paths must use it:

- profile/service
- candidate selector
- workout generation service
- ProgramGenerationRequest
- substitution engine

Support realistic home inventory at minimum:

- BODYWEIGHT
- DUMBBELL
- RESISTANCE_BAND
- BENCH
- PULL_UP_BAR

Multi-equipment requirements MUST remain strict.

Example:

Dumbbell Bench Press requires:
`DUMBBELL + BENCH`

Having only dumbbells is insufficient.

Audit Equipment.OTHER.

Add new equipment enums ONLY where current programmable catalog proves they are necessary.

If schema changes:
create NEW Alembic migration.
Never rewrite old migration history.

### Luna subtask after Sol defines backend contract

Implement frontend multi-select equipment support in bounded profile files and tests.

Sol reviews frontend diff before commit.

Run backend + frontend affected tests.

Commit/push.

---

# STAGE 4 — CURATED KNOWLEDGE
Owner: LUNA HIGH
Architecture/review: SOL

Expose existing `ExerciseAlternative` knowledge to the program engine.

Use either:

- immutable alternative IDs/index
or
- another clean immutable knowledge representation

Choose based on current architecture.

Rules:

- directionality preserved
- A→B does not imply B→A
- curated alternative is STRONG PREFERENCE only
- candidate must still pass hard eligibility
- candidate must still satisfy substitution policy

Keep explicit persisted `substitution_group`.

Persisted group > legacy/name inference.

Name-based classification may remain only as import/legacy fallback.

Do not create a second replacement engine.

Sol reviews.

Commit/push.

---

# STAGE 5 — CANONICAL SUBSTITUTION POLICY
Owner: SOL

Create:

`backend/app/workouts/program_engine/substitution_policy.py`

This file defines ALLOWED semantic degradation.

It does NOT select concrete exercises.

Centralize movement-family compatibility here.

No duplicate hidden compatibility matrices should remain across:

- substitution engine
- slot compatibility
- template replacement logic

Start from existing conservative semantics.

Examples may include, only where current architecture/domain rules support them:

Back:
horizontal pull ↔ vertical pull
as controlled suboptimal fallback.

Quadriceps:
squat ↔ lunge.

Posterior chain:
hinge / hip extension / knee flexion
only under explicitly valid hamstring/glute contexts.

Do NOT invent broad equivalence such as:
vertical push ↔ horizontal push
without explicit domain justification.

Policy inputs should account for:

- movement pattern
- primary muscle
- muscle focus
- exercise type
- goal
- strength role
- slot/day context
- substitution cause

For Strength reuse existing:

`PRIMARY_STRENGTH`
`SECONDARY_COMPOUND`
`ACCESSORY`

Do NOT create a separate loadability model yet.

Tests must cover all allowed/disallowed degradations.

Commit/push.

---

# STAGE 6 — UNIFIED SUBSTITUTION ENGINE
Owner: SOL

Create:

`backend/app/workouts/program_engine/substitution_engine.py`

This becomes the ONLY authoritative concrete ranking engine.

Suggested concepts:

- SubstitutionContext
- SubstitutionCause
- SubstitutionTier
- SubstitutionOption
- SubstitutionDecision

Use existing hard eligibility FIRST.

Pipeline:

1. hard-eligible candidate pool
2. remove target
3. apply canonical substitution policy
4. classify semantic tier
5. deterministic ranking
6. return options + explanation
7. if none valid, return explicit no-replacement result

## Recommended tiers

### Tier A
Curated/exact group + exact semantic role.

### Tier B
Same:
- movement pattern
- primary muscle
- muscle focus
- exercise type

### Tier C
Same:
- movement pattern
- primary muscle
- exercise type

compatible but different muscle focus.

### Tier D
Explicit policy-approved movement-family fallback.

Everything else:
HARD INCOMPATIBLE.

## Within a valid tier prefer

- curated alternative
- same substitution_group
- same muscle_focus
- same primary muscle
- same exercise type
- same StrengthExerciseRole when relevant
- secondary-muscle overlap
- same body_position
- same laterality
- suitability for triggering constraint
- ROM similarity
- stability similarity
- skill similarity
- impact/axial suitability
- fatigue similarity
- setup similarity
- preferred exercise
- avoid disliked exercise
- stable ID tie-break

Prefer clear lexicographic ranking rather than opaque magic scores.

## Cause-aware behavior

MISSING_EQUIPMENT:
preserve role tightly while adapting equipment.

AXIAL/LOWER-BACK:
among semantically valid candidates prefer lower axial load / supported option where appropriate.

BALANCE:
prefer lower stability demand / supported/bilateral options where valid.

OVERHEAD:
never return another overhead candidate that violates the constraint.

ROM:
candidate must satisfy allowed ROM contract.

Multiple constraints:
candidate must satisfy ALL.

Do not diagnose free-text medical conditions.

Add stable reason codes for explainability.

Examples:

- SUBSTITUTION_CURATED_ALTERNATIVE
- SUBSTITUTION_EXACT_ROLE
- SUBSTITUTION_SAME_GROUP
- SUBSTITUTION_MUSCLE_FOCUS_PRESERVED
- SUBSTITUTION_STRENGTH_ROLE_PRESERVED
- SUBSTITUTION_EQUIPMENT_ADAPTED
- SUBSTITUTION_CONSTRAINT_ADAPTED
- SUBSTITUTION_MOVEMENT_FAMILY_FALLBACK
- SUBSTITUTION_ROLE_DEGRADED
- SUBSTITUTION_NO_VALID_REPLACEMENT

Follow existing project naming conventions.

Comprehensive tests required.

Commit/push.

---

# STAGE 7 — MIGRATE ALL CALLERS
Lead: SOL

Sol first defines the integration pattern and migrates the most architecture-sensitive path.

Then use Luna High for bounded caller migrations.

Find EVERY caller generating/recommending replacements.

Expected areas include:

- template session resolution
- session builder
- dynamic program paths
- `substitution_exercise_ids`
- volume repair
- other repair paths

Do not assume this list is complete.

### Sol handles

- template path
- main dynamic path
- canonical API decisions

### Luna may handle

- volume-repair alternative call migration
- repetitive `substitution_exercise_ids` migrations
- mechanical test updates

only after Sol freezes the unified API.

`replacement_ranker.py` final state:

either delete it,
or keep only a thin compatibility forwarding wrapper.

It must contain NO independent ranking logic.

`slot_compatibility.py` may remain if useful,
but must consume canonical substitution-policy semantics rather than own another matrix.

Template substitutions must preserve:

- target muscles
- movement intent
- `structure_focus`

No volume/duration/session-structure redesign.

After migration grep the repository and prove no second concrete replacement ranking implementation remains.

Commit/push.

---

# STAGE 8 — LIMITATION-AWARE REGRESSIONS
Owner: LUNA HIGH
Reviewer: SOL

Build tests for:

- lower-back / axial load
- knee / deep flexion
- shoulder / overhead
- wrist loading
- balance
- ROM
- multiple simultaneous constraints

Test template + dynamic paths.

Mandatory:

unsafe candidate never appears as replacement.

If no professional substitute exists:
return none/UNSAT rather than unrelated filler.

Sol reviews failures and makes architecture decisions if needed.

Commit/push.

---

# STAGE 9 — HOME / LIMITED EQUIPMENT
Tests/benchmark: LUNA HIGH
Domain decisions/fixes: SOL

Test:

- bodyweight only
- dumbbells
- bodyweight+dumbbells
- dumbbells+bench
- bands
- bands+dumbbells
- bodyweight+pull-up-bar
- dumbbells+bench+bands+pull-up-bar

Across representative:

- beginner
- intermediate
- strength
- hypertrophy/muscle-gain
- valid 2/3/4 day combinations
- selected limitation combinations

Assert:

- 0 unavailable-equipment exercises
- 0 safety violations
- replacements equipment-valid
- deterministic
- exact role preferred
- muscle focus preserved where possible
- no unrelated filler
- UNSAT only when role truly unavailable

Reproduce historical home/bodyweight failures.

Do NOT fix failure by weakening safety.

If real catalog coverage is missing:
Sol decides whether minimal new exercise/catalog metadata is justified.

No mass import.

Commit/push.

---

# STAGE 10 — OBSERVABILITY / QUALITY
Owner: LUNA HIGH
Reviewer: SOL

Integrate with existing metrics/decision trace where appropriate.

Track enough to distinguish:

- substitution requests
- successes
- exact group
- exact semantic role
- muscle-focus preserved
- role preserved but focus degraded
- movement-family fallback
- equipment-triggered
- constraint-triggered
- no valid replacement

Do not overengineer metrics.

Validator/invariants must ensure surfaced alternatives are:

- active
- programmable
- not needs_review
- equipment-valid
- constraint-valid
- policy-compatible

Commit/push.

---

# STAGE 11 — FINAL CLOSEOUT
Execution: LUNA HIGH where suitable
Final review/decisions: SOL

Run:

- substitution tests
- exercise catalog tests
- profile/equipment tests
- template tests
- full program-engine tests
- full backend pytest
- affected frontend tests
- frontend typecheck/lint
- mypy
- Ruff changed files
- `git diff --check`
- existing Phase 11.x benchmarks where compatible

Do NOT regenerate baselines merely because outputs changed.

Investigate meaningful regressions.

Final benchmark must report:

- generation success
- substitution request count
- substitution success
- UNSAT
- equipment violations
- safety violations
- deterministic repeatability
- exact-role rate
- muscle-focus preservation
- movement-family fallback rate
- home subgroup results

Mandatory final invariants:

equipment violations = 0
safety violations = 0
determinism = 100%

and:

- one authoritative concrete substitution engine
- no hard-eligibility bypass
- no curated-alternative safety bypass
- one canonical equipment resolution
- template + dynamic use same engine
- repairs use same engine
- no second independent replacement policy
- session structure preserved
- supplemental architecture preserved
- duration preserved
- recovery preserved
- sex behavior unchanged

---

# FINAL ACCEPTANCE

Do NOT mark SAFE unless all are true:

1. one authoritative substitution engine exists
2. fragmented replacement ranking removed/wrapped
3. eligibility always precedes ranking
4. muscle_focus participates in semantics
5. role derives from structured metadata, not display names
6. explicit substitution_group respected
7. name inference only legacy/import fallback
8. ExerciseAlternative integrated safely
9. realistic equipment inventory supported
10. one canonical equipment resolver
11. multi-equipment requirements enforced
12. substitution cause affects suitability
13. Strength uses existing StrengthExerciseRole
14. unsafe/unavailable alternatives never surface
15. unrelated filler is never used to avoid UNSAT
16. deterministic results
17. stable explainable reason codes
18. template/dynamic/repair paths share architecture
19. realistic equipment + constraint combinations tested
20. no unrelated architecture regression

---

# FINAL REPORT

At completion report only:

- starting SHA
- stage commit SHAs
- migration revisions
- new files
- important modified files
- architecture summary
- catalog audit findings
- equipment model
- substitution tiers
- migrated callers
- test results
- backend result
- frontend result
- mypy/Ruff
- benchmark before/after
- safety violations
- equipment violations
- determinism
- remaining limitations
- SAFE / NOT SAFE

Do not give long progress narratives unless a failure/decision requires it.
