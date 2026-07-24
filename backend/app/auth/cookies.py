from typing import Annotated

from fastapi import Depends, HTTPException, Request, Response, status

from app.config import Settings, get_settings


def require_trusted_origin(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
) -> None:
    if request.headers.get("origin") != settings.frontend_origin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Untrusted request origin",
        )


def set_session_cookie(
    response: Response,
    raw_token: str,
    settings: Settings,
) -> None:
    response.set_cookie(
        key=settings.session_cookie_name,
        value=raw_token,
        max_age=settings.session_ttl_seconds,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/",
    )


def clear_session_cookie(response: Response, settings: Settings) -> None:
    response.delete_cookie(
        key=settings.session_cookie_name,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/",
    )
