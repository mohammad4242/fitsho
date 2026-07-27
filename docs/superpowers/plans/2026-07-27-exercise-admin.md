# Exercise Admin Panel Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a secure, bilingual admin-only exercise list and creation form that stores normalized exercises and validated optional media for immediate use in the existing catalog.

**Architecture:** Extend the existing session identity with one `is_admin` capability flag and enforce it in a dedicated FastAPI admin module. List all exercises through an admin GET endpoint and create exercises through one multipart POST endpoint. Validate extension, MIME, signature, size, and `ffprobe` duration before exclusive storage behind `/media`; reuse the current exercise and association tables. Add React admin list/create routes outside profile-completion guards, with domain validation separated from rendering.

**Tech Stack:** Python 3.12, FastAPI, Pydantic 2, SQLAlchemy 2, Alembic, PostgreSQL, React 19, TypeScript 6, React Router 7, i18next, Vitest, Testing Library, Docker Compose.

## Global Constraints

- Start from commit `9f1942724cd67307b3eb4945d66fe0fd166be720` on `feature/exercise-admin`; never modify `main` or `feature/exercise-catalog`.
- Preserve the existing `exercises.id` identity and normalized secondary-muscle, equipment, and alternative tables.
- Reuse the existing controlled enum values exactly.
- Guests receive `401`, authenticated non-admins receive `403`, and admins do not require a completed profile.
- Accept only GIF, MP4, and WebM uploads; derive the stored filename, public path, and media type on the backend.
- Default upload limits are 20 MiB and 20 seconds of video duration.
- Use `/exercises/exercise-placeholder.svg` when no upload is supplied.
- Store runtime media in a backend directory with a persistent Docker volume.
- Keep Persian and English UI copy complete and preserve document-level RTL/LTR behavior.
- Do not implement exercise alternatives, workout plans, AI, nutrition, progress tracking, or an authentication redesign.
- Work test-first, create one final implementation commit named `feat(admin): add exercise management panel`, push after all checks pass, and never stage the unrelated README or Persian architecture-plan changes.

---

## File map

### Backend

- `app/admin/dependencies.py`: reusable administrator authorization.
- `app/admin/exceptions.py`: admin-service domain errors.
- `app/admin/schemas.py`: admin create payload and response contracts.
- `app/admin/service.py`: promotion and transactional exercise creation.
- `app/admin/media.py`: bounded upload, signature detection, generated filenames, cleanup.
- `app/admin/router.py`: multipart HTTP boundary and status mapping.
- `app/admin/grant_admin.py`: email-based promotion CLI.
- `app/exercises/taxonomy.py`: one body-region-to-muscle mapping shared by catalog and admin validation.
- `app/exercises/media_metadata.py`: shared project-owner metadata constants.

### Frontend

- `features/admin/AdminRoute.tsx`: client-side administrator guard.
- `features/admin/types.ts`: form and response types.
- `features/admin/slug.ts`: editable slug-suggestion helper.
- `features/admin/validation.ts`: pure client validation.
- `features/admin/api.ts`: multipart request construction.
- `features/admin/OrderedTextList.tsx`: accessible 3–6 item editor.
- `features/admin/AdminExerciseForm.tsx`: controlled bilingual form.
- `features/admin/AdminExerciseListPage.tsx`: admin list, inactive status, success highlight, and Add action.
- `features/admin/AdminExerciseCreatePage.tsx`: create-page loading, submit, retry, error, and success navigation.
- `features/admin/admin.css`: responsive logical-property styling.

---

### Task 1: Administrator identity and promotion CLI

**Files:**
- Create: `backend/alembic/versions/20260727_04_add_user_admin.py`
- Create: `backend/app/admin/__init__.py`
- Create: `backend/app/admin/exceptions.py`
- Create: `backend/app/admin/service.py`
- Create: `backend/app/admin/grant_admin.py`
- Modify: `backend/app/auth/models.py`
- Modify: `backend/app/auth/schemas.py`
- Modify: `backend/tests/auth/test_register.py`
- Modify: `backend/tests/auth/test_sessions.py`
- Modify: `backend/tests/database/test_auth_models.py`
- Create: `backend/tests/admin/__init__.py`
- Create: `backend/tests/admin/test_grant_admin.py`

**Interfaces:**
- Produces: `User.is_admin: bool`.
- Produces: `UserResponse.is_admin: bool`.
- Produces: `grant_admin(db: Session, email: str) -> User`.
- Produces: `AdminUserNotFoundError`.
- Produces: `python -m app.admin.grant_admin EMAIL`.

- [ ] **Step 1: Write failing identity tests**

Add assertions that a new `User` defaults to non-admin and `/api/v1/auth/me`
returns exactly the minimum public fields plus `is_admin`:

```python
assert stored.is_admin is False
assert set(current.json()) == {"id", "email", "created_at", "is_admin"}
assert current.json()["is_admin"] is False
```

Add a database-default test using a direct SQL insert that omits `is_admin`.
Post a public registration payload containing `"is_admin": true`; assert `422`
and assert no administrator account was created.

- [ ] **Step 2: Write failing promotion tests**

Test normalized lookup, idempotent promotion, and missing-user behavior:

```python
user = User(email="admin@example.com", password_hash="hash")
db.add(user)
db.commit()

assert grant_admin(db, " ADMIN@example.com ").is_admin is True
assert grant_admin(db, "admin@example.com").is_admin is True
with pytest.raises(AdminUserNotFoundError):
    grant_admin(db, "missing@example.com")
```

Test `main(["admin@example.com"]) == 0` and a missing user returns a non-zero
exit code without creating an account.

