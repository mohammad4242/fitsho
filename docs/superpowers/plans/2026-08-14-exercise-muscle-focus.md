# Exercise Muscle Focus Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the structured `Body Region -> Muscle Group -> Muscle Focus -> Exercises` layer while preserving current catalogue, admin, importer, and workout behavior.

**Architecture:** Store one nullable controlled `MuscleFocus` value on each exercise and define compatibility/order/localized labels in the existing exercise taxonomy module. Use one deterministic classifier plus a reviewed stable-ID audit manifest for imports, seeds, placeholders, and migration backfill; expose the value through existing public/admin contracts and add a third catalogue selector whose `All` state omits the query parameter.

**Tech Stack:** Python 3.12, FastAPI, Pydantic, SQLAlchemy 2, PostgreSQL, Alembic, Pytest, React 19, TypeScript 6, Vite, Vitest, i18next.

## Global Constraints

- Keep `body_region`, `primary_muscle`, and `secondary_muscles` unchanged.
- `all` is UI/query state only and is never stored.
- Existing requests and URLs without `muscle_focus` must return the same catalogue results.
- Exercises with a known primary muscle require one compatible focus; exercises without a primary muscle require a null focus.
- Classification must use source targets and secondary muscles before names, must not silently guess, and must report unresolved stable IDs.
- Public endpoints remain read-only; admin writes remain under the protected admin router and existing permission/origin checks.
- Workout generation continues using existing primary-muscle programming behavior.
- Preserve unrelated work, including the existing local `compose.yaml` change.

---

## File Map

- `backend/app/exercises/enums.py`: persisted `MuscleFocus` string enum.
- `backend/app/exercises/taxonomy.py`: ordered focus definitions, bilingual labels, compatibility validation.
- `backend/app/exercises/focus_classifier.py`: deterministic metadata/mechanics classifier and explicit uncertainty result.
- `backend/app/exercises/focus_manifest.py`: reviewed stable exercise identity to focus/backfill mapping and audit basis.
- `backend/app/exercises/audit_muscle_focus.py`: full-catalogue report and unresolved-record gate.
- `backend/app/exercises/models.py`: nullable column, index, and database checks.
- `backend/alembic/versions/20260814_78_add_exercise_muscle_focus.py`: schema and reviewed-data backfill.
- `backend/app/exercises/{schemas,router,service}.py`: public serialization, categories, and filtering.
- `backend/app/admin/{schemas,router,service}.py`: protected create/edit/list contracts and compatibility validation.
- `backend/app/exercises/{seed_data,seed,free_exercise_db_import}.py`: deterministic future assignment and idempotent updates.
- `backend/app/training_templates/catalog_placeholders.py`: explicit placeholder focus assignment.
- `frontend/src/features/exercises/{types,api,ExerciseCatalogPage,ExerciseDetailPage,exercises.css}.ts*`: third selector, URL/API state, display, and responsive styling.
- `frontend/src/features/admin/{types,validation,AdminExerciseFields,exerciseLibraryNavigation}.ts*`: editable compatible focus and return-context preservation.
- `frontend/src/i18n/{en,fa}.ts`: focus labels and selector text.

### Task 1: Taxonomy Contract and Compatibility

**Files:**
- Modify: `backend/app/exercises/enums.py`
- Modify: `backend/app/exercises/taxonomy.py`
- Test: `backend/tests/exercises/test_taxonomy.py`

**Interfaces:**
- Produces: `MuscleFocus`, `FOCUSES_BY_MUSCLE`, `MUSCLE_FOCUS_CATEGORIES`, and `is_compatible_muscle_focus(primary_muscle, muscle_focus) -> bool`.
- Consumes: existing `MuscleGroup` and `MUSCLES_BY_REGION`.

- [ ] **Step 1: Write failing enum, ordering, and compatibility tests**

```python
def test_chest_focuses_are_ordered_for_catalogue() -> None:
    assert FOCUSES_BY_MUSCLE[MuscleGroup.CHEST] == (
        MuscleFocus.GENERAL_CHEST,
        MuscleFocus.UPPER_CHEST,
        MuscleFocus.MID_CHEST,
        MuscleFocus.LOWER_CHEST,
    )


def test_focus_compatibility_is_bound_to_primary_muscle() -> None:
    assert is_compatible_muscle_focus(MuscleGroup.CHEST, MuscleFocus.UPPER_CHEST)
    assert not is_compatible_muscle_focus(MuscleGroup.SHOULDERS, MuscleFocus.UPPER_CHEST)
    assert is_compatible_muscle_focus(None, None)
    assert not is_compatible_muscle_focus(MuscleGroup.CHEST, None)
    assert not is_compatible_muscle_focus(None, MuscleFocus.UPPER_CHEST)
```

- [ ] **Step 2: Run the focused test and confirm RED**

Run: `cd backend && .venv/bin/pytest tests/exercises/test_taxonomy.py -q`

Expected: FAIL because `MuscleFocus` and compatibility mappings do not exist.

- [ ] **Step 3: Add the approved enum and central mapping**

