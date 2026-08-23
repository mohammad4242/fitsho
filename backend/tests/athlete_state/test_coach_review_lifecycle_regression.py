from __future__ import annotations

import asyncio
from copy import deepcopy
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.models import User
from app.workout_cycles.models import WorkoutCycle
from app.workout_reviews.enums import WorkoutReviewErrorCode, WorkoutReviewStatus
from app.workout_reviews.models import WorkoutPlanReview
from app.workout_reviews.schemas import WorkoutReviewDraftUpdate
from app.workout_reviews.service import ReviewConflict, WorkoutReviewService
from app.workouts.ai_coach import AiCoachProgramCandidate
from app.workouts.ai_coach_provider import AiCoachRecommendation
from app.workouts.enums import WorkoutPlanStatus
from app.workouts.models import WorkoutPlan
from app.workouts.router import to_plan_response
from tests.athlete_state.test_cycle_transitions import _run_transition
from tests.workouts.test_service import (
    _ai_template,
    _FailingAiCoachProvider,
    _seed_candidates,
    _user_with_profile,
)
from tests.workouts.test_service import _service as generation_service


def _coach(db: Session, prefix: str) -> User:
    coach = User(email=f"{prefix}-{uuid4()}@example.com", password_hash="hash")
    db.add(coach)
    db.flush()
    return coach


def _review_for(db: Session, source: WorkoutPlan) -> WorkoutPlanReview:
    review = db.scalar(
        select(WorkoutPlanReview).where(WorkoutPlanReview.source_plan_id == source.id)
    )
    assert review is not None
    return review


def _approve_without_edits(
    db: Session,
    review: WorkoutPlanReview,
    coach: User,
) -> WorkoutPlan:
    service = WorkoutReviewService(db)
    claimed = service.claim(review.id, coach.id)
    approved = service.approve(
        review.id,
        coach.id,
        expected_revision=claimed.draft_revision,
    )
    return approved


def test_first_generated_plan_requires_review_before_activation_and_cycle_start(
    db: Session,
) -> None:
    member = _user_with_profile(db)
    _seed_candidates(db)

    generated = asyncio.run(generation_service(db).generate(member.id))
    source = generated.plan
    review = _review_for(db, source)

    assert source.status is WorkoutPlanStatus.PENDING_REVIEW
    assert (
        db.scalar(
            select(WorkoutPlan).where(
                WorkoutPlan.user_id == member.id,
                WorkoutPlan.status == WorkoutPlanStatus.ACTIVE,
            )
        )
        is None
    )
    assert (
        db.scalars(select(WorkoutCycle).where(WorkoutCycle.workout_plan_id == source.id)).all()
        == []
    )
    assert review.status is WorkoutReviewStatus.PENDING
    approved = _approve_without_edits(db, review, _coach(db, "first-approval"))

    active_plans = db.scalars(
        select(WorkoutPlan).where(
            WorkoutPlan.user_id == member.id,
            WorkoutPlan.status == WorkoutPlanStatus.ACTIVE,
        )
    ).all()
    cycles = db.scalars(
        select(WorkoutCycle).where(
            WorkoutCycle.user_id == member.id,
            WorkoutCycle.workout_plan_id == approved.id,
        )
    ).all()
    db.refresh(source)
    db.refresh(review)

    assert source.status is WorkoutPlanStatus.SUPERSEDED
    assert approved.status is WorkoutPlanStatus.ACTIVE
    assert active_plans == [approved]
    assert len(cycles) == 1
    assert cycles[0].duration_weeks == approved.profile_snapshot["program_duration_weeks"] == 4
    assert review.status is WorkoutReviewStatus.APPROVED
    assert review.approved_plan_id == approved.id
    assert (
        db.scalars(
            select(WorkoutPlanReview).where(WorkoutPlanReview.source_plan_id == approved.id)
        ).all()
        == []
    )

    active_response = to_plan_response(approved, db=db)
    source_response = to_plan_response(source, db=db)
    assert active_response.status is WorkoutPlanStatus.ACTIVE
    assert active_response.coach_review.state == "coach_approved"
    assert source_response.coach_review.state == "initial_generated"


