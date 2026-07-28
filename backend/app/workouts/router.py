from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth.cookies import require_trusted_origin
from app.auth.models import User
from app.database.session import get_db
from app.exercises.dependencies import require_completed_profile
from app.exercises.schemas import ExerciseSummary
from app.workouts.dependencies import WorkoutGenerationServiceDependency
from app.workouts.models import WorkoutPlan
from app.workouts.repository import get_plan_for_user
from app.workouts.schemas import (
    WorkoutDayResponse,
    WorkoutPlanExerciseResponse,
    WorkoutPlanGenerateResponse,
    WorkoutPlanResponse,
)
from app.workouts.service import (
    GenerationInProgressError,
    NoEligibleExercisesError,
    WorkoutGenerationFailedError,
    WorkoutGenerationService,
)

router = APIRouter(prefix="/api/v1/workout-plans", tags=["workout-plans"])
DatabaseSession = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[User, Depends(require_completed_profile)]


@router.get("/active", response_model=WorkoutPlanResponse)
def read_active_plan(
    service: WorkoutGenerationServiceDependency,
    user: CurrentUser,
) -> WorkoutPlanResponse:
    active = service.get_active(user.id)
    if active is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No active workout plan")
    return to_plan_response(active.plan, is_stale=active.is_stale)


@router.post(
    "/generate",
    response_model=WorkoutPlanGenerateResponse,
    dependencies=[Depends(require_trusted_origin)],
)
async def generate_plan(
    service: WorkoutGenerationServiceDependency,
    user: CurrentUser,
) -> WorkoutPlanGenerateResponse:
    try:
        result = await service.generate(user.id)
    except GenerationInProgressError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Workout plan generation is already in progress",
        ) from None
    except NoEligibleExercisesError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Not enough eligible exercises for a workout plan",
        ) from None
    except WorkoutGenerationFailedError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Workout plan generation is temporarily unavailable",
        ) from None
    return WorkoutPlanGenerateResponse(plan=to_plan_response(result.plan), reused=result.reused)


@router.get("/{plan_id}", response_model=WorkoutPlanResponse)
def read_plan(
    plan_id: UUID,
    db: DatabaseSession,
    user: CurrentUser,
) -> WorkoutPlanResponse:
    plan = get_plan_for_user(db, plan_id=plan_id, user_id=user.id)
    if plan is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workout plan not found")
    return to_plan_response(plan)


def to_plan_response(plan: WorkoutPlan, *, is_stale: bool = False) -> WorkoutPlanResponse:
    return WorkoutPlanResponse(
        id=plan.id,
        status=plan.status,
        created_at=plan.created_at,
        activated_at=plan.activated_at,
        plan_duration_weeks=WorkoutGenerationService.plan_duration_weeks(plan),
        is_stale=is_stale,
        days=[
            WorkoutDayResponse(
                day_number=day.day_number,
                title_en=day.title_en,
                title_fa=day.title_fa,
                estimated_duration_minutes=day.estimated_duration_minutes,
                exercises=[
                    WorkoutPlanExerciseResponse(
                        order_index=item.order_index,
                        sets=item.sets,
                        reps_min=item.reps_min,
                        reps_max=item.reps_max,
                        rest_seconds=item.rest_seconds,
                        rir=item.rir,
                        estimated_minutes=item.estimated_minutes,
                        notes_en=item.notes_en,
                        notes_fa=item.notes_fa,
                        exercise=ExerciseSummary(
                            id=item.exercise.id,
                            slug=item.exercise.slug,
                            name_en=item.exercise.name_en,
                            name_fa=item.exercise.name_fa,
                            body_region=item.exercise.body_region,
                            primary_muscle=item.exercise.primary_muscle,
                            secondary_muscles=[
                                secondary.muscle for secondary in item.exercise.secondary_muscles
                            ],
                            equipment=[
                                equipment.equipment for equipment in item.exercise.equipment_items
                            ],
                            difficulty=item.exercise.difficulty,
                            media_path=item.exercise.media_path,
                            media_type=item.exercise.media_type,
                        ),
                    )
                    for item in day.exercises
                ],
            )
            for day in plan.days
        ],
    )
