# Authentication Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** ساخت قابلیت کامل ثبت‌نام، ورود، خروج و تشخیص کاربر فعلی از رابط کاربری تا پایگاه داده

**Architecture:** بخش سرور یک تک‌برنامه ماژولار هم‌زمان است و رابط کاربری یک برنامه تک‌صفحه‌ای مستقل. نشست کاربر با توکن تصادفی در کوکی امن نگهداری می‌شود و فقط هش توکن در پایگاه داده قرار می‌گیرد.

**Tech Stack:**

```text
Python 3.12+
Node.js 24 LTS
FastAPI
Pydantic
SQLAlchemy 2
Alembic
PostgreSQL
pwdlib with Argon2
React
TypeScript
Vite
React Router
react-i18next
i18next
pytest
HTTPX
Vitest
React Testing Library
Docker Compose
```

## Global Constraints

- سند طراحی مرجع:

```text
docs/superpowers/specs/2026-07-24-authentication-design.md
```

- فقط قابلیت احراز هویت ساخته شود؛ پروفایل، برنامه تمرینی، تغذیه و هوش مصنوعی خارج از محدوده‌اند.
- محیط رابط کاربری از نسخه پشتیبانی بلندمدت ۲۴ نود یا جدیدتر استفاده کند.
- بخش سرور هم‌زمان بماند؛ دسترسی غیرهم‌زمان به پایگاه داده در این مرحله اضافه نشود.
- برای احراز هویت مرورگر از نشست مبهم سمت سرور استفاده شود؛ توکن امضاشده داخل حافظه محلی مرورگر ممنوع است.
- رمز خام و توکن نشست خام هرگز در پایگاه داده، پاسخ رابط برنامه‌نویسی یا گزارش‌ها ذخیره نشوند.
- آزمایش‌های پایگاه داده روی نمونه واقعی پایگاه داده رابطه‌ای اجرا شوند، نه پایگاه داده سبک.
- ایجاد کاربر و نشست ثبت‌نام در یک تراکنش انجام شود.
- درخواست‌های تغییردهنده بدون مبدأ مجاز رد شوند.
- کوکی محیط اصلی امن، غیرقابل دسترسی برای جاوااسکریپت و محدود به همان میزبان باشد.
- هر تغییر رفتاری با چرخه آزمایش ناموفق، پیاده‌سازی حداقلی و آزمایش موفق انجام شود.
- تغییرات موجود کاربر در فایل راهنما و سایر فایل‌های نامرتبط حفظ شوند.
- هر وظیفه یک ثبت مستقل و قابل بازبینی داشته باشد.

## Approved bilingual interface amendment

این اصلاحیه بر جزئیات قدیمی وظیفه‌های ششم تا هشتم اولویت دارد:

- زبان پیش‌فرض فارسی است و تغییر کامل میان فارسی و انگلیسی فراهم می‌شود.
- انتخاب زبان در فضای محلی مرورگر باقی می‌ماند؛ هیچ داده احراز هویت آنجا ذخیره
  نمی‌شود.
- زبان و جهت عنصر اصلی سند با هر تغییر هم‌زمان به‌روز می‌شوند.
- متن‌ها در فایل‌های ترجمه مستقل قرار می‌گیرند و اجزای نمایشی متن ثابت ندارند.
- هویت بصری «مربی روزانه» و رنگ‌های مصوب سند طراحی اجرا می‌شوند.
- صفحه ورود و ثبت‌نام در نمایشگر بزرگ دو پنل و در موبایل تک‌ستونه است.
- داشبورد فقط داده واقعی حساب و نشست را نشان می‌دهد و داده تمرینی ساختگی ندارد.
- قلم‌های فارسی و لاتین از بسته‌های محلی پروژه بارگذاری می‌شوند؛ شبکه توزیع محتوای
  بیرونی استفاده نمی‌شود.
- حرکت به یک ورود هماهنگ محدود است و ترجیح کاهش حرکت رعایت می‌شود.
- آزمایش‌ها تغییر زبان، جهت سند و باقی‌ماندن انتخاب زبان را نیز پوشش می‌دهند.

---

## نقشه فایل‌ها

فایل‌های ریشه:

```text
.env.example
.gitignore
compose.yaml
README.md
docker/postgres/init/01-create-test-db.sql
```

مسئولیت‌ها:

- فایل محیط نمونه، متغیرهای لازم را بدون مقدار محرمانه مستند می‌کند.
- فایل ترکیب محفظه‌ها فقط پایگاه داده توسعه و آزمایش را اجرا می‌کند.
- فایل راهنما روش اجرای کامل پروژه را توضیح می‌دهد.

فایل‌های بخش سرور:

```text
backend/pyproject.toml
backend/alembic.ini
backend/alembic/env.py
backend/alembic/script.py.mako
backend/alembic/versions/20260724_01_create_auth_tables.py
backend/app/__init__.py
backend/app/main.py
backend/app/config.py
backend/app/database/__init__.py
backend/app/database/base.py
backend/app/database/session.py
backend/app/auth/__init__.py
backend/app/auth/models.py
backend/app/auth/schemas.py
backend/app/auth/security.py
backend/app/auth/exceptions.py
backend/app/auth/service.py
backend/app/auth/cookies.py
backend/app/auth/dependencies.py
backend/app/auth/router.py
backend/tests/conftest.py
backend/tests/test_config.py
backend/tests/database/test_auth_models.py
backend/tests/auth/test_security.py
backend/tests/auth/test_register.py
backend/tests/auth/test_sessions.py
```

مرزها:

- تنظیمات فقط خواندن و اعتبارسنجی محیط را انجام می‌دهند.
- بخش پایگاه داده، مدل پایه، موتور و نشست را فراهم می‌کند.
- مدل‌ها فقط نگاشت جداول هستند.
- طرح‌واره‌ها فقط قرارداد عمومی درخواست و پاسخ هستند.
- ابزار امنیتی فقط هش رمز و توکن را مدیریت می‌کند.
- سرویس‌ها مالک تراکنش و حالت‌های کاربردی هستند.
- مسیریاب فقط اچ‌تی‌تی‌پی، وابستگی‌ها، کوکی و نگاشت خطا را مدیریت می‌کند.

فایل‌های رابط کاربری:

```text
frontend/package.json
frontend/package-lock.json
frontend/vite.config.ts
frontend/src/main.tsx
frontend/src/App.tsx
frontend/src/styles.css
frontend/src/test/setup.ts
frontend/src/features/auth/types.ts
frontend/src/features/auth/api.ts
frontend/src/features/auth/api.test.ts
frontend/src/features/auth/AuthContext.tsx
frontend/src/features/auth/AuthContext.test.tsx
frontend/src/features/auth/ProtectedRoute.tsx
frontend/src/features/auth/RegisterPage.tsx
frontend/src/features/auth/RegisterPage.test.tsx
frontend/src/features/auth/LoginPage.tsx
frontend/src/features/auth/LoginPage.test.tsx
frontend/src/i18n/index.ts
frontend/src/i18n/fa.ts
frontend/src/i18n/en.ts
frontend/src/pages/DashboardPage.tsx
frontend/src/shared/LanguageSwitcher.tsx
frontend/src/shared/LanguageSwitcher.test.tsx
frontend/src/App.test.tsx
```

مرزها:

- فایل ارتباط، تنها محل فراخوانی رابط برنامه‌نویسی است.
- زمینه احراز هویت، کاربر و عملیات نشست را نگه می‌دارد.
- صفحه‌ها فقط حالت فرم و نمایش خطا را مدیریت می‌کنند.
- مسیر محافظت‌شده فقط تصمیم نمایش یا انتقال را می‌گیرد.

---

### Task 1: ستون فقرات قابل اجرای بخش سرور و تنظیمات

**فایل‌ها**

ایجاد:

```text
.env.example
.gitignore
compose.yaml
docker/postgres/init/01-create-test-db.sql
backend/pyproject.toml
backend/app/__init__.py
backend/app/config.py
backend/app/database/__init__.py
backend/app/database/base.py
backend/app/database/session.py
backend/tests/test_config.py
```

**رابط‌های خروجی**

```python
Settings
get_settings() -> Settings
Base
get_engine(database_url: str) -> Engine
get_db(settings: Settings) -> Iterator[Session]
```

- [ ] **Step 1: فایل بسته و وابستگی‌های بخش سرور را ایجاد کن**

```toml
[build-system]
requires = ["setuptools>=75"]
build-backend = "setuptools.build_meta"

[project]
name = "fitsho-backend"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
  "alembic>=1,<2",
  "email-validator>=2,<3",
  "fastapi>=0.115,<1",
  "psycopg[binary]>=3,<4",
  "pwdlib[argon2]>=0.2,<1",
  "pydantic-settings>=2,<3",
  "sqlalchemy>=2,<3",
  "uvicorn[standard]>=0.30,<1",
]

[project.optional-dependencies]
dev = [
  "httpx>=0.27,<1",
  "mypy>=1.13,<2",
  "pytest>=8,<10",
  "pytest-cov>=5,<8",
  "ruff>=0.9,<1",
]

[tool.setuptools.packages.find]
include = ["app*"]

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-ra"

[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "I", "B", "UP"]

[tool.mypy]
python_version = "3.12"
strict = true
plugins = ["pydantic.mypy"]
```

