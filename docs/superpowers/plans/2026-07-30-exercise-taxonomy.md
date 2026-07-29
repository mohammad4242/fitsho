# Exercise Taxonomy Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add forearm/neck groups, fixed full-body/cardio labels, and import all 317 source exercises without fabricated anatomy.

**Architecture:** Anatomy, exercise type, and labels are independent. `forearms` and `neck` are the only new muscles. `full_body` and `cardio` are normalized labels. Unknown anatomy is stored as null, preserving source metadata and `needs_review=true`.

**Tech Stack:** FastAPI, SQLAlchemy, Alembic, PostgreSQL, Pydantic, pytest, React, TypeScript, Vite, Vitest.

## Global Constraints

- Never map hip flexors, abductors, or peroneals to an invented existing muscle.
- Preserve source identifiers, media paths, reports, dry runs, and `(source, source_id)` idempotency.
- All 317 imported records remain `needs_review=true` and `is_programmable=true`.
- Cardio-labelled candidates cannot satisfy required compound/isolation strength slots.
- Do not commit generated media, reports, database files, `backend/uv.lock`, or unrelated work.

---

### Task 1: Persist labels and optional anatomy

**Files:**
- Modify: `backend/app/exercises/enums.py`, `backend/app/exercises/models.py`, `backend/app/exercises/taxonomy.py`
- Create: `backend/alembic/versions/20260730_08_add_exercise_labels_and_nullable_anatomy.py`
- Test: `backend/tests/exercises/test_taxonomy.py`

**Interfaces:**
- `ExerciseLabel = FULL_BODY | CARDIO`
- `Exercise.body_region: BodyRegion | None`
- `Exercise.primary_muscle: MuscleGroup | None`
- `Exercise.labels: list[ExerciseLabelItem]`

- [ ] **Step 1: Write failing model tests**

```python
def test_upper_body_has_small_forearm_and_neck_groups() -> None:
    assert MuscleGroup.FOREARMS in MUSCLES_BY_REGION[BodyRegion.UPPER_BODY]
    assert MuscleGroup.NECK in MUSCLES_BY_REGION[BodyRegion.UPPER_BODY]


def test_exercise_persists_null_anatomy_and_cardio_label(db: Session) -> None:
    exercise = Exercise(
        slug="review-cardio", name_en="Review cardio", name_fa="هوازی بازبینی",
        body_region=None, primary_muscle=None, difficulty=Difficulty.BEGINNER,
        movement_pattern=MovementPattern.OTHER, exercise_type=ExerciseType.OTHER,
        instructions_en=["one", "two", "three"], instructions_fa=["یک", "دو", "سه"],
        safety_notes_en=[], safety_notes_fa=[], media_path="placeholder.webp",
        media_type=MediaType.PLACEHOLDER,
    )
    exercise.labels.append(ExerciseLabelItem(label=ExerciseLabel.CARDIO))
    db.add(exercise)
    db.commit()
    assert exercise.labels[0].label is ExerciseLabel.CARDIO
```

- [ ] **Step 2: Verify RED**

Run: `cd backend && uv run --extra dev pytest -q tests/exercises/test_taxonomy.py`

Expected: FAIL because the new enum values, relation, and nullable columns do not exist.

- [ ] **Step 3: Implement minimal schema and migration**

```python
class ExerciseLabel(StrEnum):
    FULL_BODY = "full_body"
    CARDIO = "cardio"


class ExerciseLabelItem(Base):
    __tablename__ = "exercise_label_items"
    __table_args__ = (UniqueConstraint("exercise_id", "label"),)
```

Add forearms/neck to `MuscleGroup` and upper-body taxonomy. Recreate anatomy enum check constraints, relax anatomy columns to nullable, create the association table with cascade deletion and a label index. Downgrade rejects null anatomy before reapplying non-null constraints.

- [ ] **Step 4: Verify GREEN**

Run: `cd backend && uv run alembic upgrade head && uv run --extra dev pytest -q tests/exercises/test_taxonomy.py`

Expected: PASS.

- [ ] **Step 5: Commit with `feat(exercises): add labels and nullable anatomy`**

### Task 2: Expose labels and optional anatomy in catalog/admin APIs

**Files:**
- Modify: `backend/app/exercises/schemas.py`, `backend/app/exercises/service.py`, `backend/app/exercises/router.py`
- Modify: `backend/app/admin/schemas.py`, `backend/app/admin/router.py`, `backend/app/admin/service.py`
- Test: `backend/tests/exercises/test_exercise_api.py`, `backend/tests/admin/test_exercise_api.py`