```python
class MuscleFocus(StrEnum):
    GENERAL_CHEST = "general_chest"
    UPPER_CHEST = "upper_chest"
    MID_CHEST = "mid_chest"
    LOWER_CHEST = "lower_chest"
    GENERAL_BACK = "general_back"
    LATS = "lats"
    MID_BACK_RHOMBOIDS = "mid_back_rhomboids"
    UPPER_BACK = "upper_back"
    GENERAL_SHOULDERS = "general_shoulders"
    FRONT_DELT = "front_delt"
    LATERAL_DELT = "lateral_delt"
    REAR_DELT = "rear_delt"
    GENERAL_BICEPS = "general_biceps"
    BICEPS_BRACHII = "biceps_brachii"
    BRACHIALIS_BRACHIORADIALIS = "brachialis_brachioradialis"
    GENERAL_TRICEPS = "general_triceps"
    TRICEPS_LONG_HEAD = "triceps_long_head"
    TRICEPS_LATERAL_MEDIAL_HEADS = "triceps_lateral_medial_heads"
    UPPER_TRAPS = "upper_traps"
    MID_LOWER_TRAPS = "mid_lower_traps"
    GENERAL_FOREARMS = "general_forearms"
    FOREARM_FLEXORS = "forearm_flexors"
    FOREARM_EXTENSORS = "forearm_extensors"
    NECK_FLEXION = "neck_flexion"
    NECK_LATERAL_EXTENSION = "neck_lateral_extension"
    GLUTE_MAX = "glute_max"
    GLUTE_MEDIUS_MINIMUS = "glute_medius_minimus"
    GENERAL_QUADRICEPS = "general_quadriceps"
    RECTUS_FEMORIS = "rectus_femoris"
    VASTI = "vasti"
    HAMSTRINGS_HIP_EXTENSION = "hamstrings_hip_extension"
    HAMSTRINGS_KNEE_FLEXION = "hamstrings_knee_flexion"
    HIP_ADDUCTION = "hip_adduction"
    ADDUCTOR_MOBILITY = "adductor_mobility"
    GENERAL_CALVES = "general_calves"
    GASTROCNEMIUS = "gastrocnemius"
    SOLEUS = "soleus"
    TRUNK_FLEXION = "trunk_flexion"
    HIP_FLEXION_POSTERIOR_TILT = "hip_flexion_posterior_tilt"
    ANTI_EXTENSION = "anti_extension"
    TRUNK_ROTATION = "trunk_rotation"
    LATERAL_FLEXION = "lateral_flexion"
    ANTI_ROTATION = "anti_rotation"
    LUMBAR_ERECTORS = "lumbar_erectors"
    THORACIC_MOBILITY = "thoracic_mobility"
```

Add every approved ordered tuple to `FOCUSES_BY_MUSCLE`, add matching English/Persian labels to `MUSCLE_FOCUS_CATEGORIES`, and implement compatibility as exact tuple membership with the null invariant.

- [ ] **Step 4: Run taxonomy tests and static checks**

Run: `cd backend && .venv/bin/pytest tests/exercises/test_taxonomy.py -q && .venv/bin/ruff check app/exercises/enums.py app/exercises/taxonomy.py tests/exercises/test_taxonomy.py && .venv/bin/mypy app/exercises`

Expected: PASS.

- [ ] **Step 5: Commit and push**

```bash
git add backend/app/exercises/enums.py backend/app/exercises/taxonomy.py backend/tests/exercises/test_taxonomy.py
git commit -m "feat(exercises): define muscle focus taxonomy"
git push
```

### Task 2: Deterministic Classification and Full-Catalogue Audit

**Files:**
- Create: `backend/app/exercises/focus_classifier.py`
- Create: `backend/app/exercises/focus_manifest.py`
- Create: `backend/app/exercises/audit_muscle_focus.py`
- Create: `backend/tests/exercises/test_focus_classifier.py`
- Create: `backend/tests/exercises/test_focus_manifest.py`

**Interfaces:**
- Consumes: `MuscleFocus`, `MuscleGroup`, `MovementPattern`, `ExerciseType`.
- Produces: `FocusEvidence`, `FocusClassification`, `classify_muscle_focus(...) -> FocusClassification | None`, `FOCUS_MANIFEST: dict[tuple[str, str], FocusEvidence]`, and `audit_catalogue(db: Session) -> FocusAuditReport`.

- [ ] **Step 1: Write failing precedence and uncertainty tests**

```python
def test_exact_source_target_wins_over_name_hint() -> None:
    result = classify_muscle_focus(
        primary_muscle=MuscleGroup.CHEST,
        source_target="upper pectorals",
        secondary_targets=(),
        name_en="Flat-looking press",
        movement_pattern=MovementPattern.HORIZONTAL_PUSH,
        exercise_type=ExerciseType.COMPOUND,
        instructions_en=(),
    )
    assert result == FocusClassification(
        focus=MuscleFocus.UPPER_CHEST,
        basis="source_target:upper pectorals",
    )


def test_unresolved_mechanics_return_none_instead_of_general() -> None:
    assert classify_muscle_focus(
        primary_muscle=MuscleGroup.CHEST,
        source_target="pectorals",
        secondary_targets=(),
        name_en="Unknown press",
        movement_pattern=MovementPattern.OTHER,
        exercise_type=ExerciseType.OTHER,
        instructions_en=(),
    ) is None
```

