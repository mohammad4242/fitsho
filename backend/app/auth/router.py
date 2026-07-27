from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from app.auth.cookies import (
    clear_session_cookie,
    require_trusted_origin,
    set_session_cookie,
)
from app.auth.dependencies import get_current_user
from app.auth.exceptions import (
    EmailAlreadyRegisteredError,
    InvalidCredentialsError,
)
from app.auth.models import User
from app.auth.schemas import LoginRequest, RegisterRequest, UserResponse
from app.auth.service import login_user, logout_session, register_user
from app.config import Settings, get_settings
from app.database.session import get_db

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

DatabaseSession = Annotated[Session, Depends(get_db)]
AppSettings = Annotated[Settings, Depends(get_settings)]
CurrentUser = Annotated[User, Depends(get_current_user)]


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


@router.post(
    "/login",
    response_model=UserResponse,
    dependencies=[Depends(require_trusted_origin)],
)
def login(
    payload: LoginRequest,
    response: Response,
    db: DatabaseSession,
    settings: AppSettings,
) -> UserResponse:
    try:
        result = login_user(db, payload, settings.session_ttl_seconds)
    except InvalidCredentialsError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        ) from None
    set_session_cookie(response, result.raw_token, settings)
    return UserResponse.model_validate(result.user)


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_trusted_origin)],
)
def logout(
    request: Request,
    response: Response,
    db: DatabaseSession,
    settings: AppSettings,
) -> None:
    logout_session(db, request.cookies.get(settings.session_cookie_name))
    clear_session_cookie(response, settings)


@router.get("/me", response_model=UserResponse)
def me(user: CurrentUser) -> UserResponse:
    return UserResponse.model_validate(user)
