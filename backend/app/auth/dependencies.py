from dataclasses import dataclass
from datetime import datetime
from typing import Annotated

from fastapi import Depends, HTTPException, Request, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.auth.cookies import session_cookie_deletion_header
from app.auth.models import User
from app.auth.service import (
    MobileAccessContext,
    mobile_access_context_for_token,
    session_for_token,
)
from app.config import Settings, get_settings
from app.database.session import get_db

DatabaseSession = Annotated[Session, Depends(get_db)]
AppSettings = Annotated[Settings, Depends(get_settings)]
BearerCredentials = Annotated[
    HTTPAuthorizationCredentials | None,
    Security(HTTPBearer(auto_error=False)),
]


@dataclass(frozen=True)
class AuthenticatedPrincipal:
    user: User
    mobile: MobileAccessContext | None
    via_bearer: bool
    authenticated_at: datetime | None = None


def _bearer_token(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None,
) -> str | None:
    authorization = request.headers.get("authorization")
    if authorization is None:
        return None
    if credentials is not None:
        return credentials.credentials
    scheme, separator, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not separator or not token.strip():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return token.strip()


def get_current_authentication(
    request: Request,
    db: DatabaseSession,
    settings: AppSettings,
    credentials: BearerCredentials,
) -> AuthenticatedPrincipal:
    raw_bearer_token = _bearer_token(request, credentials)
    if raw_bearer_token is not None:
        context = mobile_access_context_for_token(db, raw_bearer_token)
        if context is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return AuthenticatedPrincipal(
            user=context.user,
            mobile=context,
            via_bearer=True,
            authenticated_at=context.family.created_at,
        )

    raw_token = request.cookies.get(settings.session_cookie_name)
    if raw_token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )
    auth_session = session_for_token(db, raw_token)
    if auth_session is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"Set-Cookie": session_cookie_deletion_header(settings)},
        )
    user = db.get(User, auth_session.user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"Set-Cookie": session_cookie_deletion_header(settings)},
        )
    return AuthenticatedPrincipal(
        user=user,
        mobile=None,
        via_bearer=False,
        authenticated_at=auth_session.created_at,
    )


CurrentAuthentication = Annotated[
    AuthenticatedPrincipal,
    Depends(get_current_authentication),
]


def get_current_user(authentication: CurrentAuthentication) -> User:
    return authentication.user


def get_current_mobile_session(
    request: Request,
    db: DatabaseSession,
    credentials: BearerCredentials,
) -> MobileAccessContext:
    raw_bearer_token = _bearer_token(request, credentials)
    if raw_bearer_token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Bearer authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    context = mobile_access_context_for_token(db, raw_bearer_token)
    if context is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return context