- [ ] **Step 2: Run classifier tests and confirm RED**

Run: `cd backend && .venv/bin/pytest tests/exercises/test_focus_classifier.py -q`

Expected: FAIL because the classifier module does not exist.

- [ ] **Step 3: Implement source-first deterministic rules**

```python
@dataclass(frozen=True)
class FocusClassification:
    focus: MuscleFocus
    basis: str


def classify_muscle_focus(
    *,
    primary_muscle: MuscleGroup | None,
    source_target: str | None,
    secondary_targets: Sequence[str],
    name_en: str,
    movement_pattern: MovementPattern,
    exercise_type: ExerciseType,
    instructions_en: Sequence[str],
) -> FocusClassification | None:
    if primary_muscle is None:
        return None
    normalized_target = normalize_focus_text(source_target)
    exact = SOURCE_TARGET_RULES.get((primary_muscle, normalized_target))
    if exact is not None:
        return FocusClassification(exact, f"source_target:{normalized_target}")
    return classify_from_mechanics(
        primary_muscle=primary_muscle,
        secondary_targets=secondary_targets,
        name_en=name_en,
        movement_pattern=movement_pattern,
        exercise_type=exercise_type,
        instructions_en=instructions_en,
    )
```

Implement explicit source-target tables and mechanically explicit variants for all approved groups. Return `None` when no rule proves a focus; do not use a general focus as fallback.

- [ ] **Step 4: Generate the live audit manifest and unresolved report**

Run: `cd backend && .venv/bin/python -m app.exercises.audit_muscle_focus --format json --output var/imports/muscle-focus-audit.json`

Expected: report totals equal the live catalogue, records the stable `(source, source_id)` or seed slug, classification basis, and lists all unresolved known-primary exercises separately.

- [ ] **Step 5: Resolve each reported record using stored metadata and reliable sources**

For each unresolved record, add one explicit manifest entry only after checking `source_metadata_en`, target/secondary muscles, instructions, movement pattern, and mechanics. Store entries in this exact shape:

```python
FOCUS_MANIFEST[("free-exercise-db", "0001")] = FocusEvidence(
    focus=MuscleFocus.UPPER_CHEST,
    basis="source_target:upper pectorals",
)
```

If any known-primary record is still uncertain, stop this task and report its stable ID, names, source target, secondary muscles, movement pattern, and instructions to the user. Do not proceed to migration.

- [ ] **Step 6: Add full manifest integrity tests**

```python
def test_manifest_has_one_compatible_focus_for_every_known_primary_fixture() -> None:
    report = audit_catalogue(db_session)
    assert report.known_primary_count == report.classified_count
    assert report.unresolved == ()
    assert report.incompatible == ()


def test_null_primary_records_remain_unclassified() -> None:
    report = audit_catalogue(db_session)
    assert all(item.focus is None for item in report.null_primary)
```

- [ ] **Step 7: Run audit tests and checks**

Run: `cd backend && .venv/bin/pytest tests/exercises/test_focus_classifier.py tests/exercises/test_focus_manifest.py -q && .venv/bin/ruff check app/exercises/focus_classifier.py app/exercises/focus_manifest.py app/exercises/audit_muscle_focus.py tests/exercises/test_focus_classifier.py tests/exercises/test_focus_manifest.py && .venv/bin/mypy app/exercises`

Expected: PASS and zero unresolved known-primary fixtures.

- [ ] **Step 8: Commit and push**

```bash
git add backend/app/exercises/focus_classifier.py backend/app/exercises/focus_manifest.py backend/app/exercises/audit_muscle_focus.py backend/tests/exercises/test_focus_classifier.py backend/tests/exercises/test_focus_manifest.py
git commit -m "feat(exercises): classify catalogue muscle focuses"
git push
```

### Task 3: Persistence and Backfill Migration

**Files:**
- Modify: `backend/app/exercises/models.py`
- Create: `backend/alembic/versions/20260814_78_add_exercise_muscle_focus.py`
- Modify: `backend/tests/database/test_exercise_models.py`
- Create: `backend/tests/database/test_exercise_muscle_focus_migration.py`

**Interfaces:**
- Consumes: `MuscleFocus`, `FOCUS_MANIFEST`, and compatibility pairs from Tasks 1-2.
- Produces: `Exercise.muscle_focus: Mapped[MuscleFocus | None]`, composite index `ix_exercises_primary_muscle_muscle_focus`, and migration revision `20260814_78` after `20260814_77`.

- [ ] **Step 1: Write failing model invariant tests**

```python
def test_exercise_has_nullable_muscle_focus_column() -> None:
    column = Exercise.__table__.c.muscle_focus
    assert column.nullable is True
    assert column.type.length == 40


def test_exercise_has_primary_muscle_focus_index() -> None:
    assert "ix_exercises_primary_muscle_muscle_focus" in {
        index.name for index in Exercise.__table__.indexes
    }
```

- [ ] **Step 2: Run model tests and confirm RED**

Run: `cd backend && .venv/bin/pytest tests/database/test_exercise_models.py -q`

Expected: FAIL because the column/index are absent.

- [ ] **Step 3: Add the model column and database checks**

