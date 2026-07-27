# Exercise Admin Panel Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a secure, bilingual admin-only form that creates normalized exercises and optional validated media for immediate use in the existing catalog.

**Architecture:** Extend the existing session identity with one `is_admin` capability flag and enforce it in a dedicated FastAPI admin module. Create exercises through one multipart endpoint, store validated uploads behind a backend `/media` mount, and reuse the current exercise table and association tables. Add a React admin route outside profile-completion guards, with domain validation separated from rendering.

**Tech Stack:** Python 3.12, FastAPI, Pydantic 2, SQLAlchemy 2, Alembic, PostgreSQL, React 19, TypeScript 6, React Router 7, i18next, Vitest, Testing Library, Docker Compose.

## Global Constraints

- Start from commit `9f1942724cd67307b3eb4945d66fe0fd166be720` on `feature/exercise-admin`; never modify `main` or `feature/exercise-catalog`.
- Preserve the existing `exercises.id` identity and normalized secondary-muscle, equipment, and alternative tables.
- Reuse the existing controlled enum values exactly.
- Guests receive `401`, authenticated non-admins receive `403`, and admins do not require a completed profile.
- Accept only GIF, MP4, and WebM uploads; derive the stored filename, public path, and media type on the backend.
- Use `/exercises/exercise-placeholder.svg` when no upload is supplied.
- Store runtime media in a backend directory with a persistent Docker volume.
- Keep Persian and English UI copy complete and preserve document-level RTL/LTR behavior.
- Do not implement exercise alternatives, workout plans, AI, nutrition, progress tracking, or an authentication redesign.
- Work test-first, commit each completed task, push after verification, and never stage the unrelated README or Persian architecture-plan changes.

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
- `features/admin/AdminExercisePage.tsx`: page loading, submit, error, and success states.
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
TEST_DATABASE_URL=postgresql+psycopg://fitsho:fitsho@localhost:5432/fitsho_test .venv/bin/pytest tests/auth/test_sessions.py tests/database/test_auth_models.py tests/admin/test_grant_admin.py -q
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
other authorization data.

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
TEST_DATABASE_URL=postgresql+psycopg://fitsho:fitsho@localhost:5432/fitsho_test .venv/bin/pytest tests/auth/test_sessions.py tests/database/test_auth_models.py tests/admin/test_grant_admin.py -q
.venv/bin/ruff check app/admin app/auth tests/admin tests/auth/test_sessions.py tests/database/test_auth_models.py
.venv/bin/mypy app/admin app/auth
```

Expected: all commands pass.

- [ ] **Step 7: Commit and push**

```bash
git add backend/alembic/versions/20260727_04_add_user_admin.py backend/app/admin backend/app/auth/models.py backend/app/auth/schemas.py backend/tests/admin backend/tests/auth/test_sessions.py backend/tests/database/test_auth_models.py
git commit -m "feat(exercise-admin): add administrator identity and promotion CLI"
git push
```

---

### Task 2: Authorized placeholder exercise creation

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
- Produces: `AdminExerciseCreate` and `AdminExerciseResponse`.
- Produces: `create_exercise(db: Session, payload: AdminExerciseCreate, media: ExerciseMediaValues) -> Exercise`.
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
`201`, and an untrusted origin `403`.

- [ ] **Step 2: Write failing validation and persistence tests**

Cover:

```python
assert response.json()["media_type"] == "placeholder"
assert response.json()["media_path"] == "/exercises/exercise-placeholder.svg"
assert response.json()["is_active"] is True
assert response.json()["secondary_muscles"] == ["shoulders", "triceps"]
assert response.json()["equipment"] == ["bench", "dumbbell"]
```

Parametrize invalid slug, zero equipment, 2 or 7 instructions, empty safety
notes, cross-region primary muscle, cross-region secondary muscle, duplicate
secondary muscle, and primary repeated as secondary. Assert `422`. Create the
same slug twice and assert `409`.

Add catalog assertions: an active admin-created row appears immediately, an
inactive row stays hidden, and re-running `seed_exercises` preserves the
admin-created slug and fields.

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

The route receives `payload: Annotated[str, Form()]`, validates it with
`AdminExerciseCreate.model_validate_json(payload)`, accepts no browser media
path fields, applies `Depends(require_trusted_origin)`, and returns `201`.
Install `python-multipart>=0.0.20,<1`.

- [ ] **Step 7: Verify GREEN and regression safety**

Run:

```bash
cd backend
TEST_DATABASE_URL=postgresql+psycopg://fitsho:fitsho@localhost:5432/fitsho_test .venv/bin/pytest tests/admin/test_admin_exercise_api.py tests/exercises/test_exercise_api.py tests/exercises/test_seed.py -q
.venv/bin/ruff check app/admin app/exercises app/main.py tests/admin tests/exercises
.venv/bin/mypy app/admin app/exercises app/main.py
```

Expected: all commands pass and the existing catalog response ordering remains
unchanged.

- [ ] **Step 8: Commit and push**

```bash
git add backend/app/admin backend/app/exercises/taxonomy.py backend/app/exercises/router.py backend/app/main.py backend/pyproject.toml backend/tests/admin/test_admin_exercise_api.py backend/tests/exercises/test_exercise_api.py backend/tests/exercises/test_seed.py
git commit -m "feat(exercise-admin): add authorized exercise creation API"
git push
```

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
- Modify: `backend/tests/admin/test_admin_exercise_api.py`
- Modify: `backend/tests/test_config.py`

**Interfaces:**
- Produces: `StoredExerciseMedia(path: str, media_type: MediaType, filesystem_path: Path)`.
- Produces: `store_exercise_media(upload: UploadFile, settings: Settings) -> StoredExerciseMedia`.
- Produces: `remove_stored_media(media: StoredExerciseMedia) -> None`.
- Produces: `Settings.media_root: Path` and `Settings.media_upload_max_bytes: int`.

- [ ] **Step 1: Write failing signature and size tests**

Use minimal signature-bearing bytes:

```python
GIF = b"GIF89a" + b"\x00" * 32
MP4 = b"\x00\x00\x00\x18ftypisom" + b"\x00" * 24
WEBM = b"\x1a\x45\xdf\xa3" + b"\x00" * 32
```

For each, upload a misleading browser filename and content type. Assert the
stored suffix and API media type come from the signature. Assert random bytes
return `415`, a body over the configured limit returns `413`, and no user
filename appears in `media_path`.

- [ ] **Step 2: Write failing cleanup and metadata tests**

Force a duplicate-slug database failure after a valid upload and assert the
media directory contains no new file. Test supplied metadata is preserved.
When all optional metadata is blank, assert:

```python
assert body["media_license"] == "Project owner supplied and authorized"
assert body["media_attribution"] == "Provided by Fitsho project owner"
assert body["media_source_url"] is None
```

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
media_upload_max_bytes: int = Field(default=25 * 1024 * 1024, ge=1)
```

