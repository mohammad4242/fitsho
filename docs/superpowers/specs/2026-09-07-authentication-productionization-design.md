# Authentication Productionization Design

## Scope

Finish the existing Fitsho authentication implementation without replacing its server-side
opaque-session architecture or changing unrelated product areas. The current tree already
contains email/password authentication, password recovery, phone OTP, provider adapters, Google
ID-token authentication, email verification storage, and migration `20260907_125`.

This change closes the remaining production gaps: make the verification link usable in the current
frontend, validate provider success responses, handle a Google identity that first authenticated
without an email and later returns a verified email, document all configuration, and preserve
regression coverage.

## Architecture

Every successful method continues through the same path:

```text
email/password | phone OTP | verified Google ID token
                         -> User
                         -> AuthSession
                         -> existing secure session cookie
```

`EmailProvider`, `SmsProvider`, and `GoogleIdentityProvider` remain transport/verification
boundaries. They do not create users or sessions. `app.auth.service` remains the owner of account
linking, token hashing, transaction boundaries, and session creation.

The Google durable identity key is `google_sub`. Verified Google email may link only to an account
with no conflicting `google_sub`; unverified or absent email never performs email linking. A
Google-only user may retain a null email and password hash.

## Delivery behavior

- SMTP uses one reusable internal send method for reset, verification, and welcome messages.
- Kavenegar authentication OTPs use `verify/lookup.json` with the configured template. Both HTTP
  failures and Kavenegar application-level non-200 statuses are treated as delivery failures.
- Delivery failures are logged with safe provider/error-class context only; secrets and message
  tokens are never logged, and public responses remain generic.
- Reset and verification links use the configured frontend origin and raw tokens only in the link.

## Frontend behavior

The existing login, phone OTP, forgot-password, reset-password, and Google UI stay visually
unchanged. A small `/verify-email` guest route reads the token from the link, calls the existing
API client, and displays success or a generic invalid/expired state with a link back to login.
`VITE_GOOGLE_CLIENT_ID` is public frontend configuration; all provider credentials remain backend
configuration.

## Verification

Add focused tests for provider response handling, Google verified-email completion, email
verification API wiring, and the verification page. Run focused auth tests first, then the full
repository checks and report unrelated pre-existing failures separately if they remain.
