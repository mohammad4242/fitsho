# Workout Plan PDF Download Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Download the workout plan currently displayed in Fitsho as a Persian RTL PDF from the existing workout-plan action.

**Architecture:** The existing authenticated workout router resolves a plan through the ownership-scoped repository and passes its existing response schema to a focused WeasyPrint renderer. The existing frontend API client gains Blob response support, and the current PDF button downloads that Blob without adding another UI action.

**Tech Stack:** FastAPI, SQLAlchemy, WeasyPrint 69, React 19, TypeScript, Vitest, Testing Library

## Global Constraints

- Keep the existing PDF icon and button; do not redesign or duplicate it.
- Generate the PDF on the backend and return `application/pdf`.
- Render Persian text with RTL layout and an Arabic-capable font.
- Resolve every plan with the authenticated user's ID before rendering.
- Include plan title, days, Persian exercise names, sets, reps, rest, and available notes or instructions.
- Preserve all unrelated working-tree changes and stage only task files.

---

### Task 1: Persian PDF renderer and runtime dependencies

**Files:**
- Create: `backend/app/workouts/pdf.py`
- Create: `backend/tests/workouts/test_pdf.py`
- Modify: `backend/pyproject.toml`
- Modify: `backend/Dockerfile`

**Interfaces:**
- Consumes: `WorkoutPlanResponse` from `app.workouts.schemas`.
- Produces: `build_workout_plan_html(plan: WorkoutPlanResponse) -> str` and `render_workout_plan_pdf(plan: WorkoutPlanResponse) -> bytes`.

- [ ] **Step 1: Write the failing renderer tests**

```python
def test_html_contains_persian_plan_details_and_rtl_layout() -> None:
    html = build_workout_plan_html(plan_response())
    assert 'lang="fa" dir="rtl"' in html
    assert "برنامه تمرینی من" in html
    assert "پرس سینه دمبل" in html
    assert "۳ ست" in html
    assert "۸ تا ۱۲ تکرار" in html
    assert "۹۰ ثانیه استراحت" in html


def test_html_includes_available_notes_and_instructions() -> None:
    html = build_workout_plan_html(plan_response())
    assert "کنترل‌شده حرکت کن" in html
    assert "وزنه را تدریجی افزایش بده" in html
    assert "double_progression" in html
    assert "توضیح روز" in html
    assert "توضیح برنامه" in html
    assert "یادداشت مربی" in html


def test_renderer_returns_pdf_bytes() -> None:
    assert render_workout_plan_pdf(plan_response()).startswith(b"%PDF-")
```

- [ ] **Step 2: Run the renderer tests and confirm RED**

Run: `cd backend && uv run pytest tests/workouts/test_pdf.py -v`

Expected: FAIL because `app.workouts.pdf` does not exist.

- [ ] **Step 3: Add WeasyPrint and Debian text-rendering dependencies**

```toml
"weasyprint>=69,<70",
```

Add `fonts-dejavu-core`, `libpango-1.0-0`, `libpangoft2-1.0-0`, and
`libharfbuzz-subset0` to the existing `apt-get install --no-install-recommends` command.

- [ ] **Step 4: Implement escaped RTL HTML and PDF rendering**

```python
from html import escape

from weasyprint import HTML

from app.workouts.schemas import WorkoutPlanResponse


def build_workout_plan_html(plan: WorkoutPlanResponse) -> str:
    days_html = "".join(_render_day(day) for day in plan.days)
    optional_sections = _render_plan_notes(plan)
    return f'''<!doctype html>
<html lang="fa" dir="rtl"><head><meta charset="utf-8"><style>{PDF_CSS}</style></head>
<body><h1>برنامه تمرینی من</h1><p>{_fa_number(plan.plan_duration_weeks)} هفته</p>
{optional_sections}{days_html}</body></html>'''


def render_workout_plan_pdf(plan: WorkoutPlanResponse) -> bytes:
    return HTML(string=build_workout_plan_html(plan)).write_pdf()
```