- [ ] **Step 3: Run the new tests and confirm RED**

Run:

```bash
cd backend
TEST_DATABASE_URL=postgresql+psycopg://fitsho:fitsho@localhost:5432/fitsho_test .venv/bin/pytest tests/auth/test_register.py tests/auth/test_sessions.py tests/database/test_auth_models.py tests/admin/test_grant_admin.py -q
```

Expected: failures for the missing column, response field, admin package, and
promotion functions.

- [ ] **Step 4: Add the migration and identity field**

Create revision `20260727_04`, down-revision `20260727_03`:

```python
def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("is_admin", sa.Boolean(), server_default=sa.false(), nullable=False),
    )


def downgrade() -> None:
    op.drop_column("users", "is_admin")
```

Add the matching model field:

```python
is_admin: Mapped[bool] = mapped_column(
    Boolean,
    default=False,
    server_default=false(),
    nullable=False,
)
```

Add `is_admin: bool` to `UserResponse`; do not expose password, session, or
other authorization data. Set `RegisterRequest.model_config = ConfigDict(extra="forbid")`
so public registration rejects `is_admin` instead of silently ignoring it.

- [ ] **Step 5: Implement promotion service and CLI**

Implement the service with the existing `normalize_email` function:

```python
def grant_admin(db: Session, email: str) -> User:
    user = db.scalar(select(User).where(User.email == normalize_email(email)))
    if user is None:
        raise AdminUserNotFoundError
    if not user.is_admin:
        user.is_admin = True
        db.commit()
        db.refresh(user)
    return user
```

The CLI parses exactly one email, opens a `Session(get_engine(settings.database_url))`,
prints a success message without credentials, and returns exit code `1` for an
unknown account or database failure.

- [ ] **Step 6: Verify GREEN and static checks**

Run:

```bash
cd backend
TEST_DATABASE_URL=postgresql+psycopg://fitsho:fitsho@localhost:5432/fitsho_test .venv/bin/pytest tests/auth/test_register.py tests/auth/test_sessions.py tests/database/test_auth_models.py tests/admin/test_grant_admin.py -q
.venv/bin/ruff check app/admin app/auth tests/admin tests/auth/test_register.py tests/auth/test_sessions.py tests/database/test_auth_models.py
.venv/bin/mypy app/admin app/auth
```

Expected: all commands pass, including the public-registration escalation test.

- [ ] **Step 7: Review Task 1 scope without committing**

Run `git diff -- backend/alembic backend/app/admin backend/app/auth backend/tests/admin backend/tests/auth backend/tests/database/test_auth_models.py` and confirm only administrator identity, promotion, and registration hardening are present. Keep the changes uncommitted for the required final feature commit.

---

### Task 2: Authorized admin listing and placeholder exercise creation

**Files:**
- Create: `backend/app/admin/dependencies.py`
- Create: `backend/app/admin/schemas.py`
- Create: `backend/app/admin/router.py`
- Create: `backend/app/exercises/taxonomy.py`
- Modify: `backend/app/admin/exceptions.py`
- Modify: `backend/app/admin/service.py`
- Modify: `backend/app/exercises/router.py`
- Modify: `backend/app/main.py`
- Modify: `backend/pyproject.toml`
- Create: `backend/tests/admin/test_admin_exercise_api.py`
- Modify: `backend/tests/exercises/test_exercise_api.py`
- Modify: `backend/tests/exercises/test_seed.py`

**Interfaces:**
- Consumes: `User.is_admin`.
- Produces: `get_current_admin(user: CurrentUser) -> User`.
- Produces: `MUSCLES_BY_REGION: dict[BodyRegion, tuple[MuscleGroup, ...]]`.
- Produces: `AdminExerciseCreate`, `AdminExerciseResponse`, `AdminExerciseFilters`, and `AdminPaginatedExercises`.
- Produces: `list_admin_exercises(db: Session, filters: AdminExerciseFilters) -> tuple[list[Exercise], int]`.
- Produces: `create_exercise(db: Session, payload: AdminExerciseCreate, media: ExerciseMediaValues) -> Exercise`.
- Produces: `GET /api/v1/admin/exercises`.
- Produces: `POST /api/v1/admin/exercises`.

- [ ] **Step 1: Write failing authorization tests**

Post a valid multipart `payload` JSON field without media:

```python
response = client.post(
    "/api/v1/admin/exercises",
    headers=ORIGIN,
    files={"payload": (None, json.dumps(VALID_EXERCISE))},
)
```

Assert guest `401`, authenticated non-admin `403`, admin without a profile
`201`, and an untrusted origin `403`. Repeat guest/non-admin/admin authorization
assertions for `GET /api/v1/admin/exercises`; GET does not require an Origin.

- [ ] **Step 2: Write failing validation and persistence tests**

Cover:

```python
assert response.json()["media_type"] == "placeholder"
assert response.json()["media_path"] == "/exercises/exercise-placeholder.svg"
assert response.json()["is_active"] is True
assert response.json()["secondary_muscles"] == ["shoulders", "triceps"]
assert response.json()["equipment"] == ["bench", "dumbbell"]
```

Parametrize invalid slug, every invalid controlled enum (body region, primary
muscle, secondary muscle, equipment, difficulty), zero equipment, 2 or 7
instructions, empty safety notes, cross-region primary muscle, cross-region
secondary muscle, duplicate secondary muscle, and primary repeated as
secondary. Assert field-oriented `422` details. Create the same slug twice and
assert `409`.

Add catalog assertions: an active admin-created row appears immediately, an
inactive row stays hidden, and re-running `seed_exercises` preserves the
admin-created slug, UUID, fields, associations, and media path.