Move the two owner strings from `seed_data.py` into
`exercises/media_metadata.py` and import them from both seed and admin code.
Update the test settings fixture to use an isolated `tmp_path / "media"`.

- [ ] **Step 5: Implement bounded signature-based storage**

`store_exercise_media` must:

1. Create `<media_root>/exercises`.
2. Stream in fixed 64 KiB chunks to a `NamedTemporaryFile` in that directory.
3. Stop before writing beyond `media_upload_max_bytes`.
4. Detect GIF via `GIF87a`/`GIF89a`, MP4 via bytes `4:8 == b"ftyp"`, and WebM
   via `b"\x1a\x45\xdf\xa3"`.
5. Choose `.gif`, `.mp4`, or `.webm`, create `uuid4().hex`, and use
   `os.replace` for the final move.
6. Return public path `/media/exercises/<generated-name>`.
7. Remove the temporary file on every exception.

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
all error paths leave no orphan file.

- [ ] **Step 8: Commit and push**

```bash
git add backend/app/admin backend/app/config.py backend/app/main.py backend/app/exercises/media_metadata.py backend/app/exercises/seed_data.py backend/tests/admin backend/tests/conftest.py backend/tests/test_config.py
git commit -m "feat(exercise-admin): store validated exercise media safely"
git push
```

---

### Task 4: Persistent Docker media runtime

**Files:**
- Create: `backend/Dockerfile`
- Modify: `compose.yaml`
- Modify: `.env.example`
- Modify: `.gitignore`
- Modify: `frontend/vite.config.ts`
- Modify: `docs/running-locally.md`

**Interfaces:**
- Consumes: `MEDIA_ROOT` and `MEDIA_UPLOAD_MAX_BYTES`.
- Produces: Compose service `backend`.
- Produces: named volume `fitsho_exercise_media`.
- Produces: Vite `/media` development proxy.

