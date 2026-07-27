# User Onboarding and Fitness Profile Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** ساخت جریان کامل onboarding و پروفایل ورزشی که کاربر authenticated بدون پروفایل را به `/onboarding` هدایت کند، اطلاعات پایدار را one-to-one ذخیره کند و تغییرات وزن را به‌صورت append-only نگه دارد.

**Architecture:** backend یک ماژول مستقل `profile` داخل FastAPI modular monolith خواهد داشت و `POST`، `GET` و `PATCH /api/v1/profile` را ارائه می‌کند. frontend پس از مشخص‌شدن session، profile را در `ProfileProvider` جداگانه بارگیری می‌کند و route guardها میان مهمان، کاربر بدون profile، کاربر دارای profile و خطای موقت تمایز می‌گذارند.

**Tech Stack:** Python 3.12+, FastAPI, Pydantic 2, SQLAlchemy 2, Alembic, PostgreSQL 18, pytest, React 19, TypeScript 6, React Router 7, i18next, Vitest, React Testing Library, CSS

## Global Constraints

- سند طراحی مرجع: `docs/superpowers/specs/2026-07-27-user-onboarding-fitness-profile-design.md`
- پیاده‌سازی از آخرین commit شاخه `feature/authentication` که spec و plan تأییدشده را دارد منشعب شود و در worktree جدا با شاخه `feature/onboarding-profile` انجام شود.
- پیش از اجرای Task 1 از skill `superpowers:using-git-worktrees` استفاده شود.
- هر task با چرخه red، green و regression انجام و سپس در commit مستقل push شود.
- فایل‌های تغییرکرده کاربر، به‌ویژه `README.md` و `AGENTS.md`، بدون هماهنگی stage یا ویرایش نشوند.
- هیچ secret، `.env` یا credential وارد commit نشود.
- backend هم‌زمان و مبتنی بر `SQLAlchemy Session` فعلی باقی بماند؛ async database access و repository layer اضافه نشود.
- dependency جدید backend یا frontend اضافه نشود.
- سن مجاز دقیقاً `18` تا `100` سال کامل است.
- قد مجاز `100` تا `250` سانتی‌متر است.
- وزن مجاز `20` تا `500` کیلوگرم با حداکثر دو رقم اعشار است.
- تعداد روز تمرین دقیقاً `1` تا `7` است.
- `physical_limitations` اختیاری و حداکثر `1000` کاراکتر است.
- وزن قبلی هرگز update یا delete نشود؛ وزن متفاوت measurement جدید بسازد و وزن یکسان رکورد تکراری نسازد.
- فقط `404` از `GET /api/v1/profile` به معنی onboarding ناقص است؛ خطای شبکه یا `503` باید retry state ایجاد کند.
- اطلاعات onboarding ناقص در `localStorage`، `sessionStorage` یا backend ذخیره نشود.
- رابط فارسی و انگلیسی، RTL/LTR، keyboard navigation و screen-reader feedback حفظ شوند.
- workout generation، nutrition planning، AI، progress chart، measurement-history UI، Redis، cache، Celery و Playwright خارج از scope هستند.
- تست backend روی PostgreSQL واقعی اجرا شود؛ SQLite مجاز نیست.

---

## File Map

### Backend files

Create:

```text
backend/app/profile/__init__.py
backend/app/profile/enums.py
backend/app/profile/models.py
backend/app/profile/schemas.py
backend/app/profile/exceptions.py
backend/app/profile/service.py
backend/app/profile/router.py
backend/alembic/versions/20260727_02_create_fitness_profiles.py
backend/tests/database/test_profile_models.py
backend/tests/profile/__init__.py
backend/tests/profile/test_schemas.py
backend/tests/profile/test_profile_api.py
```

Modify:

```text
backend/alembic/env.py
backend/app/main.py
```

Responsibilities:

- `enums.py` تنها vocabulary پایدار domain را تعریف می‌کند.
- `models.py` فقط mapping و database constraintها را نگه می‌دارد.
- `schemas.py` normalization و request/response validation را انجام می‌دهد.
- `service.py` مالک queryها، transactionها و append-only weight behavior است.
- `router.py` dependencyهای HTTP و نگاشت domain error به status code را انجام می‌دهد.
- migration ساختار دیتابیس را مستقل از ORM و بدون seed data بازتولید می‌کند.

### Frontend files

Create:

```text
frontend/src/shared/apiClient.ts
frontend/src/shared/apiClient.test.ts
frontend/src/shared/AuthenticatedHeader.tsx
frontend/src/features/profile/types.ts
frontend/src/features/profile/api.ts
frontend/src/features/profile/api.test.ts
frontend/src/features/profile/profileValidation.ts
frontend/src/features/profile/profileValidation.test.ts
frontend/src/features/profile/ProfileContext.tsx
frontend/src/features/profile/ProfileContext.test.tsx
frontend/src/features/profile/ProfileRouteGuards.tsx
frontend/src/features/profile/ProfileRouteGuards.test.tsx
frontend/src/features/profile/ProfileFormFields.tsx
frontend/src/features/profile/OnboardingPage.tsx
frontend/src/features/profile/OnboardingPage.test.tsx
frontend/src/features/profile/ProfilePage.tsx
frontend/src/features/profile/ProfilePage.test.tsx
frontend/src/features/profile/profile.css
```

Modify:

```text
frontend/src/features/auth/api.ts
frontend/src/features/auth/types.ts
frontend/src/features/auth/authError.ts
frontend/src/features/auth/authError.test.ts
frontend/src/App.tsx
frontend/src/App.test.tsx
frontend/src/pages/DashboardPage.tsx
frontend/src/i18n/fa.ts
frontend/src/i18n/en.ts
```

Responsibilities:

- `shared/apiClient.ts` تنها transport عمومی fetch و `ApiError` را نگه می‌دارد.
- `profile/types.ts` قراردادهای TypeScript و enum literalها را تعریف می‌کند.
- `profileValidation.ts` توابع pure برای validation و تبدیل form value به API payload است.
- `ProfileContext.tsx` فقط lifecycle دریافت، ساخت، update و retry پروفایل را مدیریت می‌کند.
- `ProfileRouteGuards.tsx` فقط تصمیم route را می‌گیرد و فرم یا data mutation ندارد.
- `ProfileFormFields.tsx` سه گروه field قابل استفاده در onboarding و edit را render می‌کند.
- pageها state فرم، submit و feedback کاربر را مدیریت می‌کنند.
- `profile.css` ظاهر responsive و قابل دسترس صفحات profile را از CSS احراز هویت جدا می‌کند.

---

### Task 1: Profile database model and migration

**Files:**
- Create: `backend/app/profile/__init__.py`
- Create: `backend/app/profile/enums.py`
- Create: `backend/app/profile/models.py`
- Create: `backend/alembic/versions/20260727_02_create_fitness_profiles.py`
- Create: `backend/tests/database/test_profile_models.py`
- Modify: `backend/alembic/env.py`

**Interfaces:**
- Consumes: `app.auth.models.User`, `app.database.base.Base`, Alembic revision `20260724_01`
- Produces: `Sex`, `FitnessGoal`, `ExperienceLevel`, `UserProfile`, `BodyMeasurement`

- [ ] **Step 1: Write failing database model tests**

Create tests with these exact behaviors:

```python
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.models import User
from app.profile.enums import ExperienceLevel, FitnessGoal, Sex
from app.profile.models import BodyMeasurement, UserProfile


def make_user(db: Session, email: str) -> User:
    user = User(email=email, password_hash="hash")
    db.add(user)
    db.flush()
    return user


def make_profile(user: User) -> UserProfile:
    return UserProfile(
        user_id=user.id,
        display_name="Test User",
        birth_date=date(2000, 1, 1),
        sex=Sex.PREFER_NOT_TO_SAY,
        height_cm=175,
        fitness_goal=FitnessGoal.IMPROVE_FITNESS,
        experience_level=ExperienceLevel.BEGINNER,
        training_days_per_week=3,
        physical_limitations=None,
    )


def test_user_can_have_only_one_profile(db: Session) -> None:
    user = make_user(db, "one-profile@example.com")
    db.add(make_profile(user))
    db.flush()
    db.add(make_profile(user))

    with pytest.raises(IntegrityError):
        db.flush()


def test_weight_is_decimal_and_history_is_many_to_one(db: Session) -> None:
    user = make_user(db, "weights@example.com")
    db.add(make_profile(user))
    db.add_all(
        [
            BodyMeasurement(user_id=user.id, weight_kg=Decimal("72.35")),
            BodyMeasurement(user_id=user.id, weight_kg=Decimal("71.90")),
        ]
    )
    db.flush()

    weights = db.scalars(
        select(BodyMeasurement.weight_kg).where(BodyMeasurement.user_id == user.id)
    ).all()
    assert set(weights) == {Decimal("72.35"), Decimal("71.90")}


def test_deleting_user_cascades_profile_and_measurements(db: Session) -> None:
    user = make_user(db, "cascade@example.com")
    profile = make_profile(user)
    measurement = BodyMeasurement(user_id=user.id, weight_kg=Decimal("80.00"))
    db.add_all([profile, measurement])
    db.flush()

    db.delete(user)
    db.flush()

    assert db.get(UserProfile, user.id) is None
    assert db.get(BodyMeasurement, measurement.id) is None
```

- [ ] **Step 2: Run the model tests and verify red**

Run:

```bash
cd backend
TEST_DATABASE_URL=postgresql+psycopg://fitsho:fitsho@localhost:5432/fitsho_test .venv/bin/pytest tests/database/test_profile_models.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'app.profile'`.

- [ ] **Step 3: Define domain enums and ORM models**

Create string enums with these exact member/value pairs:

```python
class Sex(StrEnum):
    FEMALE = "female"
    MALE = "male"
    OTHER = "other"
    PREFER_NOT_TO_SAY = "prefer_not_to_say"


class FitnessGoal(StrEnum):
    LOSE_WEIGHT = "lose_weight"
    BUILD_MUSCLE = "build_muscle"
    IMPROVE_FITNESS = "improve_fitness"
    MAINTAIN_WEIGHT = "maintain_weight"


class ExperienceLevel(StrEnum):
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"
```

Implement `UserProfile` with `user_id` as the shared primary key, `Date`, `SmallInteger`, timestamps and named check constraints. Implement `BodyMeasurement` with UUID primary key, `Numeric(5, 2)`, server timestamp and the composite lookup index. Use non-native SQLAlchemy enums:

```python
mapped_column(
    Enum(
        Sex,
        native_enum=False,
        create_constraint=True,
        validate_strings=True,
        values_callable=lambda members: [member.value for member in members],
        name="ck_user_profiles_sex_values",
    ),
    nullable=False,
)
```

Name range constraints exactly:

```text
ck_user_profiles_display_name_length
ck_user_profiles_height_cm_range
ck_user_profiles_training_days_range
ck_user_profiles_limitations_length
ck_body_measurements_weight_kg_range
```

- [ ] **Step 4: Add the explicit Alembic revision**

Create revision `20260727_02` with `down_revision = "20260724_01"`. The migration must create `user_profiles` before `body_measurements`, reproduce every PK/FK/check constraint from the ORM, and create:

```python
op.create_index(
    "ix_body_measurements_user_id_measured_at",
    "body_measurements",
    ["user_id", "measured_at"],
)
```

Downgrade must drop the index, `body_measurements`, then `user_profiles`. Add this import to Alembic metadata discovery:

```python
from app.profile import models as profile_models  # noqa: F401
```

- [ ] **Step 5: Apply the migration and verify green**

Run:

```bash
cd backend
DATABASE_URL=postgresql+psycopg://fitsho:fitsho@localhost:5432/fitsho_test .venv/bin/alembic upgrade head
TEST_DATABASE_URL=postgresql+psycopg://fitsho:fitsho@localhost:5432/fitsho_test .venv/bin/pytest tests/database/test_profile_models.py -v
.venv/bin/ruff check app/profile tests/database/test_profile_models.py alembic/versions/20260727_02_create_fitness_profiles.py
.venv/bin/mypy app/profile
```