Create one active and one inactive row, then assert the admin GET response
contains both, includes `is_active`, `created_at`, and `updated_at`, sorts
deterministically, paginates, searches, and filters by `is_active`. Assert the
public catalog still hides the inactive row.

- [ ] **Step 3: Run the new tests and confirm RED**

Run:

```bash
cd backend
TEST_DATABASE_URL=postgresql+psycopg://fitsho:fitsho@localhost:5432/fitsho_test .venv/bin/pytest tests/admin/test_admin_exercise_api.py tests/exercises/test_exercise_api.py tests/exercises/test_seed.py -q
```

Expected: route/module-not-found failures.

- [ ] **Step 4: Centralize the exercise taxonomy**

Define immutable region tuples:

```python
MUSCLES_BY_REGION = {
    BodyRegion.UPPER_BODY: (
        MuscleGroup.CHEST, MuscleGroup.BACK, MuscleGroup.SHOULDERS,
        MuscleGroup.BICEPS, MuscleGroup.TRICEPS, MuscleGroup.TRAPS,
    ),
    BodyRegion.LOWER_BODY: (
        MuscleGroup.GLUTES, MuscleGroup.QUADRICEPS, MuscleGroup.HAMSTRINGS,
        MuscleGroup.ADDUCTORS, MuscleGroup.CALVES,
    ),
    BodyRegion.CORE: (
        MuscleGroup.ABS, MuscleGroup.OBLIQUES, MuscleGroup.LOWER_BACK,
    ),
}
```

Make the existing catalog category constants derive their muscle values from
this shared mapping while preserving current order and bilingual names.

- [ ] **Step 5: Implement admin schemas**

Use existing enums and a model validator:

```python
class AdminExerciseCreate(BaseModel):
    slug: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$", max_length=120)
    name_en: str = Field(min_length=2, max_length=160)
    name_fa: str = Field(min_length=2, max_length=160)
    body_region: BodyRegion
    primary_muscle: MuscleGroup
    secondary_muscles: list[MuscleGroup] = Field(default_factory=list)
    equipment: list[Equipment] = Field(min_length=1)
    difficulty: Difficulty
    instructions_en: list[str] = Field(min_length=3, max_length=6)
    instructions_fa: list[str] = Field(min_length=3, max_length=6)
    safety_notes_en: list[str] = Field(min_length=1)
    safety_notes_fa: list[str] = Field(min_length=1)
    is_active: bool = True
    media_source_url: AnyHttpUrl | None = None
    media_license: str | None = Field(default=None, max_length=120)
    media_attribution: str | None = Field(default=None, max_length=500)
```

Normalize all strings, reject empty list items, enforce taxonomy membership,
uniqueness, and primary/secondary separation. `AdminExerciseResponse` includes
the existing detail fields plus `is_active`, `created_at`, and `updated_at`.
`AdminExerciseFilters` provides `search`, `is_active`, `page`, and `page_size`;
`AdminPaginatedExercises` mirrors the existing pagination shape.

- [ ] **Step 6: Implement authorization, service, and route**

Authorization:

```python
def get_current_admin(user: CurrentUser) -> User:
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Administrator access required")
    return user
```

Creation uses `Exercise`, `ExerciseSecondaryMuscle`, and `ExerciseEquipment` in
one transaction. Define:

```python
@dataclass(frozen=True)
class ExerciseMediaValues:
    path: str
    media_type: MediaType


PLACEHOLDER_MEDIA = ExerciseMediaValues(
    path="/exercises/exercise-placeholder.svg",
    media_type=MediaType.PLACEHOLDER,
)
```

Map unique violations to `ExerciseSlugConflictError`, roll back every database
failure, and eagerly load associations before building the response.

Implement `list_admin_exercises` without the public `Exercise.is_active` base
condition. Apply optional search/status filters, eager-load normalized
associations, and order by `name_en` then `id`.

The route receives `payload: Annotated[str, Form()]`, validates it with
`AdminExerciseCreate.model_validate_json(payload)`, accepts no browser media
path fields, maps Pydantic locations into useful `422` details, applies
`Depends(require_trusted_origin)`, and returns `201`. The GET route uses the
same admin dependency but no trusted-origin mutation guard. Install
`python-multipart>=0.0.20,<1`.

- [ ] **Step 7: Verify GREEN and regression safety**

Run:

```bash
cd backend
TEST_DATABASE_URL=postgresql+psycopg://fitsho:fitsho@localhost:5432/fitsho_test .venv/bin/pytest tests/admin/test_admin_exercise_api.py tests/exercises/test_exercise_api.py tests/exercises/test_seed.py -q
.venv/bin/ruff check app/admin app/exercises app/main.py tests/admin tests/exercises
.venv/bin/mypy app/admin app/exercises app/main.py
```

Expected: all commands pass, the admin list includes inactive rows, and the
existing public catalog response ordering remains unchanged.

- [ ] **Step 8: Review Task 2 scope without committing**

Run `git diff -- backend/app/admin backend/app/exercises backend/app/main.py backend/pyproject.toml backend/tests/admin backend/tests/exercises` and confirm there are no public mutation endpoints and no edit/delete behavior. Keep changes for the final feature commit.

---

### Task 3: Validated runtime media storage

