# Owner Video Importer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a safe, resumable CLI that mutes and analyzes owner MP4 exercise videos, then attaches them to confirmed catalogue exercises or creates validated new/review exercises.

**Architecture:** Extend `ExerciseMediaAsset` with stable owner provenance and keep accepted files in Fitsho's existing public media tree. Split media processing, Codex structured analysis, and database orchestration into focused modules; inject command runners and analyzers for deterministic tests. Process one digest-keyed video transaction at a time so reruns and interruptions are safe.

**Tech Stack:** Python 3.12, Pydantic 2, SQLAlchemy 2, PostgreSQL, Alembic, ffmpeg/ffprobe, Codex CLI, pytest.

## Global Constraints

- Work on `main` and preserve all unrelated uncommitted files.
- Never modify, rename, or delete files below `exercise-import/raw/`.
- Do not run the importer against all 272 owner videos during implementation or tests.
- Run backend commands from `backend/` so `backend/.env` is used.
- Use SHA-256 of the original MP4 as `ExerciseMediaAsset.source_id` with `source="owner-video"`.
- Never attach an uncertain match to an existing exercise.
- Validate Codex JSON and catalogue references before any database write.
- `--dry-run` may write only its explicit report and gitignored resumable cache, never the database or accepted `var/media` tree.
- Each task follows red-green-refactor and ends with a focused Conventional Commit.
- Before migration work, confirm `20260814_79` is the single Alembic head; do not edit migration 79 or the user's current taxonomy work.

---

## File map

- Modify `backend/app/exercises/enums.py`: add `MediaPresentation.UNSPECIFIED`.
- Modify `backend/app/exercises/models.py`: add nullable asset provenance and uniqueness.
- Create `backend/alembic/versions/20260814_80_add_owner_video_media_provenance.py`: migrate provenance and presentation constraint.
- Create `backend/tests/database/test_owner_video_media_migration.py`: prove upgrade, uniqueness, and downgrade.
- Modify `backend/app/config.py`: add ffmpeg, Codex CLI, work-root, timeout, and confidence settings.
- Modify `.env.example`: document optional owner importer overrides without secrets.
- Modify `.gitignore`: ignore only `backend/var/imports/owner-video/`.
- Create `backend/app/exercises/owner_video_media.py`: hash, probe, mute, frame, cache-path, and accepted-media publication functions.
- Create `backend/tests/exercises/test_owner_video_media.py`: real ffmpeg/ffprobe media tests and command failure tests.
- Create `backend/app/exercises/owner_video_analysis.py`: strict Pydantic contract, catalogue snapshot, Codex command, cache, and deterministic match validation.
- Create `backend/tests/exercises/test_owner_video_analysis.py`: schema, invocation, cache, enum, digest, presentation, and match tests.
- Create `backend/app/exercises/owner_video_import.py`: discovery, reporting, dry-run/apply orchestration, database writes, cleanup, and CLI.
- Create `backend/tests/exercises/test_owner_video_import.py`: database, idempotency, sort order, review, rollback, report, and CLI tests.
- Modify `AGENTS.md`: add exact owner importer commands after behavior is verified.

---

### Task 1: Media provenance schema

**Files:**
- Modify: `backend/app/exercises/enums.py`
- Modify: `backend/app/exercises/models.py`
- Create: `backend/alembic/versions/20260814_80_add_owner_video_media_provenance.py`
- Create: `backend/tests/database/test_owner_video_media_migration.py`
- Modify: `backend/tests/database/test_exercise_models.py`

**Interfaces:**
- Produces: `MediaPresentation.UNSPECIFIED`.
- Produces: `ExerciseMediaAsset.source: str | None` and `source_id: str | None`.
- Produces: unique database identity `(source, source_id)` named `uq_exercise_media_assets_source_source_id`.

- [ ] **Step 1: Confirm the migration base**

Run:

```bash
cd backend
uv run alembic heads
```

Expected: exactly `20260814_79 (head)`. Stop if another head appears.

- [ ] **Step 2: Write failing model and migration tests**

Add a model test that persists an owner asset and rejects the same source identity on another row:

```python
def test_exercise_media_asset_stores_unique_owner_provenance(db: Session) -> None:
    first = make_exercise("owner-video-first")
    second = make_exercise("owner-video-second")
    first.media_assets.append(
        ExerciseMediaAsset(
            presentation=MediaPresentation.UNSPECIFIED,
            role=MediaRole.VIDEO,
            sort_order=0,
            media_path="/media/owner-video/aa/abc.mp4",
            media_type=MediaType.VIDEO,
            source="owner-video",
            source_id="a" * 64,
        )
    )
    second.media_assets.append(
        ExerciseMediaAsset(
            presentation=MediaPresentation.UNSPECIFIED,
            role=MediaRole.VIDEO,
            sort_order=0,
            media_path="/media/owner-video/aa/duplicate.mp4",
            media_type=MediaType.VIDEO,
            source="owner-video",
            source_id="a" * 64,
        )
    )
    db.add(first)
    db.flush()
    db.add(second)
    with pytest.raises(IntegrityError):
        db.flush()
```

The migration test must downgrade to `20260814_79`, insert a legacy asset, upgrade to
`20260814_80`, assert the new columns are nullable and `unspecified` is accepted, then downgrade
and verify the legacy row remains.

- [ ] **Step 3: Run tests to verify RED**

Run:

```bash
cd backend
uv run pytest tests/database/test_exercise_models.py::test_exercise_media_asset_stores_unique_owner_provenance tests/database/test_owner_video_media_migration.py -q
```

Expected: FAIL because `UNSPECIFIED`, provenance columns, and revision 80 do not exist.

- [ ] **Step 4: Implement the enum, model columns, and migration**

Add:

```python
class MediaPresentation(StrEnum):
    MALE = "male"
    FEMALE = "female"
    UNSPECIFIED = "unspecified"
```

Extend `ExerciseMediaAsset.__table_args__` with:

```python
UniqueConstraint("source", "source_id", name="uq_exercise_media_assets_source_source_id")
```

Add model columns:

```python
source: Mapped[str | None] = mapped_column(String(80), nullable=True)
source_id: Mapped[str | None] = mapped_column(String(160), nullable=True)
```

Revision `20260814_80` uses `down_revision = "20260814_79"`. Its upgrade drops and recreates
`ck_exercise_media_assets_presentation_values` with `male`, `female`, and `unspecified`, adds both
nullable columns, and adds the unique constraint. Its downgrade drops the constraint and columns,
reassigns each `unspecified` row to `male` with the next collision-free `sort_order` for its
exercise and role, then restores the old two-value check constraint. The migration test must
include existing male order 0 and unspecified order 0 rows and prove downgrade preserves both.

- [ ] **Step 5: Verify GREEN and migration round-trip**

Run:

```bash
cd backend
uv run pytest tests/database/test_exercise_models.py::test_exercise_media_asset_stores_unique_owner_provenance tests/database/test_owner_video_media_migration.py -q
uv run alembic downgrade 20260814_79
uv run alembic upgrade head
uv run alembic current
```

Expected: tests PASS and current revision is `20260814_80`.

- [ ] **Step 6: Commit**

```bash
git add backend/app/exercises/enums.py backend/app/exercises/models.py backend/alembic/versions/20260814_80_add_owner_video_media_provenance.py backend/tests/database/test_exercise_models.py backend/tests/database/test_owner_video_media_migration.py
git commit -m "feat(exercises): add owner video media provenance"
```

---

### Task 2: Safe video preparation

**Files:**
- Modify: `backend/app/config.py`
- Modify: `.env.example`
- Modify: `.gitignore`
- Create: `backend/app/exercises/owner_video_media.py`
- Create: `backend/tests/exercises/test_owner_video_media.py`

**Interfaces:**
- Produces: `VideoProbe(duration_seconds: float, video_streams: int, audio_streams: int)`.
- Produces: `PreparedOwnerVideo(source_path, source_id, muted_path, frame_paths, duration_seconds)`.
- Produces: `prepare_owner_video(source_path: Path, *, settings: Settings, runner: CommandRunner = subprocess.run) -> PreparedOwnerVideo`.
- Produces: `publish_owner_video(prepared: PreparedOwnerVideo, *, settings: Settings) -> PublishedOwnerVideo` where `created` records whether rollback may remove the file.

- [ ] **Step 1: Write failing media tests with a real AV fixture**

Create a one-second fixture entirely under `tmp_path`:

```python
subprocess.run(
    [
        "ffmpeg", "-y", "-f", "lavfi", "-i", "testsrc=size=320x240:rate=15",
        "-f", "lavfi", "-i", "sine=frequency=1000", "-t", "1",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", str(source),
    ],
    check=True,
    capture_output=True,
)
```

