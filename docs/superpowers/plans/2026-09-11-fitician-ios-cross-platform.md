# Plan: Fitician production-grade iOS parity

> **For the implementing agent:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Extend the existing `mobile/` Expo/CNG application to production-ready Android+iOS parity while preserving Android behavior, shared screens, backend contracts, privacy rules, and current user work.

**Architecture:** Shared React Native UI/data/auth/session code; explicit native adapters only for iOS OS behavior. Stable native configuration lives in `app.config.ts`, config plugins, or the local Nitro module. iOS Body Vision uses a generated Nitro Swift bridge and MediaPipe Tasks Vision with the existing local models. Android FCM and iOS APNs use typed provider identities. The existing opaque mobile session path remains authoritative.

**Tech Stack:** Expo SDK 57, React Native 0.86, React 19, TypeScript/Vitest, Nitro/Nitrogen 0.37, VisionCamera 5, MediaPipe Tasks Vision, FastAPI/Pydantic/SQLAlchemy/Alembic, CocoaPods/EAS for external iOS builds.

## Working rules

- Preserve the dirty worktree. Inspect `git diff` before each phase and stage only the phase allowlist.
- Write or update a focused test before behavior code. Generated Nitrogen output and declarative metadata are verified by contract tests and regeneration checks.
- Keep all secrets and Apple/Firebase/APNs credentials in protected environment configuration.
- Run the phase gate before starting the next phase. Commit and push only the verified phase files.
- Do not edit generated `mobile/ios/` or `mobile/android/` as source. Use clean prebuild only as a verification output.
- On Linux, distinguish static/prebuild evidence from Xcode, signed IPA, physical-device, visual, and APNs delivery evidence.

## Phase 1 — iOS baseline and hardening

### Task 1.1: Add failing configuration and script tests

Files: `mobile/scripts/releaseBuildPlan.test.mjs`, `mobile/scripts/releaseConfig.test.mjs`, `mobile/scripts/foundation.test.mjs`, new `mobile/plugins/withIosHardening.test.ts`.

- Add expectations for iOS debug/internal/production commands, EAS profile fields, bundle identity, associated domains, camera purpose text, ATS host scope, fonts, and absence of global arbitrary loads.
- Keep existing Android assertions unchanged.
- Run the focused script/plugin tests and observe the expected failures.

### Task 1.2: Add the shared iOS config baseline

Files: `mobile/package.json`, `mobile/eas.json`, `mobile/app.config.ts`, new `mobile/plugins/withIosHardening.ts`.

- Add `ios` and `build:ios:{debug,internal,production}` scripts without changing Android script behavior.
- Add iOS settings to all three existing EAS profiles and `submit.production.ios` without hardcoded credentials.
- Preserve `com.fitician.app`, `Fitician`, `fitician`, associated domains, fonts, icon, splash, portrait policy, and existing Android settings.
- Set one professional Persian camera usage description covering Body Analysis and food capture; do not request microphone or unnecessary photo permission.
- Add a host-scoped ATS exception only for the configured HTTP Tailscale backend; reject arbitrary loads and do not broaden unrelated hosts.
- Enable iOS Sign in with Apple capability through stable config for the auth phase.

### Task 1.3: Run the phase gate and commit

- Run the focused tests, mobile typecheck, `npx expo config --json` for development and production-safe configuration fixtures, and `git diff --check`.
- Commit only the phase files with `feat(mobile): add iOS baseline and native hardening` and push.

## Phase 2 — Native iOS Body Vision

### Task 2.1: Add failing Nitro/module contract tests

Files: `mobile/bodyAnalysis/nativeBodyVisionNativeContract.test.ts`, `mobile/bodyAnalysis/nativeBodyVisionModels.test.ts`, new module contract test if needed.

- Assert the dual-platform HybridObject declaration, iOS autolinking language/class, iOS module name, podspec/resource declarations, Swift implementation, and both model paths.
- Assert Android mappings and model paths remain present.
- Run the focused tests and observe failure before implementation.

### Task 2.2: Change the source contract and regenerate Nitrogen

Files: `mobile/modules/fitician-body-vision/src/FiticianBodyVision.nitro.ts`, `mobile/modules/fitician-body-vision/nitro.json`, generated `mobile/modules/fitician-body-vision/nitrogen/generated/ios/**` and any regenerated shared files.