فایل بالا در این مسیر قرار گیرد:

```text
backend/pyproject.toml
```

محیط را بساز و وابستگی‌ها را نصب کن:

```bash
cd backend
python -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -e ".[dev]"
```

خروجی مورد انتظار: نصب موفق بسته پروژه و ابزارهای توسعه.

- [ ] **Step 2: آزمایش ناموفق تنظیمات را بنویس**

```python
from app.config import Settings


def test_settings_accept_explicit_environment_values() -> None:
    settings = Settings(
        database_url="postgresql+psycopg://fitsho:fitsho@localhost:5432/fitsho",
        frontend_origin="http://localhost:5173",
        app_env="test",
        cookie_secure=False,
        session_cookie_name="fitsho_session",
    )

    assert settings.session_ttl_seconds == 604800
    assert settings.frontend_origin == "http://localhost:5173"
```

فایل آزمایش:

```text
backend/tests/test_config.py
```

- [ ] **Step 3: شکست آزمایش را تأیید کن**

```bash
cd backend
.venv/bin/pytest tests/test_config.py -v
```

خروجی مورد انتظار:

```text
FAIL: ModuleNotFoundError or Settings is not defined
```

- [ ] **Step 4: تنظیمات حداقلی را پیاده‌سازی کن**

```python
from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://fitsho:fitsho@localhost:5432/fitsho"
    frontend_origin: str = "http://localhost:5173"
    app_env: Literal["local", "test", "production"] = "local"
    cookie_secure: bool = True
    session_cookie_name: str = "__Host-fitsho_session"
    session_ttl_seconds: int = 60 * 60 * 24 * 7

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
```

فایل:

```text
backend/app/config.py
```

مدل پایه:

```python
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
```

فایل:

```text
backend/app/database/base.py
```

ساخت موتور و نشست:

```python
from collections.abc import Iterator
from functools import lru_cache

from fastapi import Depends
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session

from app.config import Settings, get_settings


@lru_cache
def get_engine(database_url: str) -> Engine:
    return create_engine(database_url, pool_pre_ping=True)


def get_db(settings: Settings = Depends(get_settings)) -> Iterator[Session]:
    with Session(get_engine(settings.database_url)) as session:
        yield session
```

فایل:

```text
backend/app/database/session.py
```

فایل‌های آغازگر بسته خالی باشند:

```text
backend/app/__init__.py
backend/app/database/__init__.py
```

- [ ] **Step 5: تنظیمات پایگاه داده محلی و آزمایش را ایجاد کن**

```yaml
services:
  db:
    image: postgres:18-alpine
    environment:
      POSTGRES_USER: fitsho
      POSTGRES_PASSWORD: fitsho
      POSTGRES_DB: fitsho
    ports:
      - "5432:5432"
    volumes:
      - fitsho_postgres_data:/var/lib/postgresql
      - ./docker/postgres/init:/docker-entrypoint-initdb.d:ro
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U fitsho -d fitsho"]
      interval: 5s
      timeout: 5s
      retries: 10

volumes:
  fitsho_postgres_data:
```

فایل:

```text
compose.yaml
```

پایگاه داده آزمایش:

```sql
CREATE DATABASE fitsho_test;
```

فایل:

```text
docker/postgres/init/01-create-test-db.sql
```

محیط نمونه:

```dotenv
DATABASE_URL=postgresql+psycopg://fitsho:fitsho@localhost:5432/fitsho
FRONTEND_ORIGIN=http://localhost:5173
APP_ENV=local
COOKIE_SECURE=false
SESSION_COOKIE_NAME=fitsho_session
SESSION_TTL_SECONDS=604800
```

فایل:

```text
.env.example
```

نادیده‌گرفتن فایل‌های تولیدی:

```gitignore
.env
.venv/
__pycache__/
.pytest_cache/
.mypy_cache/
.ruff_cache/
.coverage
htmlcov/
node_modules/
dist/
*.py[cod]
```

فایل:

```text
.gitignore
```

- [ ] **Step 6: آزمایش و بررسی ایستا را اجرا کن**

```bash
cd backend
.venv/bin/pytest tests/test_config.py -v
.venv/bin/ruff check app tests
.venv/bin/mypy app
```

خروجی مورد انتظار:

```text
1 passed
All checks passed
Success: no issues found
```

- [ ] **Step 7: ثبت کن**

```bash
git add .env.example .gitignore compose.yaml docker/postgres/init/01-create-test-db.sql backend
git commit -m "build: add backend and database backbone"
```

---

### Task 2: مدل‌های کاربر و نشست و مهاجرت اولیه

**فایل‌ها**

ایجاد:

```text
backend/alembic.ini
backend/alembic/env.py
backend/alembic/script.py.mako
backend/alembic/versions/20260724_01_create_auth_tables.py
backend/app/auth/__init__.py
backend/app/auth/models.py
backend/tests/conftest.py
backend/tests/database/test_auth_models.py
```

**رابط‌های خروجی**

```python
User
AuthSession
```

- [ ] **Step 1: پایگاه داده را اجرا کن**

```bash
docker compose up -d db
docker compose ps
```

خروجی مورد انتظار: سرویس پایگاه داده در وضعیت سالم باشد.

- [ ] **Step 2: آزمایش ناموفق محدودیت‌ها را بنویس**

```python
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.models import AuthSession, User


def test_user_email_is_unique(db: Session) -> None:
    db.add(User(email="same@example.com", password_hash="hash-1"))
    db.flush()
    db.add(User(email="same@example.com", password_hash="hash-2"))

    with pytest.raises(IntegrityError):
        db.flush()


def test_deleting_user_deletes_sessions(db: Session) -> None:
    user = User(email="delete@example.com", password_hash="hash")
    db.add(user)
    db.flush()
    session = AuthSession(
        user_id=user.id,
        token_hash="a" * 64,
        expires_at=datetime.now(timezone.utc) + timedelta(days=7),
    )
    db.add(session)
    db.flush()

    db.delete(user)
    db.flush()

    assert db.scalar(
        select(AuthSession).where(AuthSession.id == session.id)
    ) is None
```

فایل:

```text
backend/tests/database/test_auth_models.py
```

- [ ] **Step 3: شکست را تأیید کن**

```bash
cd backend
.venv/bin/pytest tests/database/test_auth_models.py -v
```

خروجی مورد انتظار:

```text
FAIL: app.auth.models does not exist
```

- [ ] **Step 4: مدل‌ها را پیاده‌سازی کن**

```python
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class AuthSession(Base):
    __tablename__ = "sessions"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
```

فایل:

```text
backend/app/auth/models.py
```

- [ ] **Step 5: محیط مهاجرت و مهاجرت صریح را ایجاد کن**

ساختار استاندارد مهاجرت را بساز:

```bash
cd backend
.venv/bin/alembic init alembic
```

خروجی مورد انتظار:

```text
Creating directory alembic
Generating alembic.ini
```

تنظیم اصلی تولیدشده مسیر اسکریپت را نگه دارد. مقدار نمونه نشانی پایگاه داده در آن
استفاده نمی‌شود، زیرا فایل محیط مقدار واقعی را از تنظیمات برنامه جایگزین می‌کند.
فایل محیط، مدل‌ها را پیش از تعیین فراداده وارد کند:

```python
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.auth import models
from app.config import get_settings
from app.database.base import Base

config = context.config
config.set_main_option("sqlalchemy.url", get_settings().database_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

فایل:

```text
backend/alembic/env.py
```

مهاجرت باید دو جدول، محدودیت یکتایی و کلید خارجی با حذف آبشاری را به‌صورت صریح
بسازد. شناسه‌های مهاجرت:

```python
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision = "20260724_01"
down_revision = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("password_hash", sa.String(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
    )
    op.create_table(
        "sessions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index("ix_sessions_user_id", "sessions", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_sessions_user_id", table_name="sessions")
    op.drop_table("sessions")
    op.drop_table("users")
```

فایل:

```text
backend/alembic/versions/20260724_01_create_auth_tables.py
```

- [ ] **Step 6: داده آزمایش را به تراکنش ایزوله متصل کن**

```python
import os
import subprocess
import sys
from collections.abc import Iterator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+psycopg://fitsho:fitsho@localhost:5432/fitsho_test",
)


@pytest.fixture(scope="session", autouse=True)
def migrated_database() -> Iterator[None]:
    environment = {**os.environ, "DATABASE_URL": TEST_DATABASE_URL}
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        check=True,
        env=environment,
    )
    yield


