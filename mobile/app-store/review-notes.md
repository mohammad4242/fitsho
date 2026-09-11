# Fitician App Store review notes

Status: **prepared for review; not submitted**.

Fitician is a Persian-first fitness and nutrition companion. The submitted
build uses the existing authenticated product flows for members, coaches, and
physicians. Specialist access is authorization-bound; administrator status
alone is not a substitute for the required role.

## Reviewer access

The review account and password must be supplied in App Store Connect from
the protected values `FITICIAN_APP_REVIEW_ACCOUNT` and
`FITICIAN_APP_REVIEW_PASSWORD`. Never commit those values. The account must
be provisioned in the production review environment and be able to complete
the sign-in flow without a private employee device or an unavailable manual
approval.

## Native capabilities

- Camera access is used for food capture and the consented body-photo flow.
- Body Vision runs on-device with bundled MediaPipe models; raw body photos
  are not uploaded for pose estimation.
- Push notifications use the configured native provider for the platform.
- Google and Apple sign-in use the configured production client identifiers.

Complete the App Store privacy labels, age rating, health declaration, and
export/compliance questions from the exact production configuration. Do not
claim a capability, provider, or URL that is not enabled in that build.
