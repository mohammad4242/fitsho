# Fitsho Nutrition Engine — Phase 0 → Phase 5 Implementation Roadmap

> **For Gemini 3.8 Flash / agentic implementation:** execute this roadmap sequentially from Phase 0 through Phase 5. Do not skip phases, do not mix future-phase work into the current phase, and do not perform unrelated refactors.
>
> At the beginning of **every phase**, print `PHASE N — GOAL` and explain:
> 1. what this phase is trying to accomplish,
> 2. why the design decision is being made,
> 3. which files will change,
> 4. which tests prove the phase is correct.
>
> At the end of **every phase**, run its gate. Do not start the next phase until the current gate is green. Continue through Phase 5. Ask the user only if a genuine ambiguity cannot be resolved from the repository or this document.

**Goal:** Rebuild Fitsho's nutrition-plan pipeline so it behaves like the workout program engine: normalize the request, apply hard eligibility, rank a small set of realistic programs, optimize according to the user's nutrition goal, safely substitute incompatible meals, generate a budget-constrained plan plus an ideal reference plan, then explain the trade-off.

**Architecture:** Preserve useful current components instead of rewriting the engine. Program selection happens before expensive weekly construction. Goal science becomes versioned strategies. Hard safety constraints are separated from preferred targets. Budget and ideal plans share the same scientific target.

**Tech Stack:** FastAPI, SQLAlchemy 2, PostgreSQL, Alembic, Pydantic, Python `Decimal`, pytest, React 19, TypeScript, Vite/Vitest.

**Spec:** This file is intentionally a combined approved design + implementation roadmap and is the execution source of truth.

---

# 0. Repository snapshot and current behavior

This roadmap was written against `main` around:

```text
4ba33b31fb7e83c81e46d74c8fabda716645e615
```

Before editing:

```bash
git status --short
git rev-parse HEAD
```

Never reset, clean, discard, or overwrite unrelated local changes. If `HEAD` is newer, re-read the named functions before editing, but preserve this roadmap's behavior.

Current useful pieces:

```text
backend/app/nutrition/
├── scientific.py
├── estimate_service.py
├── plan_service.py
├── program_selection.py
├── program_adaptation.py
├── planner_engine.py
├── planner_policy.py
├── portion_solver.py
├── budget_optimizer.py
├── template_substitution.py
├── candidate_selection.py
├── models.py
├── schemas.py
├── enums.py
├── service.py
├── router.py
├── program_catalogue.py
├── program_catalogue_seed_data.py
├── seed_program_catalogue.py
└── audit_gates.py
```

Current behavior that this roadmap intentionally changes:

- `program_selection.py` returns every active `NutritionProgram`, mainly ordered by preferred `NutritionDietStyle`.
- `plan_service.py` loops through the candidates, adapts each program, runs `plan_week()`, evaluates results, then selects the best success.
- `planner_engine.py` currently owns food filtering, template eligibility, portion repair, budget optimization, nutrient validation, and variant selection.
- `budget_optimizer.py` is mostly a post-construction repair/search mechanism.
- `candidate_selection.py` already provides useful deterministic quality dimensions: core-nutrition deviation, micronutrients, diet quality, budget, preferences, repetition, warning burden, repair burden, substitution burden.
- `scientific.py` already computes BMR/TDEE and basic goal calorie factors, but the five product goals are not five explicit coaching strategies.
- `PlannerInput` requires `weekly_budget_irr` and `budget_mode`; there is no first-class `IDEAL_REFERENCE`.
- hard food exclusion still relies too much on string matching.
- one generation currently produces one weekly plan.
- frontend weekly generation currently expects one plan.

Do not throw these parts away. Refactor orchestration around them.

---

# 1. Non-negotiable product and safety rules

1. New-product dietary scope remains `omnivore` internally, shown as **«ترکیبی (گیاهی+حیوانی)»**. Vegetarian/vegan remain backward-compatible values but unavailable for new selection until catalogue support exists.
2. Never improve success rate by weakening medical safety, allergies, hard intolerances, religious/cultural hard exclusions, `never_suggest`, refused foods, or nutrient upper limits.
3. Allergy is a hard constraint, not a dislike.
4. A single incompatible meal should normally trigger safe meal substitution, not rejection of the entire weekly program.
5. Physician/manual safety states still block automatic activation.
6. UI uses Toman; backend budget is IRR:
   - 13M Toman = 130M IRR
   - 18M Toman = 180M IRR
   - 1M Toman = 10M IRR
7. Budget tiers:
   - `ECONOMY`: <= 13M Toman/month
   - `NORMAL`: >13M and <=18M
   - `VARIED`: >18M
8. Tiers are ranking bands, not health-quality labels.
9. `IDEAL_REFERENCE` means nutrition-first without user budget cap, not “most expensive”.
10. Budget and ideal plans use the **same scientific target**.
11. Budget plan may miss a preferred target but may never violate a goal-specific hard minimum and still be called fully feasible.
12. Identical input + price snapshot + policy versions must remain deterministic.
13. Keep explicit reason codes and decision traces similar to the workout engine.
14. Do not reorganize nutrition directories during this roadmap.

---

# 2. Scientific evidence and engineering rules

## 2.1 Weight loss

Evidence:
- CDC: gradual loss around 1–2 lb/week (~0.45–0.9 kg/week) is generally more sustainable.
- Major clinical guidance commonly starts near 500–750 kcal/day deficit.
- Resistance-trained fat-loss literature commonly targets ~0.5–1.0% body weight/week.

Rules:
- store `requested_rate`, `recommended_rate`, `applied_rate`;
- a requested aggressive rate must not force an unsafe automatic target.

Sources:
- https://www.cdc.gov/healthy-weight-growth/losing-weight/index.html
- https://pmc.ncbi.nlm.nih.gov/articles/PMC13399222/
- https://pubmed.ncbi.nlm.nih.gov/40841871/
- https://pubmed.ncbi.nlm.nih.gov/34579132/

## 2.2 Protein

Evidence:
- ISSN: ~1.4–2.0 g/kg/day is sufficient for most exercising people.
- Hypocaloric resistance-trained contexts may need more to preserve lean mass; literature often cites ~2.3–3.1 g/kg FFM/day in lean resistance-trained athletes.
- Muscle-gain literature commonly supports ~1.6–2.2 g/kg/day.

Rules:
- use the existing adjusted `protein_calculation_weight_kg` for normal product behavior;
- use FFM-specific ranges only when FFM is reliable;
- do not multiply extreme protein targets by actual body weight in obesity.

Sources:
- https://pubmed.ncbi.nlm.nih.gov/28642676/
- https://pubmed.ncbi.nlm.nih.gov/24092765/
- https://pubmed.ncbi.nlm.nih.gov/34579132/
- https://pmc.ncbi.nlm.nih.gov/articles/PMC6680710/

## 2.3 Muscle-gain surplus

Evidence:
- off-season reviews: ~10–20% surplus for novice/intermediate, more conservative ~5–10% for advanced; rate ~0.25–0.5% body weight/week.
- 2023 trained-lifter experiment comparing maintenance, ~5%, ~15% surplus found faster mass gain mainly increased skinfold/fat accumulation without a clear generalized hypertrophy advantage.

Rule:
- prefer conservative surplus first; scale to experience and requested rate; never assume more surplus = more muscle.

Sources:
- https://pmc.ncbi.nlm.nih.gov/articles/PMC6680710/
- https://pmc.ncbi.nlm.nih.gov/articles/PMC10620361/

## 2.4 Carbohydrate

Evidence:
- carbohydrate can support glycogen and high-volume/long/fasted resistance training;
- 2022 systematic review found no consistent independent performance advantage in normal fed moderate-volume resistance sessions;
- 2026 hypertrophy meta-analysis found no significant independent hypertrophy effect of higher carbohydrate when energy/protein were controlled, with low certainty.

Rule:
- carbohydrate supports training and fills energy after protein/fat; it is not a universal hypertrophy hard threshold and fat loss is not automatically low-carb.

Sources:
- https://pmc.ncbi.nlm.nih.gov/articles/PMC8878406/
- https://pubmed.ncbi.nlm.nih.gov/41712097/
- https://pubmed.ncbi.nlm.nih.gov/35809162/

## 2.5 Fat

Evidence:
- healthy-adult guidance generally supports ~20–35% energy from fat;
- physique literature supports moderate intake and warns against unnecessary very-low-fat approaches.

Rule:
- do not drive fat “as low as possible” in fat loss.

Sources:
- https://pubmed.ncbi.nlm.nih.gov/24342605/
- https://pubmed.ncbi.nlm.nih.gov/24864135/

## 2.6 Recomposition

A 2026 RCT in resistance-trained participants found both isocaloric high-protein and moderate-deficit high-protein protocols with resistance training improved lean-mass outcomes; deficit reduced more fat. Study protein intake: 2.5 g/kg/day.

Rule:
- recomp defaults to maintenance or mild deficit, high protein, resistance-training support; no large automatic deficit.

Source:
- https://pubmed.ncbi.nlm.nih.gov/41940947/

## 2.7 Low energy availability

The 2023 IOC REDs consensus emphasizes health/performance risks from problematic low energy availability. Do not treat one universal `30 kcal/kg FFM/day` threshold as a diagnosis for every user, but use very low estimated energy availability as a conservative warning/review signal when reliable FFM/exercise data exists.

Sources:
- https://pubmed.ncbi.nlm.nih.gov/37752011/
- https://pubmed.ncbi.nlm.nih.gov/38713922/

## 2.8 Healthy/athletic weight gain

A 2022 critical review notes common athlete guidance around +300–500 kcal/day, while evidence that ~0.45 kg/week can be mainly lean mass is limited.

Sources:
- https://pubmed.ncbi.nlm.nih.gov/35233712/
- https://www.nhs.uk/live-well/healthy-weight/managing-your-weight/healthy-ways-to-gain-weight/

---

# 3. Weekly weight-change selector and controller

Add to nutrition profile:

```text
target_weight_change_kg_per_week
```

UI choices:

```text
0.3, 0.4, 0.5, ... 2.0 kg/week
```

Step: `0.1`.

Styling:
- `0.3–1.0`: normal
- `>1.0`: red + **«پیشنهاد نمی‌شود»**

The engine may apply a safer lower rate.

Shown for:
- `lose_weight`: loss rate
- `fat_loss`: loss rate
- `gain_weight`: gain rate
- `build_muscle`: gain rate
- `body_recomposition`: do not show 0.3–2.0 selector; display **«هدف روند وزن: تقریباً ثابت»**

Initial controller:

```python
REQUESTED_WEIGHT_RATE_ENERGY_EQUIVALENT_KCAL_PER_KG = Decimal("7700")

def requested_rate_delta_kcal_per_day(rate_kg_per_week: Decimal) -> Decimal:
    return rate_kg_per_week * REQUESTED_WEIGHT_RATE_ENERGY_EQUIVALENT_KCAL_PER_KG / Decimal("7")
```

