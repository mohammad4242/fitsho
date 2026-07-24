from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.auth.cookies import session_cookie_deletion_header
from app.auth.models import User
from app.auth.service import user_for_session
from app.config import Settings, get_settings
from app.database.session import get_db

DatabaseSession = Annotated[Session, Depends(get_db)]
AppSettings = Annotated[Settings, Depends(get_settings)]


def get_current_user(
    request: Request,
    db: DatabaseSession,
    settings: AppSettings,
) -> User:
    raw_token = request.cookies.get(settings.session_cookie_name)
    if raw_token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )
    user = user_for_session(db, raw_token)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"Set-Cookie": session_cookie_deletion_header(settings)},
        )
    return user
