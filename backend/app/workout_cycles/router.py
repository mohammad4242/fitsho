from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth.cookies import require_trusted_origin
from app.auth.dependencies import get_current_user
from app.auth.models import User
from app.database.session import get_db
from app.workout_cycles.schemas import (
    WorkoutCycleCurrentResponse,
    WorkoutExerciseReplacementCreateRequest,
    WorkoutExerciseReplacementResponse,
)
from app.workout_cycles.service import (
    WorkoutExerciseReplacementAlternativeNotAllowedError,
    WorkoutExerciseReplacementNoActiveCycleError,
    WorkoutExerciseReplacementPlanExerciseNotFoundError,
    WorkoutExerciseReplacementSelfError,
    calculate_current_week,
    get_current_active_cycle_for_user,
    record_exercise_replacement,
)

router = APIRouter(prefix="/api/v1/workout-cycles", tags=["workout-cycles"])
DatabaseSession = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_user)]


@router.get("/current", response_model=WorkoutCycleCurrentResponse)
def read_current_cycle(
    db: DatabaseSession,
    user: CurrentUser,
) -> WorkoutCycleCurrentResponse:
    cycle = get_current_active_cycle_for_user(db, user_id=user.id)
    if cycle is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active workout cycle",
        )
    return WorkoutCycleCurrentResponse(
        cycle_id=cycle.id,
        workout_plan_id=cycle.workout_plan_id,
        started_at=cycle.started_at,
        duration_weeks=cycle.duration_weeks,
        status=cycle.status,
        current_week=calculate_current_week(cycle.started_at, cycle.duration_weeks),
    )


@router.post(
    "/current/replacements",
    response_model=WorkoutExerciseReplacementResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_trusted_origin)],
)
def create_current_cycle_replacement(
    payload: WorkoutExerciseReplacementCreateRequest,
    db: DatabaseSession,
    user: CurrentUser,
) -> WorkoutExerciseReplacementResponse:
    try:
        replacement = record_exercise_replacement(
            db,
            user_id=user.id,
            workout_plan_exercise_id=payload.workout_plan_exercise_id,
            replacement_exercise_id=payload.replacement_exercise_id,
            reason=payload.reason,
            scope=payload.scope,
        )
    except WorkoutExerciseReplacementNoActiveCycleError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active workout cycle",
        ) from None
    except WorkoutExerciseReplacementPlanExerciseNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workout plan exercise not found in current cycle",
        ) from None
    except WorkoutExerciseReplacementSelfError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Replacement exercise must differ from original exercise",
        ) from None
    except WorkoutExerciseReplacementAlternativeNotAllowedError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Replacement exercise is not an allowed alternative",
        ) from None
    return WorkoutExerciseReplacementResponse.model_validate(replacement)
