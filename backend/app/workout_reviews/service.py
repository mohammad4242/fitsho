from __future__ import annotations

from collections.abc import Callable
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy.orm import Session

from app.workout_cycles.service import start_cycle
from app.workout_reviews.enums import (
    WorkoutReviewErrorCode,
    WorkoutReviewQueueView,
    WorkoutReviewStatus,
)
from app.workout_reviews.models import WorkoutPlanReview
from app.workout_reviews.repository import (
    get_active_plan_for_update,
    get_review,
    get_review_for_update,
    list_reviews,
    supersede_open_review,
)
from app.workout_reviews.schemas import WorkoutReviewDraftUpdate
from app.workout_reviews.validation import ValidatedDraft, WorkoutReviewDraftValidator
from app.workouts.enums import WorkoutPlanStatus
from app.workouts.models import WorkoutDay, WorkoutPlan, WorkoutPlanExercise

LEASE_DURATION = timedelta(minutes=30)


class ReviewConflict(Exception):
    def __init__(self, code: WorkoutReviewErrorCode) -> None:
        super().__init__(code.value)
        self.code = code


class WorkoutReviewService:
    def __init__(
        self,
        db: Session,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._db = db
        self._clock = clock or (lambda: datetime.now(UTC))
        self._validator = WorkoutReviewDraftValidator(db)

    def detail(self, review_id: UUID) -> WorkoutPlanReview:
        review = get_review(self._db, review_id)
        if review is None:
            raise ReviewConflict(WorkoutReviewErrorCode.REVIEW_NOT_FOUND)
        return review

    def queue(
        self,
        view: WorkoutReviewQueueView,
        coach_id: UUID,
    ) -> list[WorkoutPlanReview]:
        return list_reviews(self._db, view=view, coach_id=coach_id, now=self._clock())

    def claim(self, review_id: UUID, coach_id: UUID) -> WorkoutPlanReview:
        review = self._required_review(review_id)
        now = self._clock()
        self._require_open(review)
        if (
            review.claimed_by_user_id is not None
            and review.claimed_by_user_id != coach_id
            and review.lease_expires_at is not None
            and review.lease_expires_at > now
        ):
            raise ReviewConflict(WorkoutReviewErrorCode.REVIEW_ALREADY_CLAIMED)
        review.status = WorkoutReviewStatus.CLAIMED
        review.claimed_by_user_id = coach_id
        review.lease_acquired_at = now
        review.lease_expires_at = now + LEASE_DURATION
        if review.draft_payload is None:
            review.draft_payload = self._initial_draft(review.source_plan)
        self._db.commit()
        return review

    def renew(self, review_id: UUID, coach_id: UUID) -> WorkoutPlanReview:
        review = self._required_review(review_id)
        self._require_lease(review, coach_id)
        now = self._clock()
        review.lease_acquired_at = now
        review.lease_expires_at = now + LEASE_DURATION
        self._db.commit()
        return review

    def save_draft(
        self,
        review_id: UUID,
        coach_id: UUID,
        payload: WorkoutReviewDraftUpdate,
    ) -> WorkoutPlanReview:
        review = self._required_review(review_id)
        self._require_lease(review, coach_id)
        self._require_revision(review, payload.expected_revision)
        self._validator.validate(review.source_plan, payload)
        review.draft_payload = payload.model_dump(
            mode="json", exclude={"expected_revision", "coach_note"}
        )
        review.coach_note = payload.coach_note.strip() if payload.coach_note else None
        review.draft_revision += 1
        now = self._clock()
        review.lease_acquired_at = now
        review.lease_expires_at = now + LEASE_DURATION
        self._db.commit()
        return review

    def approve(
        self,
        review_id: UUID,
        coach_id: UUID,
        *,
        expected_revision: int,
    ) -> WorkoutPlan:
        review = self._required_review(review_id)
        self._require_lease(review, coach_id)
        self._require_revision(review, expected_revision)
        active = get_active_plan_for_update(self._db, review.user_id)
        if review.source_plan.status not in {
            WorkoutPlanStatus.PENDING_REVIEW,
            WorkoutPlanStatus.ACTIVE,
        } or (
            review.source_plan.status is WorkoutPlanStatus.ACTIVE
            and (active is None or active.id != review.source_plan_id)
        ):
            review.status = WorkoutReviewStatus.SUPERSEDED
            self._db.commit()
            raise ReviewConflict(WorkoutReviewErrorCode.REVIEW_SUPERSEDED)
        if review.draft_payload is None:
            raise ReviewConflict(WorkoutReviewErrorCode.INVALID_DRAFT)
        payload = WorkoutReviewDraftUpdate.model_validate(
            {
                **review.draft_payload,
                "expected_revision": expected_revision,
                "coach_note": review.coach_note,
            }
        )
        validated = self._validator.validate(review.source_plan, payload)
        approved = self._clone_approved_plan(review.source_plan, validated)
        now = self._clock()
        if active is not None:
            active.status = WorkoutPlanStatus.SUPERSEDED
            active.superseded_at = now
            supersede_open_review(self._db, active.id)
        review.source_plan.status = WorkoutPlanStatus.SUPERSEDED
        review.source_plan.superseded_at = now
        approved.status = WorkoutPlanStatus.ACTIVE
        approved.activated_at = now
        self._db.add(approved)
        self._db.flush()
        start_cycle(
            self._db,
            user_id=approved.user_id,
            workout_plan_id=approved.id,
        )
        review.status = WorkoutReviewStatus.APPROVED
        review.approved_plan_id = approved.id
        review.approved_at = now
        self._db.commit()
        return approved

    def _required_review(self, review_id: UUID) -> WorkoutPlanReview:
        review = get_review_for_update(self._db, review_id)
        if review is None:
            raise ReviewConflict(WorkoutReviewErrorCode.REVIEW_NOT_FOUND)
        return review

    @staticmethod
    def _require_open(review: WorkoutPlanReview) -> None:
        if review.status is WorkoutReviewStatus.APPROVED:
            raise ReviewConflict(WorkoutReviewErrorCode.REVIEW_ALREADY_APPROVED)
        if review.status is WorkoutReviewStatus.SUPERSEDED:
            raise ReviewConflict(WorkoutReviewErrorCode.REVIEW_SUPERSEDED)

    def _require_lease(self, review: WorkoutPlanReview, coach_id: UUID) -> None:
        self._require_open(review)
        if review.claimed_by_user_id != coach_id:
            raise ReviewConflict(WorkoutReviewErrorCode.REVIEW_ALREADY_CLAIMED)
        if review.lease_expires_at is None or review.lease_expires_at <= self._clock():
            raise ReviewConflict(WorkoutReviewErrorCode.REVIEW_LEASE_EXPIRED)

    @staticmethod
    def _require_revision(review: WorkoutPlanReview, expected_revision: int) -> None:
        if review.draft_revision != expected_revision:
            raise ReviewConflict(WorkoutReviewErrorCode.STALE_DRAFT_REVISION)

    @staticmethod
    def _initial_draft(plan: WorkoutPlan) -> dict[str, object]:
        return {
            "days": [
                {
                    "day_number": day.day_number,
                    "exercises": [
                        {
                            "order_index": item.order_index,
                            "exercise_id": str(item.exercise_id),
                            "sets": item.sets,
                            "reps_min": item.reps_min,
                            "reps_max": item.reps_max,
                            "rir": item.rir,
                            "rest_seconds": item.rest_seconds,
                            "notes_en": item.notes_en,
                            "notes_fa": item.notes_fa,
                        }
                        for item in day.exercises
                    ],
                }
                for day in plan.days
            ]
        }

    @staticmethod
    def _clone_approved_plan(source: WorkoutPlan, validated: ValidatedDraft) -> WorkoutPlan:
        plan = WorkoutPlan(
            user_id=source.user_id,
            status=WorkoutPlanStatus.GENERATING,
            generation_signature=source.generation_signature,
            profile_snapshot=deepcopy(source.profile_snapshot),
            provider=source.provider,
            model_id=source.model_id,
            prompt_version=source.prompt_version,
            generation_policy_version=source.generation_policy_version,
            candidate_set_hash=source.candidate_set_hash,
            generation_method="coach_review",
            engine_version=source.engine_version,
            ruleset_version=source.ruleset_version,
            primary_goal=source.primary_goal,
            secondary_goal=source.secondary_goal,
            training_status=source.training_status,
            safety_status=source.safety_status,
            seed=source.seed,
            exercise_catalog_snapshot=deepcopy(source.exercise_catalog_snapshot),
            assumptions=deepcopy(source.assumptions),
            warnings=deepcopy(source.warnings),
            validation_report=deepcopy(source.validation_report),
            aggregate_metrics=deepcopy(source.aggregate_metrics),
            decision_trace=deepcopy(source.decision_trace),
            body_analysis_provenance=deepcopy(source.body_analysis_provenance),
            ai_coach_template_slug=source.ai_coach_template_slug,
            ai_coach_program_explanation_fa=source.ai_coach_program_explanation_fa,
            progression_policy=deepcopy(source.progression_policy),
            previous_program_id=source.id,
            regeneration_reason="coach_review_approved",
            difference_summary={
                "source_plan_id": str(source.id),
                "reviewed_by_coach": True,
            },
        )
        source_days = {day.day_number: day for day in source.days}
        source_slots = {
            (day.day_number, item.order_index): item
            for day in source.days
            for item in day.exercises
        }
        catalog = source.exercise_catalog_snapshot.get("exercises", {})
        for output_day, draft_day in zip(validated.plan.days, validated.payload.days, strict=True):
            source_day = source_days[output_day.day_number]
            day = WorkoutDay(
                day_number=source_day.day_number,
                title_en=source_day.title_en,
                title_fa=source_day.title_fa,
                estimated_duration_minutes=output_day.estimated_duration_minutes,
                weekday=source_day.weekday,
                focus=source_day.focus,
                cardio=deepcopy(source_day.cardio),
                ai_coach_explanation_fa=source_day.ai_coach_explanation_fa,
            )
            for output_item, draft_item in zip(
                output_day.exercises, draft_day.exercises, strict=True
            ):
                source_item = source_slots[(output_day.day_number, draft_item.order_index)]
                changed_exercise = output_item.exercise_id != source_item.exercise_id
                snapshot = (
                    deepcopy(catalog.get(str(output_item.exercise_id), {}))
                    if isinstance(catalog, dict)
                    else {}
                )
                day.exercises.append(
                    WorkoutPlanExercise(
                        exercise_id=output_item.exercise_id,
                        order_index=draft_item.order_index,
                        sets=output_item.sets,
                        reps_min=output_item.reps_min,
                        reps_max=output_item.reps_max,
                        rest_seconds=output_item.rest_seconds,
                        rir=output_item.rir,
                        estimated_minutes=output_item.estimated_minutes,
                        notes_en=output_item.notes_en,
                        notes_fa=output_item.notes_fa,
                        exercise_snapshot=snapshot,
                        reason_codes=(
                            ["coach_replaced_exercise"]
                            if changed_exercise
                            else deepcopy(source_item.reason_codes)
                        ),
                        substitution_exercise_ids=(
                            []
                            if changed_exercise
                            else deepcopy(source_item.substitution_exercise_ids)
                        ),
                        warmup_sets=source_item.warmup_sets,
                        load_guidance=source_item.load_guidance,
                        progression_rule=source_item.progression_rule,
                    )
                )
            plan.days.append(day)
        return plan
