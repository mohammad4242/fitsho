# Profile Photo Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add private profile-photo upload, square-crop preview, replacement, deletion, and authorized display for members and their related coach/physician workspaces.

**Architecture:** A dedicated `user_profile_photos` row stores one active object per user. Backend owns validation, atomic private-file writes, relationship authorization, and authenticated streaming; the browser owns the square crop preview and sends the cropped result. Auth/profile and specialist response contracts expose only an authorized content URL.

**Tech Stack:** FastAPI, SQLAlchemy, Alembic, Pillow, PostgreSQL, React 19, TypeScript, Vitest, Testing Library.

**Spec:** `docs/superpowers/specs/2026-09-07-profile-photo-design.md`

## Global Constraints

- Keep profile photos outside public `media_root` and serve them only through authenticated API routes.
- Accept JPEG, PNG, and WebP up to 5 MiB; require a decodable square image and validate bytes server-side.
- Owner access is always allowed; specialist access requires the existing claimed/assigned relationship for that user.
- Preserve unrelated working-tree files and stage only feature files in each commit.
- Run the focused test cycle before every implementation commit and run full suites before the final commit.

---

### Task 1: Data model, migration, settings, and private storage

**Files:**
- Create: `backend/app/profile/photo.py`
- Modify: `backend/app/profile/models.py`
- Modify: `backend/app/auth/models.py`
- Modify: `backend/app/config.py`
- Modify: `compose.yaml`
- Modify: `.env.example`
- Create: `backend/alembic/versions/20260907_126_add_user_profile_photos.py`
- Create: `backend/tests/profile/test_profile_photo_storage.py`

**Interfaces:**
- Produces `UserProfilePhoto`, `ProfilePhotoStorage`, `NormalizedProfilePhoto`, and `ProfilePhotoValidationError` for the API task.
- Produces `User.profile_photo_url` for auth serialization.

- [ ] **Step 1: Write failing storage and validation tests**

  Add tests for a valid square JPEG, invalid MIME/signature, non-square image, over-limit upload, safe two-part keys, atomic storage, and traversal rejection. Construct `Settings` with a temporary `profile_photo_storage_root` and assert files are written outside `media_root`.

- [ ] **Step 2: Run the focused tests and verify the expected red failure**

  Run `cd backend && pytest tests/profile/test_profile_photo_storage.py -q`. Expected: import/attribute failures because the profile-photo module and settings do not exist yet.

- [ ] **Step 3: Implement the model, settings, validator, and storage**

  Add `profile_photo_storage_root=Path("var/private/profile-photos")` and `profile_photo_max_bytes=5 * 1024 * 1024` with bounds. Add the `UserProfilePhoto` table fields from the spec, a unique `user_id`, and the `User.profile_photo` relationship plus a property returning `/api/v1/profile/photo/{user_id}` with an update-version query when available. Implement Pillow validation with signature checks, EXIF orientation, square geometry, bounded pixel dimensions, and temporary-file-plus-`os.replace` storage.

- [ ] **Step 4: Add migration and runtime mounts**

  Create revision `20260907_126` after `20260907_125`, add the table and indexes/constraints, add the Backend bind mount and `PROFILE_PHOTO_STORAGE_ROOT` environment value in Compose, and add the local default to `.env.example`.

- [ ] **Step 5: Run the focused tests and migration check**

  Run `cd backend && pytest tests/profile/test_profile_photo_storage.py -q` and `DATABASE_URL=... python -m alembic upgrade head`; expected: all focused tests pass and the new revision is current.

- [ ] **Step 6: Commit the bounded task**

  `git add backend/app/profile/photo.py backend/app/profile/models.py backend/app/auth/models.py backend/app/config.py backend/alembic/versions/20260907_126_add_user_profile_photos.py backend/tests/profile/test_profile_photo_storage.py compose.yaml .env.example && git commit -m "feat(profile): add private profile photo storage" && git push origin main`

### Task 2: Owner API, relationship authorization, and response contracts

**Files:**
- Modify: `backend/app/profile/photo.py`
- Modify: `backend/app/profile/router.py`
- Modify: `backend/app/profile/schemas.py`
- Modify: `backend/app/auth/schemas.py`
- Modify: `backend/app/auth/router.py`
- Modify: `backend/app/workout_reviews/schemas.py`
- Modify: `backend/app/workout_reviews/router.py`
- Modify: `backend/app/nutrition/schemas.py`
- Modify: `backend/app/nutrition/clinical_service.py`
- Create: `backend/tests/profile/test_profile_photo_api.py`
- Modify: `backend/tests/auth/test_sessions.py`

