from typing import Annotated

from fastapi import Depends, HTTPException, status
from sqlalchemy import select

from app.auth.dependencies import DatabaseSession, get_current_user
from app.auth.models import User
from app.profile.enums import ProductMode
from app.profile.models import UserProfile

CurrentUser = Annotated[User, Depends(get_current_user)]


def require_completed_profile(
    db: DatabaseSession,
    user: CurrentUser,
) -> User:
    profile = db.scalar(select(UserProfile).where(UserProfile.user_id == user.id))
    training_complete = (
        profile is not None
        and profile.product_mode in {ProductMode.TRAINING, ProductMode.BOTH}
        and all(
            value is not None
            for value in (
                profile.display_name,
                profile.birth_date,
                profile.sex,
                profile.height_cm,
                profile.fitness_goal,
                profile.experience_level,
                profile.training_days_per_week,
                profile.training_location,
                profile.session_duration_minutes,
                profile.plan_duration_weeks,
                profile.workout_generation_method,
            )
        )
    )
    if not training_complete:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Completed fitness profile required",
        )
    return user