Assert:

```python
before = source.read_bytes()
prepared = prepare_owner_video(source, settings=test_settings)
after = source.read_bytes()
assert after == before
assert prepared.source_id == hashlib.sha256(before).hexdigest()
assert len(prepared.frame_paths) == 5
assert probe_video(prepared.muted_path, settings=test_settings).audio_streams == 0
assert probe_video(prepared.muted_path, settings=test_settings).video_streams == 1
```

Add focused tests for invalid ffprobe JSON, missing video streams, stream-copy failure followed by
H.264 fallback, total ffmpeg failure, stable accepted path, and reuse of a valid existing accepted
file.

- [ ] **Step 2: Run media tests to verify RED**

Run:

```bash
cd backend
uv run pytest tests/exercises/test_owner_video_media.py -q
```

Expected: FAIL because `owner_video_media` does not exist.

- [ ] **Step 3: Add conservative settings and exact ignore rule**

Add to `Settings`:

```python
ffmpeg_path: str = "ffmpeg"
ffmpeg_timeout_seconds: float = Field(default=60.0, gt=0, le=300)
owner_video_import_work_root: Path = Path("var/imports/owner-video")
owner_video_codex_path: str = "codex"
owner_video_codex_model: str | None = None
owner_video_codex_timeout_seconds: float = Field(default=180.0, gt=0, le=600)
owner_video_identification_confidence: float = Field(default=0.90, ge=0, le=1)
owner_video_match_confidence: float = Field(default=0.92, ge=0, le=1)
owner_video_presentation_confidence: float = Field(default=0.80, ge=0, le=1)
```

Document the uppercase environment names in `.env.example` and add only this ignore entry:

```gitignore
backend/var/imports/owner-video/
```

- [ ] **Step 4: Implement hash, probe, mute, frame extraction, and publication**

`probe_video` runs ffprobe with `-show_streams -show_format -of json`, parses duration, and counts
`codec_type` values. `prepare_owner_video` rejects empty/oversized inputs, creates
`<work-root>/<digest>/muted.mp4`, tries this first:

```python
[ffmpeg, "-y", "-i", source, "-map", "0:v:0", "-c:v", "copy", "-an", "-movflags", "+faststart", staged]
```

and falls back to:

```python
[ffmpeg, "-y", "-i", source, "-map", "0:v:0", "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p", "-an", "-movflags", "+faststart", staged]
```

Create each frame with `-ss`, `-frames:v 1`, and `-q:v 2`; use timestamps at 10, 30, 50, 70,
and 90 percent. Validate the muted result before replacing the stable work file. Publish through a
temporary sibling and `os.replace` to
`media_root / "owner-video" / digest[:2] / f"{digest}.mp4"`.

- [ ] **Step 5: Verify GREEN**

Run:

```bash
cd backend
uv run pytest tests/exercises/test_owner_video_media.py -q
uv run ruff check app/exercises/owner_video_media.py tests/exercises/test_owner_video_media.py app/config.py
uv run mypy app/exercises/owner_video_media.py app/config.py
```

Expected: all commands exit 0.

- [ ] **Step 6: Commit**

```bash
git add .gitignore .env.example backend/app/config.py backend/app/exercises/owner_video_media.py backend/tests/exercises/test_owner_video_media.py
git commit -m "feat(exercises): prepare muted owner videos safely"
```

---

### Task 3: Structured Codex analysis

**Files:**
- Create: `backend/app/exercises/owner_video_analysis.py`
- Create: `backend/tests/exercises/test_owner_video_analysis.py`

**Interfaces:**
- Consumes: `PreparedOwnerVideo` and owner confidence settings from Task 2.
- Produces: `OwnerVideoAnalysis`, a strict Pydantic model with `extra="forbid"`.
- Produces: `CatalogueExercise` and `build_catalogue_snapshot(db: Session) -> tuple[CatalogueExercise, ...]`.
- Produces: `CodexCliExerciseAnalyzer.analyze(prepared, catalogue) -> OwnerVideoAnalysis`.
- Produces: `resolve_existing_match(analysis, catalogue, settings) -> UUID | None`.

- [ ] **Step 1: Write failing structured-contract tests**

