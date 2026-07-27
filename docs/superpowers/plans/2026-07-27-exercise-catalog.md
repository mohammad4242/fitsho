# Exercise Catalog Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task in the main session. Do not delegate unless the user explicitly requests it. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an authenticated, bilingual, read-only exercise catalog with controlled relational data, 17 owner-authorized GIFs, empty future-ready categories, filtering, detail pages, and idempotent seed data.

**Architecture:** Add an independent `app.exercises` backend module with normalized equipment, secondary-muscle, and explicit-alternative associations. Expose protected FastAPI read endpoints and add two guarded React routes whose URL query parameters hold catalog selection and filters.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2, Alembic, PostgreSQL, Pydantic 2, pytest, React 19, TypeScript 6, React Router 7, i18next, Vitest, Testing Library, CSS.

## Global Constraints

- Start from `origin/main` commit `3c82a5d` on `feature/exercise-catalog`.
- Keep authentication and profile behavior unchanged except for registering the new protected routes.
- Seed only the 17 exercises with approved GIF mappings: upper body 10, lower body 7, core 0.
- Core taxonomy is exactly `abs`, `obliques`, and `lower_back`; expose empty categories for future admin additions.
- Copy only the 17 approved owner-supplied GIFs. Keep `/exercises/exercise-placeholder.svg` only as a runtime fallback; do not download or hotlink web media.
- Every API requires a valid session and completed profile.
- The API is read-only; do not add create, update, delete, AI, workout-plan, tracking, nutrition, or admin APIs. Admin/upload work is deferred to `feature/exercise-admin`.
- Future plans reference `exercises.id`; stable slugs remain URL identifiers.
- Implement with red-green-refactor and run the focused check after each task.
- Do not create intermediate commits. After every final check passes, create exactly `feat(exercises): add browsable exercise catalog`.

---

## File Map

Backend:

- `backend/app/exercises/enums.py`: controlled body, muscle, equipment, difficulty, and media values.
- `backend/app/exercises/models.py`: exercise and association ORM models.
- `backend/app/exercises/schemas.py`: category, list, pagination, and detail contracts.
- `backend/app/exercises/dependencies.py`: completed-profile API dependency.
- `backend/app/exercises/service.py`: filtered queries and idempotent seed transaction.
- `backend/app/exercises/router.py`: three read-only HTTP endpoints.
- `backend/app/exercises/seed_data.py`: 17 reviewable bilingual GIF-backed seed records.
- `backend/app/exercises/seed.py`: standalone seed command.
- `backend/alembic/versions/20260727_03_create_exercise_catalog.py`: catalog migration.
- `backend/alembic/env.py`: imports exercise metadata.
- `backend/app/main.py`: registers the exercise router.
- `backend/tests/database/test_exercise_models.py`: database constraints.
- `backend/tests/exercises/test_exercise_api.py`: access, filters, pagination, and detail behavior.
- `backend/tests/exercises/test_seed.py`: seed counts, content shape, associations, and idempotency.

Frontend:

- `frontend/src/features/exercises/types.ts`: API and filter types.
- `frontend/src/features/exercises/api.ts`: category, list, and detail requests.
- `frontend/src/features/exercises/api.test.ts`: request contract tests.
- `frontend/src/features/exercises/ExerciseMedia.tsx`: safe placeholder and media fallback.
- `frontend/src/features/exercises/ExerciseCatalogPage.tsx`: category selection, URL filters, states, and cards.
- `frontend/src/features/exercises/ExerciseCatalogPage.test.tsx`: catalog interaction tests.
- `frontend/src/features/exercises/ExerciseDetailPage.tsx`: bilingual exercise details and breadcrumbs.
- `frontend/src/features/exercises/ExerciseDetailPage.test.tsx`: detail and unknown-slug states.
- `frontend/src/features/exercises/exercises.css`: responsive catalog styling.
- `frontend/public/exercises/`: original fallback placeholder plus 17 approved GIF files organized by region and muscle.
- `frontend/src/App.tsx`: guarded exercise routes.
- `frontend/src/App.test.tsx`: route protection.
- `frontend/src/shared/AuthenticatedHeader.tsx`: Exercises navigation link.
- `frontend/src/pages/DashboardPage.tsx`: catalog card.
- `frontend/src/i18n/en.ts`: English catalog copy.
- `frontend/src/i18n/fa.ts`: Persian catalog copy.

