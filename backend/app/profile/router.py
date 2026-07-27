from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth.cookies import require_trusted_origin
from app.auth.dependencies import get_current_user
from app.auth.models import User
from app.database.session import get_db
from app.profile.exceptions import (
    InvalidWorkoutSetupError,
    ProfileAlreadyExistsError,
    ProfileInvariantError,
    ProfileNotFoundError,
)
from app.profile.schemas import ProfileCreate, ProfileResponse, ProfileUpdate
from app.profile.service import (
    ProfileSnapshot,
    create_profile,
    get_profile,
    update_profile,
)

router = APIRouter(prefix="/api/v1/profile", tags=["profile"])

DatabaseSession = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_user)]


def to_response(snapshot: ProfileSnapshot) -> ProfileResponse:
    profile = snapshot.profile
    measurement = snapshot.measurement
    return ProfileResponse(
        user_id=profile.user_id,
        display_name=profile.display_name,
        birth_date=profile.birth_date,
        sex=profile.sex,
        height_cm=profile.height_cm,
        current_weight_kg=float(measurement.weight_kg),
        weight_measured_at=measurement.measured_at,
        fitness_goal=profile.fitness_goal,
        experience_level=profile.experience_level,
        training_days_per_week=profile.training_days_per_week,
        training_location=profile.training_location,
        home_training_setup=profile.home_training_setup,
        session_duration_minutes=profile.session_duration_minutes,
        physical_limitations=profile.physical_limitations,
        created_at=profile.created_at,
        updated_at=profile.updated_at,
    )


@router.post(
    "",
    response_model=ProfileResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_trusted_origin)],
)
def create(
    payload: ProfileCreate,
    db: DatabaseSession,
    user: CurrentUser,
) -> ProfileResponse:
    try:
        return to_response(create_profile(db, user.id, payload))
    except ProfileAlreadyExistsError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Fitness profile already exists",
        ) from None
    except ProfileInvariantError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service temporarily unavailable",
        ) from None


@router.patch(
    "",
    response_model=ProfileResponse,
    dependencies=[Depends(require_trusted_origin)],
)
def update(
    payload: ProfileUpdate,
    db: DatabaseSession,
    user: CurrentUser,
) -> ProfileResponse:
    try:
        return to_response(update_profile(db, user.id, payload))
    except ProfileNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Fitness profile not found",
        ) from None
    except InvalidWorkoutSetupError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Home training setup is required for home training",
        ) from None
    except ProfileInvariantError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service temporarily unavailable",
        ) from None


@router.get("", response_model=ProfileResponse)
def read(db: DatabaseSession, user: CurrentUser) -> ProfileResponse:
    try:
        return to_response(get_profile(db, user.id))
    except ProfileNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Fitness profile not found",
        ) from None
    except ProfileInvariantError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service temporarily unavailable",
        ) from None
