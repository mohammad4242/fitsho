# Fitician mobile release operations

The Android and iOS releases use the same `mobile/` Expo codebase. EAS
profiles, runtime versions, channels, and release checks are shared unless a
platform-specific native capability requires a separate verification.

## Artifact matrix

| Artifact | EAS profile | Distribution | Expected file |
| --- | --- | --- | --- |
| Debug APK | `development` | protected developer/internal use | `.apk` |
| Internal-test AAB | `preview` | Play internal track | `.aab` |
| Production AAB | `production` | staged Play production rollout | `.aab` |

Run the artifact commands only from a protected EAS environment:

```bash
npm --prefix mobile run build:android:debug
npm --prefix mobile run build:android:internal
npm --prefix mobile run build:android:production
```

Each command requires `EAS_TOKEN`. The EAS project, remote signing,
`GOOGLE_SERVICES_JSON`, FCM configuration, app-link host, Google client ID,
OTA URL, and store URLs come from protected environment values. Build outputs
must be retained with the commit, profile, app version, runtime version, and
EAS build ID.

The manual GitHub workflow is
`.github/workflows/android-release.yml`. Its `production` environment must be
protected by reviewers and its EAS profile is configured to submit an internal
track draft. Production publication remains a deliberate Play Console action.

## Internal and closed testing

1. Install the `preview` AAB through Play internal testing.
2. Run `mobile/play-store/tester-instructions.md` with the complete role and
   device matrix.
3. Promote the same release candidate to closed testing after member,
   coach, physician, and authorization-boundary acceptance.
4. Retain tester results, crash/ANR review, privacy review, and the signed
   artifact digest before opening staged production rollout.

## Staged rollout and monitoring

Start with the smallest Play Console production percentage approved by the
release owner. Review crash-free launches, ANR rate, sign-in failures, upload
failures, notification delivery, and account-deletion failures at each
expansion gate. The performance acceptance target is at least 99.5%
crash-free launches over the recorded clean-launch cohort.

## Rollback

Pause the rollout when an approved threshold is exceeded. Stop production OTA
publication, keep the last known-good AAB and compatible EAS channel, and
restore the previous channel or release through Play Console. A native runtime
change requires a new signed AAB; never publish an OTA update across the
`appVersion` runtime boundary. Record the incident, owner, affected build,
rollback action, and recovery verification.

This repository has no EAS account/token or Android SDK, so it can validate the
release plan and CI configuration but cannot claim signed artifact creation or
Play installation from this workspace.

## iOS artifact matrix

| Artifact | EAS profile | Distribution | Expected file |
| --- | --- | --- | --- |
| Development IPA | `development` | registered physical iPhone | `.ipa` |
| Internal-test IPA | `preview` | protected internal QA | `.ipa` |
| Production IPA | `production` | TestFlight/App Store Connect | `.ipa` |

Run the exact iOS builds from a protected EAS environment:

```bash
npm --prefix mobile run build:ios:debug
npm --prefix mobile run build:ios:internal
npm --prefix mobile run build:ios:production
```

Each command requires `EAS_TOKEN` and remote Apple signing configured in the
matching EAS environment. Apple Team ID, App Store Connect App ID, bundle
identifier, provisioning, and distribution certificates are managed by EAS;
no Apple credential belongs in this repository. The production profile uses
the `production` channel and `appVersion` runtime boundary.

The manual GitHub workflow is `.github/workflows/ios-release.yml`. It runs on
Ubuntu because EAS performs the remote iOS build; it does not claim local
Xcode compilation. Protect the `development`, `preview`, and `production`
GitHub environments and expose only the required `EAS_TOKEN` secret.

## iOS development and internal device testing

Register the physical iPhone in the EAS project before creating a development
or internal build. Install the signed IPA using the install method supplied by
EAS/Apple for the selected profile. The development build is intended for
registered devices; the preview build is the QA candidate and should be
distributed only through the approved internal Apple testing path.

Run `mobile/app-store/tester-instructions.md` and
`mobile/ios-device-matrix.json`. Cover launch, authentication, member, coach,
physician, role-boundary, and body-analysis entry flows on the required device
tiers. Record device, iOS track, app version, profile, EAS build ID, result,
and sanitized evidence.

## TestFlight and App Store submission

1. Run `npm --prefix mobile run validate:app-store-readiness`.
2. Set the protected App Store metadata values documented in
   `mobile/app-store/README.md`, then run the production form of that validator.
3. Build `npm --prefix mobile run build:ios:production` and upload the exact
   production IPA to App Store Connect/TestFlight.
4. Complete privacy labels, age/content rating, health declarations, review
   notes, export/compliance questions, screenshots, and the review test
   account from the submitted build.
5. Submit the approved TestFlight candidate through App Store Connect. The
   EAS `submit.production.ios` configuration is intentionally credential-free.

The public privacy and deletion URLs are derived from
`FITICIAN_PUBLIC_WEB_ORIGIN`; the support URL is supplied through
`FITICIAN_SUPPORT_URL`. Both must be public HTTPS endpoints. Reviewer account
values must be supplied through protected secrets and never committed.

## iOS rollback and OTA boundaries

Pause TestFlight distribution or App Store release when an approved threshold
is exceeded. Keep the last known-good IPA and its EAS build ID, stop
production OTA publication, and revert the `production` channel only to a
compatible `appVersion` runtime. A native change to Swift, pods, permissions,
signing, or bundled models requires a new signed IPA; OTA must not cross the
runtime boundary. Record the incident, owner, affected build, rollback action,
and recovery verification.

This Linux workspace has no Xcode, CocoaPods, EAS CLI/token, Apple signing
credentials, or physical iPhone. It can verify source/config/prebuild
contracts and release tooling; it cannot claim a local signed IPA, TestFlight
upload, App Store review, or physical-device result.
