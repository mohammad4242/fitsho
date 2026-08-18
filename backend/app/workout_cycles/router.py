from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.auth.models import User
from app.database.session import get_db
from app.workout_cycles.schemas import WorkoutCycleCurrentResponse
from app.workout_cycles.service import get_current_active_cycle_for_user

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
    )