Build a complete `valid_analysis()` fixture and assert that Pydantic rejects an unknown enum, an
extra field, fewer than three instruction steps, unequal Persian/English instruction counts, and
an invalid digest. Assert the contextual analysis validator rejects an existing UUID absent from
the supplied catalogue.

The match acceptance test must require all of these:

```python
assert analysis.decision == "match_existing"
assert analysis.identification_confidence >= settings.owner_video_identification_confidence
assert analysis.match_confidence >= settings.owner_video_match_confidence
assert normalized_name_or_alias_matches is True
assert analysis.primary_muscle == candidate.primary_muscle
assert analysis.movement_pattern == candidate.movement_pattern
assert set(analysis.equipment) & set(candidate.equipment)
```

Test that any missing condition returns `None`, causing review rather than a guessed match. Test
that presentation confidence below 0.80 resolves to `MediaPresentation.UNSPECIFIED`.

- [ ] **Step 2: Write failing Codex invocation and cache tests**

Inject a fake runner, call `analyze`, and assert the command contains:

```python
assert command[:2] == [settings.owner_video_codex_path, "exec"]
assert command.count("--image") == 5
assert "--output-schema" in command
assert "--output-last-message" in command
assert "--ephemeral" in command
assert command[command.index("--sandbox") + 1] == "read-only"
```

Assert the prompt includes the source digest, allowed enum values, and compact catalogue JSON but
no database URL. Add cache tests proving a valid matching schema/prompt version avoids a second
runner call and an invalid/stale cache triggers a new call.

- [ ] **Step 3: Run analysis tests to verify RED**

Run:

```bash
cd backend
uv run pytest tests/exercises/test_owner_video_analysis.py -q
```

Expected: FAIL because `owner_video_analysis` does not exist.

- [ ] **Step 4: Implement strict models, schema, snapshot, invocation, and cache**

Use these top-level decisions:

```python
AnalysisDecision = Literal["match_existing", "create_new", "needs_review"]
ANALYSIS_SCHEMA_VERSION = "owner-video-analysis-v1"
ANALYSIS_PROMPT_VERSION = "owner-video-prompt-v1"
```

`OwnerVideoAnalysis` includes digest, bilingual names, visible text, aliases, body region, primary
and secondary muscles, focus, equipment, difficulty, movement pattern, exercise type, bilingual
instructions and safety notes, descriptions, cues, mistakes, breathing, caution tags,
presentation and its confidence, identification and match confidence, decision, optional existing
UUID, and review reasons.

Write `OwnerVideoAnalysis.model_json_schema()` to a digest-keyed schema file. Invoke Codex with
`-C <digest-work-dir>`, `--skip-git-repo-check`, five image arguments, schema/output paths,
`--ephemeral`, and `--sandbox read-only`. Include `--model` only when configured. Parse only the
last-message file, verify the digest, then atomically cache the validated model dump with both
version constants.

- [ ] **Step 5: Verify GREEN**

Run:

```bash
cd backend
uv run pytest tests/exercises/test_owner_video_analysis.py -q
uv run ruff check app/exercises/owner_video_analysis.py tests/exercises/test_owner_video_analysis.py
uv run mypy app/exercises/owner_video_analysis.py
```

Expected: all commands exit 0.

- [ ] **Step 6: Commit**

```bash
git add backend/app/exercises/owner_video_analysis.py backend/tests/exercises/test_owner_video_analysis.py
git commit -m "feat(exercises): analyze owner videos with Codex"
```

---

### Task 4: Database import behavior

**Files:**
- Create: `backend/app/exercises/owner_video_import.py`
- Create: `backend/tests/exercises/test_owner_video_import.py`

**Interfaces:**
- Consumes: media preparation/publication and `OwnerVideoAnalysis` from Tasks 2 and 3.
- Produces: `OwnerVideoImporter.run(*, limit: int | None, apply: bool) -> OwnerVideoImportReport`.
- Produces: `OwnerVideoImportReport` with required counters and `items: list[OwnerVideoImportItem]`.

- [ ] **Step 1: Write failing duplicate and idempotency tests**

Use generated tiny MP4 fixtures and a fake analyzer. Preinsert an asset with source `owner-video`
and its digest, then assert:

```python
assert report.duplicate_videos == 1
assert analyzer.calls == []
assert count_owner_assets(db, digest) == 1
```

Run the apply importer twice for a confirmed new exercise and assert one exercise, one media asset,
one accepted file, and `duplicate_videos == 1` on the second report.

