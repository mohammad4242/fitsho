from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.workouts.enums import WorkoutGenerationStatus, WorkoutPlanStatus
from app.workouts.models import WorkoutDay, WorkoutPlan, WorkoutPlanExercise, WorkoutPlanGeneration


def get_active_plan(db: Session, user_id: UUID) -> WorkoutPlan | None:
    return db.scalar(
        select(WorkoutPlan)
        .where(
            WorkoutPlan.user_id == user_id,
            WorkoutPlan.status == WorkoutPlanStatus.ACTIVE,
        )
        .options(
            selectinload(WorkoutPlan.days)
            .selectinload(WorkoutDay.exercises)
            .selectinload(WorkoutPlanExercise.exercise)
        )
    )


def create_generation(
    db: Session,
    *,
    user_id: UUID,
    provider: str,
    model_id: str,
    candidate_count: int,
) -> WorkoutPlanGeneration:
    generation = WorkoutPlanGeneration(
        user_id=user_id,
        provider=provider,
        model_id=model_id,
        status=WorkoutGenerationStatus.GENERATING,
        candidate_count=candidate_count,
    )
    db.add(generation)
    db.flush()
    return generation


def get_latest_completed_generation_at(db: Session, user_id: UUID) -> datetime | None:
    return db.scalar(
        select(WorkoutPlanGeneration.completed_at)
        .where(
            WorkoutPlanGeneration.user_id == user_id,
            WorkoutPlanGeneration.completed_at.is_not(None),
        )
        .order_by(WorkoutPlanGeneration.completed_at.desc())
        .limit(1)
    )


def fail_generation(
    db: Session,
    generation: WorkoutPlanGeneration,
    *,
    error_code: str,
    safe_error_message: str,
) -> None:
    generation.status = WorkoutGenerationStatus.FAILED
    generation.error_code = error_code
    generation.safe_error_message = safe_error_message
    generation.completed_at = datetime.now(UTC)
    db.flush()


def activate_plan(
    db: Session,
    plan: WorkoutPlan,
    generation: WorkoutPlanGeneration,
) -> WorkoutPlan:
    db.add(plan)
    db.flush()

    previous = db.scalar(
        select(WorkoutPlan)
        .where(
            WorkoutPlan.user_id == plan.user_id,
            WorkoutPlan.status == WorkoutPlanStatus.ACTIVE,
        )
        .with_for_update()
    )
    if previous is not None:
        previous.status = WorkoutPlanStatus.SUPERSEDED
        previous.superseded_at = datetime.now(UTC)
        db.flush()

    plan.status = WorkoutPlanStatus.ACTIVE
    plan.activated_at = datetime.now(UTC)
    generation.workout_plan = plan
    generation.status = WorkoutGenerationStatus.SUCCEEDED
    generation.completed_at = datetime.now(UTC)
    db.flush()
    return plan


def get_plan_for_user(
    db: Session,
    *,
    plan_id: UUID,
    user_id: UUID,
) -> WorkoutPlan | None:
    return db.scalar(
        select(WorkoutPlan)
        .where(WorkoutPlan.id == plan_id, WorkoutPlan.user_id == user_id)
        .options(
            selectinload(WorkoutPlan.days)
            .selectinload(WorkoutDay.exercises)
            .selectinload(WorkoutPlanExercise.exercise)
        )
    )