```python
muscle_focus: Mapped[MuscleFocus | None] = mapped_column(
    String(40),
    nullable=True,
)
```

Add the enum-value check, the generated allowed `(primary_muscle, muscle_focus)` compatibility check, the null-pair invariant, and the composite index. Keep the existing primary-muscle index.

- [ ] **Step 4: Write migration upgrade/downgrade tests**

```python
def test_upgrade_backfills_all_known_primary_exercises(migrated_connection) -> None:
    rows = migrated_connection.execute(sa.text(
        "SELECT primary_muscle, muscle_focus FROM exercises"
    )).all()
    assert all((primary is None) == (focus is None) for primary, focus in rows)


def test_upgrade_preserves_exercise_count_and_existing_columns(migrated_connection) -> None:
    assert migrated_connection.scalar(sa.text("SELECT count(*) FROM exercises")) == 341
```

- [ ] **Step 5: Implement revision `20260814_78`**

The migration must add the nullable column, bulk-update by reviewed stable source/source-id or slug mappings, assert no known-primary null remains, add the enum and compatibility checks, and add the composite index. Downgrade removes only the new index, checks, and column.

- [ ] **Step 6: Verify upgrade, invariants, and downgrade/upgrade**

Run: `cd backend && .venv/bin/pytest tests/database/test_exercise_models.py tests/database/test_exercise_muscle_focus_migration.py -q`

Run: `cd backend && .venv/bin/alembic upgrade head && .venv/bin/alembic current`

Run: `cd backend && .venv/bin/alembic downgrade 20260814_77 && .venv/bin/alembic upgrade head && .venv/bin/alembic current`

Expected: tests PASS; both final `current` outputs show `20260814_78 (head)`; exercise totals and null invariants are unchanged.

- [ ] **Step 7: Commit and push**

```bash
git add backend/app/exercises/models.py backend/alembic/versions/20260814_78_add_exercise_muscle_focus.py backend/tests/database/test_exercise_models.py backend/tests/database/test_exercise_muscle_focus_migration.py
git commit -m "feat(exercises): persist reviewed muscle focuses"
git push
```

### Task 4: Public Catalogue API and Backward Compatibility

**Files:**
- Modify: `backend/app/exercises/schemas.py`
- Modify: `backend/app/exercises/router.py`
- Modify: `backend/app/exercises/service.py`
- Modify: `backend/tests/exercises/test_exercise_api.py`

**Interfaces:**
- Consumes: `Exercise.muscle_focus`, `MUSCLE_FOCUS_CATEGORIES`, `is_compatible_muscle_focus`.
- Produces: optional `ExerciseFilters.muscle_focus`, serialized summary/detail field, and `ExerciseCategories.muscle_focuses: dict[MuscleGroup, list[MuscleFocusCategory]]`.

- [ ] **Step 1: Write failing categories, serialization, filtering, and unchanged-All tests**

```python
def test_categories_return_ordered_bilingual_chest_focuses(client) -> None:
    response = client.get("/api/v1/exercise-categories")
    assert [item["value"] for item in response.json()["muscle_focuses"]["chest"]] == [
        "general_chest", "upper_chest", "mid_chest", "lower_chest",
    ]


def test_specific_focus_filters_within_primary_muscle(client) -> None:
    response = client.get(
        "/api/v1/exercises?body_region=upper_body&primary_muscle=chest&muscle_focus=upper_chest"
    )
    assert response.status_code == 200
    assert {item["muscle_focus"] for item in response.json()["items"]} == {"upper_chest"}


def test_omitting_focus_preserves_existing_muscle_result(client) -> None:
    payload = client.get("/api/v1/exercises?primary_muscle=chest&page_size=50").json()
    assert {item["slug"] for item in payload["items"]} == {
        "dumbbell-bench-press",
        "incline-dumbbell-press",
    }
```

- [ ] **Step 2: Run focused API tests and confirm RED**

Run: `cd backend && .venv/bin/pytest tests/exercises/test_exercise_api.py -q`

Expected: new assertions FAIL because the API omits focus.

- [ ] **Step 3: Extend schemas, category response, summary/detail mapping, and query filter**

```python
class MuscleFocusCategory(BaseModel):
    value: MuscleFocus
    name_en: str
    name_fa: str


class ExerciseFilters(BaseModel):
    body_region: BodyRegion | None = None
    primary_muscle: MuscleGroup | None = None
    muscle_focus: MuscleFocus | None = None
```

Validate that a supplied focus is compatible with the supplied primary muscle and append `Exercise.muscle_focus == filters.muscle_focus` in `list_exercises`. Add `muscle_focus` to `_summary` so details inherit it.

- [ ] **Step 4: Run public API and workout regression tests**

Run: `cd backend && .venv/bin/pytest tests/exercises/test_exercise_api.py tests/workouts tests/training_templates -q`

Expected: PASS; existing workout selection/prescription results remain unchanged.

- [ ] **Step 5: Commit and push**

```bash
git add backend/app/exercises/schemas.py backend/app/exercises/router.py backend/app/exercises/service.py backend/tests/exercises/test_exercise_api.py
git commit -m "feat(exercises): filter catalogue by muscle focus"
git push
```