Documentation:

- `docs/exercise-catalog.md`: architecture, seeding, safe additions, and future ID references.
- `docs/exercise-media-attribution.md`: media source, creator, and license registry.
- `docs/running-locally.md`: migration and seed commands.

---

### Task 1: Controlled Exercise Schema and Migration

**Files:**

- Create: `backend/app/exercises/__init__.py`
- Create: `backend/app/exercises/enums.py`
- Create: `backend/app/exercises/models.py`
- Create: `backend/alembic/versions/20260727_03_create_exercise_catalog.py`
- Modify: `backend/alembic/env.py`
- Test: `backend/tests/database/test_exercise_models.py`

**Interfaces:**

- Produces: `BodyRegion`, `MuscleGroup`, `Equipment`, `Difficulty`, `MediaType`.
- Produces: `Exercise`, `ExerciseSecondaryMuscle`, `ExerciseEquipment`, `ExerciseAlternative`.
- Database revision: `20260727_03`, down revision `20260727_02`.

- [x] **Step 1: Write failing enum and constraint tests**

Create tests that instantiate a valid exercise, reject a duplicate slug, reject raw invalid
`body_region`, `primary_muscle`, `equipment`, `difficulty`, and `media_type` inserts,
reject duplicate association rows, and reject a self-alternative.

```python
def make_exercise(slug: str = "push-up") -> Exercise:
    return Exercise(
        slug=slug,
        name_en="Push-Up",
        name_fa="شنا سوئدی",
        body_region=BodyRegion.UPPER_BODY,
        primary_muscle=MuscleGroup.CHEST,
        difficulty=Difficulty.BEGINNER,
        instructions_en=["Brace your trunk.", "Lower with control.", "Press up."],
        instructions_fa=["میان‌تنه را ثابت کن.", "کنترل‌شده پایین برو.", "بالا برو."],
        safety_notes_en=["Keep the neck neutral."],
        safety_notes_fa=["گردن را در وضعیت خنثی نگه دار."],
        media_path="/exercises/exercise-placeholder.svg",
        media_type=MediaType.PLACEHOLDER,
        media_license="Fitsho original",
        media_attribution="Fitsho",
    )
```

- [x] **Step 2: Run the model test and confirm red**

Run:

```bash
cd backend
.venv/bin/pytest tests/database/test_exercise_models.py -v
```

Expected: collection fails because `app.exercises` does not exist.

- [x] **Step 3: Add enums and ORM models**

Define exact enum members from the approved design. Use UUID primary keys, `String`
columns with SQLAlchemy non-native enums and named check constraints, JSON arrays for
instructions and safety notes, composite primary keys for association tables, cascading
foreign keys, a unique slug, and `exercise_id <> alternative_exercise_id`.

```python
class BodyRegion(StrEnum):
    UPPER_BODY = "upper_body"
    LOWER_BODY = "lower_body"
    CORE = "core"


class Exercise(Base):
    __tablename__ = "exercises"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    slug: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    name_en: Mapped[str] = mapped_column(String(160), nullable=False)
    name_fa: Mapped[str] = mapped_column(String(160), nullable=False)
    instructions_en: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    instructions_fa: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    is_active: Mapped[bool] = mapped_column(
        Boolean, server_default=true(), nullable=False
    )
```

Add `selectin` relationships ordered by controlled string value. Add indexes for
`body_region`, `primary_muscle`, `difficulty`, `is_active`, secondary `muscle`, and
association `equipment`.

- [x] **Step 4: Add the explicit Alembic migration**

Create all four tables and named constraints in dependency order. Use `sa.JSON()` for
the four structured text arrays and `sa.Uuid()` for identifiers. Downgrade drops
alternatives, equipment, secondary muscles, indexes, then exercises. Import
`app.exercises.models` in `alembic/env.py`.

- [x] **Step 5: Run migration and model checks**

Run:

```bash
cd backend
.venv/bin/alembic upgrade head
.venv/bin/pytest tests/database/test_exercise_models.py -v
.venv/bin/ruff check app/exercises tests/database/test_exercise_models.py alembic
.venv/bin/mypy app/exercises
```

Expected: all commands pass and Alembic reports revision `20260727_03`.

---

### Task 2: GIF-Only Taxonomy and Idempotent Seed