**Files:**
- Create: `backend/app/admin/media.py`
- Create: `backend/app/exercises/media_metadata.py`
- Modify: `backend/app/admin/router.py`
- Modify: `backend/app/admin/service.py`
- Modify: `backend/app/config.py`
- Modify: `backend/app/main.py`
- Modify: `backend/app/exercises/seed_data.py`
- Modify: `backend/tests/conftest.py`
- Create: `backend/tests/admin/test_admin_media.py`
- Create: `backend/tests/fixtures/media/short.gif`
- Create: `backend/tests/fixtures/media/short.mp4`
- Create: `backend/tests/fixtures/media/short.webm`
- Modify: `backend/tests/admin/test_admin_exercise_api.py`
- Modify: `backend/tests/test_config.py`

**Interfaces:**
- Produces: `StoredExerciseMedia(path: str, media_type: MediaType, filesystem_path: Path)`.
- Produces: `store_exercise_media(upload: UploadFile, settings: Settings) -> StoredExerciseMedia`.
- Produces: `remove_stored_media(media: StoredExerciseMedia) -> None`.
- Produces: `probe_video_duration(path: Path, settings: Settings) -> float`.
- Produces: `Settings.media_root`, `media_upload_max_bytes`, `media_max_video_duration_seconds`, `media_ffprobe_path`, and `media_probe_timeout_seconds`.

- [ ] **Step 1: Write failing signature and size tests**

Use minimal signature-bearing bytes:

```python
GIF = b"GIF89a" + b"\x00" * 32
MP4 = b"\x00\x00\x00\x18ftypisom" + b"\x00" * 24
WEBM = b"\x1a\x45\xdf\xa3" + b"\x00" * 32
```

Use these bytes for detector unit tests. For endpoint tests, use committed tiny
valid GIF, MP4, and WebM fixtures under `backend/tests/fixtures/media/`.
Generate deterministic one-second, 16×16 silent fixtures once:

```bash
mkdir -p backend/tests/fixtures/media
ffmpeg -f lavfi -i color=c=black:s=16x16:d=1 -an -y backend/tests/fixtures/media/short.gif
ffmpeg -f lavfi -i color=c=black:s=16x16:d=1 -an -c:v libx264 -pix_fmt yuv420p -y backend/tests/fixtures/media/short.mp4
ffmpeg -f lavfi -i color=c=black:s=16x16:d=1 -an -c:v libvpx-vp9 -y backend/tests/fixtures/media/short.webm
```

Assert matching extension, allowlisted MIME, and signature succeed. Assert
unsupported MIME, unsupported extension, extension/signature mismatch, MIME/
signature mismatch, random bytes, executable bytes, and path separators in the
submitted filename are rejected. Assert an empty file returns `422`, a body over
20 MiB returns `413`, and no user filename appears in `media_path`.

- [ ] **Step 2: Write failing cleanup and metadata tests**

Force a duplicate-slug database failure after a valid upload and assert the
media directory contains no new file. Test supplied metadata is preserved.
When all optional metadata is blank, assert:

```python
assert body["media_license"] == "Project owner supplied and authorized"
assert body["media_attribution"] == "Provided by Fitsho project owner"
assert body["media_source_url"] is None
```

Monkeypatch `subprocess.run` to return durations `19.9` and `20.1`; assert the
first video succeeds and the second returns `422`. Cover invalid probe output,
non-zero exit, and timeout. Pre-create the first generated UUID filename,
force the UUID sequence to collide once, and assert the existing bytes are
unchanged while the upload receives a different generated filename.

- [ ] **Step 3: Run the media tests and confirm RED**

Run:

```bash
cd backend
TEST_DATABASE_URL=postgresql+psycopg://fitsho:fitsho@localhost:5432/fitsho_test .venv/bin/pytest tests/admin/test_admin_media.py tests/admin/test_admin_exercise_api.py tests/test_config.py -q
```

Expected: missing settings and media-module failures.

- [ ] **Step 4: Add media settings and shared metadata**

Add:

```python
media_root: Path = Path("var/media")
media_upload_max_bytes: int = Field(default=20 * 1024 * 1024, ge=1)
media_max_video_duration_seconds: float = Field(default=20.0, gt=0)
media_ffprobe_path: str = "ffprobe"
media_probe_timeout_seconds: float = Field(default=5.0, gt=0)
```

Move the two owner strings from `seed_data.py` into
`exercises/media_metadata.py` and import them from both seed and admin code.
Update the test settings fixture to use an isolated `tmp_path / "media"`.

- [ ] **Step 5: Implement bounded signature-based storage**

`store_exercise_media` must:

1. Reject absent names, NUL, `/`, or `\\` in `upload.filename` before writing.
2. Require one exact pair from `.gif`/`image/gif`, `.mp4`/`video/mp4`, or
   `.webm`/`video/webm`.
3. Create `<media_root>/exercises` and stream fixed 64 KiB chunks into a
   `NamedTemporaryFile` in that directory.
4. Reject total size zero and stop before writing beyond
   `media_upload_max_bytes`.
5. Detect GIF via `GIF87a`/`GIF89a`, MP4 via bytes `4:8 == b"ftyp"`, and WebM
   via `b"\x1a\x45\xdf\xa3"`; require signature to match extension/MIME.
6. For MP4/WebM, call `ffprobe -v error -show_entries format=duration` with an
   argument list, `shell=False`, a 20 MiB-bounded input, duration-only captured
   output, and `timeout=media_probe_timeout_seconds`; terminate on timeout and
   require a finite positive duration no greater than
   `media_max_video_duration_seconds`.
7. After validation, create `uuid4().hex` plus the validated extension and use
   `os.link(temp_path, final_path)` for atomic exclusive publication. Retry a
   bounded number of UUID collisions; never use an overwriting rename.
8. Unlink the temporary name, return `/media/exercises/<generated-name>`, and
   remove every temporary or partially published file on exception.

Map GIF to `MediaType.GIF` and both video formats to `MediaType.VIDEO`.

