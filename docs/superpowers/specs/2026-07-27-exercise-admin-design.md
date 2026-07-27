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

Public registration has no admin field. A submitted `is_admin` or other
unexpected registration field is rejected with `422`; it is never ignored and
never persisted.

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

## Admin exercise APIs

Add:

- `GET /api/v1/admin/exercises`
- `POST /api/v1/admin/exercises`

The admin list is paginated, ordered deterministically, and returns active and
inactive exercises. It supports search and active-status filtering without
changing the public catalog API. Its summaries include `is_active`,
`created_at`, and `updated_at`.

The create endpoint accepts multipart form data containing structured exercise
fields and one optional upload. No public create, update, or delete endpoint is
added. Admin edit and delete are outside this feature.

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

Duplicate slugs return `409`. Invalid structured data returns field-oriented
`422` details that the bilingual form can map back to its controls.

## Media handling

The browser never submits a storage path or stored filename. The backend:

1. Uses the existing `/exercises/exercise-placeholder.svg` and
   `MediaType.PLACEHOLDER` when no file is uploaded.
2. Rejects empty uploads, path separators in submitted filenames, unsupported
   extensions, and unsupported browser MIME types.
3. Streams an upload into a temporary file while enforcing a configurable size
   limit, defaulting to 20 MiB.
4. Requires extension, MIME allowlist, and detected signature to agree for GIF,
   MP4, or WebM.
5. Runs `ffprobe` without a shell, under a timeout, and rejects videos longer
   than the configurable 20-second default.
6. Generates a UUID-based filename and creates the final file exclusively,
   retrying on the theoretical collision instead of overwriting.
7. Moves data out of temporary storage only after all validation succeeds.
8. Stores only the generated public `/media/exercises/<filename>` path and
   derived `MediaType`.

Unsupported or mismatched media returns `415`; empty files and invalid video
metadata return `422`; oversized uploads return `413`. Temporary or finalized
files are removed if validation or database persistence fails. Executable and
arbitrary file types never reach the public media directory.

Optional source URL, license, and attribution are trimmed and stored when
provided. When a file is supplied without metadata, the existing project-owner
defaults are used:

- `Project owner supplied and authorized`
- `Provided by Fitsho project owner`

The media root, maximum bytes, maximum video duration, `ffprobe` path, and probe
timeout are configured in backend settings. FastAPI serves approved files from
`/media`; exercise media is non-sensitive and follows the existing public
catalog-media behavior. Local development uses a Git-ignored runtime directory.
Docker Compose gains a backend service with `ffprobe` installed and a named
volume mounted at the configured media root. Vite proxies `/media` to the
backend during development.

Binary data is never stored in PostgreSQL, `frontend/public`, or Git. Operations
documentation covers volume persistence, backup, restore responsibility, and
the fact that database and media backups must be coordinated.

## Persistence and catalog behavior

The service creates one `Exercise` plus normalized
`ExerciseSecondaryMuscle` and `ExerciseEquipment` rows in a single database
transaction. It does not create alternative rows.

The existing catalog already selects active rows from `exercises`. Therefore a
new active exercise appears without a second publishing step, while an inactive
exercise remains hidden. Seed execution continues to update only seed-owned
slugs. It preserves custom rows, their UUIDs, fields, normalized associations,
and uploaded media. It never converts admin-created rows into seeds or deletes
custom data. Future workout plans continue to reference `exercises.id`.

## Frontend

The authenticated user type gains `is_admin`. The shared header renders an
admin link only for administrators.

Add an `AdminRoute` inside the authenticated guard but outside completed-profile
guards. Guests are redirected to login. Authenticated non-admin users are
redirected away from the admin pages. Administrators can access both
`/admin/exercises` and `/admin/exercises/new` without a fitness profile. Backend
authorization remains authoritative.

The admin list displays existing exercises, including active status, and
provides a clear “Add exercise” action. It reuses the existing exercise media
component and catalog design language without changing public catalog pages.

The bilingual create form provides:

- English-name-based editable slug suggestion.
- Body region, filtered primary muscle, and filtered secondary-muscle controls.
- Equipment multi-select and difficulty selection.
- Three initial ordered instruction fields per language, expandable to six.
- At least one safety-note field per language.
- Active checkbox enabled by default.
- Optional GIF, MP4, or WebM upload.
- Local GIF/video preview before submission.
- Existing placeholder preview when no file is selected.
- Optional media source URL, license, and attribution.

The form uses existing translations, logical CSS properties, focus styles,
responsive conventions, and document-level RTL/LTR switching. Validation
messages and screen-reader error relationships are localized. All actions are
keyboard accessible. Submission has a loading state; because the shared Fetch
client has no upload-progress callback, the first version shows indeterminate
upload progress rather than a fabricated percentage. API failures retain form
data and expose a retry action.

After successful creation the page navigates to the admin list, highlights and
focuses the created row, and shows a success state. It links to the active
public catalog detail only when the administrator also has a completed fitness
profile.

The shared API client detects `FormData` and lets the browser set the multipart
boundary rather than forcing `application/json`. Preview object URLs are
revoked when replaced or unmounted. Video previews and catalog videos do not
autoplay with sound.

## Error handling and atomicity

The service rolls back database changes on failure. Uploaded files are cleaned
up when persistence fails. A unique filename prevents overwriting an existing
upload. Expected authorization, duplicate, validation, size, and media-format
errors use explicit HTTP responses; unexpected database failures retain the
project's existing safe `503` response.

## Verification

Backend tests cover:

- Migration defaults and user model behavior.
- Registration cannot set administrator status.
- `/auth/me` admin status.
- Guest `401`, non-admin `403`, and admin success.
- Profile-independent admin access.
- CLI promotion and missing-user behavior.
- Admin listing with active and inactive rows.
- Structured validation and normalized association rows.
- Placeholder creation, valid GIF, valid MP4, and valid WebM.
- MIME allowlist, extension/signature mismatch, empty files, size, video
  duration, path traversal, generated-name collision, and cleanup failures.
- Transaction rollback and exclusive non-overwriting storage.
- Active catalog visibility and inactive hiding.
- Seed preservation of custom fields, UUIDs, associations, and media paths.

Frontend tests cover:

- Conditional admin navigation.
- Direct-route guards for guests, non-admins, and admins without profiles.
- Admin list rendering and Add action.
- Slug suggestion and editing.
- Region-aware muscle controls.
- Ordered bilingual instruction and safety-note fields.
- Equipment and secondary-muscle multi-selects.
- GIF/video preview, placeholder preview, and object-URL cleanup.
- Multipart construction, loading, field errors, duplicate slug, retry, and
  upload failures.
- Success navigation, keyboard access, and Persian/English directionality.

The final verification runs backend tests, Ruff, formatting, MyPy, frontend
tests, lint, build, Docker Compose configuration validation, and an exact
staging review that excludes secrets, `.env`, databases, runtime uploads, and
build output.

## Documentation and delivery

Documentation covers the admin module, boolean authorization model, promotion
command, both admin APIs, every form field, media allowlists and limits,
`ffprobe`, Docker volume persistence, coordinated backups, seed/custom-data
coexistence, and future `exercises.id` references. Local-running instructions
are updated.

After every check passes, implementation and documentation are committed
together as:

```text
feat(admin): add exercise management panel
```

The branch is pushed to `feature/exercise-admin`. The workflow never
force-pushes, merges to `main`, or opens a pull request.
