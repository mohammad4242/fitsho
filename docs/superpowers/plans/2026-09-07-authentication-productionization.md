# Authentication Productionization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Finish the existing Fitsho authentication flows for production use while preserving the opaque `AuthSession` architecture and existing auth UI.

**Architecture:** Keep `User`, `AuthSession`, secure cookies, and `app.auth.service` as the single authentication path. Harden the existing provider adapters, add the missing email-verification frontend handoff, and document environment configuration without changing unrelated features.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy, PostgreSQL, Alembic, `google-auth`, SMTP, Kavenegar REST, React 19, TypeScript, React Router, Vitest.

**Spec:** `docs/superpowers/specs/2026-09-07-authentication-productionization-design.md`

## Global Constraints

- Preserve `User` + `AuthSession` + the existing secure session cookie.
- Preserve `POST /api/v1/auth/register`, `/login`, `/logout`, and `GET /api/v1/auth/me` contracts.
- Never store or log raw passwords, OTPs, reset tokens, verification tokens, session tokens, Google credentials, SMTP passwords, or Kavenegar API keys.
- Keep phone OTP generic, hashed, expiring, single-use, attempt-limited, and cooldown-protected.
- Use Google `sub` as the durable identity key and never trust frontend-decoded claims.
- Do not modify unrelated nutrition, workout, profile, body-analysis, or media behavior.
- Preserve the existing user-authored working-tree changes and stage only task files.

---

### Task 1: Harden provider result handling and Google identity completion

**Files:**
- Modify: `backend/app/auth/providers.py`
- Modify: `backend/app/auth/service.py`
- Test: `backend/tests/auth/test_providers.py`
- Test: `backend/tests/auth/test_google_auth.py`

**Interfaces:**
- `KavenegarSmsProvider.send_login_otp(phone_number: str, code: str) -> None` remains the SMS boundary.
- `authenticate_google(db: Session, identity: GoogleIdentity, session_ttl_seconds: int) -> AuthResult` remains the account/session boundary.

- [ ] **Step 1: Write failing tests**

Add a provider test whose fake Kavenegar response has HTTP 200 but `return.status` 424 and assert
`send_login_otp` raises a safe provider error. Add a Google test that first authenticates a
Google-only user with no verified email, then authenticates the same `sub` with a verified email,
and asserts the existing user receives that email and `email_verified_at` without a duplicate.

- [ ] **Step 2: Run focused tests to verify the failures**

Run:

```bash
cd backend
uv run pytest tests/auth/test_providers.py tests/auth/test_google_auth.py -q
```

Expected: the new Kavenegar test does not raise and the Google user remains without the later
verified email.

- [ ] **Step 3: Implement the smallest provider/service changes**

After the failing tests are observed, make Kavenegar treat a non-200 JSON `return.status` or an
invalid provider response as a delivery exception without including the response body or API key.
In `authenticate_google`, when an existing `google_sub` user has no email and receives a verified
email, lock/check the normalized email owner, reject a different owner with
`GoogleAccountConflictError`, then attach the verified email and timestamp atomically.

- [ ] **Step 4: Run focused tests and static checks**

Run:

```bash
cd backend
uv run pytest tests/auth/test_providers.py tests/auth/test_google_auth.py -q
uv run ruff check app/auth/providers.py app/auth/service.py tests/auth/test_providers.py tests/auth/test_google_auth.py
uv run mypy app/auth/providers.py app/auth/service.py
```

Expected: all focused tests and checks pass.

- [ ] **Step 5: Commit and push**

```bash
git add backend/app/auth/providers.py backend/app/auth/service.py backend/tests/auth/test_providers.py backend/tests/auth/test_google_auth.py
git commit -m "fix(auth): harden provider results and Google identity completion"
git push
```

### Task 2: Complete the email-verification frontend handoff