- [ ] **Step 6: Integrate upload and atomic cleanup**

Add `media: UploadFile | None = File(default=None)` to the multipart route.
Store before database creation, pass derived values to the service, apply owner
metadata defaults only for an upload with blank metadata, and call
`remove_stored_media` whenever validation or persistence fails after storage.

In `create_app`, create the configured root and mount:

```python
app.mount(
    "/media",
    StaticFiles(directory=active_settings.media_root),
    name="exercise-media",
)
```

- [ ] **Step 7: Verify GREEN, static serving, and cleanup**

Run:

```bash
cd backend
TEST_DATABASE_URL=postgresql+psycopg://fitsho:fitsho@localhost:5432/fitsho_test .venv/bin/pytest tests/admin/test_admin_media.py tests/admin/test_admin_exercise_api.py tests/test_config.py -q
.venv/bin/ruff check app/admin app/config.py app/main.py app/exercises/media_metadata.py app/exercises/seed_data.py tests/admin tests/test_config.py
.venv/bin/mypy app/admin app/config.py app/main.py app/exercises/media_metadata.py
```

Expected: supported uploads are retrievable at their returned `/media` URL and
all error paths leave no orphan file, collision tests preserve existing bytes,
and over-duration videos are rejected.

- [ ] **Step 8: Review Task 3 scope without committing**

Run `git diff -- backend/app/admin/media.py backend/app/admin/router.py backend/app/config.py backend/app/main.py backend/app/exercises backend/tests/admin backend/tests/conftest.py backend/tests/test_config.py`. Confirm binaries are only small test fixtures, no runtime upload is tracked, PostgreSQL stores paths/metadata only, and final-file creation cannot overwrite. Keep changes for the final feature commit.

---

### Task 4: Persistent Docker media runtime

**Files:**
- Create: `backend/Dockerfile`
- Create: `backend/.dockerignore`
- Modify: `compose.yaml`
- Modify: `.env.example`
- Modify: `.gitignore`
- Modify: `frontend/vite.config.ts`
- Modify: `docs/running-locally.md`

**Interfaces:**
- Consumes: `MEDIA_ROOT`, `MEDIA_UPLOAD_MAX_BYTES`, `MEDIA_MAX_VIDEO_DURATION_SECONDS`, `MEDIA_FFPROBE_PATH`, and `MEDIA_PROBE_TIMEOUT_SECONDS`.
- Produces: Compose service `backend`.
- Produces: named volume `fitsho_exercise_media`.
- Produces: Vite `/media` development proxy.

- [ ] **Step 1: Write the expected Compose configuration**

Add a Python 3.12 slim backend image that installs `ffmpeg` (providing
`ffprobe`), installs the package, exposes port 8000, and runs:

```dockerfile
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*
```

```dockerfile
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

Create `backend/.dockerignore` with `.venv`, `__pycache__`, test caches,
coverage output, `var`, and local `.env` so runtime uploads and secrets never
enter the image build context.

Add the service:

```yaml
backend:
  build:
    context: ./backend
  environment:
    DATABASE_URL: postgresql+psycopg://fitsho:fitsho@db:5432/fitsho
    FRONTEND_ORIGIN: http://localhost:5173
    APP_ENV: local
    COOKIE_SECURE: "false"
    SESSION_COOKIE_NAME: fitsho_session
    MEDIA_ROOT: /var/lib/fitsho/media
    MEDIA_UPLOAD_MAX_BYTES: "20971520"
    MEDIA_MAX_VIDEO_DURATION_SECONDS: "20"
    MEDIA_FFPROBE_PATH: /usr/bin/ffprobe
    MEDIA_PROBE_TIMEOUT_SECONDS: "5"
  ports:
    - "8000:8000"
  volumes:
    - fitsho_exercise_media:/var/lib/fitsho/media
  depends_on:
    db:
      condition: service_healthy
```

Declare `fitsho_exercise_media` under top-level volumes.

- [ ] **Step 2: Add local configuration and proxy**

Add:

```dotenv
MEDIA_ROOT=var/media
MEDIA_UPLOAD_MAX_BYTES=20971520
MEDIA_MAX_VIDEO_DURATION_SECONDS=20
MEDIA_FFPROBE_PATH=ffprobe
MEDIA_PROBE_TIMEOUT_SECONDS=5
```

Ignore `backend/var/`. Add `/media` to the existing Vite proxy with the same
backend target as `/api`.

- [ ] **Step 3: Document both local runtime modes**

Update the Persian local-running guide with:

- Host-run backend using `backend/var/media`.
- Compose backend using the persistent named volume.
- Migration, seeding, and `grant_admin` commands.
- A warning that uploaded runtime files are not repository assets.
- Coordinated PostgreSQL/media-volume backup and restore requirements.
- The local `ffprobe` prerequisite and Docker-provided binary.

- [ ] **Step 4: Validate Docker and frontend configuration**

Run:

```bash
docker compose config
docker build -t fitsho-backend-admin ./backend
docker run --rm fitsho-backend-admin ffprobe -version
cd frontend
npm test -- src/shared/apiClient.test.ts
npm run build
```

Expected: Compose resolves the backend volume, the image builds, `ffprobe` is
available inside it, and Vite configuration type-checks.

- [ ] **Step 5: Review Task 4 scope without committing**

Run `git diff -- backend/Dockerfile compose.yaml .env.example .gitignore frontend/vite.config.ts docs/running-locally.md`. Confirm the named volume is persistent, runtime paths are ignored, no `.env` file is tracked, and no upload directory is under `frontend/public`. Keep changes for the final feature commit.

---

### Task 5: Frontend administrator identity, navigation, and route guard

**Files:**
- Create: `frontend/src/features/admin/AdminRoute.tsx`
- Create: `frontend/src/features/admin/AdminExerciseListPage.tsx`
- Create: `frontend/src/features/admin/AdminExerciseCreatePage.tsx`
- Create: `frontend/src/features/admin/AdminRoute.test.tsx`
- Create: `frontend/src/shared/AuthenticatedHeader.test.tsx`
- Modify: `frontend/src/features/auth/types.ts`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/App.test.tsx`
- Modify: `frontend/src/shared/AuthenticatedHeader.tsx`
- Modify: `frontend/src/features/auth/AuthContext.test.tsx`
- Modify: `frontend/src/features/auth/LoginPage.test.tsx`
- Modify: `frontend/src/features/auth/RegisterPage.integration.test.tsx`
- Modify: `frontend/src/features/auth/api.test.ts`
- Modify: `frontend/src/features/profile/ProfileContext.test.tsx`
- Modify: `frontend/src/features/profile/ProfileRouteGuards.test.tsx`
- Modify: `frontend/src/i18n/en.ts`
- Modify: `frontend/src/i18n/fa.ts`

