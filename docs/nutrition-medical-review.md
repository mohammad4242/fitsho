# Nutrition medical policy, review, labs, and supplements

## Safety classification

`medical-condition-v1` deterministically classifies input before planning:

- Standard automatic: no declared review condition.
- Automatic draft requiring review: controlled hypertension, lipid disorder, non-insulin-treated
  type 2 diabetes, stable gastrointestinal condition, physician restriction, or dangerous food-
  reaction history.
- Physician manual plan required: kidney disease, dialysis, liver disease, insulin-treated diabetes,
  pregnancy, breastfeeding, eating-disorder concern, or complex medication-food interaction.
- Unsupported/hard blocked: danger symptoms or an unsupported/other condition.

This is routing and safety policy, not diagnosis. Allergy, intolerance, and explicit exclusion rules
remain hard planning filters. Every otherwise eligible generated Nutrition plan still receives a
mandatory physician-review request.

## Review lifecycle

A safe generated revision is immediately visible as pending review but is not active, approved, or a
tracking adherence baseline. Only the assigned authorized physician can approve the exact revision.
An approved due revision activates atomically; a future revision waits for its effective date, and
activation archives any overlapping previous active baseline. User or physician plan-defining edits
create a new immutable revision and invalidate or rebind review according to the authorized workflow.
Consumption-only tracking does not mutate approval. Historical revisions and review audit events are
preserved. User-visible notes and private physician notes are stored separately; private notes are
never serialized in member plan responses.

## Laboratory records

Lab uploads are optional PDF/JPEG/PNG private records. Owners and assigned reviewing physicians can
request a short-lived signed viewer link. Administrators receive no implicit clinical access. Files
are never sent to an AI provider. Retention removes the binary while preserving minimal audit
metadata. Physician requests explicitly transition the review to awaiting laboratory information;
upload alone never silently changes a plan.

## Physician supplement orders

Only the assigned physician can create, modify, or transition an order. Each order is linked to the
exact plan, verified catalogue ingredient, dose, duration, rationale, dietary gaps and optional lab
documents. Food and supplement nutrient contributions remain separate. Applicable total-intake and
supplemental-only
upper-limit scopes are checked before activation. Every transition has a dedicated immutable audit
snapshot; internal rationale is hidden unless explicitly marked user-visible.
