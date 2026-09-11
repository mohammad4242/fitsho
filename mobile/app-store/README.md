# Fitician iOS App Store source

This directory contains the iOS listing source and review handoff. It does
not contain Apple credentials, live URLs, reviewer passwords, or screenshots
from real users.

## Required protected release values

Set these in the protected EAS/App Store Connect release environment before a
production submission:

- `APPLE_TEAM_ID`
- `APPLE_APP_STORE_CONNECT_APP_ID`
- `FITICIAN_PUBLIC_WEB_ORIGIN`
- `FITICIAN_SUPPORT_URL`
- `FITICIAN_SUPPORT_EMAIL`
- `FITICIAN_APP_REVIEW_ACCOUNT`
- `FITICIAN_APP_REVIEW_PASSWORD`
- `EXPO_PUBLIC_GOOGLE_IOS_CLIENT_ID`

`EXPO_PUBLIC_GOOGLE_IOS_CLIENT_ID` must be a real Google OAuth client ID in
the EAS `preview` and `production` environments. It is intentionally empty in
the repository examples and must not be committed as a credential.

`FITICIAN_PUBLIC_WEB_ORIGIN` must serve `/privacy` and `/delete-account` over
HTTPS. `FITICIAN_SUPPORT_URL` must be a public HTTPS support page. The
repository intentionally stores only the variable names.

## Release path

Build the signed artifacts with the shared mobile codebase:

```bash
npm --prefix mobile run build:ios:debug
npm --prefix mobile run build:ios:internal
npm --prefix mobile run build:ios:production
```

Use the development IPA on registered devices, the preview IPA for internal
QA, and the production IPA for TestFlight/App Store Connect. Run the App Store
validator before submission:

```bash
npm --prefix mobile run validate:app-store-readiness
APPLE_TEAM_ID=... APPLE_APP_STORE_CONNECT_APP_ID=... \
FITICIAN_PUBLIC_WEB_ORIGIN=https://... FITICIAN_SUPPORT_URL=https://... \
FITICIAN_SUPPORT_EMAIL=... FITICIAN_APP_REVIEW_ACCOUNT=... \
FITICIAN_APP_REVIEW_PASSWORD=... \
npm --prefix mobile run validate:app-store-readiness -- --production
```

The final metadata, age rating, privacy answers, screenshots, and review
notes must be reviewed against the exact submitted build in App Store
Connect. A repository validation pass is not an Apple review approval.