**Interfaces:**
- Consumes: `/api/v1/auth/me` field `is_admin`.
- Produces: `User.is_admin: boolean`.
- Produces: `<AdminRoute />`.
- Produces: routes `/admin/exercises` and `/admin/exercises/new`.

- [ ] **Step 1: Update test user fixtures and write failing nav tests**

Every existing `User` fixture gains `is_admin: false`. Add header tests:

```tsx
expect(screen.queryByRole("link", { name: "Exercise admin" })).not.toBeInTheDocument();
contexts.auth.user = { ...member, is_admin: true };
expect(screen.getByRole("link", { name: "Exercise admin" })).toHaveAttribute(
  "href",
  "/admin/exercises",
);
```

Repeat the visible label assertion in Persian.

- [ ] **Step 2: Write failing direct-route guard tests**

Assert:

- Guest at each admin route reaches login.
- Non-admin at each admin route reaches `/dashboard` and then follows existing
  profile behavior.
- Admin with `profile.status === "missing"` sees both the list and create page
  headings without onboarding.
- Admin with a ready profile can access both pages.

- [ ] **Step 3: Run focused tests and confirm RED**

Run:

```bash
cd frontend
npm test -- src/shared/AuthenticatedHeader.test.tsx src/features/admin/AdminRoute.test.tsx src/App.test.tsx
```

Expected: missing `is_admin`, route, and translations.

- [ ] **Step 4: Implement identity, navigation, and guard**

Add:

```ts
export type User = {
  id: string;
  email: string;
  created_at: string;
  is_admin: boolean;
};
```

Render the link only when `user.is_admin`. Implement:

```tsx
export function AdminRoute() {
  const { user } = useAuth();
  return user?.is_admin ? <Outlet /> : <Navigate to="/dashboard" replace />;
}
```

Nest `AdminRoute` directly inside `ProtectedRoute`, not inside
`CompletedProfileRoute`. Create minimal translated list and create page shells
with `AuthenticatedHeader`; data and form behavior arrive in Tasks 6–7.

- [ ] **Step 5: Verify GREEN and all affected auth/profile tests**

Run:

```bash
cd frontend
npm test -- src/shared/AuthenticatedHeader.test.tsx src/features/admin/AdminRoute.test.tsx src/App.test.tsx src/features/auth src/features/profile
npm run lint
npm run build
```

Expected: all commands pass.

- [ ] **Step 6: Review Task 5 scope without committing**

Run `git diff -- frontend/src/App.tsx frontend/src/features/admin frontend/src/features/auth frontend/src/features/profile frontend/src/shared/AuthenticatedHeader.tsx frontend/src/i18n`. Confirm non-admin pages are not redesigned and admin navigation is hidden for non-admin users. Keep changes for the final feature commit.

---

### Task 6: Frontend form domain and multipart API

**Files:**
- Create: `frontend/src/features/admin/types.ts`
- Create: `frontend/src/features/admin/slug.ts`
- Create: `frontend/src/features/admin/slug.test.ts`
- Create: `frontend/src/features/admin/validation.ts`
- Create: `frontend/src/features/admin/validation.test.ts`
- Create: `frontend/src/features/admin/api.ts`
- Create: `frontend/src/features/admin/api.test.ts`
- Modify: `frontend/src/shared/apiClient.ts`
- Modify: `frontend/src/shared/apiClient.test.ts`

**Interfaces:**
- Produces: `suggestExerciseSlug(name: string) -> string`.
- Produces: `validateAdminExercise(input: AdminExerciseInput) -> AdminExerciseErrors`.
- Produces: `listAdminExercises(filters: AdminExerciseFilters) -> Promise<AdminPaginatedExercises>`.
- Produces: `createAdminExercise(input: AdminExerciseInput, media: File | null) -> Promise<AdminExercise>`.

- [ ] **Step 1: Write failing shared-client multipart test**

```ts
const body = new FormData();
body.append("payload", "{}");
await request("/api/test", { method: "POST", body });
const headers = new Headers(vi.mocked(fetch).mock.calls[0][1]?.headers);
expect(headers.has("Content-Type")).toBe(false);
```

Keep the existing JSON-header test passing.

- [ ] **Step 2: Write failing slug and validation tests**

Assert:

```ts
expect(suggestExerciseSlug("  Incline Dumbbell Press  ")).toBe(
  "incline-dumbbell-press",
);
expect(suggestExerciseSlug("Farmer’s Walk")).toBe("farmers-walk");
```