This is an **initial engineering estimate**, not a guarantee of real weight change.

Create later in Phase 2:

```python
@dataclass(frozen=True)
class WeightRateResolution:
    requested_kg_per_week: Decimal | None
    recommended_kg_per_week: Decimal | None
    applied_kg_per_week: Decimal | None
    calorie_delta_kcal_per_day: Decimal
    was_clamped: bool
    warning_codes: tuple[str, ...]
```

Reason codes:

```text
WEIGHT_RATE_ABOVE_RECOMMENDED
WEIGHT_RATE_CLAMPED_FOR_AUTOMATIC_SAFETY
WEIGHT_RATE_NOT_USED_FOR_RECOMPOSITION
```

---

# 4. Target architecture

```text
Profile + Exercise + Safety
          |
          v
NormalizedNutritionRequest
          |
          v
Scientific Base: BMR/TDEE
          |
          v
GoalStrategy
          |
          v
Program Cost Preflight
          |
          v
Program Hard Eligibility
          |
          v
Program Scoring / Ranking
          |
          v
Top-5 batch (+ fallback batch if needed)
          |
          v
Program Adaptation
          |
          v
Structured Food Constraints
          |
          v
Safe Meal Substitution
          |
     +----+----+
     |         |
     v         v
 BUDGET      IDEAL
     |         |
     v         v
 Planner     Planner
     |         |
     +----+----+
          |
          v
PlanComparisonReport
          |
          v
1-plan / 2-plan UX
```


---

# PHASE 0 — Nutrition selection framework

## PHASE 0 — GOAL

Make nutrition program selection structurally resemble the workout engine **without intentionally changing user-visible nutrition outcomes yet**.

Create:

```text
normalized request
-> hard eligibility
-> scoring
-> ranking
-> decision trace
```

### Why this decision

The workout engine is easier to audit because hard rejection and soft ranking are distinct. Nutrition currently goes from a loose style preference to expensive construction of every active program. Before smarter behavior, create clean seams.

## Files to create

### `backend/app/nutrition/nutrition_request.py`

Single responsibility: canonical normalized engine request.

Create:

```python
from dataclasses import dataclass
from decimal import Decimal

@dataclass(frozen=True)
class NormalizedNutritionRequest:
    user_id: str
    fitness_goal: str
    body_weight_kg: Decimal
    protein_calculation_weight_kg: Decimal
    tdee_kcal: Decimal
    monthly_budget_irr: int
    weekly_budget_irr: int
    budget_style: str
    trains: bool
    exercise_type: str | None
    training_days_per_week: int | None
    training_minutes_per_session: int | None
    training_intensity: str | None
    training_experience: str | None
    main_meal_slots: int
    snack_slots: int
    dietary_pattern: str
    maximum_meal_repetition_per_week: int
    preferred_variety: str
    requested_weight_change_kg_per_week: Decimal | None
```

In Phase 0 `requested_weight_change_kg_per_week` remains `None`; Phase 2 wires persistence/UI.

### `backend/app/nutrition/program_eligibility.py`

Single responsibility: pure hard eligibility.

```python
@dataclass(frozen=True)
class ProgramHardRejection:
    program_code: str
    reason_codes: tuple[str, ...]

@dataclass(frozen=True)
class ProgramEligibilityResult:
    eligible: bool
    reason_codes: tuple[str, ...]
```

Phase-0 hard eligibility should only represent already-certain structural requirements. Do not invent budget hard rejection yet.

### `backend/app/nutrition/program_scoring.py`

Single responsibility: pure deterministic preconstruction score.

```python
@dataclass(frozen=True)
class ProgramScore:
    budget_score: int
    goal_score: int
    training_score: int
    meal_structure_score: int
    preference_score: int
    total: int

@dataclass(frozen=True)
class ProgramScoringResult:
    score: ProgramScore
    reason_codes: tuple[str, ...]
```

In Phase 0, preserve current style-preference behavior as closely as possible. Phase 1/2 make the components meaningful.

### Tests to create

```text
backend/tests/nutrition/test_nutrition_request.py
backend/tests/nutrition/test_program_eligibility.py
backend/tests/nutrition/test_program_scoring.py
```

## Files to modify

### `backend/app/nutrition/program_selection.py`

Refactor `ProgramCandidate`:

```python
@dataclass(frozen=True)
class ProgramCandidate:
    program: NutritionProgram
    score: ProgramScoringResult
    preconstruction_rank: int
```

Add:

```python
@dataclass(frozen=True)
class ProgramSelectionResult:
    programs_considered: int
    hard_rejections: tuple[ProgramHardRejection, ...]
    candidates: tuple[ProgramCandidate, ...]
    policy_version: str

    def decision_trace(self) -> dict[str, object]:
        ...
```

Keep a compatibility wrapper only if existing callers/tests still require it.

### `backend/app/nutrition/plan_service.py`

After current profile/estimate/exercise data is loaded:

1. build `NormalizedNutritionRequest` once;
2. call new selection orchestration;
3. consume `ProgramSelectionResult.candidates`;
4. store in generation snapshot:

```text
program_selection_policy_version
program_selection_trace
```

### `backend/app/nutrition/planner_policy.py`

Add:

```python
PROGRAM_SELECTION_POLICY_VERSION = "nutrition-program-selection-v3"
```

Do not change calorie or macro tolerances in Phase 0.

### `backend/tests/nutrition/test_program_selection.py`

Add exact behavioral tests:

```text
inactive program is rejected
deterministic ordering
same input -> same trace
all currently active structurally-valid programs remain Phase-0 candidates
style preference remains behaviorally compatible
```

### `backend/tests/nutrition/test_weekly_plan_api.py`

Assert selection trace and policy version are captured in input snapshot.

## Phase 0 execution sequence

- [ ] Write the new failing tests.
- [ ] Run them and verify failure due to missing interfaces.
- [ ] Create `nutrition_request.py`.
- [ ] Create `program_eligibility.py`.
- [ ] Create `program_scoring.py`.
- [ ] Refactor `program_selection.py`.
- [ ] Wire `plan_service.py`.
- [ ] Persist decision trace.
- [ ] Run focused tests.
- [ ] Run all nutrition tests.
- [ ] Commit Phase 0 separately.

Suggested commit:

```bash
git add backend/app/nutrition backend/tests/nutrition
git commit -m "refactor(nutrition): add explicit program selection framework"
```

## PHASE 0 GATE

```bash
cd backend

uv run pytest \
  tests/nutrition/test_nutrition_request.py \
  tests/nutrition/test_program_eligibility.py \
  tests/nutrition/test_program_scoring.py \
  tests/nutrition/test_program_selection.py \
  tests/nutrition/test_weekly_plan_api.py -q

uv run pytest tests/nutrition -q
uv run ruff check app/nutrition tests/nutrition
```

Expected: architecture changed; no intentional nutrition-result change yet.

Do not start Phase 1 until green.

---

# PHASE 1 — Budget tiers, cost preflight, realistic ranking

## PHASE 1 — GOAL

Stop obviously unrealistic expensive programs from dominating early candidate selection for low-budget users.

A user with a 9M Toman monthly budget should normally start with programs that can realistically fit ~9M, rather than beginning with expensive fish/red-meat-heavy schedules and repairing them only after full construction.

## Important design choice

Use **two cost concepts**:

```text
budget_tier_hint
```

A catalogue/admin hint for initial program classification.

```text
effective_budget_tier
```

Calculated at runtime from current verified prices + this user's calorie/meal targets.

Runtime tier is authoritative for ranking.

## Files to create

### `backend/app/nutrition/program_costing.py`

Create:

```python
@dataclass(frozen=True)
class ProgramCostEstimate:
    program_code: str
    estimated_monthly_cost_irr: Decimal
    minimum_adapted_monthly_cost_irr: Decimal | None
    effective_budget_tier: str
    price_coverage_complete: bool
    estimate_confidence: str
    reason_codes: tuple[str, ...]
```

Behavior:

1. adapt program to user main/snack structure;
2. derive slot energy from the same target used by Planner;
3. estimate scheduled meal cost at target energy using verified live prices;
4. produce reference monthly cost;
5. produce a conservative minimum-adapted cost only when a safe substitute lower bound is actually established;
6. if price/search coverage is incomplete, mark uncertainty and do not claim impossibility.

### `backend/scripts/audit_nutrition_program_budget_tiers.py`

Use a canonical reference profile:

```text
2200 kcal/day
3 main meals
1 snack
omnivore
no exclusions
verified current price snapshot
```

Output:

```text
program_code
diet_style
reference_monthly_cost_toman
minimum_adapted_monthly_cost_toman
budget_tier_hint
price_coverage
```

### `backend/tests/nutrition/test_program_costing.py`

Test:

```text
tier boundaries
IRR/Toman conversion
same prices -> deterministic estimate
missing price -> uncertain, not false hard rejection
cheaper safe substitute can lower minimum-adapted cost
```

## Files to modify

### `backend/app/nutrition/enums.py`

Add:

```python
class NutritionBudgetTier(StrEnum):
    ECONOMY = "economy"
    NORMAL = "normal"
    VARIED = "varied"
```

### `backend/app/nutrition/planner_policy.py`

Add:

```python
ECONOMY_MONTHLY_MAX_IRR = 130_000_000
NORMAL_MONTHLY_MAX_IRR = 180_000_000
PROGRAM_COSTING_POLICY_VERSION = "nutrition-program-costing-v1"
INITIAL_PROGRAM_BATCH_SIZE = 5
```

Resolver:

```text
<=130M IRR -> ECONOMY
>130M and <=180M -> NORMAL
>180M -> VARIED
```

### `backend/app/nutrition/models.py`

Add nullable/explicit `budget_tier_hint` to `NutritionProgram`.

This is a hint because effective cost changes with:
- live food prices,
- calorie target,
- meal count,
- substitutions.

### Alembic

Create the next valid migration revision. Add the new column safely. Do not rewrite old migrations.

### `backend/app/nutrition/schemas.py`

Add `budget_tier_hint` to NutritionProgram admin write/read models.

### `backend/app/nutrition/program_catalogue_seed_data.py`

Assign initial hints to all 25 programs **after running the audit**.

Rules:

```text
ECO* -> expected ECONOMY unless audit disproves
PREM* -> expected VARIED unless audit disproves
IRN*, GYM*, FAST* -> derive hint from audited reference cost, not prefix alone
```

Reason: current GYM programs include a mix of chicken, fish, beef/red-meat-style meals; “GYM” is not a price category.

### `backend/app/nutrition/seed_program_catalogue.py`

Persist hint.

### `backend/app/nutrition/program_scoring.py`

Implement real budget scoring.

