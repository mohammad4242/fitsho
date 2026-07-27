from typing import Annotated

from fastapi import Depends, HTTPException, status
from sqlalchemy import select

from app.auth.dependencies import DatabaseSession, get_current_user
from app.auth.models import User
from app.profile.models import UserProfile

CurrentUser = Annotated[User, Depends(get_current_user)]


def require_completed_profile(
    db: DatabaseSession,
    user: CurrentUser,
) -> User:
    profile_user_id = db.scalar(select(UserProfile.user_id).where(UserProfile.user_id == user.id))
    if profile_user_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Completed fitness profile required",
        )
    return user