def test_replacement_approval_preserves_edits_provenance_and_is_idempotent(
    db: Session,
) -> None:
    _generation, materialized, _state, _decision, generated, provider = _run_transition(
        db, "intermediate_hypertrophy"
    )
    source = generated.plan
    previous = db.get(WorkoutPlan, materialized.cycles[-1].workout_plan_id)
    assert previous is not None
    assert previous.status is WorkoutPlanStatus.ACTIVE
    assert source.status is WorkoutPlanStatus.PENDING_REVIEW
    assert source.previous_program_id == previous.id
    assert provider.calls == 0

    review = _review_for(db, source)
    coach = _coach(db, "replacement-approval")
    review_service = WorkoutReviewService(db)
    claimed = review_service.claim(review.id, coach.id)
    assert claimed.draft_payload is not None

    original_item = source.days[0].exercises[0]
    source_values = {
        "exercise_id": original_item.exercise_id,
        "sets": original_item.sets,
        "reps_min": original_item.reps_min,
        "reps_max": original_item.reps_max,
        "rir": original_item.rir,
        "rest_seconds": original_item.rest_seconds,
        "notes_en": original_item.notes_en,
        "notes_fa": original_item.notes_fa,
    }
    snapshot_ids = [UUID(value) for value in source.exercise_catalog_snapshot["exercises"]]
    replacement_id = next(
        exercise_id for exercise_id in snapshot_ids if exercise_id != original_item.exercise_id
    )
    draft_payload = deepcopy(claimed.draft_payload)
    draft_payload["expected_revision"] = claimed.draft_revision
    draft_payload["coach_note"] = "Reviewed adaptive prescription."
    draft_payload["days"][0]["exercises"][0].update(
        {
            "exercise_id": str(replacement_id),
            "sets": 4,
            "reps_min": 6,
            "reps_max": 10,
            "rir": 3,
            "rest_seconds": 150,
            "notes_en": "Use controlled tempo.",
            "notes_fa": "با ریتم کنترل‌شده اجرا شود.",
        }
    )
    saved = review_service.save_draft(
        review.id,
        coach.id,
        WorkoutReviewDraftUpdate.model_validate(draft_payload),
    )

    db.refresh(previous)
    db.refresh(source)
    assert previous.status is WorkoutPlanStatus.ACTIVE
    assert source.status is WorkoutPlanStatus.PENDING_REVIEW
    assert (
        db.scalars(select(WorkoutCycle).where(WorkoutCycle.workout_plan_id == source.id)).all()
        == []
    )

    with pytest.raises(ReviewConflict) as conflict:
        review_service.approve(
            review.id,
            coach.id,
            expected_revision=saved.draft_revision - 1,
        )
    assert conflict.value.code is WorkoutReviewErrorCode.STALE_DRAFT_REVISION

    approved = review_service.approve(
        review.id,
        coach.id,
        expected_revision=saved.draft_revision,
    )
    approved_again = review_service.approve(
        review.id,
        coach.id,
        expected_revision=saved.draft_revision,
    )

    db.refresh(source)
    db.refresh(previous)
    db.refresh(review)
    approved_item = approved.days[0].exercises[0]
    active_plans = db.scalars(
        select(WorkoutPlan).where(
            WorkoutPlan.user_id == materialized.user.id,
            WorkoutPlan.status == WorkoutPlanStatus.ACTIVE,
        )
    ).all()
    approved_cycles = db.scalars(
        select(WorkoutCycle).where(
            WorkoutCycle.user_id == materialized.user.id,
            WorkoutCycle.workout_plan_id == approved.id,
        )
    ).all()
    diff = approved.difference_summary

    assert approved_again.id == approved.id
    assert (
        len(
            db.scalars(
                select(WorkoutPlan).where(
                    WorkoutPlan.user_id == materialized.user.id,
                    WorkoutPlan.previous_program_id == source.id,
                )
            ).all()
        )
        == 1
    )
    assert len(approved_cycles) == 1
    assert active_plans == [approved]
    assert previous.status is WorkoutPlanStatus.SUPERSEDED
    assert source.status is WorkoutPlanStatus.SUPERSEDED
    assert source_values == {
        "exercise_id": source.days[0].exercises[0].exercise_id,
        "sets": source.days[0].exercises[0].sets,
        "reps_min": source.days[0].exercises[0].reps_min,
        "reps_max": source.days[0].exercises[0].reps_max,
        "rir": source.days[0].exercises[0].rir,
        "rest_seconds": source.days[0].exercises[0].rest_seconds,
        "notes_en": source.days[0].exercises[0].notes_en,
        "notes_fa": source.days[0].exercises[0].notes_fa,
    }
    assert approved_item.exercise_id == replacement_id
    assert approved_item.sets == 4
    assert approved_item.reps_min == 6
    assert approved_item.reps_max == 10
    assert approved_item.rir == 3
    assert approved_item.rest_seconds == 150
    assert approved_item.notes_en == "Use controlled tempo."
    assert approved_item.notes_fa == "با ریتم کنترل‌شده اجرا شود."
    assert review.status is WorkoutReviewStatus.APPROVED
    assert review.approved_plan_id == approved.id
    assert approved.previous_program_id == source.id
    assert diff["source_plan_id"] == str(source.id)
    assert diff["review_id"] == str(review.id)
    assert diff["approved_plan_id"] == str(approved.id)
    assert diff["previous_active_plan_id"] == str(previous.id)
    assert {item["change_type"] for item in diff["coach_diff"]} >= {
        "exercise_changed",
        "sets_changed",
        "reps_range_changed",
        "rir_changed",
        "notes_changed",
    }
    assert all(
        item["provenance"]
        == {
            "source_plan_id": str(source.id),
            "review_id": str(review.id),
            "approved_plan_id": str(approved.id),
            "coach_id": str(coach.id),
        }
        for item in diff["coach_diff"]
    )
    assert (
        db.scalars(
            select(WorkoutPlanReview).where(WorkoutPlanReview.source_plan_id == approved.id)
        ).all()
        == []
    )
    assert (
        db.scalars(
            select(WorkoutPlanReview).where(
                WorkoutPlanReview.source_plan_id == source.id,
                WorkoutPlanReview.status == WorkoutReviewStatus.PENDING,
            )
        ).all()
        == []
    )