@pytest.fixture
def db() -> Iterator[Session]:
    engine = create_engine(TEST_DATABASE_URL)
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()
        engine.dispose()
```

فایل:

```text
backend/tests/conftest.py
```

- [ ] **Step 7: مهاجرت و آزمایش را اجرا کن**

```bash
cd backend
DATABASE_URL=postgresql+psycopg://fitsho:fitsho@localhost:5432/fitsho_test .venv/bin/alembic downgrade base
DATABASE_URL=postgresql+psycopg://fitsho:fitsho@localhost:5432/fitsho_test .venv/bin/alembic upgrade head
.venv/bin/pytest tests/database/test_auth_models.py -v
```

خروجی مورد انتظار:

```text
2 passed
```

- [ ] **Step 8: ثبت کن**

```bash
git add backend/alembic.ini backend/alembic backend/app/auth backend/tests
git commit -m "feat: add authentication data model"
```

---

### Task 3: ابزارهای امنیتی رمز و توکن

**فایل‌ها**

ایجاد:

```text
backend/app/auth/security.py
backend/tests/auth/test_security.py
```

**رابط‌های خروجی**

```python
hash_password(password: str) -> str
verify_password(password: str, password_hash: str) -> bool
make_session_token() -> tuple[str, str]
hash_session_token(raw_token: str) -> str
DUMMY_PASSWORD_HASH
```

- [ ] **Step 1: آزمایش‌های ناموفق را بنویس**

```python
from app.auth.security import (
    hash_password,
    hash_session_token,
    make_session_token,
    verify_password,
)


def test_password_is_hashed_and_verifiable() -> None:
    encoded = hash_password("correct horse battery staple")

    assert encoded != "correct horse battery staple"
    assert verify_password("correct horse battery staple", encoded)
    assert not verify_password("wrong password", encoded)


def test_session_tokens_are_random_and_only_digest_is_stable() -> None:
    raw_one, digest_one = make_session_token()
    raw_two, digest_two = make_session_token()

    assert raw_one != raw_two
    assert digest_one != digest_two
    assert digest_one == hash_session_token(raw_one)
    assert raw_one not in digest_one
    assert len(digest_one) == 64
```

- [ ] **Step 2: شکست را تأیید کن**

```bash
cd backend
.venv/bin/pytest tests/auth/test_security.py -v
```

خروجی مورد انتظار:

```text
FAIL: app.auth.security does not exist
```

- [ ] **Step 3: پیاده‌سازی حداقلی را بنویس**

```python
import hashlib
import secrets

from pwdlib import PasswordHash

_password_hash = PasswordHash.recommended()
DUMMY_PASSWORD_HASH = _password_hash.hash("fitsho-dummy-password-value")


def hash_password(password: str) -> str:
    return _password_hash.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return _password_hash.verify(password, password_hash)


def hash_session_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def make_session_token() -> tuple[str, str]:
    raw_token = secrets.token_urlsafe(32)
    return raw_token, hash_session_token(raw_token)
```

- [ ] **Step 4: آزمایش‌ها و بررسی ایستا را اجرا کن**

```bash
cd backend
.venv/bin/pytest tests/auth/test_security.py -v
.venv/bin/ruff check app/auth/security.py tests/auth/test_security.py
.venv/bin/mypy app/auth/security.py
```

خروجی مورد انتظار:

```text
2 passed
All checks passed
Success: no issues found
```

- [ ] **Step 5: ثبت کن**

```bash
git add backend/app/auth/security.py backend/tests/auth/test_security.py
git commit -m "feat: add password and session token security"
```

---

### Task 4: ثبت‌نام تراکنشی و قرارداد عمومی کاربر

**فایل‌ها**

ایجاد:

```text
backend/app/main.py
backend/app/auth/schemas.py
backend/app/auth/exceptions.py
backend/app/auth/service.py
backend/app/auth/cookies.py
backend/app/auth/router.py
backend/tests/auth/test_register.py
```

تغییر:

```text
backend/tests/conftest.py
```

**رابط‌های خروجی**

```python
RegisterRequest
LoginRequest
UserResponse
AuthResult
normalize_email(email: str) -> str
register_user(db: Session, payload: RegisterRequest, ttl_seconds: int) -> AuthResult
set_session_cookie(response: Response, raw_token: str, settings: Settings) -> None
clear_session_cookie(response: Response, settings: Settings) -> None
create_app(settings: Settings | None = None) -> FastAPI
```

- [ ] **Step 1: آزمایش‌های ناموفق ثبت‌نام را بنویس**

```python
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.models import AuthSession, User


def test_register_creates_user_session_and_cookie(client: TestClient, db: Session) -> None:
    response = client.post(
        "/api/v1/auth/register",
        headers={"Origin": "http://localhost:5173"},
        json={"email": " New@Example.com ", "password": "long password"},
    )

    assert response.status_code == 201
    assert response.json()["email"] == "new@example.com"
    assert "password_hash" not in response.json()
    assert "fitsho_session" in response.cookies
    user = db.scalar(select(User).where(User.email == "new@example.com"))
    assert user is not None
    assert user.password_hash != "long password"
    assert db.scalar(select(AuthSession).where(AuthSession.user_id == user.id)) is not None


def test_register_rejects_duplicate_email(client: TestClient) -> None:
    payload = {"email": "duplicate@example.com", "password": "long password"}
    headers = {"Origin": "http://localhost:5173"}

    assert client.post("/api/v1/auth/register", headers=headers, json=payload).status_code == 201
    response = client.post("/api/v1/auth/register", headers=headers, json=payload)

    assert response.status_code == 409
    assert response.json() == {"detail": "Email is already registered"}


def test_register_rejects_invalid_input(client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/register",
        headers={"Origin": "http://localhost:5173"},
        json={"email": "invalid", "password": "short"},
    )

    assert response.status_code == 422


def test_register_rejects_untrusted_or_missing_origin(client: TestClient) -> None:
    payload = {"email": "origin@example.com", "password": "long password"}

    assert client.post("/api/v1/auth/register", json=payload).status_code == 403
    assert client.post(
        "/api/v1/auth/register",
        headers={"Origin": "https://evil.example"},
        json=payload,
    ).status_code == 403
```

- [ ] **Step 2: برنامه آزمایشی را به نشست تراکنشی متصل کن**

به فایل داده آزمایش این fixtureها اضافه شوند:

```python
from fastapi.testclient import TestClient

from app.config import Settings, get_settings
from app.database.session import get_db
from app.main import create_app


@pytest.fixture
def test_settings() -> Settings:
    return Settings(
        database_url=TEST_DATABASE_URL,
        frontend_origin="http://localhost:5173",
        app_env="test",
        cookie_secure=False,
        session_cookie_name="fitsho_session",
        session_ttl_seconds=604800,
    )


@pytest.fixture
def client(db: Session, test_settings: Settings) -> Iterator[TestClient]:
    app = create_app(test_settings)

    def override_db() -> Iterator[Session]:
        yield db

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_settings] = lambda: test_settings
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
```

- [ ] **Step 3: شکست آزمایش را تأیید کن**

```bash
cd backend
.venv/bin/pytest tests/auth/test_register.py -v
```

خروجی مورد انتظار:

```text
FAIL: create_app, schemas, service, or router is not defined
```

- [ ] **Step 4: طرح‌واره‌ها و خطاهای دامنه را ایجاد کن**

```python
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class UserResponse(BaseModel):
    id: UUID
    email: EmailStr
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
```

فایل:

```text
backend/app/auth/schemas.py
```

خطاها:

```python
class EmailAlreadyRegisteredError(Exception):
    pass


class InvalidCredentialsError(Exception):
    pass
```

فایل:

```text
backend/app/auth/exceptions.py
```

- [ ] **Step 5: سرویس ثبت‌نام را پیاده‌سازی کن**

```python
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.exceptions import EmailAlreadyRegisteredError
from app.auth.models import AuthSession, User
from app.auth.schemas import RegisterRequest
from app.auth.security import hash_password, make_session_token


@dataclass(frozen=True)
class AuthResult:
    user: User
    raw_token: str


def normalize_email(email: str) -> str:
    return email.strip().casefold()


def register_user(
    db: Session,
    payload: RegisterRequest,
    ttl_seconds: int,
) -> AuthResult:
    raw_token, token_hash = make_session_token()
    user = User(
        email=normalize_email(str(payload.email)),
        password_hash=hash_password(payload.password),
    )
    db.add(user)
    try:
        db.flush()
        db.add(
            AuthSession(
                user_id=user.id,
                token_hash=token_hash,
                expires_at=datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds),
            )
        )
        db.commit()
        db.refresh(user)
    except IntegrityError as error:
        db.rollback()
        raise EmailAlreadyRegisteredError from error
    return AuthResult(user=user, raw_token=raw_token)
```

- [ ] **Step 6: بررسی مبدأ و مدیریت کوکی را پیاده‌سازی کن**

```python
from fastapi import Depends, HTTPException, Request, Response, status