- Change only the platform contract to include `ios: "swift"`; keep public method and output semantics unchanged.
- Add the modern Nitro iOS autolinking entry and preserve Android mapping.
- Run the installed Nitrogen CLI from the module directory. Never hand-write generated bridge files.
- Inspect generated Swift/C++ bridge names and use those exact names in the implementation/podspec.

### Task 2.3: Implement the real Swift adapter and pod

Files: new `mobile/modules/fitician-body-vision/ios/FiticianBodyVision.swift`, new `mobile/modules/fitician-body-vision/FiticianBodyVision.podspec`, `mobile/modules/fitician-body-vision/package.json`.

- Conform to the generated Swift spec and accept the VisionCamera frame type used by the installed Nitro version.
- Convert the native pixel buffer/sample buffer to `MPImage`, run Pose Landmarker and Image Segmenter in the same synchronous image-mode boundary as Kotlin, and preserve orientation/mirroring semantics.
- Expose landmarks with x/y/z/visibility, a float confidence mask as `ArrayBuffer`, frame dimensions/timestamp, timings, model status, and dropped-frame accounting.
- Use CPU-accessible mask output so the JS contract receives actual bytes; fail closed to `not-packaged` if either bundle resource is absent or task initialization fails.
- Load the tracked Android model files as CocoaPods resources rather than adding duplicate binaries.
- Declare `MediaPipeTasksVision`, React/Nitro, VisionCamera, Swift source, generated Nitrogen source, and an iOS deployment target compatible with the Expo project.
- Add `ios` and the podspec to package files.

### Task 2.4: Run the phase gate and commit

- Regenerate Nitrogen, run native contract/model tests, mobile typecheck, and Android native module checks available in the workspace.
- If macOS/CocoaPods exists, run pod installation and compile the module; otherwise record the exact unavailable check.
- Commit only phase files with `feat(mobile): add native iOS body vision implementation` and push.

## Phase 3 — Camera, photo, and Body Analysis parity

### Task 3.1: Add iOS behavior tests before changes

Files: `mobile/bodyAnalysis/BodyPhotoCapture.rntl.test.tsx`, `mobile/bodyAnalysis/nativeGhostPhotoRenderer.test.ts`, `mobile/bodyAnalysis/cameraCapture.nativeContract.test.ts`, new focused iOS contract tests if needed.

- Cover permission states, camera orientation, front-camera mirroring, countdown/capture modes, dimensions, JPEG output, ghost crop geometry, retry, lifecycle unmount, and renderer argument shape for iOS.
- Verify the privacy crop remains the existing single source of truth and the ghost remains a pose guide, never a body-shape template.

### Task 3.2: Fix only evidence-backed shared/native issues

Files limited to `mobile/bodyAnalysis/BodyPhotoCapture.tsx`, `mobile/bodyAnalysis/nativeBodyVision.ts`, `mobile/bodyAnalysis/nativeGhostPhotoRenderer.ts`, `mobile/bodyAnalysis/cameraCapture.ts`, and directly required tests.

- Keep the Android renderer workaround and upload/delete/privacy behavior unchanged.
- Preserve local-only landmark/mask processing and safe `not-packaged` behavior.
- Use iOS-specific files only if the installed API or OS requires them; otherwise retain shared code.
- Do not send raw photos to a server for pose estimation and do not replace native processing with a mock.

### Task 3.3: Run the phase gate and commit

- Run focused body-analysis tests, RNTL tests with valid development runtime fixtures, and mobile typecheck.
- Record that camera/Body Vision device behavior is unverified on Linux if no iPhone/macOS is available.
- Commit only phase files with `fix(mobile): align iOS body photo processing with native parity` and push.

## Phase 4 — Authentication, deep links, RTL, safe area, and keyboard

### Task 4.1: Add failing Apple identity/backend tests

Files: `backend/tests/auth/**`, `backend/app/auth/providers.py`, `backend/app/auth/service.py`, `backend/app/auth/router.py`, `backend/app/auth/schemas.py`, `backend/app/auth/models.py` tests first.

