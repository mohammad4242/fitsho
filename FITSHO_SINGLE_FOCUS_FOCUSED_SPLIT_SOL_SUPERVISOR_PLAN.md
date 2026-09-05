# FITSHO — Single Muscle Focus + Experienced 4/5/6-Day Focused Split Repair

## Sol Architect / Supervisor Execution Plan

**Repository:** `mohammad4242/fitsho`  
**Audited branch:** `main`  
**Audited HEAD:** `e441764772b0866d03041272aca11e682a7434e8`  
**Mission type:** architecture + delegation + verification  
**Primary implementers:** Luna agents  
**Sol role:** architect, task manager, reviewer, integrator, final verifier

---

# 0. Mission

You are **Sol acting as the architect and technical supervisor**, not the primary bulk implementer.

Your objective is to change Fitsho so that:

1. A user may select **zero or exactly one user-facing muscle group as their training focus/priority**.
2. The UI must not allow a user to choose multiple priority muscles.
3. Broad regions such as **upper body / lower body** must not be user-selectable focus values.
4. The broad pseudo-group `legs` must not be offered as the user's focus when concrete lower-body groups such as quadriceps and hamstrings are available.
5. For **Intermediate and Advanced** users training **4, 5, or 6 resistance days/week**, coherent focused splits must receive a clear ranking advantage and should normally be selected when safe and constructible.
6. In that cohort, generic broad `upper` sessions should become a **fallback**, not the normal default, when a more focused Push/Pull or body-part topology is feasible.
7. In particular, **chest and back should normally be separated into different sessions** for Intermediate/Advanced 4–6 day plans when the catalog, safety, duration, and recovery constraints permit it.
8. Lower-body specialization should also be more coherent: when enough weekly days exist, quadriceps-focused and posterior-chain/hamstrings-glutes work should be separable instead of always collapsing into one generic `legs/lower` day.
9. The selected user focus must affect template/split ranking, weekly frequency, direct volume placement, and decision trace without turning an entire workout into “only one muscle.”
10. Existing safety, equipment, duration, recovery, determinism, substitution, volume, and validation guarantees must remain intact.

The final implementation must be end-to-end: **profile contract → onboarding/profile UI → persisted value → engine mapping → template scoring → dynamic split scoring → session construction → final quality checks → regression report**.

Do not stop after changing only `split_selector.py`.

---

# 1. Important Product Semantics — Do Not Misinterpret “Single Focus”

The user's **selected focus** is singular. That does **not** mean every workout day is allowed to train only one anatomical muscle.

Examples:

- User focus = `chest`.
  - A chest-focused day may still contain triceps accessories.
  - A Push day may still contain shoulders/triceps.
  - But a 4–6 day experienced plan should not receive artificial preference for a generic `upper` day merely because that one day can claim chest + back + shoulders simultaneously.

- User focus = `back`.
  - A back day may contain biceps.
  - A Pull day is valid.
  - The user still selected only **back** as their priority.

- User focus = `quadriceps`.
  - A quad-focused day may contain calves and limited hamstring support.
  - It must not be represented to the product as generic “lower-body focus.”

- User focus = `hamstrings`.
  - A posterior-chain day can include glutes/core where programming requires it.
  - The priority remains hamstrings.

The key distinction is:

> **Single user priority ≠ single-muscle-only workout.**  
> It means one explicit programming priority, with coherent synergist/accessory work allowed.

---

# 2. Verified Current-HEAD Root Causes

## 2.1 Profile/API currently permits multiple priority muscles

Inspect first:

- `backend/app/profile/schemas.py`
- `backend/app/profile/models.py`
- `backend/app/profile/service.py`

Current architecture stores `priority_muscles` as a JSON list and exposes it as a plural collection. The schema validator currently checks uniqueness but does not enforce a maximum of one selected muscle.

**Do not immediately replace the database column with a scalar column.**

The least risky architecture is:

- preserve the storage/wire shape initially for backward compatibility;
- enforce **0 or 1** values at the product/API boundary;
- normalize the frontend form to a singular value;
- explicitly audit legacy rows containing more than one value before deciding whether a data migration is required.

A DB migration is not automatically required for this product behavior.

## 2.2 Workout request mapper accepts an arbitrary-size priority set

Inspect:

- `backend/app/workouts/service.py`
- method `_to_program_request(...)`

Current mapping converts persisted values to:

```python
priority_muscles=frozenset(
    MuscleGroup(value) for value in (profile.priority_muscles or ())
)
```

So any profile containing 2, 3, or more values reaches the engine as a multi-priority set.

This boundary must become defensive even after API validation is fixed, because old records may exist.

## 2.3 Frontend profile form is explicitly multi-select

Inspect:

- `frontend/src/features/profile/types.ts`
- `frontend/src/features/profile/ProfileFormFields.tsx`
- `frontend/src/features/profile/profileValidation.ts`

Current behavior:

- `ProfileFormValues.priority_muscles` is an array.
- `togglePriorityMuscle()` appends/removes values.
- all muscle groups are rendered as checkboxes.
- `toProfileInput()` sends every selected item.

This must become a true single-select model, preferably by making impossible multi-select states unrepresentable in the form type.

## 2.4 Public onboarding currently does not ask the focus question at all

Inspect:

- `frontend/src/features/publicOnboarding/GuidedTrainingQuestions.tsx`
- `frontend/src/features/publicOnboarding/PublicOnboardingPage.tsx`
- `frontend/src/features/publicOnboarding/onboardingDraft.ts`
- related tests

Current `GuidedTrainingQuestions` asks experience, training age, days, location, equipment, duration, intensity, cautions, and plan weeks — but no muscle focus question.

Therefore a user entering through the current public guided flow can finish training onboarding without explicitly choosing a priority muscle.

Add a dedicated **single focus** question to the guided training flow if the product flow is intended to collect this input. Keep it optional unless existing product requirements make it mandatory.

## 2.5 The muscle enum mixes true user-facing priorities with broad/safety-oriented values

Inspect:

- `backend/app/exercises/enums.py`
- `frontend/src/features/profile/types.ts`

`MuscleGroup` currently includes values such as:

- chest
- back
- shoulders
- biceps
- triceps
- traps
- forearms
- neck
- glutes
- quadriceps
- hamstrings
- adductors
- abductors
- `legs`
- calves
- abs
- obliques
- lower_back

`BodyRegion` separately contains `upper_body`, `lower_body`, `core`.

Do not use the full raw `MuscleGroup` enum as the user-focus menu.

Create a product-owned whitelist, for example a concept equivalent to:

```python
USER_SELECTABLE_PRIORITY_MUSCLES
```

Recommended initial product set unless an existing product rule clearly says otherwise:

```text
chest
back
shoulders
biceps
triceps
traps
forearms
glutes
quadriceps
hamstrings
calves
abs
```

At minimum:

- do not offer `legs` as a focus;
- do not offer `upper_body` / `lower_body` as focus;
- do not expose `neck` or `lower_back` as ordinary bodybuilding-priority choices without an explicit product/safety reason;
- do not automatically expose adductors/abductors merely because the engine enum contains them.

Keep the whitelist centralized and shared conceptually between backend validation and frontend options. Do not copy an unreviewed list in many places.

## 2.6 The core split-scoring bug: broad `upper` gets full priority credit

Inspect:

- `backend/app/workouts/program_engine/priority_allocation.py`
- `backend/app/workouts/program_engine/slot_compatibility.py`

`PriorityAllocationPolicy.split_adjustment()` counts how often each priority is trained through `focus_trains_muscle()`.

`focus_trains_muscle()` ultimately uses `focus_scope()`.

`focus_scope("upper")` includes:

```text
chest
back
shoulders
traps
biceps
triceps
```

Therefore one `upper` day can count as an exposure for every selected upper muscle.

For two `upper` sessions, a priority can appear to have two high-quality exposures even though each session is broad and the major groups are competing for the same session capacity.

This is the main scoring distortion.

### Critical architecture rule

**Do not “fix” this by shrinking `focus_scope("upper")`.**

`focus_scope()` is also used for exercise/session compatibility. A generic upper day genuinely can contain pushing, pulling, arms, and shoulders.

Instead, separate these two concepts:

1. **Session compatibility scope** — which exercises are allowed in this focus.
2. **Priority/topology affinity** — how strongly this focus represents the user's selected muscle for ranking purposes.

These must not remain the same function.

## 2.7 `upper` session construction intentionally requires Push + Pull

Inspect:

- `backend/app/workouts/program_engine/session_builder.py`
- function `slots_for_focus(...)`

For `focus.startswith("upper")`, current slots include required Push and required Pull.

So once `upper` is selected, chest/back mixing is structurally expected.

This is not a session-builder bug by itself. The higher-level bug is that experienced 4–6 day users are too often routed into `upper` in the first place.

Do not break valid 2–4 day Upper/Lower programming by removing the meaning of an Upper session globally.

## 2.8 Dynamic split candidates already contain some focused layouts, but the set is incomplete

Inspect:

- `backend/app/workouts/program_engine/split_selector.py`
- `backend/app/workouts/program_engine/enums.py`
- `backend/app/workouts/program_engine/rulesets/resistance_training_v1.py`

Current 4-day dynamic candidates include:

- Upper/Lower
- Upper/Lower specialization
- Full Body Four
- Upper/Lower/Full
- PHUL
- Body-Part Rotation = `chest_triceps / back_biceps / legs / shoulders_traps`

Current 5-day candidates include:

- Upper/Lower specialization
- PPL + Upper/Lower
- Body-Part Rotation = `chest_triceps / back_biceps / shoulders_traps / legs / specialization`

Current 6-day candidates include:

- PPL ×2
- Upper/Lower ×3
- Body-Part Rotation = `chest_triceps / back_biceps / quadriceps_calves / shoulders_traps / posterior_chain_core / specialization`

The 4-day and 5-day dynamic candidate catalogs still contain broad lower grouping where the library already demonstrates better quads/posterior separation.

## 2.9 The template library already contains the desired programming concepts

Inspect:

- `backend/app/training_templates/seed_data.py`
- `backend/app/training_templates/tags.py`

Important existing templates include:

- `t08-4-day-push-pull-quads-posterior`
- `t10-5-day-classic-body-part`
  - Chest
  - Back
  - Legs
  - Shoulders
  - Arms
- `t15-6-day-ppl-2x`
- `t16-6-day-advanced-body-part`
  - Chest
  - Back
  - Quads
  - Shoulders
  - Arms
  - Hamstrings + Glutes
- chest/back/leg specialization templates

This means the solution is **not** “invent a new workout library from scratch.”

The main work is ranking, topology semantics, input contract, and selective candidate/catalog refinement.

## 2.10 Template scoring currently has no explicit high-frequency focus-concentration quality term

Inspect:

- `backend/app/workouts/program_engine/template_scoring.py`
- `backend/app/workouts/program_engine/template_selector.py`

Current template scoring emphasizes:

- exact/regional user priority tags
- body-analysis priority
- goal affinity
- sex prior
- balanced fallback

It does not yet have a clear concept equivalent to:

```text
experienced_high_frequency_focused_topology
large_major-muscle_separation
selected_focus_concentration
broad_upper_penalty
```

Additionally, `template_selector.py` contains a special 4-day upper-priority topology check based on **multiple explicit upper priorities**. That logic was created for the old multi-priority model and must be re-audited under the new single-priority contract.

## 2.11 Engine is template-first

Inspect:

- `backend/app/workouts/program_engine/engine.py`

The engine ranks eligible templates, tries them in order, and returns immediately on the first successful template.

Only after template candidates are exhausted does it rank/try dynamic splits.

Therefore:

> Changing dynamic `split_selector.py` weights alone is insufficient.

Template ranking must express the same new topology policy, otherwise a broad successful template can still win before the improved dynamic split is ever considered.

---

# 3. Target Architecture

## 3.1 Introduce a product-level single-focus contract

Preferred location:

```text
backend/app/profile/training_focus.py
```

Create a small, explicit policy layer owning concepts equivalent to:

```python
USER_SELECTABLE_PRIORITY_MUSCLES
MAX_USER_PRIORITY_MUSCLES = 1
```

Responsibilities:

- validate product-selectable focus muscles;
- distinguish user preference from internal/body-analysis priorities;
- make the “one explicit focus” rule centralized and testable;
- avoid using raw display labels for logic.

Do not put user-facing focus policy inside the exercise catalog enum itself.

## 3.2 Preserve storage compatibility unless a data audit proves migration is necessary

Keep, initially:

```text
UserProfile.priority_muscles JSON list
Profile API priority_muscles list shape
ProgramGenerationRequest priority_muscles frozenset
```

but enforce:

```text
new writes: 0 or 1 values only
```

Why:

- avoids unnecessary destructive schema migration;
- minimizes API breakage;
- keeps older clients more manageable;
- allows a staged cleanup of legacy multi-value rows.

### Legacy data requirement

Before changing persistence:

1. inspect whether any actual persisted profiles contain `len(priority_muscles) > 1`;
2. if none exist, no data migration is necessary;
3. if such rows exist, do **not** silently discard preferences by arbitrarily taking the first item;
4. implement a documented repair/compatibility behavior and cover it with tests.

Sol must make the final decision after inspecting actual current data/migrations, not by guessing.

## 3.3 Make the frontend form singular

Preferred frontend model:

```ts
priority_muscle: UserSelectablePriorityMuscle | ""
```

rather than:

```ts
priority_muscles: MuscleGroup[]
```

The wire API may still serialize the value as:

```json
{"priority_muscles": ["shoulders"]}
```

for backward compatibility.

Use radio buttons, a segmented single-choice list, or a select — not checkboxes.

If “no special focus” is allowed, provide a clear no-focus option or leave it optional.

## 3.4 Add focus selection to public guided training onboarding

Add a training question conceptually equivalent to:

```text
“Which muscle group would you most like to prioritize?”
```

Persian should be natural and singular, e.g.:

```text
«دوست داری در برنامه روی کدام گروه عضلانی بیشتر تمرکز شود؟»
```

The answer is exactly one value or none.

Do not present:

- upper body
- lower body
- whole legs
- multiple simultaneous focus chips

## 3.5 Introduce a dedicated topology-affinity semantic layer

Preferred new module:

```text
backend/app/workouts/program_engine/focus_topology.py
```

The exact name may differ if the existing architecture offers a better home, but do not scatter this logic across five files.

Define concepts equivalent to:

```text
FocusAffinity.DEDICATED
FocusAffinity.GROUPED
FocusAffinity.BROAD
FocusAffinity.NONE
```

Example affinity semantics:

### Chest

- `chest_triceps` → DEDICATED
- `push` → GROUPED / strong
- `upper` → BROAD / weak
- `full_body*` → BROAD / weakest
- `back_biceps` → NONE

### Back

- `back_biceps` → DEDICATED
- `pull` → GROUPED / strong
- `upper` → BROAD / weak
- `full_body*` → BROAD / weakest

### Shoulders

- `shoulders_traps` → DEDICATED
- `push` → GROUPED
- `upper` → BROAD

### Quadriceps

- `quadriceps_calves` → DEDICATED
- `lower` / `legs` → BROAD
- Push/Pull → NONE

### Hamstrings / Glutes

- `posterior_chain_core` → DEDICATED/GROUPED
- `lower` / `legs` → BROAD

### Biceps / Triceps

- direct-arm specialization or relevant back/chest grouped session → strong/grouped;
- generic upper → broad.

The key rule:

> A broad `upper` day may be compatible with chest/back/shoulders, but it must not earn the same focus-ranking credit as a dedicated/grouped focus day.

## 3.6 Separate “exposure exists” from “high-quality priority exposure”

`PriorityAllocationPolicy.split_adjustment()` should not continue treating every compatible broad focus as one full-quality priority exposure.

Refactor it to consider affinity/quality.

Possible implementation model:

```text
DEDICATED = full priority exposure credit
GROUPED   = high/medium credit
BROAD     = partial credit
NONE      = zero
```

The exact numeric weights belong in the ruleset/policy, not hard-coded as magic values in scoring functions.

A broad upper day can still count toward physiological exposure/recovery. It just must not be over-rewarded as a **programming-priority match**.

Do not confuse:

- recovery exposure;
- direct volume exposure;
- topology ranking affinity.

They are separate concerns.

## 3.7 Add a high-frequency experienced split preference

Define the target cohort centrally:

```text
training_status ∈ {INTERMEDIATE, ADVANCED}
and resistance_training_days ∈ {4, 5, 6}
```

For this cohort, after hard feasibility checks:

- focused body-part / Push-Pull style splits should receive a strong preference;
- generic Upper/Lower should be down-ranked when a focused alternative is safe and constructible;
- Full Body should be strongly down-ranked for normal experienced 4–6 day bodybuilding-style plans;
- safety, equipment, recovery, and duration can still override the preference.

This is a **strong soft policy**, not a safety-breaking hard force.

## 3.8 Add/adjust dynamic topology candidates

### Four days — Intermediate / Advanced

Add a true focused dynamic candidate equivalent to:

```text
Push
Pull
Quadriceps + Calves
Posterior Chain + Glutes/Core
```

Use existing focus strings where possible:

```text
push
pull
quadriceps_calves
posterior_chain_core
```

This mirrors the already-existing `t08-4-day-push-pull-quads-posterior` concept.

If a new `SplitType` is needed, prefer a semantically precise type such as:

```text
PUSH_PULL_QUADS_POSTERIOR
```

Before adding it, inspect all SplitType serialization, ruleset complexity maps, tests, and persistence/display assumptions.

Do not overload a misleading enum solely to avoid adding one clear type.

### Five days — Intermediate / Advanced

Add or promote a focused five-day topology equivalent to:

```text
chest_triceps
back_biceps
quadriceps_calves
shoulders_traps
posterior_chain_core
```

This better satisfies the desired product behavior than a generic `legs` day plus an ambiguous `specialization` day.

It gives:

- chest and back separate days;
- shoulders separate day;
- quadriceps separate emphasis;
- hamstrings/glutes posterior day.