from app.config import Settings, get_settings


def require_trusted_origin(
    request: Request,
    settings: Settings = Depends(get_settings),
) -> None:
    if request.headers.get("origin") != settings.frontend_origin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Untrusted request origin",
        )


def set_session_cookie(
    response: Response,
    raw_token: str,
    settings: Settings,
) -> None:
    response.set_cookie(
        key=settings.session_cookie_name,
        value=raw_token,
        max_age=settings.session_ttl_seconds,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/",
    )


def clear_session_cookie(response: Response, settings: Settings) -> None:
    response.delete_cookie(
        key=settings.session_cookie_name,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/",
    )
```

فایل:

```text
backend/app/auth/cookies.py
```

- [ ] **Step 7: مسیر ثبت‌نام و برنامه را پیاده‌سازی کن**

```python
from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.auth.cookies import require_trusted_origin, set_session_cookie
from app.auth.exceptions import EmailAlreadyRegisteredError
from app.auth.schemas import RegisterRequest, UserResponse
from app.auth.service import register_user
from app.config import Settings, get_settings
from app.database.session import get_db

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_trusted_origin)],
)
def register(
    payload: RegisterRequest,
    response: Response,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> UserResponse:
    try:
        result = register_user(db, payload, settings.session_ttl_seconds)
    except EmailAlreadyRegisteredError:
        from fastapi import HTTPException

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email is already registered",
        ) from None
    set_session_cookie(response, result.raw_token, settings)
    return UserResponse.model_validate(result.user)
```

فایل:

```text
backend/app/auth/router.py
```

کارخانه برنامه:

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.auth.router import router as auth_router
from app.config import Settings, get_settings


def create_app(settings: Settings | None = None) -> FastAPI:
    active_settings = settings or get_settings()
    app = FastAPI(title="Fitsho API")
    app.dependency_overrides[get_settings] = lambda: active_settings
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[active_settings.frontend_origin],
        allow_credentials=True,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )
    app.include_router(auth_router)
    return app


app = create_app()
```

فایل:

```text
backend/app/main.py
```

- [ ] **Step 8: آزمایش ثبت‌نام را سبز کن**

```bash
cd backend
.venv/bin/pytest tests/auth/test_register.py -v
.venv/bin/ruff check app tests
.venv/bin/mypy app
```

خروجی مورد انتظار:

```text
4 passed
All checks passed
Success: no issues found
```

- [ ] **Step 9: ثبت کن**

```bash
git add backend/app backend/tests
git commit -m "feat: add transactional user registration"
```

---

### Task 5: ورود، تشخیص کاربر، خروج و انقضای نشست

**فایل‌ها**

ایجاد:

```text
backend/app/auth/dependencies.py
backend/tests/auth/test_sessions.py
```

تغییر:

```text
backend/app/auth/service.py
backend/app/auth/router.py
```

**رابط‌های خروجی**

```python
login_user(db: Session, payload: LoginRequest, ttl_seconds: int) -> AuthResult
user_for_session(db: Session, raw_token: str) -> User | None
logout_session(db: Session, raw_token: str | None) -> None
get_current_user(request: Request, db: Session, settings: Settings) -> User
```

- [ ] **Step 1: آزمایش‌های ناموفق نشست را بنویس**

```python
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.models import AuthSession
from app.auth.security import hash_session_token

ORIGIN = {"Origin": "http://localhost:5173"}


def register(client: TestClient, email: str = "user@example.com") -> None:
    response = client.post(
        "/api/v1/auth/register",
        headers=ORIGIN,
        json={"email": email, "password": "long password"},
    )
    assert response.status_code == 201


def test_login_and_me_return_public_user(client: TestClient) -> None:
    register(client)
    client.post("/api/v1/auth/logout", headers=ORIGIN)

    login = client.post(
        "/api/v1/auth/login",
        headers=ORIGIN,
        json={"email": "USER@example.com", "password": "long password"},
    )
    current = client.get("/api/v1/auth/me")

    assert login.status_code == 200
    assert current.status_code == 200
    assert current.json()["email"] == "user@example.com"
    assert set(current.json()) == {"id", "email", "created_at"}


def test_login_uses_generic_error_for_unknown_email_and_wrong_password(
    client: TestClient,
) -> None:
    register(client)
    wrong_password = client.post(
        "/api/v1/auth/login",
        headers=ORIGIN,
        json={"email": "user@example.com", "password": "wrong password"},
    )
    unknown_email = client.post(
        "/api/v1/auth/login",
        headers=ORIGIN,
        json={"email": "unknown@example.com", "password": "wrong password"},
    )

    assert wrong_password.status_code == 401
    assert unknown_email.status_code == 401
    assert wrong_password.json() == unknown_email.json() == {
        "detail": "Invalid email or password"
    }


def test_me_rejects_missing_and_forged_sessions(client: TestClient) -> None:
    assert client.get("/api/v1/auth/me").status_code == 401
    client.cookies.set("fitsho_session", "forged")
    assert client.get("/api/v1/auth/me").status_code == 401


def test_expired_session_is_deleted(client: TestClient, db: Session) -> None:
    register(client)
    raw_token = client.cookies["fitsho_session"]
    stored = db.scalar(
        select(AuthSession).where(
            AuthSession.token_hash == hash_session_token(raw_token)
        )
    )
    assert stored is not None
    stored.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    db.commit()

    assert client.get("/api/v1/auth/me").status_code == 401
    assert db.get(AuthSession, stored.id) is None


def test_logout_invalidates_only_current_session(client: TestClient) -> None:
    register(client)

    assert client.post("/api/v1/auth/logout", headers=ORIGIN).status_code == 204
    assert client.get("/api/v1/auth/me").status_code == 401
    assert client.post("/api/v1/auth/logout", headers=ORIGIN).status_code == 204
```

- [ ] **Step 2: شکست را تأیید کن**

```bash
cd backend
.venv/bin/pytest tests/auth/test_sessions.py -v
```

خروجی مورد انتظار:

```text
FAIL: login, me, and logout routes are missing
```

- [ ] **Step 3: عملیات نشست را به سرویس اضافه کن**

```python
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from app.auth.exceptions import InvalidCredentialsError
from app.auth.schemas import LoginRequest
from app.auth.security import (
    DUMMY_PASSWORD_HASH,
    hash_session_token,
    verify_password,
)


def login_user(
    db: Session,
    payload: LoginRequest,
    ttl_seconds: int,
) -> AuthResult:
    email = normalize_email(str(payload.email))
    user = db.scalar(select(User).where(User.email == email))
    stored_hash = user.password_hash if user is not None else DUMMY_PASSWORD_HASH
    password_is_valid = verify_password(payload.password, stored_hash)
    if user is None or not password_is_valid:
        raise InvalidCredentialsError

    raw_token, token_hash = make_session_token()
    db.add(
        AuthSession(
            user_id=user.id,
            token_hash=token_hash,
            expires_at=datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds),
        )
    )
    try:
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        raise
    return AuthResult(user=user, raw_token=raw_token)


def user_for_session(db: Session, raw_token: str) -> User | None:
    token_hash = hash_session_token(raw_token)
    auth_session = db.scalar(
        select(AuthSession).where(AuthSession.token_hash == token_hash)
    )
    if auth_session is None:
        return None
    if auth_session.expires_at <= datetime.now(timezone.utc):
        db.delete(auth_session)
        try:
            db.commit()
        except SQLAlchemyError:
            db.rollback()
            raise
        return None
    return db.get(User, auth_session.user_id)


def logout_session(db: Session, raw_token: str | None) -> None:
    if raw_token is None:
        return
    auth_session = db.scalar(
        select(AuthSession).where(
            AuthSession.token_hash == hash_session_token(raw_token)
        )
    )
    if auth_session is not None:
        db.delete(auth_session)
        try:
            db.commit()
        except SQLAlchemyError:
            db.rollback()
            raise
```

کد بالا به فایل سرویس افزوده شود.

- [ ] **Step 4: وابستگی کاربر فعلی را ایجاد کن**

```python
from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.auth.models import User
from app.auth.service import user_for_session
from app.config import Settings, get_settings
from app.database.session import get_db


def get_current_user(
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> User:
    raw_token = request.cookies.get(settings.session_cookie_name)
    if raw_token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )
    user = user_for_session(db, raw_token)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )
    return user
```

فایل:

```text
backend/app/auth/dependencies.py
```

- [ ] **Step 5: مسیرها را کامل کن**

