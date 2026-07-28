from typing import Annotated

from fastapi import Depends, HTTPException, status

from app.auth.dependencies import get_current_user
from app.auth.models import User


def require_admin(user: Annotated[User, Depends(get_current_user)]) -> User:
    if not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrator access required",
        )
    return user


AdminUser = Annotated[User, Depends(require_admin)]