Direct arms can remain accessory work inside chest/back or be handled by session capacity; do not invent a dedicated arms day unless needed by an existing topology/template.

### Six days — Intermediate

PPL ×2 is a valid focused default because Push and Pull separate chest-dominant and back-dominant work.

Prefer it over Upper/Lower ×3 when recovery and equipment permit.

A body-part rotation is also valid if the candidate/session capacity is coherent.

### Six days — Advanced

Body-part rotation / advanced body-part should receive the strongest default preference when safe and practical, with PPL ×2 as another strong candidate.

Generic Upper/Lower ×3 should not normally win purely because it produces many broad priority “hits.”

## 3.9 Template and dynamic paths must share one policy

Do not create one ranking philosophy for templates and a different one for dynamic splits.

The same topology semantics should be reusable by:

- `template_scoring.py`
- `template_selector.py`
- `split_selector.py`
- `priority_allocation.py`
- coach-quality/decision-trace code where appropriate

This is why a small shared topology module is preferred.

---

# 4. Exact File Map — Likely Changes

Sol must verify current HEAD before every edit, but the audited change surface is:

## Backend — Profile/Product Contract

### Must inspect/change

- `backend/app/profile/schemas.py`
  - enforce max one user-selected priority;
  - validate against user-selectable whitelist;
  - update create + patch/update behavior consistently.

- `backend/app/profile/service.py`
  - ensure priority serialization/deserialization is symmetrical;
  - ensure patch/update cannot bypass the new contract.

- `backend/app/workouts/service.py`
  - harden `_to_program_request(...)` against legacy invalid multi-priority records;
  - preserve one explicit focus through generation signature and request mapping.

### Recommended new file

- `backend/app/profile/training_focus.py`
  - centralized user-selectable focus policy.

### Usually no schema migration initially

- `backend/app/profile/models.py`
  - inspect, but keep JSON list storage unless actual data constraints justify a migration.

## Backend — Engine Semantics and Split Ranking

### Must inspect/change

- `backend/app/workouts/program_engine/priority_allocation.py`
  - stop using broad focus compatibility as full priority-ranking credit;
  - use topology affinity.

- `backend/app/workouts/program_engine/split_selector.py`
  - add/promote focused 4/5/6-day candidates;
  - add high-frequency experienced preference;
  - broad Upper/Lower becomes fallback/default-lower-ranked in target cohort.

- `backend/app/workouts/program_engine/rulesets/resistance_training_v1.py`
  - own new weights/penalties/bonuses;
  - no scattered magic constants.

- `backend/app/workouts/program_engine/enums.py`
  - only if a new semantic `SplitType` is required.

- `backend/app/workouts/program_engine/template_scoring.py`
  - add topology/focus-quality scoring.

- `backend/app/workouts/program_engine/template_selector.py`
  - remove/rewrite old assumptions requiring multiple upper priorities;
  - ensure single focus works with hard eligibility and ranking.

- `backend/app/workouts/program_engine/engine.py`
  - inspect template-first short-circuit;
  - change only if improved ranking cannot guarantee correct candidate ordering.
  - avoid a large engine rewrite unless evidence shows it is necessary.

### Recommended new file

- `backend/app/workouts/program_engine/focus_topology.py`
  - canonical focus-affinity and experienced high-frequency topology semantics.

### Inspect, avoid unnecessary behavior changes

- `backend/app/workouts/program_engine/slot_compatibility.py`
  - keep compatibility semantics intact;
  - may reuse centralized topology helpers only if clean.

- `backend/app/workouts/program_engine/session_builder.py`
  - `upper` requiring Push + Pull is valid for a true Upper session;
  - do not globally remove Push/Pull requirements just to hide the symptom.

- `backend/app/workouts/program_engine/recovery.py`
  - verify new topologies still satisfy real muscle-exposure recovery.

- `backend/app/workouts/program_engine/final_gate.py`
- `backend/app/workouts/program_engine/coach_quality.py`
  - consider a final observable quality invariant/reason code after ranking behavior is correct.

## Backend — Template Catalog

### Must inspect

- `backend/app/training_templates/tags.py`
  - currently has exact priority tags for chest, back, shoulders, arms, glutes, quads, hamstrings;
  - assess whether calves/traps/abs need product-level template tags or can be handled by topology/direct-target scoring;
  - do not add tags without structural evidence.

- `backend/app/training_templates/seed_data.py`
  - reuse existing t08/t10/t15/t16 concepts;
  - retag only where current topology evidence justifies it;
  - do not duplicate the library just to change ranking.

## Frontend — Profile and Guided Onboarding

### Must change

- `frontend/src/features/profile/types.ts`
  - introduce singular form-level focus type/state;
  - separate user-selectable focus list from raw `muscleGroups` enum list.

- `frontend/src/features/profile/ProfileFormFields.tsx`
  - replace priority checkboxes with single-select UI;
  - no multi-select toggle logic.

- `frontend/src/features/profile/profileValidation.ts`
  - singular form validation;
  - wrap single value into API list for wire compatibility;
  - handle profile→form conversion safely.

- `frontend/src/features/publicOnboarding/GuidedTrainingQuestions.tsx`
  - add focus question;
  - one selection only.

- `frontend/src/features/publicOnboarding/PublicOnboardingPage.tsx`
  - update `emptyValues` / flow state as required.

- `frontend/src/features/publicOnboarding/onboardingDraft.ts`
  - ensure draft serialization/hydration preserves the singular selection via the ProfileInput wire shape.

- `frontend/src/i18n/fa.ts`
- `frontend/src/i18n/en.ts`
  - singular focus wording and labels.

### Inspect/change if affected

- `frontend/src/features/profile/OnboardingPage.tsx`
- `frontend/src/features/profile/ProfilePage.tsx`
- `frontend/src/features/profile/ProfileContext.tsx`
- `frontend/src/features/profile/api.ts`

Do not edit these unless type/state/API propagation actually requires it.

---

# 5. Scoring Policy — Required Behavioral Direction

Do not solve this with a single giant `+1000 BODY_PART_ROTATION` hack.

The score must be explainable and ruleset-owned.