- Add tests for Apple issuer/audience/expiry/nonce/signature validation, private relay email, durable subject reuse, conflict handling, and the existing opaque mobile session response.
- Keep Google, email, phone, password reset, refresh, logout, and session restore tests unchanged and passing.

### Task 4.2: Implement Apple authentication through the existing session path

Files: new/modified backend auth provider/service/router/schema/model/migration files; `mobile/package.json`, `mobile/auth/**`, `mobile/app/(auth)/auth/sign-in.tsx`, `mobile/app.config.ts` tests.

- Add the Expo native Apple authentication dependency and iOS-only native button at the existing auth surface; keep Android/Web behavior and disabled Apple semantics explicit where unsupported.
- Generate/verify nonce, send only the identity token and first-use profile data, and use the same mobile metadata and access/refresh issuance path as Google.
- Add a unique Apple subject field or equivalent provider identity extension without creating a second user/session system.
- Cache Apple JWKs with bounded refresh behavior, validate issuer/audience/claims, and keep provider errors safe.
- Validate `EXPO_PUBLIC_GOOGLE_IOS_CLIENT_ID` for the environments where Google is enabled, without committing the value. Preserve actionable missing-config feedback.
- Verify `fitician` callback handling, universal/associated links, RTL text, mixed Persian/English text, safe-area edges, keyboard behavior, and natural iOS navigation gestures through shared screens.

### Task 4.3: Run the phase gate and commit

- Run backend auth tests, Alembic migration tests, mobile auth/RTL/screen tests, mobile typecheck, and frontend contract tests if shared OpenAPI changes.
- Commit only phase files with `feat(auth): add iOS Apple identity and auth parity` and push.

## Phase 5 — Provider-correct notifications

### Task 5.1: Add failing provider-aware tests

Files: `mobile/notifications/*.test.ts`, `backend/tests/notifications/**`, migration test fixtures.

- Add iOS permission/token/registration tests and assert APNs is never sent as FCM.
- Add APNs request/header/payload/status classification tests, invalid-token cleanup, retry/backoff, unsupported-provider, and worker routing tests.
- Change the old unknown-provider test to reject an actually unsupported value while accepting `apns`.

### Task 5.2: Genericize the mobile notification bootstrap

Files: `mobile/notifications/notificationPermission.ts`, `notificationRegistration.ts`, `notificationApi.ts`, `mobile/app/_layout.tsx`, directly required tests.

- Add `prepareNotifications`, `getNativePushToken`, and `registerNotifications` with a typed provider/token result.
- Keep Android channel/API-level/permission behavior and compatibility exports intact.
- Implement iOS authorization handling, APNs token retrieval, token rotation listener, denial/block behavior, and existing foreground/background/tap routing.
- Make root bootstrap shared and keep the Android back provider safe no-op on iOS.

### Task 5.3: Add backend APNs provider

Files: `backend/app/notifications/schemas.py`, `models.py`, `service.py`, `worker.py`, `fcm.py`, new `backend/app/notifications/apns.py`, `backend/app/config.py`, `backend/pyproject.toml`, `backend/uv.lock`, new Alembic revision, notification tests.

- Extend provider union/check constraint to `fcm|apns` through a migration-safe revision.
- Add environment-only APNs key ID, team ID, private key, topic/bundle ID, sandbox/production endpoint, enable flag, and timeout settings.
- Implement HTTP/2 JWT APNs requests with redacted logging and provider-specific status/reason classification.
- Refactor worker delivery to select the matching configured provider, while preserving existing FCM behavior and retry/dead-letter semantics.
- Keep token hashes and stored values protected; never log raw tokens or private key material.

### Task 5.4: Run the phase gate and commit

- Run all notification backend tests, migration upgrade tests, mobile notification tests, backend Ruff/mypy, mobile typecheck, and relevant OpenAPI checks.
- Commit only phase files with `feat(notifications): add provider-correct iOS push delivery` and push.

## Phase 6 — Release, CI, device matrix, Maestro, and App Store assets

### Task 6.1: Add failing release/config tests

Files: `mobile/scripts/releaseBuildPlan.test.mjs`, `releaseArtifacts.test.mjs`, `releaseConfig.test.mjs`, `foundation.test.mjs`, `deviceMatrix.test.mjs`, new `iosDeviceMatrix.test.mjs`, new `appStoreReadiness.test.mjs`, `maestro.test.mjs`.

