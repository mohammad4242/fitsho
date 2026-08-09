# Coach Workout Review Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a coach review queue that preserves the generated workout plan as an active immutable version, lets one coach safely edit a draft, and activates a separately approved plan while keeping both versions visible to the member.

**Architecture:** Add a focused `app.workout_reviews` module for persistence, lease/concurrency rules, validation, approval, and coach APIs. Existing workout tables remain the immutable version store; an approved review clones the source into a new `WorkoutPlan` linked by `previous_program_id`. Workout generation creates one idempotent pending review, while member endpoints expose review state and version history without depending on coach-specific provider details.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2, PostgreSQL, Alembic, Pydantic 2, pytest, React 19, TypeScript, React Router 7, i18next, Vitest.

## Global Constraints

- The generated version remains active and usable while coach review is pending.
- Source and approved workout-plan versions are immutable after activation.
- Coaches may edit only exercise selection, sets, repetition range, rest duration, and exercise notes.
- A coach must hold a renewable 30-minute lease before saving or approving a draft.
- Only the `coach` specialist role may access coach review APIs and pages.
- Final approval must validate the full draft and atomically activate the approved version.
- Nutrition physician review behavior and external push/SMS notifications remain unchanged.
- New UI copy must support Persian RTL and English LTR.
- Preserve unrelated dirty work in the repository.

---

## File Structure

### Backend

- Create `backend/app/workout_reviews/__init__.py` — module boundary.
- Create `backend/app/workout_reviews/enums.py` — review status and stable error codes.
- Create `backend/app/workout_reviews/models.py` — persisted review, lease, draft, and approval link.
- Create `backend/app/workout_reviews/schemas.py` — typed draft, queue, detail, and member metadata contracts.
- Create `backend/app/workout_reviews/repository.py` — eager-loading queries and plan cloning/activation primitives.
- Create `backend/app/workout_reviews/validation.py` — draft-to-validator adapter and catalogue eligibility checks.
- Create `backend/app/workout_reviews/service.py` — idempotent creation, claim, renewal, save, and approval transaction.
- Create `backend/app/workout_reviews/dependencies.py` — `coach` role authorization and service dependency.
- Create `backend/app/workout_reviews/router.py` — coach review HTTP endpoints.
- Create `backend/alembic/versions/20260809_58_add_coach_workout_reviews.py` — schema migration.
- Modify `backend/app/workouts/models.py` — review relationships only; no mutable review fields on plans.
- Modify `backend/app/workouts/repository.py` — member history and reviewed-plan activation query.
- Modify `backend/app/workouts/schemas.py` — nested member review/version metadata.
- Modify `backend/app/workouts/router.py` — member history endpoint and review-aware responses.
- Modify `backend/app/workouts/service.py` — create pending review after successful new-plan activation.
- Modify `backend/app/main.py` — include coach review router.

### Frontend

- Create `frontend/src/features/workoutReviews/types.ts` — coach queue/detail/draft contracts.
- Create `frontend/src/features/workoutReviews/api.ts` — access, queue, claim, renew, save, and approve calls.
- Create `frontend/src/features/workoutReviews/CoachWorkoutReviewPage.tsx` — queue and editor workspace.
- Create `frontend/src/features/workoutReviews/coachWorkoutReview.css` — responsive RTL/LTR workspace styling.
- Modify `frontend/src/features/profile/ProfileRouteGuards.tsx` — `CoachRoute` API-probed guard.
- Modify `frontend/src/App.tsx` — protected `/coach/workouts` route.
- Modify `frontend/src/shared/AuthenticatedHeader.tsx` — coach workspace link after successful access discovery.
- Modify `frontend/src/features/workouts/types.ts` — member review and version-summary types.
- Modify `frontend/src/features/workouts/api.ts` — history and historical plan reads.
- Modify `frontend/src/features/workouts/WorkoutPlanPage.tsx` — status badges and read-only version switcher.
- Modify `frontend/src/features/workouts/workoutPlan.css` — review and version-history presentation.
- Modify `frontend/src/i18n/fa.ts` and `frontend/src/i18n/en.ts` — complete bilingual copy.

---

### Task 1: Persist Coach Review State

