# Fitsho Nutrition Engine — 90%+ Generation Success Roadmap

**Target implementer:** Luna Max  
**Repository:** `mohammad4242/fitsho`  
**Audited branch:** `main`  
**Audited commit:** `fd68ac2d17f1e3010665d88029d661d541704d01`  
**Primary scope:** `backend/app/nutrition/`, its tests, and the 100-profile nutrition audit script  
**Primary release objective:** make the deterministic Nutrition Engine reliably produce the **best safe feasible weekly plan**, not merely the first plan that happens to build.

---

## 0. Execution directive

Read this roadmap completely before editing code.

Then execute it **in the exact stage order below**:

1. **Candidate Architecture + Best-Plan Selection**
2. **Template Substitution**
3. **Budget Optimization + Economical Candidate Repair**
4. **Goal-Contract Repair**
5. **Portion / Macro Solver + Dynamic Rescaling**
6. **Micronutrient Quality + Variety + Preferences / Adherence**
7. **Safety Regression Protection + Reproducible >90% Audit Gates**

Do not reorder the stages. Later stages intentionally build on abstractions introduced earlier.

Before editing:

```bash
git status --short
cat AGENTS.md
cd backend
```

Follow the repository's existing backend workflow from `AGENTS.md`:

```bash
pytest
ruff check
mypy
```

Run focused tests after every stage, then run the complete Nutrition test suite before moving to the next stage.

Do not discard, reset, overwrite, or "clean up" unrelated working-tree changes.

Continue through the roadmap until completion. Ask the user only if a genuine ambiguity requires a product decision that cannot be resolved from the repository or this roadmap.


## 0.1 Freeze the baseline before the first code change

Before Stage 1, run the current historical 100-profile audit **without modifying planner behavior** and save a baseline artifact containing:

```text
git commit
planner version
planner policy version
profile seed
raw success rate
automatically eligible success rate
safe resolution rate
failure histogram
mean/p50/p95 generation latency
```

This baseline is not a repair stage and does not change the required stage order. It exists so every later improvement can be measured against the exact same cohort rather than memory or a regenerated sample.

Also freeze a second independent **holdout cohort definition** now, before tuning begins. Do not inspect individual holdout failures while implementing Stages 1–6. The holdout is used only at final acceptance so the engine is not accidentally overfit to the original 100 profiles.

Recommended holdout size:

```text
200–500 deterministic profiles
```

The original 100-profile cohort remains the development/regression cohort because it preserves direct historical comparison.

---

# 1. Desired end-state

The current planner behaves too much like:

```text
choose one program
    ↓
try to build it once
    ↓
fail or persist it
```

The target architecture must behave like:

```text
profile + safety decision
        ↓
scientific nutrition targets
        ↓
load active programs + verified foods + verified meals + prices
        ↓
enumerate ALL active approved program candidates
        ↓
for every candidate
    adapt meal-count structure
        ↓
    build scheduled week
        ↓
    safely substitute unavailable/incompatible scheduled meals
        ↓
    construct initial portions
        ↓
    repair micronutrients
        ↓
    repair budget
        ↓
    rebalance calories/macros within portion bounds
        ↓
    full hard validation
        ↓
    calculate deterministic candidate quality
        ↓
collect every candidate result
        ↓
admit only SUCCESS candidates
        ↓
compare all admitted candidates
        ↓
select BEST candidate
        ↓
persist only winner + bounded selection trace
```

The core model is:

> **Generate → Validate → Repair → Score → Select Best**

There must be **no `break` after the first successful program**.

---

# 2. Release metrics

Report these metrics separately. Never manipulate the denominator to make the result look better.

### 2.1 Raw generation success rate

```text
successful generations / all audit profiles
```

This keeps comparison with the historical 100-profile audit honest.

### 2.2 Automatically eligible generation success rate

```text
successful generations /
profiles that the existing safety policy allows to receive an automatic plan
```

Exclude only profiles that the pre-existing safety system explicitly routes to manual/physician handling or hard-blocks.

Do **not** exclude a profile merely because it has:

- a strict budget,
- allergies/intolerances,
- vegetarian/vegan requirements,
- a difficult macro target,
- a goal mismatch,
- missing scheduled meals,
- or any ordinary planner failure.

Those are exactly the cases this repair must improve.

### 2.3 Safe resolution rate

```text
(successful automatic plans + correctly safety-routed profiles) / all profiles
```

### Required acceptance gates

The implementation is not complete until:

```text
automatically_eligible_success_rate > 90%
safe_resolution_rate == 100%
allergy_violations == 0
dietary_pattern_violations == 0
medical_safety_violations == 0
strict_budget_violations == 0
determinism_failures == 0
```

Also assert:

```text
selected_candidate.sort_key <= first_valid_candidate.sort_key
```

for every case where at least one candidate succeeds.

---

# 3. Non-negotiable engineering rules

These rules apply to every stage.

1. **Never weaken safety constraints to increase success rate.**
   - allergies,
   - intolerances/excluded terms,
   - dietary pattern,
   - medical screening,
   - nutrient upper limits,
   - verified-food requirements,
   - strict-budget semantics.

2. **Never convert a strict budget into flexible.**

3. **Do not widen calorie or macro tolerances just to improve the audit score.**
   Current policy values should remain scientifically meaningful. Improvements should come from better search and repair.

4. **Do not use an LLM inside the deterministic planner.**
   An LLM must not choose:
   - foods,
   - meals,
   - grams,
   - targets,
   - safety outcomes,
   - prices,
   - or the final winning plan.

5. **Do not use `user_id`, UUID modulo, randomness, current time, or DB row order to choose the winner.**

6. **Do not stop after the first successful candidate.**

7. **Do not persist full losing plans.**
   Persist only:
   - final winner,
   - compact candidate summaries,
   - failure counts,
   - selection diagnostics.

8. **Do not catch broad `Exception` around candidate generation.**
   Expected planner failures must become typed deterministic domain outcomes. Unexpected failures must remain visible.

9. **Do not treat missing micronutrient data as zero.**
   Missing data is uncertainty, not proof of deficiency and not proof of adequacy.

10. **Keep `NutritionDietStyle` and `DietaryPattern` separate.**
    - `NutritionDietStyle` describes program style.
    - `DietaryPattern` is a user compatibility/safety constraint.
    Do not create program styles such as VEGAN merely to solve compatibility.

11. **Do not explode the weekly program catalogue into diet-specific copies.**
    Solve compatibility with safe meal substitution.

12. **Do not add a database migration unless the existing model genuinely cannot store the required information.**
    The current generation diagnostics JSON is sufficient for the candidate-selection trace described below.

13. **Pure planner modules must remain pure.**
    SQLAlchemy/session queries belong in the orchestration/service layer, not in scoring/solver modules.

14. **Bump planner/policy version identifiers whenever planner semantics materially change.**
    Do not silently keep old version labels for a different algorithm.

---


# 4. Scientific policy guardrails

The search/repair architecture may change aggressively, but the scientific target layer must not be tuned merely to make the audit pass.

The engine should behave as a sports-nutrition planner, not as a score optimizer that learns to exploit its own tolerances.

## 4.1 Evidence hierarchy

When Luna changes a scientific target, range, or interpretation, use this evidence priority:

```text
1. major professional position stand / consensus statement
2. systematic review or meta-analysis
3. high-quality randomized or controlled evidence
4. authoritative Dietary Reference Intake / national reference standard
5. single observational or mechanistic paper only when stronger evidence is unavailable
```

Do not convert bodybuilding folklore, social-media advice, or one coach's preference into a hard medical/nutrition constraint.

Record every material scientific-policy change through the repository's existing version/source-manifest mechanism.

## 4.2 Protein guardrails

For healthy resistance-trained adults, the implementation must preserve the distinction between:

```text
minimum acceptable protein
preferred target
context-specific higher target
```

Evidence anchors to use when validating the existing target engine:

- Morton et al., 2018, *British Journal of Sports Medicine*, meta-analysis of protein supplementation during resistance training. The population-level benefit for fat-free-mass gain plateaued around roughly **1.6 g/kg/day**, with uncertainty above that point. PMID: `28698222`.
- Jäger et al., 2017, International Society of Sports Nutrition position stand. A common evidence-based daily range for exercising adults is approximately **1.4–2.0 g/kg/day**, with context-dependent higher intakes potentially useful during energy restriction. PMID: `28642676`.
- Helms et al., 2014, natural bodybuilding contest-preparation review, is relevant when very lean resistance-trained athletes are dieting and preserving lean mass; do not apply contest-prep protein targets blindly to ordinary users.

Implementation rules:

1. Do not hardcode one protein number for every user.
2. Do not use target body weight, actual body weight, or fat-free mass interchangeably without an explicit policy rule.
3. Energy deficit, training status, body composition and goal may change the preferred target.
4. A higher protein target is not a reason to violate calorie, renal/medical, budget, dietary-pattern or tolerance constraints.
5. Existing medical safety policy has precedence over generic sports-nutrition ranges.

## 4.3 Energy balance / fat-loss / muscle-gain guardrails

Use energy balance as the primary driver of expected weight change.

Evidence anchor:

- Aragon et al., 2017, ISSN position stand on diets and body composition. Sustainable energy deficit is central to fat loss; adherence and individual context matter, and no single named diet pattern is universally superior. PMID: `28630601`.

Implementation rules:

- do not make one arbitrary fixed percentage deficit/surplus the only valid value for all users;
- keep a preferred target plus safe acceptable corridor;
- slower loss should be available when lean-mass retention is a priority;
- muscle gain/recomposition logic must consider actual resistance-training stimulus but must not unnecessarily block safe nutrition generation;
- never claim a nutrition plan alone guarantees hypertrophy without an appropriate training stimulus.

## 4.4 Sports-performance context

Evidence anchor:

- Thomas, Erdman & Burke, 2016, Academy of Nutrition and Dietetics / Dietitians of Canada / ACSM joint position paper on nutrition and athletic performance. PMID: `26920240`.

Implementation rules:

- total daily energy and protein adequacy come before timing optimizations;
- structured exercise can influence carbohydrate distribution and meal timing;
- workout timing is a **soft quality preference** unless a specific safety rule requires otherwise;
- do not fail an otherwise safe plan just because nutrient timing is not theoretically perfect.

## 4.5 Protein distribution as a soft quality signal

If the current food data and meal structure are sufficient, Stage 6 may score protein distribution across meals.

A reasonable evidence-based concept is multiple meaningful protein feedings distributed across the day rather than placing nearly all protein in one meal. The exact per-meal target must be policy-versioned and should follow the ISSN/ACSM evidence base; do not turn a literature range into a rigid failure condition.

Rules:

```text
TOTAL DAILY PROTEIN = core target
PER-MEAL DISTRIBUTION = soft plan-quality signal
```

Do not make a candidate infeasible solely because one meal falls outside an ideal per-meal distribution range if the total plan is otherwise safe and nutritionally strong.

## 4.6 Micronutrient reference semantics

