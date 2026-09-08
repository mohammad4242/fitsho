# Fitician account deletion and retention matrix

Status: **technical implementation ready; product/legal approval required before production enablement**

Owner: Fitician product and legal owners

Approval record: not yet recorded. The backend keeps `ACCOUNT_DELETION_ENABLED=false` by default and
rejects production startup when deletion is enabled without `ACCOUNT_DELETION_LEGAL_APPROVAL`.

This matrix is the contract for the deletion worker. A production approval must reference this
document version and an approved retention policy. No row may be changed in production without a
new approval record and a corresponding test/migration review.

| Data or reference | Owner / scope | Effective deletion action | Retention after completion |
| --- | --- | --- | --- |
| `users` and login identifiers | Member | Delete the user row | None |
| Web sessions, mobile token families, access/refresh tokens, password-reset and verification tokens, OTP challenges, mobile auth events | Member | Revoke/delete with the user-owned auth state | None |
| Profile, body measurements, preferences, onboarding state, workout plans, workout cycles, exercise feedback and replacement records | Member | Delete through user-owned cascades | None |
| Body-photo sessions, photos, consents and body analyses | Member | Delete database rows and private media objects | None |
| Profile photo, food-photo estimates and private food media | Member | Delete database rows and private media objects | None |
| Nutrition profile, medical conditions, safety decisions, estimates, meal feedback, daily check-ins, consumption and weekly plans | Member | Delete through user-owned cascades | None |
| Lab documents, lab requests, physician reviews, supplement orders and member-visible clinical records | Member | Delete member-owned records and private lab objects | None |
| Notification devices, preferences, delivery/outbox records and pending notification state | Member | Delete through user-owned cascades | None |
| Coach/physician audit rows that reference the deleted member or actor | Member reference | Delete member-owned audit rows; set approved actor/member references to `NULL` where the audit schema requires an immutable operational record | Only the minimum approved audit metadata, without member content or private media |
| Global exercise, training-template, nutrition-catalogue, policy-version and provider-reference data | Product-owned | Do not delete; these rows are not member-owned | Product retention policy |
| `account_deletion_requests` lifecycle row | System | Keep only the minimum completion status and timestamps with `user_id=NULL` | Product/legal-approved operational retention period |

Deletion must remove private files before the associated database rows are committed. A failed file
delete leaves the request pending so the next worker attempt can retry. Repeated requests are
idempotent and never create a second pending deletion for the same member.

## Play Data Safety declaration basis

The mobile release collects account identifiers, health/fitness and nutrition/medical data,
photos/files, device identifiers for native sessions/notifications, and app diagnostics required
for operation. Data is transmitted to Fitician backend services over HTTPS. Food-photo inference
uses the configured provider only after the member's processing consent; lab documents are not
sent to an AI provider. Data is not sold. Member data is deleted according to the approved matrix.

Product/legal owners must use the current runtime and provider configuration when submitting Google
Play Data Safety answers. This document is evidence, not a substitute for that submission or legal
approval.
