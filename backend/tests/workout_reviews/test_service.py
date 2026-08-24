from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.athlete_state.schemas import (
    AthleteState,
    AthleteStateAdherence,
    AthleteStateBodyProgress,
    AthleteStateDifficultyTrend,
    AthleteStateExerciseContext,
    AthleteStateProvenance,
    AthleteStateReasonCode,
    AthleteStateRecoveryTrend,
    AthleteStateReplacementContext,
    AthleteStateSafetyContext,
    AthleteStateScheduleContext,
)
from app.auth.models import User
from app.exercises.enums import (
    BodyRegion,
    Difficulty,
    ExerciseType,
    MediaType,
    MovementPattern,
    MuscleFocus,
    MuscleGroup,
)
from app.exercises.models import Exercise
from app.workout_cycles.enums import WorkoutExerciseReplacementReason
from app.workout_cycles.models import WorkoutCycle
from app.workout_cycles.service import start_cycle
from app.workout_reviews.diff import build_coach_diff
from app.workout_reviews.enums import WorkoutReviewErrorCode, WorkoutReviewStatus
from app.workout_reviews.models import WorkoutPlanReview
from app.workout_reviews.repository import ensure_pending_review
from app.workout_reviews.schemas import WorkoutReviewDraftUpdate, WorkoutReviewExerciseDraft
from app.workout_reviews.service import ReviewConflict, WorkoutReviewService
from app.workout_reviews.summary import build_athlete_summary, build_fitsho_recommendation
from app.workout_reviews.validation import DraftValidationError
from app.workouts.enums import WorkoutPlanStatus
from app.workouts.models import WorkoutDay, WorkoutPlan, WorkoutPlanExercise


class Clock:
    def __init__(self) -> None:
        self.now = datetime(2026, 8, 9, 8, 30, tzinfo=UTC)

    def __call__(self) -> datetime:
        return self.now

    def advance(self, *, minutes: int) -> None:
        self.now += timedelta(minutes=minutes)


def _user(db: Session, prefix: str) -> User:
    user = User(email=f"{prefix}-{uuid4()}@example.com", password_hash="hash")
    db.add(user)
    db.flush()
    return user


def _exercise(db: Session, slug: str, *, programmable: bool = True) -> Exercise:
    exercise = Exercise(
        slug=f"{slug}-{uuid4().hex}",
        name_en=slug.replace("-", " ").title(),
        name_fa=f"حرکت {slug}",
        body_region=BodyRegion.UPPER_BODY,
        primary_muscle=MuscleGroup.CHEST,
        muscle_focus=MuscleFocus.MID_CHEST,
        difficulty=Difficulty.BEGINNER,
        movement_pattern=MovementPattern.HORIZONTAL_PUSH,
        exercise_type=ExerciseType.COMPOUND,
        instructions_en=["Set up.", "Move safely.", "Finish."],
        instructions_fa=["آماده شو.", "ایمن حرکت کن.", "تمام کن."],
        safety_notes_en=["Move with control."],
        safety_notes_fa=["کنترل‌شده حرکت کن."],
        media_path="/exercises/exercise-placeholder.svg",
        media_type=MediaType.PLACEHOLDER,
        is_active=True,
        is_programmable=programmable,
        needs_review=False,
    )
    db.add(exercise)
    db.flush()
    return exercise


def _candidate_snapshot(exercise: Exercise) -> dict[str, object]:
    return {
        "id": str(exercise.id),
        "primary_muscle": exercise.primary_muscle.value if exercise.primary_muscle else None,
        "secondary_muscles": [],
        "movement_pattern": exercise.movement_pattern.value,
        "exercise_type": exercise.exercise_type.value,
        "equipment": [],
        "difficulty": exercise.difficulty.value,
        "caution_tags": [],
        "labels": [],
    }