**Interfaces:**
- `ExerciseFilters(labels: list[ExerciseLabel] | None, exercise_type: ExerciseType | None)`
- Summary/detail/admin payloads expose nullable anatomy and `labels: list[ExerciseLabel]`.

- [ ] **Step 1: Write failing endpoint tests**

```python
def test_catalog_filters_by_repeated_labels(client, completed_user) -> None:
    response = client.get("/api/v1/exercises?labels=cardio&labels=full_body", headers=auth(completed_user))
    assert response.status_code == 200
    assert response.json()["items"][0]["labels"] == ["cardio", "full_body"]


def test_admin_accepts_review_record_without_anatomy(client, admin) -> None:
    response = client.post("/api/v1/admin/exercises", headers=auth(admin), json={
        **valid_payload(), "body_region": None, "primary_muscle": None,
        "labels": ["cardio"], "needs_review": True,
    })
    assert response.status_code == 201
```

- [ ] **Step 2: Verify RED**

Run: `cd backend && uv run --extra dev pytest -q tests/exercises/test_exercise_api.py tests/admin/test_exercise_api.py`

Expected: FAIL because anatomy is required and labels are absent.

- [ ] **Step 3: Implement API loading, filtering, and admin validation**

```python
if filters.labels:
    statement = statement.where(Exercise.labels.any(ExerciseLabelItem.label.in_(filters.labels)))
```

Use `selectinload(Exercise.labels)`. Repeated labels use AND semantics. Permit absent anatomy only for `needs_review=true`; otherwise keep the existing region-to-muscle check. Synchronize labels with set differences, as equipment and cautions do.

- [ ] **Step 4: Verify GREEN**

Run: `cd backend && uv run --extra dev pytest -q tests/exercises/test_exercise_api.py tests/admin/test_exercise_api.py`

Expected: PASS.

- [ ] **Step 5: Commit with `feat(catalog): expose exercise labels`**

### Task 3: Import all 317 source records conservatively

**Files:**
- Modify: `backend/app/exercises/free_exercise_db_import.py`, `backend/app/exercises/generate_free_exercise_db_translations.py`, `backend/app/exercises/free_exercise_db_translations.py`
- Test: `backend/tests/exercises/test_free_exercise_db_import.py`

**Interfaces:**
- `ImportCandidate(body_region: BodyRegion | None, primary_muscle: MuscleGroup | None, labels: tuple[ExerciseLabel, ...])`
- The report continues listing every unresolved source enum value even when the record imports.

- [ ] **Step 1: Write failing importer tests**

```python
def test_importer_maps_forearm_and_neck_variants(
    db: Session, test_settings: Settings, tmp_path: Path
) -> None:
    record = source_record()
    record["target"] = "forearms"
    source_root = tmp_path / "source"
    write_source(source_root, record)
    FreeExerciseDbImporter(db, settings=test_settings, source_root=source_root, translator=FakeTranslator()).run()
    exercise = db.scalar(select(Exercise).where(Exercise.source_id == "0001"))
    assert exercise is not None
    assert exercise.primary_muscle is MuscleGroup.FOREARMS


def test_importer_keeps_unmapped_anatomy_null_and_reviewable(
    db: Session, test_settings: Settings, tmp_path: Path
) -> None:
    record = source_record()
    record["target"] = "hip flexors"
    source_root = tmp_path / "source"
    write_source(source_root, record)
    report = FreeExerciseDbImporter(db, settings=test_settings, source_root=source_root, translator=FakeTranslator()).run()
    exercise = db.scalar(select(Exercise).where(Exercise.source_id == "0001"))
    assert report.imported_records == ["0001"]
    assert exercise is not None
    assert exercise.primary_muscle is None
    assert exercise.needs_review is True


def test_importer_adds_supported_cardio_label(
    db: Session, test_settings: Settings, tmp_path: Path
) -> None:
    record = source_record()
    record.update({"bodyPart": "cardio", "target": "cardiovascular system"})
    source_root = tmp_path / "source"
    write_source(source_root, record)
    FreeExerciseDbImporter(db, settings=test_settings, source_root=source_root, translator=FakeTranslator()).run()
    exercise = db.scalar(select(Exercise).where(Exercise.source_id == "0001"))
    assert exercise is not None
    assert {item.label for item in exercise.labels} == {ExerciseLabel.CARDIO}
```