Add concepts equivalent to:

```text
experienced_high_frequency_focused_split_bonus
experienced_high_frequency_broad_upper_penalty
selected_focus_dedicated_affinity_bonus
selected_focus_grouped_affinity_bonus
selected_focus_broad_affinity_credit
large_major_muscle_separation_bonus
```

The exact numeric values must be selected after running focused ranking tests and must live in the ruleset/policy.

## Ranking intent

### Intermediate / Advanced, 4 days

Normal balanced gym case:

```text
Push / Pull / Quads / Posterior
```

or another equally coherent focused structure should outrank generic:

```text
Upper / Lower / Upper / Lower
```

when both are feasible.

### Intermediate / Advanced, 5 days

A focused rotation approximately equivalent to:

```text
Chest + Triceps
Back + Biceps
Quads + Calves
Shoulders + Traps
Hamstrings + Glutes / Posterior
```

should normally outrank broad Upper/Lower hybrids.

### Intermediate, 6 days

Prefer:

```text
Push / Pull / Legs ×2
```

or a coherent focused body-part layout over:

```text
Upper / Lower ×3
```

when both are feasible.

### Advanced, 6 days

Prefer advanced body-part or focused PPL-style topology; broad Upper/Lower ×3 should generally be lower-ranked.

## Lower-frequency/non-target cohort

Do **not** globally destroy Upper/Lower or Full Body.

Examples:

- 2–3 day users may legitimately need Full Body or broad regional sessions.
- novice/first-month users should remain simple and safe.
- constrained home/equipment cases may need broader sessions.
- poor recovery may require different session count/structure.

The change is cohort-aware, not a universal ban.

---

# 6. Luna Task Decomposition

Sol must delegate implementation in small tasks. One Luna should not receive the whole refactor.

Each Luna task must return only:

```text
1. files changed
2. root cause addressed
3. tests added/updated
4. commands run
5. failures remaining
6. any architectural concern for Sol
```

Sol reviews the diff and tests after every task before assigning the next one.

---

## Luna Task A — Baseline, data-flow map, and failing regressions

**Goal:** prove the current failures before changing behavior.

### Inspect

- `AGENTS.md`
- profile priority schemas/models/service
- frontend profile priority field
- public onboarding training flow
- `_to_program_request`
- priority allocation
- split selector
- template selector/scoring
- existing relevant tests

### Add failing tests first

Backend tests should demonstrate:

1. Profile API currently accepts >1 priority muscle and must reject it after fix.
2. A concrete allowed priority (e.g. shoulders) is accepted.
3. `legs` is rejected as a new user-selected focus if it is excluded by the approved whitelist.
4. Single-focus Intermediate 4-day ranking currently allows broad Upper/Lower to beat or tie a more focused feasible topology in a representative case.
5. Equivalent 5-day regression.
6. Equivalent 6-day Intermediate regression.
7. Equivalent 6-day Advanced regression.
8. Template-first selection can currently choose a broad template before a more suitable focused topology in at least one representative fixture if reproducible.

Frontend tests should demonstrate:

1. current profile focus UI is multi-select;
2. public guided onboarding lacks or does not enforce a single focus;
3. final serialized request can contain multiple values.

### No broad implementation in Task A

Return exact reproduction evidence and root-cause locations.

---

## Luna Task B — Backend single-focus product contract

**Goal:** new profile writes support `None` or one user-selectable muscle only.

### Files

- new `backend/app/profile/training_focus.py` or architecture-consistent equivalent
- `backend/app/profile/schemas.py`
- `backend/app/profile/service.py`
- `backend/app/workouts/service.py`
- relevant profile/workout service tests

### Requirements

- centralized whitelist;
- max one value;
- broad `legs` not accepted for new user focus;
- raw BodyRegion values cannot enter this field;
- create and update behave identically;
- patch endpoint cannot bypass the rule;
- mapper remains safe for legacy records;
- no arbitrary truncation of old multi-focus data.

### Legacy audit

Inspect database/test fixtures/migrations for multi-focus persisted rows.

If actual legacy multi-focus data exists, report it to Sol with a recommended non-destructive repair strategy before a migration is committed.

### Tests

At minimum:

- zero priorities accepted;
- one allowed priority accepted;
- two allowed priorities rejected;
- disallowed broad focus rejected;
- create/update parity;
- mapper behavior is deterministic and safe.

---

## Luna Task C — Frontend singular focus + public onboarding question

**Goal:** the UI can never create multiple user priorities.

### Files

- `frontend/src/features/profile/types.ts`
- `frontend/src/features/profile/ProfileFormFields.tsx`
- `frontend/src/features/profile/profileValidation.ts`
- `frontend/src/features/publicOnboarding/GuidedTrainingQuestions.tsx`
- `frontend/src/features/publicOnboarding/PublicOnboardingPage.tsx`
- `frontend/src/features/publicOnboarding/onboardingDraft.ts` if needed
- `frontend/src/i18n/fa.ts`
- `frontend/src/i18n/en.ts`
- corresponding tests

### Requirements

- form-level singular state preferred;
- use single-choice UI, not checkboxes;
- display only approved focus muscles;
- no upper/lower/legs regional focus option;
- guided onboarding asks the focus question;
- edit profile uses the same list/contract;
- wire payload remains API-compatible if backend still expects an array;
- null/no-focus remains representable if optional;
- no silent multi-value form state.

### Tests

- only one option can be selected;
- selecting a second replaces the first;
- serialized payload contains max one value;
- profile edit round-trip preserves one value;
- guided onboarding draft survives save/load/hydration with focus intact;
- Persian/English labels exist.

---

## Luna Task D — Canonical focus-topology affinity layer

**Goal:** stop treating broad compatibility as full priority quality.

### Files

- new `backend/app/workouts/program_engine/focus_topology.py` or equivalent
- `backend/app/workouts/program_engine/priority_allocation.py`
- possibly `slot_compatibility.py` imports only if clean
- tests in `test_priority_allocation.py` and a new focused topology test module if useful

### Requirements

