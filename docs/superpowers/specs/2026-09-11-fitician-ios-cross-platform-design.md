# Fitician iOS cross-platform production design

Date: 2026-09-11

## Goal

Make the existing `mobile/` Expo/CNG application a production-ready shared
Android and iOS codebase. Android remains the mobile visual and behavior
reference. Shared React Native screens, state, transport, persistence, privacy
rules, and business contracts remain the source used by both platforms.

Generated `mobile/android/` and `mobile/ios/` trees remain verification outputs,
not source. Stable native behavior belongs in `app.config.ts`, config plugins,
or the local Nitro module.

## Audit findings

- The existing mobile app already centralizes screen UI and uses explicit RTL,
  LTR, safe-area, and iOS keyboard branches. No full iOS screen fork is needed.
- Android back handling is already guarded by `Platform.OS === "android"`; the
  provider can remain a compatibility-named shared wrapper with no iOS hardware
  listener.
- Google authentication already selects separate Android and iOS client IDs and
  uses the existing opaque mobile session path.
- Body Vision has a real Kotlin implementation using the pose and segmentation
  models, but the Nitro contract, generated iOS bridge, podspec, and Swift
  implementation are absent.
- Notification registration currently labels every token as FCM. Expo's native
  token API returns FCM on Android and APNs on iOS, so a provider-typed contract
  and backend APNs provider are required.
- Production mobile endpoints are HTTP on a fixed Tailscale host. iOS will use
  a host-scoped ATS exception only; global arbitrary loads are prohibited.
- Linux has Node and Expo tooling but no Xcode, `xcodebuild`, CocoaPods, EAS
  token, Apple signing credentials, or APNs credentials. Source, prebuild, and
  static validation can be verified here; signed iOS binaries and physical
  device behavior require macOS/EAS credentials.

## Decisions

### Native body vision

Use Nitro's current platform contract:

```ts
HybridObject<{ android: "kotlin"; ios: "swift" }>
```

Regenerate Nitrogen output after the spec change. Add a `FiticianBodyVision`
Swift class conforming to the generated iOS spec and use MediaPipe Tasks Vision
with the existing `pose_landmarker_lite.task` and `selfie_segmenter.tflite`.
The class keeps the Kotlin contract and metrics: landmarks, visibility, mask,
frame dimensions/timestamp, model status, processing timings, and dropped
frames. It returns `not-packaged` and a safe empty result when either bundled
model is unavailable. No cloud inference or raw-photo workaround is allowed.

The existing tracked Android model files are reused as deterministic CocoaPods
resources so the repository does not carry a second model copy. The podspec
loads Nitrogen's generated iOS extension with `add_nitrogen_files`, declares
React/Nitro/VisionCamera/MediaPipe dependencies, and exposes Swift plus model
resources.

### Authentication

Keep `User -> AuthSession` and mobile access/refresh token issuance unchanged.
Add Sign in with Apple as a second external identity provider because the app
offers Google Sign-In for primary account authentication and Apple's guideline
4.8 requires an equivalent privacy-preserving login service. Apple identities
use the same user/session service and a durable unique provider subject; they do
not create a parallel account or token system. Verify Apple identity tokens
against Apple's issuer, audience, signature/JWK, expiry, and nonce. Credentials,
private keys, and service identifiers are environment-only.

The iOS UI adds the native Apple button at the same auth surface as Google. The
existing email and phone flows remain unchanged. Apple account name/email are
used only when supplied on the first authorization, with private relay email
supported.

### Notifications

Use one shared mobile API with a typed native token:

- Android: `{ provider: "fcm", token }`
- iOS: `{ provider: "apns", token }`

Preserve the existing Android channel, permission, registration, and routing
behavior. iOS uses `expo-notifications` permission status and APNs device token
registration. A push-token listener re-registers rotated tokens. The backend
keeps FCM and adds a direct APNs HTTP/2 JWT provider with the same sent,
retryable, invalid-token, and permanent-error semantics. Token values never
enter logs. The database constraint and API schema accept only `fcm` or `apns`.

### iOS configuration and release

Add a reusable iOS hardening config plugin for camera purpose text, minimum
ATS exception for the configured Tailscale HTTP host, and required entitlements
without adding microphone or broad network permissions. Preserve branding,
fonts, scheme `fitician`, bundle ID `com.fitician.app`, associated domains,
portrait policy, and Android configuration.

Add iOS EAS settings to the existing development/preview/production profiles,
generic platform-aware release scripts while preserving the current Android
API, iOS validation/device matrix, a manual iOS GitHub workflow, truthful
App-Store/TestFlight source documentation, and release-config validators.
Apple Team ID, ASC App ID, support/privacy URLs, Google iOS client ID, EAS
token, and signing/APNs values are configuration requirements, never committed
values.

### Verification boundary

Tests will cover shared contracts, iOS branches, config plugins, Nitro metadata,
release tooling, APNs classification, migration behavior, auth verification,
and Android regression. `CI=1 npx expo prebuild --clean --no-install` will be
used for generated-tree inspection. A Linux run cannot claim Xcode compilation,
signed IPA creation, physical iPhone camera/Body Vision output, APNs delivery,
or pixel-level visual parity; those outcomes will remain explicit external
verification items until a macOS/device/EAS environment is available.

## Execution order

1. Baseline/config and shared iOS hardening.
2. Nitro regeneration, Swift Body Vision, pod/resources.
3. Camera/photo/ghost pipeline contract hardening.
4. Apple/Google/deep-link/auth and RTL/safe-area verification.
5. Generic notifications and backend APNs.
6. EAS/release/App-Store/device-matrix tooling and docs.
7. Full validation, prebuild inspection, and Android regression.

