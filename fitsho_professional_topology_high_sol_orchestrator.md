# Fitsho Workout Engine — Professional Topology Preference
## Orchestrated Implementation Prompt for High Sol + Luna Subagents

You are **High Sol**, the **owner, architect, integrator, and final reviewer** of this task.

You are not just a coordinator. You own the correctness of the final implementation.

Your responsibilities are:

- understand the full task and current architecture before any code changes;
- make the important architectural decisions yourself;
- break the work into small, independent, clearly scoped subtasks;
- choose the appropriate subagent model for each subtask:
  - **Luna Low** for simple, mechanical, low-risk work;
  - **Luna Medium** for moderate reasoning, contained implementation, or test work;
  - **Luna High** for complex local reasoning, non-trivial code changes, or risky edge cases;
- delegate only narrowly scoped work;
- review every subagent result yourself;
- verify that every subagent followed the intended architecture;
- reject or correct subagent work when it is incomplete, inconsistent, over-engineered, or unsafe;
- personally fix mistakes if needed;
- integrate the work coherently;
- run and inspect the relevant tests;
- perform the final end-to-end review yourself.

**Do not delegate architectural ownership.**
**Do not delegate final correctness.**
**Do not accept a subagent result merely because it compiles or passes a local test.**

The goal of using subagents is to reduce token usage and parallelize small pieces of work without lowering implementation quality.

---

# Main Product Goal

Implement a **strong but soft professional-topology preference** in the Fitsho workout program engine.

For genuinely **Intermediate** and **Advanced** users training **4, 5, or 6 resistance days per week**, the engine should have a **much stronger tendency** to choose professional / muscle-group-oriented structures such as:

- Body-Part splits
- Arnold-style splits
- PPL
- PPL ×2
- PPL + Upper/Lower hybrid
- professional specialization templates
- FST-7 style specialization when it actually matches the user's priority
- other semantically equivalent professional structures already represented in the catalog

The engine should **not** primarily gravitate toward generic pure Upper/Lower when better professional structures are feasible.

However:

> **Upper/Lower must NOT be banned.**

It must remain eligible and may still win when:
- professional alternatives are infeasible;
- duration/recovery/equipment constraints make them unsuitable;
- another legitimate existing scoring signal is strong enough;
- all higher-preference candidates fail construction or validation.

This is a **ranking preference**, not a hard exclusion rule.

---

# Critical Architecture Fact

Before changing code, verify the current flow yourself.

The engine currently attempts **reference templates first** and returns on the first successful one.

Only after reference-template candidates are exhausted does it rank/generated split candidates.

Therefore this feature **must affect both paths**:

1. Reference-template ranking
2. Generated/fallback split ranking

A change only inside `split_selector.py` is incomplete and must be rejected.

---

# Required Files to Inspect First

Read these carefully before planning:

```text
backend/app/workouts/program_engine/engine.py
backend/app/workouts/program_engine/template_scoring.py
backend/app/workouts/program_engine/template_selector.py
backend/app/workouts/program_engine/split_selector.py
backend/app/workouts/program_engine/schemas.py
backend/app/workouts/program_engine/normalization.py
backend/app/workouts/program_engine/enums.py
backend/app/workouts/program_engine/rulesets/resistance_training_v1.py

backend/app/training_templates/tags.py
backend/app/training_templates/engine_reference.py
backend/app/training_templates/models.py
backend/app/training_templates/seed_data.py
```

Also inspect the relevant tests under:

```text
backend/tests/workouts/program_engine/
```

Especially:

```text
test_template_scoring.py
test_template_selector_baseline.py
test_template_selection_trace.py
test_template_reference.py
test_template_structure_propagation.py
test_split_volume.py
test_regression_profiles.py
test_workout_engine_reference_profiles.py
test_duration_capacity.py
test_phase11_7_template_recovery.py
test_session_duration_targets.py
test_validation_quality.py
```

Do not assume enum names, reason-code conventions, score dataclass signatures, or test helpers. Verify them from the current repository.

---

# Phase 1 — Sol Architecture Review

Before delegating anything, High Sol must:

1. Read the relevant code.
2. Confirm the current template-first engine flow.
3. Confirm how `TemplateReference.split_type` is derived.
4. Confirm how `focus_tags` are validated.
5. Confirm current split scoring and legacy Body-Part bonuses.
6. Confirm normalization behavior for training experience/status.
7. Confirm how template decision traces are structured.
8. Identify all tests likely to require updates.
9. Decide the smallest coherent architecture for a shared topology preference policy.

