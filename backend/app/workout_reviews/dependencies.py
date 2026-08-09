from typing import Annotated

from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.auth.models import User
from app.body_analysis.enums import SpecialistRole
from app.body_analysis.models import UserSpecialistRole
from app.database.session import get_db
from app.workout_reviews.enums import WorkoutReviewErrorCode
from app.workout_reviews.service import WorkoutReviewService

DatabaseSession = Annotated[Session, Depends(get_db)]
AuthenticatedUser = Annotated[User, Depends(get_current_user)]


def require_coach(user: AuthenticatedUser, db: DatabaseSession) -> User:
    role = db.scalar(
        select(UserSpecialistRole).where(
            UserSpecialistRole.user_id == user.id,
            UserSpecialistRole.role == SpecialistRole.COACH,
        )
    )
    if role is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": WorkoutReviewErrorCode.COACH_ROLE_REQUIRED.value,
                "message": "Coach role is required",
            },
        )
    return user


CoachUser = Annotated[User, Depends(require_coach)]


def get_workout_review_service(db: DatabaseSession) -> WorkoutReviewService:
    return WorkoutReviewService(db)


WorkoutReviewServiceDependency = Annotated[
    WorkoutReviewService, Depends(get_workout_review_service)
]
