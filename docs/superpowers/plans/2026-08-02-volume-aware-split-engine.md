# Volume-aware Split Engine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the deterministic Fitsho coach select and repair individualized resistance-training splits and volume without rejecting valid four-, six-, or seven-available-day profiles.

**Architecture:** Keep the existing program engine pipeline. Extend its ruleset and typed domain models with soft/hard volume boundaries, evaluate split templates across all feasible session counts, and allocate integer set budgets before final validation. Templates are candidates rather than universal prescriptions; selection remains deterministic and explains its reasons.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy, Pydantic, pytest, Ruff, mypy.

## Global Constraints

- Preserve the existing FastAPI and workout-plan persistence contracts.
- Keep safety, equipment, and hard volume constraints deterministic.
- `available_training_days` is a maximum, not an exact session count.
- Do not add image analysis, a new external dependency, or a migration in this iteration.
- Raw image-model opinions must never affect a plan; a future approved assessment maps into the existing `priority_muscles` input.
- Do not stage unrelated untracked files.

---

### Task 1: Model unknown training history and volume ranges

**Files:**
- Modify: `backend/app/workouts/program_engine/schemas.py`
- Modify: `backend/app/workouts/program_engine/normalization.py`
- Modify: `backend/app/workouts/program_engine/rulesets/resistance_training_v1.py`
- Modify: `backend/app/workouts/program_engine/volume_planner.py`
- Test: `backend/tests/workouts/program_engine/test_split_volume.py`

**Interfaces:**
- Produces `VolumeTarget(minimum_soft, target_sets, maximum_soft, maximum_hard, fractional_sets)`.
- `VolumeTarget.direct_sets` remains a read-only compatibility property returning `target_sets`.
- `RecentTrainingHistory.consistent_weeks` accepts `None` for unknown history.

- [ ] **Step 1: Write failing range and unknown-history tests**

```python
def test_unknown_history_does_not_reduce_declared_advanced_status() -> None:
    request = normalized(
        training_experience=TrainingExperience.ADVANCED,
        training_age_months=72,
        recent_training_history=RecentTrainingHistory(),
    )
    assert request.training_status is TrainingStatus.ADVANCED


def test_volume_target_exposes_soft_and_hard_boundaries() -> None:
    request = normalized(primary_goal=Goal.HYPERTROPHY)
    target = plan_weekly_volume(request, select_split(request, RULESET), RULESET).targets[0]
    assert target.minimum_soft <= target.target_sets <= target.maximum_soft <= target.maximum_hard
```

- [ ] **Step 2: Run the focused test and verify RED**

Run: `TEST_DATABASE_URL='postgresql+psycopg://fitsho:fitsho@localhost:55433/fitsho_test' uv run pytest tests/workouts/program_engine/test_split_volume.py -q`

Expected: failure because unknown history is currently treated as zero and the new range fields do not exist.

- [ ] **Step 3: Implement the typed range policy**

```python
@dataclass(frozen=True)
class VolumeTarget:
    muscle: MuscleGroup
    minimum_soft: int
    target_sets: int
    maximum_soft: int
    maximum_hard: int
    fractional_sets: float

    @property
    def direct_sets(self) -> int:
        return self.target_sets
```

Use the existing ruleset minima and maxima as the soft floor and hard ceiling. Add a ruleset mapping for soft-maximum allowance by training status and reduce it to one when recovery is poor. Derive `maximum_soft` as `min(maximum_hard, target_sets + allowance)`.

Make `consistent_weeks: int | None = None` and only apply the recent-consistency downgrade when it is not `None` and below the configured threshold.

- [ ] **Step 4: Run focused tests and verify GREEN**

Run: `TEST_DATABASE_URL='postgresql+psycopg://fitsho:fitsho@localhost:55433/fitsho_test' uv run pytest tests/workouts/program_engine/test_split_volume.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/workouts/program_engine/{schemas.py,normalization.py,volume_planner.py,rulesets/resistance_training_v1.py} backend/tests/workouts/program_engine/test_split_volume.py
git commit -m "feat(workouts): add soft and hard volume ranges"
```

### Task 2: Select split candidates below the available-day ceiling

**Files:**
- Modify: `backend/app/workouts/program_engine/enums.py`
- Modify: `backend/app/workouts/program_engine/split_selector.py`
- Modify: `backend/app/workouts/program_engine/rulesets/resistance_training_v1.py`
- Test: `backend/tests/workouts/program_engine/test_split_volume.py`