- [ ] **Step 1: Write the expected Compose configuration**

Add a Python 3.12 slim backend image that installs the package, exposes port
8000, and runs:

```dockerfile
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

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
MEDIA_UPLOAD_MAX_BYTES=26214400
```

Ignore `backend/var/`. Add `/media` to the existing Vite proxy with the same
backend target as `/api`.

- [ ] **Step 3: Document both local runtime modes**

Update the Persian local-running guide with:

- Host-run backend using `backend/var/media`.
- Compose backend using the persistent named volume.
- Migration, seeding, and `grant_admin` commands.
- A warning that uploaded runtime files are not repository assets.

- [ ] **Step 4: Validate Docker and frontend configuration**

Run:

```bash
docker compose config
docker build -t fitsho-backend-admin ./backend
cd frontend
npm test -- src/shared/apiClient.test.ts
npm run build
```

Expected: Compose resolves the backend volume, the image builds, and Vite
configuration type-checks.

- [ ] **Step 5: Commit and push**

```bash
git add backend/Dockerfile compose.yaml .env.example .gitignore frontend/vite.config.ts docs/running-locally.md
git commit -m "build(exercise-admin): persist backend exercise uploads"
git push
```

---

### Task 5: Frontend administrator identity, navigation, and route guard

**Files:**
- Create: `frontend/src/features/admin/AdminRoute.tsx`
- Create: `frontend/src/features/admin/AdminExercisePage.tsx`
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
- Produces: route `/admin/exercises/new`.

- [ ] **Step 1: Update test user fixtures and write failing nav tests**

Every existing `User` fixture gains `is_admin: false`. Add header tests:

```tsx
expect(screen.queryByRole("link", { name: "Exercise admin" })).not.toBeInTheDocument();
contexts.auth.user = { ...member, is_admin: true };
expect(screen.getByRole("link", { name: "Exercise admin" })).toHaveAttribute(
  "href",
  "/admin/exercises/new",
);
```

Repeat the visible label assertion in Persian.

- [ ] **Step 2: Write failing direct-route guard tests**

Assert:

- Guest at `/admin/exercises/new` reaches login.
- Non-admin reaches `/dashboard` and then follows existing profile behavior.
- Admin with `profile.status === "missing"` sees the admin heading without
  onboarding.
- Admin with a ready profile also sees the page.

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
`CompletedProfileRoute`. Create a minimal translated page shell with
`AuthenticatedHeader`; the full form arrives in Task 7.

- [ ] **Step 5: Verify GREEN and all affected auth/profile tests**

Run:

```bash
cd frontend
npm test -- src/shared/AuthenticatedHeader.test.tsx src/features/admin/AdminRoute.test.tsx src/App.test.tsx src/features/auth src/features/profile
npm run lint
npm run build
```

Expected: all commands pass.

- [ ] **Step 6: Commit and push**

```bash
git add frontend/src/features/admin frontend/src/features/auth frontend/src/features/profile frontend/src/shared/AuthenticatedHeader.tsx frontend/src/shared/AuthenticatedHeader.test.tsx frontend/src/App.tsx frontend/src/App.test.tsx frontend/src/i18n/en.ts frontend/src/i18n/fa.ts
git commit -m "feat(exercise-admin): protect administrator frontend access"
git push
```

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
`payload` part and optional `media`.

- [ ] **Step 6: Verify GREEN and type safety**

Run:

```bash
cd frontend
npm test -- src/shared/apiClient.test.ts src/features/admin/slug.test.ts src/features/admin/validation.test.ts src/features/admin/api.test.ts
npm run lint
npm run build
```

Expected: all commands pass.

- [ ] **Step 7: Commit and push**

```bash
git add frontend/src/features/admin/types.ts frontend/src/features/admin/slug.ts frontend/src/features/admin/slug.test.ts frontend/src/features/admin/validation.ts frontend/src/features/admin/validation.test.ts frontend/src/features/admin/api.ts frontend/src/features/admin/api.test.ts frontend/src/shared/apiClient.ts frontend/src/shared/apiClient.test.ts
git commit -m "feat(exercise-admin): add validated multipart form domain"
git push
```

---

### Task 7: Bilingual administrator exercise form

