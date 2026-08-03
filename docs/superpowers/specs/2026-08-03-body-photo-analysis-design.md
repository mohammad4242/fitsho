# Body Photo Analysis and Progress Tracking Design

## Scope and product contract

Body photos are optional. Skipping the workflow never changes profile completion or blocks plan generation. A session contains exactly front, side, and back images that have been head-cropped in the browser, confirmed by the user, then decoded and re-encoded by the server before private storage. Original images have no upload endpoint and are never persisted.

## Architecture

`body_photos` is a new modular backend domain. It owns sessions, separate immutable consent records, private image storage, analysis jobs, normalized analysis versions, reviewer decisions, progress comparisons, and authorization. It exposes authenticated user endpoints, specialist review endpoints and bounded admin controls. It stores files below a separate private root and streams them only after ownership/role authorization.

The browser owns preprocessing behind `BodyPhotoProcessor`: decode/orientation normalization, lightweight quality evaluation, safe head crop, EXIF removal, output re-encoding, preview confirmation and buffer cleanup. A MediaPipe Pose Landmarker adapter supplies landmarks when available; the wizard retains a constrained manual retry path and refuses upload whenever a safe crop cannot be established.

`body_analysis` owns a provider-neutral protocol. OpenRouter is the first adapter. Provider task configuration, encrypted credential material, catalog cache, capability filtering, primary/fallback selection and audit records remain separate from the existing Zen workout-routing records.

`workouts` receives an immutable `BodyAnalysisInfluence`, resolved from the most recent eligible normalized analysis version. Safety and exercise eligibility run first. Only high-confidence `mild_lag` and `clear_lag` mappings make bounded deterministic adjustments to template scoring, ranking and volume. The selected version and whether it was provisional, coach reviewed, doctor reviewed or fully reviewed are captured in the plan signature and decision trace.

## Assumptions forced by the current repository

- There is no workout-cycle or feedback model, so a minimal `WorkoutCycle` module is introduced. Existing plans continue to work; an initial photo session can optionally reference a plan, and completed cycles own feedback and comparison triggers.
- Users only have `is_admin`. A small role-assignment relation adds coach and doctor capability without changing member authentication or existing admin behavior.
- There is no durable queue. A persistent analysis-run record plus an idempotent service is the source of truth. FastAPI background execution is only an initial launcher; retries re-claim a durable run. A future worker can invoke the same service.
- Pillow and `cryptography` are required new backend dependencies: Pillow safely decodes/re-encodes images and removes metadata; Fernet encrypts admin-managed provider credentials from an environment-provided master key. `@mediapipe/tasks-vision` is the required frontend dependency for the client landmark adapter; it is hidden behind a local interface.

## Privacy and safety decisions

- Separate `operational_processing` and `model_training` consent records carry versioned text, grants and revocations. Training consent is opt-in, revocable, and never changes eligibility of earlier sessions.
- No raw upload body, credential, image path, provider request image data, or original image is logged.
- Server image validation enforces signature, decoded image format, MIME, size, pixels, orientation normalization, EXIF removal, generated storage keys, mandatory client crop evidence, and a conservative top-boundary image-structure check. It stores only a recompressed image.
- `client_crop_confirmed` records the browser processor and user-preview claim. `server_geometry_checked` records only server-observed dimensions, evidence binding, and boundary image structure; it is not proof that a head or person detector succeeded.
- Because the original image never reaches the backend, the server cannot independently reconstruct the anatomical crop. A malicious or modified client can forge crop coordinates and content-bound digests. This residual client-adversary limitation is accepted to preserve the stronger privacy boundary; downstream analysis must remain fail-closed and non-medical.
- Analysis is non-medical and marks all results provisional until independent coach and doctor approvals. Edited reviews create a new normalized-analysis version rather than overwriting AI output.

## Delivery phases

1. Private sessions, consents, storage, protected content APIs, user wizard shell.
2. Browser processing and safe preview.
3. Generic provider configuration, OpenRouter catalog/client and encryption.
4. Analysis runs, normalized results, result/retry UI.
5. Roles, independent specialist reviews and versioning.
6. Deterministic workout influence and provenance.
7. Workout cycles, end-of-cycle flow and progress comparisons.
8. Security review, migration verification, complete test/build gates and documentation.