Expected: migration and all checks PASS.

- [ ] **Step 6: Commit and push the database slice**

```bash
git add backend/app/profile backend/alembic/env.py backend/alembic/versions/20260727_02_create_fitness_profiles.py backend/tests/database/test_profile_models.py
git commit -m "feat: add fitness profile data model"
git push -u origin feature/onboarding-profile
```

Confirm GitHub contains only this task before continuing.

---

### Task 2: Backend profile schemas and validation

**Files:**
- Create: `backend/app/profile/schemas.py`
- Create: `backend/tests/profile/__init__.py`
- Create: `backend/tests/profile/test_schemas.py`

**Interfaces:**
- Consumes: `Sex`, `FitnessGoal`, `ExperienceLevel`
- Produces: `calculate_age(birth_date: date, today: date) -> int`, `ProfileCreate`, `ProfileUpdate`, `ProfileResponse`

- [ ] **Step 1: Write failing schema tests**

Cover exact boundaries and normalization:

```python
from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.profile.schemas import ProfileCreate, ProfileUpdate, calculate_age


def valid_payload() -> dict[str, object]:
    return {
        "display_name": "  Mohammad  ",
        "birth_date": date(2000, 5, 14),
        "sex": "male",
        "height_cm": 178,
        "current_weight_kg": "76.50",
        "fitness_goal": "build_muscle",
        "experience_level": "beginner",
        "training_days_per_week": 3,
        "physical_limitations": "   ",
    }


def test_profile_create_normalizes_text_and_decimal() -> None:
    profile = ProfileCreate.model_validate(valid_payload())
    assert profile.display_name == "Mohammad"
    assert profile.current_weight_kg == Decimal("76.50")
    assert profile.physical_limitations is None


def test_calculate_age_handles_birthday_boundary() -> None:
    today = date(2026, 7, 27)
    assert calculate_age(date(2008, 7, 27), today) == 18
    assert calculate_age(date(2008, 7, 28), today) == 17


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("height_cm", 99),
        ("height_cm", 251),
        ("current_weight_kg", "19.99"),
        ("current_weight_kg", "500.01"),
        ("current_weight_kg", "70.123"),
        ("training_days_per_week", 0),
        ("training_days_per_week", 8),
        ("sex", "unknown"),
        ("fitness_goal", "bulk"),
        ("experience_level", "expert"),
    ],
)
def test_profile_create_rejects_invalid_values(field: str, value: object) -> None:
    payload = valid_payload()
    payload[field] = value
    with pytest.raises(ValidationError):
        ProfileCreate.model_validate(payload)


def test_profile_update_rejects_empty_body_and_null_required_field() -> None:
    with pytest.raises(ValidationError):
        ProfileUpdate.model_validate({})
    with pytest.raises(ValidationError):
        ProfileUpdate.model_validate({"height_cm": None})


def test_profile_update_allows_clearing_limitations() -> None:
    update = ProfileUpdate.model_validate({"physical_limitations": None})
    assert update.model_fields_set == {"physical_limitations"}
```

Add date tests for exactly 18, exactly 100, younger than 18, older than 100, and future dates. Compute boundary birth dates relative to `date.today()` when exercising `ProfileCreate`; use the fixed date only for `calculate_age` unit tests.

- [ ] **Step 2: Run schema tests and verify red**

```bash
cd backend
.venv/bin/pytest tests/profile/test_schemas.py -v
```

Expected: FAIL because `app.profile.schemas` does not exist.

- [ ] **Step 3: Implement normalized create/update schemas**

Use `Field`, `field_validator` and `model_validator`. Required update fields may be omitted but must reject explicit `null`; only `physical_limitations` accepts explicit `null`. Reject an empty patch with the stable message `At least one profile field is required`.

Define response fields exactly:

```python
class ProfileResponse(BaseModel):
    user_id: UUID
    display_name: str
    birth_date: date
    sex: Sex
    height_cm: int
    current_weight_kg: float
    weight_measured_at: datetime
    fitness_goal: FitnessGoal
    experience_level: ExperienceLevel
    training_days_per_week: int
    physical_limitations: str | None
    created_at: datetime
    updated_at: datetime
```

Keep request weight as `Decimal`; expose response weight as JSON number through `float`.

- [ ] **Step 4: Run schema checks and regression**

```bash
cd backend
.venv/bin/pytest tests/profile/test_schemas.py tests/auth -v
.venv/bin/ruff check app/profile/schemas.py tests/profile/test_schemas.py
.venv/bin/mypy app/profile
```

Expected: PASS.

- [ ] **Step 5: Commit and push schema validation**

```bash
git add backend/app/profile/schemas.py backend/tests/profile
git commit -m "feat: validate fitness profile payloads"
git push
```

---

### Task 3: Create and read profile APIs

**Files:**
- Create: `backend/app/profile/exceptions.py`
- Create: `backend/app/profile/service.py`
- Create: `backend/app/profile/router.py`
- Create: `backend/tests/profile/test_profile_api.py`
- Modify: `backend/app/main.py`

**Interfaces:**
- Consumes: `get_current_user`, `require_trusted_origin`, `ProfileCreate`, `ProfileResponse`, ORM models
- Produces: `ProfileSnapshot`, `create_profile(db, user_id, payload)`, `get_profile(db, user_id)`, registered `/api/v1/profile` router

- [ ] **Step 1: Write failing create/read API tests**

Define one valid payload constant and a registration helper. Add these exact cases:

```python
ORIGIN = {"Origin": "http://localhost:5173"}
VALID_PROFILE = {
    "display_name": "  Mohammad  ",
    "birth_date": "2000-05-14",
    "sex": "male",
    "height_cm": 178,
    "current_weight_kg": 76.5,
    "fitness_goal": "build_muscle",
    "experience_level": "beginner",
    "training_days_per_week": 3,
    "physical_limitations": None,
}


def register(client: TestClient, email: str = "profile@example.com") -> UUID:
    response = client.post(
        "/api/v1/auth/register",
        headers=ORIGIN,
        json={"email": email, "password": "long password"},
    )
    assert response.status_code == 201
    return UUID(response.json()["id"])


def test_create_profile_atomically_stores_profile_and_initial_weight(
    client: TestClient, db: Session
) -> None:
    user_id = register(client)
    response = client.post("/api/v1/profile", headers=ORIGIN, json=VALID_PROFILE)

    assert response.status_code == 201
    assert response.json()["display_name"] == "Mohammad"
    assert response.json()["current_weight_kg"] == 76.5
    assert db.get(UserProfile, user_id) is not None
    measurements = db.scalars(
        select(BodyMeasurement).where(BodyMeasurement.user_id == user_id)
    ).all()
    assert len(measurements) == 1


def test_get_profile_returns_404_until_onboarding_is_complete(client: TestClient) -> None:
    register(client)
    response = client.get("/api/v1/profile")
    assert response.status_code == 404
    assert response.json() == {"detail": "Fitness profile not found"}


def test_profile_endpoints_require_authentication(client: TestClient) -> None:
    assert client.get("/api/v1/profile").status_code == 401
    assert client.post("/api/v1/profile", headers=ORIGIN, json=VALID_PROFILE).status_code == 401


def test_create_profile_rejects_duplicate_and_untrusted_origin(client: TestClient) -> None:
    register(client)
    assert client.post("/api/v1/profile", headers=ORIGIN, json=VALID_PROFILE).status_code == 201
    assert client.post("/api/v1/profile", headers=ORIGIN, json=VALID_PROFILE).status_code == 409
    assert client.post("/api/v1/profile", json=VALID_PROFILE).status_code == 403
```

Also add:

- a two-user ownership test that creates user A and its profile, logs out, creates user B and its profile, then logs back into each account and proves each GET returns only that account profile;
- a commit-failure test that monkeypatches `db.commit`, expects `503`, and asserts neither profile nor measurement remains after rollback;
- a validation-error test proving rejected sensitive text is absent from the safe `422` body.

- [ ] **Step 2: Run API tests and verify red**

```bash
cd backend
TEST_DATABASE_URL=postgresql+psycopg://fitsho:fitsho@localhost:5432/fitsho_test .venv/bin/pytest tests/profile/test_profile_api.py -v
```

Expected: FAIL with `404` for the unregistered profile routes.

- [ ] **Step 3: Implement domain errors and service transactions**

Define:

```python
class ProfileAlreadyExistsError(Exception):
    pass


class ProfileNotFoundError(Exception):
    pass


class ProfileInvariantError(Exception):
    pass


@dataclass(frozen=True)
class ProfileSnapshot:
    profile: UserProfile
    measurement: BodyMeasurement
```

Implement `create_profile(db: Session, user_id: UUID, payload: ProfileCreate) -> ProfileSnapshot`
and `get_profile(db: Session, user_id: UUID) -> ProfileSnapshot` with concrete
SQLAlchemy statements in `service.py`.

The service implementation must use concrete SQLAlchemy statements and be fully implemented. `create_profile` performs `flush`, adds the measurement, commits, refreshes server-generated values and rolls back on every `IntegrityError` or `SQLAlchemyError`. `get_profile` orders measurements by `measured_at.desc()` and `id.desc()` and raises `ProfileInvariantError` if a profile exists without a measurement.

- [ ] **Step 4: Add router and response mapping**

Register a router with prefix `/api/v1/profile`. `POST ""` returns `201`, requires trusted origin and maps duplicate to `409`. `GET ""` maps missing to `404`. Both derive `user.id` from `get_current_user`; neither accepts user identity from request data.

Map a snapshot explicitly:

```python
def to_response(snapshot: ProfileSnapshot) -> ProfileResponse:
    profile = snapshot.profile
    measurement = snapshot.measurement
    return ProfileResponse(
        user_id=profile.user_id,
        display_name=profile.display_name,
        birth_date=profile.birth_date,
        sex=profile.sex,
        height_cm=profile.height_cm,
        current_weight_kg=float(measurement.weight_kg),
        weight_measured_at=measurement.measured_at,
        fitness_goal=profile.fitness_goal,
        experience_level=profile.experience_level,
        training_days_per_week=profile.training_days_per_week,
        physical_limitations=profile.physical_limitations,
        created_at=profile.created_at,
        updated_at=profile.updated_at,
    )
```

Map `ProfileInvariantError` to the same safe `503` detail used by the global database handler. Include the router in `create_app`.

- [ ] **Step 5: Run create/read tests and backend regression**

```bash
cd backend
TEST_DATABASE_URL=postgresql+psycopg://fitsho:fitsho@localhost:5432/fitsho_test .venv/bin/pytest tests/profile/test_profile_api.py tests/auth tests/database -v
.venv/bin/ruff check app tests
.venv/bin/mypy app
```

Expected: PASS.

- [ ] **Step 6: Commit and push create/read API**

```bash
git add backend/app/profile backend/app/main.py backend/tests/profile/test_profile_api.py
git commit -m "feat: add profile create and read APIs"
git push
```

---

### Task 4: Update profile API and append-only weight

**Files:**
- Modify: `backend/app/profile/service.py`
- Modify: `backend/app/profile/router.py`
- Modify: `backend/app/main.py`
- Modify: `backend/tests/profile/test_profile_api.py`

**Interfaces:**
- Consumes: `ProfileUpdate`, `ProfileSnapshot`
- Produces: `update_profile(db: Session, user_id: UUID, payload: ProfileUpdate) -> ProfileSnapshot`, `PATCH /api/v1/profile`

- [ ] **Step 1: Write failing PATCH tests**

Add exact cases:

```python
def test_patch_updates_stable_fields_and_appends_changed_weight(
    client: TestClient, db: Session
) -> None:
    user_id = register(client)
    client.post("/api/v1/profile", headers=ORIGIN, json=VALID_PROFILE)

    response = client.patch(
        "/api/v1/profile",
        headers=ORIGIN,
        json={"display_name": "New Name", "current_weight_kg": 75.25},
    )

    assert response.status_code == 200
    assert response.json()["display_name"] == "New Name"
    assert response.json()["current_weight_kg"] == 75.25
    assert db.scalar(
        select(func.count()).select_from(BodyMeasurement).where(
            BodyMeasurement.user_id == user_id
        )
    ) == 2


def test_patch_same_weight_is_idempotent(client: TestClient, db: Session) -> None:
    user_id = register(client)
    client.post("/api/v1/profile", headers=ORIGIN, json=VALID_PROFILE)

    first = client.patch(
        "/api/v1/profile", headers=ORIGIN, json={"current_weight_kg": 76.5}
    )
    second = client.patch(
        "/api/v1/profile", headers=ORIGIN, json={"current_weight_kg": 76.5}
    )

    assert first.status_code == second.status_code == 200
    assert db.scalar(
        select(func.count()).select_from(BodyMeasurement).where(
            BodyMeasurement.user_id == user_id
        )
    ) == 1
```

Add tests for empty body `422`, explicit null required field `422`, clearing limitations with null `200`, missing profile `404`, guest `401`, missing/wrong Origin `403`, CORS preflight allowing PATCH, and simulated commit failure rolling back both stable-field and new-weight changes.

- [ ] **Step 2: Run PATCH tests and verify red**

```bash
cd backend
.venv/bin/pytest tests/profile/test_profile_api.py -k patch -v
```

Expected: FAIL because PATCH returns `405 Method Not Allowed`.

- [ ] **Step 3: Implement serialized update transaction**

Load the current profile with:

```python
select(UserProfile).where(UserProfile.user_id == user_id).with_for_update()
```

Use `payload.model_dump(exclude_unset=True)`, remove `current_weight_kg` from the stable-field dictionary, set only supplied profile attributes and load the latest measurement. Add a new `BodyMeasurement` only when the Decimal value differs. Commit once, rollback on `SQLAlchemyError`, refresh server-generated timestamps and return `ProfileSnapshot`.

- [ ] **Step 4: Register PATCH and CORS method**

Add `@router.patch("", response_model=ProfileResponse)` with trusted-Origin protection. Extend `allow_methods` in `app/main.py` from `GET, POST` to:

```python
allow_methods=["GET", "POST", "PATCH"]
```

- [ ] **Step 5: Run backend checks**

```bash
cd backend
TEST_DATABASE_URL=postgresql+psycopg://fitsho:fitsho@localhost:5432/fitsho_test .venv/bin/pytest -v
.venv/bin/ruff check app tests
.venv/bin/mypy app
```

Expected: PASS with all authentication and profile tests.

- [ ] **Step 6: Commit and push update behavior**

```bash
git add backend/app/profile backend/app/main.py backend/tests/profile/test_profile_api.py
git commit -m "feat: preserve weight history on profile updates"
git push
```

---

### Task 5: Shared frontend API transport

**Files:**
- Create: `frontend/src/shared/apiClient.ts`
- Create: `frontend/src/shared/apiClient.test.ts`
- Modify: `frontend/src/features/auth/api.ts`
- Modify: `frontend/src/features/auth/types.ts`
- Modify: `frontend/src/features/auth/authError.ts`
- Modify: `frontend/src/features/auth/authError.test.ts`

**Interfaces:**
- Consumes: browser `fetch`
- Produces: `ApiError`, `request<T>(path: string, init?: RequestInit) -> Promise<T>`

- [ ] **Step 1: Write failing shared transport tests**

```typescript
import { afterEach, expect, it, vi } from "vitest";

import { ApiError, request } from "./apiClient";

afterEach(() => vi.restoreAllMocks());

it("always includes cookies and JSON headers", async () => {
  vi.spyOn(globalThis, "fetch").mockResolvedValue(
    new Response(JSON.stringify({ ok: true }), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    }),
  );
  await request<{ ok: boolean }>("/api/test", { method: "POST", body: "{}" });
  expect(fetch).toHaveBeenCalledWith(
    "/api/test",
    expect.objectContaining({
      credentials: "include",
      headers: expect.objectContaining({ "Content-Type": "application/json" }),
    }),
  );
});

it("maps HTTP failures and empty success responses", async () => {
  vi.spyOn(globalThis, "fetch")
    .mockResolvedValueOnce(
      new Response(JSON.stringify({ detail: "Conflict" }), {
        status: 409,
        headers: { "Content-Type": "application/json" },
      }),
    )
    .mockResolvedValueOnce(new Response(null, { status: 204 }));

  await expect(request("/api/fail")).rejects.toEqual(new ApiError(409, "Conflict"));
  await expect(request<void>("/api/empty")).resolves.toBeUndefined();
});
```

- [ ] **Step 2: Run test and verify red**

```bash
cd frontend
npm test -- src/shared/apiClient.test.ts
```

Expected: FAIL because `apiClient.ts` does not exist.

- [ ] **Step 3: Extract transport without changing auth behavior**

Move `ApiError` and the private request logic from auth into `shared/apiClient.ts`. Treat a non-string `detail` as `Request failed` so Pydantic error arrays are not converted into accidental UI text. Update auth imports and keep public auth function signatures unchanged.

- [ ] **Step 4: Run shared and auth regression checks**

```bash
cd frontend
npm test -- src/shared/apiClient.test.ts src/features/auth
npm run lint
npm run build
```

Expected: PASS.

- [ ] **Step 5: Commit and push transport refactor**

```bash
git add frontend/src/shared/apiClient.ts frontend/src/shared/apiClient.test.ts frontend/src/features/auth
git commit -m "refactor: share frontend API transport"
git push
```

---

### Task 6: Frontend profile contracts, API and pure validation