**Interfaces:**
- `generate_split_candidates(days: int) -> tuple[SplitCandidate, ...]` continues to return candidates for one exact number of sessions.
- `select_split(request, ruleset)` scores candidates for every session count from one through `min(available_training_days, max_resistance_days)`.
- New split types: `PHUL` and `BODY_PART_ROTATION`.

- [ ] **Step 1: Write failing selection tests**

```python
def test_advanced_user_with_seven_available_days_selects_six_safe_sessions() -> None:
    split = select_split(
        normalized(
            available_training_days=7,
            training_experience=TrainingExperience.ADVANCED,
            training_age_months=72,
            recent_training_history=RecentTrainingHistory(consistent_weeks=40),
        ),
        RULESET,
    )
    assert len(split.day_focuses) == 6
    assert "RESISTANCE_DAYS_CAPPED_AT_RULESET_MAXIMUM" in split.reason_codes


def test_poor_recovery_user_can_receive_fewer_sessions_than_available() -> None:
    split = select_split(normalized(available_training_days=6, sleep_quality=RecoveryRating.POOR), RULESET)
    assert len(split.day_focuses) < 6


def test_advanced_hypertrophy_user_can_select_body_part_rotation() -> None:
    split = select_split(
        normalized(
            available_training_days=4,
            session_duration_minutes=75,
            primary_goal=Goal.HYPERTROPHY,
            training_experience=TrainingExperience.ADVANCED,
            training_age_months=72,
            recent_training_history=RecentTrainingHistory(consistent_weeks=40),
        ),
        RULESET,
    )
    assert split.split_type is SplitType.BODY_PART_ROTATION
```

- [ ] **Step 2: Run the focused test and verify RED**

Run: `TEST_DATABASE_URL='postgresql+psycopg://fitsho:fitsho@localhost:55433/fitsho_test' uv run pytest tests/workouts/program_engine/test_split_volume.py -q`

Expected: the body-part enum/template is missing and selection only evaluates the maximum day count.

- [ ] **Step 3: Implement deterministic multi-count split scoring**

Add `recommended_resistance_days` to the ruleset keyed by training status. Penalize the absolute distance from the recommended count, increase the desired count for short sessions when it helps distribute volume, and reduce it for poor recovery. Retain existing safety spacing and deterministic sort tie-breakers.

Add templates:

```python
SplitType.PHUL: (
    "upper_strength", "lower_strength", "upper_hypertrophy", "lower_hypertrophy",
)
SplitType.BODY_PART_ROTATION: (
    "chest_triceps", "back_biceps", "shoulders_traps", "legs",
)
```

Give body-part rotation a score bonus only for advanced hypertrophy users with at least 60-minute sessions, and retain more general templates as viable candidates. Include a `SPLIT_SELECTED_FOR_APPROPRIATE_SESSION_COUNT` reason when the selected count is below the user cap.

- [ ] **Step 4: Run focused tests and verify GREEN**

Run: `TEST_DATABASE_URL='postgresql+psycopg://fitsho:fitsho@localhost:55433/fitsho_test' uv run pytest tests/workouts/program_engine/test_split_volume.py -q`

Expected: PASS with deterministic selected templates and safe session counts.

- [ ] **Step 5: Commit**

```bash
git add backend/app/workouts/program_engine/{enums.py,split_selector.py,rulesets/resistance_training_v1.py} backend/tests/workouts/program_engine/test_split_volume.py
git commit -m "feat(workouts): score flexible coaching split templates"
```

### Task 3: Compose muscle-group slots from the selected template

**Files:**
- Modify: `backend/app/workouts/program_engine/session_builder.py`
- Test: `backend/tests/workouts/program_engine/test_selection_sessions.py`

**Interfaces:**
- `_slots_for_focus(focus: str)` supports `upper_*`, `lower_*`, `chest_triceps`, `back_biceps`, and `shoulders_traps`.
- Each slot keeps an approved movement-pattern set and an optional target muscle; it never bypasses eligibility filtering.

Add this test helper beside the existing `candidate()` helper:

```python
def body_part_catalog() -> tuple[ExerciseCandidate, ...]:
    return (
        candidate("chest press", MovementPattern.HORIZONTAL_PUSH, MuscleGroup.CHEST),
        candidate("triceps extension", MovementPattern.ELBOW_EXTENSION, MuscleGroup.TRICEPS),
        candidate("row", MovementPattern.HORIZONTAL_PULL, MuscleGroup.BACK),
        candidate("curl", MovementPattern.ELBOW_FLEXION, MuscleGroup.BICEPS),
        candidate("shoulder press", MovementPattern.VERTICAL_PUSH, MuscleGroup.SHOULDERS),
        candidate("lateral raise", MovementPattern.SHOULDER_ABDUCTION, MuscleGroup.SHOULDERS),
        candidate("shrug", MovementPattern.SHRUG, MuscleGroup.TRAPS),
        candidate("squat", MovementPattern.SQUAT, MuscleGroup.QUADRICEPS),
        candidate("hinge", MovementPattern.HIP_HINGE, MuscleGroup.HAMSTRINGS),
        candidate("plank", MovementPattern.CORE_ANTI_EXTENSION, MuscleGroup.ABS),
    )
```