**Files:**
- Create: `frontend/src/features/admin/OrderedTextList.tsx`
- Create: `frontend/src/features/admin/AdminExerciseForm.tsx`
- Create: `frontend/src/features/admin/AdminExercisePage.test.tsx`
- Create: `frontend/src/features/admin/admin.css`
- Modify: `frontend/src/features/admin/AdminExercisePage.tsx`
- Modify: `frontend/src/i18n/en.ts`
- Modify: `frontend/src/i18n/fa.ts`

**Interfaces:**
- Consumes: `suggestExerciseSlug`, `validateAdminExercise`, and `createAdminExercise`.
- Produces: complete `/admin/exercises/new` UI.

- [ ] **Step 1: Write failing form interaction tests**

Test in Persian and English:

- English name suggests `incline-dumbbell-press`.
- Editing slug stops later name changes from overwriting it.
- Selecting `lower_body` exposes only lower-body primary/secondary muscles.
- Changing region removes invalid prior muscle selections.
- Equipment requires at least one checkbox; bodyweight satisfies it.
- Instruction editors start with three rows, add up to six, and never remove
  below three.
- Safety editors require one non-empty row.
- Active starts checked.
- File input accepts `.gif,.mp4,.webm`.
- Submitted `File` and structured payload reach the mocked API.

- [ ] **Step 2: Write failing state and direction tests**

Assert:

- English fields use `dir="ltr"` and Persian fields use `dir="rtl"` regardless
  of the current page language.
- `422`, `409`, `413`, `415`, and generic API failures show localized messages.
- Successful active creation shows confirmation.
- The catalog detail link appears only when profile status is `ready`.
- A successful inactive creation does not show a catalog link.

- [ ] **Step 3: Run page tests and confirm RED**

Run:

```bash
cd frontend
npm test -- src/features/admin/AdminExercisePage.test.tsx
```

Expected: missing form controls and translations.

- [ ] **Step 4: Implement ordered text editor**

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

- [ ] **Step 5: Implement the controlled form**

Use semantic `fieldset` groups and checkbox multi-selects. Keep a
`slugWasEdited` flag. On body-region change, clear invalid primary and
secondary values. Run pure validation before submit, focus the first invalid
field, disable controls while saving, and pass only typed input plus the
selected `File` to the API.

- [ ] **Step 6: Implement page states, translations, and CSS**

Map `ApiError.status` to specific localized messages. Clear the form only after
success. Use the existing authenticated header, color variables, rounded
asymmetric cards, logical properties, `:focus-visible`, responsive breakpoints,
and reduced-motion convention. Avoid physical left/right properties except for
fixed LTR content.

- [ ] **Step 7: Verify GREEN, RTL/LTR, lint, and build**

Run:

```bash
cd frontend
npm test -- src/features/admin/AdminExercisePage.test.tsx src/features/admin src/App.test.tsx src/shared/AuthenticatedHeader.test.tsx
npm run lint
npm run build
```

Expected: all commands pass in both language test cases.

- [ ] **Step 8: Commit and push**

```bash
git add frontend/src/features/admin frontend/src/i18n/en.ts frontend/src/i18n/fa.ts
git commit -m "feat(exercise-admin): add bilingual exercise creation form"
git push
```

---

### Task 8: Full-system verification and operator documentation

**Files:**
- Modify: `docs/running-locally.md`
- Create: `docs/exercise-admin.md`

**Interfaces:**
- Documents: admin promotion, media persistence, supported formats, limits,
  ownership defaults, and recovery checks.

- [ ] **Step 1: Add concise operator documentation**

Document:

```bash
cd backend
.venv/bin/alembic upgrade head
.venv/bin/python -m app.admin.grant_admin admin@example.com
```

Include the admin URL, supported upload formats, 25 MiB default, placeholder
behavior, named Docker volume, backup responsibility, and confirmation that
seed execution does not remove admin-created rows.

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
git diff --check
git status --short
```

Expected: Compose resolves, feature files have no whitespace errors, and only
the known unrelated README and Persian architecture-plan changes remain outside
the feature commits.

- [ ] **Step 5: Commit documentation and push**

```bash
git add docs/running-locally.md docs/exercise-admin.md
git commit -m "docs(exercise-admin): document administration and media operations"
git push
```

- [ ] **Step 6: Record final evidence**

Capture the backend test count, frontend test count, lint/build results, Docker
validation result, final commit hash, and remote tracking status in the final
handoff. Do not claim success without the fresh command output from Steps 2–4.
