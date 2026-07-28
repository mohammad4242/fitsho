from uuid import UUID

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.models import User
from app.workouts.enums import WorkoutGenerationStatus, WorkoutPlanStatus
from app.workouts.models import WorkoutPlan, WorkoutPlanGeneration


def make_user(db: Session, email: str) -> User:
    user = User(email=email, password_hash="hash")
    db.add(user)
    db.flush()
    return user


def active_plan(user_id: UUID) -> WorkoutPlan:
    return WorkoutPlan(
        user_id=user_id,
        status=WorkoutPlanStatus.ACTIVE,
        generation_signature="a" * 64,
        profile_snapshot={"plan_duration_weeks": 4},
        provider="fake",
        model_id="fake-model",
        prompt_version="v1",
        generation_policy_version="v1",
        candidate_set_hash="b" * 64,
        generation_method="ai",
    )


def test_user_cannot_have_two_active_workout_plans(db: Session) -> None:
    user = make_user(db, "active-plans@example.com")
    db.add_all([active_plan(user.id), active_plan(user.id)])

    with pytest.raises(IntegrityError, match="uq_workout_plans_one_active_per_user"):
        db.flush()


def test_user_cannot_have_two_generations_in_progress(db: Session) -> None:
    user = make_user(db, "generating-plans@example.com")
    db.add_all(
        [
            WorkoutPlanGeneration(
                user_id=user.id,
                provider="fake",
                model_id="fake-model",
                status=WorkoutGenerationStatus.GENERATING,
                candidate_count=1,
            ),
            WorkoutPlanGeneration(
                user_id=user.id,
                provider="fake",
                model_id="fake-model",
                status=WorkoutGenerationStatus.GENERATING,
                candidate_count=1,
            ),
        ]
    )

    with pytest.raises(IntegrityError, match="uq_workout_plan_generations_one_running_per_user"):
        db.flush()