Validate slug format, bilingual names, taxonomy, unique secondary muscles,
primary exclusion, equipment count, 3–6 trimmed instructions, non-empty safety
notes, and optional URL validity. Use the same region map and enum arrays from
`features/exercises/types.ts`.

- [ ] **Step 3: Write failing multipart API test**

Assert `createAdminExercise` appends exactly:

```ts
expect(form.get("payload")).toBe(JSON.stringify(expectedSnakeCasePayload));
expect(form.get("media")).toBe(file);
```

Assert credentials are included through the shared client and no `media_path`,
`media_type`, or stored filename appears in the JSON.

Also test `listAdminExercises` encodes `search`, `is_active`, `page`, and
`page_size`, returns inactive items unchanged, and calls
`GET /api/v1/admin/exercises` through the shared client.

- [ ] **Step 4: Run domain tests and confirm RED**

Run:

```bash
cd frontend
npm test -- src/shared/apiClient.test.ts src/features/admin/slug.test.ts src/features/admin/validation.test.ts src/features/admin/api.test.ts
```

Expected: missing helpers and forced multipart content type.

- [ ] **Step 5: Implement client behavior and pure domain helpers**

Change the shared client condition:

```ts
if (!headers.has("Content-Type") && !(init?.body instanceof FormData)) {
  headers.set("Content-Type", "application/json");
}
```

Implement ASCII lowercase kebab normalization, a typed `MUSCLES_BY_REGION`,
field-keyed validation errors, and `FormData` serialization with one JSON
`payload` part and optional `media`. Add list/filter/response types matching the
backend admin pagination contract. Keep Fetch as the shared transport: it does
not expose upload-progress callbacks, so the UI will use an indeterminate
loading state rather than fake percentage progress.

- [ ] **Step 6: Verify GREEN and type safety**

Run:

```bash
cd frontend
npm test -- src/shared/apiClient.test.ts src/features/admin/slug.test.ts src/features/admin/validation.test.ts src/features/admin/api.test.ts
npm run lint
npm run build
```

Expected: all commands pass.

- [ ] **Step 7: Review Task 6 scope without committing**

Run `git diff -- frontend/src/features/admin/types.ts frontend/src/features/admin/slug.ts frontend/src/features/admin/validation.ts frontend/src/features/admin/api.ts frontend/src/shared/apiClient.ts frontend/src/features/admin/*.test.ts frontend/src/shared/apiClient.test.ts`. Confirm no browser-supplied storage path or detected media type exists in the request type. Keep changes for the final feature commit.

---

### Task 7: Bilingual administrator list and exercise form

**Files:**
- Create: `frontend/src/features/admin/OrderedTextList.tsx`
- Create: `frontend/src/features/admin/AdminMediaPreview.tsx`
- Create: `frontend/src/features/admin/AdminExerciseForm.tsx`
- Create: `frontend/src/features/admin/AdminExerciseListPage.test.tsx`
- Create: `frontend/src/features/admin/AdminExerciseCreatePage.test.tsx`
- Create: `frontend/src/features/admin/admin.css`
- Modify: `frontend/src/features/admin/AdminExerciseListPage.tsx`
- Modify: `frontend/src/features/admin/AdminExerciseCreatePage.tsx`
- Modify: `frontend/src/i18n/en.ts`
- Modify: `frontend/src/i18n/fa.ts`

**Interfaces:**
- Consumes: `listAdminExercises`, `suggestExerciseSlug`, `validateAdminExercise`, and `createAdminExercise`.
- Produces: complete `/admin/exercises` and `/admin/exercises/new` UIs.

- [ ] **Step 1: Write failing admin-list tests**

Test in Persian and English:

- Active and inactive exercises render with localized status.
- Existing media renders through `ExerciseMedia`.
- “Add exercise” links to `/admin/exercises/new`.
- Loading, empty, API error, retry, search, status filter, and pagination work.
- `?created=new-slug` highlights and focuses the matching row and announces
  success to assistive technology.
- The created active item links to public catalog detail only when profile
  status is `ready`.

- [ ] **Step 2: Write failing form interaction tests**

Test in Persian and English:

- English name suggests `incline-dumbbell-press`.
- Editing slug stops later name changes from overwriting it.
- Selecting `lower_body` exposes only lower-body primary/secondary muscles.
- Changing region removes invalid prior muscle selections.
- Equipment requires at least one checkbox; bodyweight satisfies it.
- Instruction editors start with three rows, add up to six, and never remove
  below three.
- Safety editors start with one row, add/remove dynamically, and never remove
  below one.
- Active starts checked.
- File input accepts `.gif,.mp4,.webm`.
- No selected file renders the existing placeholder.
- Selected GIF renders an image preview; selected MP4/WebM renders a muted,
  controlled, non-autoplaying video preview.
- Replacing/removing a selection revokes its object URL.
- Submitted `File` and structured payload reach the mocked API.

- [ ] **Step 3: Write failing state, retry, accessibility, and direction tests**

Assert:

- English fields use `dir="ltr"` and Persian fields use `dir="rtl"` regardless
  of the current page language.
- `422` field details connect through `aria-describedby`; `409`, `413`, `415`,
  and generic failures show localized screen-reader-visible messages.
- Submit disables repeated actions and shows indeterminate uploading/loading
  status; no percentage is shown because Fetch exposes no upload progress.
- Generic/API upload failure preserves all values and offers a retry button.
- Successful creation navigates to `/admin/exercises?created=<slug>`.
- Tab/Enter/Space keyboard interaction covers selects, checkbox multi-selects,
  repeatable controls, media selection, retry, and submit.