- [ ] **Step 2: Verify RED**

Run: `cd backend && uv run --extra dev pytest -q tests/exercises/test_free_exercise_db_import.py`

Expected: FAIL because unknown primary anatomy is currently skipped and labels are absent.

- [ ] **Step 3: Implement parsing and label classification**

```python
if target in {"forearms", "forearm extensors"}:
    primary_muscle = MuscleGroup.FOREARMS
elif target in {"neck flexors", "sternocleidomastoid"}:
    primary_muscle = MuscleGroup.NECK
else:
    primary_muscle = map_muscle_group(target)
```

Unknown anatomy becomes `None` after report recording, never a skip. Give `cardio` only to explicit cardiovascular source records and `full_body` only to explicit full-body source records. Stretch/mobility has priority over an erroneous cardio body part. Compare and synchronize labels in `_is_current` and `_apply_candidate`; regenerate the static Persian catalog for now-importable records.

- [ ] **Step 4: Verify GREEN**

Run: `cd backend && uv run --extra dev pytest -q tests/exercises/test_free_exercise_db_import.py`

Expected: PASS.

- [ ] **Step 5: Verify real source import**

Run:

```bash
cd backend
SOURCE_ROOT=/home/mohammad/project/free-exercise-db-with-videos
MEDIA_ROOT="$PWD/var/media" uv run --extra dev python -m app.exercises.free_exercise_db_import --source-root "$SOURCE_ROOT" --dry-run
MEDIA_ROOT="$PWD/var/media" uv run --extra dev python -m app.exercises.free_exercise_db_import --source-root "$SOURCE_ROOT" --report import-report-free-exercise-db.json
MEDIA_ROOT="$PWD/var/media" uv run --extra dev python -m app.exercises.free_exercise_db_import --source-root "$SOURCE_ROOT" --dry-run
```

Expected: first dry run has 317 pending source records; full run stores 317 source records; final dry run has zero inserts and updates.

- [ ] **Step 6: Commit with `feat(import): retain unresolved exercise anatomy`**

### Task 4: Keep workout generation safe

**Files:**
- Modify: `backend/app/workouts/schemas.py`, `backend/app/workouts/candidate_selector.py`, `backend/app/workouts/prompt_builder.py`, `backend/app/workouts/signature.py`, `backend/app/workouts/validator.py`
- Test: `backend/tests/workouts/test_candidate_selector.py`, `backend/tests/workouts/test_prompt_builder.py`, `backend/tests/workouts/test_validator.py`

**Interfaces:**
- Workout candidates carry nullable anatomy and labels.
- Cardio labels are preserved in prompts/signatures but do not satisfy strength quotas.

- [ ] **Step 1: Write failing workout tests**

```python
def test_candidate_preserves_cardio_label_and_null_primary_muscle(db: Session) -> None:
    cardio = exercise(db, "cardio-step", equipment=(Equipment.BODYWEIGHT,))
    cardio.primary_muscle = None
    cardio.labels.append(ExerciseLabelItem(label=ExerciseLabel.CARDIO))
    db.commit()
    candidate = WorkoutCandidateSelector(db).select(
        profile(location=TrainingLocation.HOME, setup=HomeTrainingSetup.BODYWEIGHT_ONLY)
    ).exercises[0]
    assert candidate.primary_muscle is None
    assert ExerciseLabel.CARDIO in candidate.labels


def test_cardio_cannot_fill_required_strength_slot() -> None:
    result = validator.validate(plan_with_only_cardio_for_strength_slot)
    assert result.code == "insufficient_strength_movements"
```

- [ ] **Step 2: Verify RED**

Run: `cd backend && uv run --extra dev pytest -q tests/workouts/test_candidate_selector.py tests/workouts/test_prompt_builder.py tests/workouts/test_validator.py`

Expected: FAIL because candidates require anatomy and do not expose labels.

- [ ] **Step 3: Implement nullable-safe selection and validation**

```python
is_cardio = ExerciseLabel.CARDIO in candidate.labels
can_fill_strength_slot = not is_cardio and candidate.exercise_type in {
    ExerciseType.COMPOUND, ExerciseType.ISOLATION,
}
```

Skip null primary muscles when building muscle sets, serialize null anatomy/labels, retain `is_programmable=true`, and rank cardio after strength candidates.

- [ ] **Step 4: Verify GREEN**

