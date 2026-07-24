from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.auth.cookies import require_trusted_origin, set_session_cookie
from app.auth.exceptions import EmailAlreadyRegisteredError
from app.auth.schemas import RegisterRequest, UserResponse
from app.auth.service import register_user
from app.config import Settings, get_settings
from app.database.session import get_db

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

DatabaseSession = Annotated[Session, Depends(get_db)]
AppSettings = Annotated[Settings, Depends(get_settings)]


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_trusted_origin)],
)
def register(
    payload: RegisterRequest,
    response: Response,
    db: DatabaseSession,
    settings: AppSettings,
) -> UserResponse:
    try:
        result = register_user(db, payload, settings.session_ttl_seconds)
    except EmailAlreadyRegisteredError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email is already registered",
        ) from None
    set_session_cookie(response, result.raw_token, settings)
    return UserResponse.model_validate(result.user)