### Task 5: Protected Admin API and Validation

**Files:**
- Modify: `backend/app/admin/schemas.py`
- Modify: `backend/app/admin/router.py`
- Modify: `backend/app/admin/service.py`
- Modify: `backend/tests/admin/test_exercise_api.py`

**Interfaces:**
- Consumes: `MuscleFocus` and `is_compatible_muscle_focus`.
- Produces: admin list filter and create/edit persistence for `muscle_focus`, without changing route protection.

- [ ] **Step 1: Write failing authorization, filter, create, edit, and validation tests**

```python
def test_admin_can_create_exercise_with_compatible_focus(admin_client) -> None:
    payload = valid_payload(primary_muscle="chest", muscle_focus="upper_chest")
    response = post_exercise(admin_client, payload)
    assert response.status_code == 201
    assert response.json()["muscle_focus"] == "upper_chest"


def test_admin_cannot_save_incompatible_focus(admin_client) -> None:
    payload = valid_payload(primary_muscle="shoulders", muscle_focus="upper_chest")
    response = post_exercise(admin_client, payload)
    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"][-1] == "muscle_focus"


def test_non_admin_still_cannot_write_exercises(member_client) -> None:
    assert post_exercise(member_client, valid_payload()).status_code == 403
```

- [ ] **Step 2: Run admin API tests and confirm RED**

Run: `cd backend && .venv/bin/pytest tests/admin/test_exercise_api.py -q`

Expected: focus create/filter assertions FAIL; existing authorization assertions remain green.

- [ ] **Step 3: Extend protected schemas, payload validation, services, and detail mapping**

Add `muscle_focus` to `AdminExerciseFilters` and `AdminExerciseCreate`; require compatible focus whenever anatomy is known and require null focus for unknown review anatomy. Persist it in `create_admin_exercise` and `update_admin_exercise`, and filter it in `list_admin_exercises`.

- [ ] **Step 4: Run admin security and API checks**

Run: `cd backend && .venv/bin/pytest tests/admin/test_exercise_api.py tests/auth -q && .venv/bin/ruff check app/admin tests/admin/test_exercise_api.py && .venv/bin/mypy app/admin`

Expected: PASS; non-admin writes remain rejected and trusted-origin protection remains tested.

- [ ] **Step 5: Commit and push**

```bash
git add backend/app/admin/schemas.py backend/app/admin/router.py backend/app/admin/service.py backend/tests/admin/test_exercise_api.py
git commit -m "feat(admin): manage exercise muscle focus"
git push
```

### Task 6: Seeds, Placeholders, and Future Imports

**Files:**
- Modify: `backend/app/exercises/seed_data.py`
- Modify: `backend/app/exercises/seed.py`
- Modify: `backend/app/exercises/service.py`
- Modify: `backend/app/exercises/free_exercise_db_import.py`
- Modify: `backend/app/training_templates/catalog_placeholders.py`
- Modify: `backend/tests/exercises/test_seed.py`
- Modify: `backend/tests/exercises/test_free_exercise_db_import.py`
- Modify: `backend/tests/training_templates/test_catalog_placeholders.py`

**Interfaces:**
- Consumes: classifier and manifest from Task 2.
- Produces: explicit `ExerciseSeed.muscle_focus`, import-candidate focus, `_is_current` focus comparison, and compatible placeholder focus.

- [ ] **Step 1: Write failing seed/import/placeholder tests**

```python
def test_every_seed_has_compatible_focus() -> None:
    assert all(
        is_compatible_muscle_focus(seed.primary_muscle, seed.muscle_focus)
        for seed in EXERCISE_SEEDS
    )


def test_import_uses_source_target_for_upper_chest(importer) -> None:
    candidate = importer.build_candidate(record(target="upper pectorals", name="Incline Press"))
    assert candidate.muscle_focus is MuscleFocus.UPPER_CHEST


def test_import_rejects_unresolved_known_primary(importer) -> None:
    with pytest.raises(UnresolvedMuscleFocusError):
        importer.build_candidate(record(target="pectorals", name="Unknown Press"))
```

- [ ] **Step 2: Run focused tests and confirm RED**

Run: `cd backend && .venv/bin/pytest tests/exercises/test_seed.py tests/exercises/test_free_exercise_db_import.py tests/training_templates/test_catalog_placeholders.py -q`

Expected: new focus assertions FAIL.

- [ ] **Step 3: Add explicit focus to curated records and placeholders**

Extend `ExerciseSeed` and `_exercise(...)` with `muscle_focus: MuscleFocus`; assign every curated seed explicitly and copy it in `_apply_seed_fields`. For template placeholders, derive a deterministic compatible focus from the slot's primary muscle and movement pattern through a dedicated explicit mapping; raise on an unmapped slot.

- [ ] **Step 4: Integrate the classifier into import candidate construction and idempotency**

```python
classification = classify_muscle_focus(
    primary_muscle=primary_muscle,
    source_target=source_target,
    secondary_targets=secondary_targets,
    name_en=name_en,
    movement_pattern=movement_pattern,
    exercise_type=exercise_type,
    instructions_en=translation.instructions_en,
)
if primary_muscle is not None and classification is None:
    raise UnresolvedMuscleFocusError(source_id=source_id, name_en=name_en)
muscle_focus = classification.focus if classification is not None else None
```