- [ ] **Step 2: Write failing existing-match and sort-order tests**

Create an existing exercise with male video orders 0 and 1. Return a confirmed male analysis that
passes deterministic corroboration. Assert no new exercise is created and the owner asset has
`sort_order == 2`. Repeat with `female` and `unspecified` to prove ordering is scoped by exercise,
presentation, and role.

- [ ] **Step 3: Write failing new and review exercise tests**

For `create_new`, assert complete bilingual metadata and normalized associations are stored,
`needs_review is False`, `is_programmable is True`, `source == "owner-video"`, and both normalized
and legacy primary media fields point to the muted file.

For low identification confidence or rejected matching evidence, assert a new exercise is created
with:

```python
assert exercise.needs_review is True
assert exercise.is_programmable is False
assert exercise.source_metadata_en["owner_video_analysis"]["review_reasons"]
assert report.needs_review == 1
```

Also assert the uncertain asset is never attached to the proposed existing UUID.

- [ ] **Step 4: Write failing rollback and per-file isolation tests**

Inject a persistence callback that raises after media publication but before commit. Assert the
database has no new rows and the newly created accepted file is absent. Add two inputs where the
first analyzer fails and the second succeeds; assert `failed == 1`, `created_new == 1`, and only the
second digest exists in the database.

- [ ] **Step 5: Run importer tests to verify RED**

Run:

```bash
cd backend
uv run pytest tests/exercises/test_owner_video_import.py -q
```

Expected: FAIL because `OwnerVideoImporter` does not exist.

- [ ] **Step 6: Implement per-file orchestration and persistence**

Discover only regular `.mp4` files, case-insensitively, in stable filename order. Define report
semantics as:

```python
total = number_of_all_discovered_mp4_files
processed = number_of_selected_files_examined_in_this_run
needs_review = subset_of_created_new_requiring_review
```

Before media work, query the unique provenance identity. For accepted existing matches, lock the
exercise row with `SELECT ... FOR UPDATE`, load its media assets, calculate the next scoped order,
and append without changing existing or legacy primary media.

For new/review rows, generate a stable slug beginning `owner-<digest[:12]>-`, populate every
required `Exercise` field and normalized association, mirror the first video into legacy media,
and persist the complete validated analysis in `source_metadata_en`.

Publish immediately before flush/commit. Track `PublishedOwnerVideo.created`; on any exception,
roll back and unlink only files created by that item. Convert expected item failures into report
details and continue.

- [ ] **Step 7: Verify GREEN**

Run:

```bash
cd backend
uv run pytest tests/exercises/test_owner_video_import.py -q
uv run ruff check app/exercises/owner_video_import.py tests/exercises/test_owner_video_import.py
uv run mypy app/exercises/owner_video_import.py
```

Expected: all commands exit 0.

- [ ] **Step 8: Commit**

```bash
git add backend/app/exercises/owner_video_import.py backend/tests/exercises/test_owner_video_import.py
git commit -m "feat(exercises): import owner videos idempotently"
```

---

### Task 5: CLI, report, and interruption contract

**Files:**
- Modify: `backend/app/exercises/owner_video_import.py`
- Modify: `backend/tests/exercises/test_owner_video_import.py`
- Modify: `AGENTS.md`

**Interfaces:**
- Produces: `python -m app.exercises.owner_video_import` with mutually exclusive `--dry-run` and `--apply`.
- Produces: atomic JSON report with `total`, `processed`, `matched_existing`, `created_new`, `duplicate_videos`, `needs_review`, and `failed`.

- [ ] **Step 1: Write failing CLI/report tests**

Call `main()` with injected settings/session/analyzer factories. Assert neither mode, both modes,
non-positive limits, and a missing `--report` exit with parser error. Assert `--limit 2` examines
the first two stable filenames while `total` still reports all discovered files.

Assert report JSON has exactly the seven required top-level counters plus `items`, includes digest,
status, review/failure reason, exercise UUID, and media path per item, and contains no database URL,
Codex configuration, or environment secrets.

Force report replacement failure and prove the previous report remains intact. Prove dry-run calls
analysis and writes cache/report but leaves database and `settings.media_root` unchanged.

- [ ] **Step 2: Run focused tests to verify RED**

Run:

```bash
cd backend
uv run pytest tests/exercises/test_owner_video_import.py -k "cli or report or dry_run or limit" -q
```

