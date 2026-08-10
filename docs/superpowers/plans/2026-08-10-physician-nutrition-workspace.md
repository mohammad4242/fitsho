# Physician Nutrition Workspace Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the existing physician nutrition workflow discoverable and provide pending, claimed, and approved queues while retaining every current clinical action.

**Architecture:** Extend the existing physician review query with server-owned queue views and typed response data. Keep all clinical mutations in the current nutrition services, add role-aware navigation, and reshape the existing physician page into a queue-and-case workspace without new clinical persistence.

**Tech Stack:** FastAPI, SQLAlchemy, Pydantic, PostgreSQL, React 19, TypeScript, React Router, Vitest, pytest.

## Global Constraints

- Reuse `UserSpecialistRole`, `NutritionPlanPhysicianReview`, lab security, supplement orders, and audit events.
- Never expose `internal_notes` through queue or plan responses.
- Approved cases are read-only and only visible to the physician who approved them.
- Keep coach, member nutrition, workout, and admin behavior unchanged.
- Preserve unrelated dirty work and do not stage existing profile, onboarding, i18n, Compose, media, or nutrition-question changes.
- Implement each behavior test-first and commit each verified task separately on branch `nutrition`.

---

### Task 1: Typed physician queue views

**Files:**
- Modify: `backend/app/nutrition/schemas.py`
- Modify: `backend/app/nutrition/clinical_service.py`
- Modify: `backend/app/nutrition/router.py`
- Test: `backend/tests/nutrition/test_clinical_review_api.py`

**Interfaces:**
- Consumes: existing `NutritionPlanPhysicianReview`, `NutritionWeeklyPlan`, and `UserProfile` rows.
- Produces: `GET /api/v1/nutrition/physician/reviews?view=pending|claimed|approved` returning `PhysicianReviewQueueItemResponse[]`.

- [ ] **Step 1: Write failing API tests for all three views**

Add tests that create a pending review, claim it, approve it, and assert that its membership moves
from `pending` to `claimed` to `approved`. Assert that another physician cannot see the approved row
and that each row contains `member_display_name`, `user_id`, timestamps, priority, and ownership but
does not contain `internal_notes`.

```python
pending = client.get("/api/v1/nutrition/physician/reviews?view=pending")
assert pending.status_code == 200
assert pending.json()[0]["member_display_name"] == "Clinical member"

claimed = client.get("/api/v1/nutrition/physician/reviews?view=claimed")
assert claimed.json()[0]["physician_user_id"] == str(physician.id)

approved = client.get("/api/v1/nutrition/physician/reviews?view=approved")
assert approved.json()[0]["status"] == "approved"
assert "internal_notes" not in approved.json()[0]
```

- [ ] **Step 2: Run the tests and verify RED**

Run:

```bash
cd backend
uv run pytest -q tests/nutrition/test_clinical_review_api.py -k "queue_view or approved_history"
```

Expected: failures because `view` is ignored and approved rows are excluded.

- [ ] **Step 3: Add typed queue schemas**

Add these contracts to `schemas.py`:

```python
PhysicianQueueView = Literal["pending", "claimed", "approved"]

class PhysicianReviewQueueItemResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    review_id: UUID
    plan_id: UUID
    user_id: UUID
    member_display_name: str | None
    status: str
    priority: int
    physician_user_id: UUID | None
    requested_at: datetime
    target_review_by: datetime | None
    reviewed_at: datetime | None
    overdue: bool
```

- [ ] **Step 4: Implement server-owned filtering**

Change `review_queue` to accept `view: PhysicianQueueView`. Join review → plan → profile and apply
exact filters:

```python
if view == "pending":
    status_filter = review.status.in_([PENDING, CHANGES_REQUESTED])
    owner_filter = or_(review.physician_user_id.is_(None), review.physician_user_id == physician_id)
elif view == "claimed":
    status_filter = review.status.in_([IN_REVIEW, AWAITING_LAB_INFORMATION])
    owner_filter = review.physician_user_id == physician_id
else:
    status_filter = review.status == APPROVED
    owner_filter = review.physician_user_id == physician_id
```