Preserve the distinction among:

```text
EAR = Estimated Average Requirement
RDA = Recommended Dietary Allowance
AI  = Adequate Intake
UL  = Tolerable Upper Intake Level
```

Use authoritative DRI/reference sources through the repository's versioned micronutrient source model. NIH Office of Dietary Supplements / National Academies DRI materials are appropriate reference anchors.

Rules:

- RDA/AI are adequacy concepts, not values that should be maximized without bound;
- UL is a safety ceiling, not a target;
- many micronutrients are better assessed over a weekly/rolling window than by forcing every single day to equal the reference;
- missing nutrient data is uncertainty and must never be silently converted to zero or perfect adequacy.

## 4.7 Optimization is allowed to search harder, not to change science

The optimization system may:

```text
search more programs
substitute compatible meals
change portions within verified bounds
find lower-cost combinations
repair macros/micronutrients
rank adherence/variety
```

It may **not**:

```text
change a protein target because it is inconvenient
widen a calorie corridor because a template does not fit
ignore a UL to get a higher score
silently raise the budget
change the user's dietary pattern
```

Scientific target generation and search optimization are separate layers.

---

# 5. Current repository findings

This roadmap is based on the current Nutrition Engine at the audited commit.

## 5.1 `backend/app/nutrition/program_selection.py`

The current production path chooses exactly one program.

Current behavior:

```text
_select_style(context)
    ↓
filter programs to that style
    ↓
sort by program code
    ↓
choose one using user_id.int % len(candidates)
```

This is not best-plan selection.

The UUID modulo is deterministic, but it is nutritionally meaningless. A user's UUID must never determine which otherwise-feasible diet program is returned.

The program style should become a **soft preference**, not a hard candidate filter.

---

## 5.2 `backend/app/nutrition/plan_service.py`

`generate_weekly_plan(...)` currently performs approximately:

```text
safety
→ scientific targets
→ load foods/meals/programs
→ select_program once
→ adapt that program
→ build one template schedule
→ plan_week once
→ persist success or failure
```

This is the main orchestration bottleneck.

The service must become the coordinator of a multi-candidate search.

Also inspect existing diagnostic names carefully. The current code already uses candidate-like terminology for food candidate counts. Do not create ambiguous fields.

Prefer explicit names such as:

```text
food_candidate_count
program_candidate_count
evaluated_program_candidate_count
successful_program_candidate_count
```

---

## 5.3 `backend/app/nutrition/planner_engine.py`

The planner already performs useful safety-compatible filtering before plan construction:

- valid price coverage,
- mandatory nutrient fields,
- excluded-term filtering,
- dietary-pattern filtering,
- required-template ingredient eligibility.

Preserve that behavior.

However, scheduled weekly programs reference exact Meal Catalogue IDs.

If a scheduled meal disappears from the eligible pool because one of its required foods is incompatible, the current scheduled builder can fail with:

```text
Scheduled Meal Catalogue template is unavailable: ...
```

That converts a recoverable meal incompatibility into a complete program failure.

The current portion logic also roughly:

1. scales a meal template toward target energy;
2. clamps each ingredient independently to its min/max grams.

Independent clamping can distort the macro ratio after scaling. The planner can then reject the entire plan instead of solving the remaining calorie/macro error.

Current budget repair is also narrower than the required target architecture; it does not globally search cheaper compatible weekly alternatives before final rejection.

---

## 5.4 `backend/app/nutrition/planner_policy.py`

Current important identifiers include:

```python
PLANNER_POLICY_VERSION = "weekly-planner-v1"
MEAL_DISTRIBUTION_POLICY_VERSION = "meal-distribution-v1"
PORTION_POLICY_VERSION = "portion-bounds-v1"
PLANNER_VERSION = "deterministic-heuristic-v2"
```

Current policy already defines important constraints such as:

- flexible budget overage cap,
- calorie tolerance,
- macro tolerance,
- portion bounds,
- micronutrient repair iteration count,
- price-age limits,
- candidate score weights.

Preserve the meaning of existing safety/feasibility limits. Add new repair/search limits explicitly instead of hiding them in magic constants.

---

## 5.5 `backend/app/nutrition/scientific.py`

The current target-generation contract contains goal/training combinations that can cause hard reselection failure.

Examples include:

- `FitnessGoal.IMPROVE_FITNESS`,
- physique/strength-oriented goals whose current training stimulus is not considered suitable.

A mismatch between a user's training behavior and ideal training for their goal should normally produce:

```text
safe nutrition target + coaching warning
```

not:

```text
nutrition plan generation unavailable
```

unless the nutrition target itself is genuinely unsafe or impossible to calculate.

---

## 5.6 `backend/app/nutrition/program_adaptation.py`

This module correctly operates on the selected weekly program structure and adapts meal/snack counts.

Keep that responsibility here.

Do **not** put allergy/vegan substitution logic here. At this point the code does not yet have the planner's final safe eligible-template pool.

Template substitution belongs after eligibility filtering.

---

## 5.7 `backend/app/nutrition/program_catalogue_seed_data.py`

The file explicitly contains the canonical Meal UUID registry and **25 approved weekly program matrices**.

Many matrices reference exact breakfast/lunch/dinner/snack/post-workout Meal Catalogue IDs.

The correct repair is not to create dozens of duplicated "vegan program", "allergy program", etc. matrices.

The correct repair is:

```text
curated weekly program structure
+
safe compatible meal substitution
```

---

## 5.8 `backend/app/nutrition/meal_catalogue.py`

Preserve catalogue verification.

Any new fallback meal added later must still satisfy the existing Meal Catalogue rules and use valid verified food/nutrition data.

Do not let the planner construct arbitrary unverified meals merely to avoid a failure.

---

## 5.9 `backend/app/nutrition/adherence_service.py`

The repository already records useful meal feedback, including concepts equivalent to:

- liked,
- disliked,
- prefer more often,
- do not suggest again.

This data should eventually influence **quality ranking**, but it must not alter scientific targets or override safety.

Do not make the pure candidate comparator query the DB itself. Build a user-specific preference snapshot in the service layer and pass it into the pure planning/scoring path.

---

## 5.10 `backend/app/nutrition/price_mass_conversion.py`

The historical audit included a price/mass conversion crash class.

The current audited `main` already contains deterministic price-mass conversion handling that appears to address the previous class of issue.

Therefore this roadmap does **not** allocate a separate implementation stage to rewriting that module.

Keep regression coverage in:

```text
backend/tests/nutrition/test_price_mass_conversion.py
```

Change `price_mass_conversion.py` only if a current reproducible test proves that the bug still exists.

---

# 6. Target candidate admission and ranking model

Do not use one weighted scalar that allows convenience to compensate for a serious nutritional deficiency.

Use two layers.

## 6.1 Layer A — hard admission

A plan is not rankable unless the existing planner returns `SUCCESS`.

A candidate that violates any hard condition is excluded before quality comparison.

Examples:

```text
unsafe food
dietary-pattern violation
nutrient upper-limit violation
strict budget exceeded
flexible budget cap exceeded
required verified data unavailable
unrepairable calorie/macro infeasibility
```

A failure can be useful diagnostically, but it cannot compete with successful plans.

## 6.2 Layer B — deterministic lexicographic quality

For admitted candidates, use a quality vector.

Recommended final shape, lower is better:

```python
(
    core_nutrition_max_deviation,
    core_nutrition_total_deviation,
    micronutrient_gap_penalty,
    diet_quality_penalty,
    sports_nutrition_distribution_penalty,  # when supported by sufficient data
    budget_utilization_penalty,
    preference_and_feedback_penalty,
    repetition_penalty,
    warning_burden,
    repair_burden,
    substitution_burden,
    preferred_program_style_penalty,
    stable_program_code,
    stable_variant_key,
)
```

The order is intentional.

### Why lexicographic?

A plan with clearly worse nutrition should not win only because it is slightly cheaper or uses a liked food.

### Normalize nutrition deviations

Never compare:

```text
100 kcal
```

directly with:

```text
10 g protein
```

Use normalized dimensionless deviations, such as:

```python
abs(planned - preferred) / preferred
```

or a deficit-only equivalent when excessive intake is not the relevant penalty.

### Stable tie-breaking

Final tie-breaking must use stable domain data such as:

```text
program.code
meal_id / stable meal code
```

Never use:

```text
UUID modulo
Python set order
database row order
random()
current timestamp
```

---


## 6.3 Define exactly what "all candidates" means

The user requirement is that **every active approved base Nutrition Program must be evaluated**, not that the engine may stop after finding one acceptable program.

However, one base program can create more than one valid full-week plan after substitutions and repairs.

Use these terms consistently:

```text
Base Program Candidate
    = one active approved NutritionProgram matrix

Plan Variant
    = one fully constructed weekly realization of a Base Program Candidate
      after deterministic substitutions / budget repair / portion repair

Admitted Plan Variant
    = a Plan Variant that passes every hard validator
```

Mandatory search semantics:

1. **Every active approved Base Program Candidate receives an evaluation attempt.**
2. A base program may emit multiple Plan Variants when materially different safe substitutions are available.
3. Candidate selection compares **admitted full-week variants**, not merely program labels.
4. The engine must not claim to have selected the global best plan if it only evaluated one arbitrary substitution path.
5. Because exhaustive enumeration of every meal combination can explode combinatorially, use a deterministic bounded search for variants and record the search coverage in diagnostics.

Recommended bounded strategy after Stage 2:

```text
all active base programs
      ↓
for each program:
    expand safe substitution choices
      ↓
    deterministic beam / branch-and-bound search
      ↓
    keep top-K partial variants using a conservative lower-bound quality key
      ↓
    fully repair + validate surviving variants
      ↓
collect all admitted full-week variants
      ↓
select global best evaluated variant
```

The beam/branch limit is a **performance control**, not permission to stop at first-valid.

Record:

```text
base_program_candidate_count
plan_variant_count_generated
plan_variant_count_fully_evaluated
plan_variant_count_admitted
search_truncated: true|false
```

If `search_truncated == true`, diagnostics must not describe the result as mathematically proven global optimum. It is the **best evaluated feasible variant** under the versioned deterministic search policy.

Once Stage 2 introduces multiple variants per base program, extend candidate identity with a deterministic `stable_variant_key` derived only from stable domain identifiers (for example ordered replacement Meal IDs / stable action IDs). Two variants of the same program must never collapse into one diagnostic identity or tie-break only by program code.

---

# STAGE 1 — Candidate Architecture + Best-Plan Selection

## Stage objective

Before fixing template fallback or budget/macro repair, replace the current single-program orchestration with an architecture that:

- enumerates **all active approved programs**,
- evaluates every program independently,
- records both success and failure,
- never stops at the first success,
- deterministically selects the best successful result,
- persists only that winner.

This is the foundation for every later repair.

---

## Files

### CREATE

```text
backend/app/nutrition/candidate_selection.py
backend/tests/nutrition/test_candidate_selection.py
```

### MODIFY

