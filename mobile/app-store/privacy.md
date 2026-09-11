# Fitician iOS privacy and deletion links

The App Store listing uses the public HTTPS origin supplied through the
protected `FITICIAN_PUBLIC_WEB_ORIGIN` value:

- Privacy policy: `${FITICIAN_PUBLIC_WEB_ORIGIN}/privacy`
- Account deletion: `${FITICIAN_PUBLIC_WEB_ORIGIN}/delete-account`

The app's authenticated deletion flow and the public deletion page use the
existing account lifecycle. Private body photos, food photos, laboratory
documents, and related records remain private and follow the approved
retention/deletion rules. No raw body photo is sent to a cloud pose-estimation
provider by the mobile Body Vision module.

Before submission, product and legal owners must verify that the published
privacy policy describes the production providers, notification tokens,
authentication providers, media retention, and user deletion behavior.
