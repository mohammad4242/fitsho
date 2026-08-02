# Body Photo Analysis Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement optional private three-view body-photo analysis, review, progress comparison and deterministic plan influence without blocking normal Fitsho programs.

**Architecture:** New `body_photos`, `body_analysis`, and `workout_cycles` modules own their data and APIs. The existing workout engine receives only a versioned influence object after its safety filter. UI work stays inside a new `features/bodyPhotos` feature plus small entry-point changes.

**Tech Stack:** React 19, TypeScript, Vite, FastAPI, SQLAlchemy, Alembic, PostgreSQL, Pillow, cryptography/Fernet, MediaPipe Tasks Vision, pytest, Vitest.

## Global Constraints

- Only anonymized, head-cropped images may cross the network or persist.
- Consent is separate, versioned and optional; normal plan generation always works without it.
- Body-photo storage is private and never under the public `/media` mount.
- New state transitions are validated in domain services and are idempotent.
- Provider credentials are encrypted, masked and never logged or returned.
- Raw provider prose must not influence workout selection.
- Safety exclusions remain final and cannot be reversed by body priorities.

---

### Task 1: Private photo-session foundation

**Files:**
- Create: `backend/app/body_photos/{enums,models,schemas,storage,image_validation,service,router}.py`
- Modify: `backend/app/config.py`, `backend/app/main.py`, `backend/alembic/env.py`
- Create: `backend/alembic/versions/20260803_18_create_body_photo_sessions.py`
- Test: `backend/tests/body_photos/test_session_api.py`, `backend/tests/body_photos/test_storage.py`

**Interfaces:**
- `BodyPhotoStorage.store/delete/open` stores private generated keys.
- `BodyPhotoService.create_session/upload_processed_photo/submit/delete_session` owns state changes.
- User API provides session create/list/detail/upload/delete/submit/protected-content routes.

- [ ] Write failing tests proving consent is required only for submit, ownership protects content, one image per view is replaceable, unsupported/decompression-bomb image uploads fail, and skipped photos do not touch workout generation.
- [ ] Implement models, migration, private local storage and image decode/re-encode checks.
- [ ] Implement authenticated routes with trusted-origin mutation checks and safe DTOs.
- [ ] Run focused tests, full backend tests, Ruff and mypy; commit.

### Task 2: Client anonymization and optional wizard

**Files:**
- Create: `frontend/src/features/bodyPhotos/{types,api,processor,BodyPhotoWizard,BodyPhotoConsentModal,PhotoCaptureStep,BodyPhotoSessionPage}.tsx`
- Modify: `frontend/src/App.tsx`, `frontend/src/features/profile/ProfilePage.tsx`, `frontend/src/features/workouts/WorkoutPlanPage.tsx`, `frontend/src/i18n/{fa,en}.ts`
- Modify: `frontend/package.json`
- Test: `frontend/src/features/bodyPhotos/*.test.tsx`

**Interfaces:**
- `BodyPhotoProcessor.process(file, view)` returns `ProcessedBodyPhoto` or structured validation failures.
- The wizard uploads only `ProcessedBodyPhoto.file` after preview confirmation and operational consent.

- [ ] Write failing tests for optional skip, separate consents, repeated clothing guidance, disabled upload, replace/retake and preview confirmation.
- [ ] Implement the processor adapter, MediaPipe abstraction, canvas crop/EXIF-free encoding and object-URL cleanup.
- [ ] Implement responsive three-view wizard and profile/workout entry points.
- [ ] Run focused/full frontend tests, lint and production build; commit.

### Task 3: Generic analysis provider and admin configuration