**Files:**

- Create: `backend/app/exercises/seed_data.py`
- Create: `backend/app/exercises/service.py`
- Create: `backend/app/exercises/seed.py`
- Create: `backend/tests/exercises/__init__.py`
- Create: `backend/tests/exercises/test_seed.py`
- Modify: `backend/app/exercises/enums.py`
- Modify: `backend/alembic/versions/20260727_03_create_exercise_catalog.py`
- Modify: `backend/tests/database/test_exercise_models.py`

**Interfaces:**

- Consumes: exercise enums and models from Task 1.
- Produces: immutable `ExerciseSeed` and `AlternativeSeed` dataclasses.
- Produces: `seed_exercises(db: Session) -> SeedResult`.
- Produces: `SeedResult(exercises: int, alternatives: int)`.

- [x] **Step 1: Change tests first for lower-back taxonomy and GIF-only Seed**

Assert all of these exact invariants:

```python
EXPECTED_BY_REGION = {"upper_body": 10, "lower_body": 7}
EXPECTED_BY_MUSCLE = {
    "chest": 1, "back": 1, "shoulders": 3, "biceps": 4,
    "triceps": 1, "glutes": 1, "quadriceps": 4,
    "hamstrings": 1, "calves": 1,
}
```

Assert `MuscleGroup.LOWER_BACK.value == "lower_back"` and that the category contract can
expose `abs`, `obliques`, and `lower_back` even when their counts are zero. Assert 17 unique
slugs, bilingual names, 3–6 non-empty instruction steps per language, at least one safety
note and equipment item, exactly 17 GIF media records, zero placeholder seed records, one
directed alternative, and equal row counts after calling `seed_exercises(db)` twice.

- [x] **Step 2: Run the changed tests and confirm red**

Run:

```bash
cd backend
.venv/bin/pytest tests/exercises/test_seed.py -v
```

Expected: assertions fail because the current taxonomy and manifest do not match the new contract.

- [x] **Step 3: Replace the manifest with the exact 17 GIF-backed records**

Use these stable slugs:

```text
chest:
dumbbell-bench-press

back:
barbell-bent-over-row

shoulders:
dumbbell-lateral-raise, smith-machine-shoulder-press, rear-delt-fly

biceps:
dumbbell-curl, hammer-curl, cable-curl, barbell-curl

triceps:
overhead-dumbbell-extension

glutes:
glute-bridge

quadriceps:
goblet-squat, leg-press, leg-extension, dumbbell-lunge

hamstrings:
romanian-deadlift

calves:
standing-calf-raise
```

Replace `MuscleGroup.CORE_STABILITY` with `MuscleGroup.LOWER_BACK = "lower_back"` in
`enums.py`, the migration check values, and model tests. Keep `abs` and `obliques`.
The category API in Task 3 must label the core group as `Abs / شکم`, `Obliques / پهلو`,
and `Lower Back / فیله` regardless of exercise counts.

Research concise execution and safety facts using reputable exercise-library or health
organization sources. Do not copy long passages or medical claims. Retain the reviewed
English and Persian summaries only for these records. Every record uses its exact organized
GIF path from the design spec, `media_type=MediaType.GIF`, `media_source_url=None`, license
`Project owner supplied and authorized`, and attribution
`Provided by Fitsho project owner`.

- [x] **Step 4: Keep one explicit directed alternative row**

Create these intentional replacements with bilingual reasons:

```text
leg-press -> goblet-squat
```

- [x] **Step 5: Preserve transactional idempotent upsert for the reduced manifest**

Use UUIDv5 derived from a project namespace and slug only for new seeded rows. Update
mutable seeded fields by slug, synchronize secondary muscles and equipment for those rows,
upsert the one directed alternative, preserve IDs, and do not delete non-seed rows.
Commit once on success and roll back on `SQLAlchemyError`.

```python
@dataclass(frozen=True)
class SeedResult:
    exercises: int
    alternatives: int


def seed_exercises(db: Session) -> SeedResult:
    try:
        exercises_by_slug = _upsert_exercises(db, EXERCISE_SEEDS)
        _sync_exercise_associations(db, exercises_by_slug, EXERCISE_SEEDS)
        _upsert_alternatives(db, exercises_by_slug, ALTERNATIVE_SEEDS)
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        raise
    return SeedResult(
        exercises=len(exercises_by_slug),
        alternatives=len(ALTERNATIVE_SEEDS),
    )
```

