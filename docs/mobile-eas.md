# Fitician EAS release configuration

`mobile/eas.json` defines three isolated profiles:

- `development`: internal debug APK with the development client and the
  `development` channel;
- `preview`: remotely signed internal-test AAB on the `preview` channel;
- `production`: remotely signed auto-incremented AAB on the `production`
  channel, submitted as an internal-track draft.

All profiles use EAS-managed versions and remote signing. The app uses the
`appVersion` runtime policy, so an OTA update cannot cross a native runtime
change. `EXPO_UPDATES_URL` and `EAS_PROJECT_ID` are supplied by the matching
EAS environment; production OTA updates require an explicit release review.

Configure these values in EAS environments or protected CI secret storage:

| Name | Type | Scope |
| --- | --- | --- |
| `EAS_PROJECT_ID` | environment value | mobile builds and updates |
| `EXPO_UPDATES_URL` | environment value | mobile builds and updates |
| `GOOGLE_SERVICES_JSON` | protected file secret | Android FCM build config |
| `EXPO_PUBLIC_GOOGLE_ANDROID_CLIENT_ID` | environment value | Google native sign-in |
| `FCM_SERVICE_ACCOUNT_JSON` | protected backend/worker secret | notification delivery |

Never commit signing files, Google service files, FCM service accounts, API
keys, or `.env` files. `GOOGLE_SERVICES_JSON` is consumed only as a protected
file path by `app.config.ts`; it is not checked into the repository.

The required commands are:

```bash
eas build --profile development --platform android
eas build --profile preview --platform android
eas build --profile production --platform android
eas update --channel development --platform android
eas update --channel preview --platform android
```

Production channel updates and production submissions remain manual release
steps after the acceptance matrix and crash/ANR review pass.
