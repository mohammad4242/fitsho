# Exercise Admin Panel Design

## Scope

Add an authenticated, admin-only page for creating exercises in the existing
catalog. An active exercise becomes visible through the current catalog
immediately. This feature does not manage alternatives or add unrelated product
features.

## Approved decisions

- Authorization: add `users.is_admin` as a non-null boolean with a database
  default of `false`.
- Media storage: use a backend-managed upload directory backed by a persistent
  Docker volume.

## Authorization

An Alembic migration adds `users.is_admin`. Registration always creates a
non-admin user. `UserResponse` and `/api/v1/auth/me` expose only the additional
`is_admin` boolean needed by the frontend.

A reusable `get_current_admin` dependency builds on the existing session
dependency:

- Missing or invalid session returns `401`.
- Authenticated non-admin user returns `403`.
- Admin user is returned to the route.

Admin API routes use this backend dependency and the existing trusted-origin
check for state-changing cookie-authenticated requests. They do not use the
completed-profile dependency.

The command below promotes an existing user and is safe to run repeatedly:

```bash
python -m app.admin.grant_admin admin@example.com
```

It normalizes the email with the existing authentication rule, fails clearly
when the account does not exist, and never creates an account.

## Exercise creation API

Add `POST /api/v1/admin/exercises`. The endpoint accepts multipart form data
containing structured exercise fields and one optional upload.

The backend validates:

- Unique lowercase kebab-case slug.
- Trimmed English and Persian names.
- Existing body-region, muscle, equipment, difficulty, and media enums.
- Primary and secondary muscles against one shared body-region taxonomy.
- No duplicate secondary muscles and no primary muscle repeated as secondary.
- At least one equipment value.
- Three to six non-empty ordered instructions in each language.
- At least one non-empty safety note in each language.
- Active status, defaulting to `true`.

An empty secondary-muscle collection remains valid because existing exercises
can have no secondary muscle. Alternative exercises are not accepted.

Duplicate slugs return `409`. Invalid structured data returns `422`.

## Media handling

The browser never submits a storage path or stored filename. The backend:

1. Uses the existing `/exercises/exercise-placeholder.svg` and
   `MediaType.PLACEHOLDER` when no file is uploaded.
2. Streams an upload into a temporary file while enforcing a configurable size
   limit, defaulting to 25 MiB.
3. Detects GIF, MP4, or WebM from file signatures instead of trusting the
   browser filename or content type.
4. Generates a UUID-based filename with the detected extension.
5. Moves the completed file into the configured exercise upload directory.
6. Stores only the generated public `/media/exercises/<filename>` path and
   derived `MediaType`.

Unsupported media returns `415`; an oversized upload returns `413`. Temporary
or finalized files are removed if validation or database persistence fails.

Optional source URL, license, and attribution are trimmed and stored when
provided. When a file is supplied without metadata, the existing project-owner
defaults are used:

- `Project owner supplied and authorized`
- `Provided by Fitsho project owner`

The media root is configured in backend settings. FastAPI serves it from
`/media`; exercise media is non-sensitive and follows the existing public
catalog-media behavior. Local development uses a Git-ignored runtime directory.
Docker Compose gains a backend service and a named volume mounted at the
configured media root. Vite proxies `/media` to the backend during development.

## Persistence and catalog behavior

The service creates one `Exercise` plus normalized
`ExerciseSecondaryMuscle` and `ExerciseEquipment` rows in a single database
transaction. It does not create alternative rows.

The existing catalog already selects active rows from `exercises`. Therefore a
new active exercise appears without a second publishing step, while an inactive
exercise remains hidden. Seed execution continues to update only known seed
slugs and does not delete or rewrite admin-created exercises. Future workout
plans continue to reference `exercises.id`.

## Frontend

The authenticated user type gains `is_admin`. The shared header renders an
admin link only for administrators.

Add an `AdminRoute` inside the authenticated guard but outside completed-profile
guards. Guests are redirected to login. Authenticated non-admin users are
redirected away from the admin page. Administrators can access the page without
a fitness profile. Backend authorization remains authoritative.

The bilingual create form provides:

- English-name-based editable slug suggestion.
- Body region, filtered primary muscle, and filtered secondary-muscle controls.
- Equipment multi-select and difficulty selection.
- Three initial ordered instruction fields per language, expandable to six.
- At least one safety-note field per language.
- Active checkbox enabled by default.
- Optional GIF, MP4, or WebM upload.
- Optional media source URL, license, and attribution.

The form uses existing translations, logical CSS properties, focus styles,
responsive conventions, and document-level RTL/LTR switching. Validation
messages are localized. After successful creation it shows confirmation. It
links to the active catalog detail only when the administrator also has a
completed fitness profile.

The shared API client detects `FormData` and lets the browser set the multipart
boundary rather than forcing `application/json`.

## Error handling and atomicity

The service rolls back database changes on failure. Uploaded files are cleaned
up when persistence fails. A unique filename prevents overwriting an existing
upload. Expected authorization, duplicate, validation, size, and media-format
errors use explicit HTTP responses; unexpected database failures retain the
project's existing safe `503` response.

## Verification

Backend tests cover:

- Migration defaults and user model behavior.
- `/auth/me` admin status.
- Guest `401`, non-admin `403`, and admin success.
- Profile-independent admin access.
- CLI promotion and missing-user behavior.
- Structured validation and normalized association rows.
- Placeholder creation and each supported upload format.
- Signature, size, path, duplicate-slug, and cleanup failures.
- Active catalog visibility, inactive hiding, and seed preservation.

Frontend tests cover:

- Conditional admin navigation.
- Direct-route guards for guests, non-admins, and admins without profiles.
- Slug suggestion and editing.
- Region-aware muscle controls.
- Ordered bilingual fields and validation.
- Multipart request construction and upload errors.
- Success behavior and Persian/English directionality.

The final verification runs backend tests, Ruff, formatting, MyPy, frontend
tests, lint, build, and Docker Compose configuration validation.