**Files:**
- Create: `backend/app/workout_reviews/__init__.py`
- Create: `backend/app/workout_reviews/enums.py`
- Create: `backend/app/workout_reviews/models.py`
- Create: `backend/alembic/versions/20260809_58_add_coach_workout_reviews.py`
- Modify: `backend/app/workouts/models.py`
- Test: `backend/tests/database/test_workout_review_models.py`

**Interfaces:**
- Consumes: `WorkoutPlan`, `User`, and existing `SpecialistRole.COACH`.
- Produces: `WorkoutReviewStatus`, `WorkoutReviewErrorCode`, and `WorkoutPlanReview`.

- [ ] **Step 1: Write failing model and migration tests**

```python
def test_workout_review_defaults_to_pending_with_version_one(db, active_plan):
    review = WorkoutPlanReview(source_plan_id=active_plan.id, user_id=active_plan.user_id)
    db.add(review)
    db.flush()
    assert review.status is WorkoutReviewStatus.PENDING
    assert review.draft_revision == 1
    assert review.claimed_by_user_id is None


def test_only_one_review_can_exist_for_a_source_plan(db, active_plan):
    db.add_all([
        WorkoutPlanReview(source_plan_id=active_plan.id, user_id=active_plan.user_id),
        WorkoutPlanReview(source_plan_id=active_plan.id, user_id=active_plan.user_id),
    ])
    with pytest.raises(IntegrityError):
        db.flush()
```

- [ ] **Step 2: Run the focused tests and verify failure**

Run: `cd backend && pytest tests/database/test_workout_review_models.py -q`

Expected: FAIL because `app.workout_reviews.models` does not exist.

- [ ] **Step 3: Add enums and the persisted review model**

```python
class WorkoutReviewStatus(StrEnum):
    PENDING = "pending"
    CLAIMED = "claimed"
    APPROVED = "approved"
    SUPERSEDED = "superseded"


class WorkoutReviewErrorCode(StrEnum):
    COACH_ROLE_REQUIRED = "COACH_ROLE_REQUIRED"
    REVIEW_NOT_FOUND = "REVIEW_NOT_FOUND"
    REVIEW_ALREADY_CLAIMED = "REVIEW_ALREADY_CLAIMED"
    REVIEW_LEASE_EXPIRED = "REVIEW_LEASE_EXPIRED"
    STALE_DRAFT_REVISION = "STALE_DRAFT_REVISION"
    INVALID_DRAFT = "INVALID_DRAFT"
    EXERCISE_NOT_ALLOWED = "EXERCISE_NOT_ALLOWED"
    REVIEW_ALREADY_APPROVED = "REVIEW_ALREADY_APPROVED"
    REVIEW_SUPERSEDED = "REVIEW_SUPERSEDED"


class WorkoutPlanReview(Base):
    __tablename__ = "workout_plan_reviews"

    id: Mapped[UUID]
    source_plan_id: Mapped[UUID]
    user_id: Mapped[UUID]
    status: Mapped[WorkoutReviewStatus]
    claimed_by_user_id: Mapped[UUID | None]
    lease_acquired_at: Mapped[datetime | None]
    lease_expires_at: Mapped[datetime | None]
    coach_note: Mapped[str | None]
    draft_payload: Mapped[dict[str, object] | None]
    draft_revision: Mapped[int]
    approved_plan_id: Mapped[UUID | None]
    approved_at: Mapped[datetime | None]
    created_at: Mapped[datetime]
    updated_at: Mapped[datetime]
```

Implement unique constraints on `source_plan_id` and non-null `approved_plan_id`, indexes on
`status`, `claimed_by_user_id`, and `user_id`, a positive draft-revision check, 2,000-character
coach-note limit, and foreign keys with `CASCADE` only for the owning member/source review data.
Coach and approved-plan references use `RESTRICT`/`SET NULL` so audit history is not silently lost.

- [ ] **Step 4: Add migration 58 and model registration relationships**

Set `revision = "20260809_58"` and `down_revision = "20260809_57"`. Create the table and partial
indexes without backfilling legacy workout plans. Add source/approved review relationships to
`WorkoutPlan` using explicit `foreign_keys` to avoid an ambiguous join.