**Files:**
- Create: `backend/app/body_analysis/{provider,openrouter,models,schemas,config_service,router}.py`, `backend/app/security/credentials.py`
- Modify: `backend/app/config.py`, `backend/app/main.py`, `backend/alembic/env.py`, `backend/app/admin/router.py`
- Create: `backend/alembic/versions/20260803_19_create_body_analysis_provider_config.py`
- Create: `frontend/src/features/admin/AdminBodyAnalysisSettingsPage.tsx`
- Modify: `frontend/src/App.tsx`, `frontend/src/features/admin/{api,types,admin.css}.ts`, `frontend/src/i18n/{fa,en}.ts`
- Test: `backend/tests/body_analysis/test_provider_config.py`, `frontend/src/features/admin/AdminBodyAnalysisSettingsPage.test.tsx`

**Interfaces:**
- `BodyAnalysisProvider.analyze_images` and `list_models` are provider-neutral.
- Encrypted credential material is only accepted in write payloads and returned as a mask.

- [ ] Write failing tests for encrypted/masked credentials, task-specific model capability filtering and safe connection checks.
- [ ] Implement OpenRouter catalog/client and task config CRUD without altering Zen workout routing.
- [ ] Implement admin settings controls and model filtering.
- [ ] Run phase gates; commit.

### Task 4: Durable analysis, results and specialist reviews

**Files:**
- Create: `backend/app/body_analysis/{jobs,normalization,review_service,review_router}.py`, `backend/app/auth/roles.py`
- Modify: `backend/app/auth/models.py`, `backend/app/main.py`, `backend/alembic/env.py`
- Create: `backend/alembic/versions/20260803_20_create_body_analysis_and_reviews.py`
- Create: `frontend/src/features/bodyPhotos/{BodyAnalysisResult,ProgressComparison,SpecialistReviewStatus}.tsx`
- Test: `backend/tests/body_analysis/test_jobs.py`, `backend/tests/body_analysis/test_reviews.py`, frontend result tests

**Interfaces:**
- Persistent runs claim/retry once and normalize provider output into versioned findings.
- Coach and doctor reviews have independent identities/statuses and preserve AI results.

- [ ] Write failing tests for idempotency, fallback, malformed output, retry, independent approvals and review version history.
- [ ] Implement background launcher plus durable run service, normalized schema, result APIs and user UI.
- [ ] Add role capability checks and review endpoints/UI states.
- [ ] Run phase gates; commit.

### Task 5: Deterministic influence, cycles and comparison

**Files:**
- Create: `backend/app/workout_cycles/{models,schemas,service,router,comparison}.py`
- Modify: `backend/app/workouts/{models,service,schemas}.py`, `backend/app/workouts/program_engine/{schemas,engine,template_selector,volume_planner,exercise_ranker,validation}.py`, `backend/app/main.py`
- Create: `backend/alembic/versions/20260803_21_add_cycles_and_analysis_influence.py`
- Modify: `frontend/src/features/workouts/WorkoutPlanPage.tsx`, body-photo result UI
- Test: workout-engine, cycle, comparison and API integration tests

**Interfaces:**
- `BodyAnalysisInfluenceService.resolve_for_user` returns confidence-gated mappings and provenance.
- `WorkoutGenerationService` includes influence version in signature, snapshot and decision trace.

- [ ] Write failing tests proving uncertainty has no effect, safety wins, provisional/reviewed provenance differs, correction changes future generation and failed analysis does not block a plan.
- [ ] Implement versioned cycles/feedback and normalized-finding comparison.
- [ ] Implement bounded deterministic template/ranking/volume influence and end-of-cycle entry flow.
- [ ] Run phase gates; commit.

### Task 6: Integration security review and delivery

**Files:**
- Modify: docs and affected test fixtures only as required
- Test: all backend/frontend suites and a manually enabled OpenRouter smoke test

- [ ] Review cross-user access, storage exposure, retention/delete behavior, request logging, CSRF, error redaction, capability filtering and migration upgrade/downgrade.
- [ ] Run full backend/frontend tests, lint, mypy, build and Alembic upgrade verification independently.
- [ ] Review final diff and write architecture/security/operator documentation; commit and push.