- [ ] **Step 1: Write failing body-part and priority-order tests**

```python
def test_body_part_rotation_places_chest_and_direct_triceps_in_one_session() -> None:
    request = normalized(
        priority_muscles=[MuscleGroup.CHEST],
        training_experience=TrainingExperience.ADVANCED,
        training_age_months=72,
        recent_training_history=RecentTrainingHistory(consistent_weeks=40),
    )
    split = SplitPlan(SplitType.BODY_PART_ROTATION, ("chest_triceps",), (0,), 1, ())
    sessions = build_sessions(request, split, plan_weekly_volume(request, split, RULESET), body_part_catalog(), RULESET)
    muscles = {item.primary_muscle for item in sessions[0].exercises}
    assert {MuscleGroup.CHEST, MuscleGroup.TRICEPS}.issubset(muscles)


def test_priority_muscle_is_first_when_its_focus_is_programmed() -> None:
    request = normalized(priority_muscles=[MuscleGroup.SHOULDERS])
    split = SplitPlan(SplitType.BODY_PART_ROTATION, ("shoulders_traps",), (0,), 1, ())
    sessions = build_sessions(request, split, plan_weekly_volume(request, split, RULESET), body_part_catalog(), RULESET)
    shoulder_day = next(day for day in sessions if day.focus == "shoulders_traps")
    assert shoulder_day.exercises[0].primary_muscle is MuscleGroup.SHOULDERS
```

- [ ] **Step 2: Run focused test and verify RED**

Run: `TEST_DATABASE_URL='postgresql+psycopg://fitsho:fitsho@localhost:55433/fitsho_test' uv run pytest tests/workouts/program_engine/test_selection_sessions.py -q`

Expected: failure because the body-part focus and typed slot do not exist.

- [ ] **Step 3: Implement typed slot composition**

Introduce a private frozen `SlotSpec(patterns, required, target_muscle=None)` in `session_builder.py`. Use target-muscle matching as a ranking preference, not an eligibility override. Define body-part slots so chest/back compounds are required, direct arms are optional when indirect volume exists, shoulders are required, and shrugs are optional because catalog coverage varies.

Treat `upper_strength` and `upper_hypertrophy` as upper focuses and the lower variants as lower focuses. Keep compounds before accessories unless a priority muscle is present, in which case place the priority-targeted safe slot first.

- [ ] **Step 4: Run focused tests and verify GREEN**

Run: `TEST_DATABASE_URL='postgresql+psycopg://fitsho:fitsho@localhost:55433/fitsho_test' uv run pytest tests/workouts/program_engine/test_selection_sessions.py -q`

Expected: PASS; all substitutions remain eligible.

- [ ] **Step 5: Commit**

```bash
git add backend/app/workouts/program_engine/session_builder.py backend/tests/workouts/program_engine/test_selection_sessions.py
git commit -m "feat(workouts): compose priority-aware muscle group sessions"
```

### Task 4: Allocate exact set budgets and repair soft-range overflow

**Files:**
- Create: `backend/app/workouts/program_engine/volume_repair.py`
- Modify: `backend/app/workouts/program_engine/prescription.py`
- Modify: `backend/app/workouts/program_engine/engine.py`
- Modify: `backend/app/workouts/program_engine/validation.py`
- Test: `backend/tests/workouts/program_engine/test_volume_repair.py`
- Test: `backend/tests/workouts/program_engine/test_golden_scenarios.py`

**Interfaces:**
- `allocate_direct_sets(target_sets: int, appearance_count: int, minimum_working_sets: int) -> tuple[int, ...]` returns exact, nonnegative allocations.
- `repair_volume(days, volume, request, ruleset) -> tuple[tuple[WorkoutDay, ...], tuple[str, ...]]` reduces non-priority excess before final validation.

- [ ] **Step 1: Write failing allocation and repair tests**