Target preconstruction weighting for Budget mode:

```text
Budget fit          40%
Goal affinity       25%
Training fit        10%
Meal structure      10%
Preference/variety  15%
```

Phase 1 fully implements budget fit; Phase 2 fills richer goal/training logic.

Budget behavior:

```text
within budget / same tier -> high
slightly above but adaptably reachable -> moderate penalty
one tier above -> strong penalty
two tiers above -> very strong penalty
proven minimum > budget cap -> hard reject
uncertain lower bound -> never hard reject
```

Reason codes:

```text
BUDGET_TIER_MATCH
BUDGET_TIER_ONE_LEVEL_HIGHER
BUDGET_TIER_TWO_LEVELS_HIGHER
PROGRAM_COST_WITHIN_USER_BUDGET
PROGRAM_COST_ABOVE_USER_BUDGET
PROGRAM_BUDGET_PROVABLY_INFEASIBLE
PROGRAM_COST_PREFLIGHT_UNCERTAIN
```

### `backend/app/nutrition/program_eligibility.py`

Hard budget rejection only when:

```python
minimum_adapted_monthly_cost_irr is not None
and minimum_adapted_monthly_cost_irr > allowed_monthly_budget_cap
```

Search failure is not automatically proof of infeasibility.

### `backend/app/nutrition/program_selection.py`

Rank all eligible programs, but construction occurs in batches:

```text
rank
-> try top 5
-> if no successful final plan, try next 5
-> continue bounded batches until success exists or candidates exhausted
```

This preserves fallback coverage while improving normal performance.

### `backend/app/nutrition/plan_service.py`

Stop eagerly constructing every candidate.

Decision trace must record:

```text
programs_considered
programs_hard_rejected
programs_constructed
fallback_batches_used
program_cost_estimates
```

### Admin frontend

Modify:

```text
frontend/src/features/admin/types.ts
frontend/src/features/admin/AdminNutritionProgramsPage.tsx
frontend/src/features/admin/AdminNutritionProgramEditorPage.tsx
```

Show `Budget tier hint`. Make clear it is catalogue metadata, not a live user quote.

Update their tests.

## PHASE 1 GATE

```bash
cd backend

uv run pytest \
  tests/nutrition/test_program_costing.py \
  tests/nutrition/test_program_eligibility.py \
  tests/nutrition/test_program_scoring.py \
  tests/nutrition/test_program_selection.py \
  tests/nutrition/test_budget_optimizer.py \
  tests/nutrition/test_weekly_plan_api.py -q

uv run python scripts/audit_nutrition_program_budget_tiers.py
uv run pytest tests/nutrition -q
uv run ruff check app/nutrition scripts tests/nutrition
```

Frontend:

```bash
cd frontend
npm test
npm run lint
npm run build
```

Commit:

```bash
git commit -m "feat(nutrition): rank program candidates by live budget feasibility"
```

Do not start Phase 2 until green.

---

# PHASE 2 — Five evidence-based Goal Algorithms

## PHASE 2 — GOAL

Replace the current coarse goal factors with five explicit, versioned coaching strategies:

```text
LOSE_WEIGHT
FAT_LOSS
GAIN_WEIGHT
BUILD_MUSCLE
BODY_RECOMPOSITION
```

Each strategy must influence:

```text
calorie target
protein band
fat band
carbohydrate remainder/preference
weekly rate resolution
program preconstruction scoring
portion optimization priorities
training-nutrition quality
candidate selection quality
```

### Why this decision

The five goals are not merely five calorie multipliers. A real coach changes the optimization objective:

- generic weight loss prioritizes sustainable deficit and adherence;
- fat loss prioritizes lean-mass retention and training support;
- healthy weight gain prioritizes adequate energy without forcing bodybuilding macros;
- muscle gain prioritizes hypertrophy support while limiting unnecessary fat gain;
- recomposition prioritizes high protein, resistance training and maintenance/mild deficit.

Do not scatter `if fitness_goal == ...` branches across Planner. Put goal policy in one versioned component and let Planner consume resolved targets.

## Files to create

### `backend/app/nutrition/nutrition_targets.py`

Purpose: avoid a circular dependency between `scientific.py` and `goal_strategy.py`.

Move the shared pure data structures from `scientific.py` here:

```python
@dataclass(frozen=True)
class TargetBand:
    unit: str
    minimum: Decimal | None = None
    preferred: Decimal | None = None
    preferred_maximum: Decimal | None = None
    maximum: Decimal | None = None

@dataclass(frozen=True)
class NutrientTargets:
    carbohydrate: TargetBand
    total_fat: TargetBand
    fibre: TargetBand
    free_sugar: TargetBand
    added_sugar: TargetBand
    saturated_fat: TargetBand
    trans_fat: TargetBand
    sodium: TargetBand
```

`scientific.py` may re-export/import `TargetBand` for compatibility, but there must be one canonical definition.

### `backend/app/nutrition/weight_rate_policy.py`

Create:

```python
from dataclasses import dataclass
from decimal import Decimal

WEIGHT_RATE_POLICY_VERSION = "nutrition-weight-rate-v1"
KCAL_PER_KG_ENGINEERING_ESTIMATE = Decimal("7700")

@dataclass(frozen=True)
class WeightRateResolution:
    requested_kg_per_week: Decimal | None
    recommended_kg_per_week: Decimal | None
    applied_kg_per_week: Decimal | None
    calorie_delta_kcal_per_day: Decimal
    was_clamped: bool
    warning_codes: tuple[str, ...]
```

Public pure functions:

```python
def requested_rate_delta_kcal_per_day(rate_kg_per_week: Decimal) -> Decimal:
    ...

def resolve_weight_rate(
    *,
    goal: str,
    body_weight_kg: Decimal,
    tdee_kcal: Decimal,
    requested_kg_per_week: Decimal | None,
    training_experience: str | None,
) -> WeightRateResolution:
    ...
```

The `7700 kcal/kg` value is an initial control approximation. Add a docstring that explicitly says:

```text
This converts a requested scale-weight rate into an initial energy-control
signal. It does not predict or guarantee real-world weight change.
```

### `backend/app/nutrition/goal_strategy.py`

Create:

```python
@dataclass(frozen=True)
class GoalMacroStrategy:
    goal: str
    goal_calories: TargetBand
    protein: TargetBand
    carbohydrate: TargetBand
    total_fat: TargetBand
    fibre: TargetBand
    target_weight_rate: WeightRateResolution
    protein_distribution_g_per_meal: Decimal | None
    training_carbohydrate_priority: str
    energy_density_preference: str
    goal_reason_codes: tuple[str, ...]
```

Public function:

```python
def resolve_goal_strategy(
    inputs: ScientificInputs,
    *,
    bmr: TargetBand,
    tdee: TargetBand,
    protein_calculation_weight_kg: Decimal,
    reliable_ffm_kg: Decimal | None = None,
) -> GoalMacroStrategy:
    ...
```

If importing `ScientificInputs` creates a cycle, define a narrow `GoalStrategyInputs` dataclass in `goal_strategy.py` and have `scientific.py` map to it. Prefer the narrow input object; do not use `TYPE_CHECKING` tricks to hide a real cyclic design.

Recommended exact narrow object:

```python
@dataclass(frozen=True)
class GoalStrategyInputs:
    fitness_goal: str
    body_weight_kg: Decimal
    protein_calculation_weight_kg: Decimal
    requested_weight_change_kg_per_week: Decimal | None
    exercise_type: str | None
    training_days_per_week: int | None
    training_minutes_per_session: int | None
    training_experience: str | None
```

### Tests to create

```text
backend/tests/nutrition/test_weight_rate_policy.py
backend/tests/nutrition/test_goal_strategy.py
backend/tests/nutrition/test_nutrition_targets.py
```

---

## Phase 2A — `LOSE_WEIGHT`

### Coaching objective

Reduce scale weight at a sustainable rate while preserving reasonable lean mass, food quality and adherence.

### Weekly-rate resolution

Default recommendation if the user has not selected a rate:

```text
0.5 kg/week
```

User-selected rate remains stored exactly.

Theoretical initial energy delta:

```text
0.3 kg/week ≈ 330 kcal/day deficit
0.5 kg/week ≈ 550 kcal/day deficit
0.7 kg/week ≈ 770 kcal/day deficit
1.0 kg/week ≈ 1100 kcal/day theoretical deficit
```

Do not apply the theoretical number blindly.

Recommended automatic controller:

```python
recommended_rate = Decimal("0.5")

max_rate_from_body_weight = body_weight_kg * Decimal("0.01")  # 1% BW/week
max_deficit_kcal = min(
    Decimal("1000"),
    tdee_kcal * Decimal("0.25"),
)

applied_deficit = min(
    requested_rate_delta,
    max_deficit_kcal,
)
```

Also preserve the current project's conservative lower-energy guard. Do not remove an existing BMR/medical safety floor simply to satisfy the requested rate. Treat that floor as a product safety guard, not a claim that BMR is a universal clinical prescription floor.

If clamped:

```text
WEIGHT_RATE_ABOVE_RECOMMENDED
WEIGHT_RATE_CLAMPED_FOR_AUTOMATIC_SAFETY
```

### Protein

Use `protein_calculation_weight_kg`, not blindly actual body weight.

Without resistance/mixed training:

```text
minimum:   ~1.2 g/kg
preferred: ~1.4–1.6 g/kg
```

With resistance/mixed training:

```text
minimum:   ~1.4–1.6 g/kg
preferred: ~1.6–2.0 g/kg
```

Use one deterministic preferred value inside each range based on training volume, e.g.:

```text
light/moderate RT -> 1.6–1.8
higher RT demand  -> 1.8–2.0
```

### Fat

```text
preferred: 25–30% of calories
general acceptable target band: 20–35%
```

Do not target 15% in ordinary weight loss.

### Carbohydrate

Compute carbohydrate from energy remaining after preferred protein and fat:

```text
carb_kcal = goal_kcal - protein_kcal - fat_kcal
```

Clamp only to evidence/safety bands and rebalance fat/protein if required.

No universal low-carb rule.

### Program/meal scoring

Positive:

```text
protein density
fibre density
micronutrient adequacy
moderate/lower energy density
fruit/vegetable presence where represented
good user preference/adherence
```

Negative:

```text
free-sugar burden
saturated-fat excess
extremely energy-dense structure that makes deficit difficult
```

---

## Phase 2B — `FAT_LOSS`

### Coaching objective

Reduce fat mass while preserving lean mass and resistance-training performance.

This is more body-composition/sports-focused than generic `LOSE_WEIGHT`.

### Weekly-rate resolution

Evidence anchor:

```text
~0.5–1.0% body weight/week
```

Default recommendation:

```text
~0.5% body weight/week
```

If reliable body-fat/FFM context suggests a lean, well-trained user, bias toward the slower end.