- [ ] **Step 4: Run page tests and confirm RED**

Run:

```bash
cd frontend
npm test -- src/features/admin/AdminExerciseListPage.test.tsx src/features/admin/AdminExerciseCreatePage.test.tsx
```

Expected: missing form controls and translations.

- [ ] **Step 5: Implement ordered text editor and media preview**

`OrderedTextList` receives:

```ts
type OrderedTextListProps = {
  legend: string;
  values: string[];
  direction: "ltr" | "rtl";
  minItems: number;
  maxItems: number;
  onChange: (values: string[]) => void;
};
```

Use numbered labels, stable React keys, explicit add/remove buttons, and
localized accessible names. Disable add/remove at bounds.

`AdminMediaPreview` creates one object URL for a selected file, revokes it on
replacement/unmount, chooses image or video from the allowlisted file type,
and otherwise renders `ExerciseMedia` with the existing placeholder path. Video
uses `controls`, `muted`, `playsInline`, and no `autoPlay`.

- [ ] **Step 6: Implement the controlled form**

Use semantic `fieldset` groups and checkbox multi-selects. Keep a
`slugWasEdited` flag. On body-region change, clear invalid primary and
secondary values. Run pure validation before submit, focus the first invalid
field, disable controls while saving, and pass only typed input plus the
selected `File` to the API.

- [ ] **Step 7: Implement list, page states, translations, and CSS**

Load the admin list including inactive rows and reuse `ExerciseMedia`. Map
`ApiError.status` and backend field locations to localized messages. Preserve
the form for retry and navigate only after success. Use the existing
authenticated header, color variables, rounded asymmetric cards, logical
properties, `:focus-visible`, responsive breakpoints, and reduced-motion
convention. Avoid physical left/right properties except for fixed LTR content.

- [ ] **Step 8: Verify GREEN, RTL/LTR, lint, and build**

Run:

```bash
cd frontend
npm test -- src/features/admin/AdminExerciseListPage.test.tsx src/features/admin/AdminExerciseCreatePage.test.tsx src/features/admin src/App.test.tsx src/shared/AuthenticatedHeader.test.tsx
npm run lint
npm run build
```

Expected: all commands pass in both language test cases.

- [ ] **Step 9: Review Task 7 scope without committing**

Run `git diff -- frontend/src/features/admin frontend/src/i18n/en.ts frontend/src/i18n/fa.ts`. Confirm public auth/profile/catalog layouts are unchanged, media previews revoke object URLs, videos never autoplay with sound, and every requested state has bilingual copy. Keep changes for the final feature commit.

---

### Task 8: Full-system verification and operator documentation

**Files:**
- Modify: `docs/running-locally.md`
- Create: `docs/exercise-admin.md`

**Interfaces:**
- Documents: architecture, authorization, APIs, every form field, admin
  promotion, media security/persistence, seed coexistence, `exercises.id`, and
  recovery checks.

- [ ] **Step 1: Add concise operator documentation**

Document:

```bash
cd backend
.venv/bin/alembic upgrade head
.venv/bin/python -m app.admin.grant_admin admin@example.com
```

Include both admin URLs, boolean authorization model, GET/POST API contracts,
every required/optional/generated form field, MIME/extension/signature rules,
20 MiB and 20-second defaults, `ffprobe`, placeholder behavior, named Docker
volume, coordinated database/media backup responsibility, and confirmation
that seed execution preserves custom rows, UUIDs, associations, and media.
State that future workout plans continue to reference `exercises.id`.

- [ ] **Step 2: Run the complete backend verification**

Run:

```bash
cd backend
TEST_DATABASE_URL=postgresql+psycopg://fitsho:fitsho@localhost:5432/fitsho_test .venv/bin/pytest
.venv/bin/ruff check app tests
.venv/bin/ruff format --check app tests
.venv/bin/mypy app tests
```

Expected: all tests and checks pass with zero failures.

- [ ] **Step 3: Run the complete frontend verification**

Run:

```bash
cd frontend
npm test
npm run lint
npm run build
```

Expected: all tests and checks pass with zero failures.

- [ ] **Step 4: Validate deployment configuration and working tree scope**

Run:

```bash
docker compose config
docker run --rm fitsho-backend-admin ffprobe -version
git diff --check
git status --short
```

Expected: Compose resolves, `ffprobe` is available, feature files have no
whitespace errors, and only the known unrelated README and Persian
architecture-plan changes remain outside the feature scope.

- [ ] **Step 5: Review and stage the exact feature diff**

```bash
git diff --stat
git diff
git add backend frontend .env.example .gitignore compose.yaml docs/running-locally.md docs/exercise-admin.md
git diff --cached --check
git diff --cached --name-only
git diff --cached --stat
git diff --cached
```

Confirm the staged list contains no secrets, `.env`, database files, runtime
uploads, `frontend/dist`, caches, or unrelated README/Persian-plan changes.
Confirm it contains no public mutation route and no edit/delete feature.

- [ ] **Step 6: Create the required implementation commit and push**

```bash
git commit -m "feat(admin): add exercise management panel"
git push
```

- [ ] **Step 7: Verify Git delivery and record final evidence**

Run:

```bash
git status -sb
git show --stat --oneline HEAD
git rev-parse HEAD
git rev-parse origin/feature/exercise-admin
```

Capture the backend test count, frontend test count, lint/build results, Docker
validation result, complete changed-file summary, final commit hash, and remote
tracking status. The final report also lists the selected architecture,
authorization model, migration, fields, APIs, media behavior, frontend guards,
and tests. Do not claim success without fresh output from Steps 2–7. Do not
force-push, merge, or create a pull request.
