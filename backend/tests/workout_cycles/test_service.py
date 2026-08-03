from uuid import UUID

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.models import User
from app.workout_cycles.enums import WorkoutCycleStatus
from app.workout_cycles.models import WorkoutCycle
from app.workout_cycles.schemas import CompletionFeedbackInput
from app.workout_cycles.service import (
    WorkoutCycleAlreadyCompletedError,
    WorkoutCycleNotFoundError,
    complete_cycle,
    get_cycle_for_user,
    start_cycle,
)
from app.workouts.enums import WorkoutPlanStatus
from app.workouts.models import WorkoutPlan


def make_user(db: Session, email: str) -> User:
    user = User(email=email, password_hash="hash")
    db.add(user)
    db.flush()
    return user


def make_plan(db: Session, user_id: UUID, *, duration_weeks: int = 4) -> WorkoutPlan:
    plan = WorkoutPlan(
        user_id=user_id,
        status=WorkoutPlanStatus.ACTIVE,
        generation_signature="a" * 64,
        profile_snapshot={"plan_duration_weeks": duration_weeks},
        provider="fake",
        model_id="fake-model",
        prompt_version="v1",
        generation_policy_version="v1",
        candidate_set_hash="b" * 64,
        generation_method="deterministic",
    )
    db.add(plan)
    db.flush()
    return plan


@pytest.mark.parametrize("duration_weeks", [4, 6, 8])
def test_start_cycle_accepts_supported_plan_durations(
    db: Session, duration_weeks: int
) -> None:
    user = make_user(db, f"duration-{duration_weeks}@example.com")
    plan = make_plan(db, user.id, duration_weeks=duration_weeks)

    cycle = start_cycle(db, user_id=user.id, workout_plan_id=plan.id)

    assert cycle.status is WorkoutCycleStatus.ACTIVE
    assert cycle.duration_weeks == duration_weeks
    assert cycle.user_id == user.id
    assert cycle.workout_plan_id == plan.id


def test_start_cycle_is_idempotent_for_one_plan(db: Session) -> None:
    user = make_user(db, "idempotent-cycle@example.com")
    plan = make_plan(db, user.id)

    first = start_cycle(db, user_id=user.id, workout_plan_id=plan.id)
    second = start_cycle(db, user_id=user.id, workout_plan_id=plan.id)

    assert second.id == first.id
    assert db.query(WorkoutCycle).filter_by(workout_plan_id=plan.id).count() == 1


def test_start_cycle_rejects_unsupported_plan_duration(db: Session) -> None:
    user = make_user(db, "unsupported-duration@example.com")
    plan = make_plan(db, user.id, duration_weeks=5)

    with pytest.raises(ValueError, match="4, 6, or 8"):
        start_cycle(db, user_id=user.id, workout_plan_id=plan.id)


def test_cycle_cannot_be_created_twice_at_database_level(db: Session) -> None:
    user = make_user(db, "unique-cycle@example.com")
    plan = make_plan(db, user.id)
    db.add_all(
        [
            WorkoutCycle(user_id=user.id, workout_plan_id=plan.id, duration_weeks=4),
            WorkoutCycle(user_id=user.id, workout_plan_id=plan.id, duration_weeks=4),
        ]
    )

    with pytest.raises(IntegrityError, match="uq_workout_cycles_workout_plan_id"):
        db.flush()


def test_other_user_cannot_read_or_complete_cycle(db: Session) -> None:
    owner = make_user(db, "cycle-owner@example.com")
    other = make_user(db, "cycle-other@example.com")
    plan = make_plan(db, owner.id)
    cycle = start_cycle(db, user_id=owner.id, workout_plan_id=plan.id)

    assert get_cycle_for_user(db, cycle_id=cycle.id, user_id=other.id) is None
    with pytest.raises(WorkoutCycleNotFoundError):
        complete_cycle(db, cycle_id=cycle.id, user_id=other.id)


def test_complete_cycle_allows_feedback_to_be_omitted(db: Session) -> None:
    user = make_user(db, "optional-feedback@example.com")
    plan = make_plan(db, user.id, duration_weeks=6)
    cycle = start_cycle(db, user_id=user.id, workout_plan_id=plan.id)

    completed = complete_cycle(db, cycle_id=cycle.id, user_id=user.id)

    assert completed.status is WorkoutCycleStatus.COMPLETED
    assert completed.completed_at is not None
    assert completed.completion_feedback is None


def test_complete_cycle_stores_structured_optional_feedback(db: Session) -> None:
    user = make_user(db, "cycle-feedback@example.com")
    plan = make_plan(db, user.id, duration_weeks=8)
    cycle = start_cycle(db, user_id=user.id, workout_plan_id=plan.id)
    feedback = CompletionFeedbackInput(
        adherence_percent=82,
        performance_changes="Added reps on pressing movements.",
        pain_or_limitation_feedback="Mild discomfort during deep knee flexion.",
        measurements={"weight_kg": 81.2, "waist_cm": 84},
    )

    completed = complete_cycle(
        db,
        cycle_id=cycle.id,
        user_id=user.id,
        feedback=feedback,
    )

    assert completed.completion_feedback is not None
    assert completed.completion_feedback.adherence_percent == 82
    assert completed.completion_feedback.measurements == {
        "weight_kg": 81.2,
        "waist_cm": 84,
    }
    assert completed.completion_feedback.submitted_at is not None


def test_completed_cycle_cannot_be_completed_again(db: Session) -> None:
    user = make_user(db, "complete-once@example.com")
    plan = make_plan(db, user.id)
    cycle = start_cycle(db, user_id=user.id, workout_plan_id=plan.id)
    complete_cycle(db, cycle_id=cycle.id, user_id=user.id)

    with pytest.raises(WorkoutCycleAlreadyCompletedError):
        complete_cycle(db, cycle_id=cycle.id, user_id=user.id)