Automatic rate cap:

```text
<=1.0% body weight/week
```

Automatic energy-deficit cap for ordinary Fitsho planning:

```python
max_deficit_kcal = min(
    Decimal("750"),
    tdee_kcal * Decimal("0.20"),
)
```

Why more conservative than generic scale-weight loss: lean-mass/performance preservation. A meta-regression found prolonged deficits around 500 kcal/day can prevent lean-mass gains during resistance training, while sport fat-loss reviews emphasize slow loss for FFM retention.

Do not claim 750 is a universal medical boundary; it is the automatic product ceiling for this strategy.

### Protein

If reliable FFM exists and user is resistance-trained, support an expert branch informed by:

```text
~2.3–3.1 g/kg FFM/day
```

For ordinary product behavior based on Fitsho's adjusted calculation weight:

```text
minimum:   ~1.8 g/kg calculation weight
preferred: ~2.0–2.4 g/kg calculation weight
```

For non-resistance users:

```text
preferred: ~1.6–2.0 g/kg calculation weight
```

Never apply `3 g/kg` to actual weight in obesity.

### Fat

```text
preferred: 20–30% calories
```

A ~15% energy lower boundary may exist in physique literature but is not the target.

### Carbohydrate

Fill remaining calories after protein/fat.

For resistance-trained users, use:

```text
~2–5 g/kg/day
```

as a **soft training-support preference where total calories permit**, not a hard universal requirement.

### Protein distribution

Where meal count allows, quality bonus for:

```text
~0.40–0.55 g/kg per protein feeding
3–6 feedings/day
```

This is a scoring preference, not a hard reason to reject a safe plan.

### Program/meal scoring

Strong positive:

```text
high protein per 100 kcal
fibre
micronutrient adequacy
moderate energy density
distributed protein
training-compatible carbohydrate placement
```

Do not implement:

```text
fat_loss == low_carb
fat_loss == almost_zero_fat
```

---

## Phase 2C — `GAIN_WEIGHT`

### Coaching objective

Gradual healthy body-mass gain. This goal is not automatically bodybuilding.

### Weekly-rate resolution

Default recommendation:

```text
0.3 kg/week
```

Recommended user-facing healthy automatic range:

```text
~0.3–0.5 kg/week
```

The UI still allows `0.3–2.0`; values `>1.0` are red, but backend also bounds them.

Initial preferred surplus:

```text
~300–500 kcal/day
```

Automatic ceiling:

```python
max_surplus_kcal = min(
    Decimal("750"),
    tdee_kcal * Decimal("0.20"),
)
```

For an ordinary gain-weight user, do not automatically chase 2 kg/week.

### Protein

No resistance training:

```text
preferred: ~1.2–1.6 g/kg calculation weight
```

Resistance/mixed training:

```text
preferred: ~1.6–2.0 g/kg calculation weight
```

Avoid excessive protein that unnecessarily displaces energy/carbohydrate/fat and may make a calorie surplus harder to consume.

### Fat

```text
preferred: 25–35% calories
```

Use healthy energy-dense sources when useful.

### Carbohydrate

Remainder after protein/fat.

For active users, carbohydrate gets a positive training/energy score.

### Program/meal scoring

Positive:

```text
nutrient-dense energy
reasonable energy density
easy portion expansion
carbohydrate adjuster capacity
healthy fat adjuster capacity
adequate protein
high adherence/ease of eating
```

Do not implement:

```text
gain_weight -> unlimited fat
```

Saturated fat, free sugar, fibre, sodium and micronutrient rules stay active.

---

## Phase 2D — `BUILD_MUSCLE`

### Coaching objective

Support resistance-training hypertrophy while minimizing unnecessary fat gain.

### Training alignment

Resistance/mixed training strongly preferred.

If absent, preserve the existing Fitsho coaching-warning behavior:

```text
TRAINING_STIMULUS_MISMATCH
TARGETS_GENERATED_WITH_GOAL_COACHING_WARNING
```

Do not hard-fail solely because resistance training is absent; do not pretend nutrition alone is a hypertrophy program.

### Weekly-rate resolution

Evidence anchor:

```text
~0.25–0.5% body weight/week
```

Recommended:

```text
first_month/beginner/intermediate -> toward 0.25–0.5% BW/week
advanced -> toward ~0.25% BW/week
```

The user can request 0.3–2.0 kg/week, but the **applied** muscle-gain rate must be clamped to experience/body-weight policy.

### Calories

Recommended starting surplus:

```text
advanced:
  ~5–10% TDEE

first_month/beginner/intermediate:
  ~5–15% TDEE
```

Allow movement toward the older 10–20% off-season range only when requested rate, training status and body-composition context justify it.

Automatic hard ceiling:

```text
20% TDEE
```

The 2023 surplus study is the reason the modern default is conservative: faster mass gain can increase fat accumulation without clear generalized hypertrophy benefit.

### Protein

```text
minimum:   ~1.6 g/kg calculation weight
preferred: ~1.8–2.2 g/kg calculation weight
```

### Fat

```text
preferred: ~20–30% calories
```

A practical g/kg range can be used internally, but the total-energy percentage and hard scientific limits remain authoritative.

### Carbohydrate

After protein and fat, allocate remaining energy to carbohydrate.

For high-volume resistance training:

```text
soft preferred range ~3–5 g/kg/day when feasible
```

Do **not** fail a scientifically good muscle-gain plan solely because it is below 3–5 g/kg. The 2026 meta-analysis does not support treating higher carbohydrate as an independent hypertrophy requirement when energy/protein are controlled.

### Program/meal scoring

Strong positive:

```text
protein target capacity
protein distribution capacity
easy carbohydrate scaling
pre/post-training compatibility
portion headroom
ability to reach surplus without absurd portions
moderate fat
```

---

## Phase 2E — `BODY_RECOMPOSITION`

### Coaching objective

Improve fat mass and lean mass simultaneously. Scale weight is secondary.

### Weekly-rate selector

Do not show the 0.3–2.0 selector.

Use:

```text
requested_rate = null
applied_rate ≈ 0
```

Frontend copy:

```text
هدف روند وزن: تقریباً ثابت
```

### Training alignment

Resistance/mixed training receives strong goal score.

If absent, preserve:

```text
TRAINING_STIMULUS_MISMATCH
TARGETS_GENERATED_WITH_GOAL_COACHING_WARNING
```

### Calories

Default:

```text
~maintenance / TDEE
```

Only when there is a **reliable** body-composition signal indicating higher fat stores and no safety conflict:

```text
mild deficit ~5–10% TDEE
```

Do not infer high body fat from weak or absent data merely to create a deficit.

For resistance-trained recomposition, avoid a large prolonged deficit by default. Evidence indicates ~500 kcal/day deficits can impair lean-mass gains during RT.

### Protein

Maintenance-calorie recomp:

```text
preferred: ~1.8–2.2 g/kg calculation weight
```

Mild-deficit recomp:

```text
preferred: ~2.0–2.4 g/kg calculation weight
```

A healthy resistance-trained context with reliable data may move toward ~2.5 g/kg when justified, consistent with the 2026 RCT, but 2.5 is not universal.

### Fat

```text
preferred: ~20–30% calories
```

### Carbohydrate

Remainder after protein/fat.

Soft training-support preference:

```text
~2–4 g/kg/day where feasible
```

### Program/meal scoring

Strong positive:

```text
high protein
protein distribution
resistance-training support
fibre/micronutrients
moderate energy density
high adherence
low unnecessary repair burden
```

---

# Phase 2 repository changes

## `backend/app/nutrition/scientific.py`

Keep here:

```text
Mifflin BMR
activity multiplier
exercise energy
TDEE
confidence
generic nutrient upper limits
generic sugar/sodium/fibre rules
training-alignment warning framework
```

Move/delegate:

```text
five-goal calorie/macro strategy -> goal_strategy.py
weekly-rate resolution -> weight_rate_policy.py
shared TargetBand/NutrientTargets -> nutrition_targets.py
```

`calculate_targets()` becomes conceptually:

```text
calculate BMR
-> calculate TDEE
-> resolve protein calculation weight
-> build GoalStrategyInputs
-> resolve_goal_strategy()
-> derive generic nutrient limits from strategy calories
-> validate macro energy feasibility
-> return ScientificResult
```

### Energy-consistent macro resolver

Add a single pure resolver, preferably inside `goal_strategy.py`:

```python
def resolve_energy_consistent_macros(
    *,
    calories: Decimal,
    protein: TargetBand,
    preferred_fat_ratio: Decimal,
    fat_min_ratio: Decimal,
    fat_max_ratio: Decimal,
    carbohydrate_soft_min_g: Decimal | None,
    carbohydrate_soft_max_g: Decimal | None,
) -> tuple[TargetBand, TargetBand]:
    ...
```

Algorithm:

1. choose preferred protein within its band;
2. choose preferred fat within its goal band;
3. carbohydrate gets remaining energy;
4. if carbohydrate is outside a **hard** bound, clamp and rebalance fat first, then protein within allowed bands;
5. soft carbohydrate ranges affect quality, not hard feasibility;
6. verify:

```text
protein*4 + carbs*4 + fat*9
```

is within a tight rounding tolerance of goal calories.

Do not recreate the previous mathematically contradictory macro target problem.

## `backend/app/nutrition/models.py`

Add to `NutritionProfile`:

```text
target_weight_change_kg_per_week
```

Recommended type:

```text
Numeric(3, 1), nullable=True
```

Positive magnitude only. Direction comes from `fitness_goal`.

## Alembic

Create next valid migration.

Old profiles remain valid with `NULL`.

## `backend/app/nutrition/schemas.py`

Add:

```python
target_weight_change_kg_per_week: Decimal | None
```

Field-level accepted numeric range:

```text
0.3–2.0 when non-null
```

Goal-specific requirement/null behavior cannot be fully validated inside NutritionProfile alone because `fitness_goal` lives in the shared profile. Perform final cross-object validation in the nutrition service/estimate orchestration.

## `backend/app/nutrition/service.py`

Persist/return the field.

When saving nutrition profile:

```text
lose_weight/fat_loss/gain_weight/build_muscle:
  rate may be supplied

body_recomposition:
  force/require null
```

For old/legacy goal values, preserve compatible behavior and do not invent a new rate.

## `backend/app/nutrition/estimate_service.py`

Pass to scientific resolution:

```text
requested rate
training experience when available
reliable FFM/body-composition only when source confidence is acceptable
```

Persist in estimate input snapshot:

```text
requested_weight_change_kg_per_week
recommended_weight_change_kg_per_week
applied_weight_change_kg_per_week
weight_rate_policy_version
goal_strategy_version
goal_strategy_reason_codes
```

## `backend/app/nutrition/program_scoring.py`

Goal scoring must consume resolved `GoalMacroStrategy`.