Include `muscle_focus` in `ImportCandidate`, `_is_current`, create, and update paths. Preserve null focus for null-primary imports.

- [ ] **Step 5: Run idempotency and catalogue seed checks**

Run: `cd backend && .venv/bin/pytest tests/exercises/test_seed.py tests/exercises/test_free_exercise_db_import.py tests/training_templates/test_catalog_placeholders.py -q`

Expected: PASS, including a second import/seed run with zero unintended updates.

- [ ] **Step 6: Commit and push**

```bash
git add backend/app/exercises/seed_data.py backend/app/exercises/seed.py backend/app/exercises/service.py backend/app/exercises/free_exercise_db_import.py backend/app/training_templates/catalog_placeholders.py backend/tests/exercises/test_seed.py backend/tests/exercises/test_free_exercise_db_import.py backend/tests/training_templates/test_catalog_placeholders.py
git commit -m "feat(exercises): assign focus during catalogue imports"
git push
```

### Task 7: Frontend Types, API, and URL Context

**Files:**
- Modify: `frontend/src/features/exercises/types.ts`
- Modify: `frontend/src/features/exercises/api.ts`
- Modify: `frontend/src/features/exercises/api.test.ts`
- Modify: `frontend/src/features/admin/types.ts`
- Modify: `frontend/src/features/admin/exerciseLibraryNavigation.ts`
- Modify: `frontend/src/features/admin/exerciseLibraryNavigation.test.ts`

**Interfaces:**
- Produces: `MuscleFocus`, `muscleFocuses`, focus category types, `ExerciseFilters.muscle_focus`, and navigation preservation of `muscle_focus`.
- Consumes: backend string values defined in Task 1.

- [ ] **Step 1: Write failing API-query and return-context tests**

```typescript
it("sends a selected muscle focus", async () => {
  await getExercises({ primary_muscle: "chest", muscle_focus: "upper_chest" });
  expect(fetch).toHaveBeenCalledWith(
    "/api/v1/exercises?primary_muscle=chest&muscle_focus=upper_chest",
    expect.anything(),
  );
});

it("preserves muscle focus in admin return context", () => {
  expect(exerciseLibraryReturnPath(
    "/exercises?body_region=upper_body&primary_muscle=chest&muscle_focus=upper_chest&search=press",
    "upper_body", "chest", true, false,
  )).toContain("muscle_focus=upper_chest");
});
```

- [ ] **Step 2: Run focused frontend tests and confirm RED**

Run: `cd frontend && npm test -- src/features/exercises/api.test.ts src/features/admin/exerciseLibraryNavigation.test.ts`

Expected: TypeScript/test failure because focus types/context do not exist.

- [ ] **Step 3: Add exact enum unions and API/category contracts**

```typescript
export const muscleFocuses = [
  "general_chest", "upper_chest", "mid_chest", "lower_chest",
  "general_back", "lats", "mid_back_rhomboids", "upper_back",
  "general_shoulders", "front_delt", "lateral_delt", "rear_delt",
  "general_biceps", "biceps_brachii", "brachialis_brachioradialis",
  "general_triceps", "triceps_long_head", "triceps_lateral_medial_heads",
  "upper_traps", "mid_lower_traps",
  "general_forearms", "forearm_flexors", "forearm_extensors",
  "neck_flexion", "neck_lateral_extension",
  "glute_max", "glute_medius_minimus",
  "general_quadriceps", "rectus_femoris", "vasti",
  "hamstrings_hip_extension", "hamstrings_knee_flexion",
  "hip_adduction", "adductor_mobility",
  "general_calves", "gastrocnemius", "soleus",
  "trunk_flexion", "hip_flexion_posterior_tilt", "anti_extension",
  "trunk_rotation", "lateral_flexion", "anti_rotation",
  "lumbar_erectors", "thoracic_mobility",
] as const;
export type MuscleFocus = (typeof muscleFocuses)[number];

export type MuscleFocusCategory = {
  value: MuscleFocus;
  name_en: string;
  name_fa: string;
};
```

Add `muscle_focus` to summaries, filters, admin detail/form types, and `ExerciseCategories.muscle_focuses`. Add it to the safe allowlist in library return navigation.

- [ ] **Step 4: Run type-facing tests and production type build**

Run: `cd frontend && npm test -- src/features/exercises/api.test.ts src/features/admin/exerciseLibraryNavigation.test.ts && npm run build`

Expected: PASS.

- [ ] **Step 5: Commit and push**

```bash
git add frontend/src/features/exercises/types.ts frontend/src/features/exercises/api.ts frontend/src/features/exercises/api.test.ts frontend/src/features/admin/types.ts frontend/src/features/admin/exerciseLibraryNavigation.ts frontend/src/features/admin/exerciseLibraryNavigation.test.ts
git commit -m "feat(exercises): add muscle focus client contracts"
git push
```

### Task 8: Exercise Library Third-Level Selector