- [ ] **Step 5: Run migration and model tests**

Run: `cd backend && alembic upgrade head && pytest tests/database/test_workout_review_models.py -q`

Expected: PASS and Alembic current revision `20260809_58`.

- [ ] **Step 6: Commit the persistence slice**

```bash
git add backend/app/workout_reviews backend/app/workouts/models.py backend/alembic/versions/20260809_58_add_coach_workout_reviews.py backend/tests/database/test_workout_review_models.py
git commit -m "feat(workouts): persist coach review drafts and leases"
```

---

### Task 2: Implement Lease, Draft Validation, and Approval

**Files:**
- Create: `backend/app/workout_reviews/schemas.py`
- Create: `backend/app/workout_reviews/repository.py`
- Create: `backend/app/workout_reviews/validation.py`
- Create: `backend/app/workout_reviews/service.py`
- Modify: `backend/app/workouts/repository.py`
- Test: `backend/tests/workout_reviews/test_service.py`
- Test: `backend/tests/workout_reviews/test_validation.py`

**Interfaces:**
- Consumes: `WorkoutPlanReview`, `WorkoutPlanModelOutput`, `WorkoutPlanValidator`, persisted exercise-catalogue snapshots, and `WorkoutGenerationPolicy`.
- Produces: `ensure_pending_review(db, plan)`, `WorkoutReviewService.claim`, `renew`, `save_draft`, and `approve`.

- [ ] **Step 1: Write failing lease and idempotency tests**

```python
def test_ensure_pending_review_is_idempotent(db, active_plan):
    first = ensure_pending_review(db, active_plan)
    second = ensure_pending_review(db, active_plan)
    assert first.id == second.id


def test_claim_rejects_second_coach_until_lease_expires(service, review, coaches, clock):
    service.claim(review.id, coaches.first.id)
    with pytest.raises(ReviewConflict) as error:
        service.claim(review.id, coaches.second.id)
    assert error.value.code == "REVIEW_ALREADY_CLAIMED"
    clock.advance(minutes=31)
    claimed = service.claim(review.id, coaches.second.id)
    assert claimed.claimed_by_user_id == coaches.second.id
```

- [ ] **Step 2: Run lease tests and verify failure**

Run: `cd backend && pytest tests/workout_reviews/test_service.py -q`

Expected: FAIL because the service and repository are missing.

- [ ] **Step 3: Implement row-locked claim and renewal**

```python
LEASE_DURATION = timedelta(minutes=30)

def claim(self, review_id: UUID, coach_id: UUID) -> WorkoutPlanReview:
    review = self._repository.get_for_update(review_id)
    now = self._clock()
    if review.status is WorkoutReviewStatus.APPROVED:
        raise ReviewConflict(WorkoutReviewErrorCode.REVIEW_ALREADY_APPROVED)
    if review.lease_expires_at and review.lease_expires_at > now:
        if review.claimed_by_user_id != coach_id:
            raise ReviewConflict(WorkoutReviewErrorCode.REVIEW_ALREADY_CLAIMED)
    review.status = WorkoutReviewStatus.CLAIMED
    review.claimed_by_user_id = coach_id
    review.lease_acquired_at = now
    review.lease_expires_at = now + LEASE_DURATION
    self._db.commit()
    return review
```

`renew` requires the same coach and a still-valid lease. Every successful draft save renews the
lease. The service accepts an injectable UTC clock for deterministic tests.

- [ ] **Step 4: Write failing draft validation tests**

```python
def test_validator_rejects_exercise_outside_source_candidate_snapshot(validator, draft):
    draft.days[0].exercises[0].exercise_id = uuid4()
    with pytest.raises(DraftValidationError) as error:
        validator.validate(draft)
    assert "EXERCISE_NOT_ALLOWED" in error.value.codes


def test_validator_rejects_inactive_or_nonprogrammable_exercise(validator, draft, exercise):
    exercise.is_programmable = False
    with pytest.raises(DraftValidationError):
        validator.validate(draft)
```

- [ ] **Step 5: Implement typed draft contracts and validator adapter**