**Files:**
- Create: `frontend/src/features/profile/types.ts`
- Create: `frontend/src/features/profile/api.ts`
- Create: `frontend/src/features/profile/api.test.ts`
- Create: `frontend/src/features/profile/profileValidation.ts`
- Create: `frontend/src/features/profile/profileValidation.test.ts`

**Interfaces:**
- Consumes: `request`, `ApiError`
- Produces: `Profile`, `ProfileInput`, `ProfilePatch`, `ProfileFormValues`, `getProfile`, `createProfile`, `updateProfile`, `validateStep`, `validateAll`, `toProfileInput`, `toProfilePatch`

- [ ] **Step 1: Write failing profile API tests**

Verify exact endpoints, methods, bodies and 404 semantics:

```typescript
await expect(getProfile()).resolves.toBeNull();
await expect(createProfile(profileInput)).resolves.toEqual(profile);
await expect(updateProfile({ current_weight_kg: 75.25 })).resolves.toEqual(updated);

expect(fetch).toHaveBeenNthCalledWith(
  2,
  "/api/v1/profile",
  expect.objectContaining({ method: "POST", body: JSON.stringify(profileInput) }),
);
expect(fetch).toHaveBeenNthCalledWith(
  3,
  "/api/v1/profile",
  expect.objectContaining({ method: "PATCH" }),
);
```

Mock `404` for GET and prove it maps to null. Mock `503` and prove it remains an `ApiError` rather than null.

- [ ] **Step 2: Write failing pure validation tests**

Use fixed `today = new Date("2026-07-27T12:00:00Z")` and assert:

- step 1 rejects blank/one-character names, invalid dates, age 17 and age 101;
- step 1 accepts exact ages 18 and 100;
- step 2 accepts boundaries 100/250 cm and 20/500 kg and rejects values outside them or three decimal places;
- step 3 rejects zero/eight days and limitations over 1000 characters;
- `toProfileInput` trims strings, converts numeric strings to numbers and converts blank limitations to null;
- `toProfilePatch` emits only changed fields and returns an empty object for unchanged values.

Use stable error codes rather than translated prose:

```typescript
export type ProfileValidationCode =
  | "required"
  | "displayNameLength"
  | "birthDateInvalid"
  | "ageRange"
  | "heightRange"
  | "weightRange"
  | "weightPrecision"
  | "trainingDaysRange"
  | "limitationsLength";
```

- [ ] **Step 3: Run both test files and verify red**

```bash
cd frontend
npm test -- src/features/profile/api.test.ts src/features/profile/profileValidation.test.ts
```

Expected: FAIL because the profile modules do not exist.

- [ ] **Step 4: Implement exact TypeScript contracts and API functions**

Use readonly literal arrays for `sexes`, `fitnessGoals` and `experienceLevels`, with union types derived by `(typeof values)[number]`. Define profile JSON fields exactly as the backend response. `getProfile` catches only `ApiError` status `404`; every other error is rethrown.

- [ ] **Step 5: Implement validation and conversions**

Keep input state as strings:

```typescript
export type ProfileFormValues = {
  display_name: string;
  birth_date: string;
  sex: Sex | "";
  height_cm: string;
  current_weight_kg: string;
  fitness_goal: FitnessGoal | "";
  experience_level: ExperienceLevel | "";
  training_days_per_week: string;
  physical_limitations: string;
};
```

Parse `YYYY-MM-DD` with component round-trip validation rather than `Date.parse` alone. `validateStep(values, step, today)` validates only fields visible in that step; `validateAll` validates all three groups. `toProfileInput` may only be called after successful validation.

- [ ] **Step 6: Run profile foundation and frontend regression**

```bash
cd frontend
npm test -- src/features/profile/api.test.ts src/features/profile/profileValidation.test.ts
npm run lint
npm run build
```

Expected: PASS.

- [ ] **Step 7: Commit and push frontend profile foundation**

```bash
git add frontend/src/features/profile
git commit -m "feat: add profile frontend contracts"
git push
```

---

### Task 7: Profile startup state

**Files:**
- Create: `frontend/src/features/profile/ProfileContext.tsx`
- Create: `frontend/src/features/profile/ProfileContext.test.tsx`

**Interfaces:**
- Consumes: `useAuth`, profile API functions and types
- Produces: `ProfileProvider`, `useProfile`, `ProfileStatus = "idle" | "loading" | "missing" | "ready" | "error"`

- [ ] **Step 1: Write failing ProfileContext tests**

Build a probe that renders `status`, `profile?.display_name` and buttons calling retry/create/update. Mock `useAuth` and profile API. Cover:

```text
auth user null         -> idle, getProfile not called
auth user exists       -> loading then ready
GET resolves null      -> missing
GET rejects            -> error, not missing
retry after error      -> second GET and ready
create success         -> ready with returned profile
update success         -> ready with updated profile
logout during request  -> stale response ignored and state reset to idle
```

- [ ] **Step 2: Run context tests and verify red**

```bash
cd frontend
npm test -- src/features/profile/ProfileContext.test.tsx
```

Expected: FAIL because `ProfileContext.tsx` does not exist.

- [ ] **Step 3: Implement generation-safe provider**

Expose:

```typescript
type ProfileContextValue = {
  profile: Profile | null;
  status: ProfileStatus;
  retryProfile: () => void;
  createProfile: (input: ProfileInput) => Promise<Profile>;
  updateProfile: (patch: ProfilePatch) => Promise<Profile>;
};
```

Mirror AuthContext's request-generation protection so a late GET cannot restore data after logout or overwrite a successful create/update. A failed create leaves `missing`; a failed update leaves the existing profile and `ready` status so the page can show a submit error without losing data.

- [ ] **Step 4: Run context and full frontend tests**

```bash
cd frontend
npm test -- src/features/profile/ProfileContext.test.tsx
npm test
npm run lint
npm run build
```

Expected: PASS.

- [ ] **Step 5: Commit and push profile state**

```bash
git add frontend/src/features/profile/ProfileContext.tsx frontend/src/features/profile/ProfileContext.test.tsx
git commit -m "feat: manage profile startup state"
git push
```