The standalone command opens `SessionLocal`, calls the service, and prints:

```text
Seeded 17 exercises and 1 alternative.
```

- [x] **Step 6: Run taxonomy and seed checks twice**

Run:

```bash
cd backend
.venv/bin/pytest tests/exercises/test_seed.py -v
.venv/bin/pytest tests/database/test_exercise_models.py -v
.venv/bin/python -m app.exercises.seed
.venv/bin/python -m app.exercises.seed
.venv/bin/ruff check app/exercises tests/exercises/test_seed.py
.venv/bin/mypy app/exercises
```

Expected: tests pass and both command runs report 17 exercises and 1 alternative. Use a
fresh isolated PostgreSQL test database so the earlier development seed run does not
affect row-count verification.

---

### Task 3: Protected Categories and Exercise APIs

**Files:**

- Create: `backend/app/exercises/dependencies.py`
- Create: `backend/app/exercises/schemas.py`
- Create: `backend/app/exercises/router.py`
- Modify: `backend/app/exercises/service.py`
- Modify: `backend/app/main.py`
- Create: `backend/tests/exercises/test_exercise_api.py`

**Interfaces:**

- Consumes: models, enums, and `get_current_user`.
- Produces: `require_completed_profile(db: DatabaseSession, user: CurrentUser) -> User`.
- Produces: `list_exercises(db, filters) -> tuple[list[Exercise], int]`.
- Produces: `get_active_exercise_by_slug(db, slug) -> Exercise | None`.
- Routes: `/api/v1/exercise-categories`, `/api/v1/exercises`, `/api/v1/exercises/{slug}`.

- [x] **Step 1: Write failing API access and contract tests**

Create registered users with and without `UserProfile`. Seed inside each test transaction.
Assert guest `401`, missing profile `403`, ready profile `200`, exact category order and
bilingual labels, inactive exclusion, active detail response, and inactive/unknown slug
`404`.

```python
assert client.get("/api/v1/exercises").status_code == 401
assert ready_client.get("/api/v1/exercises/not-a-slug").status_code == 404
core = ready_client.get("/api/v1/exercise-categories").json()["core"]
assert [(item["value"], item["name_fa"]) for item in core] == [
    ("abs", "شکم"),
    ("obliques", "پهلو"),
    ("lower_back", "فیله"),
]
```

- [x] **Step 2: Write failing filter and pagination tests**

Assert body region, primary muscle, equipment, difficulty, Persian search, English
search, page boundaries, total count, and invalid enum/page values. Verify combined filters
use AND semantics and results are ordered by `name_en`, then `id`.

- [x] **Step 3: Run API tests and confirm red**

Run:

```bash
cd backend
.venv/bin/pytest tests/exercises/test_exercise_api.py -v
```

Expected: collection fails because schemas and router do not exist.

- [x] **Step 4: Implement completed-profile dependency**

Depend on `get_current_user`, query `UserProfile.user_id`, and return the current user.
Raise:

```python
HTTPException(
    status_code=status.HTTP_403_FORBIDDEN,
    detail="Completed fitness profile required",
)
```

when the profile row is absent.

- [x] **Step 5: Implement schemas and service queries**

Define:

```python
class ExerciseFilters(BaseModel):
    body_region: BodyRegion | None = None
    primary_muscle: MuscleGroup | None = None
    equipment: Equipment | None = None
    difficulty: Difficulty | None = None
    search: str | None = Field(default=None, min_length=1, max_length=100)
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=12, ge=1, le=50)


class PaginatedExercises(BaseModel):
    items: list[ExerciseSummary]
    page: int
    page_size: int
    total: int
    total_pages: int
```

Use `EXISTS` for equipment, `ILIKE` with escaped user input for search, a separate
count query, offset pagination, and `selectinload` for collections. Return sorted unique
equipment and secondary-muscle values.

- [x] **Step 6: Implement the three read-only routes**

Categories return static taxonomy from enums and label mappings, including the empty core
groups `abs`, `obliques`, and `lower_back`. List uses typed FastAPI
query parameters so invalid values produce `422`. Detail returns `404` for missing or
inactive slugs. All routes depend on `require_completed_profile`. Register the router in
`app.main`.