- define deterministic affinity between a session focus and one selected muscle;
- dedicated/grouped/broad distinction;
- `upper` remains valid compatibility but lower priority-ranking value;
- `full_body` even lower priority-ranking value in high-frequency experienced cohort;
- recovery logic remains based on actual muscle exposure, not the new ranking affinity;
- body-analysis priorities remain separate from explicit user focus and continue to function.

### Critical regression

For one selected focus such as chest:

```text
chest_triceps
```

must be a stronger topology match than:

```text
upper
```

and two broad Upper sessions must not be scored as equivalent to two dedicated chest exposures.

Repeat representative assertions for:

- back
- shoulders
- quadriceps
- hamstrings or glutes

---

## Luna Task E — Dynamic 4/5/6-day focused split topology

**Goal:** make focused candidates exist and rank correctly.

### Files

- `backend/app/workouts/program_engine/split_selector.py`
- `backend/app/workouts/program_engine/enums.py` if needed
- `backend/app/workouts/program_engine/rulesets/resistance_training_v1.py`
- split/priority tests

### Requirements

#### 4 days

Ensure candidate equivalent to:

```text
push
pull
quadriceps_calves
posterior_chain_core
```

exists and is eligible for Intermediate/Advanced.

#### 5 days

Ensure candidate equivalent to:

```text
chest_triceps
back_biceps
quadriceps_calves
shoulders_traps
posterior_chain_core
```

exists.

#### 6 days

Keep PPL×2 and focused body-part options; rank them above Upper/Lower×3 for normal Intermediate/Advanced cases when feasible.

### Scoring

- add ruleset-owned experienced/high-frequency focused preference;
- add broad-upper penalty only in target cohort;
- selected focus affinity participates in ranking;
- duration infeasibility still outranks score preference;
- recovery-limited users may fall back;
- no magic constants outside the ruleset.

### Reason codes

Add stable reason codes equivalent to:

```text
SPLIT_FOCUSED_TOPOLOGY_PREFERRED_FOR_EXPERIENCED_HIGH_FREQUENCY
SPLIT_SELECTED_FOCUS_MATCH
SPLIT_BROAD_UPPER_DOWNRANKED_FOR_HIGH_FREQUENCY
SPLIT_FOCUSED_TOPOLOGY_CONSTRAINED
```

Names may differ but must be stable and observable.

---

## Luna Task F — Template ranking and single-focus specialization

**Goal:** template-first execution must obey the same new policy.

### Files

- `backend/app/workouts/program_engine/template_scoring.py`
- `backend/app/workouts/program_engine/template_selector.py`
- `backend/app/training_templates/tags.py`
- `backend/app/training_templates/seed_data.py` only where evidence requires retagging
- template tests

### Requirements

1. Extend template score/result with topology quality or equivalent.
2. Reuse the same focus-affinity semantics from Task D.
3. Rewrite/remove the old 4-day helper that assumes “two or more explicit upper priorities” as the trigger for special topology.
4. A single chest/back/shoulder/quads/hamstrings/glutes focus must be enough to affect ranking meaningfully.
5. `t08-4-day-push-pull-quads-posterior` should be competitive/preferred for suitable 4-day experienced users.
6. `t10-5-day-classic-body-part` should be strongly competitive for ordinary 5-day Intermediate/Advanced users.
7. `t15-6-day-ppl-2x` should be strong for suitable 6-day Intermediate/Advanced users.
8. `t16-6-day-advanced-body-part` should be a strong default candidate for suitable 6-day Advanced users.
9. Exact muscle specialization templates should win when the selected focus and feasibility support them.
10. Do not add unsupported tags just to increase a score; every tag must satisfy template structural evidence.

### `tags.py` audit

Existing exact tags cover chest/back/shoulders/arms/glutes/quads/hamstrings.

If user-selectable calves/traps/abs need exact template priority ranking, decide whether:

- direct day-target topology scoring is sufficient; or
- a new structural tag is justified.

Prefer topology evidence over tag proliferation.

---

## Luna Task G — Engine integration / template-first arbitration

**Goal:** prove the full engine picks the right plan, not only unit-level rankings.

### File

- `backend/app/workouts/program_engine/engine.py`
- integration tests

### First preference

Do **not** rewrite engine flow if Tasks D–F make template ranking and dynamic ranking sufficient.

### If evidence shows template-first still defeats a clearly superior focused plan

Introduce the smallest architecture-consistent arbitration layer.

Possible acceptable direction:

- rank template candidates with the new shared topology score so a suitable focused template is first;
- only compare template vs dynamic top candidate if there is no clean way to express the policy inside template ranking.

Do not duplicate whole program construction merely to compare paths.

### End-to-end proof

`generate_program(...)` must demonstrate final selected topology for 4/5/6-day representative profiles.

---

## Luna Task H — Coach-quality gate and observability

**Goal:** prevent silent regression after ranking is fixed.

### Inspect

- `backend/app/workouts/program_engine/final_gate.py`
- `backend/app/workouts/program_engine/coach_quality.py`
- decision trace structures

### Required behavior

For Intermediate/Advanced 4–6 day plans:

- if a focused topology was selected, expose the reason;
- if a broad Upper/Lower topology was selected instead, expose why the focused alternative was constrained when that information is available;
- do not silently accept “broad upper won because it got more fake priority exposure score.”

Do not create a brittle final gate that rejects valid constrained plans without access to alternative-feasibility evidence.

Prefer observability + a targeted quality invariant over blind hard rejection.

---

## Luna Task I — Regression matrix

Create/extend focused regression coverage across the full matrix.

### Cohort matrix

At minimum include:

#### 4 days

- Intermediate, focus chest
- Intermediate, focus back
- Intermediate, focus shoulders
- Advanced, focus quadriceps
- Advanced, focus hamstrings

Expected normal behavior:

- a focused Push/Pull/Quads/Posterior or similarly coherent structure wins;
- generic Upper/Lower is not the normal winner when focused candidate is feasible;
- chest and back are not both forced into the same generic upper session by default.

#### 5 days

- Intermediate, focus chest
- Intermediate, focus back
- Advanced, focus shoulders
- Advanced, focus quadriceps
- Advanced, focus hamstrings/glutes

Expected:

- focused body-part/specialization topology;
- chest day and back day separate;
- shoulders receive coherent placement;
- quad/posterior separation when feasible.

#### 6 days

- Intermediate, focus chest or back
- Intermediate, focus legs-derived concrete muscle (quadriceps or hamstrings)
- Advanced, focus chest
- Advanced, focus shoulders
- Advanced, focus glutes/hamstrings

Expected:

- Intermediate: PPL×2 or focused body-part topology preferred over Upper/Lower×3;
- Advanced: advanced body-part/focused topology strongly preferred when feasible.

### Non-regression matrix

Also prove:

- 2-day novice still works;
- 3-day beginner/full-body remains valid;
- first-month behavior remains simple;
- recovery-limited experienced user can fall back appropriately;
- limited-equipment home user can fall back;
- caution/injury safety remains fail-closed;
- selected number of resistance days is preserved when feasible;
- determinism remains stable regardless of catalog iteration order.

---

## Luna Task J — Frontend + API end-to-end regression

**Goal:** prove product input really reaches the engine as one focus.

Test flow:

```text
Public onboarding
→ choose one focus
→ draft save/load
→ account hydration/profile create
→ profile read
→ WorkoutGenerationService._to_program_request
→ ProgramGenerationRequest.priority_muscles
→ PriorityAllocationPolicy
```

Assert exactly one explicit user priority survives the full path.

Also test profile-edit replacement:

```text
old focus: chest
new focus: shoulders
```

Result must be exactly shoulders, not `[chest, shoulders]`.

---

## Luna Task K — Full verification and regenerated evidence

Run project-authoritative commands from `AGENTS.md`.

### Backend

```bash
cd backend
uv sync
ruff check
ruff format --check
mypy
pytest
```

### Frontend

```bash
cd frontend
npm install
npm run lint
npm run test
npm run build
```

Then:

1. run the focused 4/5/6 regression matrix;
2. run the existing workout-engine reference/golden profile suites;
3. run the current 10-profile production-path harness/report generator if present;
4. ensure the report runner still uses the production mapper and deterministic engine path;
5. inspect the actual generated plans, not only test exit codes;
6. confirm decision traces explain the selected split/template.

If the 10 random profiles do not include enough Intermediate/Advanced 4/5/6-day cases, add a **separate deterministic focused-split regression batch** rather than relying on luck from random sampling.

---

# 7. Required Test Files to Inspect/Extend

Sol should assign Luna tasks to the smallest relevant modules, especially:

## Backend profile

- `backend/tests/profile/test_schemas.py`
- `backend/tests/profile/test_profile_api.py`
- `backend/tests/profile/test_profile_update_api.py`

## Backend workout engine

- `backend/tests/workouts/program_engine/test_priority_allocation.py`
- `backend/tests/workouts/program_engine/test_split_volume.py`
- `backend/tests/workouts/program_engine/test_selection_sessions.py`
- `backend/tests/workouts/program_engine/test_template_scoring.py`
- `backend/tests/workouts/program_engine/test_template_selector_baseline.py`
- `backend/tests/workouts/program_engine/test_template_reference.py`
- `backend/tests/workouts/program_engine/test_template_selection_trace.py`
- `backend/tests/workouts/program_engine/test_coach_quality_regressions.py`
- `backend/tests/workouts/program_engine/test_recovery_exposure_load.py`
- `backend/tests/workouts/program_engine/test_regression_profiles.py`
- `backend/tests/workouts/program_engine/test_workout_engine_reference_profiles.py`

## Frontend profile

- `frontend/src/features/profile/OnboardingPage.test.tsx`
- `frontend/src/features/profile/ProfilePage.test.tsx`
- `frontend/src/features/profile/profileValidation.test.ts`
- `frontend/src/features/profile/api.test.ts`
- `frontend/src/features/profile/ProfileContext.test.tsx` if state shape changes

## Public onboarding

- `frontend/src/features/publicOnboarding/GuidedTrainingQuestions.test.tsx`
- `frontend/src/features/publicOnboarding/PublicOnboardingPage.test.tsx`
- `frontend/src/features/publicOnboarding/onboardingDraft.test.ts`

Prefer extending existing test modules over creating many duplicate test files unless isolation clearly improves maintainability.

---

# 8. Sol Review Checklist After Every Luna Task

Before accepting a Luna result, Sol must inspect the diff and answer:

1. Did it fix a root cause or only special-case one fixture?
2. Did it preserve determinism?
3. Did it preserve safety and equipment filtering?
4. Did it preserve requested training-day count when feasible?
5. Did it introduce raw display-name matching?
6. Did it add magic constants outside the ruleset/policy?
7. Did it mistakenly change `focus_scope("upper")` compatibility to solve a ranking problem?
8. Did it preserve valid Upper/Lower for low-frequency/novice/constrained users?
9. Does the single-focus rule exist in backend validation, not only frontend UI?
10. Can a profile PATCH still sneak through multiple priorities?
11. Does public onboarding actually collect the focus?
12. Does profile editing remain single-select?
13. Does template-first selection obey the same focused-split policy as dynamic selection?
14. Are chest/back major groups separated by default in the target cohort?
15. Are quads/posterior lower-body focuses separated when weekly frequency allows it?
16. Does the selected focus materially change ranking/volume rather than being display-only metadata?
17. Are reason codes/decision traces understandable?
18. Did the task change unrelated nutrition/auth/body-analysis behavior?
19. Are tests behavioral, not implementation-detail-only?
20. Did the Luna run the smallest relevant checks before handing back?

Reject or correct any task that fails these checks.

---

# 9. Non-Negotiable Constraints

- Preserve deterministic generation.
- Preserve safety-first behavior.
- Never bypass caution/injury filtering to make a focused split constructible.
- Never select unavailable equipment.
- Do not silently reduce requested resistance days.
- Do not hard-code user names, fixture IDs, or exact random-profile seeds in production logic.
- Do not use Persian/English exercise display names for engine decisions.
- Do not globally ban Upper/Lower.
- Do not globally ban Full Body.
- Do not interpret a user focus as permission to neglect full-program muscle coverage.
- Do not create junk volume merely to fill session duration.
- Do not create a new database migration unless the current persisted data/schema requires it.
- Do not silently truncate legacy multi-priority rows.
- Do not add duplicate templates when existing canonical templates already express the desired topology.
- Do not make template and dynamic ranking policies diverge.
- Do not weaken recovery spacing.
- Do not collapse direct muscle focus and indirect synergist exposure into the same score.
- Keep new thresholds/weights centralized in ruleset/policy.
- Preserve stable reason codes and decision trace.