- Validate both platforms, all three profiles, iOS IPA artifacts, source-map entry points, remote credentials, channels, environment variables, bundle identity, runtime/update config, iOS native module, fonts, associated domains, camera permission, and no generated-tree requirement.
- Validate a maintainable iOS matrix with representative size/age/Dynamic Island/physical tiers and required flows including auth and Body Analysis entry.
- Validate truthful App Store files and explicit external configuration requirements.

### Task 6.2: Genericize scripts and validators

Files: `mobile/scripts/release-build-plan.mjs`, `releaseArtifacts.mjs`, `validate-release-config.mjs`, `validate-foundation.mjs`, `validate-device-matrix.mjs`, `validate-maestro.mjs`, new `validate-ios-device-matrix.mjs`, new `validate-app-store-readiness.mjs`, `mobile/package.json`.

- Add explicit `android|ios` platform handling and preserve the current Android function/API compatibility.
- Add iOS IPA and `index.ios.js`/`.map` source-map definitions.
- Chain iOS matrix/store checks into the existing mobile validation command without weakening Android checks.
- Keep Maestro flows shared; add subflows or minimal platform-neutral flows for auth and Body Analysis entry rather than duplicating role flows.

### Task 6.3: Add CI/docs/store source

Files: new `.github/workflows/ios-release.yml`, `docs/mobile-release.md`, new `mobile/ios-device-matrix.json`, new `mobile/app-store/{README.md,store-metadata.json,privacy.md,review-notes.md,tester-instructions.md,screenshots/README.md}`.

- Add manual protected-environment iOS release workflow using the real iOS scripts, `npm ci`, Node engine-compatible version, and `EAS_TOKEN`; hardcode no Apple values.
- Preserve Android release documentation and add iOS development/internal/preview/production/TestFlight/App Store/signing/rollback/OTA boundaries with exact commands.
- Mark missing Apple Team ID, ASC App ID, support/privacy URLs, reviewer account, screenshots, and EAS credentials as configuration requirements rather than inventing values.

### Task 6.4: Run the phase gate and commit

- Run all script/config validators and tests, mobile typecheck, and `git diff --check`.
- Commit only phase files with `feat(release): add cross-platform iOS delivery tooling` and push.

## Phase 7 — Full validation and regression

### Task 7.1: Run repository gates

Run, recording exact output:

```bash
npm ci
npm run build:core
npm run typecheck --workspace @fitician/mobile
npm run test --workspace @fitician/mobile
npm run test:native --workspace @fitician/mobile
npm run test:foundation --workspace @fitician/mobile
npm run validate --workspace @fitician/mobile
```

Also run backend notification/auth tests, backend Ruff/mypy/pytest, all mobile script tests, frontend tests/build/lint when OpenAPI or shared contracts changed, and Android prebuild/config checks.

### Task 7.2: Generate and inspect CNG outputs

From `mobile/`, run:

```bash
CI=1 npx expo prebuild --clean --no-install
```

Inspect generated iOS and Android outputs for bundle/package IDs, app name, scheme, camera purpose, URL scheme, associated domains, fonts, notification entitlement, ATS scope, Body Vision pod/autolinking, Swift sources, and model resources. Do not edit generated files.

### Task 7.3: Attempt external builds only when available

- If macOS/Xcode/CocoaPods is available, run iOS pod/build validation and `npx expo run:ios` as appropriate.
- If EAS credentials are available, run `npm --prefix mobile run build:ios:debug`; run preview and production only when their protected credentials/config are present.
- Otherwise report the external blocker exactly and do not claim signed IPA, physical iPhone, camera/Body Vision, notification delivery, or visual-parity success.

### Task 7.4: Final Android regression and handoff

- Re-run mandatory Android tests/prebuild/config checks after all iOS changes.
- Review the final diff against the user allowlist and ensure no secrets, generated native trees, unrelated WIP, or web redesign entered the commits.
- Commit any narrowly scoped final validation/docs correction with a specific Conventional Commit message and push.
- Final report must separate complete, verified, unverified, and externally blocked items, include exact iOS debug/production commands, tests passed/failed, Android regression result, and remaining credential/device blockers.