Run: `cd backend && uv run --extra dev pytest -q tests/workouts/test_candidate_selector.py tests/workouts/test_prompt_builder.py tests/workouts/test_validator.py`

Expected: PASS.

- [ ] **Step 5: Commit with `feat(workouts): support labelled unresolved exercises`**

### Task 5: Add catalog/admin label UI

**Files:**
- Modify: `frontend/src/features/exercises/types.ts`, `frontend/src/features/exercises/api.ts`, `frontend/src/features/exercises/ExerciseCatalogPage.tsx`, `frontend/src/features/exercises/ExerciseDetailPage.tsx`, `frontend/src/features/exercises/exercises.css`
- Modify: `frontend/src/features/admin/types.ts`, `frontend/src/features/admin/validation.ts`, `frontend/src/features/admin/AdminExerciseNewPage.tsx`, `frontend/src/features/admin/AdminExerciseEditPage.tsx`, `frontend/src/features/admin/AdminExerciseForm.tsx`, `frontend/src/features/admin/admin.css`
- Test: `frontend/src/features/exercises/ExerciseCatalogPage.test.tsx`, `frontend/src/features/exercises/ExerciseDetailPage.test.tsx`, `frontend/src/features/admin/AdminExerciseNewPage.test.tsx`, `frontend/src/features/admin/validation.test.ts`

**Interfaces:**
- Exercise UI types use `body_region: BodyRegion | null`, `primary_muscle: MuscleGroup | null`, and `labels: ExerciseLabel[]`.
- URL state uses repeated `labels` parameters.

- [ ] **Step 1: Write failing UI tests**

```tsx
it("opens the cardio catalog section", async () => {
  renderCatalog("/exercises");
  await userEvent.click(screen.getByRole("button", { name: "هوازی" }));
  expect(locationValue()).toBe("/exercises?labels=cardio");
});


it("allows a review record with labels and no anatomy", async () => {
  renderNewExercisePage();
  await userEvent.click(screen.getByLabelText("هوازی"));
  expect(screen.getByLabelText("عضلهٔ اصلی")).not.toBeRequired();
});
```

- [ ] **Step 2: Verify RED**

Run: `cd frontend && npm test -- --run ExerciseCatalogPage.test.tsx ExerciseDetailPage.test.tsx AdminExerciseNewPage.test.tsx validation.test.ts`

Expected: FAIL because label controls and optional API types are absent.

- [ ] **Step 3: Implement label browsing and review display**

```ts
export type ExerciseLabel = "full_body" | "cardio";

export type ExerciseSummary = {
  body_region: BodyRegion | null;
  primary_muscle: MuscleGroup | null;
  labels: ExerciseLabel[];
};
```

Render special filters «تمام‌بدن», «هوازی», and «کشش و موبیلیتی». Render forearms/neck in a smaller upper-body group. Render absent anatomy as «نیازمند بازبینی» and permit empty admin anatomy only when review is active.

- [ ] **Step 4: Verify GREEN**

Run: `cd frontend && npm test -- --run ExerciseCatalogPage.test.tsx ExerciseDetailPage.test.tsx AdminExerciseNewPage.test.tsx validation.test.ts`

Expected: PASS.

- [ ] **Step 5: Commit with `feat(frontend): browse exercises by labels`**

### Task 6: Full verification and publication

**Files:**
- Modify: `docs/superpowers/specs/2026-07-30-exercise-taxonomy-design.md` only if a verified design correction is necessary.

- [ ] **Step 1: Run backend checks**

Run:

```bash
cd backend
uv run --extra dev ruff check app tests
uv run --extra dev pytest -q
```

Expected: no lint errors and all non-live backend tests pass.

- [ ] **Step 2: Run frontend checks**

Run:

```bash
cd frontend
npm test -- --run
npm run build
```

Expected: all frontend tests and the production build pass.

- [ ] **Step 3: Verify final source and storage**

Run a dry run against `../free-exercise-db-with-videos`, confirm 317 source records and zero pending inserts/updates, inspect the report, and confirm every stored media path exists beneath the active media root. In Docker Compose, run the importer with `MEDIA_ROOT=/var/lib/fitsho/media` or copy media into the named `fitsho_exercise_media` volume.

- [ ] **Step 4: Push `feature/exercise-taxonomy`**

If verification changes the specification, commit it with `docs(exercises): record taxonomy verification`; otherwise do not create an empty commit.