```text
backend/app/nutrition/program_selection.py
backend/app/nutrition/plan_service.py
backend/app/nutrition/planner_engine.py
backend/app/nutrition/planner_policy.py
backend/app/nutrition/exceptions.py

backend/tests/nutrition/test_program_selection.py
backend/tests/nutrition/test_planner_engine.py
backend/tests/nutrition/test_weekly_plan_api.py
```

No schema migration should be needed for this stage.

---

## 1.1 Search call sites before refactoring

Before deleting or changing the existing selector:

```bash
rg "select_program\(" backend
rg "_select_style\(" backend
```

If a non-generation call site relies on the old API, either migrate it or retain a clearly deprecated compatibility wrapper. The production weekly-plan path must stop using the old one-program winner behavior.

---

## 1.2 Convert style from hard filter to soft preference

In `program_selection.py`, preserve the existing style inference concept but change its semantic role.

Preferred direction:

```python
@dataclass(frozen=True)
class ProgramCandidate:
    program: NutritionProgram
    preferred_style: bool
    preconstruction_rank: int
```

Add a pure function equivalent to:

```python
def enumerate_program_candidates(
    programs: Iterable[NutritionProgram],
    context: ProgramSelectionContext,
) -> tuple[ProgramCandidate, ...]:
    ...
```

Rules:

1. include every active approved program supplied by the caller;
2. do not filter candidates out merely because `diet_style` differs from the preferred style;
3. preferred style may be evaluated first;
4. within the same preference group, use stable ordering:
   ```python
   (program.code, str(program.id))
   ```
5. remove `user_id` from the selection decision;
6. remove `user_id.int % len(candidates)`;
7. do not randomize candidate order;
8. evaluate all 25 active program matrices when all 25 are active.

The existing style logic becomes a quality/tie preference, not eligibility.

---

## 1.3 Create pure candidate-selection types

In new `candidate_selection.py`, define immutable types close to:

```python
from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

@dataclass(frozen=True)
class CandidateQuality:
    core_nutrition_max_deviation: Decimal
    core_nutrition_total_deviation: Decimal
    micronutrient_gap_penalty: Decimal
    diet_quality_penalty: Decimal
    budget_utilization_penalty: Decimal
    preference_and_feedback_penalty: Decimal
    repetition_penalty: Decimal
    warning_burden: int
    repair_burden: int
    substitution_burden: int
    preferred_program_style_penalty: int
    stable_program_code: str

    def sort_key(self) -> tuple[object, ...]:
        return (
            self.core_nutrition_max_deviation,
            self.core_nutrition_total_deviation,
            self.micronutrient_gap_penalty,
            self.diet_quality_penalty,
            self.budget_utilization_penalty,
            self.preference_and_feedback_penalty,
            self.repetition_penalty,
            self.warning_burden,
            self.repair_burden,
            self.substitution_burden,
            self.preferred_program_style_penalty,
            self.stable_program_code,
        )
```

```python
@dataclass(frozen=True)
class CandidateEvaluation:
    program_id: UUID
    program_code: str
    stable_variant_key: tuple[str, ...]
    preconstruction_rank: int
    preferred_style: bool
    result: PlannerResult
    quality: CandidateQuality | None
```

```python
@dataclass(frozen=True)
class CandidateSelection:
    selected: CandidateEvaluation | None
    first_valid: CandidateEvaluation | None
    evaluations: tuple[CandidateEvaluation, ...]
```

Keep this module pure:

```text
NO Session
NO SQLAlchemy queries
NO commits
NO current time
NO randomness
```

---

## 1.4 Implement an initial quality comparator

Stage 1 must already choose the best result using the information the planner currently exposes.

Use:

```text
PlannerResult.nutrient_comparisons
PlannerResult.weekly_cost_irr
PlannerResult.budget_status
PlannerResult.warning_codes
PlannerResult.repair_actions
program style preference
program code
```

Stage 1 can temporarily set future components such as substitution burden to zero.

### Core nutrition

Compute normalized deviation components for supported core targets.

Examples:

```text
calories:
abs(planned - preferred) / preferred

protein:
max(preferred - planned, 0) / preferred
```

For nutrients represented by a min/max/range contract, penalize distance outside the desired preferred/range semantics already encoded by the existing comparison model.

Do not invent a new scientific target here.

### Missing comparison data

If a comparison that should exist is unexpectedly absent, do not make the plan look perfect by assigning zero penalty.

Use a deterministic data-quality penalty or ensure the candidate cannot receive an artificially optimal sort key.

### Micronutrients

In Stage 1, calculate a conservative normalized gap from the supported `nutrient_comparisons`.

Stage 6 will make this richer.

### Budget

For successful plans:

```python
budget_utilization = weekly_cost / weekly_budget
```

Handle zero budget explicitly; do not divide by zero.

Budget ranking comes **after nutrition quality**.

---

## 1.5 Isolate expected scheduled-template failure

Multi-candidate search only works if one broken candidate cannot abort the whole loop.

In `exceptions.py`, add a typed expected construction exception:

```python
class ScheduledTemplateUnavailableError(Exception):
    def __init__(self, meal_id: str, category: str) -> None:
        self.meal_id = meal_id
        self.category = category
        super().__init__(f"{meal_id}:{category}")
```

In `planner_engine.py`:

- replace the current generic `ValueError` used specifically for an unavailable scheduled Meal Catalogue template;
- raise `ScheduledTemplateUnavailableError`;
- at the appropriate `plan_week(...)` construction boundary, catch **this exact domain exception only**;
- convert it to a deterministic planner failure:

```python
PlannerResult(
    outcome=GenerationOutcome.INFEASIBLE,
    reason_codes=("SCHEDULED_TEMPLATE_UNAVAILABLE",),
)
```

Do not catch every `ValueError`.

Do not catch broad `Exception`.

Unexpected programmer/data-corruption errors must still fail loudly.

Stage 2 will make this failure much rarer by adding substitution.

---

## 1.6 Rewrite `generate_weekly_plan(...)` as candidate orchestration

In `plan_service.py`, separate candidate-independent data from candidate-specific data.

Build once:

```text
safety decision
scientific targets
eligible price snapshot
foods
verified meal templates
nutrition profile
selection context
base PlannerInput without one concrete schedule
```

Then enumerate all program proposals.

Target orchestration shape:

```python
proposals = enumerate_program_candidates(programs, selection_context)

evaluations: list[CandidateEvaluation] = []

for proposal in proposals:
    adapted = adapt_program(
        proposal.program,
        ...
    )

    schedule = build_template_schedule(adapted, ...)

    candidate_input = dataclasses.replace(
        base_planner_input,
        template_schedule=schedule,
    )

    result = plan_week(
        inputs=candidate_input,
        foods=foods,
        meal_templates=meal_templates,
        policy=DEFAULT_POLICY,
    )

    evaluations.append(
        evaluate_candidate(
            proposal=proposal,
            result=result,
            ...
        )
    )

selection = select_best_candidate(tuple(evaluations))
```

Mandatory details:

- do not mutate `base_planner_input` between candidates;
- no DB commit inside the candidate loop;
- do not persist `NutritionWeeklyPlan` objects for losers;
- do not persist 25 full seven-day losing plans into JSON;
- do not `break` after first success;
- record `first_valid` only for diagnostics/comparison;
- after all candidates finish, persist only `selection.selected`.

---

## 1.7 Failure aggregation when no program succeeds

If `selection.selected is None`, do not pretend one failed program was the selected plan.

Collect a stable failure summary:

```python
{
    "TARGET_INFEASIBLE": 7,
    "SCHEDULED_TEMPLATE_UNAVAILABLE": 12,
    "STRICT_BUDGET_EXCEEDED": 6,
}
```

Sort reason keys before serializing.

Use existing public outcome semantics wherever possible.

Example policy:

- if all candidates fail with live-price coverage, final generation outcome may remain `LIVE_PRICE_UNAVAILABLE`;
- otherwise use the existing appropriate non-success generation outcome;
- include candidate failure histogram in diagnostic JSON.

Do not expose a random losing `program_id`.

The existing weekly plan model already allows `program_id` to be nullable; preserve truthful persistence.

---

## 1.8 Store a bounded candidate-selection trace

Use the existing generation diagnostics JSON.

Recommended schema:

```json
{
  "selection_trace": {
    "schema_version": "nutrition-selection-trace-v1",
    "strategy": "best-admitted-all-active-programs-v1",
    "proposed_candidate_count": 25,
    "evaluated_candidate_count": 25,
    "successful_candidate_count": 6,
    "first_valid_program_code": "P04",
    "selected_program_code": "P11",
    "selected_differs_from_first_valid": true,
    "selected_quality": {
      "core_nutrition_max_deviation": "0.031",
      "core_nutrition_total_deviation": "0.082",
      "budget_utilization_penalty": "0.71"
    },
    "failure_reason_counts": {
      "SCHEDULED_TEMPLATE_UNAVAILABLE": 8,
      "STRICT_BUDGET_EXCEEDED": 4
    },
    "candidates": [
      {
        "program_code": "P01",
        "variant_key": "base",
        "outcome": "infeasible",
        "reason_codes": ["SCHEDULED_TEMPLATE_UNAVAILABLE"],
        "quality": null
      },
      {
        "program_code": "P04",
        "variant_key": "base",
        "outcome": "success",
        "reason_codes": ["SAFE_FEASIBLE_DRAFT_GENERATED"],
        "quality": {
          "core_nutrition_max_deviation": "0.055"
        }
      }
    ]
  }
}
```

Do not put every losing meal/food gram into this trace.

---

## 1.9 Versioning

After Stage 1 changes production selection semantics, bump planner selection/version metadata.

Do not silently keep a version that describes the old single-program behavior.

Use a name that clearly indicates all-candidate best selection, for example:

```text
deterministic-candidate-search-v1
```

Follow the repository's existing policy-version persistence conventions.

---

## 1.10 Stage 1 tests

### `test_program_selection.py`

Add tests proving:

- all active supplied programs are enumerated;
- style mismatch does not exclude a program;
- preferred style is ordered first only as a preference;
- result order is deterministic;
- different `user_id` values cannot alter program proposal order;
- UUID modulo is gone from production selection.

### `test_candidate_selection.py`

Add tests proving:

- failed candidates cannot be selected;
- a later successful candidate can beat the first valid candidate;
- all successful candidates are compared;
- nutrition quality beats cost preference;
- deterministic program-code tie break works;
- missing comparison data does not become zero-cost perfection;
- selected sort key is <= first-valid sort key.

### `test_weekly_plan_api.py`

Use mocks/spies only where appropriate to prove:

- generation continues after the first success;
- every active candidate is attempted;
- only one final plan is persisted;
- losing candidates are not persisted as plans;
- diagnostics include candidate counts and selected/first-valid codes;
- no-success result includes aggregate failure diagnostics.

### Stage exit gate

Do not proceed to Stage 2 until focused tests pass and a controlled profile proves:

```text
evaluated_program_candidate_count == active_program_count
```