- [x] **Step 7: Run backend API checks**

Run:

```bash
cd backend
.venv/bin/pytest tests/exercises/test_exercise_api.py -v
.venv/bin/ruff check app/exercises app/main.py tests/exercises
.venv/bin/mypy app/exercises app/main.py
```

Expected: all commands pass.

---

### Task 4: Frontend API Contracts and Media Placeholder

**Files:**

- Create: `frontend/src/features/exercises/types.ts`
- Create: `frontend/src/features/exercises/api.ts`
- Create: `frontend/src/features/exercises/api.test.ts`
- Create: `frontend/src/features/exercises/ExerciseMedia.tsx`
- Create: `frontend/src/features/exercises/ExerciseMedia.test.tsx`
- Create: `frontend/public/exercises/exercise-placeholder.svg`
- Create: 17 approved GIF files under the region/muscle paths in the design spec

**Interfaces:**

- Produces: controlled TypeScript string unions and API response types.
- Produces: `getExerciseCategories()`, `getExercises(filters)`, `getExercise(slug)`.
- Produces: `ExerciseMedia({ path, name, mediaType })`.

- [x] **Step 1: Write failing request-contract tests**

Mock fetch and assert credentials come from the shared client, filters are encoded with
`URLSearchParams`, empty values are omitted, slugs are encoded, and `404` detail returns
`null` while other errors remain `ApiError`.

```ts
await getExercises({
  body_region: "upper_body",
  primary_muscle: "chest",
  page: 2,
});
expect(fetch).toHaveBeenCalledWith(
  "/api/v1/exercises?body_region=upper_body&primary_muscle=chest&page=2",
  expect.objectContaining({ credentials: "include" }),
);
```

- [x] **Step 2: Write failing media tests**

Assert placeholder rendering for `media_type="placeholder"`, meaningful localized alt
text, no autoplay, and fallback to the shared placeholder after an image error.

- [x] **Step 3: Run focused frontend tests and confirm red**

Run:

```bash
cd frontend
npm test -- src/features/exercises/api.test.ts src/features/exercises/ExerciseMedia.test.tsx
```

Expected: tests fail because the exercise modules do not exist.

- [x] **Step 4: Add types, API functions, original SVG, and approved media**

Mirror backend enum literals exactly. Define `ExerciseSummary`, `ExerciseDetail`,
`ExerciseCategory`, `PaginatedExercises`, and `ExerciseFilters`. Use the shared
`request<T>()` only. Create an original, non-photographic Fitsho SVG using existing petrol,
turquoise, persimmon, and saffron colors; include no third-party marks or embedded data.
Copy only the 17 approved GIF files, rename them to their target slugs, preserve their
bytes, and place them under the approved region/muscle directories. Do not commit the ZIP,
inspection directory, ambiguous files, or duplicate files.

- [x] **Step 5: Implement safe media rendering**

Use `<img>` for `image`, `animated_webp`, and `gif`; use `<video controls muted playsInline>`
for `video`; render the shared placeholder for placeholder or failed media. Never use
`autoPlay`.

- [x] **Step 6: Run frontend contract checks**

Run:

```bash
cd frontend
npm test -- src/features/exercises/api.test.ts src/features/exercises/ExerciseMedia.test.tsx
npm run lint
npm run build
```

Expected: all commands pass.

---

### Task 5: Catalog Browsing Page

**Files:**

- Create: `frontend/src/features/exercises/ExerciseCatalogPage.tsx`
- Create: `frontend/src/features/exercises/ExerciseCatalogPage.test.tsx`
- Create: `frontend/src/features/exercises/exercises.css`
- Modify: `frontend/src/i18n/en.ts`
- Modify: `frontend/src/i18n/fa.ts`

**Interfaces:**

- Consumes: Task 4 API functions, types, and `ExerciseMedia`.
- Produces: `ExerciseCatalogPage`.
- URL keys: `body_region`, `primary_muscle`, `equipment`, `difficulty`, `search`, `page`.

- [x] **Step 1: Write failing category-flow tests**

Mock API modules and assert initial region buttons, correct upper/lower/core labels, muscles
only after region selection, cards only after muscle selection, both names, card metadata,
detail links preserving query parameters, and breadcrumb reset actions.

- [x] **Step 2: Write failing filter and state tests**