def _active_plan(
    db: Session,
    *,
    user: User,
    exercises: list[Exercise],
    status: WorkoutPlanStatus = WorkoutPlanStatus.ACTIVE,
) -> WorkoutPlan:
    plan = WorkoutPlan(
        user_id=user.id,
        status=status,
        generation_signature="a" * 64,
        profile_snapshot={"plan_duration_weeks": 4, "session_duration_minutes": 45},
        provider="fake",
        model_id="fake-model",
        prompt_version="v1",
        generation_policy_version="v1",
        candidate_set_hash="b" * 64,
        generation_method="ai",
        exercise_catalog_snapshot={
            "exercises": {str(exercise.id): _candidate_snapshot(exercise) for exercise in exercises}
        },
    )
    day = WorkoutDay(
        day_number=1,
        title_en="Upper body",
        title_fa="بالاتنه",
        estimated_duration_minutes=20,
    )
    day.exercises.append(
        WorkoutPlanExercise(
            exercise_id=exercises[0].id,
            order_index=1,
            sets=3,
            reps_min=8,
            reps_max=12,
            rest_seconds=90,
            rir=2,
            estimated_minutes=5,
            notes_en=None,
            notes_fa=None,
            exercise_snapshot=_candidate_snapshot(exercises[0]),
        )
    )
    plan.days.append(day)
    db.add(plan)
    db.flush()
    return plan


def _draft(
    review: WorkoutPlanReview,
    *,
    exercise_id: str | None = None,
) -> WorkoutReviewDraftUpdate:
    assert review.draft_payload is not None
    payload = deepcopy(review.draft_payload)
    payload["expected_revision"] = review.draft_revision
    if exercise_id is not None:
        payload["days"][0]["exercises"][0]["exercise_id"] = exercise_id
    return WorkoutReviewDraftUpdate.model_validate(payload)


def test_ensure_pending_review_is_idempotent(db: Session) -> None:
    member = _user(db, "idempotent-member")
    exercise = _exercise(db, "press")
    plan = _active_plan(db, user=member, exercises=[exercise])

    first = ensure_pending_review(db, plan)
    second = ensure_pending_review(db, plan)

    assert first.id == second.id
    assert db.scalars(select(WorkoutPlanReview)).all() == [first]


def test_athlete_summary_maps_state_without_rederiving_signals(db: Session) -> None:
    member = _user(db, "summary-state-member")
    source = _active_plan(db, user=member, exercises=[_exercise(db, "summary-press")])
    state = AthleteState(
        user_id=member.id,
        adherence=AthleteStateAdherence(sessions_completed=3, planned_sessions=4, percent=75),
        recovery_trend=AthleteStateRecoveryTrend(),
        difficulty_trend=AthleteStateDifficultyTrend(),
        schedule=AthleteStateScheduleContext(),
        body_progress=AthleteStateBodyProgress(),
        provenance=AthleteStateProvenance(),
    )
    ensure_pending_review(db, source)

    summary = build_athlete_summary(state, previous_approved_plan_id=source.id)

    assert summary.athlete_state is state
    assert summary.previous_approved_plan_id == source.id
    assert summary.athlete_state.adherence.percent == 75


def test_athlete_summary_preserves_distinct_signals_and_provenance() -> None:
    user_id = uuid4()
    original_id = uuid4()
    replacement_id = uuid4()
    replacement_source_id = uuid4()
    safety_source_id = uuid4()
    preference_source_id = uuid4()
    state = AthleteState(
        user_id=user_id,
        adherence=AthleteStateAdherence(
            sessions_completed=6,
            planned_sessions=6,
            percent=100,
            reason_codes=(AthleteStateReasonCode.ADHERENCE_CALCULATED_FROM_WEEKLY_CHECK_INS,),
        ),
        recovery_trend=AthleteStateRecoveryTrend(),
        difficulty_trend=AthleteStateDifficultyTrend(),
        persistent_disliked_exercises=(original_id,),
        unavailable_equipment_context=(
            AthleteStateExerciseContext(
                exercise_id=original_id,
                source_preference_ids=(preference_source_id,),
                reason_codes=(AthleteStateReasonCode.PERSISTENT_EQUIPMENT_CONTEXT,),
            ),
        ),
        replacement_context=(
            AthleteStateReplacementContext(
                original_exercise_id=original_id,
                replacement_exercise_id=replacement_id,
                persistent_count=2,
                reasons=(WorkoutExerciseReplacementReason.DISLIKE,),
                source_replacement_ids=(replacement_source_id,),
            ),
        ),
        safety_context=(
            AthleteStateSafetyContext(
                exercise_id=original_id,
                signal_count=1,
                source_safety_signal_ids=(safety_source_id,),
            ),
        ),
        pain_sensitive_exercises=(original_id,),
        schedule=AthleteStateScheduleContext(),
        body_progress=AthleteStateBodyProgress(),
        provenance=AthleteStateProvenance(
            replacement_ids=(replacement_source_id,),
            preference_ids=(preference_source_id,),
            safety_signal_ids=(safety_source_id,),
        ),
    )

    response = build_athlete_summary(state, previous_approved_plan_id=None)

    assert response.athlete_state.persistent_disliked_exercises == (original_id,)
    assert response.athlete_state.pain_sensitive_exercises == (original_id,)
    assert response.athlete_state.replacement_context[0].source_replacement_ids == (
        replacement_source_id,
    )
    assert response.athlete_state.safety_context[0].source_safety_signal_ids == (safety_source_id,)
    assert response.athlete_state.provenance.preference_ids == (preference_source_id,)


