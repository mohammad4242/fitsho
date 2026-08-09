# Nutrition security and privacy

## Access and roles

Nutrition records are owner-scoped. Lab files are available only to their owner or an assigned
physician who has a related review. Administrator status does not grant clinical access. Food
photos are owner-only. Cross-user lookups return not found.

Private files are outside the public media root. A file download requires both an authenticated
session and an HMAC-signed, actor-bound, resource-bound URL that expires after five minutes by
default. Signing keys must be random production secrets and are never returned by an API.

## Uploads and third-party processing

Food-photo processing requires explicit consent. Images are decoded, bounded by byte and pixel
limits, converted to JPEG, and re-encoded without source metadata before OpenRouter receives the
minimum image payload. No profile, identity, lab, or medical free text is sent to the model.

Lab uploads accept structurally valid PDF, JPEG, or PNG files. Active PDF content and malformed,
oversized, or decompression-bomb images are rejected. Lab files are never sent to an AI provider.
Database-backed rate limits protect both upload paths. `Idempotency-Key` prevents duplicate food
photo inference; content hashes prevent duplicate lab storage.

## Retention and audit

Food-photo content and estimates expire after `FOOD_PHOTO_RETENTION_DAYS`. Lab binaries expire
after `NUTRITION_LAB_RETENTION_DAYS`; their minimal audit row remains. A daily idempotent cleanup
runs under a PostgreSQL advisory lock and retries hourly after failure. Developers can run it with:

```bash
cd backend
uv run python -m app.nutrition.retention_cleanup
```

Security audit events contain IDs, action, outcome, content type, and byte count only. They never
contain image bytes, lab contents, user notes, medical free text, credentials, or signed tokens.
Physician review and supplement workflows retain their dedicated immutable audit records.

## Operations

The nutrition admin monitoring API reports price-provider health and aggregate AI request, error,
and token counters. Operational events contain safe counters and generic failure state only.
Encrypted AI provider credentials use the existing AI credential store and remain masked in admin
responses and audit logs.
