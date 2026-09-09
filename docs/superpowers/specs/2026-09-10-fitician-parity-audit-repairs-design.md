# Fitician parity audit repairs

## Scope

Close the code and automated-verification defects found in the Web-to-Native parity audit without changing API contracts, query ownership, authentication, navigation, private-media behavior, or unrelated worktree changes.

Physical-device visual acceptance remains explicitly pending because this scope does not install or provision an Android emulator or device.

## Offline exercise video

Restore the existing explicit public-video download flow on the exercise detail screen. The screen will use `PublicExerciseVideoCache` with `ExpoPublicExerciseVideoStore`, check for a persisted copy whenever the selected video changes, prefer its local URI when available, and expose native download/remove actions with localized status and error copy.

Only validated public `/media/` video paths may enter the cache. Online playback remains the fallback, images are unchanged, and no private or authenticated media is persisted by this cache.

## Performance evidence

Extend the existing performance module with a payload-free report summarizer. It will calculate p95 per metric, reject missing required metrics, preserve per-sample budget results, and validate the documented clean-launch cohort fields. Automated tests will use synthetic timings only to test report logic; documentation will not present them as release evidence.

Real memory, battery, camera/video, device-tier, and crash-free measurements remain a physical release gate.

## Dependency validation

Keep SDK 57 as the compatibility boundary while allowing patch-level declarations for `expo` and `expo-router`. The lockfile must still resolve to SDK 57. No package declaration or lockfile change will be included in this repair.

## Documentation

Correct the environment statement: Android SDK and ADB are installed, while no attached device or configured AVD is available. Mark performance and visual acceptance as awaiting physical evidence.

## Tests and delivery

Use failing tests first for cache integration, performance reporting, and dependency validation. Then run focused tests, core build, mobile typecheck, all mobile Vitest/Jest suites, foundation validation, `validate:mobile`, and `git diff --check`.

Commit only the files in this repair and push `main`. Existing unrelated tracked and untracked work remains untouched.