def test_fitsho_recommendation_reuses_adaptation_difference_reasons(db: Session) -> None:
    member = _user(db, "recommendation-member")
    previous_exercise = _exercise(db, "recommendation-previous")
    previous = _active_plan(db, user=member, exercises=[previous_exercise])
    previous.status = WorkoutPlanStatus.SUPERSEDED
    previous.aggregate_metrics = {
        "weekly_effective_sets_by_muscle": {MuscleGroup.SHOULDERS.value: 10.0},
        "weekly_direct_sets_by_muscle": {MuscleGroup.SHOULDERS.value: 8.0},
    }
    db.flush()
    proposed = _active_plan(db, user=member, exercises=[previous_exercise])
    proposed.status = WorkoutPlanStatus.PENDING_REVIEW
    proposed.previous_program_id = previous.id
    proposed.aggregate_metrics = {
        "weekly_effective_sets_by_muscle": {MuscleGroup.SHOULDERS.value: 12.0},
        "weekly_direct_sets_by_muscle": {MuscleGroup.SHOULDERS.value: 9.0},
    }
    review = ensure_pending_review(db, proposed)
    state = AthleteState(
        user_id=member.id,
        adherence=AthleteStateAdherence(sessions_completed=19, planned_sessions=20, percent=95),
        recovery_trend=AthleteStateRecoveryTrend(
            summary="good",
        ),
        difficulty_trend=AthleteStateDifficultyTrend(
            summary="appropriate",
        ),
        lagging_muscles=(MuscleGroup.SHOULDERS,),
        priority_muscles=(MuscleGroup.SHOULDERS,),
        schedule=AthleteStateScheduleContext(),
        body_progress=AthleteStateBodyProgress(),
        provenance=AthleteStateProvenance(
            cycle_ids=(uuid4(),),
            workout_plan_ids=(previous.id, proposed.id),
        ),
    )
    db.flush()

    recommendation = build_fitsho_recommendation(db, review, state=state)

    volume = next(
        item for item in recommendation.difference_summary if item.change.value == "muscle_volume"
    )
    priority = next(
        item for item in recommendation.difference_summary if item.change.value == "priority_muscle"
    )
    assert recommendation.overall_action.value == "increase"
    assert volume.previous == 10.0
    assert volume.next == 12.0
    assert "LAGGING_MUSCLE_SUPPORTED_CONSERVATIVELY" in volume.reason_codes
    assert priority.previous is False
    assert priority.next is True
    assert (
        recommendation.to_snapshot_json()
        == build_fitsho_recommendation(
            db,
            review,
            state=state,
        ).to_snapshot_json()
    )


