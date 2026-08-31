import secrets

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .config import Settings, get_settings

bearer = HTTPBearer(auto_error=False)


def require_internal_auth(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),  # noqa: B008
    settings: Settings = Depends(get_settings),  # noqa: B008
) -> None:
    expected = settings.agent_service_token.get_secret_value()
    supplied = credentials.credentials if credentials is not None else ""
    if (
        credentials is None
        or credentials.scheme.lower() != "bearer"
        or not secrets.compare_digest(supplied, expected)
    ):
        raise HTTPException(
            status_code=401, detail="unauthorized", headers={"WWW-Authenticate": "Bearer"}
        )