even when the first program succeeds.

Suggested commit:

```text
nutrition: evaluate all program candidates and select best
```

---

# STAGE 2 — Template Substitution

## Stage objective

Eliminate the largest recoverable failure class:

```text
scheduled program references meal X
↓
meal X becomes ineligible after diet/allergy/exclusion filtering
↓
entire candidate fails
```

New behavior:

```text
scheduled meal unavailable
↓
search already-safe eligible templates for compatible replacement
↓
rank replacements deterministically
↓
try best compatible replacement
↓
continue constructing candidate
```

Do not bypass eligibility to preserve the original meal.

---

## Files

### CREATE

```text
backend/app/nutrition/template_substitution.py
backend/tests/nutrition/test_template_substitution.py
```

### MODIFY

```text
backend/app/nutrition/planner_engine.py
backend/app/nutrition/planner_policy.py
backend/app/nutrition/candidate_selection.py
backend/tests/nutrition/test_planner_engine.py
backend/tests/nutrition/test_program_adaptation.py
```

### MODIFY ONLY IF COVERAGE ANALYSIS PROVES A REAL GAP

```text
backend/app/nutrition/meal_catalogue.py
backend/app/nutrition/program_catalogue_seed_data.py
backend/tests/nutrition/test_meal_catalogue.py
backend/tests/nutrition/test_program_catalogue_seed.py
```

Do not add new meals before proving the compatible eligible pool is actually insufficient.

---

## 2.1 Substitution must operate on `EligibleMealTemplate`

The substitution input must be the pool that has **already** passed:

- dietary-pattern filtering,
- excluded-term/allergy filtering,
- mandatory nutrient checks,
- price eligibility,
- required ingredient availability,
- prepared-recipe ingredient eligibility.

This is critical.

Do not search the raw Meal Catalogue and then reimplement half of the safety checks.

---

## 2.2 Add substitution data types

Recommended pure type:

```python
@dataclass(frozen=True)
class SubstitutionAction:
    day_index: int
    role: str
    slot_index: int
    requested_template_id: str
    replacement_template_id: str
    reason_code: str
```

Extend `PlannerResult` with:

```python
substitution_actions: tuple[SubstitutionAction, ...] = ()
```

Do this backward-compatibly for existing constructor tests.

Stage 1 candidate quality should now set:

```text
substitution_burden = len(result.substitution_actions)
```

or a richer deterministic count if some substitutions are more invasive.

---

## 2.3 Hard substitution constraints

A replacement candidate is not allowed unless it satisfies all required hard compatibility.

At minimum:

1. **slot/category compatibility**
   - breakfast → breakfast,
   - lunch → lunch,
   - dinner → dinner,
   - snack → snack,
   - post-workout → post-workout,
   unless an explicit tested policy mapping says otherwise.

2. **dietary pattern compatibility**

3. **allergy/exclusion compatibility**

4. **verified ingredient/nutrient eligibility**

5. **valid current price coverage**

6. **required items present**

7. **portion bounds capable of producing a meaningful portion**

8. **prepared recipe fully eligible**

Do not use a breakfast as lunch merely because calories match.

Do not replace a post-workout slot with an arbitrary snack unless product semantics explicitly permit it.

---

## 2.4 Deterministic substitution ranking

Create a pure function approximately:

```python
def rank_template_substitutes(
    requested: PlannerMealTemplate,
    eligible_candidates: tuple[EligibleMealTemplate, ...],
    context: SubstitutionContext,
) -> tuple[EligibleMealTemplate, ...]:
    ...
```

Recommended lexicographic ranking:

```text
1. exact category/slot semantic match
2. functional-role / macro-archetype similarity
3. normalized energy closeness to slot target
4. normalized protein closeness to slot target
5. expected weekly repetition penalty
6. preference penalty
7. expected cost
8. stable meal/template ID
```

Nutrition compatibility must come before cost.

If the original template is unavailable because it is unsafe for the user, never include it in the candidate pool.

---

## 2.5 Avoid "first substitute wins" if it breaks the week

A substitute can be locally valid but globally bad because it causes:

- excessive repetition,
- budget overflow,
- macro infeasibility.

Therefore scheduled-day construction should be capable of trying the next ranked substitute when a replacement creates a recoverable downstream failure.

You do not need an unbounded combinatorial search.

Use a deterministic bounded approach.

Recommended policy additions:

```python
maximum_template_substitution_attempts_per_slot: int
maximum_candidate_rebuild_attempts: int
```

Choose conservative finite values based on catalogue size.

No infinite recursion.

---


## 2.5A Generate multiple viable full-week variants, not only one locally-valid substitute

A locally valid substitute can be worse than another valid substitute even when both allow the week to succeed.

Therefore do not implement Stage 2 as:

```text
first compatible substitute
→ lock it forever
```

Instead, when a slot has multiple materially viable substitutes, allow the base program to emit multiple partial/full Plan Variants.

Recommended deterministic beam state:

```python
@dataclass(frozen=True)
class PartialWeekVariant:
    days_built: tuple[PlannedDay, ...]
    pending_slots: tuple[object, ...]
    substitutions: tuple[SubstitutionAction, ...]
    partial_quality_lower_bound: tuple[object, ...]
    stable_variant_key: tuple[str, ...]
```

Recommended policy fields:

```python
maximum_substitutes_per_slot: int
maximum_partial_variants_per_program: int
maximum_full_variants_per_program: int
```

Rules:

- rank all safe substitutes deterministically;
- expand up to the versioned per-slot bound;
- keep a bounded set of best partial variants;
- never prune a variant only because its program style is not preferred;
- nutrition lower-bound must dominate preference/cost when pruning;
- stable IDs break equal partial scores;
- final winner is chosen only after complete hard validation and final quality calculation.

This prevents a hidden "first substitute wins" architecture from surviving inside the new all-program search.

After this point, `CandidateEvaluation` should represent a **full Plan Variant**, not only a base program. Add a stable variant identity, for example:

```python
stable_variant_key: tuple[str, ...]
```

The final comparator should use `(stable_program_code, stable_variant_key)` only as the last deterministic tie-break.

---

## 2.6 Integrate into scheduled-day construction

Replace:

```text
requested ID not found
→ throw ScheduledTemplateUnavailableError immediately
```

with:

```text
requested ID found
→ use it

requested ID not found
→ rank safe substitutes
→ try substitute
→ record SubstitutionAction

no compatible substitute
→ deterministic failure:
   NO_COMPATIBLE_TEMPLATE_SUBSTITUTE
```

Keep `ScheduledTemplateUnavailableError` as an internal typed error if it remains useful, but normal incompatible-user cases should now be resolved by substitution rather than surfacing that failure.

---

## 2.7 Repetition rules after substitution

Substitution must not accidentally turn a varied weekly program into the same cheap meal every day.

Track template usage during weekly construction.

Respect the user's existing:

```text
maximum_meal_repetition_per_week
```

When the best replacement would exceed repetition limits:

```text
try next compatible substitute
```

If no replacement can satisfy both compatibility and repetition rules, return a precise reason code.

---

## 2.8 Catalogue coverage analysis before adding data

After implementing substitution against the existing verified pool, rerun the 100-profile audit.

Create a small development diagnostic showing, for every unresolved substitution:

```text
slot/category
dietary_pattern
excluded terms
requested meal
number of eligible alternatives
reason each alternative was rejected
```

Only if this proves a real catalogue hole should Luna edit `meal_catalogue.py` or seed data.

If new meals are required:

- use existing Meal Catalogue model;
- use verified foods only;
- add real portion min/reference/max;
- add valid category;
- add price-covered foods;
- add tests;
- do not create unverified arbitrary fallback recipes.

---

## 2.9 Stage 2 tests

Create tests for:

- original meal available → no substitution;
- original meal incompatible → safe substitute chosen;
- vegetarian profile never receives incompatible meat meal;
- vegan profile never receives animal-product meal;
- allergy/excluded term never re-enters through substitution;
- prepared recipe is rejected if one required ingredient is incompatible;
- no eligible substitute → `NO_COMPATIBLE_TEMPLATE_SUBSTITUTE`;
- same input → same substitute;
- repetition cap respected;
- next-ranked substitute tried when first option violates repetition;
- `SubstitutionAction` records requested/replacement IDs;
- candidate ranking includes substitution burden;
- no unverified template enters the plan.

Stage exit gate:

Rerun the audit and verify that historical scheduled-template-unavailable failures collapse substantially.

Do **not** move to Stage 3 merely because raw success improved. Confirm zero dietary/allergy regressions.

Suggested commit:

```text
nutrition: substitute incompatible scheduled meal templates
```

---

# STAGE 3 — Budget Optimization + Economical Candidate Repair

## Stage objective

Reduce strict/flexible budget failures by finding **cheaper safe feasible versions of a candidate**, not by weakening the user's budget.

Candidate Architecture from Stage 1 already gives a large improvement because all program styles are explored.

Stage 3 adds local deterministic budget repair inside each candidate.

---

## Files

### CREATE

```text
backend/app/nutrition/budget_optimizer.py
backend/tests/nutrition/test_budget_optimizer.py
```

### MODIFY

```text
backend/app/nutrition/planner_engine.py
backend/app/nutrition/planner_policy.py
backend/app/nutrition/candidate_selection.py

backend/tests/nutrition/test_planner_engine.py
backend/tests/nutrition/test_weekly_plan_api.py
backend/tests/nutrition/test_price_mass_conversion.py
backend/tests/nutrition/test_food_pricing.py
```

### COVERAGE-DRIVEN ONLY

Potentially modify:

```text
backend/app/nutrition/meal_catalogue.py
food catalogue/seed modules actually used by the current repository
```

Only do this if the optimizer proves the existing safe catalogue cannot satisfy important low-budget profiles.

Do not duplicate weekly program matrices just to make cheaper variants.

---

## 3.1 Preserve exact budget semantics

Current policy has:

```text
strict
flexible
```

Keep them.

For strict:

```python
final_weekly_cost <= weekly_budget_irr
```

For flexible:

```python
final_weekly_cost <= weekly_budget_irr * (1 + existing_flexible_overage_cap)
```

Do not increase the existing 15% cap merely to pass the audit.

Do not silently reinterpret zero/invalid budgets. Keep current input validation semantics.

---

## 3.2 Add budget repair types

Recommended:

```python
@dataclass(frozen=True)
class BudgetRepairAction:
    day_index: int
    role: str
    slot_index: int
    action_type: str
    before_cost_irr: Decimal
    after_cost_irr: Decimal
    saved_irr: Decimal
    reason_code: str
```

Extend `PlannerResult`:

```python
budget_repair_actions: tuple[BudgetRepairAction, ...] = ()
```

Candidate quality:

```text
repair_burden += len(budget_repair_actions)
```

Do not penalize repaired plans so heavily that a slightly more expensive but nutritionally identical clean plan always wins incorrectly. Repair burden comes after nutrition/budget quality in the comparator.

---

## 3.3 Build a pure budget optimizer

