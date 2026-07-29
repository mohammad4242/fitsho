# Imported Exercise Programming Metadata Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Classify every imported Free Exercise DB exercise for program generation and correct existing imports idempotently.

**Architecture:** Keep classification in the importer as a pure function of the source metadata. Store its result in `ImportCandidate`, synchronize the exercise fields and caution-tag relationship on save, and include it in the current-record comparison so reruns repair old imports without duplicates.

**Tech Stack:** Python 3.12, SQLAlchemy, PostgreSQL, pytest.

## Global Constraints

- Do not add enum values or infer medical or injury claims from video media.
- Caution tags require explicit source-text or movement-pattern support.
- Every valid imported record has `is_programmable=True` and `needs_review=True`.
- Existing imports are updated through the idempotent importer; no migration is required.

---

### Task 1: Classify source records

**Files:**
- Modify: `backend/app/exercises/free_exercise_db_import.py`
- Test: `backend/tests/exercises/test_free_exercise_db_import.py`

**Interfaces:**
- Produces: `ProgrammingMetadata` with `movement_pattern`, `exercise_type`, and `caution_tags`.
- Consumes: source name, instructions, steps, form cues, common mistakes, target muscle, and `BodyRegion`.

- [ ] **Step 1: Write the failing classification tests**

```python
def test_programming_metadata_classifies_known_movements_conservatively() -> None:
    hyperextension = classify_programming_metadata(
        name_en="45 Degree Hyperextension", primary_muscle=MuscleGroup.LOWER_BACK,
        instructions_en=[], steps_en=[], form_cues_en=[], common_mistakes_en=[],
    )
    bicycle_crunch = classify_programming_metadata(
        name_en="45-Degree Bicycle Twisting Crunch", primary_muscle=MuscleGroup.OBLIQUES,
        instructions_en=[], steps_en=[], form_cues_en=["Do not pull on neck"], common_mistakes_en=[],
    )
    stretch = classify_programming_metadata(
        name_en="All Fours Groin Stretch", primary_muscle=MuscleGroup.ADDUCTORS,
        instructions_en=[], steps_en=[], form_cues_en=[], common_mistakes_en=[],
    )
    assert hyperextension.movement_pattern is MovementPattern.HIP_HINGE
    assert bicycle_crunch.caution_tags == (
        ExerciseCautionTag.SPINAL_FLEXION,
        ExerciseCautionTag.NECK_LOADING,
    )
    assert stretch.exercise_type is ExerciseType.MOBILITY
```

- [ ] **Step 2: Run the focused test and verify it fails**

Run:

```bash
uv run pytest tests/exercises/test_free_exercise_db_import.py -k programming_metadata -q
```

Expected: failure because `classify_programming_metadata` does not exist.

- [ ] **Step 3: Implement the pure classifier**

```python
@dataclass(frozen=True)
class ProgrammingMetadata:
    movement_pattern: MovementPattern
    exercise_type: ExerciseType
    caution_tags: tuple[ExerciseCautionTag, ...]

def classify_programming_metadata(
    *, name_en: str, primary_muscle: MuscleGroup, instructions_en: Sequence[str],
    steps_en: Sequence[str], form_cues_en: Sequence[str], common_mistakes_en: Sequence[str],
) -> ProgrammingMetadata:
    """Return explicit pattern, type, and conservative caution tags."""
```

- [ ] **Step 4: Run the focused test and verify it passes**

Run:

```bash
uv run pytest tests/exercises/test_free_exercise_db_import.py -k programming_metadata -q
```

Expected: PASS.

### Task 2: Persist and reconcile metadata

**Files:**
- Modify: `backend/app/exercises/free_exercise_db_import.py`
- Test: `backend/tests/exercises/test_free_exercise_db_import.py`

**Interfaces:**
- Consumes: `ImportCandidate.programming_metadata` from Task 1.
- Produces: populated exercise metadata, synchronized `ExerciseCautionTagItem` rows, and updates on importer rerun.

- [ ] **Step 1: Write the failing importer regression test**

```python
def test_importer_programs_new_and_existing_exercises(db, test_settings, tmp_path) -> None:
    first = importer.run()
    second = importer.run()
    exercise = db.scalar(select(Exercise).where(Exercise.source_id == "0001"))
    assert first.imported_records == ["0001"]
    assert second.updated_records == ["0001"]
    assert exercise.is_programmable is True
    assert exercise.movement_pattern is MovementPattern.HORIZONTAL_PUSH
```

- [ ] **Step 2: Run the focused test and verify it fails**

Run:

```bash
uv run pytest tests/exercises/test_free_exercise_db_import.py -k programs_new_and_existing -q
```

Expected: failure because the importer leaves the database defaults in place and skips the second run.

- [ ] **Step 3: Apply and compare programming metadata**

```python
exercise.movement_pattern = candidate.programming_metadata.movement_pattern
exercise.exercise_type = candidate.programming_metadata.exercise_type
exercise.is_programmable = True
_sync_caution_tags(exercise, candidate.programming_metadata.caution_tags)
```

Load caution-tag rows in `_existing_exercise` and include their values plus all three metadata fields in `_is_current`.

- [ ] **Step 4: Run focused importer tests and verify they pass**

Run:

```bash
uv run pytest tests/exercises/test_free_exercise_db_import.py -q
```

Expected: PASS.

### Task 3: Correct the local imported sample

**Files:**
- Modify: none
- Test: `backend/tests/exercises/test_free_exercise_db_import.py`

**Interfaces:**
- Consumes: idempotent importer from Task 2 and the locally downloaded source dataset.
- Produces: updated rows `0489`, both bicycle crunch IDs, the groin stretch, and `0970`.

- [ ] **Step 1: Add the exact five-record regression test**

```python
assert metadata["0489"] == (MovementPattern.HIP_HINGE, ExerciseType.COMPOUND, {ExerciseCautionTag.LOWER_BACK_LOADING})
assert metadata["0970"] == (MovementPattern.VERTICAL_PULL, ExerciseType.COMPOUND, {ExerciseCautionTag.OVERHEAD_POSITION})
```

- [ ] **Step 2: Run the test and verify the classifier covers the source sample**

Run:

```bash
uv run pytest tests/exercises/test_free_exercise_db_import.py -k imported_sample -q
```

Expected: PASS after Task 1 and Task 2 have been applied.

- [ ] **Step 3: Re-run the five-record import**

```bash
uv run python -m app.exercises.free_exercise_db_import \
  --source-root ../../free-exercise-db-with-videos --limit 5
```

- [ ] **Step 4: Verify database state and the full backend suite**

Run:

```bash
uv run pytest -q
```

Expected: PASS. Confirm the import report lists the five source IDs as updated and no duplicate exercises exist.

- [ ] **Step 5: Commit**

```bash
git add backend/app/exercises/free_exercise_db_import.py backend/tests/exercises/test_free_exercise_db_import.py
git commit -m "feat(import): classify exercise programming metadata"
```