Then produce a short internal implementation plan.

Only after that should subtasks be delegated.

---

# Target Scope

The new professional-topology preference applies only when:

```text
request.training_status in {INTERMEDIATE, ADVANCED}
AND
request.resistance_training_days in {4, 5, 6}
```

Use **normalized `TrainingStatus`**, not just user-declared `TrainingExperience`.

If normalization downgraded a declared Intermediate or Advanced user because of:
- insufficient training age;
- poor/recent consistency;
- other existing normalization rules;

then the new professional-topology preference must **not bypass that downgrade**.

Outside this scope, preserve current behavior as closely as possible.

Specifically:

- FIRST_MONTH: unchanged
- BEGINNER: unchanged
- Intermediate/Advanced 1–3 days: unchanged
- existing low-frequency behavior: unchanged

---

# New Professional Topology Tiers

Inside the target scope, apply a new **single topology score component**.

The desired tiers are:

```text
0 points
--------
FULL_BODY variants
UPPER_LOWER
UPPER_LOWER_FULL
UPPER_LOWER_SPECIALIZATION
UPPER_LOWER_X3
PHUL
other generic Upper/Lower-derived structures

30 points
---------
PUSH_PULL_LEGS_UPPER_LOWER hybrid

40 points
---------
PUSH_PULL_LEGS
PUSH_PULL_LEGS_X2

50 points
---------
BODY_PART_ROTATION
muscle-group rotation
Arnold-style layouts represented semantically as BODY_PART_ROTATION

60 points
---------
professional specialization whose specialization metadata genuinely matches:
- an explicit user priority, or
- an eligible body-analysis priority
```

Important:

> These are **tiers**, not additive bonuses.

A matching specialization that is otherwise Body-Part receives:

```text
60
```

not:

```text
50 + 60 = 110
```

Example:

```text
FST-7 Arms template
BODY_PART_ROTATION + ARMS_PRIORITY + SPECIALIZATION

User priority = biceps/triceps
=> professional topology score = 60

User priority = quadriceps
=> professional topology score = 50
```

---

# Important Product Interpretation

Professional structure preference should be **strong**, but still soft.

Expected general behavior:

```text
professional feasible structure
    gets a major head start

existing legitimate signals
    still participate

hard constraints
    always win over score
```

Example:

```text
Upper/Lower
professional topology = 0
other score = 75
total = 75

Body-Part
professional topology = 50
other score = 20
total = 70

=> Upper/Lower may still win
```

This is valid.

Do not create a hidden hard ban through an extreme penalty.

---

# Shared Policy Architecture

Do not duplicate `30/40/50/60` logic in multiple files.

High Sol should create or approve one shared policy/helper module, for example:

```text
backend/app/workouts/program_engine/topology_preference.py
```

or another repository-consistent name.

That shared policy should own, at minimum:

- target-scope detection;
- topology classification;
- professional tier lookup;
- specialization matching;
- semantic reason-code generation where appropriate.

The shared policy must support both:

- TemplateReference scoring
- SplitCandidate / SplitType scoring

Do not let the template path and fallback split path drift into independent implementations.

---

# Ruleset Ownership of Numbers

Do not scatter magic numbers.

Put the numeric values into the current workout ruleset, with clear names.

For example:

```text
professional_hybrid_bonus = 30
professional_ppl_bonus = 40
professional_body_part_bonus = 50
professional_matching_specialization_bonus = 60
```

Naming may be improved to match repository style.

Do not unnecessarily change unrelated scoring values.

---

# Template Scoring Changes

Extend template scoring with a dedicated component, for example:

```python
professional_structure_score: int = 0
```

It must be included in `TemplateScore.total`.

Preserve compatibility with existing positional `TemplateScore(...)` calls.

Existing tests may construct five positional score fields. Do not cause broad unrelated breakage just by inserting a required field in the wrong position.

The existing components must retain their current meaning:

- priority
- body analysis
- goal
- sex
- fallback

Do not rewrite their scoring logic.

The new professional topology score is an **independent additional component**.

---

# Template Semantic Classification — Critical Edge Case

Do not rank templates by slug or display name.

Forbidden patterns include:

```python
if "fst7" in template.slug:
```

```python
if "arnold" in template.slug:
```

```python
if "professional" in template.slug:
```

Use canonical semantic metadata only.

