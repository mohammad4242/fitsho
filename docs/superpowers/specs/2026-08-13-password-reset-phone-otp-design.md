# Password Reset and Phone OTP Design

## Scope

Extend the existing `app/auth` module and browser session flow. Email/password registration and
login remain compatible. Phone OTP verification creates a phone-only account when the normalized
phone is not already registered.

## Account model

- Add nullable, unique `phone_number` to `users`, stored in Iranian E.164 form (`+989...`).
- Make `email` and `password_hash` nullable for phone-only users.
- Keep existing rows unchanged and require each user to have at least one login identifier.
- Return nullable `email` and `phone_number` from the existing public user response.

## Password reset

- `POST /api/v1/auth/forgot-password` always returns the same accepted response.
- For a matching email account, generate a high-entropy URL-safe token, store only its SHA-256
  digest, and send a link through the configured email provider.
- `POST /api/v1/auth/reset-password` accepts the raw token and a new password. A valid, unexpired,
  unused token updates the password, consumes all reset tokens for that user, and deletes every
  existing `AuthSession` for the user in one transaction.
- SMTP is the production email implementation. A fake in-memory provider is used by tests.

## Phone OTP

- Normalize `09...`, `+98...`, and `0098...` to `+989...`; reject other formats.
- `POST /api/v1/auth/phone/send-otp` creates a six-digit cryptographically random code. The database
  stores only an HMAC-SHA-256 digest using a backend-only secret.
- A persisted challenge records expiration, resend availability, remaining attempts, consumption,
  and creation time. Resending before cooldown returns the same generic accepted response without
  sending. An allowed resend invalidates prior active challenges.
- `POST /api/v1/auth/phone/verify-otp` uses a generic invalid-code response for unknown, expired,
  exhausted, reused, or wrong challenges. Wrong codes consume an attempt. Successful verification
  consumes the challenge, finds or creates the user, and creates the existing opaque `AuthSession`.
- Kavenegar is the production SMS implementation. A fake in-memory provider is used by tests.

## Configuration and delivery

- Provider selection, SMTP host/port/user/password/from-address/TLS, Kavenegar base URL/API key/
  sender, OTP HMAC secret, TTLs, cooldown, and attempt limits are environment-driven.
- Production validation requires real provider configuration and a strong OTP HMAC secret.
- No credentials or message secrets are logged or returned.

## Frontend

- Keep `LoginPage` and add email/mobile tabs. The email form fields and login behavior remain.
- Add `/forgot-password` and `/reset-password` guest routes using the existing `AuthShell`.
- Mobile mode supports send, OTP verification, cooldown countdown, resend, loading, and generic
  errors. Successful verification updates `AuthContext` and navigates like email login.
- Add Persian-first translations with English equivalents and reuse existing auth styles.

## Security and testing

- Every state-changing endpoint uses the existing trusted-origin dependency.
- Tests cover hashing, normalization, generic responses, expiry, reuse, attempts, cooldown, session
  invalidation, account creation, migration constraints, email-login regression, API contracts, and
  frontend flows.
- Verification includes backend tests, Ruff, `mypy app`, Alembic upgrade/current; frontend tests,
  lint, and production build.
