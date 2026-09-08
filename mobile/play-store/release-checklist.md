# Fitician Play release checklist

## Repository gates

- [x] Package ID is `com.fitician.app`.
- [x] App name, scheme, channels, and release metadata use Fitician.
- [x] Target and compile API are 36; minimum API is 24.
- [x] Branded icon, adaptive foreground, and splash assets are present.
- [x] EAS development, preview, and production profiles use remote signing.
- [x] CI covers backend, frontend, shared core, mobile, OpenAPI, Android, dependency, and secret gates.
- [x] Public privacy and account-deletion routes are implemented in the web frontend.
- [x] Deletion and private-media retention behavior is covered by the existing backend lifecycle.

## Release-owner gates

- [ ] Set and verify the production EAS project, protected signing credentials,
  FCM service account, Google services file, Google Android client ID, and OTA
  URL in the matching EAS environments.
- [ ] Build and retain the debug APK, internal-test AAB, and production AAB;
  upload JavaScript, R8 mapping, and native symbols to the approved telemetry
  provider.
- [ ] Set `FITICIAN_PUBLIC_WEB_ORIGIN` and `FITICIAN_SUPPORT_EMAIL`, verify both
  public URLs over HTTPS, and publish the approved privacy policy.
- [ ] Complete the Health apps declaration, Data Safety form, content rating,
  target-audience declaration, and account-deletion review in Play Console.
- [ ] Capture and approve the Persian and English screenshot set.
- [ ] Complete internal testing and closed testing with the member, coach,
  physician, and unauthorized-member acceptance matrix.
- [ ] Approve staged rollout thresholds for crash-free launches, ANR rate,
  sign-in failures, upload failures, and notification delivery.

## Rollback

Pause the staged rollout when an agreed threshold is exceeded. Keep the last
known-good production AAB and EAS update channel available, stop production
OTA publication, and revert the production channel to the last compatible
runtime. Native runtime changes require a new signed AAB; OTA rollback must
never cross the `appVersion` runtime boundary. Record the incident, affected
version, decision owner, and recovery verification.

The unchecked items require Play Console, EAS, provider, legal, or physical
device access and cannot be truthfully marked complete by repository tests.