Production references are built from validated `focus_tags`.

However, some tests create synthetic `TemplateReference` instances without a primary structure tag.

`TemplateReference.split_type` may fall back to `BODY_PART_ROTATION` when no matching structure tag exists.

Therefore:

> Do not blindly use `template.split_type` to award Body-Part professional points.

Inspect:

```text
tags & PRIMARY_STRUCTURE_TAGS
```

directly.

If no primary structure tag exists:

```text
professional_structure_score = 0
```

This protects existing synthetic tests and prevents malformed references from receiving false professional credit.

---

# Specialization Matching

`SPECIALIZATION` alone does not justify 60 points.

The specialization must actually match a meaningful user signal.

Reuse existing canonical helpers where appropriate:

```text
priority_tags_for_muscles()
regional_priority_tags_for_muscles()
priority_tag_for_muscle()
eligible_body_analysis_priorities()
```

Respect existing:

```text
SUPPLEMENTAL_MUSCLES
```

Do not build another independent mapping from strings/muscle names.

Explicit priorities and eligible body-analysis priorities should remain consistent with the existing engine semantics.

A generic Upper/Lower family structure should not regain the maximum professional tier merely by carrying some specialization-like marker.

The maximum 60 tier is for a matching **professional** specialization topology.

---

# Template Hard Eligibility Must Remain Unchanged

Do not use this feature to add hard-rejection rules for Upper/Lower.

Preserve current hard eligibility behavior around:

- days mismatch
- experience-level mismatch
- core-slot resolvability
- provably infeasible required-core duration

Do not add:

```text
UPPER_LOWER_DISALLOWED
```

or equivalent behavior.

Upper/Lower must remain inside the ranked candidate pool.

---

# Template Decision Trace

Extend template decision traces to make this new behavior visible.

Current score trace should gain a field similar to:

```text
professional_structure
```

Total must equal the sum of all score components.

Example:

```text
priority
body_analysis
goal
sex
fallback
professional_structure
total
```

Add clear reason codes following repository conventions, for example:

```text
PROFESSIONAL_TOPOLOGY_HYBRID_PREFERENCE
PROFESSIONAL_TOPOLOGY_PPL_PREFERENCE
PROFESSIONAL_TOPOLOGY_BODY_PART_PREFERENCE
PROFESSIONAL_TOPOLOGY_MATCHING_SPECIALIZATION_PREFERENCE
```

High Sol should choose final names that fit existing conventions.

Traceability is important because we will later evaluate random generated profiles and need to see why a professional template outranked another candidate.

---

# Dynamic Split Ranking

Apply the same shared policy in `score_split_candidates()`.

Do not remove legitimate existing scoring such as:

- base
- complexity
- session-count distance
- twice-weekly frequency
- goal specificity
- priority specialization
- PHUL behavior
- priority allocation adjustment
- recovery penalties
- duration/capacity handling

The new topology preference should be added coherently to those signals.

---

# Existing Body-Part Bonus — Prevent Double Counting

There is already a legacy `body_part_rotation_bonus`.

Do not accidentally create:

```text
legacy Body-Part bonus +30
new professional Body-Part tier +50
------------------------------------
effective +80
```

That would make the fallback split path inconsistent with the reference-template path.

Inside the new professional-topology scope:

```text
use the new shared topology tier
instead of the legacy body_part_rotation_bonus
```

Outside the new scope:

```text
preserve the legacy behavior unchanged
```

This is a required regression-safety rule.

---

# Expected Six-Day Direction

Under comparable conditions, current split scoring can favor Upper/Lower ×3.

After the new feature, the professional topology head start should be strong enough that the relative direction becomes approximately:

```text
UPPER_LOWER_X3
new professional topology = 0

PUSH_PULL_LEGS_X2
new professional topology = 40

BODY_PART_ROTATION
new professional topology = 50
```

Do not hard-code final total scores.

Existing goal/frequency/complexity/recovery/priority logic must still matter.

It is valid for PPL×2 to beat Body-Part for one user and Body-Part to beat PPL×2 for another.

---

# Safety Boundaries

Do not change or weaken:

```text
exercise eligibility
injury/limitation filtering
safety screening
exercise selection
template construction
session builder
substitution logic
weekly volume planning
volume allocation
weekly recovery validation
duration repair
session duration hard constraints
final validation
cardio
progression
deload logic
```

A high professional topology score must never override hard infeasibility.

If a professional template is hard-ineligible, it remains rejected.