def test_fitsho_recommendation_keeps_safety_and_preference_decisions_distinct(
    db: Session,
) -> None:
    member = _user(db, "recommendation-safety-member")
    exercise = _exercise(db, "recommendation-safety")
    replacement = _exercise(db, "recommendation-safe-alternative")
    previous = _active_plan(db, user=member, exercises=[exercise])
    previous.status = WorkoutPlanStatus.SUPERSEDED
    db.flush()
    proposed = _active_plan(db, user=member, exercises=[exercise])
    proposed.status = WorkoutPlanStatus.PENDING_REVIEW
    proposed.previous_program_id = previous.id
    review = ensure_pending_review(db, proposed)
    source_replacement_id = uuid4()
    signal_id = uuid4()
    state = AthleteState(
        user_id=member.id,
        adherence=AthleteStateAdherence(sessions_completed=0, planned_sessions=0, percent=None),
        recovery_trend=AthleteStateRecoveryTrend(),
        difficulty_trend=AthleteStateDifficultyTrend(),
        persistent_disliked_exercises=(exercise.id,),
        pain_sensitive_exercises=(exercise.id,),
        replacement_context=(
            AthleteStateReplacementContext(
                original_exercise_id=exercise.id,
                replacement_exercise_id=replacement.id,
                persistent_count=2,
                reasons=(WorkoutExerciseReplacementReason.DISLIKE,),
                source_replacement_ids=(source_replacement_id,),
            ),
        ),
        safety_context=(
            AthleteStateSafetyContext(
                exercise_id=exercise.id,
                signal_count=1,
                source_safety_signal_ids=(signal_id,),
                source_replacement_ids=(source_replacement_id,),
            ),
        ),
        schedule=AthleteStateScheduleContext(),
        body_progress=AthleteStateBodyProgress(),
        provenance=AthleteStateProvenance(
            replacement_ids=(source_replacement_id,),
            safety_signal_ids=(signal_id,),
        ),
    )

    recommendation = build_fitsho_recommendation(db, review, state=state)

    safety = next(
        item
        for item in recommendation.difference_summary
        if item.change.value == "safety_constraint"
    )
    replacement_item = next(
        item
        for item in recommendation.difference_summary
        if item.change.value == "exercise_replacement"
    )
    assert safety.target == str(exercise.id)
    assert "PAIN_SIGNAL_PRESENT" in safety.reason_codes
    assert "PREFERENCE_OVERRIDDEN_BY_SAFETY" in recommendation.reason_codes
    assert replacement_item.target == str(exercise.id)
    assert "PREFERRED_ALTERNATIVE" in replacement_item.reason_codes
    assert signal_id in safety.provenance.safety_signal_ids


def test_claim_rejects_second_coach_until_lease_expires(db: Session) -> None:
    member = _user(db, "lease-member")
    first_coach = _user(db, "first-coach")
    second_coach = _user(db, "second-coach")
    exercise = _exercise(db, "row")
    review = ensure_pending_review(db, _active_plan(db, user=member, exercises=[exercise]))
    clock = Clock()
    service = WorkoutReviewService(db, clock=clock)

    service.claim(review.id, first_coach.id)
    with pytest.raises(ReviewConflict) as error:
        service.claim(review.id, second_coach.id)
    assert error.value.code is WorkoutReviewErrorCode.REVIEW_ALREADY_CLAIMED

    clock.advance(minutes=31)
    claimed = service.claim(review.id, second_coach.id)

    assert claimed.claimed_by_user_id == second_coach.id
    assert claimed.status is WorkoutReviewStatus.CLAIMED


def test_save_rejects_stale_revision_and_preserves_draft(db: Session) -> None:
    member = _user(db, "stale-member")
    coach = _user(db, "stale-coach")
    exercise = _exercise(db, "squat")
    review = ensure_pending_review(db, _active_plan(db, user=member, exercises=[exercise]))
    service = WorkoutReviewService(db, clock=Clock())
    service.claim(review.id, coach.id)
    original = deepcopy(review.draft_payload)
    payload = _draft(review)
    payload.expected_revision -= 1

    with pytest.raises(ReviewConflict) as error:
        service.save_draft(review.id, coach.id, payload)

    assert error.value.code is WorkoutReviewErrorCode.STALE_DRAFT_REVISION
    assert review.draft_payload == original


def test_save_rejects_exercise_outside_source_snapshot(db: Session) -> None:
    member = _user(db, "outside-member")
    coach = _user(db, "outside-coach")
    allowed = _exercise(db, "allowed")
    outside = _exercise(db, "outside")
    review = ensure_pending_review(db, _active_plan(db, user=member, exercises=[allowed]))
    service = WorkoutReviewService(db, clock=Clock())
    service.claim(review.id, coach.id)

    with pytest.raises(DraftValidationError) as error:
        service.save_draft(review.id, coach.id, _draft(review, exercise_id=str(outside.id)))

    assert error.value.problems[0]["code"] == WorkoutReviewErrorCode.EXERCISE_NOT_ALLOWED.value