---

### Task 8: Route protection by authentication and profile status

**Files:**
- Create: `frontend/src/features/profile/ProfileRouteGuards.tsx`
- Create: `frontend/src/features/profile/ProfileRouteGuards.test.tsx`
- Create: `frontend/src/features/profile/OnboardingPage.tsx`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/App.test.tsx`
- Modify: `frontend/src/i18n/fa.ts`
- Modify: `frontend/src/i18n/en.ts`

**Interfaces:**
- Consumes: `useAuth`, `useProfile`, `ProtectedRoute`
- Produces: `GuestRoute`, `OnboardingRoute`, `CompletedProfileRoute`, final route matrix

- [ ] **Step 1: Write failing route matrix tests**

Mock both contexts and exercise `AppRoutes` through `MemoryRouter`. Assert:

```text
guest /dashboard                    -> login
guest /onboarding                   -> login
authenticated + missing /dashboard -> onboarding
authenticated + missing /login     -> onboarding
authenticated + missing /onboarding-> onboarding introduction
authenticated + ready /onboarding  -> dashboard
authenticated + ready /login       -> dashboard
authenticated + loading            -> loading screen, no redirect target content
authenticated + error              -> alert + retry button, retryProfile called
```

- [ ] **Step 2: Run route tests and verify red**

```bash
cd frontend
npm test -- src/features/profile/ProfileRouteGuards.test.tsx src/App.test.tsx
```

Expected: FAIL because authenticated users without profile still reach dashboard.

- [ ] **Step 3: Implement guards and provider wiring**

Create a real introductory `OnboardingPage` containing the localized page heading,
a short explanation that three steps will be collected, and no data mutation. Wrap
`Routes` with `ProfileProvider` inside `AuthProvider`. Structure routes exactly:

```tsx
<Route element={<GuestRoute />}>
  <Route path="/login" element={<LoginPage />} />
  <Route path="/register" element={<RegisterPage />} />
</Route>
<Route element={<ProtectedRoute />}>
  <Route element={<OnboardingRoute />}>
    <Route path="/onboarding" element={<OnboardingPage />} />
  </Route>
  <Route element={<CompletedProfileRoute />}>
    <Route path="/dashboard" element={<DashboardPage />} />
  </Route>
</Route>
```

All profile-dependent guards share one loading/error renderer. On error, render `errors.network` and call `retryProfile`; never navigate.

- [ ] **Step 4: Run route and auth regression**

```bash
cd frontend
npm test -- src/features/profile/ProfileRouteGuards.test.tsx src/App.test.tsx src/features/auth
npm run lint
npm run build
```

Expected: PASS.

- [ ] **Step 5: Commit and push protected routing**

```bash
git add frontend/src/App.tsx frontend/src/App.test.tsx frontend/src/features/profile/ProfileRouteGuards.tsx frontend/src/features/profile/ProfileRouteGuards.test.tsx frontend/src/features/profile/OnboardingPage.tsx frontend/src/i18n/fa.ts frontend/src/i18n/en.ts
git commit -m "feat: route incomplete profiles to onboarding"
git push
```

---

### Task 9: Accessible three-step onboarding UI

**Files:**
- Create: `frontend/src/features/profile/ProfileFormFields.tsx`
- Modify: `frontend/src/features/profile/OnboardingPage.tsx`
- Create: `frontend/src/features/profile/OnboardingPage.test.tsx`
- Create: `frontend/src/features/profile/profile.css`
- Modify: `frontend/src/i18n/fa.ts`
- Modify: `frontend/src/i18n/en.ts`

**Interfaces:**
- Consumes: `useProfile.createProfile`, profile form types and validation
- Produces: `PersonalFields`, `BodyGoalFields`, `ExperienceFields`, `OnboardingPage`

- [ ] **Step 1: Invoke visual implementation guidance**

Before editing UI files, invoke the `frontend-design` skill. Preserve Fitsho's existing petrol, turquoise, persimmon and saffron palette, Vazirmatn/Manrope typography and asymmetric card language. Do not add generated raster assets because the onboarding is form-led and does not need new imagery.

- [ ] **Step 2: Write failing onboarding interaction tests**

Render `OnboardingPage` inside `MemoryRouter` with mocked `useProfile`. Test in Persian:

```text
initial render announces step 1 of 3
Next with empty fields shows field errors and remains on step 1
valid personal values advance to step 2
invalid height/weight remain on step 2 and focus first invalid input
valid body values advance to step 3
Back returns to step 2 with entered values preserved
invalid training days/long limitations block submit
valid final submit calls createProfile exactly once with normalized typed payload
successful submit navigates with replace to /dashboard
rejected API call keeps all values and shows an alert
busy submit disables navigation and submit controls
```

Include one English-language assertion after switching i18n to `en` so both resource trees are exercised.

- [ ] **Step 3: Run onboarding tests and verify red**

```bash
cd frontend
npm test -- src/features/profile/OnboardingPage.test.tsx
```

Expected: FAIL because the introductory page does not yet contain the three-step form.

- [ ] **Step 4: Implement reusable controlled field groups**

Each input/select/textarea must have a stable `id`, visible label, appropriate `autoComplete`, numeric `inputMode`, `aria-invalid` and `aria-describedby` when an error exists. Render translated field error adjacent to its control. Do not store values outside component memory.

- [ ] **Step 5: Implement the three-step state machine**

Keep `step` as `1 | 2 | 3`, one `ProfileFormValues` object, one error map and submit state. Validate current step before advancing and all fields before submit. Use an effect keyed by the error map to focus the first invalid `[name]` control. Render progress as an ordered list with translated `aria-label` and `aria-current="step"`.

On success:

```typescript
await createProfile(toProfileInput(values));
navigate("/dashboard", { replace: true });
```

Do not clear the form on rejection.

- [ ] **Step 6: Add complete bilingual copy and responsive styles**

Add translation groups for page title, three step names, every field label, enum option, hint, button, busy state and each validation code. Import `profile.css` from `OnboardingPage.tsx`. Styles must support 320px width, visible keyboard focus, reduced motion and both `html[dir="rtl"]` and LTR without hard-coded left/right layout rules.

- [ ] **Step 7: Connect the completed form and run frontend checks**

Keep the existing `/onboarding` route connected to the now-complete `OnboardingPage`, update route tests to locate the localized heading and first-step form, then run:

```bash
cd frontend
npm test -- src/features/profile/OnboardingPage.test.tsx src/features/profile/ProfileRouteGuards.test.tsx src/App.test.tsx
npm test
npm run lint
npm run build
```

Expected: PASS.

- [ ] **Step 8: Commit and push onboarding UI**

```bash
git add frontend/src/features/profile frontend/src/i18n/fa.ts frontend/src/i18n/en.ts
git commit -m "feat: add three-step fitness onboarding"
git push
```

---

### Task 10: Profile read/edit page and authenticated navigation

**Files:**
- Create: `frontend/src/shared/AuthenticatedHeader.tsx`
- Create: `frontend/src/features/profile/ProfilePage.tsx`
- Create: `frontend/src/features/profile/ProfilePage.test.tsx`
- Modify: `frontend/src/features/profile/profileValidation.ts`
- Modify: `frontend/src/features/profile/profileValidation.test.ts`
- Modify: `frontend/src/features/profile/profile.css`
- Modify: `frontend/src/pages/DashboardPage.tsx`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/App.test.tsx`
- Modify: `frontend/src/i18n/fa.ts`
- Modify: `frontend/src/i18n/en.ts`

