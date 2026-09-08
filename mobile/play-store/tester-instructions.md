# Fitician internal and closed-test instructions

## Test account policy

Use only dedicated test accounts provisioned in the target backend. Supply
credentials through Play Console tester management or protected CI/EAS
secrets. Never put credentials, tokens, body photos, laboratory documents, or
medical notes in this repository.

Required fixtures:

- a member with a completed profile;
- a coach with explicit coach authorization;
- a physician with explicit physician authorization;
- a member without specialist authorization for boundary checks.

Administrator status alone must not grant coach or physician access. Admin
operations remain web-only.

## Acceptance pass

1. Install the signed internal-test AAB through Google Play.
2. Sign in with email and mobile paths, then exercise session expiry and
   re-authentication.
3. Verify member workout, exercise video, nutrition, body-progress, offline,
   notification, deep-link, and account-deletion flows.
4. Verify coach review and physician review with their authorized fixtures.
5. Verify the unauthorized member cannot enter either specialist workspace.
6. Check RTL Persian layout, English LTR layout, font scaling, TalkBack,
   contrast, back navigation, and process restoration.
7. Record API level, device model, app version, build profile, result, and
   sanitized failure evidence in the release report.

The required API and device matrix is in `mobile/device-matrix.json`. The
Maestro flows are in `mobile/.maestro/`.