The optimizer receives already-constructed planner objects. It must not query prices from DB itself.

Suggested interface:

```python
def optimize_weekly_budget(
    *,
    days: tuple[PlannedDay, ...],
    inputs: PlannerInput,
    eligible_templates: tuple[EligibleMealTemplate, ...],
    policy: PlannerPolicy,
) -> BudgetOptimizationResult:
    ...
```

Return:

```text
repaired days
repair actions
final cost
failure code if no feasible repair exists
```

---

## 3.4 Allowed budget moves

Generate only moves that remain semantically valid.

### Move A — cheaper compatible meal-template substitution

For a costly meal slot:

- same required category/slot semantics,
- already eligible template,
- compatible diet/allergy constraints,
- nutritionally similar enough to remain solvable,
- lower expected cost.

### Move B — reduce optional expensive ingredient within bounds

Only when:

- ingredient is optional;
- new grams remain >= min allowed if present;
- full meal/day nutrients are recomputed;
- final candidate remains nutritionally repairable.

### Move C — safe portion rescaling

Reduce expensive portions only if:

- min grams respected;
- energy/protein/macros remain inside or can be repaired by Stage 5;
- no safety/UL violation;
- result is not simply starving the plan to meet budget.

### Ingredient substitution

Do **not** invent generic food-for-food recipe substitutions unless the Meal Catalogue model already explicitly represents interchangeable items/roles with tested semantics.

If the current model does not support it, prefer whole-template substitution.

---

## 3.5 Rank budget moves deterministically

A candidate move should expose:

```text
predicted cost saving
predicted normalized nutrition penalty
repetition impact
preference impact
stable identifier
```

Choose moves using deterministic priority such as:

```text
largest cost saving with smallest nutrition damage
```

but hard nutrition feasibility remains non-negotiable.

A useful internal ranking can be lexicographic:

```python
(
    hard_feasibility_class,
    normalized_nutrition_penalty,
    -cost_saved,
    repetition_penalty,
    preference_penalty,
    stable_action_id,
)
```

Do not use floating nondeterministic ordering.

---

## 3.6 Recompute after every accepted repair

Do not keep applying predicted deltas to stale values.

After each accepted move:

```text
rebuild affected meal nutrients
rebuild affected day nutrients
rebuild weekly nutrients
rebuild weekly cost
recheck budget
recheck hard limits
```

Then calculate the next move.

Add explicit bounded policy:

```python
maximum_budget_repair_iterations
```

If the limit is reached without success, return a clear failure.

---

## 3.7 Precise failure codes

Replace generic budget failure where useful with reason codes that distinguish:

```text
STRICT_BUDGET_NO_FEASIBLE_REPAIR
FLEXIBLE_BUDGET_NO_FEASIBLE_REPAIR
INSUFFICIENT_LOW_COST_TEMPLATE_COVERAGE
```

Do not hide the final actual cost. Put it in diagnostics.

---


## 3.7A Add a minimum-cost feasibility fallback before declaring budget infeasible

Local greedy budget repair is useful but is not sufficient evidence that no affordable plan exists.

Before returning:

```text
STRICT_BUDGET_NO_FEASIBLE_REPAIR
FLEXIBLE_BUDGET_NO_FEASIBLE_REPAIR
```

the engine must run a second deterministic **minimum-cost feasibility pass** over the current safe candidate/variant search space.

The question is:

> "Does any safe combination within the verified catalogue, portion bounds, slot semantics and nutrition constraints satisfy this budget?"

not:

> "Did the first few local swaps happen to fix the budget?"

### Solver abstraction

Create a narrow pure interface, either in `budget_optimizer.py` or a new module if it materially improves separation:

```python
class BudgetFeasibilitySolver(Protocol):
    def solve(
        self,
        *,
        inputs: PlannerInput,
        variants: tuple[object, ...],
        policy: PlannerPolicy,
    ) -> BudgetFeasibilityResult:
        ...
```

The service/planner must depend on the interface, not on one solver library.

### Solver choice

Inspect existing dependencies first.

Preferred order:

1. reuse an already-approved deterministic optimization dependency if present;
2. otherwise benchmark an LP/MILP-capable approach when the model can be expressed linearly;
3. CP-SAT is acceptable for discrete meal/template choices if dependency policy allows it;
4. otherwise implement deterministic bounded branch-and-bound over the small verified catalogue.

Do not add a heavyweight dependency merely because it is fashionable.

Do not introduce floating nondeterminism without stable tolerances and deterministic tie-breaking.

### Scientific/engineering basis

Food-based diet planning is a classic constrained optimization problem. Linear-programming approaches such as the WHO/LSHTM Optifood framework demonstrate the usefulness of formal feasibility searches for finding food combinations under nutrient and food-pattern constraints.

Fitsho does not need to copy Optifood's product semantics. The relevant lesson is:

```text
prove/search feasibility under explicit constraints
before declaring the user's constraints impossible
```

### What the minimum-cost pass must preserve

Hard constraints remain hard:

```text
verified foods/templates
allergy/exclusion filters
dietary pattern
slot semantics
portion bounds
nutrient upper limits
core calorie/macro corridor
repetition limits
price validity
```

The objective is minimum weekly cost **subject to those constraints**.

If the minimum feasible weekly cost is above a strict budget, the planner now has evidence for genuine strict-budget infeasibility.

Diagnostics should include, when available:

```text
minimum_feasible_weekly_cost_irr
user_weekly_budget_irr
budget_gap_irr
feasibility_solver_version
feasibility_search_exhaustive: true|false
```

If the fallback is bounded rather than mathematically exhaustive, use wording such as `NO_FEASIBLE_PLAN_FOUND_WITHIN_SEARCH_POLICY`, not a false proof of mathematical impossibility.

---

## 3.8 Economical catalogue expansion policy

After the optimizer works, inspect unresolved budget failures.

For each diet/slot combination, calculate:

```text
eligible template count
minimum achievable representative cost
minimum reasonable protein/calorie contribution
price-data freshness
```

Add new economical foods/meals only when the data proves a gap.

A new economical meal must not be "cheap junk" added solely to reduce cost.

Require:

- real verified nutrient source,
- valid food mass basis,
- current price reference,
- acceptable energy/protein/fibre role,
- category compatibility,
- realistic min/reference/max portions,
- Meal Catalogue tests.

Do not weaken nutritional quality to make an impossible budget look feasible.

A genuinely impossible strict budget is allowed to remain infeasible, but the audit must prove why.

---

## 3.9 Preserve price/mass regression coverage

Explicitly add regression cases in:

```text
backend/tests/nutrition/test_price_mass_conversion.py
```

for the historical failure class, including any previously problematic produce item represented in the current catalogue.

Do not rewrite the conversion architecture unless the regression test still fails on current code.

---

## 3.10 Stage 3 tests

Add tests proving:

- over-budget candidate is repaired when a cheaper compatible plan exists;
- strict plan never ends above strict budget;
- flexible plan never exceeds existing flexible cap;
- optimizer does not choose an unsafe/incompatible cheaper meal;
- nutrition is recomputed after a repair;
- repetition rules still hold;
- deterministic same input → same repair sequence;
- impossible strict budget returns explicit infeasibility;
- candidate comparator does not choose cheaper nutrition if nutrition quality is materially worse;
- price/mass conversion regression remains fixed;
- no stale/invalid price reference is used.

Stage exit gate:

Rerun the 100-profile audit and report budget failures by:

```text
strict
flexible
dietary pattern
budget decile
```

Do not proceed until the optimizer is deterministic and has zero budget-rule violations.

Suggested commit:

```text
nutrition: optimize candidate budgets deterministically
```

---

# STAGE 4 — Goal-Contract Repair

## Stage objective

Decouple two different questions:

```text
Can Fitsho safely calculate a nutrition plan for this user?
```

and:

```text
Is the user's current training stimulus ideal for their chosen fitness goal?
```

A training mismatch should usually produce a coaching warning, not disable nutrition.

---

## Files

### MODIFY

```text
backend/app/nutrition/scientific.py
backend/app/nutrition/plan_service.py
backend/app/nutrition/exceptions.py

backend/tests/nutrition/test_scientific_engine.py
backend/tests/nutrition/test_nutrition_estimate_api.py
backend/tests/nutrition/test_weekly_plan_api.py
```

Avoid model/schema changes unless existing API warning fields truly cannot represent the new explanation codes.

---

## 4.1 Separate nutrition-target support from training-goal alignment

Refactor the scientific goal contract into concepts equivalent to:

```python
target_contract = calculate_safe_nutrition_target(...)
training_alignment = assess_training_stimulus_alignment(...)
```

A user can have:

```text
valid nutrition target
+
training alignment warning
```

at the same time.

Do not make `training_alignment` a hidden blocker.

---

## 4.2 Repair `IMPROVE_FITNESS`

The current hard failure for:

```text
FitnessGoal.IMPROVE_FITNESS
```

must be replaced by an explicit supported nutrition contract.

Use the current scientific architecture and existing goal definitions.

Do not invent an aggressive calorie surplus/deficit.

Preferred product behavior:

- derive a conservative maintenance/performance-oriented target from the existing BMR/TDEE system;
- preserve protein/fat/carbohydrate safety logic;
- emit an explanation code indicating that this is a general-fitness nutrition contract.

Example code naming:

```text
GENERAL_FITNESS_NUTRITION_TARGET
```

If the repository already has a more appropriate established target policy, reuse it instead of duplicating formulas.

---

## 4.3 Repair physique goal + insufficient training stimulus

For goals such as muscle gain/recomposition where current structured training does not match the ideal stimulus:

Old behavior:

```text
goal reselection required
→ no nutrition generation
```

Target behavior:

```text
calculate safe nutrition target from current profile
→ keep user's explicit goal unchanged
→ emit TRAINING_STIMULUS_MISMATCH warning
→ provide coaching/advice through existing explanation mechanism
→ continue candidate generation
```

Do not assume the user will start training tomorrow.

Do not falsify activity expenditure.

Use actual structured exercise/activity inputs.

---

## 4.4 Keep true hard failures hard

This stage must not turn every scientific error into a warning.

Still block/reroute when:

- safety policy says automatic nutrition is not allowed;
- required profile data is missing;
- target calculation is mathematically/medically infeasible;
- existing minimum/maximum target guards cannot produce a safe contract.

Differentiate:

```text
TARGETS_GENERATED_WITH_GOAL_COACHING_WARNING
```

from:

```text
GOAL_RESELECTION_REQUIRED
NUTRITION_TARGET_INFEASIBLE
```

The latter should become rarer and should mean something real.

---

## 4.5 Do not mutate the user's goal

Never silently change:

```text
fitness_goal
```

just to get generation to work.

If product behavior requires changing the stored goal, that remains an explicit user-confirmed action through the existing consent/update flow.

---

## 4.6 Stage 4 tests

Add/modify tests proving:

- `IMPROVE_FITNESS` now receives a supported safe target;
- muscle/recomposition-like goal without ideal resistance training gets a target plus warning instead of unnecessary hard failure;
- matched training behavior remains supported;
- actual unsafe/infeasible target still blocks;
- user's stored goal is not silently changed;
- target-update consent behavior remains intact;
- weekly generation continues when the only issue is training-goal alignment.

Stage exit gate:

Rerun the audit and confirm the old goal-contract failure family is replaced by successful generation + explicit warning for safe cases.

Suggested commit:

```text
nutrition: decouple goal coaching from target generation
```

---

# STAGE 5 — Portion / Macro Solver + Dynamic Rescaling

## Stage objective

Stop throwing away an otherwise-good candidate merely because initial template scaling + independent min/max clamping leaves a fixable calorie/macro error.

Replace one-pass clamping with deterministic bounded optimization.

---

## Files

### CREATE

```text
backend/app/nutrition/portion_solver.py
backend/tests/nutrition/test_portion_solver.py
```

### MODIFY

```text
backend/app/nutrition/planner_engine.py
backend/app/nutrition/planner_policy.py
backend/app/nutrition/candidate_selection.py

backend/tests/nutrition/test_planner_engine.py
backend/tests/nutrition/test_weekly_plan_api.py
```

Do not add a heavy optimization dependency without checking the existing backend dependency policy first.

---

## 5.1 Solver variable model

For each adjustable meal ingredient:

```text
variable = grams
lower bound = item.min_grams
upper bound = item.max_grams
```

Keep required/optional semantics intact.

The solver must never exceed catalogue portion bounds just to satisfy macros.

Prepared-recipe quantities need to respect their own existing recipe semantics; do not mutate a prepared recipe incorrectly as though each cooked output ingredient were a free independent variable.

---

## 5.2 Initial state

Reuse the existing planner's current scale-and-clamp output as an initial guess.

Do not delete stable current logic unnecessarily.

The new solver repairs the residual error after initial construction.

---

## 5.3 Optimize at day level

Do not optimize every meal in isolation and assume the day will work.

A breakfast can be slightly protein-light if lunch/dinner make the day correct.

The primary target unit should be:

```text
PlannedDay
```

with meal semantics and portion bounds preserved.

---

## 5.4 Deterministic objective

Use hard feasibility plus lexicographic/minimax optimization.

Recommended objective order:

```text
1. never violate nutrient upper limits / safety
2. minimize maximum normalized calorie/protein/carb/fat deviation
3. minimize total normalized core-macro deviation
4. minimize fibre deficit
5. minimize departure from reference portions
6. minimize cost increase
7. stable variable/action ordering
```

This avoids "fixing calories" by destroying protein, or vice versa.

---

## 5.5 Solver implementation strategy

First inspect current dependencies.

If the repository already has an accepted deterministic optimizer dependency suitable for bounded linear-ish optimization, reuse it.

Otherwise implement a small deterministic bounded solver rather than adding a heavy dependency.

A reasonable custom approach:

1. compute residual nutrient error;
2. calculate each adjustable ingredient's nutrient leverage per gram;
3. generate bounded gram moves;
4. score moves by reduction in normalized max deviation;
5. accept only moves that improve the lexicographic objective;
6. recompute exact nutrients;
7. iterate until:
   - target corridor satisfied, or
   - no improving move exists, or
   - iteration limit reached.

Use fixed stable ingredient order to break ties.

No random search.

No simulated annealing.

No LLM.

---

## 5.6 Quantization

Keep calculations deterministic.

Use the repository's Decimal approach.

After solver updates, quantize final portions to a realistic policy increment.

Add an explicit policy field if needed:

```python
portion_adjustment_increment_g: Decimal
maximum_portion_solver_iterations: int
```

Do not leave tiny unusable values such as:

```text
83.274918273 g
```

if the rest of the product expects human-usable gram portions.

After quantization, recompute nutrients one final time.

---

## 5.7 Add portion repair trace

Recommended type:

```python
@dataclass(frozen=True)
class PortionAdjustmentAction:
    day_index: int
    role: str
    slot_index: int
    food_id: str | None
    before_grams: Decimal
    after_grams: Decimal
    reason_code: str
```

Add to `PlannerResult`:

```python
portion_adjustment_actions: tuple[PortionAdjustmentAction, ...] = ()
```

Candidate quality repair burden should include this bounded count.

---

## 5.8 Budget ↔ macro repair loop

Budget repair can worsen macros.

Macro repair can increase cost.

Therefore after Stage 5 the final candidate pipeline must have a **bounded combined repair loop**.

Recommended structure:

```text
initial construction
↓
micronutrient repair
↓
budget repair
↓
portion/macro repair
↓
recompute everything
↓
if budget and macro constraints both pass:
    done
else if another deterministic repair iteration is allowed:
    repeat
else:
    precise infeasibility
```

Do not ping-pong forever.

Add policy:

```python
maximum_combined_repair_passes
```

Keep it small and deterministic.

---

## 5.9 Precise infeasibility

If the bounds genuinely cannot meet the target, report why.

Examples:

```text
CALORIE_TARGET_UNREACHABLE_WITH_PORTION_BOUNDS
PROTEIN_TARGET_UNREACHABLE_WITH_PORTION_BOUNDS
CARBOHYDRATE_TARGET_UNREACHABLE_WITH_PORTION_BOUNDS
FAT_TARGET_UNREACHABLE_WITH_PORTION_BOUNDS
MULTI_MACRO_TARGET_UNREACHABLE_WITH_PORTION_BOUNDS
```

Do not label every impossible combination as generic `TARGET_INFEASIBLE`.

This diagnostic precision matters for the final >90% loop.

---

## 5.10 Stage 5 tests

Add tests proving:

- a scale-then-clamp case that previously failed can now be repaired;
- every ingredient remains within min/max;
- solver reduces max normalized macro deviation;
- final values are recomputed after quantization;
- same input gives identical gram output;
- solver cannot loop forever;
- impossible bounds produce a precise reason;
- strict/flexible budget remains valid after macro repair;
- upper limits remain valid after repair;
- repaired candidate ranking uses final, not pre-repair, nutrient values.

Stage exit gate:

Rerun 100-profile audit.

Inspect remaining `TARGET_INFEASIBLE` cases individually. The majority should now represent genuine catalogue/portion impossibility, not one-pass clamping artifacts.

Suggested commit:

```text
nutrition: rebalance portions to calorie and macro targets
```

---

# STAGE 6 — Micronutrient Quality + Variety + Preferences / Adherence

## Stage objective

At this point generation success should already be high.

Now improve which successful plan wins.

The engine should behave more like a good coach:

- nutrition adequacy first,
- then diet quality,
- then cost,
- then personal preference/adherence,
- then variety/cleanliness of construction.

This stage must improve **selection quality**, not weaken feasibility.

---

## Files

### CREATE

Recommended:

```text
backend/app/nutrition/preference_snapshot.py
```

Optional dedicated tests:

```text
backend/tests/nutrition/test_preference_snapshot.py
```

### MODIFY

```text
backend/app/nutrition/candidate_selection.py
backend/app/nutrition/planner_engine.py
backend/app/nutrition/planner_policy.py
backend/app/nutrition/plan_service.py

backend/tests/nutrition/test_candidate_selection.py
backend/tests/nutrition/test_planner_engine.py
backend/tests/nutrition/test_adherence_api.py
backend/tests/nutrition/test_weekly_plan_api.py
backend/tests/nutrition/test_micronutrient_policy.py
```

Only modify `adherence_service.py` if a small reusable extraction is genuinely necessary. Avoid creating circular dependencies.

---

## 6.1 Build a DB-independent preference snapshot

Load user-specific data once in the service layer.

Recommended pure structure:

```python
@dataclass(frozen=True)
class PreferenceSnapshot:
    liked_food_ids: tuple[str, ...]
    disliked_food_ids: tuple[str, ...]
    preferred_meal_ids: tuple[str, ...]
    disliked_meal_ids: tuple[str, ...]
    excluded_meal_ids: tuple[str, ...]
    historical_meal_adherence: tuple[tuple[str, Decimal], ...]
    data_sufficient: bool
```

Populate from current profile/feedback/adherence data.

Then pass the snapshot into candidate scoring/planning as immutable data.

Do not let `candidate_selection.py` query `NutritionMealFeedback` itself.

---

## 6.2 Feedback semantics

Recommended interpretation of existing feedback:

```text
do_not_suggest_again
    → hard user-specific meal exclusion

disliked
    → strong preference penalty

liked
    → preference bonus / lower penalty

prefer_more_often
    → stronger preference bonus
```

None may override:

- safety,
- diet,
- budget,
- nutrient feasibility.

If `do_not_suggest_again` would leave no feasible plan, report a clear user-preference infeasibility rather than silently serving the forbidden meal.

Do not change scientific targets based on likes/dislikes.

---

## 6.3 Micronutrient quality component

Use existing micronutrient targets/upper limits/comparison confidence.

For each supported micronutrient:

- calculate normalized deficit when below target;
- respect existing upper-limit hard failure;
- account for data confidence/completeness;
- do not treat absent data as zero;
- do not treat absent data as perfect.

A possible normalized deficit:

```python
max(target - planned, 0) / target
```

Aggregate in a way that does not hide one major gap.

Recommended:

```text
max micronutrient deficit
+
bounded total deficit
+
data uncertainty penalty
```

The exact representation can remain inside `CandidateQuality` as one deterministic component if tests prove the ordering.

---

## 6.4 Diet-quality component

Use nutrients already present in the planner where data quality is sufficient.

Potential components:

- fibre adequacy,
- saturated-fat excess,
- trans-fat excess,
- free/added sugar excess,
- sodium excess,
- supported micronutrient adequacy.

Do not invent a pseudo-scientific "healthy score" unrelated to current policy.

Keep every component traceable to existing targets/limits/policy.

---

## 6.5 Variety / repetition

Even when the hard maximum repetition cap is not violated, two feasible plans can have different variety.

Add a soft repetition penalty such as:

```text
sum(max(usage_count - 1, 0)^2)
```

or another simple deterministic formula.

Keep the existing hard:

```text
maximum_meal_repetition_per_week
```

separate.

Hard repetition failure must not be replaced by a soft score.

---

## 6.6 Historical adherence

Use historical adherence only when enough data exists.

Do not infer that a user's weight changed *because* of one meal or plan.

The existing adherence logic is explicitly confidence-aware and avoids causal weight claims; preserve that principle.

Safe use:

```text
user repeatedly confirms meal X
→ small preference advantage

user repeatedly rejects/skips meal Y
→ small penalty
```

Unsafe use:

```text
weight increased
→ assume meal X caused it
```

Do not do that.

If adherence data is insufficient:

```text
neutral score
```

not:

```text
negative score
```

---


## 6.6A Add sports-nutrition quality signals only as soft ranking features

After total daily targets are feasible, the final candidate ranking may prefer plans that better support training.

When structured exercise timing is available, consider soft components such as:

```text
protein distributed across multiple meaningful meals
reasonable carbohydrate availability around demanding training
post-workout meal compatibility when the program explicitly contains that slot
avoidance of putting nearly all daily energy/protein into one meal without user reason
```

Rules:

1. total daily energy/protein/macro adequacy remains more important than nutrient timing;
2. do not fail a plan solely because workout timing is imperfect;
3. do not add carbohydrate timing penalties if the user's workout schedule/time is unknown;
4. do not infer amino-acid/leucine precision if the verified Food Catalogue does not contain reliable amino-acid data;
5. every new soft component must be policy-versioned, explainable and covered by ranking tests.

Recommended candidate-quality extension only if data support is sufficient:

```python
sports_nutrition_distribution_penalty: Decimal
```

Place it after core nutrition/diet quality and before convenience-only preferences.

---

## 6.7 Final candidate quality ordering

After this stage, implement the full comparator:

```python
CandidateQuality.sort_key() == (
    core_nutrition_max_deviation,
    core_nutrition_total_deviation,
    micronutrient_gap_penalty,
    diet_quality_penalty,
    sports_nutrition_distribution_penalty,  # when supported by sufficient data
    budget_utilization_penalty,
    preference_and_feedback_penalty,
    repetition_penalty,
    warning_burden,
    repair_burden,
    substitution_burden,
    preferred_program_style_penalty,
    stable_program_code,
    stable_variant_key,
)
```

Important:

- preference never beats hard nutrition;
- lower cost never beats hard nutrition;
- preferred style never beats clearly better nutritional quality;
- stable code only breaks genuine ties.

Add human-readable component values to the selection trace for the selected candidate and first-valid candidate.

---

## 6.8 Stage 6 tests

Add tests proving:

- when two plans are nutritionally equal, liked foods can break the tie;
- disliked meals are penalized;
- `do_not_suggest_again` meal is excluded;
- a preference cannot make a nutritionally worse plan beat a clearly better one;
- variety can break a nutritional/cost tie;
- missing micronutrient data cannot produce a perfect micronutrient score;
- low-confidence data is represented conservatively;
- insufficient adherence history is neutral;
- no scientific targets change without the existing explicit confirmation mechanism;
- same inputs/history produce identical selected plan;
- `selected.sort_key <= first_valid.sort_key`.

Stage exit gate:

Take a sample where at least 2–5 candidates succeed and inspect the trace manually.

The selected plan should be explainable from the quality vector without hidden randomness.

Suggested commit:

```text
nutrition: rank feasible plans by quality and adherence
```

---

# STAGE 7 — Safety Regression Protection + Reproducible >90% Audit Gates

## Stage objective

Do not end with "tests pass".

Prove the repaired engine performs correctly across a broad cohort and make future regressions visible.

---

## Files

### MODIFY

```text
backend/scripts/generate_100_profiles_audit_report.py
```

### OPTIONAL CREATE

If keeping audit logic out of the report script improves maintainability:

```text
backend/scripts/nutrition_candidate_search_benchmark.py
```

### MODIFY TESTS AS REQUIRED

At minimum:

```text
backend/tests/nutrition/test_safety_policy.py
backend/tests/nutrition/test_planner_engine.py
backend/tests/nutrition/test_candidate_selection.py
backend/tests/nutrition/test_weekly_plan_api.py
backend/tests/nutrition/test_program_catalogue.py
backend/tests/nutrition/test_meal_catalogue.py
backend/tests/nutrition/test_price_mass_conversion.py
backend/tests/nutrition/test_scientific_engine.py
```

Only modify CI configuration if the repository's current CI can run this audit at a reasonable cost. Do not make every tiny PR run a prohibitively expensive 1000-profile benchmark.

---

## 7.1 Make the 100-profile audit reproducible

The report must record:

```text
audit schema version
git commit
planner version
planner policy version
random seed
profile-generation seed
catalogue version / relevant data version
timestamp for report metadata only
```

The timestamp must not influence plan output.

A repeated run with:

```text
same commit
same catalogue
same seed
```

must produce the same profile inputs and the same deterministic planner results.

---

## 7.2 Add failure histogram

For every failed automatically eligible profile, record:

```text
final generation outcome
top-level reason codes
candidate failure reason histogram
active candidate count
evaluated candidate count
successful candidate count
```

Aggregate report:

```text
SCHEDULED_TEMPLATE_UNAVAILABLE: N
NO_COMPATIBLE_TEMPLATE_SUBSTITUTE: N
STRICT_BUDGET_NO_FEASIBLE_REPAIR: N
MULTI_MACRO_TARGET_UNREACHABLE_WITH_PORTION_BOUNDS: N
...
```

This is the feedback loop for getting from "better" to >90%.

---

## 7.3 Add selected-vs-first-valid analysis

For successful profiles report:

```text
first valid program
selected best program
selected differs from first valid?
first-valid quality vector
selected quality vector
number of successful candidates
```

Aggregate:

```text
% profiles where best-plan selection changed the winner
```

Assert the selected quality key is never worse.

This proves Stage 1 is actually doing useful work.

---

## 7.4 Add cohort breakdowns

For the existing 100-profile audit, add breakdowns where the profile generator has the dimension:

```text
dietary pattern
allergy / exclusion presence
strict vs flexible budget
budget range / decile
fitness goal
training type
main meal count
snack count
cooking constraints
```

A global 91% can hide a broken 30% vegan subgroup.

Report subgroup success rates when sample size is meaningful.

---

## 7.5 Add safety invariants to the audit

For every successful plan, independently validate:

```text
no excluded/allergic food
dietary pattern respected
all foods/templates verified as required
strict budget respected
flexible cap respected
upper limits respected
portion bounds respected
meal count contract respected
repetition contract respected
```

The audit should fail loudly if the planner says `SUCCESS` but an independent invariant check finds a violation.

---

## 7.6 Performance metrics

Evaluating all 25 programs is deliberately more expensive than evaluating one.

Measure it.

Report:

```text
mean generation latency
p50
p95
max
program candidates evaluated
successful candidates
```

Do not prematurely reduce candidate count before measuring.

If performance is unacceptable after correctness is achieved, optimize repeated immutable calculations:

- food eligibility,
- meal eligibility,
- shared target data,
- price lookup,
- template nutrient baseline calculations.

Cache only candidate-independent work.

Do not reintroduce "try only one program" as a performance shortcut.

---

## 7.7 Extended stress cohort

After the historical 100-profile acceptance passes, run a larger deterministic cohort, recommended:

```text
300–1000 profiles
```

Stratify or intentionally include difficult cases.

The larger stress cohort is for confidence; the existing historical 100-profile audit remains useful for direct before/after comparison.

---


## 7.7A Run a frozen untouched holdout before final acceptance

The development team may repeatedly inspect and fix failures from the historical 100-profile cohort. That makes the original cohort a regression/tuning set.

Final >90% acceptance must therefore also run the **frozen independent holdout cohort created before Stage 1**.

Rules:

```text
same frozen profile seed/definition
no code changes after looking at individual holdout failures unless a second new holdout is frozen first
report all safety invariants
report success rate separately from development cohort
```

Required final report:

```text
Development 100-profile success rate
Frozen holdout automatically-eligible success rate
Frozen holdout safe-resolution rate
Frozen holdout safety violation counts
```

Recommended acceptance target:

```text
frozen_holdout_automatically_eligible_success_rate > 90%
frozen_holdout_safe_resolution_rate == 100%
```

If the development cohort is >90% but the frozen holdout is not, the repair is not finished; it is likely overfit or missing a general failure family.

---

## 7.8 Final acceptance gates

Implementation is complete only if all of the following are true.

### Correctness

```text
automatically eligible generation success > 90%
frozen holdout automatically eligible generation success > 90%
safe resolution = 100%
frozen holdout safe resolution = 100%
allergy violations = 0
dietary-pattern violations = 0
medical safety violations = 0
strict-budget violations = 0
upper-limit violations in SUCCESS plans = 0
portion-bound violations = 0
```

### Selection

```text
all active approved program candidates are evaluated
no first-success early exit
no UUID/user-id winner selection
selected candidate is never worse than first valid
same input produces same winner
```

### Repair behavior

```text
safe substitution works
budget repair respects budget mode
goal mismatch no longer unnecessarily blocks nutrition
macro/portion repair respects bounds
preferences never override safety/nutrition
```

### Engineering quality

```text
focused tests pass
full backend/tests/nutrition passes
ruff check passes for changed scope/repo according to project convention
mypy passes according to project convention
no unrelated files modified
planner/policy versions updated
diagnostics are bounded and JSON-safe
```

Suggested commit:

```text
nutrition: add generation audit acceptance gates
```

---

# Appendix A — Exact file responsibility map

Use this as a guard against putting logic in the wrong layer.

| File | Responsibility after repair |
|---|---|
| `program_selection.py` | enumerate all active program proposals; infer preferred style only as a soft preference |
| `candidate_selection.py` | pure candidate quality calculation, deterministic comparison, failure aggregation, best-result selection |
| `plan_service.py` | DB/service orchestration; load shared data; loop all program candidates; persist winner; diagnostics |
| `program_adaptation.py` | adapt curated program structure to requested meal/snack counts; no allergy substitution logic |
| `planner_engine.py` | deterministic weekly construction pipeline and final hard feasibility checks |
| `template_substitution.py` | pure safe compatible template fallback/ranking |
| `budget_optimizer.py` | pure bounded economical repair plus minimum-cost feasibility fallback interface for a constructed candidate |
| `portion_solver.py` | deterministic bounded gram optimization within catalogue portion limits |
| `scientific.py` | calculate scientifically valid targets; distinguish target feasibility from training-goal coaching |
| `preference_snapshot.py` | immutable user-specific preference/adherence data contract |
| `adherence_service.py` | existing adherence/feedback persistence and reporting; source of data, not planner kernel |
| `planner_policy.py` | explicit algorithm limits, tolerances, repair iteration caps and version identifiers |
| `meal_catalogue.py` | verified Meal Catalogue semantics; not a bypassable fallback factory |
| `program_catalogue_seed_data.py` | curated canonical weekly structures; do not duplicate per dietary restriction |
| `price_mass_conversion.py` | deterministic price-unit/mass conversion; regression-only unless bug reproduced |
| `generate_100_profiles_audit_report.py` | reproducible end-to-end quality/safety/selection audit |

---

# Appendix B — Recommended new internal data contracts

These are architectural targets for the **final Stage 6/7 state**, not a requirement to copy the names character-for-character if the existing code style suggests a cleaner equivalent. Stage 1 may temporarily omit fields that are introduced only by later stages, but the final architecture must converge on equivalent information.

```python
@dataclass(frozen=True)
class ProgramCandidate:
    program: NutritionProgram
    preferred_style: bool
    preconstruction_rank: int
```