**Interfaces:**
- Consumes: `useProfile.profile`, `useProfile.updateProfile`, reusable field groups, `useAuth.logout`
- Produces: `AuthenticatedHeader`, `ProfilePage`, working `/profile` read/update UI

- [ ] **Step 1: Write failing profile edit tests**

Mock a ready profile and `updateProfile`. Assert:

```text
all saved profile values render in controls
last measured weight and measured date are visible
Save without changes does not call PATCH
changing display name sends only {display_name: "New Name"}
changing weight sends only {current_weight_kg: 75.25}
clearing limitations sends {physical_limitations: null}
invalid edit focuses the first invalid field and does not call updateProfile
successful update shows localized success status using returned profile
failed update keeps edits and shows localized alert
header links navigate to dashboard/profile and logout returns to login
```

- [ ] **Step 2: Run edit tests and verify red**

```bash
cd frontend
npm test -- src/features/profile/ProfilePage.test.tsx
```

Expected: FAIL because `ProfilePage.tsx` does not exist.

- [ ] **Step 3: Implement authenticated header**

Extract brand, `LanguageSwitcher`, dashboard/profile navigation and logout from `DashboardPage`. Keep logout's busy/error handling inside `AuthenticatedHeader`. Use React Router `Link`, not raw anchors, for internal navigation. Preserve the existing auth header accessibility and styles.

- [ ] **Step 4: Implement profile edit page**

Initialize form values from the ready context profile, render all three reusable field groups in one form, validate all fields, calculate a minimal patch with `toProfilePatch`, and skip the request when the patch is empty. On success, use the returned profile already stored by the context and reset the form baseline so a second Save without edits is a no-op.

Show `weight_measured_at` as localized date/time but submit no measurement timestamp; the server owns it.

- [ ] **Step 5: Update dashboard and final routing**

Use `AuthenticatedHeader` in dashboard and profile. Replace the coming-soon profile
card with a real `Link` to `/profile`, use the profile display name in the greeting
where appropriate, and add the protected `/profile` route with `<ProfilePage />`.

- [ ] **Step 6: Run frontend regression**

```bash
cd frontend
npm test
npm run lint
npm run build
```

Expected: PASS.

- [ ] **Step 7: Commit and push profile editing**

```bash
git add frontend/src/shared/AuthenticatedHeader.tsx frontend/src/features/profile frontend/src/pages/DashboardPage.tsx frontend/src/App.tsx frontend/src/App.test.tsx frontend/src/i18n/fa.ts frontend/src/i18n/en.ts
git commit -m "feat: add fitness profile editing"
git push
```

---

## Final Verification Gate

Do not claim completion until every command below has fresh successful output.

- [ ] **Step 1: Verify migration reversibility on the test database**

```bash
cd backend
DATABASE_URL=postgresql+psycopg://fitsho:fitsho@localhost:5432/fitsho_test .venv/bin/alembic upgrade head
DATABASE_URL=postgresql+psycopg://fitsho:fitsho@localhost:5432/fitsho_test .venv/bin/alembic downgrade 20260724_01
DATABASE_URL=postgresql+psycopg://fitsho:fitsho@localhost:5432/fitsho_test .venv/bin/alembic upgrade head
DATABASE_URL=postgresql+psycopg://fitsho:fitsho@localhost:5432/fitsho_test .venv/bin/alembic check
```

Expected: all commands exit `0`; `alembic check` reports no new upgrade operations.

- [ ] **Step 2: Run complete backend verification**

```bash
cd backend
TEST_DATABASE_URL=postgresql+psycopg://fitsho:fitsho@localhost:5432/fitsho_test .venv/bin/pytest -v
.venv/bin/ruff check .
.venv/bin/ruff format --check .
.venv/bin/mypy app
```

Expected: all tests and static checks PASS.

- [ ] **Step 3: Run complete frontend verification**

```bash
cd frontend
npm test
npm run lint
npm run build
```

Expected: all Vitest tests PASS, oxlint exits `0`, TypeScript compilation and Vite build succeed.

- [ ] **Step 4: Check scope and repository state**

```bash
git diff --check
git status -sb
git log --oneline origin/feature/authentication..HEAD
```

Confirm:

- branch is synchronized with `origin/feature/onboarding-profile`;
- no secret or environment file is tracked;
- unrelated `README.md` and `AGENTS.md` changes are not in feature commits;
- commit list contains one reviewable commit per task;
- no workout, nutrition, AI, chart, Redis, cache, queue or Playwright code was added.
