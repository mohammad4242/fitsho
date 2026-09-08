# Fitician public privacy and deletion pages

The existing web frontend exposes the two pages required for Play listing and
account deletion outside the app:

- Privacy policy: `/privacy`
- Account deletion: `/delete-account`

The production Play URLs are generated from the approved HTTPS origin in
`FITICIAN_PUBLIC_WEB_ORIGIN`. The same origin must serve the public web
frontend without authentication, use the visible Fitician name, and keep both
pages reachable while the app is distributed.

The in-app deletion flow and the public page use the existing authenticated
session and account-deletion lifecycle. The retention matrix is the authority
for member data, private media, specialist references, and repeat requests:
`docs/mobile-account-deletion-retention-matrix.md`.

Before submission, the product/legal owner must verify the published policy,
deletion instructions, support contact, and retention language against the
production configuration.