**Files:**
- Modify: `frontend/src/features/exercises/ExerciseCatalogPage.tsx`
- Modify: `frontend/src/features/exercises/ExerciseCatalogPage.test.tsx`
- Modify: `frontend/src/features/exercises/ExerciseDetailPage.tsx`
- Modify: `frontend/src/features/exercises/ExerciseDetailPage.test.tsx`
- Modify: `frontend/src/features/exercises/exercises.css`
- Modify: `frontend/src/i18n/en.ts`
- Modify: `frontend/src/i18n/fa.ts`

**Interfaces:**
- Consumes: `ExerciseCategories.muscle_focuses`, `ExerciseFilters.muscle_focus`.
- Produces: query-aware third selector, `All` omission, breadcrumb/detail return preservation, and localized labels.

- [ ] **Step 1: Write failing selector and backward-compatibility tests**

```typescript
it("shows All plus compatible chest focuses after selecting chest", async () => {
  renderCatalog("/exercises?body_region=upper_body&primary_muscle=chest");
  expect(await screen.findByRole("button", { name: "All" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Upper Chest" })).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Rear Delt" })).not.toBeInTheDocument();
});

it("All omits muscle_focus and preserves existing filters", async () => {
  renderCatalog("/exercises?body_region=upper_body&primary_muscle=chest&muscle_focus=upper_chest&search=press&page=3");
  await user.click(await screen.findByRole("button", { name: "All" }));
  expect(currentLocation()).toBe(
    "/exercises?body_region=upper_body&primary_muscle=chest&search=press"
  );
});

it("changing muscle clears stale focus and resets pagination", async () => {
  renderCatalog("/exercises?body_region=upper_body&primary_muscle=chest&muscle_focus=upper_chest&page=3");
  await user.click(await screen.findByRole("button", { name: "Back" }));
  expect(currentLocation()).toBe(
    "/exercises?body_region=upper_body&primary_muscle=back"
  );
});
```

- [ ] **Step 2: Run catalogue/detail tests and confirm RED**

Run: `cd frontend && npm test -- src/features/exercises/ExerciseCatalogPage.test.tsx src/features/exercises/ExerciseDetailPage.test.tsx`

Expected: focus selector assertions FAIL.

- [ ] **Step 3: Extend query parsing/writing and request construction**

Add `muscle_focus?: MuscleFocus` to the local query type; accept only values from `muscleFocuses`; pass it only when compatible with the selected muscle's returned categories. Clear focus on region/muscle/special-category changes and reset page on focus changes.

- [ ] **Step 4: Render the third selector and breadcrumb**

Render one `All` control and returned focus categories after a muscle is selected. `All` calls `writeQuery({ muscle_focus: undefined })`; specific controls write the enum value. Add the localized focus to the results heading, exercise-card anatomy line, detail-page anatomy list, breadcrumb, and detail-return URLs.

- [ ] **Step 5: Add English/Persian translations and responsive styling**

Add `catalog.focusTitle`, `catalog.focusAll`, and every focus label in both locale files. Style the focus control using the existing selector visual language and verify wrapping at 360px in RTL and LTR without altering normal-user controls.

- [ ] **Step 6: Run catalogue UI, i18n, lint, and build checks**

Run: `cd frontend && npm test -- src/features/exercises/ExerciseCatalogPage.test.tsx src/features/exercises/ExerciseDetailPage.test.tsx src/i18n && npm run lint && npm run build`

Expected: PASS.

- [ ] **Step 7: Commit and push**

```bash
git add frontend/src/features/exercises/ExerciseCatalogPage.tsx frontend/src/features/exercises/ExerciseCatalogPage.test.tsx frontend/src/features/exercises/ExerciseDetailPage.tsx frontend/src/features/exercises/ExerciseDetailPage.test.tsx frontend/src/features/exercises/exercises.css frontend/src/i18n/en.ts frontend/src/i18n/fa.ts
git commit -m "feat(exercises): browse catalogue by muscle focus"
git push
```

### Task 9: Admin Focus Form and Library Context

**Files:**
- Modify: `frontend/src/features/admin/validation.ts`
- Modify: `frontend/src/features/admin/validation.test.ts`
- Modify: `frontend/src/features/admin/AdminExerciseFields.tsx`
- Modify: `frontend/src/features/admin/AdminExerciseNewPage.tsx`
- Modify: `frontend/src/features/admin/AdminExerciseNewPage.test.tsx`
- Modify: `frontend/src/features/admin/AdminExerciseEditPage.tsx`
- Modify: `frontend/src/features/admin/AdminExerciseEditPage.test.tsx`

**Interfaces:**
- Consumes: categories focus mapping and admin `muscle_focus` type.
- Produces: compatible editable focus field and preservation after create/edit return.

- [ ] **Step 1: Write failing form prefill, validation, and return tests**