Do not hardcode:

```text
"salmon good"
"beef bad"
"chicken good"
```

Derive meal/program features from data:

```text
protein density
fibre density
energy density
carbohydrate scaling capacity
fat scaling capacity
portion headroom
protein distribution capacity
training-slot compatibility
micronutrient adequacy
```

Goal-specific score consumes these features.

## `backend/app/nutrition/candidate_selection.py`

Add explicit:

```text
goal_target_penalty
```

and implement the currently-placeholder sports nutrition distribution dimension.

Examples:

```text
fat_loss -> protein shortfall + distribution + training support
build_muscle -> surplus/protein capacity + training support
recomp -> protein + training support
gain_weight -> calorie/portion scalability
lose_weight -> deficit adherence + fibre/protein density
```

Do not compare goal quality before hard safety feasibility.

## `backend/app/nutrition/planner_engine.py`

Planner receives resolved targets and goal-quality hints.

Do not add five separate goal implementations here.

## `backend/app/nutrition/planner_policy.py`

Add version constants:

```python
GOAL_STRATEGY_VERSION = "nutrition-goal-strategy-v1"
WEIGHT_RATE_POLICY_VERSION = "nutrition-weight-rate-v1"
MACRO_RESOLUTION_POLICY_VERSION = "nutrition-macro-resolution-v2"
```

Keep numeric constants centralized and versioned.

## Frontend

Modify:

```text
frontend/src/features/nutrition/types.ts
frontend/src/features/nutrition/NutritionOnboardingFlow.tsx
frontend/src/features/nutrition/NutritionOnboardingFlow.test.tsx
frontend/src/features/nutrition/NutritionEstimatePage.tsx
frontend/src/features/nutrition/NutritionEstimatePage.test.tsx
```

Use the existing shared-profile fitness goal; do not create a duplicate goal field.

If `NutritionOnboardingFlow` currently does not receive the shared goal, pass it from its existing parent/route state.

Add rate control:

```text
هفته‌ای چقدر می‌خواهی وزن کم کنی؟
هفته‌ای چقدر می‌خواهی وزن اضافه کنی؟
```

Values:

```text
0.3 ... 2.0 kg/week
```

For values `>1.0`:

```text
red visual state
"پیشنهاد نمی‌شود"
```

If backend clamps the request, `NutritionEstimatePage` shows structured facts:

```text
درخواست شما
مقدار پیشنهادی
مقدار اعمال‌شده
```

Do not show scary warning copy when requested and applied are effectively the same.

## Phase 2 tests

At minimum:

```text
LOSE_WEIGHT + 0.5 kg/week
LOSE_WEIGHT + 2.0 -> clamped + warning
FAT_LOSS + resistance -> higher protein priority than generic LOSE_WEIGHT
FAT_LOSS protein uses adjusted weight unless reliable FFM branch applies
GAIN_WEIGHT + 0.3
GAIN_WEIGHT + 2.0 -> bounded
BUILD_MUSCLE + resistance + beginner
BUILD_MUSCLE + resistance + advanced -> more conservative
BUILD_MUSCLE without resistance -> coaching warning
BODY_RECOMPOSITION + resistance -> maintenance/mild-deficit strategy
BODY_RECOMPOSITION without resistance -> warning
BODY_RECOMPOSITION rate selector absent
all five strategies produce energy-consistent macros
same input -> same result
```

## PHASE 2 GATE

```bash
cd backend

uv run pytest \
  tests/nutrition/test_nutrition_targets.py \
  tests/nutrition/test_weight_rate_policy.py \
  tests/nutrition/test_goal_strategy.py \
  tests/nutrition/test_scientific_engine.py \
  tests/nutrition/test_nutrition_api.py \
  tests/nutrition/test_program_scoring.py \
  tests/nutrition/test_candidate_selection.py -q

uv run pytest tests/nutrition -q
uv run ruff check app/nutrition tests/nutrition
```

Frontend:

```bash
cd frontend
npm test
npm run lint
npm run build
```

Commit:

```bash
git commit -m "feat(nutrition): add five goal-specific nutrition strategies"
```

Do not start Phase 3 until the five strategies and frontend rate flow are green.

---

# PHASE 3 — Structured constraints and safe meal substitution

## PHASE 3 — GOAL

Make restrictions behave like exercise substitution in the workout engine:

```text
unsafe/incompatible food
-> meal becomes incompatible
-> find closest safe meal substitute
-> preserve program if possible
-> reject whole program only when no safe resolution exists
```

### Why this decision

A weekly program is a useful structure. One incompatible meal should not usually destroy the entire candidate. The current engine already has `template_substitution.py`, but hard exclusions are still too dependent on name/slug string matching. This is not safe enough for semantic allergens such as gluten.

## Files to create

### `backend/app/nutrition/food_constraints.py`

This becomes the **single source of truth** for food-level hard/soft constraints.

Create:

```python
from dataclasses import dataclass
from enum import StrEnum

class ConstraintSeverity(StrEnum):
    HARD = "hard"
    SOFT = "soft"

@dataclass(frozen=True)
class NormalizedFoodConstraint:
    code: str
    severity: ConstraintSeverity
    source: str
    raw_label: str | None = None

@dataclass(frozen=True)
class FoodConstraintDecision:
    allowed: bool
    hard_reason_codes: tuple[str, ...]
    soft_penalty_codes: tuple[str, ...]
```

Public functions:

```python
def normalize_food_constraints(...) -> tuple[NormalizedFoodConstraint, ...]:
    ...

def evaluate_food_constraints(
    *,
    food_allergen_tags: tuple[str, ...],
    food_slug: str,
    food_name_fa: str,
    constraints: tuple[NormalizedFoodConstraint, ...],
) -> FoodConstraintDecision:
    ...
```

Structured tags are authoritative.

Legacy text matching can remain only as a conservative compatibility fallback when structured data does not yet cover the user's free-text restriction.

Unknown hard allergy/intolerance text must **not be silently ignored**. If it cannot be normalized with enough confidence, return an explicit unresolved hard-constraint state so automatic planning can stop/review instead of guessing.

Reason code:

```text
UNRESOLVED_HARD_FOOD_CONSTRAINT
```

### `backend/tests/nutrition/test_food_constraints.py`

Must cover:
- known canonical allergen;
- alias normalization;
- unknown hard allergy;
- dislike is soft;
- `never_suggest` is hard;
- structured tag beats misleading display name.

## Files to modify

### `backend/app/nutrition/enums.py`

Add canonical allergen tags relevant to the catalogue.

At minimum:

```text
gluten
wheat
milk
egg
peanut
tree_nut
soy
fish
shellfish
sesame
```

Do not claim these are a complete clinical allergen ontology. They are the explicitly supported verified product taxonomy for this version.

### `backend/app/nutrition/models.py`

Add structured metadata to `NutritionCatalogueFood`:

```text
allergen_tags
```

Use the repository's established PostgreSQL representation for small structured string collections. If JSON is already the stable pattern here, use JSON. If a normalized association table is already the pattern, use that. Do not invent two representations.

### Alembic migration

Create a new revision that adds structured allergen metadata safely.

Existing food rows default to an empty list only after seed/backfill behavior is clear. Do not let an empty list falsely mean “verified allergen-free”; distinguish:

```text
known tags
metadata completeness/verification
```

If needed, add:

```text
allergen_metadata_verified: bool
```

so absence of tags is not automatically proof of absence.

### `backend/app/nutrition/schemas.py`

Admin food write/read models expose allergen tags and metadata verification.

### `backend/app/nutrition/catalogue_seed_data.py`

Annotate all seeded foods that can contain the supported allergens.

Examples:

```text
ordinary wheat breads -> wheat + gluten
milk/yogurt/cheese -> milk
egg -> egg
peanut/peanut butter -> peanut
walnut/nuts -> tree_nut as appropriate
fish -> fish
soy products -> soy
```

Do not infer ordinary lavash as gluten-free.

### `backend/app/nutrition/food_catalogue.py`

Persist/read structured tags.

### Admin food catalogue frontend

Locate the current admin food catalogue editor/API and add:

```text
Allergen tags
Metadata verified
```

Use existing admin patterns; do not create a second duplicate editor.

Update its tests.

### `backend/app/nutrition/planner_engine.py`

Extend `PlannerFood`:

```python
allergen_tags: tuple[str, ...]
allergen_metadata_verified: bool
```

Replace `_excluded()` as the primary hard-constraint mechanism with `food_constraints.py`.

Keep any legacy string fallback in exactly one place, not duplicated.

### `backend/app/nutrition/plan_service.py`

Build normalized constraints once.

Classification:

```text
allergy                 -> HARD
clinically-hard intolerance -> HARD
religious/cultural explicit exclusion -> HARD
never_suggest           -> HARD
refused                 -> HARD

disliked                -> SOFT
liked/favourite         -> positive preference
```

If the current product cannot distinguish “clinically-hard” from softer intolerance in the input model, treat declared intolerance conservatively as hard for automatic planning until the product explicitly models severity.

### `backend/app/nutrition/template_substitution.py`

Extend `SubstitutionContext`:

```python
constraints: tuple[NormalizedFoodConstraint, ...]
optimization_mode: str
```

Ranking order:

```text
1. hard-safe
2. category-compatible
3. preserve required functional roles
4. close to slot target kcal
5. close to slot target protein
6. repetition policy
7. user preference/adherence
8. cost preference only in BUDGET_CONSTRAINED
9. stable deterministic ID
```

Add reason codes:

```text
MEAL_SUBSTITUTED_FOR_ALLERGY
MEAL_SUBSTITUTED_FOR_INTOLERANCE
MEAL_SUBSTITUTED_FOR_HARD_EXCLUSION
NO_SAFE_MEAL_SUBSTITUTE
```

### `backend/app/nutrition/budget_optimizer.py`

Remove duplicated food exclusion logic that can disagree with Planner.

Use the shared constraint evaluator.

Budget optimization must never reintroduce a hard allergen/exclusion to save money.

### `backend/app/nutrition/program_eligibility.py`

Do **not** hard-reject a program just because a scheduled meal is incompatible if a safe category-compatible substitute exists.

Reject only when preflight can establish:

```text
PROGRAM_HARD_CONSTRAINT_UNRESOLVABLE
```

If preflight is uncertain, let bounded construction/substitution attempt resolution.

### `backend/app/nutrition/program_scoring.py`

Add a preconstruction `expected_substitution_burden` penalty.

A naturally compatible program should outrank one needing many replacements, all else equal.

This penalty must not outrank:
- safety,
- goal feasibility,
- budget feasibility.

## Mandatory Phase 3 scenarios

### Gluten

Input:

```text
allergy = gluten
```

Program asks for sangak.

Correct:

```text
sangak -> unsafe
ordinary lavash -> unsafe
other ordinary wheat bread -> unsafe
rice/potato -> can be safe by ingredient
verified gluten-free bread -> safe if metadata confirms
```

### Fish allergy

```text
fish meal -> replace meal
whole weekly program survives when safe substitute exists
```

### Milk allergy

Milk/yogurt/cheese must not re-enter through:
- template substitution,
- portion repair,
- budget optimization.

### Disliked fish

If the user only dislikes fish:

```text
soft penalty / prefer substitute
```

unless user explicitly chose `never_suggest/refused`.

### Unknown allergy

If user entered an unknown hard allergy that cannot be mapped safely:

```text
automatic generation does not guess
UNRESOLVED_HARD_FOOD_CONSTRAINT
```

## PHASE 3 GATE

```bash
cd backend

uv run pytest \
  tests/nutrition/test_food_constraints.py \
  tests/nutrition/test_template_substitution.py \
  tests/nutrition/test_planner_engine.py \
  tests/nutrition/test_budget_optimizer.py \
  tests/nutrition/test_program_eligibility.py \
  tests/nutrition/test_weekly_plan_api.py -q

uv run pytest tests/nutrition -q
uv run ruff check app/nutrition tests/nutrition
```

Add audit invariants:

```text
hard_allergen_violations == 0
hard_exclusion_violations == 0
```

Commit:

```bash
git commit -m "feat(nutrition): add structured constraints and safe meal substitution"
```

Do not start Phase 4 until green.

---

# PHASE 4 — Dual optimization: Budget Plan + Ideal Reference Plan

## PHASE 4 — GOAL

Generate two different **solutions to the same scientific target**:

```text
Budget Plan
= best safe plan under the user's budget

Ideal Reference Plan
= best safe nutrition-first plan without the user's budget cap
```

The ideal plan is a comparison reference. It is never automatically the user's active tracked diet.

## Core invariant

There is only **one scientific target** for the estimate.

Example:

```text
Goal:
2200 kcal/day
protein hard minimum: 135 g/day
protein preferred: 165 g/day
```

Possible Budget Plan:

```text
148 g protein/day
```

Possible Ideal Plan:

```text
164 g protein/day
```

Report:

```text
Budget Plan is ~17 g/day below the preferred protein target.
```

Do not lower the preferred scientific target to 148 just because the budget is lower.

## Files to create

### `backend/app/nutrition/plan_comparison.py`

Initial domain object:

```python
@dataclass(frozen=True)
class PlanComparisonReport:
    user_monthly_budget_irr: int
    budget_plan_monthly_cost_irr: int | None
    ideal_plan_monthly_cost_irr: int | None
    minimum_feasible_monthly_cost_irr: int | None
    monthly_cost_gap_irr: int | None

    calorie_gap_kcal_per_day: Decimal | None
    protein_gap_g_per_day: Decimal | None
    carbohydrate_gap_g_per_day: Decimal | None
    fat_gap_g_per_day: Decimal | None
    fibre_gap_g_per_day: Decimal | None

    micronutrient_gaps_improved: tuple[str, ...]
    unique_meal_count_budget: int | None
    unique_meal_count_ideal: int | None
    unique_protein_sources_budget: int | None
    unique_protein_sources_ideal: int | None

    meaningful_quality_improvement: bool
    show_ideal_plan: bool
    reason_codes: tuple[str, ...]
```

Phase 4 creates the comparison facts. Phase 5 finalizes presentation thresholds.

### `backend/tests/nutrition/test_plan_comparison.py`

Start with:
- cost calculations;
- macro gaps;
- unique meal/source counts;
- null-safe budget-insufficient states.

## Files to modify

### `backend/app/nutrition/enums.py`

Add:

```python
class NutritionOptimizationMode(StrEnum):
    BUDGET_CONSTRAINED = "budget_constrained"
    IDEAL_REFERENCE = "ideal_reference"

class NutritionPlanRole(StrEnum):
    BUDGET = "budget"
    IDEAL_REFERENCE = "ideal_reference"
```

### `backend/app/nutrition/planner_engine.py`

Change `PlannerInput`:

```python
optimization_mode: NutritionOptimizationMode
weekly_budget_irr: int | None
budget_mode: str | None
```

Validation:

```text
BUDGET_CONSTRAINED:
  weekly_budget_irr required
  budget_mode required

IDEAL_REFERENCE:
  weekly_budget_irr optional/null
  budget_mode optional/null
```

In `_evaluate_built_days()`:

```text
BUDGET_CONSTRAINED
-> portion repair
-> budget optimizer
-> post-budget portion repair
-> validation

IDEAL_REFERENCE
-> portion repair
-> no user-budget repair
-> calculate actual weekly cost
-> validation
```

Do not simulate ideal mode with:

```text
weekly_budget = 999999999999
```

That hides intent and leaks budget scoring into ideal mode.

### Hard feasibility vs preferred quality

Refactor validation so these are explicit.

Hard:

```text
goal-specific macro minimums
nutrient upper limits
medical safety
food/allergen constraints
structural feasibility
```

Preferred quality:

```text
closeness to preferred calories
closeness to preferred protein
goal-specific carb/fat preference
micronutrient preferred values
variety
sports-nutrition distribution
preference/adherence
```

Budget Plan can be a valid success below **preferred** protein if it remains above the hard goal-specific minimum.

Add warnings:

```text
BUDGET_PLAN_BELOW_PREFERRED_PROTEIN
BUDGET_PLAN_BELOW_PREFERRED_CALORIES
BUDGET_PLAN_REDUCED_VARIETY
```

A hard-minimum violation remains infeasible, not a warning.

### `backend/app/nutrition/budget_optimizer.py`

Only execute in `BUDGET_CONSTRAINED`.

Preserve/return:

```text
minimum_feasible_weekly_cost_irr
search_exhaustive
```

where established.

Do not produce a precise “minimum budget” from a truncated search.

### `backend/app/nutrition/candidate_selection.py`

Make ranking mode-aware.

#### Budget mode ordering

```text
1. hard-safe success
2. preferred core-nutrition deviation
3. goal-specific quality
4. micronutrient quality
5. adherence/preferences
6. budget fit
7. repetition
8. repair/substitution burden
9. stable tie-break
```

Budget is a constraint first; among valid under-budget plans, do not automatically prefer a more expensive plan.

#### Ideal mode ordering

```text
1. hard-safe success
2. preferred calories/macros
3. goal-specific quality
4. micronutrients
5. sports/training nutrition
6. variety
7. adherence/preferences
8. repetition
9. repair/substitution burden
10. lower cost only as a late tie-break
```

Ideal mode must never contain “higher cost = better”.

### `backend/app/nutrition/program_selection.py`

Generate two ranked views from the same normalized request and catalogue features:

```text
rank_for_budget()
rank_for_ideal()
```

Budget:
- strong budget-fit component.

Ideal:
- budget score weight = zero;
- goal/training/nutrition capacity dominate.

Use first batch size 5 per mode.

If no success in a mode:
- try next batch;
- continue bounded fallback until one success or candidates exhausted.

This prevents the dual-plan feature from doubling current all-25 eager work.

### `backend/app/nutrition/plan_service.py`

Top-level orchestration becomes:

```text
1 load profile/safety/estimate once
2 build normalized request once
3 build food/price/template snapshots once
4 resolve scientific target once
5 compute reusable program features/cost preflight once

6 select + build Budget candidates
7 choose best Budget Plan

8 select + build Ideal candidates
9 choose best Ideal Reference Plan

10 compare plans
11 persist bundle + child generations
12 return compatibility response
```

Share immutable/cost caches when safe.

Do not share mutable mode-specific repair state.

## Persistence: exact design

Preserve:

```text
one NutritionPlanGeneration -> one NutritionWeeklyPlan
```

Add a parent bundle and explicit role.

### `backend/app/nutrition/models.py`

Create:

```text
NutritionPlanBundle
```

Fields:

```text
id UUID PK
user_id FK user_profiles
estimate_id FK nutrition_estimates
comparison_snapshot JSON nullable
created_at
```

Add to `NutritionPlanGeneration`:

```text
bundle_id UUID nullable FK nutrition_plan_bundles
plan_role: budget | ideal_reference | legacy
```

Legacy generations created before this migration may keep:

```text
bundle_id = NULL
plan_role = legacy
```

New dual-plan generation:
- one bundle;
- budget child generation;
- optional ideal child generation.

Why this schema:
- preserves one-generation/one-weekly-plan invariant;
- avoids circular foreign keys from bundle to two generation columns;
- future plan roles can be added without redesigning the bundle.

### Alembic migration

Create:
1. `nutrition_plan_bundles`;
2. `bundle_id` on generation;
3. `plan_role` on generation;
4. indexes/constraints for at most one budget and one ideal role per bundle if PostgreSQL/index conventions allow cleanly.

Do not rewrite old migration history.

### Active plan rule

Only the Budget Plan can be the automatically active/tracked user plan.

The Ideal Reference Plan is reference-only.

Inspect and modify all functions that select “active/latest weekly plan”, especially in:

```text
backend/app/nutrition/plan_service.py
backend/app/nutrition/tracking_service.py
backend/app/nutrition/adherence_service.py
backend/app/nutrition/plan_editing.py
```

Add explicit tests proving `ideal_reference` is never returned as the active diet merely because it is newer.

### `backend/app/nutrition/schemas.py`

Evolve response compatibly:

```python
class WeeklyPlanGenerationResponse(BaseModel):
    generation_id: UUID
    outcome: str
    reason_codes: list[str]
    warning_codes: list[str]

    # compatibility:
    plan: WeeklyPlanResponse | None

    budget_plan: WeeklyPlanResponse | None
    ideal_plan: WeeklyPlanResponse | None
    comparison: PlanComparisonResponse | None
```

During migration:

```text
plan == budget_plan
```

when budget plan exists.

### `backend/app/nutrition/router.py`

Keep the existing weekly generation endpoint unless current routing forces a change. Evolve the response; do not create duplicate endpoints without need.

## Budget-insufficient state

If no hard-safe plan fits the user's budget:

```text
budget_plan = null
```

If a true lower bound/minimum was established:

```text
minimum_feasible_monthly_cost_irr = known value
```

If search was truncated/uncertain:

```text
minimum_feasible_monthly_cost_irr = null
```

Reason:

```text
USER_BUDGET_BELOW_MINIMUM_FEASIBLE
```

only when minimum infeasibility is actually established.

Otherwise use a non-claiming reason such as:

```text
NO_BUDGET_FEASIBLE_PLAN_FOUND
```

Ideal Plan may still be generated if safe.

## PHASE 4 GATE

Tests must prove:

```text
budget and ideal use identical scientific target snapshot
strict budget plan does not exceed strict cap
ideal ignores user budget cap
ideal respects allergies/safety
ideal does not win because it costs more
preferred protein miss can be a budget warning above hard minimum
hard minimum violation fails
budget-insufficient exact minimum appears only when established
ideal is never active/tracked
top-5 batching uses fallback when needed
determinism remains intact
```

Commands:

```bash
cd backend

uv run pytest \
  tests/nutrition/test_plan_comparison.py \
  tests/nutrition/test_candidate_selection.py \
  tests/nutrition/test_budget_optimizer.py \
  tests/nutrition/test_planner_engine.py \
  tests/nutrition/test_weekly_plan_api.py \
  tests/nutrition/test_plan_editing_api.py -q

uv run pytest tests/nutrition -q
uv run ruff check app/nutrition tests/nutrition
```

Commit:

```bash
git commit -m "feat(nutrition): generate budget and ideal reference plans"
```

Do not start Phase 5 until green.

---

# PHASE 5 — Comparison report, one-plan/two-plan UX, final audit

## PHASE 5 — GOAL

Turn the two-plan engine into a useful user explanation.

The user should understand:

```text
What can Fitsho do with my budget?
What would my nutrition-first reference plan cost?
What exactly improves if I spend more?
Is the difference meaningful enough to show me a second plan?
```

The UI must not shame users for having a lower budget.

## One-plan vs two-plan product rule

Product price threshold:

```text
1,000,000 Toman/month
= 10,000,000 IRR/month
```

Final rule:

```python
show_ideal_plan = (
    monthly_cost_gap_irr is not None
    and monthly_cost_gap_irr >= 10_000_000
    and meaningful_quality_improvement
)
```

Therefore:

```text
gap < 1M Toman
-> show only Budget Plan

gap >= 1M but no meaningful nutrition/goal improvement
-> show only Budget Plan

gap >= 1M and meaningful improvement
-> show Budget Plan + Ideal Reference Plan
```

This is deliberately better than a price-only rule. A more expensive duplicate plan is noise.

## Define meaningful quality improvement exactly

In `plan_comparison.py`, set `meaningful_quality_improvement=True` if **at least one** of these deterministic conditions is met:

```text
A. preferred protein gap improves by >= 10 g/day

OR

B. maximum normalized core target deviation improves by >= 0.05
   (= five percentage points)

OR

C. at least 2 micronutrient preferred gaps that are present
   in Budget Plan are resolved in Ideal Plan

OR

D. unique meal templates improve by >= 3

OR

E. unique protein-source foods improve by >= 2

OR

F. goal-specific normalized quality penalty improves by >= 0.05
```

For `F`, make the goal-specific quality penalty a normalized `Decimal` in `[0,1]` in Phase 2/4. Do not compare arbitrary raw score units.

Add:

```python
PLAN_COMPARISON_POLICY_VERSION = "nutrition-plan-comparison-v1"
MIN_IDEAL_DISPLAY_COST_GAP_IRR = 10_000_000
MIN_PROTEIN_IMPROVEMENT_G = Decimal("10")
MIN_CORE_DEVIATION_IMPROVEMENT = Decimal("0.05")
MIN_UNIQUE_MEAL_IMPROVEMENT = 3
MIN_PROTEIN_SOURCE_IMPROVEMENT = 2
MIN_GOAL_QUALITY_IMPROVEMENT = Decimal("0.05")
```

## Files to modify

### `backend/app/nutrition/plan_comparison.py`

Finish:

```text
meaningful quality rules
show_ideal_plan
reason codes
structured differences
```

Reason codes:

```text
IDEAL_PLAN_HIDDEN_COST_GAP_SMALL
IDEAL_PLAN_HIDDEN_NO_MEANINGFUL_GAIN
IDEAL_PLAN_SHOWN_MEANINGFUL_GAIN

USER_BUDGET_BELOW_MINIMUM_FEASIBLE
NO_BUDGET_FEASIBLE_PLAN_FOUND

BUDGET_PLAN_PROTEIN_PREFERRED_GAP
BUDGET_PLAN_CALORIE_PREFERRED_GAP
BUDGET_PLAN_VARIETY_GAP
BUDGET_PLAN_MICRONUTRIENT_GAP
```

Never infer a gap that is unsupported by source nutrient data.

### `backend/app/nutrition/schemas.py`

Add explicit API models.

Recommended:

```python
class PlanComparisonMetricResponse(BaseModel):
    budget_value: float | int | None
    ideal_value: float | int | None
    difference: float | int | None
    unit: str

class PlanComparisonResponse(BaseModel):
    user_monthly_budget_irr: int
    budget_plan_monthly_cost_irr: int | None
    ideal_plan_monthly_cost_irr: int | None
    minimum_feasible_monthly_cost_irr: int | None
    monthly_cost_gap_irr: int | None

    calorie_gap: PlanComparisonMetricResponse | None
    protein_gap: PlanComparisonMetricResponse | None
    carbohydrate_gap: PlanComparisonMetricResponse | None
    fat_gap: PlanComparisonMetricResponse | None
    fibre_gap: PlanComparisonMetricResponse | None

    unique_meal_count_budget: int | None
    unique_meal_count_ideal: int | None
    unique_protein_sources_budget: int | None
    unique_protein_sources_ideal: int | None

    meaningful_quality_improvement: bool
    show_ideal_plan: bool
    reason_codes: list[str]
    policy_version: str
```

Backend returns facts, not AI-written prose.

### `backend/app/nutrition/plan_service.py`

Persist `comparison_snapshot` on the bundle.

Why:
- prices change later;
- user should see the comparison that was true at generation time;
- audits must be reproducible.

### `backend/app/nutrition/router.py`

Return the structured comparison through the existing generation/read paths.

If a “get current nutrition plan” endpoint exists, keep returning Budget/active plan as primary and include reference/comparison only where the product needs it.

### `frontend/src/features/nutrition/types.ts`

Add:

```text
budget_plan
ideal_plan
comparison
```

Preserve old `plan` during compatibility.

### `frontend/src/features/nutrition/api.ts`

Parse/return the extended response.

Do not calculate business-critical comparison metrics independently in the browser. Backend is the source of truth.

### `frontend/src/features/nutrition/NutritionEstimatePage.tsx`

Add the result layout:

```text
[Budget summary]

[Plan comparison summary]

[برنامه پیشنهادی با بودجه شما]
  weekly accordion

[برنامه مرجع]   <-- only if show_ideal_plan
  weekly accordion

[Why they differ]
```

User-facing labels:

```text
برنامه پیشنهادی با بودجه شما
برنامه مرجع
بودجه ماهانه شما
هزینه تقریبی برنامه
اختلاف با هدف ترجیحی
پروتئین روزانه
تنوع وعده‌ها
تنوع منابع پروتئینی
```

Clearly label:

```text
برنامه مرجع برای مقایسه است و برنامه فعال شما نیست.
```

### Suggested deterministic Persian copy

Frontend can choose copy templates from reason codes and structured values.

#### Two-plan example

```text
بودجه ماهانه شما ۸ میلیون تومان است.
برنامه پیشنهادی با بودجه شما حدود ۷.۹ میلیون تومان هزینه دارد.

برنامه مرجع متناسب با هدف شما حدود ۱۲.۱ میلیون تومان هزینه دارد.
نسخه بودجه‌ای حداقل‌های تعیین‌شده را رعایت می‌کند، اما نسبت به هدف
ترجیحی حدود ۱۸ گرم پروتئین در روز کمتر دارد و تنوع منابع پروتئینی
پایین‌تر است.
```

Only say “حداقل‌ها را رعایت می‌کند” if backend hard-minimum validation confirms it.

#### Gap below 1M

```text
بودجه شما به هزینه برنامه مرجع بسیار نزدیک است؛ بنابراین همان برنامه
پیشنهادی با بودجه شما نمایش داده می‌شود.
```

#### Budget below hard-safe minimum

If exact minimum was established:

```text
با بودجه فعلی، ساخت برنامه‌ای که حداقل‌های تعیین‌شده برای هدف شما را
رعایت کند ممکن نشد.

بودجه شما: ۶ میلیون تومان
حداقل هزینه تخمینی برنامه قابل‌اجرا: حدود ۸.۴ میلیون تومان
```

If minimum is unknown:

```text
با قیمت‌ها و کاتالوگ فعلی، برنامه سازگار در این بودجه پیدا نشد.
```

Never invent a minimum from a truncated search.

### `frontend/src/features/nutrition/NutritionEstimatePage.test.tsx`

Add:

```text
gap < 1M -> one plan
gap >= 1M + meaningful -> two plans
gap >= 1M + not meaningful -> one plan
protein gap renders correctly
budget-insufficient + known minimum
budget-insufficient + unknown minimum
ideal plan says reference-only
legacy `plan` remains compatible
```

### i18n

Update the current repository FA/EN translation files for all new labels/reasons.

Do not hardcode every visible sentence inside the component if the project uses i18n.

### Audit scripts

Modify:

```text
backend/scripts/run_nutrition_100_profiles_audit.py
backend/scripts/audit_nutrition_engine_100_profiles.py
```

Add output fields:

```text
budget_tier
requested_weight_change_kg_per_week
recommended_weight_change_kg_per_week
applied_weight_change_kg_per_week
goal_strategy
goal_strategy_version

programs_considered
programs_hard_rejected
programs_constructed
fallback_batches_used

budget_plan_success
budget_plan_monthly_cost_irr
ideal_plan_success
ideal_plan_monthly_cost_irr
monthly_cost_gap_irr

protein_preferred_gap_g_per_day
calorie_preferred_gap_kcal_per_day
unique_meal_gap
unique_protein_source_gap

show_ideal_plan
comparison_reason_codes

hard_allergen_violations
hard_exclusion_violations
medical_safety_violations
```

The supported production cohort remains the product-supported omnivore/mixed scope unless requirements are explicitly changed later.

Never count legitimate medical manual-plan/hard-block outcomes as fake successful automatic plans.

## PHASE 5 GATE

Backend:

```bash
cd backend

uv run pytest tests/nutrition -q
uv run ruff check app/nutrition scripts tests/nutrition
```

Frontend:

```bash
cd frontend

npm test
npm run lint
npm run build
```

Final deterministic audit:

```bash
cd backend

uv run python scripts/audit_nutrition_engine_100_profiles.py \
  --count 100 \
  --seed 20260903 \
  --output-json ../artifacts/nutrition_engine_phase5_final.json \
  --output-pdf ../artifacts/nutrition_engine_phase5_final.pdf
```

Commit:

```bash
git commit -m "feat(nutrition): explain budget versus ideal plan tradeoffs"
```

---

# 6. Full acceptance criteria

The roadmap is complete only when all boxes are true.

## Architecture

```text
[ ] NormalizedNutritionRequest exists
[ ] explicit ProgramEligibility exists
[ ] explicit ProgramScore exists
[ ] ProgramSelectionResult + decision_trace exist
[ ] expensive construction is batched
[ ] fallback batch prevents top-5 false negatives
[ ] policy versions are stored in snapshots
```

