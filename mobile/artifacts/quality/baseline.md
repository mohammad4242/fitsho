# Fitician Android Quality Baseline

- Recorded: 2026-09-09 (Asia/Tehran)
- Branch: `main`
- Commit: `8d59a0f86f0e`
- Build identity: `com.fitician.app`
- Device evidence: unavailable; `adb devices -l` returned no connected device.
- Screenshot evidence: unavailable for this checkout and commit.
- APK evidence: local APK files exist, but none was built from commit `8d59a0f86f0e`; they are not accepted as current runtime evidence.

## Static verification

| Check | Result |
|---|---|
| `npm run build:core` | Passed |
| `npm run typecheck:mobile` | Passed |
| `npm run test --workspace @fitician/mobile` | Passed: 128 files, 396 tests |
| `npm run test:native --workspace @fitician/mobile` | Passed: 9 suites, 17 tests |
| `npm run test:mobile:foundation` | Passed: 31 tests |
| Mobile Oxlint | Passed |
| `git diff --check` | Passed |
| `npm run validate:mobile` | Failed: declared Expo `~57.0.21` differs from validator expectation `~57.0.0` |
| `npm run audit:dependencies --workspace @fitician/mobile` | Failed: one high-severity production advisory in the Expo CLI dependency chain |

The package and lockfile drift predates this quality audit and remains unmodified.

## Route and flow inventory

- Public: landing, login, register, forgot/reset password, Google callback.
- Onboarding: account hydration and profile completion.
- Member: home, workouts, nutrition, profile, exercise catalogue/detail, nutrition plan, food catalogue, meal catalogue.
- Body Analysis: history, capture, review, confirmation, progress.
- Specialist: coach and physician destinations.
- Account: deletion flow.

## Evidence limits

- Automated tests confirm contracts and source behavior, not visual parity.
- No physical-device interaction, RTL rendering, camera flow, gesture, keyboard, accessibility-service, or performance evidence is available.
- Final acceptance remains blocked until a current development APK is installed and the required routes are exercised on an Android phone.