Declare the router query as `view: PhysicianQueueView = "pending"` and set the response model to the
new typed list. Do not include private notes.

- [ ] **Step 5: Verify backend queue behavior**

Run:

```bash
cd backend
uv run pytest -q tests/nutrition/test_clinical_review_api.py
uv run ruff check app/nutrition tests/nutrition/test_clinical_review_api.py
uv run mypy app/nutrition
```

Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add backend/app/nutrition/schemas.py backend/app/nutrition/clinical_service.py backend/app/nutrition/router.py backend/tests/nutrition/test_clinical_review_api.py
git commit -m "feat(nutrition): expose physician review queue views"
```

---

### Task 2: Physician-aware application navigation

**Files:**
- Modify: `frontend/src/shared/AuthenticatedHeader.tsx`
- Modify: `frontend/src/App.test.tsx`
- Test: `frontend/src/features/profile/ProfileRouteGuards.test.tsx`

**Interfaces:**
- Consumes: existing `verifyPhysicianAccess(): Promise<{ authorized: true }>`.
- Produces: physician navigation links to `/physician/nutrition` without changing coach access.

- [ ] **Step 1: Write failing navigation and authorization tests**

Add an App test where physician access resolves and coach access rejects. Open the account menu and
assert a `پنل پزشک` link exists. Also assert that regular members do not see it. Extend route-guard
mocks so an authorized physician can open `/physician/nutrition` without a completed member profile.

```tsx
expect(await screen.findAllByRole("link", { name: "پنل پزشک" })).not.toHaveLength(0);
expect(screen.queryByRole("link", { name: "پنل مربی" })).not.toBeInTheDocument();
```

- [ ] **Step 2: Run tests and verify RED**

Run:

```bash
cd frontend
npm run test -- --run src/App.test.tsx src/features/profile/ProfileRouteGuards.test.tsx
```

Expected: the physician link assertion fails.

- [ ] **Step 3: Add independent physician capability detection**

Import `verifyPhysicianAccess`, add an independent `isPhysician` state, and probe it in the same
authenticated effect pattern as coach access. Render bilingual links in both navigation surfaces:

```tsx
{isPhysician && (
  <Link to="/physician/nutrition">
    {i18n.resolvedLanguage === "en" ? "Physician workspace" : "پنل پزشک"}
  </Link>
)}
```

Use `Promise.resolve(verifyPhysicianAccess())` so older test mocks returning `undefined` do not crash.

- [ ] **Step 4: Verify navigation tests and lint**

Run:

```bash
cd frontend
npm run test -- --run src/App.test.tsx src/features/profile/ProfileRouteGuards.test.tsx
npm run lint
```

Expected: all pass with no hook warnings.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/shared/AuthenticatedHeader.tsx frontend/src/App.test.tsx frontend/src/features/profile/ProfileRouteGuards.test.tsx
git commit -m "feat(nutrition): add physician workspace navigation"
```

---

### Task 3: Physician queue-and-case workspace

**Files:**
- Modify: `frontend/src/features/nutrition/api.ts`
- Modify: `frontend/src/features/nutrition/PhysicianNutritionReviewPage.tsx`
- Create: `frontend/src/features/nutrition/physicianWorkspace.css`
- Modify: `frontend/src/features/nutrition/NutritionWorkflowPages.test.tsx`
- Test: `frontend/src/features/nutrition/api.test.ts`

**Interfaces:**
- Consumes: queue view API from Task 1 and all existing physician plan/lab/supplement mutations.
- Produces: `PhysicianQueueView`, `PhysicianReviewQueueItem`, and a responsive bilingual workspace.

- [ ] **Step 1: Write failing API contract tests**

Add API tests that call each view and verify exact URLs:

```typescript
await listPhysicianReviews("approved");
expect(fetch).toHaveBeenCalledWith(
  "/api/v1/nutrition/physician/reviews?view=approved",
  expect.objectContaining({ credentials: "include" }),
);
```

- [ ] **Step 2: Write failing workspace behavior tests**

Cover these behaviors in `NutritionWorkflowPages.test.tsx`:

- three bilingual queue tabs display separate results;
- pending rows offer claim and open;
- claimed rows open directly and retain food, lab, supplement, public note, private note, approve,
  request-changes, and reject controls;
- approved rows open read-only and show physician note without mutation controls;
- a queue conflict shows a useful error and refreshes the queues.

```tsx
await user.click(screen.getByRole("button", { name: "Approved" }));
await user.click(screen.getByRole("button", { name: /Open approved case/ }));
expect(screen.getByText("Read-only approved case")).toBeInTheDocument();
expect(screen.queryByRole("button", { name: "Approve this revision" })).not.toBeInTheDocument();
```

- [ ] **Step 3: Run focused tests and verify RED**

Run:

```bash
cd frontend
npm run test -- --run src/features/nutrition/api.test.ts src/features/nutrition/NutritionWorkflowPages.test.tsx
```

Expected: failures for the missing view argument, tabs, and read-only state.

- [ ] **Step 4: Add typed frontend queue API**

Add:

```typescript
export type PhysicianQueueView = "pending" | "claimed" | "approved";
export type PhysicianReviewQueueItem = {
  review_id: string;
  plan_id: string;
  user_id: string;
  member_display_name: string | null;
  status: string;
  priority: number;
  physician_user_id: string | null;
  requested_at: string;
  target_review_by: string | null;
  reviewed_at: string | null;
  overdue: boolean;
};

export function listPhysicianReviews(view: PhysicianQueueView = "pending") {
  return request<PhysicianReviewQueueItem[]>(`${nutritionPath}/physician/reviews?view=${view}`);
}
```

- [ ] **Step 5: Build the workspace state and layout**

Load all three queues, maintain `activeView`, and select a case by review row. Claim only pending
rows; open claimed/approved rows directly. Determine read-only state from `status === "approved"`.
Preserve the current clinical handlers and reload queues after every lifecycle action.

Use a restrained clinical-console visual direction based on existing Fitsho tokens: dark petrol
queue rail, paper case surface, turquoise active status, saffron waiting status, and coral overdue
status. Keep data-dense controls grouped into plan, labs, supplements, and decision sections. Add
visible keyboard focus and a single-column mobile layout.

- [ ] **Step 6: Verify focused frontend behavior**

Run:

```bash
cd frontend
npm run test -- --run src/features/nutrition/api.test.ts src/features/nutrition/NutritionWorkflowPages.test.tsx
npm run lint
npm run build
```

Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/features/nutrition/api.ts frontend/src/features/nutrition/PhysicianNutritionReviewPage.tsx frontend/src/features/nutrition/physicianWorkspace.css frontend/src/features/nutrition/NutritionWorkflowPages.test.tsx frontend/src/features/nutrition/api.test.ts
git commit -m "feat(nutrition): redesign physician review workspace"
```

---

### Task 4: Documentation, full verification, and runtime smoke

**Files:**
- Modify: `docs/nutrition-api.md`
- Test: all backend and frontend files changed above.

**Interfaces:**
- Consumes: completed physician workspace.
- Produces: operator documentation and fresh verification evidence.

- [ ] **Step 1: Document physician access and queue views**

Document `/physician/nutrition`, the `physician` role, the three queue query values, approved
read-only history, and the existing plan/lab/supplement actions. Do not document secrets.

- [ ] **Step 2: Run complete backend verification**

```bash
cd backend
uv run alembic upgrade head
uv run alembic current
uv run ruff check app tests
uv run mypy app
uv run pytest -q
```

Expected: one Alembic head and all checks pass; the opt-in live-provider test may remain skipped.

- [ ] **Step 3: Run complete frontend verification**

```bash
cd frontend
npm run lint
npm run test -- --run
npm run build
```

Expected: all checks pass.

- [ ] **Step 4: Run local runtime smoke**

Rebuild the existing backend container, verify the OpenAPI queue route, and confirm the Vite app is
available on the configured local port. Exercise the automated API scenario for pending → claimed →
approved and verify approved history remains visible only to the responsible physician.

- [ ] **Step 5: Commit and push**

```bash
git add docs/nutrition-api.md
git commit -m "docs(nutrition): document physician workspace operations"
git push origin nutrition
```