**Interfaces:**
- Consumes `ProfilePhotoStorage` and `UserProfilePhoto` from Task 1.
- Produces `PUT /api/v1/profile/photo`, `GET /api/v1/profile/photo`, `GET /api/v1/profile/photo/{user_id}`, and `DELETE /api/v1/profile/photo`.
- Produces optional `profile_photo_url`/`member_profile_photo_url` fields in owner and specialist payloads.

- [ ] **Step 1: Write failing API and authorization tests**

  Register users and assert anonymous requests return `401`; owner upload returns metadata and streams bytes with `private, no-store`; replacement changes the stored key and removes the old file; delete returns `204` and leaves no file; invalid uploads return `422`; unrelated authenticated users and unclaimed/unassigned specialists cannot stream a target photo; a coach with a claimed workout review and a physician with an assigned nutrition review can stream it. Assert `/auth/me` and profile responses include the optional URL and specialist queue items include it only after authorization.

- [ ] **Step 2: Run the focused API tests and verify red**

  Run `cd backend && pytest tests/profile/test_profile_photo_api.py tests/auth/test_sessions.py -q`. Expected: missing routes/fields and the old exact auth response-key assertion fails.

- [ ] **Step 3: Implement the service and routes**

  Add owner CRUD routes with trusted-origin protection on mutations, map validation/storage errors to `422`/`503`, stream through the storage class, and build URLs with the row version. Add a target GET route guarded by a relationship query that checks the viewer's specialist role and claimed/assigned workout or nutrition care record. Keep admins without a relationship out of this member-photo surface.

- [ ] **Step 4: Wire profile/auth serializers**

  Add `profile_photo_url: str | None` to `UserResponse`, `ProfileResponse`, and `SharedProfileResponse`; populate profile URLs from the current row and use the User property for auth responses. Pass the viewer ID into coach/physician queue serializers, add optional member-photo URL fields, and include them only for a claimed/assigned viewer relationship.

- [ ] **Step 5: Run focused tests and static checks**

  Run `cd backend && pytest tests/profile/test_profile_photo_storage.py tests/profile/test_profile_photo_api.py tests/auth/test_sessions.py tests/workout_reviews/test_api.py tests/nutrition/test_clinical_review_api.py -q` and `ruff check app/profile app/auth app/workout_reviews app/nutrition tests/profile tests/auth`. Expected: all pass.

- [ ] **Step 6: Commit the bounded task**

  `git add backend/app/profile backend/app/auth/schemas.py backend/app/auth/router.py backend/app/workout_reviews/schemas.py backend/app/workout_reviews/router.py backend/app/nutrition/schemas.py backend/app/nutrition/clinical_service.py backend/tests/profile backend/tests/auth/test_sessions.py && git commit -m "feat(profile): authorize private photo access" && git push origin main`

### Task 3: Frontend API, crop control, and profile page

**Files:**
- Modify: `frontend/src/features/auth/types.ts`
- Modify: `frontend/src/features/profile/types.ts`
- Modify: `frontend/src/features/profile/api.ts`
- Create: `frontend/src/features/profile/ProfilePhoto.tsx`
- Create: `frontend/src/features/profile/profilePhoto.css`
- Modify: `frontend/src/features/profile/ProfilePage.tsx`
- Modify: `frontend/src/features/profile/profile.css`
- Create: `frontend/src/features/profile/ProfilePhoto.test.tsx`
- Modify: `frontend/src/features/profile/ProfilePage.test.tsx`

**Interfaces:**
- Consumes owner photo CRUD routes from Task 2.
- Produces a reusable `ProfilePhoto` component with `url`, fallback label, and owner controls, plus `uploadProfilePhoto`/`deleteProfilePhoto` API functions.

- [ ] **Step 1: Write failing component/API tests**

  Assert the API uses multipart `PUT` and `DELETE`; the profile summary renders an initial fallback without a URL; selecting a valid image opens the square preview; confirming calls upload and displays the returned URL; invalid type/size shows an alert; delete requires confirmation and then removes the image.

- [ ] **Step 2: Run the focused frontend tests and verify red**

  Run `cd frontend && npm test -- --run src/features/profile/ProfilePhoto.test.tsx src/features/profile/ProfilePage.test.tsx`. Expected: missing API functions/component and absent profile-photo controls.

- [ ] **Step 3: Implement crop and owner controls**

  Add a browser helper that loads the selected image, center-crops it to a square on a canvas, emits a JPEG `File`, and falls back safely when canvas is unavailable. Render an accessible modal preview, hidden file input, upload/delete busy states, localized errors, and confirmation. Keep the existing initial-letter fallback and expose a cache-busting URL from the response.