```python
from fastapi import Request

from app.auth.dependencies import get_current_user
from app.auth.exceptions import InvalidCredentialsError
from app.auth.models import User
from app.auth.schemas import LoginRequest
from app.auth.service import login_user, logout_session


@router.post(
    "/login",
    response_model=UserResponse,
    dependencies=[Depends(require_trusted_origin)],
)
def login(
    payload: LoginRequest,
    response: Response,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> UserResponse:
    try:
        result = login_user(db, payload, settings.session_ttl_seconds)
    except InvalidCredentialsError:
        from fastapi import HTTPException

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        ) from None
    set_session_cookie(response, result.raw_token, settings)
    return UserResponse.model_validate(result.user)


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_trusted_origin)],
)
def logout(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> None:
    logout_session(db, request.cookies.get(settings.session_cookie_name))
    clear_session_cookie(response, settings)


@router.get("/me", response_model=UserResponse)
def me(user: User = Depends(get_current_user)) -> UserResponse:
    return UserResponse.model_validate(user)
```

کد بالا به مسیریاب افزوده شود و importهای تکراری در بالای فایل یکپارچه شوند.

- [ ] **Step 6: آزمایش‌های نشست و کل بخش سرور را اجرا کن**

```bash
cd backend
.venv/bin/pytest tests/auth/test_sessions.py -v
.venv/bin/pytest -v
.venv/bin/ruff check app tests
.venv/bin/mypy app
```

خروجی مورد انتظار:

```text
5 session tests passed
all backend tests passed
All checks passed
Success: no issues found
```

- [ ] **Step 7: ثبت کن**

```bash
git add backend/app/auth backend/tests/auth
git commit -m "feat: add login and server-side sessions"
```

---

### Task 6: ستون فقرات رابط کاربری و ارتباط احراز هویت

**فایل‌ها**

ایجاد با ابزار ساخت و سپس تغییر:

```text
frontend/package.json
frontend/package-lock.json
frontend/vite.config.ts
frontend/src/test/setup.ts
frontend/src/features/auth/types.ts
frontend/src/features/auth/api.ts
frontend/src/features/auth/api.test.ts
frontend/src/features/auth/AuthContext.tsx
frontend/src/features/auth/AuthContext.test.tsx
```

**رابط‌های خروجی**

```typescript
type User = { id: string; email: string; created_at: string }
type Credentials = { email: string; password: string }
function register(credentials: Credentials): Promise<User>
function login(credentials: Credentials): Promise<User>
function logout(): Promise<void>
function getCurrentUser(): Promise<User | null>
function useAuth(): AuthContextValue
```

- [ ] **Step 1: پروژه رابط کاربری را بساز و ابزارهای لازم را نصب کن**

```bash
npm create vite@latest frontend -- --template react-ts
cd frontend
npm install
npm install react-router-dom
npm install --save-dev vitest jsdom @testing-library/react @testing-library/jest-dom @testing-library/user-event
npm pkg set scripts.test="vitest run"
```

خروجی مورد انتظار: فایل قفل وابستگی‌ها ساخته شود و نصب بدون خطا پایان یابد.

- [ ] **Step 2: محیط آزمایش و واسط توسعه را تنظیم کن**

```typescript
import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: false,
      },
    },
  },
  test: {
    environment: "jsdom",
    setupFiles: "./src/test/setup.ts",
    globals: true,
  },
});
```

فایل:

```text
frontend/vite.config.ts
```

```typescript
import "@testing-library/jest-dom/vitest";
```

فایل:

```text
frontend/src/test/setup.ts
```

- [ ] **Step 3: آزمایش ناموفق لایه ارتباط را بنویس**

```typescript
import { afterEach, describe, expect, it, vi } from "vitest";

import { getCurrentUser, login, logout, register } from "./api";

const user = {
  id: "018f0000-0000-7000-8000-000000000001",
  email: "user@example.com",
  created_at: "2026-07-24T00:00:00Z",
};

afterEach(() => vi.restoreAllMocks());

describe("auth api", () => {
  it("always includes browser credentials", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify(user), {
        status: 201,
        headers: { "Content-Type": "application/json" },
      }),
    );

    await register({ email: user.email, password: "long password" });

    expect(fetch).toHaveBeenCalledWith(
      "/api/v1/auth/register",
      expect.objectContaining({ credentials: "include" }),
    );
  });

  it("maps an unauthorized current-user response to null", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(null, { status: 401 }));

    await expect(getCurrentUser()).resolves.toBeNull();
  });

  it("calls login and logout endpoints", async () => {
    vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(
        new Response(JSON.stringify(user), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      )
      .mockResolvedValueOnce(new Response(null, { status: 204 }));

    await expect(login({ email: user.email, password: "long password" })).resolves.toEqual(user);
    await expect(logout()).resolves.toBeUndefined();
  });
});
```

- [ ] **Step 4: شکست لایه ارتباط را تأیید کن**

```bash
cd frontend
npm test -- src/features/auth/api.test.ts
```

خروجی مورد انتظار:

```text
FAIL: ./api does not exist
```

- [ ] **Step 5: نوع‌ها و لایه ارتباط را پیاده‌سازی کن**

```typescript
export type User = {
  id: string;
  email: string;
  created_at: string;
};

export type Credentials = {
  email: string;
  password: string;
};

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    message: string,
  ) {
    super(message);
  }
}
```

فایل:

```text
frontend/src/features/auth/types.ts
```

```typescript
import type { Credentials, User } from "./types";
import { ApiError } from "./types";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    ...init,
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...init?.headers,
    },
  });
  if (!response.ok) {
    const body = (await response.json().catch(() => null)) as { detail?: string } | null;
    throw new ApiError(response.status, body?.detail ?? "Request failed");
  }
  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}

export function register(credentials: Credentials): Promise<User> {
  return request<User>("/api/v1/auth/register", {
    method: "POST",
    body: JSON.stringify(credentials),
  });
}

export function login(credentials: Credentials): Promise<User> {
  return request<User>("/api/v1/auth/login", {
    method: "POST",
    body: JSON.stringify(credentials),
  });
}

export function logout(): Promise<void> {
  return request<void>("/api/v1/auth/logout", { method: "POST" });
}

export async function getCurrentUser(): Promise<User | null> {
  try {
    return await request<User>("/api/v1/auth/me");
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) {
      return null;
    }
    throw error;
  }
}
```

- [ ] **Step 6: آزمایش ناموفق زمینه احراز هویت را بنویس**

```typescript
import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";

import * as api from "./api";
import { AuthProvider, useAuth } from "./AuthContext";

afterEach(() => vi.restoreAllMocks());

function Probe() {
  const { user, loading } = useAuth();
  return <div>{loading ? "loading" : user?.email ?? "guest"}</div>;
}

it("loads the current user on startup", async () => {
  vi.spyOn(api, "getCurrentUser").mockResolvedValue({
    id: "1",
    email: "user@example.com",
    created_at: "2026-07-24T00:00:00Z",
  });

  render(
    <AuthProvider>
      <Probe />
    </AuthProvider>,
  );

  expect(screen.getByText("loading")).toBeInTheDocument();
  await waitFor(() => expect(screen.getByText("user@example.com")).toBeInTheDocument());
});
```

- [ ] **Step 7: زمینه احراز هویت را پیاده‌سازی کن**

```typescript
import {
  createContext,
  type ReactNode,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";

import * as api from "./api";
import type { Credentials, User } from "./types";

type AuthContextValue = {
  user: User | null;
  loading: boolean;
  register: (credentials: Credentials) => Promise<void>;
  login: (credentials: Credentials) => Promise<void>;
  logout: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.getCurrentUser()
      .then(setUser)
      .finally(() => setLoading(false));
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      loading,
      register: async (credentials) => setUser(await api.register(credentials)),
      login: async (credentials) => setUser(await api.login(credentials)),
      logout: async () => {
        await api.logout();
        setUser(null);
      },
    }),
    [loading, user],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (context === null) {
    throw new Error("useAuth must be used within AuthProvider");
  }
  return context;
}
```

- [ ] **Step 8: آزمایش و بررسی رابط کاربری را اجرا کن**

```bash
cd frontend
npm test -- src/features/auth/api.test.ts src/features/auth/AuthContext.test.tsx
npm run lint
npm run build
```

خروجی مورد انتظار:

```text
all selected tests passed
lint completed without errors
build completed successfully
```

- [ ] **Step 9: ثبت کن**

```bash
git add frontend
git commit -m "feat: add frontend authentication state"
```

---

### Task 7: فرم‌های ثبت‌نام و ورود

**پیش‌نیاز فرایندی**

پیش از طراحی ظاهری، راهنمای طراحی رابط کاربری خوانده شود تا صفحه‌ها راست‌به‌چپ،
متمایز و قابل دسترس باشند، بدون اینکه کتابخانه ظاهری غیرضروری اضافه شود.

```text
frontend-design
```

**فایل‌ها**

ایجاد:

```text
frontend/src/features/auth/RegisterPage.tsx
frontend/src/features/auth/RegisterPage.test.tsx
frontend/src/features/auth/LoginPage.tsx
frontend/src/features/auth/LoginPage.test.tsx
```

**رفتار خروجی**