def test_approval_creates_new_active_version_and_preserves_source(db: Session) -> None:
    member = _user(db, "approval-member")
    coach = _user(db, "approval-coach")
    original_exercise = _exercise(db, "original")
    replacement = _exercise(db, "replacement")
    source = _active_plan(db, user=member, exercises=[original_exercise, replacement])
    review = ensure_pending_review(db, source)
    service = WorkoutReviewService(db, clock=Clock())
    service.claim(review.id, coach.id)
    raw_payload = deepcopy(review.draft_payload)
    assert raw_payload is not None
    raw_payload["expected_revision"] = review.draft_revision
    raw_payload["days"][0]["exercises"][0].update(
        {
            "exercise_id": str(replacement.id),
            "sets": 4,
            "reps_min": 6,
            "reps_max": 10,
            "rir": 4,
            "rest_seconds": 120,
            "notes_en": "Coach-adjusted note",
            "notes_fa": "یادداشت مربی",
        }
    )
    raw_payload["coach_note"] = "Approved with reviewed prescription."
    payload = WorkoutReviewDraftUpdate.model_validate(raw_payload)
    saved = service.save_draft(review.id, coach.id, payload)
    source_payload = deepcopy(saved.source_plan.days[0].exercises[0].exercise_snapshot)

    assert saved.draft_payload is not None
    assert saved.draft_payload["days"][0]["exercises"][0]["rir"] == 4

    approved = service.approve(
        review.id,
        coach.id,
        expected_revision=saved.draft_revision,
    )

    db.refresh(source)
    db.refresh(review)
    assert source.status is WorkoutPlanStatus.SUPERSEDED
    assert source.days[0].exercises[0].exercise_id == original_exercise.id
    assert source.days[0].exercises[0].sets == 3
    assert source.days[0].exercises[0].rir == 2
    assert source.days[0].exercises[0].exercise_snapshot == source_payload
    assert approved.status is WorkoutPlanStatus.ACTIVE
    assert approved.previous_program_id == source.id
    assert approved.days[0].exercises[0].exercise_id == replacement.id
    assert approved.days[0].exercises[0].sets == 4
    assert approved.days[0].exercises[0].reps_min == 6
    assert approved.days[0].exercises[0].reps_max == 10
    assert approved.days[0].exercises[0].rir == 4
    assert approved.days[0].exercises[0].rest_seconds == 120
    assert approved.days[0].exercises[0].notes_en == "Coach-adjusted note"
    assert approved.days[0].exercises[0].notes_fa == "یادداشت مربی"
    assert review.approved_plan_id == approved.id
    assert review.status is WorkoutReviewStatus.APPROVED
    assert review.claimed_by_user_id == coach.id
    assert review.approved_at == Clock().now
    assert review.coach_note == "Approved with reviewed prescription."
    assert approved.difference_summary == {
        "schema_version": "1.0",
        "source_plan_id": str(source.id),
        "review_id": str(review.id),
        "approved_plan_id": str(approved.id),
        "reviewed_by_coach_id": str(coach.id),
        "reviewed_by_coach": True,
        "previous_active_plan_id": str(source.id),
        "coach_diff": [
            {
                "change_type": "exercise_changed",
                "day_number": 1,
                "order_index": 1,
                "generated": str(original_exercise.id),
                "approved": str(replacement.id),
                "generated_exercise_id": str(original_exercise.id),
                "approved_exercise_id": str(replacement.id),
                "provenance": {
                    "source_plan_id": str(source.id),
                    "review_id": str(review.id),
                    "approved_plan_id": str(approved.id),
                    "coach_id": str(coach.id),
                },
            },
            {
                "change_type": "sets_changed",
                "day_number": 1,
                "order_index": 1,
                "generated": 3,
                "approved": 4,
                "generated_exercise_id": str(original_exercise.id),
                "approved_exercise_id": str(replacement.id),
                "provenance": {
                    "source_plan_id": str(source.id),
                    "review_id": str(review.id),
                    "approved_plan_id": str(approved.id),
                    "coach_id": str(coach.id),
                },
            },
            {
                "change_type": "reps_range_changed",
                "day_number": 1,
                "order_index": 1,
                "generated": {"min": 8, "max": 12},
                "approved": {"min": 6, "max": 10},
                "generated_exercise_id": str(original_exercise.id),
                "approved_exercise_id": str(replacement.id),
                "provenance": {
                    "source_plan_id": str(source.id),
                    "review_id": str(review.id),
                    "approved_plan_id": str(approved.id),
                    "coach_id": str(coach.id),
                },
            },
            {
                "change_type": "rir_changed",
                "day_number": 1,
                "order_index": 1,
                "generated": 2,
                "approved": 4,
                "generated_exercise_id": str(original_exercise.id),
                "approved_exercise_id": str(replacement.id),
                "provenance": {
                    "source_plan_id": str(source.id),
                    "review_id": str(review.id),
                    "approved_plan_id": str(approved.id),
                    "coach_id": str(coach.id),
                },
            },
            {
                "change_type": "rest_changed",
                "day_number": 1,
                "order_index": 1,
                "generated": 90,
                "approved": 120,
                "generated_exercise_id": str(original_exercise.id),
                "approved_exercise_id": str(replacement.id),
                "provenance": {
                    "source_plan_id": str(source.id),
                    "review_id": str(review.id),
                    "approved_plan_id": str(approved.id),
                    "coach_id": str(coach.id),
                },
            },
            {
                "change_type": "notes_changed",
                "day_number": 1,
                "order_index": 1,
                "generated": {"en": None, "fa": None},
                "approved": {"en": "Coach-adjusted note", "fa": "یادداشت مربی"},
                "generated_exercise_id": str(original_exercise.id),
                "approved_exercise_id": str(replacement.id),
                "provenance": {
                    "source_plan_id": str(source.id),
                    "review_id": str(review.id),
                    "approved_plan_id": str(approved.id),
                    "coach_id": str(coach.id),
                },
            },
        ],
    }