- [ ] **Step 4: Integrate into the profile page**

  Add the control to the account summary, initialize it from the shared/profile response, and update local state after mutations. Keep the existing wizard and nutrition-only path intact.

- [ ] **Step 5: Run focused tests and lint**

  Run `cd frontend && npm test -- --run src/features/profile/ProfilePhoto.test.tsx src/features/profile/ProfilePage.test.tsx && npm run lint`. Expected: all focused tests and lint pass.

- [ ] **Step 6: Commit the bounded task**

  `git add frontend/src/features/auth/types.ts frontend/src/features/profile && git commit -m "feat(profile): add square crop photo controls" && git push origin main`

### Task 4: Global account and specialist workspace display

**Files:**
- Modify: `frontend/src/shared/AuthenticatedHeader.tsx`
- Modify: `frontend/src/pages/MorePage.tsx`
- Modify: `frontend/src/features/workoutReviews/types.ts`
- Modify: `frontend/src/features/workoutReviews/CoachWorkoutReviewPage.tsx`
- Modify: `frontend/src/features/nutrition/api.ts`
- Modify: `frontend/src/features/nutrition/PhysicianNutritionReviewPage.tsx`
- Modify: `frontend/src/shared/authenticatedHeader.css`
- Modify: `frontend/src/pages/more.css`
- Modify: `frontend/src/features/workoutReviews/coachWorkoutReview.css`
- Modify: `frontend/src/features/nutrition/nutritionEstimate.css`
- Modify: `frontend/src/i18n/fa.ts`
- Modify: `frontend/src/i18n/en.ts`
- Modify: `frontend/src/App.test.tsx`
- Modify: `frontend/src/pages/MorePage.test.tsx`
- Modify: `frontend/src/features/workoutReviews/CoachWorkoutReviewPage.test.tsx`
- Modify: `frontend/src/features/nutrition/NutritionWorkflowPages.test.tsx`

**Interfaces:**
- Consumes `User.profile_photo_url` and specialist queue `member_profile_photo_url` from Tasks 2–3.
- Produces visible photo avatars in the global account surfaces and only related specialist case cards.

- [ ] **Step 1: Write failing display tests**

  Add assertions that the authenticated header and More card render an image URL when present and initials otherwise, and that claimed coach/physician case displays render the authorized member photo while pending unassigned cases remain initials-only.

- [ ] **Step 2: Run the focused display tests and verify red**

  Run `cd frontend && npm test -- --run src/App.test.tsx src/pages/MorePage.test.tsx src/features/workoutReviews/CoachWorkoutReviewPage.test.tsx src/features/nutrition/NutritionWorkflowPages.test.tsx`. Expected: image assertions fail because only initials are rendered.

- [ ] **Step 3: Implement shared avatar rendering and localized labels**

  Reuse the profile-photo avatar component for header, More, coach, and physician views. Add image alt/aria labels, RTL-safe styles, and Persian/English upload-related copy without changing existing navigation contracts.

- [ ] **Step 4: Run focused display tests, lint, and build**

  Run `cd frontend && npm test -- --run src/App.test.tsx src/pages/MorePage.test.tsx src/features/workoutReviews/CoachWorkoutReviewPage.test.tsx src/features/nutrition/NutritionWorkflowPages.test.tsx && npm run lint && npm run build`. Expected: all pass.

- [ ] **Step 5: Commit the bounded task**

  `git add frontend/src/shared frontend/src/pages/MorePage.tsx frontend/src/pages/more.css frontend/src/features/workoutReviews frontend/src/features/nutrition frontend/src/i18n frontend/src/App.test.tsx && git commit -m "feat(profile): show authorized photo avatars" && git push origin main`

### Task 5: Full verification and handoff

**Files:**
- Modify only if verification exposes a feature regression; otherwise no source changes.

- [ ] **Step 1: Run full Backend verification**

  Run `cd backend && pytest -q`, `ruff check`, and `mypy app`. Record exact counts and any skipped tests.

- [ ] **Step 2: Run full Frontend verification**

  Run `cd frontend && npm test -- --run`, `npm run lint`, and `npm run build`.

- [ ] **Step 3: Run repository hygiene checks**

  Run `git diff --check`, `git status --short`, inspect the final diff, and confirm no `.env`, credentials, or unrelated dirty files were staged.

- [ ] **Step 4: Perform runtime contract checks**

  Confirm `GET /openapi.json` includes the three photo routes, run an authenticated upload/read/delete smoke against the configured test/runtime app when available, and inspect Compose mount values without deleting volumes.

- [ ] **Step 5: Final commit/push if verification-only fixes were needed**

  Use a specific Conventional Commit describing the actual fix, push `origin/main`, and report the exact commands and results in Persian.