```python
class WorkoutReviewExerciseDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")
    exercise_id: UUID
    sets: int = Field(ge=1, le=10)
    reps_min: int = Field(ge=1, le=100)
    reps_max: int = Field(ge=1, le=100)
    rest_seconds: int = Field(ge=0, le=600)
    notes_en: str | None = Field(default=None, max_length=1000)
    notes_fa: str | None = Field(default=None, max_length=1000)


class WorkoutReviewDraftUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_revision: int = Field(ge=1)
    coach_note: str | None = Field(default=None, max_length=2000)
    days: list[WorkoutReviewDayDraft] = Field(min_length=1, max_length=6)
```

Convert the draft to `WorkoutPlanModelOutput`, preserving source day titles, RIR, and non-editable
metadata. Reconstruct allowed candidates from `source_plan.exercise_catalog_snapshot`, then require
every selected database exercise to be active, programmable, not `needs_review`, and present in that
snapshot. Run `WorkoutPlanValidator` with the source session duration and day count. Return stable
field-level error codes; never mutate the review or plan on validation failure.

- [ ] **Step 6: Write failing immutable approval tests**

```python
def test_approval_creates_new_active_version_and_preserves_source(service, review, coach, db):
    original_payload = serialize_plan(review.source_plan)
    approved = service.approve(review.id, coach.id, expected_revision=review.draft_revision)
    db.refresh(review.source_plan)
    assert serialize_plan(review.source_plan) == original_payload
    assert review.source_plan.status is WorkoutPlanStatus.SUPERSEDED
    assert approved.status is WorkoutPlanStatus.ACTIVE
    assert approved.previous_program_id == review.source_plan_id
    assert review.approved_plan_id == approved.id


def test_approval_cannot_replace_a_newer_active_plan(service, review, coach, newer_plan):
    with pytest.raises(ReviewConflict) as error:
        service.approve(review.id, coach.id, expected_revision=review.draft_revision)
    assert error.value.code == "REVIEW_SUPERSEDED"
    assert newer_plan.status is WorkoutPlanStatus.ACTIVE
```

- [ ] **Step 7: Implement atomic clone and approval**

Clone plan provenance, days, non-editable prescription values, exercise snapshots, and progression
metadata. Apply only the five approved edit categories from the validated draft. Set
`generation_method="coach_review"`, `previous_program_id=source.id`,
`regeneration_reason="coach_review_approved"`, and an explicit `difference_summary`. Lock the review
and current active plan, supersede the source, activate the clone, mark the review approved, and
commit once. Roll back all changes on conflict or database failure.

- [ ] **Step 8: Run the service and validation suites**

Run: `cd backend && pytest tests/workout_reviews/test_service.py tests/workout_reviews/test_validation.py tests/workouts/test_repository.py -q`

Expected: PASS.

- [ ] **Step 9: Commit the domain slice**

```bash
git add backend/app/workout_reviews backend/app/workouts/repository.py backend/tests/workout_reviews backend/tests/workouts/test_repository.py
git commit -m "feat(workouts): approve immutable coach-reviewed plan versions"
```

---

### Task 3: Expose Coach Queue and Member Version APIs

**Files:**
- Create: `backend/app/workout_reviews/dependencies.py`
- Create: `backend/app/workout_reviews/router.py`
- Modify: `backend/app/workout_reviews/schemas.py`
- Modify: `backend/app/workouts/schemas.py`
- Modify: `backend/app/workouts/repository.py`
- Modify: `backend/app/workouts/router.py`
- Modify: `backend/app/workouts/service.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/workout_reviews/test_api.py`
- Test: `backend/tests/workouts/test_workout_plan_api.py`
- Test: `backend/tests/workouts/test_service.py`

**Interfaces:**
- Consumes: Task 2 service methods and existing session authentication.
- Produces: `/api/v1/coach/workout-reviews/*`, `/api/v1/workout-plans/history`, and review-aware `WorkoutPlanResponse`.

- [ ] **Step 1: Write failing role and queue API tests**