Assert semantic labels, query-string updates, equipment/difficulty/search filters, page
reset after filter changes, loading, API failure with retry, empty results, no-match copy,
and keyboard activation of region and muscle buttons.

- [x] **Step 3: Run catalog tests and confirm red**

Run:

```bash
cd frontend
npm test -- src/features/exercises/ExerciseCatalogPage.test.tsx
```

Expected: test collection fails because `ExerciseCatalogPage` does not exist.

- [x] **Step 4: Implement URL-driven data flow**

Load categories on mount. Parse only known query keys. Fetch exercises only when both
region and muscle are selected. Use `AbortController` or an active-request guard to prevent
stale results. Region change removes muscle and page; muscle/filter changes reset page.
Retry increments a request generation without changing filters.

- [x] **Step 5: Implement accessible catalog markup**

Use `<main>`, labeled `<nav>` breadcrumbs, `<section>` headings, button groups, labeled
`<select>` and search input, `<article>` cards, and navigation links. Put the active-language
name first and the other-language name beneath it with explicit `dir`.

- [x] **Step 6: Add responsive styles and bilingual copy**

Use existing CSS variables, 82rem content width, asymmetrical Fitsho radii, visible focus,
responsive auto-fit cards, logical properties, RTL/LTR-safe alignment, and reduced-motion
support. Add exact English/Persian labels for every region, muscle, equipment, difficulty,
state, action, and breadcrumb.

- [x] **Step 7: Run catalog checks**

Run:

```bash
cd frontend
npm test -- src/features/exercises/ExerciseCatalogPage.test.tsx
npm run lint
npm run build
```

Expected: all commands pass.

---

### Task 6: Detail Page, Routes, Header, and Dashboard

**Files:**