def test_ai_coach_generation_also_stops_at_human_review_gate(
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    member = _user_with_profile(db)
    exercises = _seed_candidates(db)
    templates = (
        _ai_template("candidate-a", (exercises[0].id, exercises[1].id)),
        _ai_template("candidate-b", (exercises[1].id, exercises[0].id)),
    )
    monkeypatch.setattr(
        "app.workouts.service.select_ai_coach_candidates",
        lambda **_kwargs: tuple(
            AiCoachProgramCandidate(template=template, score=100) for template in templates
        ),
    )
    provider = _FailingAiCoachProvider(
        AiCoachRecommendation(
            selected_candidate_id="candidate-a",
            program_explanation_fa="این گزینه برای شرایط فعلی مناسب است.",
            day_explanations=(),
            model_id="test-ai-model",
            provider_request_id="test-request",
            input_tokens=10,
            output_tokens=20,
        )
    )

    generated = asyncio.run(
        generation_service(
            db,
            ai_coach_provider=provider,
            generation_method="ai",
            deterministic_fallback_enabled=False,
        ).generate(member.id)
    )
    review = _review_for(db, generated.plan)

    assert provider.calls == 1
    assert generated.plan.generation_method == "ai"
    assert generated.plan.status is WorkoutPlanStatus.PENDING_REVIEW
    assert review.status is WorkoutReviewStatus.PENDING
    assert (
        db.scalars(
            select(WorkoutCycle).where(WorkoutCycle.workout_plan_id == generated.plan.id)
        ).all()
        == []
    )
