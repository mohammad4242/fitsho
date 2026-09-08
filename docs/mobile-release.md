# Fitician Android release operations

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
