# Workout Plan PDF Download Design

## Scope

Activate the existing workout-plan PDF action. The currently displayed plan is rendered by the
backend as a Persian RTL PDF and downloaded by the browser. No new button or parallel workout-plan
data path is introduced.

## Backend

Add `GET /api/v1/workout-plans/{plan_id}/pdf` to the existing workout-plan router. The route uses
the authenticated profile dependency and `get_plan_for_user(db, plan_id, user.id)`, so an absent or
foreign plan returns the same `404` response as the existing plan-detail endpoint.

Create a focused PDF renderer in the workouts module. It renders an HTML document and converts it
with WeasyPrint. The document uses Persian labels, `dir="rtl"`, RTL CSS, and an Arabic-capable font.
The response has `Content-Type: application/pdf` and an attachment filename in
`Content-Disposition`.

The document includes:

- plan title and duration;
- every training day and its available explanation;
- Persian exercise names;
- sets, repetition range, and rest time;
- exercise notes, load guidance, and progression instructions when present;
- program-level AI explanation and coach note when present.

No database migration or stored PDF is required. Each response is generated from the requested
plan's current persisted snapshot.

## Frontend

Extend the existing workout API module with a credentialed Blob request for the PDF endpoint. The
workout page connects this call to the existing document-icon button and passes the ID of the plan
currently displayed, including a historical version selected in the existing history UI.

While downloading, the button is disabled and shows a localized loading label. On success, the
page creates a temporary object URL, triggers an anchor download, then revokes the URL. On failure,
it restores the button and shows a localized inline alert in the tools section.

## Error Handling

- Missing or foreign plans return `404` without revealing ownership.
- PDF rendering failures are not converted into a successful or partial document.
- The frontend displays a retryable error state and prevents duplicate clicks while a request is
  active.

## Tests

Backend API tests verify authentication, ownership isolation, PDF content type, attachment headers,
and a valid PDF signature. Renderer tests verify that the HTML input contains Persian plan data and
all optional instructions without depending on PDF text extraction.

Frontend tests verify that the existing button downloads the displayed plan as a Blob, exposes its
loading state, revokes the object URL, and reports request failures. Existing workout-page behavior
must remain unchanged.
