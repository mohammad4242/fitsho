# Fitician mobile E2E acceptance

The Maestro flows live under `mobile/.maestro/` and use only the Fitician
package ID. Test credentials are supplied by the runner; no account, token, or
medical data is stored in the repository.

Run them from the mobile workspace:

```bash
FITICIAN_TEST_MEMBER_EMAIL=... FITICIAN_TEST_MEMBER_PASSWORD=... \
FITICIAN_TEST_COACH_EMAIL=... FITICIAN_TEST_COACH_PASSWORD=... \
FITICIAN_TEST_PHYSICIAN_EMAIL=... FITICIAN_TEST_PHYSICIAN_PASSWORD=... \
maestro test .maestro
```

The member fixture must have a completed profile. Coach and physician fixtures
must have their respective backend specialist authorization; admin status alone
does not grant either role. The positive specialist flows use the
development-only `EXPO_PUBLIC_E2E=1` role launcher, while the role-boundary flow
uses a member fixture and must return to the member home.

The required device profiles are recorded in `mobile/device-matrix.json` for
API 24, 29, 33, and 36, plus low- and mid-range physical tiers. The current
repository environment has Android SDK/ADB tooling, but no Maestro CLI, attached
device, or configured AVD. Static flow validation is available here; device
execution is not claimed.