```python
def test_member_cannot_read_coach_queue(client, member_session):
    response = client.get("/api/v1/coach/workout-reviews")
    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "COACH_ROLE_REQUIRED"


def test_coach_lists_and_claims_pending_review(client, db, coach_session, pending_review):
    queue = client.get("/api/v1/coach/workout-reviews?view=pending")
    assert [item["id"] for item in queue.json()] == [str(pending_review.id)]
    claimed = client.post(f"/api/v1/coach/workout-reviews/{pending_review.id}/claim")
    assert claimed.status_code == 200
    assert claimed.json()["status"] == "claimed"
```

- [ ] **Step 2: Run API tests and verify failure**

Run: `cd backend && pytest tests/workout_reviews/test_api.py -q`

Expected: FAIL with route not found.

- [ ] **Step 3: Add coach dependency and HTTP contracts**

`require_coach` queries `UserSpecialistRole` for the authenticated user and exact
`SpecialistRole.COACH`. Add these endpoints:

```text
GET  /api/v1/coach/workout-reviews/access
GET  /api/v1/coach/workout-reviews?view=pending|mine|approved
GET  /api/v1/coach/workout-reviews/{review_id}
POST /api/v1/coach/workout-reviews/{review_id}/claim
POST /api/v1/coach/workout-reviews/{review_id}/renew
PUT  /api/v1/coach/workout-reviews/{review_id}/draft
POST /api/v1/coach/workout-reviews/{review_id}/approve
```

Require trusted origin on mutating endpoints. Map not-found to 404, role failure to 403, stale
revision/lease conflict to 409, and draft validation to 422 with `{code, problems}`.

- [ ] **Step 4: Write failing member history and generation-hook tests**

```python
def test_new_generation_creates_one_pending_review(service, db, user):
    result = asyncio.run(service.generate(user.id))
    reviews = db.scalars(select(WorkoutPlanReview).where(
        WorkoutPlanReview.source_plan_id == result.plan.id
    )).all()
    assert len(reviews) == 1


def test_member_history_returns_initial_and_approved_versions(client, member_session, versions):
    response = client.get("/api/v1/workout-plans/history")
    assert response.status_code == 200
    assert [item["review_state"] for item in response.json()] == [
        "coach_approved", "initial_generated"
    ]
```

- [ ] **Step 5: Integrate idempotent review creation and member history**

Call `ensure_pending_review` after each successful non-reused deterministic or AI plan activation
and before its existing commit. Do not create reviews for legacy plans, reused plans, or
coach-approved clones. When generation supersedes a source plan, mark its open review `superseded`
in the same transaction. Add newest-first user-scoped history and enrich plan responses with a
`coach_review` field using:

```python
class WorkoutPlanCoachReviewResponse(BaseModel):
    state: Literal["pending_coach_review", "initial_generated", "coach_approved", "none"]
    coach_display_name: str | None
    coach_note: str | None
    approved_at: datetime | None


class WorkoutPlanVersionSummaryResponse(BaseModel):
    id: UUID
    created_at: datetime
    activated_at: datetime | None
    is_active: bool
    review: WorkoutPlanCoachReviewResponse
```

The existing `GET /{plan_id}` remains owner-scoped and supports opening a historical version.

- [ ] **Step 6: Run backend API and generation regressions**

Run: `cd backend && pytest tests/workout_reviews/test_api.py tests/workouts/test_workout_plan_api.py tests/workouts/test_service.py -q`

Expected: PASS.

- [ ] **Step 7: Commit the API slice**

```bash
git add backend/app/workout_reviews backend/app/workouts backend/app/main.py backend/tests/workout_reviews backend/tests/workouts
git commit -m "feat(workouts): expose coach queue and member plan history"
```

---

### Task 4: Add Frontend Contracts and Coach Route Guard

**Files:**
- Create: `frontend/src/features/workoutReviews/types.ts`
- Create: `frontend/src/features/workoutReviews/api.ts`
- Modify: `frontend/src/features/profile/ProfileRouteGuards.tsx`
- Modify: `frontend/src/App.tsx`
- Test: `frontend/src/features/workoutReviews/api.test.ts`
- Test: `frontend/src/features/profile/ProfileRouteGuards.test.tsx`
- Test: `frontend/src/App.test.tsx`

**Interfaces:**
- Consumes: Task 3 HTTP contracts.
- Produces: `verifyCoachAccess`, queue/review mutations, and `CoachRoute`.

- [ ] **Step 1: Write failing API and guard tests**