If a generated split is provably duration-infeasible and a feasible split exists, the professional score must not move the infeasible split ahead of the feasible one if current sort semantics intentionally prioritize feasibility.

Preserve existing fallback/recovery behavior.

---

# Database / Catalog Scope

Do not add migrations for this task unless High Sol discovers a truly unavoidable architectural requirement.

Expected approach:

- use current `focus_tags`;
- use current template metadata;
- do not add ranking logic based on slugs;
- do not rewrite seed templates merely to manipulate score.

The catalog already contains professional template families.

This task should primarily change ranking policy, not catalog storage.

---

# Subagent Delegation Strategy

High Sol owns task decomposition.

Use the smallest capable Luna model for each subtask.

## Luna Low

Use for tasks such as:

- straightforward test additions with exact expected behavior already defined;
- small mechanical refactors;
- adding simple trace fields;
- updating repetitive assertions;
- simple ruleset field additions;
- formatting / cleanup after architecture is fixed.

Do not assign Luna Low ambiguous architecture or cross-path behavioral decisions.

## Luna Medium

Use for tasks such as:

- implementing a clearly specified helper;
- contained scoring logic;
- medium-complexity tests;
- updating template scoring using an already-approved shared policy;
- updating split scoring after Sol defines exact behavior;
- investigating a localized test failure.

## Luna High

Use for tasks such as:

- non-trivial specialization matching;
- subtle integration tests;
- reasoning-heavy regression investigation;
- complex interaction between ranking and feasibility;
- difficult failures involving existing engine semantics.

Luna High still does not own architecture.

---

# Recommended Work Decomposition

High Sol may change this decomposition after reading the code, but a good default is:

### Subtask A — Shared topology policy
Possible model: Luna Medium or Luna High

Scope:
- shared helper/policy
- target-scope predicate
- topology tiers
- specialization matching
- unit tests

### Subtask B — Template scoring + trace
Possible model: Luna Medium

Scope:
- `TemplateScore`
- template professional score
- reason codes
- decision trace
- targeted template tests

### Subtask C — Dynamic split integration
Possible model: Luna Medium

Scope:
- apply shared policy
- prevent legacy Body-Part double-count
- preserve out-of-scope legacy behavior
- targeted 4/5/6-day split tests

### Subtask D — Integration/regression tests
Possible model: Luna High

Scope:
- `generate_program()` template-first behavior
- Upper/Lower remains eligible
- professional template wins when feasible
- fallback still works
- normalized downgrade behavior
- duration/recovery interaction

### Subtask E — Mechanical test updates
Possible model: Luna Low

Scope:
- trace sum assertions
- new score field expectations
- version expectation updates if needed

High Sol should not mechanically follow this split if repository inspection suggests a better one.

---

# Rules for Every Subagent Assignment

Every delegated task must include:

1. exact files allowed to change;
2. exact behavior to implement;
3. explicit non-goals;
4. tests to add/run;
5. instruction not to redesign unrelated code;
6. instruction to report any architectural concern instead of improvising a new architecture.

Subagents must not make broad unrequested changes.

If a subagent discovers that the assigned design conflicts with current code, it should report the conflict to High Sol.

High Sol decides what to do.

---

# Sol Review Requirements After Every Subagent

High Sol must inspect the actual diff.

For each subagent result, verify:

- Did it follow the shared architecture?
- Did it duplicate policy logic?
- Did it add slug/name-based behavior?
- Did it accidentally create hard rejection?
- Did it bypass normalized training status?
- Did it double-count existing bonuses?
- Did it alter unrelated safety/recovery/duration logic?
- Did it preserve determinism?
- Are tests meaningful or just matching implementation?
- Does the change work in the engine's actual template-first flow?

If anything is wrong:

> High Sol must correct it.

Do not simply ask the same subagent repeatedly without understanding the failure.

---

# Required Tests

The implementation is incomplete without focused tests.

At minimum cover:

## 1. Scope isolation

Verify:

- FIRST_MONTH 4–6 days gets no new professional topology score.
- BEGINNER 4–6 days gets no new professional topology score.
- Intermediate/Advanced 1–3 days gets no new professional topology score.
- a declared Intermediate/Advanced user downgraded by normalization does not receive the new bonus.

## 2. Target-scope tiers

For genuine Intermediate/Advanced 4/5/6-day requests:

```text
generic Upper/Lower family => 0
PPL + UL hybrid            => 30
PPL / PPL×2                => 40
Body-Part                  => 50
```

## 3. Specialization

Verify:

- matching professional specialization => 60
- non-matching specialization => base professional topology tier
- no slug or name matching is used

## 4. Synthetic TemplateReference safety

Verify:

- a template with no PRIMARY_STRUCTURE_TAGS gets professional score 0
- it does not accidentally become Body-Part because of `TemplateReference.split_type` fallback behavior

## 5. Template ranking

Verify:

- comparable feasible professional template ranks above generic Upper/Lower in scope
- Upper/Lower remains eligible
- Upper/Lower is not hard rejected
- Upper/Lower can still be selected if professional alternatives are hard-infeasible or fail construction

## 6. Main engine integration

Add at least one test through:

```text
generate_program()
```

with multiple reference templates.

It must prove that the professional reference is ranked/attempted first when feasible.

This test is critical because the reference-template path is the primary engine path.

## 7. Dynamic split ranking

Verify at least:

- 4-day Intermediate/Advanced: Body-Part strongly outranks generic Upper/Lower under comparable conditions
- 5-day: PPL+UL and Body-Part receive correct tier behavior
- 6-day Intermediate: PPL×2 and/or Body-Part ranks above UPPER_LOWER_X3 under comparable default conditions
- Advanced equivalent remains coherent

## 8. Decision trace

Verify:

- `professional_structure` exists
- total includes it
- correct reason code appears
- deterministic tie-breaking still works

## 9. Outside-scope regression

Verify that existing Beginner and low-frequency behavior remains stable.

---

# Test Execution

High Sol must decide the exact commands from repository conventions.

At minimum:

1. run focused new/modified tests;
2. run related template/split/duration/recovery regression tests;
3. run the full `backend/tests/workouts/program_engine/` suite if feasible;
4. inspect failures rather than blindly patching assertions.

Do not silently fix unrelated pre-existing failures.

If unrelated failures already exist, report them separately.

---

# Versioning

This is a material ranking-policy behavior change.

Inspect repository conventions around:

```text
ProgramRuleset.version
ruleset_version
engine_version
```

If ruleset version is intended to identify behavioral policy, bump it appropriately.

Do not bump `engine_version` unless repository conventions actually require it.

Update only the necessary tests/expectations.

---

# Acceptance Criteria

The task is complete only if all of the following are true:

- genuine Intermediate/Advanced 4–6-day users have a clearly stronger preference for professional/muscle-group-oriented structures;
- reference-template ranking and generated split ranking use one shared policy;
- generic Upper/Lower gets zero **new** professional-topology points;
- Upper/Lower is still eligible and can still legitimately win;
- PPL+UL = 30;
- PPL/PPL×2 = 40;
- Body-Part = 50;
- matching professional specialization = 60;
- tiers do not stack;
- specialization matching is semantic and personalized;
- no slug/name-based scoring exists;
- synthetic tagless template references do not get false Body-Part credit;
- the new component is visible in decision trace;
- old Body-Part bonus is not double-counted inside target scope;
- out-of-scope legacy behavior is preserved;
- hard safety/duration/recovery/eligibility constraints are unchanged;
- template-first engine behavior is covered by an integration test;
- relevant tests pass.

---

# Final High Sol Verification

After all subagents finish:

1. Review the entire combined diff yourself.
2. Search for duplicated topology scoring logic.
3. Search for hard-coded 30/40/50/60 values outside the approved policy/ruleset.
4. Search for slug/name-based ranking shortcuts.
5. Confirm Upper/Lower remains eligible.
6. Confirm normalized downgrade behavior.
7. Confirm no Safety/Recovery/Duration logic was weakened.
8. Confirm the reference-template path and fallback split path behave consistently.
9. Run the relevant tests.
10. Fix any incorrect subagent work yourself.
11. Only then declare the task complete.

---

# Final Report Required From High Sol

At the end, provide a concise implementation report with:

```text
1. Architecture implemented
2. Files changed
3. Subtasks delegated and which Luna tier handled each one
4. Any subagent work Sol corrected/reworked
5. Exact topology scoring policy
6. Tests added/updated
7. Test commands executed
8. Test results
9. Ruleset/version change, if any
10. Any remaining risk or known limitation
```

Do not stop after planning.
Continue through implementation, verification, correction, and final review.

Only stop and ask the user if there is a genuine product ambiguity that cannot be resolved from the repository and this specification.
