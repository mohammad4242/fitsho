# AGENTS.md

## Project

Fitsho is an AI-powered fitness and nutrition companion. Monorepo with two packages:

- `backend/` — Python 3.12, FastAPI, SQLAlchemy, Alembic, PostgreSQL
- `frontend/` — React 19, TypeScript, Vite, Vitest, Oxlint

## Setup

### Backend

```bash
cd backend
uv sync
cp ../.env.example .env   # edit values; keep OPENCODE_ZEN_API_KEY out of git
```

### Frontend

```bash
cd frontend
npm install
```

### Services (PostgreSQL + backend)

```bash
docker compose up --build
```

The compose stack runs `alembic upgrade head` before starting the backend. The Docker
init script (`docker/postgres/init/01-create-test-db.sql`) creates the `fitsho_test`
database used by the test suite.

## Commands

### Backend

| Task | Command |
|---|---|
| Dev server | `uvicorn app.main:app --reload` |
| Lint | `ruff check` |
| Format | `ruff format` |
| Typecheck | `mypy` |
| Test | `pytest` |
| Migrations | `alembic upgrade head` |
| Autogenerate migration | `alembic revision --autogenerate -m "msg"` |
| Seed exercises | `python -m app.exercises.seed` |
| Import exercise dataset | `python -m app.exercises.free_exercise_db_import --source-root <path>` |
| Grant admin | `python -m app.admin.grant_admin <email>` |

### Frontend

| Task | Command |
|---|---|
| Dev server | `npm run dev` |
| Build | `npm run build` |
| Lint | `npm run lint` |
| Test | `npm run test` |
| Preview | `npm run preview` |

## Workflow

- Work in small, logical steps and run relevant checks after each step.
- When the user explicitly requests autonomous, end-to-end, or "continue until finished"
  execution, continue through every required step without waiting for intermediate approval.
- Progress updates must describe completed work or current verification; they must not end the
  turn while safe, in-scope implementation work remains.
- For autonomous execution, finish implementation, verification, focused commits, and pushing
  the current branch when a remote is configured before returning the final report.
- Stop early only for a genuine blocker that requires user authority, a material product choice,
  or an unavailable external dependency.

## Key Architecture Notes

### Backend

- **Settings** (`app/config.py`): loaded from a `.env` file in the current working
  directory. Run backend commands from `backend/` so it picks up `backend/.env`.
  `app_env` controls cookie security: `production` requires HTTPS, secure cookies,
  and the `__Host-fitsho_session` cookie name.
- **App entrypoint** (`app/main.py`): `app = create_app()`. The lifespan handler
  creates an `httpx.AsyncClient` stored on `app.state.zen_http_client` for the
  OpenCode Zen API.
- **Modules**: `auth`, `profile`, `workouts`, `exercises`, `admin`, `ai`, `database`.
- **Exercise import** (`app/exercises/free_exercise_db_import.py`): requires
  `--source-root` pointing to a directory containing `data/exercises.json`,
  `videos/male`, `videos/female`, `thumbnails/male`, `thumbnails/female`.
  Each exercise needs at least one local video asset. Uses
  `CuratedExerciseTranslator` by default; pass `--dry-run` to skip translation.
  Reports are written with `--report <path>`.
- **Exercise seed** (`app/exercises/seed.py`): loads 16 curated exercises with
  Persian translations and GIFs from `app/exercises/seed_data.py`.
- **Admin grant** (`app/admin/grant_admin.py`): promotes an existing user to
  admin by email. Admin routes are under `/admin/*`.
- **Test DB** (`tests/conftest.py`): uses `TEST_DATABASE_URL` env var
  (default `postgresql+psycopg://fitsho:fitsho@localhost:5432/fitsho_test`).
  A session-scoped fixture runs `alembic upgrade head` automatically. Each test
  gets a transaction that rolls back, so tests don't pollute each other.
- **Media**: stored in `var/media/` (gitignored). Served at `/media` via
  `StaticFiles`. Import copies files by SHA-256 hash into `var/media/free-exercise-db/`.
- **AI provider**: `app/ai/provider.py` defines the `WorkoutPlanModelProvider`
  protocol. `opencode_zen.py` is the real implementation; `fake_provider.py` is
  for tests. The HTTP client is created in the app lifespan and configured with
  `OPENCODE_ZEN_PROXY_URL` support.

### Frontend

- **Vite proxy** (`vite.config.ts`): `/api` and `/media` are proxied to
  `http://localhost:8000` during dev. No proxy needed in production (served by
  the same backend).
- **Tests** (`vitest.config` in `vite.config.ts`): jsdom environment, globals
  enabled, setup file at `src/test/setup.ts`.
- **i18n**: `src/i18n/` with `i18next` and `react-i18next`. Persian (fa) is the
  primary language.
- **Routing** (`src/App.tsx`): React Router v7 with nested routes. Route guards:
  `GuestRoute` (login/register), `ProtectedRoute`, `AdminRoute`, `OnboardingRoute`,
  `CompletedProfileRoute`.

## Conventions

- Backend: ruff line-length 100, target py312, select `E F I B UP`. mypy strict
  with pydantic plugin.
- Frontend: TypeScript strict, `verbatimModuleSyntax`, `noUnusedLocals`,
  `noUnusedParameters`. Oxlint with react and typescript plugins.
- Exercise slugs are generated as `fedb-<source_id>-<normalized_name>` for
  imported exercises, or manually defined for seeded exercises.
- Never commit `backend/.env` or any real API keys.
