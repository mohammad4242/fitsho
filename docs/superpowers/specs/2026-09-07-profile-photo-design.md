# Profile Photo Design

## Goal

Allow each Fitsho user to upload, replace, and delete one square-cropped profile photo. The photo is private, visible to the owner and to specialists who are already related to that user's active review or care record.

## Decisions

- Store photo metadata in a dedicated `user_profile_photos` table with one active row per user.
- Store normalized image bytes outside public media under a dedicated private profile-photo root.
- Accept JPEG, PNG, and WebP uploads up to 5 MiB. The browser creates a square crop preview and uploads the resulting image; the Backend still validates MIME, signature, decodability, dimensions, and byte size.
- Expose the image through an authenticated Backend content endpoint with `Cache-Control: private, no-store`; never expose a public `/media` URL.
- Owner access is always allowed. Coach access is allowed only when the coach owns a claimed workout review for the user. Physician access is allowed only when the physician owns an assigned/claimed nutrition review, lab request, supplement order, or equivalent active care record for the user. A specialist role by itself is insufficient.
- Replacing a photo stores the new object atomically, updates the active row, and removes the previous object only after the database transaction succeeds. Deleting removes the row and private object.
- The profile page owns upload/crop/delete controls. The authenticated header and More account card render the photo with the existing initial-letter fallback. Existing specialist response cards receive an optional photo content URL only when their current authorization already covers the user.

## Backend Design

Create a `user_profile_photos` model and Alembic migration with `user_id` as a unique foreign key to `users`, `storage_key`, `mime_type`, `byte_size`, `width`, `height`, and timestamps. Add `profile_photo_storage_root` and `profile_photo_max_bytes` settings, mount the root in Compose, and keep it outside `media_root`.

Add a focused profile-photo service that validates and normalizes uploads, writes through a temporary file plus `os.replace`, and validates storage keys before opening or deleting files. Add these authenticated routes beneath the existing profile router:

- `PUT /api/v1/profile/photo` (multipart field `file`) to create or replace the owner photo.
- `GET /api/v1/profile/photo` to stream the owner's photo.
- `DELETE /api/v1/profile/photo` to remove it.

The owner-facing profile/shared/auth responses expose an optional `profile_photo_url` pointing to the GET route. Specialist workspace payloads use the same URL only after an explicit relationship query; unauthorized users receive neither the URL nor bytes.

## Frontend Design

Add `profile_photo_url` to the auth/profile types and API response mapping. Implement a reusable profile-photo control on the profile summary: a circular preview, hidden file input, square crop preview dialog, upload state, validation error, replace action, and confirmed delete action. Refresh the auth/profile state after a successful mutation and add a cache-busting query value to the authenticated content URL after replacement.

Update `AuthenticatedHeader` and `MorePage` to render the photo when available and retain the current initial fallback. Keep RTL copy in Persian with English translations in the existing i18n files.

## Error Handling and Privacy

Return `401` for anonymous requests, `404` when no photo exists or a requested private object is unavailable, `403` for an unrelated specialist, `422` for invalid image input, and `503` for storage failures. Do not include filesystem paths, raw upload names, or private metadata in responses or logs.

## Verification

Backend tests cover migration/model serialization, upload validation, owner-only mutations, specialist relationship checks, replacement cleanup, deletion cleanup, private headers, and traversal protection. Frontend tests cover crop confirmation, upload/delete states, photo rendering in the profile/header/More card, and initial fallback. Run focused tests, full Backend and Frontend suites, Ruff, mypy, lint, build, and `git diff --check` before the feature commit.