```tsx
it("allows the coach route only after backend authorization", async () => {
  api.verifyCoachAccess.mockResolvedValue(undefined);
  renderCoachGuard();
  expect(await screen.findByText("coach workspace")).toBeInTheDocument();
});

it("redirects a non-coach to the dashboard", async () => {
  api.verifyCoachAccess.mockRejectedValue(new ApiError(403, "forbidden"));
  renderCoachGuard();
  expect(await screen.findByText("dashboard")).toBeInTheDocument();
});
```

- [ ] **Step 2: Run frontend contract tests and verify failure**

Run: `cd frontend && npm run test -- src/features/workoutReviews/api.test.ts src/features/profile/ProfileRouteGuards.test.tsx src/App.test.tsx`

Expected: FAIL because the API module and guard do not exist.

- [ ] **Step 3: Implement strict TypeScript contracts and API calls**

```typescript
export type WorkoutReviewStatus = "pending" | "claimed" | "approved" | "superseded";
export type WorkoutReviewQueueView = "pending" | "mine" | "approved";

export function saveWorkoutReviewDraft(
  reviewId: string,
  payload: WorkoutReviewDraftUpdate,
): Promise<WorkoutReviewDetail> {
  return request(`${basePath}/${reviewId}/draft`, { method: "PUT", body: payload });
}
```

Type every queue field, lease timestamp, editable exercise, revision, validation problem, and
approval response. Do not use `any` or expose backend-only provenance unnecessarily.

- [ ] **Step 4: Add API-probed `CoachRoute` and protected route**

Follow `PhysicianRoute`: show startup loading, call `/access`, render `Outlet` on success, and
redirect to `/dashboard` on denial. Register `/coach/workouts` inside `ProtectedRoute` and outside
member profile-completion guards so a coach account does not need a member workout profile.

- [ ] **Step 5: Run contract and guard tests**

Run: `cd frontend && npm run test -- src/features/workoutReviews/api.test.ts src/features/profile/ProfileRouteGuards.test.tsx src/App.test.tsx`

Expected: PASS.

- [ ] **Step 6: Commit the frontend access slice**

```bash
git add frontend/src/features/workoutReviews frontend/src/features/profile/ProfileRouteGuards.tsx frontend/src/App.tsx frontend/src/App.test.tsx
git commit -m "feat(workouts): protect coach review workspace routes"
```

---

### Task 5: Build the Coach Queue and Editor

**Files:**
- Create: `frontend/src/features/workoutReviews/CoachWorkoutReviewPage.tsx`
- Create: `frontend/src/features/workoutReviews/coachWorkoutReview.css`
- Modify: `frontend/src/features/workoutReviews/api.ts`
- Modify: `frontend/src/shared/AuthenticatedHeader.tsx`
- Modify: `frontend/src/i18n/fa.ts`
- Modify: `frontend/src/i18n/en.ts`
- Test: `frontend/src/features/workoutReviews/CoachWorkoutReviewPage.test.tsx`
- Test: `frontend/src/shared/AuthenticatedHeader.test.tsx`

**Interfaces:**
- Consumes: Task 4 frontend API and typed contracts.
- Produces: shared queue tabs, exclusive claim flow, editable draft, save, lease renewal, and approval UI.

- [ ] **Step 1: Write failing queue and claim tests**

```tsx
it("shows pending, mine, and approved queue tabs", async () => {
  api.listWorkoutReviews.mockResolvedValue([pendingReview]);
  renderPage();
  expect(await screen.findByRole("tab", { name: "در انتظار بررسی" })).toBeVisible();
  expect(screen.getByRole("tab", { name: "در حال بررسی من" })).toBeVisible();
  expect(screen.getByRole("tab", { name: "تأییدشده" })).toBeVisible();
});

it("claims a review before enabling draft controls", async () => {
  const user = userEvent.setup();
  renderPage();
  await user.click(await screen.findByRole("button", { name: "شروع بازبینی" }));
  expect(api.claimWorkoutReview).toHaveBeenCalledWith(pendingReview.id);
  expect(await screen.findByLabelText("تعداد ست")).toBeEnabled();
});
```

- [ ] **Step 2: Run page tests and verify failure**