def test_review_draft_rejects_rir_outside_supported_range() -> None:
    with pytest.raises(ValueError):
        WorkoutReviewExerciseDraft(
            order_index=1,
            exercise_id=uuid4(),
            sets=3,
            reps_min=8,
            reps_max=12,
            rir=6,
            rest_seconds=90,
        )


def test_review_draft_rejects_invalid_rep_and_rest_ranges() -> None:
    with pytest.raises(ValueError):
        WorkoutReviewExerciseDraft(
            order_index=1,
            exercise_id=uuid4(),
            sets=3,
            reps_min=13,
            reps_max=12,
            rir=2,
            rest_seconds=90,
        )
    with pytest.raises(ValueError):
        WorkoutReviewExerciseDraft(
            order_index=1,
            exercise_id=uuid4(),
            sets=3,
            reps_min=8,
            reps_max=12,
            rir=2,
            rest_seconds=601,
        )


def test_approval_activates_pending_plan_without_creating_review_loop(db: Session) -> None:
    member = _user(db, "pending-approval-member")
    coach = _user(db, "pending-approval-coach")
    exercise = _exercise(db, "pending-press")
    source = _active_plan(
        db,
        user=member,
        exercises=[exercise],
        status=WorkoutPlanStatus.PENDING_REVIEW,
    )
    review = ensure_pending_review(db, source)
    assert (
        db.scalars(select(WorkoutCycle).where(WorkoutCycle.workout_plan_id == source.id)).all()
        == []
    )
    service = WorkoutReviewService(db, clock=Clock())
    service.claim(review.id, coach.id)
    raw_payload = deepcopy(review.draft_payload)
    assert raw_payload is not None
    raw_payload["expected_revision"] = review.draft_revision
    raw_payload["coach_note"] = "Pending source stays immutable."
    raw_payload["days"][0]["exercises"][0]["sets"] = 5
    raw_payload["days"][0]["exercises"][0]["rir"] = 3
    saved = service.save_draft(
        review.id,
        coach.id,
        WorkoutReviewDraftUpdate.model_validate(raw_payload),
    )

    approved = service.approve(
        review.id,
        coach.id,
        expected_revision=saved.draft_revision,
    )

    db.refresh(source)
    db.refresh(review)
    assert source.status is WorkoutPlanStatus.SUPERSEDED
    assert source.days[0].exercises[0].sets == 3
    assert source.days[0].exercises[0].rir == 2
    assert approved.status is WorkoutPlanStatus.ACTIVE
    assert approved.days[0].exercises[0].sets == 5
    assert approved.days[0].exercises[0].rir == 3
    assert review.coach_note == "Pending source stays immutable."
    assert approved.activated_at == Clock().now
    cycle = db.scalar(select(WorkoutCycle).where(WorkoutCycle.workout_plan_id == approved.id))
    assert cycle is not None
    assert cycle.user_id == member.id
    assert cycle.duration_weeks == approved.profile_snapshot["plan_duration_weeks"] == 4
    assert review.status is WorkoutReviewStatus.APPROVED
    assert review.approved_plan_id == approved.id
    assert (
        db.query(WorkoutPlanReview).filter(WorkoutPlanReview.source_plan_id == approved.id).count()
        == 0
    )

    repeated = start_cycle(
        db,
        user_id=member.id,
        workout_plan_id=approved.id,
    )
    assert repeated.id == cycle.id
    assert db.scalars(
        select(WorkoutCycle).where(WorkoutCycle.workout_plan_id == approved.id)
    ).all() == [cycle]

    repeated = service.approve(
        review.id,
        coach.id,
        expected_revision=saved.draft_revision,
    )
    assert repeated.id == approved.id
    assert repeated.days[0].exercises[0].sets == approved.days[0].exercises[0].sets
    plans = db.scalars(select(WorkoutPlan)).all()
    assert len(plans) == 2
    assert {plan.id for plan in plans} == {source.id, approved.id}
    assert db.scalars(select(WorkoutCycle)).all() == [cycle]


