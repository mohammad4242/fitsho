# Resumable Body Analysis Sessions

## Goal

Distinguish incomplete photo uploads from sessions already submitted for analysis. Let users
resume or delete every incomplete session without losing photos that were uploaded successfully.

## Classification

The frontend derives the display category from the existing session contract:

- A session with `submitted_at === null` is an incomplete upload.
- A session with `submitted_at !== null` is an analysis session.
- Analysis states keep their existing processing, review, completion, and failure meanings.

No database migration or new API field is required.

## History Page

`BodyProgressPage` renders two independent groups:

1. Incomplete uploads show the session date, uploaded-view count, current upload status, a
   **Continue upload** action, and a **Delete** action.
2. Analysis sessions show the existing analysis history and link to the analysis result page.

An incomplete session must never receive the "latest analysis" label or a "view analysis" link.
The newest submitted session is treated as the latest analysis even when a newer incomplete
upload exists.

Deleting requires user confirmation. After a successful deletion, the card is removed locally.
If deletion fails, the card remains and shows an inline error.

## Resume Flow

The continue action opens `/body-progress/new?sessionId=<id>`. The wizard loads the owner-scoped
session, keeps every uploaded photo, and starts at the first missing view in the order front,
side, then back.

Existing server photos count toward completion. A newly uploaded photo replaces only the same
view. When all three views exist, the wizard shows the review and consent step and then uses the
existing submit and analysis-start APIs.

If all three photos already exist in an unsubmitted session, resuming opens the review step
directly. Failed analyses continue to use the existing per-view replacement and retry flow.

## Errors and Safety

- A resume-load failure shows the existing load error and does not create a replacement session.
- Upload, submission, and analysis-start errors keep their existing recovery behavior.
- Delete uses the existing owner-scoped delete endpoint and trusted-origin protection.
- Existing headless-photo validation and the no-face-processing privacy contract remain unchanged.

## Tests

Frontend tests cover:

- separating incomplete uploads from submitted analyses;
- assigning the latest-analysis marker only to a submitted session;
- linking every incomplete session to its resume URL;
- successful deletion and inline deletion failure;
- loading an existing session and starting at its first missing view;
- preserving existing views while uploading missing views;
- opening review directly when an unsubmitted session already has three photos;
- submitting the resumed session and starting analysis.

Focused frontend tests, lint, and build must pass before completion.