```python
def test_allocate_direct_sets_distributes_ten_sets_without_ceiling_overflow() -> None:
    assert allocate_direct_sets(10, 3, 2) == (4, 3, 3)


def test_four_day_program_repairs_shoulder_volume_before_validation() -> None:
    source = golden_scenarios()["intermediate_4_days_hypertrophy"]
    result = generate_program(source, full_catalog(), RULESET)
    assert result.program is not None, result.errors
    assert result.program.validation_report.metrics["weekly_direct_sets_by_muscle"]["shoulders"] <= 10


def test_soft_volume_deviation_is_a_warning_not_a_failure() -> None:
    source = golden_scenarios()["intermediate_4_days_hypertrophy"]
    result = generate_program(source, full_catalog(), RULESET)
    assert result.program is not None, result.errors
    assert "WEEKLY_MUSCLE_VOLUME_ABOVE_SOFT_MAXIMUM" not in result.program.validation_report.errors
```

- [ ] **Step 2: Run focused tests and verify RED**

Run: `TEST_DATABASE_URL='postgresql+psycopg://fitsho:fitsho@localhost:55433/fitsho_test' uv run pytest tests/workouts/program_engine/test_volume_repair.py tests/workouts/program_engine/test_golden_scenarios.py -q`

Expected: missing allocation/repair interfaces and current `WEEKLY_MUSCLE_VOLUME_EXCEEDED` failure.

- [ ] **Step 3: Implement exact allocation and deterministic repair**

Use quotient/remainder allocation. When there are too many appearances for the target, assign zero to the least valuable appearances and omit those exercises; never convert a zero allocation into a two-set exercise.

Run repair after prescription and cardio selection. For a hard excess, reduce non-priority accessories with the lowest selection score/reason priority first, then remove redundant slots. Preserve a minimum working set count for remaining exercises, rebuild day estimates, and record repair reasons. The repair must never alter IDs, equipment, safety flags, or a hard constraint.

Update validation to:

- retain a hard error above `maximum_hard`;
- emit warnings for direct targets below `minimum_soft` or above `maximum_soft`;
- report direct, fractional indirect, and effective volume separately.

- [ ] **Step 4: Run focused tests and verify GREEN**

Run: `TEST_DATABASE_URL='postgresql+psycopg://fitsho:fitsho@localhost:55433/fitsho_test' uv run pytest tests/workouts/program_engine/test_volume_repair.py tests/workouts/program_engine/test_golden_scenarios.py -q`

Expected: PASS, including four- and six-day regression cases.

- [ ] **Step 5: Commit**

```bash
git add backend/app/workouts/program_engine/{volume_repair.py,prescription.py,engine.py,validation.py} backend/tests/workouts/program_engine/{test_volume_repair.py,test_golden_scenarios.py}
git commit -m "fix(workouts): repair deterministic volume before validation"
```

### Task 5: Document the coach-decision trace and run final verification

**Files:**
- Modify: `docs/superpowers/specs/2026-08-02-volume-aware-split-engine-design.md`
- Test: `backend/tests/workouts/program_engine/test_golden_scenarios.py`

**Interfaces:**
- The decision trace records selected session count, candidate split choice, volume soft/hard bounds, priority placement, and repair reasons.

- [ ] **Step 1: Write a failing explanation test**

```python
def test_program_trace_explains_priority_volume_and_repair() -> None:
    program = generate_program(
        golden_scenarios()["intermediate_5_days_shoulder_priority"], full_catalog(), RULESET
    ).program
    assert program is not None
    stages = {entry["stage"] for entry in program.decision_trace}
    assert {"split", "volume", "repair"}.issubset(stages)
```

- [ ] **Step 2: Run the focused test and verify RED**

Run: `TEST_DATABASE_URL='postgresql+psycopg://fitsho:fitsho@localhost:55433/fitsho_test' uv run pytest tests/workouts/program_engine/test_golden_scenarios.py -q`

Expected: missing `repair` trace stage.

- [ ] **Step 3: Add explainability and update the approved design**

Append the coach-template selection policy and future approved-physique-assessment boundary to the design spec. Add the `repair` stage to the engine trace even when no repair was needed, with an empty reason list.

- [ ] **Step 4: Run full verification and verify GREEN**

Run:

```bash
cd backend && TEST_DATABASE_URL='postgresql+psycopg://fitsho:fitsho@localhost:55433/fitsho_test' uv run pytest -q && uv run ruff check . && uv run mypy app
cd frontend && npm run test -- --run && npm run lint && npm run build
```

Expected: all tests, lint, type checks, and production build pass.

- [ ] **Step 5: Commit and push**

```bash
git add docs/superpowers/specs/2026-08-02-volume-aware-split-engine-design.md backend/tests/workouts/program_engine/test_golden_scenarios.py backend/app/workouts/program_engine/engine.py
git commit -m "docs(workouts): explain individualized coaching decisions"
git push -u origin feature/volume-aware-split-engine
```