def test_approval_without_coach_changes_persists_empty_structured_diff(db: Session) -> None:
    member = _user(db, "no-diff-member")
    coach = _user(db, "no-diff-coach")
    source = _active_plan(db, user=member, exercises=[_exercise(db, "no-diff-press")])
    review = ensure_pending_review(db, source)
    service = WorkoutReviewService(db, clock=Clock())
    service.claim(review.id, coach.id)
    saved = service.save_draft(review.id, coach.id, _draft(review))

    approved = service.approve(
        review.id,
        coach.id,
        expected_revision=saved.draft_revision,
    )

    first_summary = deepcopy(approved.difference_summary)
    assert first_summary["coach_diff"] == []
    db.expire(approved)
    reloaded = service.detail(review.id).approved_plan
    assert reloaded is not None
    assert reloaded.difference_summary == first_summary


def test_structured_diff_captures_reorder_add_remove_and_is_deterministic(db: Session) -> None:
    member = _user(db, "diff-structure-member")
    first = _exercise(db, "diff-first")
    second = _exercise(db, "diff-second")
    added = _exercise(db, "diff-added")
    source = _active_plan(
        db,
        user=member,
        exercises=[first, second],
        status=WorkoutPlanStatus.PENDING_REVIEW,
    )
    source.days[0].exercises.append(
        WorkoutPlanExercise(
            exercise_id=second.id,
            order_index=2,
            sets=3,
            reps_min=8,
            reps_max=12,
            rest_seconds=90,
            rir=2,
            estimated_minutes=5,
            exercise_snapshot=_candidate_snapshot(second),
        )
    )
    db.flush()

    reordered_only = _active_plan(
        db,
        user=member,
        exercises=[second],
        status=WorkoutPlanStatus.SUPERSEDED,
    )
    reordered_only.days[0].exercises.append(
        WorkoutPlanExercise(
            exercise_id=first.id,
            order_index=2,
            sets=3,
            reps_min=8,
            reps_max=12,
            rest_seconds=90,
            rir=2,
            estimated_minutes=5,
            exercise_snapshot=_candidate_snapshot(first),
        )
    )
    db.flush()

    reordered = _active_plan(
        db,
        user=member,
        exercises=[second],
        status=WorkoutPlanStatus.SUPERSEDED,
    )
    reordered.days[0].exercises.append(
        WorkoutPlanExercise(
            exercise_id=first.id,
            order_index=2,
            sets=3,
            reps_min=8,
            reps_max=12,
            rest_seconds=90,
            rir=2,
            estimated_minutes=5,
            exercise_snapshot=_candidate_snapshot(first),
        )
    )
    reordered.days[0].exercises.append(
        WorkoutPlanExercise(
            exercise_id=added.id,
            order_index=3,
            sets=3,
            reps_min=8,
            reps_max=12,
            rest_seconds=90,
            rir=2,
            estimated_minutes=5,
            exercise_snapshot=_candidate_snapshot(added),
        )
    )
    db.flush()

    removed = _active_plan(db, user=member, exercises=[first], status=WorkoutPlanStatus.SUPERSEDED)
    provenance = {"source_plan_id": str(source.id), "review_id": str(uuid4())}
    diff = build_coach_diff(source, reordered, provenance=provenance)
    assert {item["change_type"] for item in diff} == {
        "exercise_added",
        "exercise_changed",
        "exercise_reordered",
    }
    assert any(item["approved_exercise_id"] == str(added.id) for item in diff)
    reordered_only_diff = build_coach_diff(source, reordered_only, provenance=provenance)
    assert {item["change_type"] for item in reordered_only_diff} == {"exercise_reordered"}
    assert build_coach_diff(source, reordered, provenance=provenance) == diff
    removed_diff = build_coach_diff(source, removed, provenance=provenance)
    assert any(item["change_type"] == "exercise_removed" for item in removed_diff)