Render Persian numerals for day, duration, sets, reps, and rest. Include optional day explanation,
exercise notes, load guidance, progression rule, program explanation, and coach note only when
non-empty.

- [ ] **Step 5: Run focused backend checks and confirm GREEN**

Run: `cd backend && uv run pytest tests/workouts/test_pdf.py -v && uv run ruff check app/workouts/pdf.py tests/workouts/test_pdf.py && uv run mypy app/workouts/pdf.py`

Expected: PASS.

- [ ] **Step 6: Commit and push the renderer**

```bash
git add backend/app/workouts/pdf.py backend/tests/workouts/test_pdf.py backend/pyproject.toml backend/Dockerfile
git commit -m "feat(workouts): render Persian workout plan PDFs"
git push origin main
```

### Task 2: Authenticated ownership-scoped PDF endpoint

**Files:**
- Modify: `backend/app/workouts/router.py`
- Modify: `backend/tests/workouts/test_workout_plan_api.py`

**Interfaces:**
- Consumes: `get_plan_for_user`, `to_plan_response`, and `render_workout_plan_pdf`.
- Produces: `GET /api/v1/workout-plans/{plan_id}/pdf` returning a PDF attachment.

- [ ] **Step 1: Write failing endpoint tests**

```python
def test_workout_plan_pdf_requires_authentication(client: TestClient) -> None:
    assert client.get(f"/api/v1/workout-plans/{uuid4()}/pdf").status_code == 401


def test_workout_plan_pdf_is_scoped_to_owner(client: TestClient, db: Session) -> None:
    owner_id = _register_and_complete_profile(client, "pdf-owner@example.com")
    plan = plan_with_day_and_exercise(db, owner_id)
    response = client.get(f"/api/v1/workout-plans/{plan.id}/pdf")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.headers["content-disposition"].startswith("attachment;")
    assert response.content.startswith(b"%PDF-")
    client.post("/api/v1/auth/logout", headers=ORIGIN)
    _register_and_complete_profile(client, "pdf-other@example.com")
    assert client.get(f"/api/v1/workout-plans/{plan.id}/pdf").status_code == 404
```

- [ ] **Step 2: Run endpoint tests and confirm RED**

Run: `cd backend && uv run pytest tests/workouts/test_workout_plan_api.py -k pdf -v`

Expected: FAIL with `404` because the PDF route does not exist.

- [ ] **Step 3: Implement the endpoint in the existing router**

```python
@router.get("/{plan_id}/pdf", response_class=Response)
def download_plan_pdf(plan_id: UUID, db: DatabaseSession, user: CurrentUser) -> Response:
    plan = get_plan_for_user(db, plan_id=plan_id, user_id=user.id)
    if plan is None:
        raise HTTPException(status_code=404, detail="Workout plan not found")
    content = render_workout_plan_pdf(to_plan_response(plan, db=db))
    return Response(
        content=content,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="fitsho-workout-plan-{plan.id}.pdf"'},
    )
```

- [ ] **Step 4: Run focused backend checks and confirm GREEN**

Run: `cd backend && uv run pytest tests/workouts/test_workout_plan_api.py -k 'pdf or scoped_to_its_owner' -v && uv run ruff check app/workouts/router.py tests/workouts/test_workout_plan_api.py && uv run mypy app/workouts/router.py`

Expected: PASS.

- [ ] **Step 5: Commit and push the endpoint**

```bash
git add backend/app/workouts/router.py backend/tests/workouts/test_workout_plan_api.py
git commit -m "feat(workouts): serve owned workout plan PDF downloads"
git push origin main
```

### Task 3: Blob support in the existing frontend API path

**Files:**
- Modify: `frontend/src/shared/apiClient.ts`
- Modify: `frontend/src/shared/apiClient.test.ts`
- Modify: `frontend/src/features/workouts/api.ts`
- Modify: `frontend/src/features/workouts/api.test.ts`