## Budget selection

```text
[ ] <=13M Toman -> ECONOMY user tier
[ ] >13M and <=18M -> NORMAL
[ ] >18M -> VARIED
[ ] runtime effective cost can override static program tier hint
[ ] low-budget users normally rank realistic candidates first
[ ] uncertain preflight is not called proven infeasibility
[ ] Budget Optimizer remains the precise downstream repair/search layer
```

## Five goal algorithms

```text
[ ] LOSE_WEIGHT has its own strategy
[ ] FAT_LOSS has its own strategy
[ ] GAIN_WEIGHT has its own strategy
[ ] BUILD_MUSCLE has its own strategy
[ ] BODY_RECOMPOSITION has its own strategy

[ ] rate-dependent goals support 0.3–2.0 kg/week input
[ ] UI marks >1.0 kg/week red / "پیشنهاد نمی‌شود"
[ ] requested/recommended/applied values are separate
[ ] unsafe/aggressive request can be clamped
[ ] body recomposition does not use the 0.3–2.0 selector

[ ] fat loss genuinely prioritizes higher protein / lean-mass preservation
[ ] fat loss is not hardcoded low-carb
[ ] fat is not pushed near zero
[ ] muscle gain uses conservative experience-aware surplus
[ ] muscle gain gets adequate carbs after protein/fat
[ ] gain weight is not treated as unlimited-fat bodybuilding
[ ] recomp defaults to maintenance/mild deficit + high protein
[ ] every macro target is energy-consistent
```

## Safety / restrictions

```text
[ ] structured allergen metadata exists
[ ] hard and soft constraints are separate
[ ] allergy is hard
[ ] dislike is soft
[ ] never_suggest/refused is hard
[ ] unknown hard allergy is not silently ignored
[ ] ordinary lavash is not a gluten-safe substitute for sangak
[ ] budget repair cannot reintroduce excluded foods
[ ] one incompatible meal attempts substitution first
[ ] whole program rejects only when hard constraint is unresolvable
[ ] medical safety behavior remains intact
```

## Dual plans

```text
[ ] Budget and Ideal use the same scientific target
[ ] Budget plan respects its budget rules
[ ] Ideal plan has no user-budget constraint
[ ] Ideal plan still respects all safety/hard constraints
[ ] Ideal means nutrition quality, not expense
[ ] preferred-target shortfall can be reported honestly
[ ] hard-minimum shortfall cannot be called success
[ ] one bundle owns child generations
[ ] one generation still owns one weekly plan
[ ] ideal plan is never automatically active/tracked
```

## User comparison

```text
[ ] cost gap <1M Toman -> one plan
[ ] gap >=1M + no meaningful gain -> one plan
[ ] gap >=1M + meaningful gain -> two plans
[ ] protein/calorie/variety differences come from structured facts
[ ] exact minimum feasible budget shown only when established
[ ] no budget-shaming language
```

## Quality / audit

```text
[ ] backend nutrition tests pass
[ ] backend lint passes
[ ] frontend tests pass
[ ] frontend lint passes
[ ] frontend build passes
[ ] hard allergen violations = 0
[ ] hard exclusion violations = 0
[ ] medical safety violations = 0
[ ] same input snapshot remains deterministic
```

For automatically eligible supported product profiles:

```text
target safe plan-generation success >= 90%
```

Do not manipulate the denominator by converting legitimate medical safety blocks into successes.

---

# 7. Final file ownership after Phase 5

Do not physically move files during this roadmap; these are logical responsibilities.

```text
scientific.py
  BMR/TDEE/base science/generic safety limits

nutrition_targets.py
  shared TargetBand/NutrientTargets

weight_rate_policy.py
  requested weekly rate -> safe applied rate

goal_strategy.py
  five goal algorithms

nutrition_request.py
  normalized engine request

program_costing.py
  preconstruction user-specific program cost

program_eligibility.py
  hard program rejection only

program_scoring.py
  preconstruction ranking

program_selection.py
  ranking + batch/fallback orchestration

program_adaptation.py
  program structure -> user meal counts

food_constraints.py
  single hard/soft food-constraint evaluator

template_substitution.py
  safe meal-level replacement

planner_engine.py
  concrete weekly construction and validation

portion_solver.py
  bounded portion feasibility/repair

budget_optimizer.py
  budget-constrained optimization only

candidate_selection.py
  fully-built candidate comparison by mode

plan_comparison.py
  Budget vs Ideal structured gap

plan_service.py
  top-level orchestration/persistence
```

If `plan_service.py` grows during implementation, do not mix a broad directory/file reorganization into these phases. Finish behavior first; restructure later in a separate verified refactor.

---

# 8. Phase-by-phase execution protocol for Gemini 3.8 Flash

At the start of **every phase**, output:

```text
PHASE N — GOAL
WHY THIS DESIGN
FILES TO TOUCH
TESTS THAT PROVE IT
```

Before every non-obvious implementation decision, state briefly:

```text
Decision:
Why:
Alternative rejected:
How it is tested:
```

Then execute only the current phase.

Required work rhythm:

```text
1. read current files for this phase
2. write failing test
3. run failing test
4. implement minimal correct behavior
5. run focused tests
6. complete remaining task in same phase
7. run full phase gate
8. inspect git diff for accidental unrelated changes
9. commit phase
10. only then proceed to next phase
```

Do not:

```text
jump ahead to a later phase
change unrelated UI/code
move nutrition files into new folders
relax safety to increase success rate
change scientific thresholds merely to make tests green
create fake huge budget for Ideal mode
hardcode "expensive food = good"
hardcode "fat loss = low carb"
hardcode "weight gain = high fat"
silently ignore unknown allergies
treat search exhaustion as proven infeasibility
stop after scaffolding interfaces
```

If a current repository function/file has changed since this roadmap:
- read the current version;
- adapt exact line placement;
- preserve this roadmap's interface/behavior;
- do not revert newer unrelated work.

---

# 9. End-to-end scenarios Gemini must verify

## Scenario 1 — 9M Toman, fat loss, resistance training

```text
goal: FAT_LOSS
weight: 90 kg
requested rate: 0.5 kg/week
budget: 9M Toman
resistance training: yes
```

Expected:

```text
moderate safe deficit
high protein strategy
economy/high-protein-compatible programs rank high
clearly premium programs rank low
safe substitutions preserve candidate where possible
Budget Plan respects budget/hard minimums
Ideal Plan can cost more
comparison explains real protein/variety difference
```

## Scenario 2 — 2 kg/week requested weight loss

Expected:

```text
request persists as 2.0
UI value is red + "پیشنهاد نمی‌شود"
backend derives theoretical request
safe policy clamps applied rate/deficit
warning is returned
user can see requested vs applied
```

## Scenario 3 — muscle gain, 4 resistance sessions

Expected:

```text
experience-aware conservative surplus
protein ~1.6–2.2 g/kg policy
adequate carbohydrate support
moderate fat
scalable protein/carb meals rank well
large surplus is not selected merely because user requested fast gain
```

## Scenario 4 — recomposition

Expected:

```text
no weekly 0.3–2.0 selector
maintenance or mild deficit using reliable context
high protein
resistance training strongly supported
training mismatch warning if absent
```

## Scenario 5 — gluten allergy

Program contains sangak:

```text
sangak -> unsafe
ordinary lavash -> unsafe
safe category-compatible meal is sought
whole program survives when a truly safe substitute exists
```

## Scenario 6 — plans within 1M

```text
Budget: 11.8M
Ideal: 12.4M
gap: 0.6M
```

Expected:

```text
one plan shown
```

## Scenario 7 — large price gap but negligible quality gain

```text
Budget: 12M
Ideal: 16M
protein improvement: 1 g
core targets: nearly identical
variety: same
micronutrients: same
```

Expected:

```text
one plan shown
```

## Scenario 8 — budget cannot meet hard minimums

Expected:

```text
do not lower hard minimum and fake success
budget plan may be null
known minimum feasible cost shown only if established
ideal reference may still exist
```

---

# 10. Source-to-rule references Gemini should preserve in policy documentation

Use concise comments/docstrings. Do not paste long abstracts into code.

```text
General gradual weight loss:
CDC
https://www.cdc.gov/healthy-weight-growth/losing-weight/index.html

500–750 kcal/day clinical deficit guidance:
2026 AHA/ACC/ADA/ASN CKM guideline
https://pmc.ncbi.nlm.nih.gov/articles/PMC13399222/

Protein and exercise:
ISSN Position Stand
https://pubmed.ncbi.nlm.nih.gov/28642676/

Resistance-trained fat loss:
https://pubmed.ncbi.nlm.nih.gov/34579132/

Protein during caloric restriction in lean resistance-trained athletes:
https://pubmed.ncbi.nlm.nih.gov/24092765/

Off-season bodybuilding:
https://pmc.ncbi.nlm.nih.gov/articles/PMC6680710/

5% vs 15% energy surplus study:
https://pmc.ncbi.nlm.nih.gov/articles/PMC10620361/

Healthy/athletic weight gain:
https://pubmed.ncbi.nlm.nih.gov/35233712/

Resistance-training carbohydrate systematic review:
https://pmc.ncbi.nlm.nih.gov/articles/PMC8878406/

2026 carbohydrate/hypertrophy meta-analysis:
https://pubmed.ncbi.nlm.nih.gov/41712097/

Energy deficit / lean mass meta-analysis:
https://pubmed.ncbi.nlm.nih.gov/34623696/

2026 body recomposition RCT:
https://pubmed.ncbi.nlm.nih.gov/41940947/

Dietary fat 20–35%:
https://pubmed.ncbi.nlm.nih.gov/24342605/

2023 IOC REDs consensus:
https://pubmed.ncbi.nlm.nih.gov/37752011/
```

Where evidence is uncertain, encode a conservative preferred range and explicit policy version rather than fake precision.

---

# 11. Final instruction to Gemini 3.8 Flash

Read this entire roadmap once before editing.

Then:

1. Start at Phase 0.
2. Re-read the current repository files named in Phase 0.
3. State the Phase 0 goal and why the design exists.
4. Implement and test **only Phase 0**.
5. Pass Phase 0 gate and commit it.
6. Move to Phase 1.
7. Repeat the same discipline through Phase 5.
8. At each phase, keep all attention on that phase; do not pre-implement future phases.
9. Preserve unrelated current local/remote work.
10. Keep safety/hard constraints above success-rate optimization.
11. Use deterministic logic and explicit reason codes.
12. Run the final 100-profile audit after Phase 5.
13. Continue until every phase and final gate is complete.
14. **Only if a genuine ambiguity prevents a correct implementation, ask the user a question. Otherwise continue to the end.**