def test_approval_supersedes_previous_active_plan_only_at_approval(db: Session) -> None:
    member = _user(db, "approval-transition-member")
    coach = _user(db, "approval-transition-coach")
    previous_exercise = _exercise(db, "previous-press")
    pending_exercise = _exercise(db, "pending-press")
    previous = _active_plan(db, user=member, exercises=[previous_exercise])
    source = _active_plan(
        db,
        user=member,
        exercises=[pending_exercise],
        status=WorkoutPlanStatus.PENDING_REVIEW,
    )
    review = ensure_pending_review(db, source)
    service = WorkoutReviewService(db, clock=Clock())
    service.claim(review.id, coach.id)
    saved = service.save_draft(review.id, coach.id, _draft(review))

    assert previous.status is WorkoutPlanStatus.ACTIVE

    approved = service.approve(
        review.id,
        coach.id,
        expected_revision=saved.draft_revision,
    )

    db.refresh(previous)
    assert previous.status is WorkoutPlanStatus.SUPERSEDED
    assert previous.superseded_at == Clock().now
    assert approved.status is WorkoutPlanStatus.ACTIVE
    assert approved.activated_at == Clock().now
    assert approved.difference_summary["previous_active_plan_id"] == str(previous.id)
    assert (
        db.query(WorkoutPlan)
        .filter(
            WorkoutPlan.user_id == member.id,
            WorkoutPlan.status == WorkoutPlanStatus.ACTIVE,
        )
        .count()
        == 1
    )
    cycles = db.scalars(select(WorkoutCycle).where(WorkoutCycle.user_id == member.id)).all()
    assert len(cycles) == 1
    assert cycles[0].workout_plan_id == approved.id


def test_approval_cannot_replace_a_newer_active_plan(db: Session) -> None:
    member = _user(db, "newer-member")
    coach = _user(db, "newer-coach")
    exercise = _exercise(db, "deadlift")
    source = _active_plan(db, user=member, exercises=[exercise])
    review = ensure_pending_review(db, source)
    service = WorkoutReviewService(db, clock=Clock())
    service.claim(review.id, coach.id)
    source.status = WorkoutPlanStatus.SUPERSEDED
    newer = _active_plan(db, user=member, exercises=[exercise])
    db.flush()

    with pytest.raises(ReviewConflict) as error:
        service.approve(review.id, coach.id, expected_revision=review.draft_revision)

    assert error.value.code is WorkoutReviewErrorCode.REVIEW_SUPERSEDED
    assert newer.status is WorkoutPlanStatus.ACTIVE
