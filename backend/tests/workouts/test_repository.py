from uuid import UUID

from sqlalchemy.orm import Session

from app.auth.models import User
from app.workouts.enums import WorkoutGenerationStatus, WorkoutPlanStatus
from app.workouts.models import WorkoutPlan
from app.workouts.repository import activate_plan, create_generation, get_active_plan


def make_user(db: Session) -> User:
    user = User(email="repository@example.com", password_hash="hash")
    db.add(user)
    db.flush()
    return user


def new_plan(user_id: UUID, signature: str) -> WorkoutPlan:
    return WorkoutPlan(
        user_id=user_id,
        status=WorkoutPlanStatus.SUPERSEDED,
        generation_signature=signature,
        profile_snapshot={"plan_duration_weeks": 4},
        provider="fake",
        model_id="fake-model",
        prompt_version="v1",
        generation_policy_version="v1",
        candidate_set_hash="b" * 64,
        generation_method="ai",
    )


def test_activate_plan_supersedes_previous_active_plan(db: Session) -> None:
    user = make_user(db)
    previous = new_plan(user.id, "a" * 64)
    previous.status = WorkoutPlanStatus.ACTIVE
    db.add(previous)
    db.flush()
    generation = create_generation(
        db,
        user_id=user.id,
        provider="fake",
        model_id="fake-model",
        candidate_count=1,
    )
    replacement = new_plan(user.id, "c" * 64)

    activate_plan(db, replacement, generation)

    assert previous.status is WorkoutPlanStatus.SUPERSEDED
    assert replacement.status is WorkoutPlanStatus.ACTIVE
    assert generation.status is WorkoutGenerationStatus.SUCCEEDED
    assert get_active_plan(db, user.id) is replacement