**Files:**
- Create: `frontend/src/features/auth/VerifyEmailPage.tsx`
- Modify: `frontend/src/features/auth/api.ts`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/i18n/fa.ts`
- Modify: `frontend/src/i18n/en.ts`
- Test: `frontend/src/features/auth/PasswordRecoveryPages.test.tsx`
- Test: `frontend/src/features/auth/api.test.ts`

**Interfaces:**
- `verifyEmail(token: string): Promise<void>` calls `POST /api/v1/auth/email/verify`.
- `/verify-email?token=<raw-token>` remains a guest route and does not create a new session system.

- [ ] **Step 1: Write the failing page/API regression test**

Keep the existing user-authored `verifyEmail` API test and add page tests for a valid token calling
the API and showing a success status, an invalid token showing the generic invalid state, and a
missing token not calling the API.

- [ ] **Step 2: Run the focused frontend tests to verify failure**

Run:

```bash
cd frontend
npm run test -- --run src/features/auth/api.test.ts src/features/auth/PasswordRecoveryPages.test.tsx
```

Expected: the existing API test fails because `verifyEmail` is absent, and the new page tests fail
because the page/route is absent.

- [ ] **Step 3: Implement the minimal API, page, route, and translations**

Add `verifyEmail` beside the existing auth API functions. Build the page with `AuthShell`,
`useSearchParams`, one guarded effect, generic API error mapping, Persian-first/English copy, and
a login link. Add the lazy import and guest route in `App.tsx`; do not change existing auth layout
or CSS.

- [ ] **Step 4: Run focused and full frontend auth tests**

Run:

```bash
cd frontend
npm run test -- --run src/features/auth
```

Expected: all auth tests pass, including existing email, phone, Google, forgot-password, and
reset-password regressions.

- [ ] **Step 5: Commit and push**

```bash
git add frontend/src/features/auth/VerifyEmailPage.tsx frontend/src/features/auth/api.ts frontend/src/App.tsx frontend/src/i18n/fa.ts frontend/src/i18n/en.ts frontend/src/features/auth/PasswordRecoveryPages.test.tsx
git commit -m "feat(auth): complete email verification link flow"
git push
```

### Task 3: Publish complete environment and operator setup

**Files:**
- Create: `frontend/.env.example`
- Create: `docs/authentication-setup.md`
- Modify: `.env.example`
- Modify: `README.md`

**Interfaces:**
- Backend reads secret/provider values from `backend/.env`.
- Vite reads only public values such as `VITE_GOOGLE_CLIENT_ID` from `frontend/.env`.

- [ ] **Step 1: Add configuration documentation**

Document `EMAIL_PROVIDER`, SMTP settings, `EMAIL_VERIFICATION_TTL_SECONDS`,
`SMS_PROVIDER`, Kavenegar API/base/template settings, `GOOGLE_CLIENT_ID`, auth rate limits,
`PHONE_OTP_HMAC_SECRET`, `FRONTEND_ORIGIN`, localhost origins, production origins, and the public
`VITE_GOOGLE_CLIENT_ID`. Explicitly state which values are backend-only secrets.

- [ ] **Step 2: Update examples and README links**

Add safe empty placeholders for every auth setting to `.env.example`, add the frontend public env
example, and link the setup document from the root README. Do not add real credentials.

- [ ] **Step 3: Verify documentation/config surface**

Run:

```bash
rg -n "EMAIL_PROVIDER|SMTP_|EMAIL_VERIFICATION_TTL_SECONDS|SMS_PROVIDER|KAVENEGAR_|GOOGLE_CLIENT_ID|PHONE_OTP_HMAC_SECRET|VITE_GOOGLE_CLIENT_ID" .env.example frontend/.env.example docs/authentication-setup.md
git diff --check
```

Expected: every required setting is present and no whitespace errors are reported.

- [ ] **Step 4: Commit and push**

```bash
git add .env.example frontend/.env.example docs/authentication-setup.md README.md
git commit -m "docs(auth): document transactional provider configuration"
git push
```

### Task 4: Run migration, regression, and production-build verification

**Files:**
- Verify only: `backend/alembic/versions/20260907_125_productionize_authentication.py`
- Verify only: `backend/alembic/versions/20260907_126_add_user_profile_photos.py`
- Verify only: auth source, tests, and frontend files changed above

- [ ] **Step 1: Verify database migration state**

Run:

```bash
cd backend
uv run alembic upgrade head
uv run alembic current
```

Expected: current revision is `20260907_126 (head)` and no migration error occurs.

- [ ] **Step 2: Run backend validation**

Run:

```bash
cd backend
uv run pytest
uv run ruff check
uv run mypy app
```

Record exact failures and distinguish unrelated pre-existing failures from auth regressions.

- [ ] **Step 3: Run frontend validation**

Run:

```bash
cd frontend
npm run test -- --run
npm run lint
npm run build
```

Record exact failures and distinguish unrelated pre-existing failures from auth regressions.

- [ ] **Step 4: Inspect final diff and Git state**

Run:

```bash
git diff --check
git diff --stat origin/main...HEAD
git status --short --branch
```

Confirm only the staged authentication/docs commits changed tracked task files and unrelated user
WIP remains untouched.