Run: `cd frontend && npm run test -- src/features/workoutReviews/CoachWorkoutReviewPage.test.tsx`

Expected: FAIL because the page is missing.

- [ ] **Step 3: Implement queue state and review selection**

Render accessible tab buttons, loading/empty/error states, member goal/experience/constraints, lease
owner and expiry, and the immutable source prescription. Claim before rendering enabled form
controls. On 409, reload the queue and explain that another coach owns the review.

- [ ] **Step 4: Write failing edit, save, and approve tests**

```tsx
it("saves only permitted prescription fields with the current revision", async () => {
  const user = userEvent.setup();
  renderClaimedReview();
  await user.clear(await screen.findByLabelText("تعداد ست"));
  await user.type(screen.getByLabelText("تعداد ست"), "4");
  await user.click(screen.getByRole("button", { name: "ذخیره پیش‌نویس" }));
  expect(api.saveWorkoutReviewDraft).toHaveBeenCalledWith(review.id, expect.objectContaining({
    expected_revision: review.draft_revision,
  }));
});

it("moves an approved review to the approved tab", async () => {
  const user = userEvent.setup();
  renderClaimedReview();
  await user.click(await screen.findByRole("button", { name: "تأیید و ارسال برای کاربر" }));
  expect(api.approveWorkoutReview).toHaveBeenCalledOnce();
});
```

- [ ] **Step 5: Implement editor, validation feedback, and lease renewal**

Provide an active programmable exercise selector, numeric inputs for sets/repetitions/rest, Persian
and English exercise notes, and a user-visible coach note. Disable approval while fields are invalid
or a save is pending. Renew the lease during successful saves and with a low-frequency timer while
the editor is open; stop the timer on unmount. Render backend 422 field problems next to the
corresponding day/exercise and handle stale revision by reloading instead of overwriting.

- [ ] **Step 6: Add coach navigation discovery and bilingual styling**

Probe coach access once for the authenticated header and show the coach link only when authorized.
Style the queue/editor with the existing dark Fitsho surface tokens, clear focus states, responsive
cards, and correct RTL/LTR input alignment. Add complete Persian and English translation keys.

- [ ] **Step 7: Run coach workspace tests and frontend static checks**

Run: `cd frontend && npm run test -- src/features/workoutReviews/CoachWorkoutReviewPage.test.tsx src/shared/AuthenticatedHeader.test.tsx && npm run lint && npm run build`

Expected: PASS.

- [ ] **Step 8: Commit the coach workspace**

```bash
git add frontend/src/features/workoutReviews frontend/src/shared/AuthenticatedHeader.tsx frontend/src/shared/AuthenticatedHeader.test.tsx frontend/src/i18n
git commit -m "feat(workouts): add coach workout review workspace"
```

---

### Task 6: Show Review State and Immutable Version History to Members

**Files:**
- Modify: `frontend/src/features/workouts/types.ts`
- Modify: `frontend/src/features/workouts/api.ts`
- Modify: `frontend/src/features/workouts/WorkoutPlanPage.tsx`
- Modify: `frontend/src/features/workouts/workoutPlan.css`
- Modify: `frontend/src/i18n/fa.ts`
- Modify: `frontend/src/i18n/en.ts`
- Test: `frontend/src/features/workouts/api.test.ts`
- Test: `frontend/src/features/workouts/WorkoutPlanPage.test.tsx`

**Interfaces:**
- Consumes: Task 3 member history API and review-aware plan responses.
- Produces: pending/approved status, coach metadata, and read-only initial/approved plan switching.

- [ ] **Step 1: Write failing member status tests**

```tsx
it("keeps the generated plan visible while coach review is pending", async () => {
  api.getActiveWorkoutPlan.mockResolvedValue({
    ...plan,
    coach_review: { state: "pending_coach_review", coach_display_name: null,
      coach_note: null, approved_at: null },
  });
  renderPage();
  expect(await screen.findByText("در انتظار تأیید مربی")).toBeVisible();
  expect(screen.getByText("پرس سینه دمبل")).toBeVisible();
});

it("shows coach approval metadata", async () => {
  api.getActiveWorkoutPlan.mockResolvedValue(approvedPlan);
  renderPage();
  expect(await screen.findByText("تأییدشده توسط مربی")).toBeVisible();
  expect(screen.getByText("یادداشت مربی")).toBeVisible();
});
```

