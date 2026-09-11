# Fitician iOS tester instructions

Use dedicated test accounts only. Do not use real body photos, laboratory
documents, medical notes, tokens, or personal metrics in screenshots or
review evidence.

## Development and internal QA

1. Build with `npm --prefix mobile run build:ios:debug` or
   `npm --prefix mobile run build:ios:internal`.
2. Register the physical iPhone in the EAS project before the development
   build. Install the IPA through the signed distribution method exposed by
   EAS/Apple for that build.
3. Use the preview IPA for internal QA and distribute it through the approved
   Apple internal-testing path.

## Acceptance flows

Run the shared Maestro flows where the iOS runner is available:

- launch
- authentication
- member
- coach
- physician
- role-boundary
- body-analysis entry

Also verify email and phone auth, Google and Apple paths, session restore,
deep-link callback, RTL Persian layout, English mixed text, safe areas,
keyboard forms, camera permission denial/retry, front/side/back body capture,
ghost guide and privacy crop, upload retry, notification permission and tap
routing, account deletion, and logout.

Record the device tier, iOS track, app version, EAS profile, result, and
sanitized failure evidence. The required device tiers are in
`mobile/ios-device-matrix.json`.