---

# 10. Acceptance Criteria — Product Input

Do not declare completion until all are true:

- User can choose no focus or exactly one focus according to approved UX.
- User cannot select multiple focus muscles in profile edit.
- User cannot select multiple focus muscles in public onboarding.
- New API create/update requests containing more than one focus are rejected.
- Broad upper/lower regions are not accepted as user muscle focus.
- `legs` is not offered as a broad focus where quads/hamstrings are separately available.
- Public onboarding visibly asks the single-focus question.
- Profile edit visibly uses the same single-focus vocabulary.
- Wire/storage compatibility is intentional and tested.
- Legacy multi-focus data has an explicit audited handling strategy.

---

# 11. Acceptance Criteria — Engine Split Behavior

For normal safe gym users with sufficient exercise catalog coverage:

## Intermediate, 4 days

A focused 4-day split such as:

```text
Push / Pull / Quads / Posterior
```

must rank above generic Upper/Lower when both are feasible.

## Advanced, 4 days

Focused Push/Pull/body-part topology must normally win over broad Upper/Lower unless a hard feasibility/recovery reason says otherwise.

## Intermediate, 5 days

A focused body-part topology with separate chest/back and separate quad/posterior emphasis must normally win over broad Upper/Lower hybrids.

## Advanced, 5 days

Classic body-part or focus-specific specialization must normally win when feasible.

## Intermediate, 6 days

PPL ×2 or another focused topology must normally rank above Upper/Lower ×3.

## Advanced, 6 days

Advanced body-part/focused split must be a top/default structure when feasible; PPL ×2 remains valid.

Across all target cases:

- chest and back are not normally bundled into a generic `upper` session;
- selected focus receives appropriate direct/grouped exposure;
- broad `upper` cannot win merely by collecting full priority-frequency credit for many muscles;
- quads and hamstrings/posterior can have separate emphasis at high weekly frequency;
- recovery remains valid on actual weekdays;
- duration remains within accepted quality policy;
- equipment/safety constraints can override preference with an explicit reason.

---

# 12. Acceptance Criteria — Non-Regression

- 2-day programming remains valid.
- 3-day Full Body remains valid where appropriate.
- First-month and Beginner behavior is not made unnecessarily complex.
- Home/bodyweight-limited users still construct safely or fail honestly.
- Existing injury/caution regressions remain green.
- Semantic duplicate prevention remains green.
- Session-duration repair remains green.
- Push-up/pull-up ordering regressions remain green.
- Weekly coverage and volume regressions remain green.
- Body-analysis influence still works and remains separate from explicit user focus.
- Template catalog validation remains green.
- Frontend RTL/Persian behavior remains correct.
- Full backend and frontend checks are green.

---

# 13. Final Evidence Sol Must Review Personally

Sol must not rely solely on Luna summaries.

Before final completion, Sol must personally inspect:

1. final diff across all touched files;
2. the centralized single-focus policy;
3. one backend profile create/update test proving max-one focus;
4. one frontend UI test proving replacement rather than accumulation;
5. 4-day Intermediate final `generate_program(...)` output;
6. 5-day Intermediate/Advanced final output;
7. 6-day Intermediate final output;
8. 6-day Advanced final output;
9. decision trace for at least one focused split selection;
10. one constrained case where broad fallback is justified;
11. full test/lint/typecheck/build results;
12. regenerated profile report/harness evidence.

If any target cohort still frequently receives broad Upper/Lower without a real hard constraint, continue debugging. Do not declare success based solely on unit tests.

---

# 14. Required Final Report From Sol

Keep the final report concise and evidence-based.

Report exactly:

## Product contract

- final user-selectable focus list;
- whether focus is optional or required;
- how legacy multi-focus rows are handled;
- whether DB migration was necessary.

## Engine architecture

- new topology-affinity concept;
- changes to priority scoring;
- changes to template ranking;
- changes to dynamic split candidates;
- reason codes added.

## Behavioral proof

For each:

- 4d Intermediate
- 4d Advanced
- 5d Intermediate
- 5d Advanced
- 6d Intermediate
- 6d Advanced

show:

```text
selected split/template
selected user focus
day focuses
why it won over broad Upper/Lower
```

## Verification

- backend commands + result;
- frontend commands + result;
- focused regression matrix result;
- 10-profile/report result;
- remaining known limitations, if any.

Do not say “completed” unless evidence is green.

---

# 15. Execution Order Summary

Sol should execute in this order:

```text
A. Baseline + failing tests
B. Backend single-focus contract
C. Frontend single-select + public onboarding
D. Shared focus-topology semantics
E. Dynamic 4/5/6 split candidates + scoring
F. Template scoring/selection
G. Engine integration if still needed
H. Coach-quality observability
I. 4/5/6 regression matrix
J. Product path end-to-end focus propagation
K. Full verification + regenerated evidence
```

Do not let a Luna jump directly to “increase BODY_PART_ROTATION bonus” without completing Tasks A and D first. The original problem is architectural: broad focus compatibility is being reused as priority-ranking quality.

---

# 16. Core Design Principle

The desired final model is:

```text
User chooses ONE muscle priority
        ↓
Profile/API preserves ONE explicit priority
        ↓
Engine distinguishes session compatibility from priority affinity
        ↓
4/5/6-day experienced users strongly prefer focused topology
        ↓
Template and dynamic paths use the same policy
        ↓
Safety / recovery / duration / equipment can override
        ↓
Decision trace explains the result
```

The implementation is correct when Fitsho behaves like a competent coach choosing an appropriate weekly structure first, instead of maximizing the number of broad “muscle covered” ticks inside generic Upper sessions.