- Create: `frontend/src/features/exercises/ExerciseDetailPage.tsx`
- Create: `frontend/src/features/exercises/ExerciseDetailPage.test.tsx`
- Modify: `frontend/src/features/exercises/exercises.css`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/App.test.tsx`
- Modify: `frontend/src/shared/AuthenticatedHeader.tsx`
- Modify: `frontend/src/pages/DashboardPage.tsx`
- Modify: `frontend/src/i18n/en.ts`
- Modify: `frontend/src/i18n/fa.ts`

**Interfaces:**

- Consumes: `getExercise`, exercise types, and `ExerciseMedia`.
- Produces: `ExerciseDetailPage`.
- Routes: `/exercises`, `/exercises/:slug`.

- [x] **Step 1: Write failing detail tests**

Assert loading, API failure and retry, `404` unknown exercise, both names with RTL/LTR,
media, primary and secondary muscles, equipment, difficulty, ordered instructions,
safety notes, breadcrumb, and back link preserving the current query string.

- [x] **Step 2: Extend failing route and navigation tests**

Assert guests visiting either exercise route reach login, authenticated users without a
profile reach onboarding, ready users render catalog/detail, the header marks all exercise
paths active, and the dashboard catalog card links to `/exercises`.

- [x] **Step 3: Run focused tests and confirm red**

Run:

```bash
cd frontend
npm test -- src/features/exercises/ExerciseDetailPage.test.tsx src/App.test.tsx
```

Expected: tests fail because the detail page and routes are absent.

- [x] **Step 4: Implement detail states and content**

Read `slug` from route params and preserve `location.search` for catalog navigation. Treat
`null` as the localized unknown state and other failures as retryable. Render semantic
definition lists, ordered instruction lists, safety note section, and `ExerciseMedia`.

- [x] **Step 5: Register routes and navigation**

Add both routes inside the existing `CompletedProfileRoute`. Add the header item beside
Dashboard and Profile using:

```ts
location.pathname.startsWith("/exercises")
```

for `aria-current`. Add a distinct dashboard catalog card without changing profile-card
behavior.

- [x] **Step 6: Finish detail/dashboard styles and translations**

Add responsive detail layout, media aspect ratio, badges, list spacing, unknown/error
panels, and a catalog dashboard-card variation. Keep all controls labeled and focus-visible.

- [x] **Step 7: Run frontend feature checks**

Run:

```bash
cd frontend
npm test -- src/features/exercises src/App.test.tsx
npm run lint
npm run build
```

Expected: all commands pass.

---

### Task 7: Documentation and Media Licensing

**Files:**

- Create: `docs/exercise-catalog.md`
- Create: `docs/exercise-media-attribution.md`
- Modify: `docs/running-locally.md`

**Interfaces:**

- Documents: `python -m app.exercises.seed`.
- Documents: future workout-plan foreign keys target `exercises.id`.

- [x] **Step 1: Write catalog operations documentation**

Document module boundaries, four tables, controlled values, filtering, deterministic IDs,
idempotent upsert behavior, migration order, exact seed command, adding a bilingual record,
association synchronization, and safe alternative curation.

- [x] **Step 2: Write media policy and directory structure**

Document:

```text
frontend/public/exercises/
├── exercise-placeholder.svg
├── upper-body/{chest,back,shoulders,biceps,triceps,traps}/
├── lower-body/{glutes,quadriceps,hamstrings,adductors,calves}/
└── core/{abs,obliques,lower-back}/
```

Require local files, verified Public Domain/CC0/CC BY/CC BY-SA terms, source URL, creator,
license, attribution, and ShareAlike compliance. Forbid scraping and hotlinking.

- [x] **Step 3: Add the attribution registry**

Register `exercise-placeholder.svg` as original Fitsho project artwork with source `local`,
creator `Fitsho`, license `project-owned`, and attribution `not required`. Register all 17
owner-authorized assets with final path, original archive filename, provider
`Fitsho project owner`, license `Project owner supplied and authorized`, and attribution
`Provided by Fitsho project owner`.

- [x] **Step 4: Update local-running commands**

Add:

```bash
cd backend
.venv/bin/alembic upgrade head
.venv/bin/python -m app.exercises.seed
```

and explain that rerunning seed is safe.

- [x] **Step 5: Check documentation and working tree**

Run:

```bash
git diff --check
rg -n "exercise|media|seed|exercises.id" docs
git status --short
```

Expected: no whitespace errors; new documentation and feature files are listed.

---

### Task 8: Full Verification and One Focused Commit

**Files:**

- Verify all files from Tasks 1–7.
- Commit the complete feature once.

**Interfaces:**

- Produces: verified branch `feature/exercise-catalog`.

- [x] **Step 1: Start and verify PostgreSQL**

Run:

```bash
docker compose up -d db
docker compose ps
```

Expected: `fitsho-db-1` is `healthy`.

- [x] **Step 2: Verify migrations from the current database**

Run:

```bash
cd backend
.venv/bin/alembic upgrade head
.venv/bin/alembic current
```

Expected: current revision is `20260727_03 (head)`.

- [x] **Step 3: Run the complete backend suite**

Run:

```bash
cd backend
.venv/bin/pytest
.venv/bin/ruff check app tests alembic
.venv/bin/ruff format --check app tests alembic
.venv/bin/mypy app tests
```

Expected: every test passes and Ruff/mypy exit with status 0.

- [x] **Step 4: Run seed twice against the local database**

Run:

```bash
cd backend
.venv/bin/python -m app.exercises.seed
.venv/bin/python -m app.exercises.seed
```

Expected twice:

```text
Seeded 17 exercises and 1 alternative.
```

- [x] **Step 5: Run the complete frontend suite**

Run:

```bash
cd frontend
npm test
npm run lint
npm run build
```

Expected: every Vitest test passes, lint exits 0, and Vite produces `dist`.

- [x] **Step 6: Verify migration downgrade and re-upgrade**

Run:

```bash
cd backend
.venv/bin/alembic downgrade 20260727_02
.venv/bin/alembic upgrade head
```

Expected: both commands exit 0. Run the seed command once again after upgrade.

- [x] **Step 7: Review exact feature scope**

Run:

```bash
git diff --check
git status --short
git diff --stat
```

Confirm no `.env`, credentials, web-downloaded or unapproved media, ZIP archives,
inspection files, unrelated auth/profile redesign, build output, or database files are
staged.

- [ ] **Step 8: Show and create the requested commit**

Proposed commit message:

```text
feat(exercises): add browsable exercise catalog
```

Stage only the files listed in this plan, commit once, and capture:

```bash
git rev-parse HEAD
git status -sb
```

Expected: clean `feature/exercise-catalog` branch and one new feature commit.

- [ ] **Step 9: Push the current branch**

Run:

```bash
git push -u origin feature/exercise-catalog
```

Expected: remote branch updates successfully. Do not force-push.