- فرم ثبت‌نام رمز تکراری را فقط در مرورگر بررسی می‌کند.
- فرم‌ها هنگام ارسال دوباره ارسال نمی‌شوند.
- خطای اعتبارسنجی کنار فیلد و خطای سرور در ناحیه اعلام زنده نمایش داده می‌شود.
- موفقیت، کاربر را به داشبورد منتقل می‌کند.

- [ ] **Step 1: آزمایش ناموفق فرم ثبت‌نام را بنویس**

```typescript
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { expect, it, vi } from "vitest";

const { register } = vi.hoisted(() => ({ register: vi.fn() }));
vi.mock("./AuthContext", () => ({
  useAuth: () => ({ register }),
}));

import { RegisterPage } from "./RegisterPage";

it("does not submit mismatched passwords", async () => {
  const user = userEvent.setup();
  render(
    <MemoryRouter>
      <RegisterPage />
    </MemoryRouter>,
  );

  await user.type(screen.getByLabelText("ایمیل"), "user@example.com");
  await user.type(screen.getByLabelText("رمز عبور"), "long password");
  await user.type(screen.getByLabelText("تکرار رمز عبور"), "different password");
  await user.click(screen.getByRole("button", { name: "ساخت حساب" }));

  expect(register).not.toHaveBeenCalled();
  expect(screen.getByText("دو رمز عبور یکسان نیستند.")).toBeInTheDocument();
});


it("submits valid credentials once", async () => {
  register.mockResolvedValue(undefined);
  const user = userEvent.setup();
  render(
    <MemoryRouter>
      <RegisterPage />
    </MemoryRouter>,
  );

  await user.type(screen.getByLabelText("ایمیل"), "user@example.com");
  await user.type(screen.getByLabelText("رمز عبور"), "long password");
  await user.type(screen.getByLabelText("تکرار رمز عبور"), "long password");
  await user.click(screen.getByRole("button", { name: "ساخت حساب" }));

  expect(register).toHaveBeenCalledWith({
    email: "user@example.com",
    password: "long password",
  });
});
```

- [ ] **Step 2: آزمایش ناموفق فرم ورود را بنویس**

```typescript
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { expect, it, vi } from "vitest";

import { ApiError } from "./types";

const { login } = vi.hoisted(() => ({ login: vi.fn() }));
vi.mock("./AuthContext", () => ({
  useAuth: () => ({ login }),
}));

import { LoginPage } from "./LoginPage";

it("shows the generic invalid-credentials message", async () => {
  login.mockRejectedValue(new ApiError(401, "Invalid email or password"));
  const user = userEvent.setup();
  render(
    <MemoryRouter>
      <LoginPage />
    </MemoryRouter>,
  );

  await user.type(screen.getByLabelText("ایمیل"), "user@example.com");
  await user.type(screen.getByLabelText("رمز عبور"), "wrong password");
  await user.click(screen.getByRole("button", { name: "ورود" }));

  expect(await screen.findByRole("alert")).toHaveTextContent(
    "ایمیل یا رمز عبور درست نیست.",
  );
});
```

- [ ] **Step 3: شکست هر دو فرم را تأیید کن**

```bash
cd frontend
npm test -- src/features/auth/RegisterPage.test.tsx src/features/auth/LoginPage.test.tsx
```

خروجی مورد انتظار:

```text
FAIL: RegisterPage and LoginPage do not exist
```

- [ ] **Step 4: فرم ثبت‌نام را پیاده‌سازی کن**

```typescript
import { type FormEvent, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { useAuth } from "./AuthContext";
import { ApiError } from "./types";

export function RegisterPage() {
  const { register } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [passwordConfirmation, setPasswordConfirmation] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (password !== passwordConfirmation) {
      setError("دو رمز عبور یکسان نیستند.");
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      await register({ email, password });
      navigate("/dashboard", { replace: true });
    } catch (caught) {
      if (caught instanceof ApiError && caught.status === 409) {
        setError("این ایمیل قبلاً ثبت شده است.");
      } else if (caught instanceof TypeError) {
        setError("ارتباط با سرور برقرار نشد. دوباره تلاش کنید.");
      } else {
        setError("ثبت‌نام انجام نشد. دوباره تلاش کنید.");
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="auth-shell">
      <section className="auth-card" aria-labelledby="register-title">
        <p className="eyebrow">شروع مسیر شخصی شما</p>
        <h1 id="register-title">ساخت حساب</h1>
        <p>برای نگهداری امن برنامه‌ها و پیشرفتتان یک حساب بسازید.</p>
        <form onSubmit={handleSubmit}>
          <label htmlFor="register-email">ایمیل</label>
          <input
            id="register-email"
            type="email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            autoComplete="email"
            required
          />
          <label htmlFor="register-password">رمز عبور</label>
          <input
            id="register-password"
            dir="ltr"
            type={showPassword ? "text" : "password"}
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            autoComplete="new-password"
            minLength={8}
            maxLength={128}
            required
          />
          <label htmlFor="register-confirmation">تکرار رمز عبور</label>
          <input
            id="register-confirmation"
            dir="ltr"
            type={showPassword ? "text" : "password"}
            value={passwordConfirmation}
            onChange={(event) => setPasswordConfirmation(event.target.value)}
            autoComplete="new-password"
            minLength={8}
            maxLength={128}
            required
          />
          <button
            type="button"
            className="text-button"
            onClick={() => setShowPassword((visible) => !visible)}
          >
            {showPassword ? "پنهان‌کردن رمز" : "نمایش رمز"}
          </button>
          {error && <p role="alert">{error}</p>}
          <button type="submit" disabled={submitting}>
            {submitting ? "در حال ساخت…" : "ساخت حساب"}
          </button>
        </form>
        <p>
          حساب دارید؟ <Link to="/login">وارد شوید</Link>
        </p>
      </section>
    </main>
  );
}
```

- [ ] **Step 5: فرم ورود را پیاده‌سازی کن**

```typescript
import { type FormEvent, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { useAuth } from "./AuthContext";
import { ApiError } from "./types";

export function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      await login({ email, password });
      navigate("/dashboard", { replace: true });
    } catch (caught) {
      if (caught instanceof ApiError && caught.status === 401) {
        setError("ایمیل یا رمز عبور درست نیست.");
      } else if (caught instanceof TypeError) {
        setError("ارتباط با سرور برقرار نشد. دوباره تلاش کنید.");
      } else {
        setError("ورود انجام نشد. دوباره تلاش کنید.");
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="auth-shell">
      <section className="auth-card" aria-labelledby="login-title">
        <p className="eyebrow">بازگشت به برنامه شما</p>
        <h1 id="login-title">ورود</h1>
        <form onSubmit={handleSubmit}>
          <label htmlFor="login-email">ایمیل</label>
          <input
            id="login-email"
            type="email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            autoComplete="email"
            required
          />
          <label htmlFor="login-password">رمز عبور</label>
          <input
            id="login-password"
            dir="ltr"
            type={showPassword ? "text" : "password"}
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            autoComplete="current-password"
            minLength={8}
            maxLength={128}
            required
          />
          <button
            type="button"
            className="text-button"
            onClick={() => setShowPassword((visible) => !visible)}
          >
            {showPassword ? "پنهان‌کردن رمز" : "نمایش رمز"}
          </button>
          {error && <p role="alert">{error}</p>}
          <button type="submit" disabled={submitting}>
            {submitting ? "در حال ورود…" : "ورود"}
          </button>
        </form>
        <p>
          حساب ندارید؟ <Link to="/register">ثبت‌نام کنید</Link>
        </p>
      </section>
    </main>
  );
}
```

- [ ] **Step 6: آزمایش‌های فرم را سبز کن**

```bash
cd frontend
npm test -- src/features/auth/RegisterPage.test.tsx src/features/auth/LoginPage.test.tsx
npm run lint
```

خروجی مورد انتظار:

```text
all form tests passed
lint completed without errors
```

- [ ] **Step 7: ثبت کن**

```bash
git add frontend/src/features/auth
git commit -m "feat: add registration and login forms"
```

---

### Task 8: مسیر محافظت‌شده، داشبورد و خروج

**فایل‌ها**

ایجاد:

```text
frontend/src/features/auth/ProtectedRoute.tsx
frontend/src/pages/DashboardPage.tsx
frontend/src/App.test.tsx
```

تغییر:

```text
frontend/src/App.tsx
frontend/src/main.tsx
frontend/src/styles.css
```

- [ ] **Step 1: آزمایش ناموفق مسیریابی را بنویس**