- [ ] **Step 2: Run member page tests and verify failure**

Run: `cd frontend && npm run test -- src/features/workouts/WorkoutPlanPage.test.tsx src/features/workouts/api.test.ts`

Expected: FAIL because review metadata and history are not rendered.

- [ ] **Step 3: Add history API and strict member types**

```typescript
export type WorkoutPlanCoachReview = {
  state: "pending_coach_review" | "initial_generated" | "coach_approved" | "none";
  coach_display_name: string | null;
  coach_note: string | null;
  approved_at: string | null;
};

export function getWorkoutPlanHistory(): Promise<WorkoutPlanVersionSummary[]> {
  return request(`${workoutPlansPath}/history`);
}

export function getWorkoutPlan(planId: string): Promise<WorkoutPlan> {
  return request(`${workoutPlansPath}/${planId}`);
}
```

- [ ] **Step 4: Implement member badges and version switcher**

Load active plan and history together. Keep the active version selected initially. Render pending or
approved badge, coach name/date/note when available, and a “Plan versions” section ordered newest
first. Selecting a historical ID loads it read-only and clearly labels it historical; generation or
update actions remain associated only with the active plan view.

- [ ] **Step 5: Add bilingual copy and responsive history styling**

Add Persian and English copy for pending, approved, initial version, historical version, active
version, coach note, history loading, and history errors. Use locale date formatting and preserve
RTL/LTR direction.

- [ ] **Step 6: Run member UI tests and frontend checks**

Run: `cd frontend && npm run test -- src/features/workouts/WorkoutPlanPage.test.tsx src/features/workouts/api.test.ts && npm run lint && npm run build`

Expected: PASS.

- [ ] **Step 7: Commit the member history slice**

```bash
git add frontend/src/features/workouts frontend/src/i18n/fa.ts frontend/src/i18n/en.ts
git commit -m "feat(workouts): show coach approval and plan version history"
```

---

### Task 7: Verify Migration, Security, and Cross-Feature Compatibility

**Files:**
- Modify: `docs/workout-plan-generator.md`
- Test: all files changed by Tasks 1–6.

**Interfaces:**
- Consumes: complete backend and frontend feature.
- Produces: migration evidence, regression evidence, and operational documentation.

- [ ] **Step 1: Add workflow documentation**

Document the member lifecycle, coach role requirement, `/coach/workouts` route, 30-minute lease,
immutable version behavior, and the existing `user_specialist_roles` mechanism for granting the
`coach` role. Do not document raw credentials or environment secrets.

- [ ] **Step 2: Verify migration from current head and from an empty database**

Run: `cd backend && alembic upgrade head && alembic current`

Expected: one head at `20260809_58`.

Run the project's disposable test-database migration path from zero to head, then remove only that
explicit disposable database. Confirm legacy workout rows receive no fabricated review rows.

- [ ] **Step 3: Run complete backend verification**

Run: `cd backend && ruff check app tests && mypy app && pytest -q`

Expected: all checks pass; the pre-existing explicitly skipped live-provider test may remain skipped.

- [ ] **Step 4: Run complete frontend verification**

Run: `cd frontend && npm run lint && npm run test -- --run && npm run build`

Expected: all checks pass.

- [ ] **Step 5: Inspect API and runtime behavior**

Start the existing Compose backend and Vite frontend using the configured local ports. Verify:

```text
member generates plan -> active plan shows pending coach approval
coach claims plan -> second coach receives 409
coach edits and approves -> approved clone becomes active
member history -> both initial and approved versions open read-only
nutrition physician panel -> unchanged and accessible only to physicians
```

- [ ] **Step 6: Commit final documentation or regression fixes**

```bash
git add docs/workout-plan-generator.md <only-files-changed-for-verified-regression-fixes>
git commit -m "docs(workouts): document coach review operations"
```

- [ ] **Step 7: Push the dedicated branch**

Run: `git push origin nutrition`

Expected: `origin/nutrition` points to the final verified commit.