```python
@dataclass(frozen=True)
class CandidateQuality:
    core_nutrition_max_deviation: Decimal
    core_nutrition_total_deviation: Decimal
    micronutrient_gap_penalty: Decimal
    diet_quality_penalty: Decimal
    sports_nutrition_distribution_penalty: Decimal
    budget_utilization_penalty: Decimal
    preference_and_feedback_penalty: Decimal
    repetition_penalty: Decimal
    warning_burden: int
    repair_burden: int
    substitution_burden: int
    preferred_program_style_penalty: int
    stable_program_code: str
    stable_variant_key: tuple[str, ...]
```

```python
@dataclass(frozen=True)
class CandidateEvaluation:
    program_id: UUID
    program_code: str
    preconstruction_rank: int
    preferred_style: bool
    result: PlannerResult
    quality: CandidateQuality | None
```

```python
@dataclass(frozen=True)
class CandidateSelection:
    selected: CandidateEvaluation | None
    first_valid: CandidateEvaluation | None
    evaluations: tuple[CandidateEvaluation, ...]
```

```python
@dataclass(frozen=True)
class SubstitutionAction:
    day_index: int
    role: str
    slot_index: int
    requested_template_id: str
    replacement_template_id: str
    reason_code: str
```

```python
@dataclass(frozen=True)
class BudgetRepairAction:
    day_index: int
    role: str
    slot_index: int
    action_type: str
    before_cost_irr: Decimal
    after_cost_irr: Decimal
    saved_irr: Decimal
    reason_code: str
```

```python
@dataclass(frozen=True)
class PortionAdjustmentAction:
    day_index: int
    role: str
    slot_index: int
    food_id: str | None
    before_grams: Decimal
    after_grams: Decimal
    reason_code: str
```

```python
@dataclass(frozen=True)
class PreferenceSnapshot:
    liked_food_ids: tuple[str, ...]
    disliked_food_ids: tuple[str, ...]
    preferred_meal_ids: tuple[str, ...]
    disliked_meal_ids: tuple[str, ...]
    excluded_meal_ids: tuple[str, ...]
    historical_meal_adherence: tuple[tuple[str, Decimal], ...]
    data_sufficient: bool
```

Keep public API contracts stable unless a real product requirement forces a response-schema change.

Most of the new debugging information belongs in existing internal generation diagnostics.

---

# Appendix C — Planner policy additions

Do not hardcode new iteration/search limits in random functions.

Add them to `PlannerPolicy`, with explicit values chosen conservatively after observing current catalogue size.

Expected additions:

```python
maximum_template_substitution_attempts_per_slot: int
maximum_substitutes_per_slot: int
maximum_partial_variants_per_program: int
maximum_full_variants_per_program: int
maximum_candidate_rebuild_attempts: int
maximum_budget_repair_iterations: int
maximum_portion_solver_iterations: int
maximum_combined_repair_passes: int
portion_adjustment_increment_g: Decimal
```

If additional substitution similarity tolerances are needed, make them explicit and test them.

Do not change current:

```text
calorie_tolerance_ratio
macro_tolerance_ratio
flexible_budget_overage_cap
```

without a separate scientific/product justification.

After behavior changes, update planner/policy version strings and any seeded `NutritionPlannerPolicyVersion` data following the repository's existing policy-version conventions.

---

# Appendix D — Failure-code taxonomy

Avoid generic failures when the engine can state the real cause.

Recommended stable reason codes:

### Candidate/schedule

```text
SCHEDULED_TEMPLATE_UNAVAILABLE
NO_COMPATIBLE_TEMPLATE_SUBSTITUTE
SUBSTITUTION_REPETITION_LIMIT_EXHAUSTED
```

### Budget

```text
STRICT_BUDGET_NO_FEASIBLE_REPAIR
FLEXIBLE_BUDGET_NO_FEASIBLE_REPAIR
INSUFFICIENT_LOW_COST_TEMPLATE_COVERAGE
```

### Portion/macros

```text
CALORIE_TARGET_UNREACHABLE_WITH_PORTION_BOUNDS
PROTEIN_TARGET_UNREACHABLE_WITH_PORTION_BOUNDS
CARBOHYDRATE_TARGET_UNREACHABLE_WITH_PORTION_BOUNDS
FAT_TARGET_UNREACHABLE_WITH_PORTION_BOUNDS
MULTI_MACRO_TARGET_UNREACHABLE_WITH_PORTION_BOUNDS
```

### Goal contract

```text
GENERAL_FITNESS_NUTRITION_TARGET
TRAINING_STIMULUS_MISMATCH
TARGETS_GENERATED_WITH_GOAL_COACHING_WARNING
```

Do not rename existing externally consumed codes casually.

If an existing API/test depends on an old code, preserve backward compatibility at the public boundary while recording the more precise internal diagnostic.

---

# Appendix E — Test execution plan

The exact test runner from repository `AGENTS.md` is `pytest`.

Run from `backend/`.

## After Stage 1

```bash
pytest \
  tests/nutrition/test_program_selection.py \
  tests/nutrition/test_candidate_selection.py \
  tests/nutrition/test_planner_engine.py \
  tests/nutrition/test_weekly_plan_api.py
```

## After Stage 2

```bash
pytest \
  tests/nutrition/test_template_substitution.py \
  tests/nutrition/test_program_adaptation.py \
  tests/nutrition/test_planner_engine.py \
  tests/nutrition/test_weekly_plan_api.py
```

## After Stage 3

```bash
pytest \
  tests/nutrition/test_budget_optimizer.py \
  tests/nutrition/test_planner_engine.py \
  tests/nutrition/test_price_mass_conversion.py \
  tests/nutrition/test_food_pricing.py \
  tests/nutrition/test_weekly_plan_api.py
```

## After Stage 4

```bash
pytest \
  tests/nutrition/test_scientific_engine.py \
  tests/nutrition/test_nutrition_estimate_api.py \
  tests/nutrition/test_weekly_plan_api.py
```

## After Stage 5

```bash
pytest \
  tests/nutrition/test_portion_solver.py \
  tests/nutrition/test_planner_engine.py \
  tests/nutrition/test_weekly_plan_api.py
```

## After Stage 6

```bash
pytest \
  tests/nutrition/test_candidate_selection.py \
  tests/nutrition/test_preference_snapshot.py \
  tests/nutrition/test_adherence_api.py \
  tests/nutrition/test_micronutrient_policy.py \
  tests/nutrition/test_planner_engine.py \
  tests/nutrition/test_weekly_plan_api.py
```

If `test_preference_snapshot.py` is not created because the logic fits an existing test module cleanly, use the actual chosen test file instead.

## Before final acceptance

```bash
pytest tests/nutrition
ruff check
mypy
```

Then run the updated 100-profile audit script using its real current CLI. Do not invent new command-line arguments without adding/parser-testing them first.

---

# Appendix F — Stage-by-stage definition of done

## Stage 1 is done when

- UUID modulo is gone from production plan selection.
- all active programs are evaluated.
- first success does not stop search.
- one deterministic best successful candidate wins.
- only winner is persisted.
- selection trace exists.

## Stage 2 is done when

- an incompatible scheduled Meal ID can be replaced safely;
- substitutes come only from already-eligible templates;
- repetition is respected;
- no diet/allergy bypass exists;
- unresolved cases have precise diagnostics.

## Stage 3 is done when

- over-budget candidates are repaired when a safe cheaper alternative exists;
- strict/flexible semantics are unchanged;
- budget repair is deterministic;
- current price/mass regression remains fixed.

## Stage 4 is done when

- safe users are not unnecessarily denied nutrition because training behavior is suboptimal for their goal;
- warnings replace unnecessary hard failures;
- true target/safety failures remain hard.

## Stage 5 is done when

- fixable scale/clamp macro failures are repaired dynamically;
- all portions stay in bounds;
- repair is deterministic and bounded;
- budget and macro constraints survive the combined loop.

## Stage 6 is done when

- final winner uses nutrition quality first;
- micronutrient data confidence is respected;
- preferences/adherence improve tie-breaking;
- safety/scientific targets cannot be overridden by preference.

## Stage 7 is done when

- audit is reproducible;
- all safety invariants are independently validated;
- automatically eligible success is >90%;
- safe resolution is 100%;
- selected plan is never worse than first valid;
- full Nutrition tests/lint/typecheck pass.

---

# Appendix G — What Luna must NOT do

Do not "solve" this roadmap using any of these shortcuts:

```text
❌ choose only the preferred program style
❌ pick a program using user UUID
❌ stop after first success
❌ randomize programs to get more variety
❌ widen tolerances until failures disappear
❌ increase flexible budget cap
❌ ignore strict budget
❌ remove allergy filters
❌ turn missing nutrient data into zero
❌ clone 25 programs into 25 vegan + 25 vegetarian + ...
❌ generate arbitrary unverified fallback meals
❌ allow substitution before safety eligibility
❌ exceed meal ingredient max grams to hit macros
❌ shrink portions below minimum to hit budget
❌ silently change the user's fitness goal
❌ let preferences override nutrition
❌ persist every losing weekly plan
❌ dump huge loser plans into diagnostics
❌ catch every exception and call it infeasible
❌ add an LLM to make deterministic decisions
❌ add unrelated frontend/UI work to this repair
```

The target is not merely a higher success number.

The target is a **safer, more capable deterministic nutrition planner whose success rate improves because it searches and repairs intelligently**.

---

# Appendix H — Recommended implementation commits

Keep each stage reviewable.

```text
1. nutrition: evaluate all program candidates and select best
2. nutrition: substitute incompatible scheduled meal templates
3. nutrition: optimize candidate budgets deterministically
4. nutrition: decouple goal coaching from target generation
5. nutrition: rebalance portions to calorie and macro targets
6. nutrition: rank feasible plans by quality and adherence
7. nutrition: add generation audit acceptance gates
```

Do not squash stages together before they are independently tested unless the repository workflow explicitly requires it.

---

# Appendix I — Final report Luna must provide

At the end, provide a concise implementation report containing:

```text
1. Files created
2. Files modified
3. Planner/policy versions before → after
4. Focused test results for every stage
5. Full Nutrition test result
6. Ruff result
7. Mypy result
8. Historical 100-profile:
   - raw success rate
   - automatically eligible success rate
   - safe resolution rate
   - top remaining failure reasons
9. Frozen holdout:
   - automatically eligible success rate
   - safe resolution rate
   - safety violation counts
10. Extended cohort result, if run
11. Number of profiles where selected best != first valid
12. Allergy/diet/safety/budget violation counts
13. Mean and p95 generation latency
14. Any genuinely unresolved blocker
```

If success remains <=90%, do **not** stop with a generic statement.

Use the final failure histogram to identify the largest remaining factual failure family, repair that family without weakening hard constraints, rerun focused tests, and rerun the audit.

Continue until the acceptance gate is met or a genuine product/safety decision requires user input.

---

# Appendix J — One-sentence architectural target

After this roadmap, Fitsho's Nutrition Engine should no longer ask:

> "Can this one preselected weekly program work?"

It should ask:

> **"Across every approved program and every safe deterministic repair available, which feasible weekly plan best satisfies this user's nutrition targets, safety constraints, budget, preferences, and real-world adherence?"**
