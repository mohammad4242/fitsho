# Fitician Google Play Data Safety basis

Status: **prepared for product and legal review; not submitted in Play Console**

This document is the current runtime evidence for the Data Safety form. The
form must be completed from the production build, enabled providers, and
current retention approvals. Google defines collection as transmitting data
off the device, including transmission by libraries and SDKs.

## First party and service providers

The first party shown to users is **Fitician**. The mobile app communicates
with Fitician backend services over HTTPS. Push delivery uses the configured
Firebase Cloud Messaging service. Food-photo inference may use the configured
provider only after the member grants the explicit processing consent shown in
the feature. Laboratory documents are not sent to an AI provider.

## Data types to declare

| Play data type | Runtime evidence | Purpose | Handling | Deletion basis |
| --- | --- | --- | --- | --- |
| Personal info: email address, phone number, name | Account and profile fields | Account management and app functionality | User-provided; email or phone is required for the selected sign-in path | Deleted with the member account |
| Health and fitness info | Goals, training profile, measurements, workout history, nutrition profile, check-ins, and specialist workflow records | App functionality | User-provided or generated from the user’s inputs; feature-dependent | Deleted through the approved member-owned cascade |
| Photos and videos | Profile, body-progress, and food photos | App functionality | Optional; body and food photos are uploaded only in their respective consented flows | Private media is deleted with the owning record |
| Files and documents | Laboratory uploads | App functionality | Optional; sent to Fitician backend only | Private laboratory files are removed by the retention/deletion worker |
| Device or other IDs | Auth device identifier and push registration token | Account management, notifications, and app functionality | Feature-dependent; token is sent to the notification service | Revoked and deleted with mobile auth and notification state |
| App info and performance | Fixed diagnostic and crash events when the release telemetry adapter is enabled | App functionality and reliability | No route, request body, account identifier, token, photo, laboratory content, or medical text is sent | Retained only under the approved telemetry retention policy |

No advertising ID, contacts, location, messages, payment information, or
public social graph is collected by the mobile runtime. The app does not sell
user data. Data in transit is encrypted with HTTPS. The app provides an
in-app deletion request and a public deletion page outside the app.

## Deletion and privacy links

The Play Console URLs are formed from the production HTTPS value of
`FITICIAN_PUBLIC_WEB_ORIGIN`:

- Privacy policy: `${FITICIAN_PUBLIC_WEB_ORIGIN}/privacy`
- Account deletion: `${FITICIAN_PUBLIC_WEB_ORIGIN}/delete-account`

The support address is supplied through the protected
`FITICIAN_SUPPORT_EMAIL` release value. Do not submit an example host or an
unapproved address.

## Evidence used for review

- `docs/mobile-account-deletion-retention-matrix.md`
- `docs/nutrition-security-privacy.md`
- `mobile/platform/logging.ts`
- `mobile/app.config.ts`

Reference: [Google Play Data safety](https://support.google.com/googleplay/android-developer/answer/10787469).