```typescript
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { expect, it, vi } from "vitest";

import { AppRoutes } from "./App";

const auth = vi.hoisted(() => ({
  value: {
    user: null as null | {
      id: string;
      email: string;
      created_at: string;
    },
    loading: false,
    login: vi.fn(),
    register: vi.fn(),
    logout: vi.fn(),
  },
}));

vi.mock("./features/auth/AuthContext", () => ({
  useAuth: () => auth.value,
}));

it("redirects a guest away from the dashboard", () => {
  render(
    <MemoryRouter initialEntries={["/dashboard"]}>
      <AppRoutes />
    </MemoryRouter>,
  );

  expect(screen.getByRole("heading", { name: "ورود" })).toBeInTheDocument();
});


it("lets an authenticated user log out", async () => {
  auth.value = {
    user: {
      id: "1",
      email: "user@example.com",
      created_at: "2026-07-24T00:00:00Z",
    },
    loading: false,
    login: vi.fn(),
    register: vi.fn(),
    logout: vi.fn().mockResolvedValue(undefined),
  };
  const user = userEvent.setup();
  render(
    <MemoryRouter initialEntries={["/dashboard"]}>
      <AppRoutes />
    </MemoryRouter>,
  );

  expect(screen.getByText("user@example.com")).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "خروج" }));

  expect(auth.value.logout).toHaveBeenCalledOnce();
  expect(screen.getByRole("heading", { name: "ورود" })).toBeInTheDocument();
});
```

- [ ] **Step 2: شکست را تأیید کن**

```bash
cd frontend
npm test -- src/App.test.tsx
```

خروجی مورد انتظار:

```text
FAIL: AppRoutes or ProtectedRoute is missing
```

- [ ] **Step 3: مسیر محافظت‌شده را پیاده‌سازی کن**

```typescript
import { Navigate, Outlet } from "react-router-dom";

import { useAuth } from "./AuthContext";

export function ProtectedRoute() {
  const { user, loading } = useAuth();
  if (loading) {
    return <main aria-busy="true">در حال بررسی حساب…</main>;
  }
  return user ? <Outlet /> : <Navigate to="/login" replace />;
}
```

- [ ] **Step 4: داشبورد و مسیرها را پیاده‌سازی کن**

داشبورد:

```typescript
import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { useAuth } from "../features/auth/AuthContext";

export function DashboardPage() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleLogout() {
    setSubmitting(true);
    setError(null);
    try {
      await logout();
      navigate("/login", { replace: true });
    } catch {
      setError("خروج انجام نشد. دوباره تلاش کنید.");
      setSubmitting(false);
    }
  }

  return (
    <main className="dashboard-shell">
      <section className="dashboard-card">
        <p className="eyebrow">حساب شما آماده است</p>
        <h1>داشبورد</h1>
        <p dir="ltr">{user?.email}</p>
        <p>در مرحله بعد، پروفایل ورزشی و محدودیت‌های شما را ثبت می‌کنیم.</p>
        {error && <p role="alert">{error}</p>}
        <button type="button" onClick={handleLogout} disabled={submitting}>
          {submitting ? "در حال خروج…" : "خروج"}
        </button>
      </section>
    </main>
  );
}
```

مسیریابی:

```typescript
import { Navigate, Route, Routes } from "react-router-dom";

import { LoginPage } from "./features/auth/LoginPage";
import { ProtectedRoute } from "./features/auth/ProtectedRoute";
import { RegisterPage } from "./features/auth/RegisterPage";
import { DashboardPage } from "./pages/DashboardPage";

export function AppRoutes() {
  return (
    <Routes>
      <Route path="/register" element={<RegisterPage />} />
      <Route path="/login" element={<LoginPage />} />
      <Route element={<ProtectedRoute />}>
        <Route path="/dashboard" element={<DashboardPage />} />
      </Route>
      <Route path="*" element={<Navigate to="/dashboard" replace />} />
    </Routes>
  );
}
```

ریشه برنامه:

```typescript
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";

import { AppRoutes } from "./App";
import { AuthProvider } from "./features/auth/AuthContext";
import "./styles.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <BrowserRouter>
      <AuthProvider>
        <AppRoutes />
      </AuthProvider>
    </BrowserRouter>
  </StrictMode>,
);
```

- [ ] **Step 5: ظاهر راست‌به‌چپ و دسترس‌پذیر را کامل کن**

فایل سبک باید این ویژگی‌های پایه را داشته باشد:

```css
:root {
  font-family: Vazirmatn, system-ui, sans-serif;
  color: #173126;
  background: #f4f1e8;
  font-synthesis: none;
}

* {
  box-sizing: border-box;
}

body {
  margin: 0;
  min-width: 320px;
  min-height: 100vh;
  direction: rtl;
}

.auth-shell,
.dashboard-shell {
  min-height: 100vh;
  display: grid;
  place-items: center;
  padding: 2rem 1rem;
  background:
    radial-gradient(circle at 15% 15%, #d6e6c3 0 8rem, transparent 8.1rem),
    linear-gradient(145deg, #f7f2e7, #e8efe1);
}

.auth-card,
.dashboard-card {
  width: min(100%, 30rem);
  padding: clamp(1.5rem, 4vw, 3rem);
  border: 1px solid #c7d2bd;
  border-radius: 1.5rem 0.4rem 1.5rem 0.4rem;
  background: rgba(255, 255, 255, 0.9);
  box-shadow: 0 1.5rem 4rem rgba(35, 64, 50, 0.12);
}

.eyebrow {
  margin: 0;
  color: #b95f24;
  font-size: 0.85rem;
  font-weight: 700;
  letter-spacing: 0.04em;
}

h1 {
  margin-block: 0.4rem 1rem;
  font-size: clamp(2rem, 8vw, 3.5rem);
  line-height: 1;
}

form {
  display: grid;
  gap: 0.75rem;
  margin-block: 1.5rem;
}

label {
  font-weight: 700;
}

input {
  width: 100%;
  min-height: 3rem;
  padding-inline: 0.9rem;
  border: 1px solid #9daf99;
  border-radius: 0.45rem;
  background: #fffef9;
  font: inherit;
}

input[type="email"],
input[type="password"] {
  direction: ltr;
  text-align: left;
}

button {
  min-height: 3rem;
  padding-inline: 1.2rem;
  border: 0;
  border-radius: 0.45rem;
  color: #fff;
  background: #1f5c43;
  font: inherit;
  font-weight: 800;
  cursor: pointer;
}

button:hover {
  background: #174734;
}

button:disabled {
  cursor: wait;
  opacity: 0.65;
}

.text-button {
  justify-self: start;
  min-height: auto;
  padding: 0;
  color: #1f5c43;
  background: transparent;
  font-weight: 700;
}

[role="alert"] {
  padding: 0.75rem;
  border-right: 4px solid #a93c2f;
  color: #7a271d;
  background: #fff0ec;
}

a {
  color: #9a4b1d;
  font-weight: 800;
}

button:focus-visible,
input:focus-visible,
a:focus-visible {
  outline: 3px solid #d97732;
  outline-offset: 2px;
}
```

استفاده از قلم بیرونی یا شبکه توزیع محتوا در این مرحله ممنوع است؛ فهرست قلم بالا باید
به قلم‌های موجود سیستم بازگردد.

- [ ] **Step 6: تمام آزمایش‌های رابط کاربری را اجرا کن**

```bash
cd frontend
npm test
npm run lint
npm run build
```

خروجی مورد انتظار:

```text
all frontend tests passed
lint completed without errors
production build completed successfully
```

- [ ] **Step 7: ثبت کن**

```bash
git add frontend/src
git commit -m "feat: protect dashboard and add logout"
```

---

### Task 9: سخت‌سازی قراردادها و بررسی یکپارچه

**فایل‌ها**

تغییر:

```text
backend/app/main.py
backend/app/auth/service.py
backend/tests/auth/test_register.py
frontend/src/features/auth/RegisterPage.test.tsx
```

- [ ] **Step 1: آزمایش ناموفق خطای پایگاه داده و بازگشت تراکنش را اضافه کن**

```python
from sqlalchemy.exc import OperationalError


def test_database_failure_returns_503_and_rolls_back_user(
    client: TestClient,
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_commit = db.commit

    def unavailable_commit() -> None:
        raise OperationalError("COMMIT", {}, Exception("database unavailable"))

    monkeypatch.setattr(db, "commit", unavailable_commit)
    response = client.post(
        "/api/v1/auth/register",
        headers={"Origin": "http://localhost:5173"},
        json={"email": "rollback@example.com", "password": "long password"},
    )
    monkeypatch.setattr(db, "commit", original_commit)

    assert response.status_code == 503
    assert response.json() == {"detail": "Service temporarily unavailable"}
    assert db.scalar(
        select(User).where(User.email == "rollback@example.com")
    ) is None
```

این آزمایش به فایل ثبت‌نام اضافه شود و واردکردن ابزار آزمایش و خطای عملیاتی نیز در
بالای فایل قرار گیرد.

- [ ] **Step 2: شکست مشخص را تأیید کن**

```bash
cd backend
.venv/bin/pytest tests/auth/test_register.py::test_database_failure_returns_503_and_rolls_back_user -v
```

خروجی مورد انتظار:

```text
FAIL: OperationalError is not mapped to 503 and the transaction is not rolled back
```