**Interfaces:**
- Produces: `requestBlob(path: string, init?: RequestInit) -> Promise<Blob>`.
- Produces: `downloadWorkoutPlanPdf(planId: string) -> Promise<Blob>`.

- [ ] **Step 1: Write failing Blob API tests**

```typescript
it("downloads binary responses with the authenticated API client", async () => {
  const pdf = new Blob(["%PDF-test"], { type: "application/pdf" });
  vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(pdf));
  await expect(requestBlob("/api/pdf")).resolves.toEqual(expect.any(Blob));
  expect(fetch).toHaveBeenCalledWith("/api/pdf", expect.objectContaining({ credentials: "include" }));
});


it("downloads a workout plan PDF through Fitsho", async () => {
  vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(new Blob(["pdf"])));
  await downloadWorkoutPlanPdf(plan.id);
  expect(fetch).toHaveBeenCalledWith(
    `/api/v1/workout-plans/${plan.id}/pdf`,
    expect.objectContaining({ credentials: "include" }),
  );
});
```

Also assert that `requestBlob` maps JSON HTTP failures to the existing `ApiError` shape.

- [ ] **Step 2: Run frontend API tests and confirm RED**

Run: `cd frontend && npm run test -- src/shared/apiClient.test.ts src/features/workouts/api.test.ts`

Expected: FAIL because `requestBlob` and `downloadWorkoutPlanPdf` are missing.

- [ ] **Step 3: Reuse request setup and error mapping for Blob responses**

```typescript
export async function requestBlob(path: string, init?: RequestInit): Promise<Blob> {
  const response = await fetchResponse(path, init);
  await throwApiError(response);
  return response.blob();
}
```

Keep `request<T>` behavior unchanged and share its credential, header, and error logic rather than
introducing a second raw-fetch implementation.

```typescript
export function downloadWorkoutPlanPdf(planId: string): Promise<Blob> {
  return requestBlob(`${workoutPlansPath}/${planId}/pdf`);
}
```

- [ ] **Step 4: Run focused frontend API checks and confirm GREEN**

Run: `cd frontend && npm run test -- src/shared/apiClient.test.ts src/features/workouts/api.test.ts && npm run lint -- src/shared/apiClient.ts src/features/workouts/api.ts`

Expected: PASS.

- [ ] **Step 5: Commit and push Blob API support**

```bash
git add frontend/src/shared/apiClient.ts frontend/src/shared/apiClient.test.ts frontend/src/features/workouts/api.ts frontend/src/features/workouts/api.test.ts
git commit -m "feat(workouts): fetch workout plan PDFs as blobs"
git push origin main
```

### Task 4: Existing download button loading, download, and error flow

**Files:**
- Modify: `frontend/src/features/workouts/WorkoutPlanPage.tsx`
- Modify: `frontend/src/features/workouts/WorkoutPlanPage.test.tsx`
- Modify: `frontend/src/i18n/fa.ts`
- Modify: `frontend/src/i18n/en.ts`

**Interfaces:**
- Consumes: `downloadWorkoutPlanPdf(plan.id) -> Promise<Blob>`.
- Produces: the existing PDF button's loading, automatic download, and inline error behavior.

- [ ] **Step 1: Write failing page tests**

```typescript
it("downloads the displayed workout plan from the existing PDF button", async () => {
  api.getActiveWorkoutPlan.mockResolvedValue(plan);
  api.downloadWorkoutPlanPdf.mockResolvedValue(new Blob(["pdf"], { type: "application/pdf" }));
  const createObjectURL = vi.spyOn(URL, "createObjectURL").mockReturnValue("blob:plan");
  const revokeObjectURL = vi.spyOn(URL, "revokeObjectURL").mockImplementation(() => undefined);
  const click = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => undefined);
  render(<MemoryRouter><WorkoutPlanPage planDurationWeeks={4} /></MemoryRouter>);
  await userEvent.click(await screen.findByRole("button", { name: "دانلود PDF" }));
  expect(api.downloadWorkoutPlanPdf).toHaveBeenCalledWith(plan.id);
  expect(createObjectURL).toHaveBeenCalled();
  expect(click).toHaveBeenCalled();
  expect(revokeObjectURL).toHaveBeenCalledWith("blob:plan");
});
```