```typescript
it("prefills focus from the exercise library context", async () => {
  renderNew("/admin/exercises/new?body_region=upper_body&primary_muscle=chest&muscle_focus=upper_chest");
  expect(await screen.findByLabelText("Muscle focus")).toHaveValue("upper_chest");
});

it("clears an incompatible focus when primary muscle changes", async () => {
  renderNew("/admin/exercises/new?body_region=upper_body&primary_muscle=chest&muscle_focus=upper_chest");
  await user.selectOptions(await screen.findByLabelText("Primary muscle"), "shoulders");
  expect(screen.getByLabelText("Muscle focus")).toHaveValue("");
  await user.click(screen.getByRole("button", { name: "Save exercise" }));
  expect(await screen.findByText("Muscle focus is required")).toBeInTheDocument();
});

it("returns to the preserved focus after editing", async () => {
  renderEdit("/admin/exercises/exercise-id?return_to=%2Fexercises%3Fbody_region%3Dupper_body%26primary_muscle%3Dchest%26muscle_focus%3Dupper_chest%26search%3Dpress%26page%3D3");
  await user.click(await screen.findByRole("button", { name: "Save changes" }));
  expect(currentLocation()).toBe(
    "/exercises?body_region=upper_body&primary_muscle=chest&muscle_focus=upper_chest&search=press"
  );
});
```

- [ ] **Step 2: Run focused admin UI tests and confirm RED**

Run: `cd frontend && npm test -- src/features/admin/validation.test.ts src/features/admin/AdminExerciseNewPage.test.tsx src/features/admin/AdminExerciseEditPage.test.tsx`

Expected: new focus assertions FAIL.

- [ ] **Step 3: Add form state, compatibility validation, and serialized payload**

Require focus when `primary_muscle` is present, require it empty when primary muscle is absent, and validate membership in `categories.muscle_focuses[primary_muscle]`. Include the field in `emptyExerciseForm`, detail-to-form mapping, and multipart JSON payload.

- [ ] **Step 4: Add the dependent focus selector and context prefill**

Place the selector next to existing anatomy fields. Its options come only from the selected primary muscle; changing region/muscle clears stale focus. Read and validate `muscle_focus` from create navigation context and preserve it in post-create/edit return paths.

- [ ] **Step 5: Run admin UI regression, lint, and build**

Run: `cd frontend && npm test -- src/features/admin/validation.test.ts src/features/admin/AdminExerciseNewPage.test.tsx src/features/admin/AdminExerciseEditPage.test.tsx src/features/exercises/ExerciseCatalogPage.test.tsx && npm run lint && npm run build`

Expected: PASS, including all existing full-field edit behavior.

- [ ] **Step 6: Commit and push**

```bash
git add frontend/src/features/admin/validation.ts frontend/src/features/admin/validation.test.ts frontend/src/features/admin/AdminExerciseFields.tsx frontend/src/features/admin/AdminExerciseNewPage.tsx frontend/src/features/admin/AdminExerciseNewPage.test.tsx frontend/src/features/admin/AdminExerciseEditPage.tsx frontend/src/features/admin/AdminExerciseEditPage.test.tsx
git commit -m "feat(admin): edit exercise muscle focus"
git push
```

### Task 10: Complete Verification and Runtime Catalogue Audit

**Files:**
- Modify only if a verification failure identifies an in-scope defect.

**Interfaces:**
- Consumes: all prior tasks.
- Produces: verified migration/runtime state and catalogue invariants.

- [ ] **Step 1: Run the full backend quality gate**

Run: `cd backend && .venv/bin/pytest -q`

Run: `cd backend && .venv/bin/ruff check app tests alembic`

Run: `cd backend && .venv/bin/mypy app`

Expected: all PASS.

- [ ] **Step 2: Run the full frontend quality gate**

Run: `cd frontend && npm test`

Run: `cd frontend && npm run lint && npm run build`

Expected: all PASS.

- [ ] **Step 3: Verify live migration and exact catalogue invariants**

Run: `docker compose exec -T backend alembic upgrade head && docker compose exec -T backend alembic current`

Run: `docker compose exec -T backend python -m app.exercises.audit_muscle_focus --format summary`

Expected: revision `20260814_78 (head)`; total exercise count unchanged; all known-primary exercises classified compatibly; all null-primary exercises retain null focus; zero unresolved records.

- [ ] **Step 4: Verify representative public and protected API behavior**

Check authenticated requests for:

```text
/api/v1/exercises?primary_muscle=chest
/api/v1/exercises?primary_muscle=chest&muscle_focus=upper_chest
/api/v1/exercises?primary_muscle=shoulders&muscle_focus=lateral_delt
/api/v1/admin/exercises?muscle_focus=rear_delt&is_active=false
/api/v1/admin/exercises?needs_review=true
```

Expected: `All` total equals the pre-migration muscle total; focused responses contain only the requested compatible focus; admin-only inactive/review data is available only through the protected route.

- [ ] **Step 5: Verify mobile library flow**

At 360px in Persian RTL and English LTR, verify region -> muscle -> focus -> exercise, `All`, search/filter/pagination preservation, detail back-navigation, admin add/edit prefill, and post-save return.

Expected: no clipping or hidden actions; normal users see no admin controls; admin controls remain readable.

- [ ] **Step 6: Commit any verification-only corrections and push**

If no correction was required, do not create an empty commit. If corrections were required:

```bash
git add backend/app/exercises frontend/src/features/exercises frontend/src/features/admin
git commit -m "fix(exercises): correct muscle focus integration"
git push
```

- [ ] **Step 7: Report final evidence**

Report only the final revision, exact test/check results, exact catalogue totals/invariants, pushed commit range, and the mobile URLs the user should test.