- [ ] **Step 3: بازگشت خطا و پاسخ عمومی پایگاه داده را پیاده‌سازی کن**

در سرویس ثبت‌نام، شاخه خطای پایگاه داده پس از شاخه یکتایی اضافه شود:

```python
from sqlalchemy.exc import IntegrityError, SQLAlchemyError


except IntegrityError as error:
    db.rollback()
    raise EmailAlreadyRegisteredError from error
except SQLAlchemyError:
    db.rollback()
    raise
```

در کارخانه برنامه، مدیریت خطای پایگاه داده اضافه شود:

```python
from fastapi import Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError


@app.exception_handler(SQLAlchemyError)
async def database_error_handler(
    request: Request,
    error: SQLAlchemyError,
) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={"detail": "Service temporarily unavailable"},
    )
```

نام پارامترها برای ثبت امن نوع خطا قابل استفاده است، اما محتوای استثنا نباید داخل
پاسخ یا گزارش عمومی قرار گیرد.

- [ ] **Step 4: آزمایش ویژگی‌های کوکی محیط اصلی را اضافه کن**

```python
def test_production_cookie_uses_host_security_prefix(
    db: Session,
    test_settings: Settings,
) -> None:
    production_settings = test_settings.model_copy(
        update={
            "app_env": "production",
            "frontend_origin": "https://fitsho.example",
            "cookie_secure": True,
            "session_cookie_name": "__Host-fitsho_session",
        }
    )
    app = create_app(production_settings)

    def override_db() -> Iterator[Session]:
        yield db

    app.dependency_overrides[get_db] = override_db
    with TestClient(app, base_url="https://testserver") as secure_client:
        response = secure_client.post(
            "/api/v1/auth/register",
            headers={"Origin": "https://fitsho.example"},
            json={"email": "secure@example.com", "password": "long password"},
        )

    cookie = response.headers["set-cookie"]
    assert response.status_code == 201
    assert cookie.startswith("__Host-fitsho_session=")
    assert "HttpOnly" in cookie
    assert "Secure" in cookie
    assert "SameSite=lax" in cookie
    assert "Path=/" in cookie
    assert "Domain=" not in cookie
```

این آزمایش به فایل ثبت‌نام اضافه شود. واردکردن کارخانه برنامه، تنظیمات، وابستگی
پایگاه داده و نوع تکرارگر نیز به‌صورت صریح در بالای فایل انجام شود.

- [ ] **Step 5: آزمایش خطای قطعی شبکه رابط کاربری را اضافه کن**

```typescript
it("shows a retryable message for a network failure", async () => {
  register.mockRejectedValue(new TypeError("network failure"));
  const user = userEvent.setup();
  render(
    <MemoryRouter>
      <RegisterPage />
    </MemoryRouter>,
  );

  await user.type(screen.getByLabelText("ایمیل"), "user@example.com");
  await user.type(screen.getByLabelText("رمز عبور"), "long password");
  await user.type(screen.getByLabelText("تکرار رمز عبور"), "long password");
  await user.click(screen.getByRole("button", { name: "ساخت حساب" }));

  expect(await screen.findByRole("alert")).toHaveTextContent(
    "ارتباط با سرور برقرار نشد. دوباره تلاش کنید.",
  );
  expect(screen.queryByText("long password")).not.toBeInTheDocument();
});
```

- [ ] **Step 6: آزمایش‌های سخت‌سازی را اجرا کن**

```bash
cd backend
.venv/bin/pytest tests/auth -v
cd ../frontend
npm test -- src/features/auth/RegisterPage.test.tsx
```

خروجی مورد انتظار: تمام آزمایش‌های سخت‌سازی موفق باشند و هیچ داده حساسی در پیام
شکست ظاهر نشود.

- [ ] **Step 7: مجموعه کامل بررسی‌ها را اجرا کن**

```bash
cd backend
.venv/bin/pytest --cov=app --cov-report=term-missing
.venv/bin/ruff check app tests
.venv/bin/ruff format --check app tests
.venv/bin/mypy app
cd ../frontend
npm test
npm run lint
npm run build
```

خروجی مورد انتظار:

```text
all backend tests passed
all frontend tests passed
all static checks passed
production build completed successfully
```

- [ ] **Step 8: ثبت کن**

```bash
git add backend frontend
git commit -m "test: harden authentication boundaries"
```

---

### Task 10: مستندسازی و تأیید نهایی مسیر واقعی

**فایل‌ها**

تغییر با حفظ محتوای موجود:

```text
README.md
```

- [ ] **Step 1: پیش‌نیازها و راه‌اندازی را مستند کن**

بخش توسعه باید این موارد را به‌ترتیب توضیح دهد:

1. ساخت فایل محیط از نمونه
2. اجرای پایگاه داده
3. ساخت محیط پایتون و نصب وابستگی‌ها
4. اجرای مهاجرت
5. اجرای بخش سرور
6. نصب و اجرای رابط کاربری
7. اجرای آزمایش‌ها و بررسی‌های ایستا

فرمان‌های مستند:

```bash
cp .env.example backend/.env
docker compose up -d db

cd backend
python -m venv .venv
.venv/bin/python -m pip install -e ".[dev]"
.venv/bin/alembic upgrade head
.venv/bin/uvicorn app.main:app --reload

cd ../frontend
npm install
npm run dev
```

متن زیر بدون حذف بخش‌های معرفی و اصول محصول به انتهای فایل راهنما افزوده شود:

````markdown
## Local development

### Prerequisites

- Python 3.12 or newer
- Node.js 24 LTS or newer with npm
- Docker with Docker Compose

### Start PostgreSQL

```bash
cp .env.example backend/.env
docker compose up -d db
```

### Start the API

```bash
cd backend
python -m venv .venv
.venv/bin/python -m pip install -e ".[dev]"
.venv/bin/alembic upgrade head
.venv/bin/uvicorn app.main:app --reload
```

The interactive API documentation is available at:

```text
http://localhost:8000/docs
```

### Start the frontend

```bash
cd frontend
npm install
npm run dev
```

Open the application at:

```text
http://localhost:5173
```

### Run checks

```bash
cd backend
.venv/bin/pytest --cov=app --cov-report=term-missing
.venv/bin/ruff check app tests
.venv/bin/ruff format --check app tests
.venv/bin/mypy app

cd ../frontend
npm test
npm run lint
npm run build
```
````

- [ ] **Step 2: پایگاه داده آزمایش را از ابتدا مهاجرت بده**

```bash
cd backend
DATABASE_URL=postgresql+psycopg://fitsho:fitsho@localhost:5432/fitsho_test .venv/bin/alembic downgrade base
DATABASE_URL=postgresql+psycopg://fitsho:fitsho@localhost:5432/fitsho_test .venv/bin/alembic upgrade head
```

خروجی مورد انتظار: رفت و برگشت مهاجرت بدون خطا.

- [ ] **Step 3: بررسی کامل را از ریشه پروژه اجرا کن**

```bash
cd backend
.venv/bin/pytest --cov=app --cov-report=term-missing
.venv/bin/ruff check app tests
.venv/bin/ruff format --check app tests
.venv/bin/mypy app

cd ../frontend
npm test
npm run lint
npm run build
```

هیچ ادعای موفقیت قبل از مشاهده خروجی واقعی این فرمان‌ها مجاز نیست.

- [ ] **Step 4: مسیر واقعی را به‌صورت دستی بررسی کن**

بخش سرور و رابط کاربری را اجرا کن و این مسیر را در مرورگر طی کن:

```text
register -> automatic login -> dashboard -> logout -> login -> dashboard
```

در ابزار توسعه مرورگر تأیید کن:

- توکن برای جاوااسکریپت قابل خواندن نیست.
- پاسخ کاربر فقط شناسه، ایمیل و زمان ساخت را دارد.
- درخواست داشبورد بدون نشست به ورود هدایت می‌شود.
- خروج، نشست جاری را نامعتبر می‌کند.

- [ ] **Step 5: محدوده و داده حساس را بازبینی کن**

```bash
rg -n "localStorage|sessionStorage|password_hash|token_hash|raw_token" backend frontend
git diff --check
git status --short
```

خروجی‌ها را دستی بررسی کن:

- هیچ ذخیره توکن در مرورگر وجود نداشته باشد.
- فیلدهای حساس فقط در مدل و منطق داخلی ظاهر شوند.
- هیچ فایل محیط، پایگاه داده یا وابستگی تولیدی ثبت نشده باشد.
- تغییر نامرتبط وارد ثبت نهایی نشده باشد.

- [ ] **Step 6: ثبت مستندات**

```bash
git add README.md
git commit -m "docs: add local authentication setup"
```

## پایان برنامه

پس از پایان وظیفه دهم، قابلیت احراز هویت کامل است. کار متوقف شود و هیچ قابلیت دیگری
بدون درخواست و انتخاب بعدی کاربر شروع نشود.