Add separate tests that hold the Promise pending to assert the same button is disabled and displays
`در حال آماده‌سازی PDF…`, and reject it to assert the localized alert is shown and the button is
enabled for retry. Select a historical plan first and assert its ID is downloaded.

- [ ] **Step 2: Run the workout page tests and confirm RED**

Run: `cd frontend && npm run test -- src/features/workouts/WorkoutPlanPage.test.tsx`

Expected: FAIL because the existing PDF button remains disabled and has no handler.

- [ ] **Step 3: Implement the existing button flow**

```typescript
const [downloadingPdf, setDownloadingPdf] = useState(false);
const [pdfError, setPdfError] = useState(false);

function downloadPdf() {
  if (plan === null || downloadingPdf) return;
  setDownloadingPdf(true);
  setPdfError(false);
  void downloadWorkoutPlanPdf(plan.id)
    .then((blob) => {
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = `fitsho-workout-plan-${plan.id}.pdf`;
      anchor.click();
      URL.revokeObjectURL(url);
    })
    .catch(() => setPdfError(true))
    .finally(() => setDownloadingPdf(false));
}
```

Attach this handler to the current document-icon button, disable it when no plan exists or a download
is active, replace the `comingSoon` label with localized ready/loading copy, and show the localized
error directly below the existing quick-action group.

- [ ] **Step 4: Run focused frontend checks and confirm GREEN**

Run: `cd frontend && npm run test -- src/features/workouts/WorkoutPlanPage.test.tsx && npm run lint -- src/features/workouts/WorkoutPlanPage.tsx src/features/workouts/WorkoutPlanPage.test.tsx src/i18n/fa.ts src/i18n/en.ts && npm run build`

Expected: PASS.

- [ ] **Step 5: Commit and push the button flow**

```bash
git add frontend/src/features/workouts/WorkoutPlanPage.tsx frontend/src/features/workouts/WorkoutPlanPage.test.tsx frontend/src/i18n/fa.ts frontend/src/i18n/en.ts
git commit -m "feat(workouts): download current workout plans as PDF"
git push origin main
```

### Task 5: End-to-end verification

**Files:**
- Verify only; no planned source edits.

**Interfaces:**
- Verifies the complete backend-to-browser contract.

- [ ] **Step 1: Run backend verification**

Run: `cd backend && uv run pytest tests/workouts/test_pdf.py tests/workouts/test_workout_plan_api.py -v && uv run ruff check app/workouts/pdf.py app/workouts/router.py tests/workouts/test_pdf.py tests/workouts/test_workout_plan_api.py && uv run mypy app`

Expected: PASS.

- [ ] **Step 2: Run frontend verification**

Run: `cd frontend && npm run test -- src/shared/apiClient.test.ts src/features/workouts/api.test.ts src/features/workouts/WorkoutPlanPage.test.tsx && npm run lint && npm run build`

Expected: PASS.

- [ ] **Step 3: Build and smoke-test the backend container**

Run: `docker compose build backend && docker compose up -d db backend && curl -fsS http://localhost:8001/openapi.json >/dev/null && docker compose exec -T backend python -m weasyprint --info`

Expected: image builds, API OpenAPI responds, and WeasyPrint reports its runtime versions.

- [ ] **Step 4: Confirm repository and remote state**

Run: `git status --short --branch && git log -5 --oneline --decorate`

Expected: task commits are present on `main` and pushed; only the user's pre-existing unrelated changes remain.