Expected: FAIL because the final parser and atomic report contract are incomplete.

- [ ] **Step 3: Implement parser, atomic report, and documented commands**

Use an argparse mutually exclusive required group:

```python
mode = parser.add_mutually_exclusive_group(required=True)
mode.add_argument("--dry-run", action="store_true")
mode.add_argument("--apply", action="store_true")
parser.add_argument("--source-root", type=Path, default=Path("../exercise-import/raw"))
parser.add_argument("--limit", type=positive_int)
parser.add_argument("--report", type=Path, required=True)
```

Write the report to a temporary sibling, flush and `fsync`, then `os.replace`. Add these commands
to `AGENTS.md` only after they are verified:

```bash
python -m app.exercises.owner_video_import --dry-run --source-root ../exercise-import/raw --limit 5 --report var/imports/owner-video/dry-run-5.json
python -m app.exercises.owner_video_import --apply --source-root ../exercise-import/raw --report var/imports/owner-video/full-import.json
```

- [ ] **Step 4: Verify GREEN**

Run:

```bash
cd backend
uv run pytest tests/exercises/test_owner_video_import.py -q
uv run ruff check app/exercises/owner_video_import.py tests/exercises/test_owner_video_import.py
uv run mypy app/exercises/owner_video_import.py
```

Expected: all commands exit 0.

- [ ] **Step 5: Commit**

```bash
git add AGENTS.md backend/app/exercises/owner_video_import.py backend/tests/exercises/test_owner_video_import.py
git commit -m "feat(exercises): add owner video import CLI"
```

---

### Task 6: Full verification without importing owner videos

**Files:**
- Verify only; modify earlier task files only for failures directly caused by this feature.

**Interfaces:**
- Consumes: all prior tasks.
- Produces: fresh evidence that migrations, focused tests, full backend checks, CLI help, and a generated-fixture dry run pass.

- [ ] **Step 1: Run migration and focused verification**

```bash
cd backend
uv run alembic downgrade 20260814_79
uv run alembic upgrade head
uv run alembic current
uv run pytest tests/database/test_owner_video_media_migration.py tests/database/test_exercise_models.py tests/exercises/test_owner_video_media.py tests/exercises/test_owner_video_analysis.py tests/exercises/test_owner_video_import.py -q
```

Expected: current revision `20260814_80`; all focused tests PASS.

- [ ] **Step 2: Run full backend quality checks**

```bash
cd backend
uv run ruff check
uv run mypy app
uv run pytest -q
```

Expected: all commands exit 0. If an unrelated pre-existing failure remains, record its exact test
and output rather than claiming the suite passes.

- [ ] **Step 3: Verify CLI without touching the 272-video source**

Run help and a dry run against a generated one-video fixture under the test workspace, never
against `exercise-import/raw/`:

```bash
cd backend
uv run python -m app.exercises.owner_video_import --help
```

Expected: help lists `--dry-run`, `--apply`, `--source-root`, `--limit`, and required `--report`.
Use the fake analyzer injection path in an integration test for the one-video dry run; do not call
real Codex as part of automated verification.

- [ ] **Step 4: Review changed-file containment and secrets**

```bash
git status --short
git diff --check
git diff --name-only HEAD~5..HEAD
git diff HEAD~5..HEAD -- .env backend/.env
```

Expected: only planned files are in feature commits and no `.env`, key, token, credential, source
video, generated frame, muted video, cache, or report is tracked.

- [ ] **Step 5: Commit any verification-only corrections**

Only when Step 1-4 required an in-scope correction:

```bash
git add .gitignore .env.example AGENTS.md backend/app/config.py backend/app/exercises/enums.py backend/app/exercises/models.py backend/app/exercises/owner_video_media.py backend/app/exercises/owner_video_analysis.py backend/app/exercises/owner_video_import.py backend/alembic/versions/20260814_80_add_owner_video_media_provenance.py backend/tests/database/test_exercise_models.py backend/tests/database/test_owner_video_media_migration.py backend/tests/exercises/test_owner_video_media.py backend/tests/exercises/test_owner_video_analysis.py backend/tests/exercises/test_owner_video_import.py
git commit -m "fix(exercises): correct owner video importer verification"
```

If no correction was needed, create no empty commit.

- [ ] **Step 6: Push `main`**

```bash
git push origin main
```

Expected: the feature commits are present on `origin/main` without force-pushing.
