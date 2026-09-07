from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.account_deletion.models import AccountDeletionRequest
from app.account_deletion.schemas import (
    AccountDeletionCancelRequest,
    AccountDeletionInitiateRequest,
    AccountDeletionStatusResponse,
)
from app.account_deletion.service import (
    AccountDeletionError,
    cancel_deletion,
    get_deletion_status,
    initiate_deletion,
)
from app.auth.cookies import require_trusted_origin
from app.auth.dependencies import (
    AuthenticatedPrincipal,
    CurrentAuthentication,
    DatabaseSession,
)
from app.config import Settings, get_settings

router = APIRouter(prefix="/api/v1/account-deletion", tags=["account-deletion"])
AppSettings = Annotated[Settings, Depends(get_settings)]


def _status_response(deletion: AccountDeletionRequest | None) -> AccountDeletionStatusResponse:
    if deletion is None:
        return AccountDeletionStatusResponse(
            status="none",
            request_id=None,
            requested_at=None,
            reauthenticated_at=None,
            grace_period_ends_at=None,
            cancelled_at=None,
            completed_at=None,
        )
    return AccountDeletionStatusResponse(
        status=deletion.status.value,
        request_id=deletion.id,
        requested_at=deletion.requested_at,
        reauthenticated_at=deletion.reauthenticated_at,
        grace_period_ends_at=deletion.grace_period_ends_at,
        cancelled_at=deletion.cancelled_at,
        completed_at=deletion.completed_at,
    )


def _raise_account_error(error: AccountDeletionError) -> None:
    if error.code == "ACCOUNT_DELETION_NOT_ENABLED":
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Account deletion is temporarily unavailable",
        ) from None
    if error.code in {"INVALID_REAUTHENTICATION", "RECENT_AUTHENTICATION_REQUIRED"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=error.code) from None
    if error.code == "NO_PENDING_DELETION":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=error.code) from None
    if error.code == "GRACE_PERIOD_EXPIRED":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=error.code) from None
    raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=error.code) from None


def _require_mutation_origin(
    request: Request,
    principal: AuthenticatedPrincipal,
    settings: Settings,
) -> None:
    if not principal.via_bearer:
        require_trusted_origin(request, settings)


@router.get("", response_model=AccountDeletionStatusResponse)
def get_status(
    db: DatabaseSession,
    settings: AppSettings,
    principal: CurrentAuthentication,
) -> AccountDeletionStatusResponse:
    try:
        return _status_response(get_deletion_status(db, principal.user.id, settings))
    except AccountDeletionError as error:
        _raise_account_error(error)
    raise AssertionError("unreachable")


@router.post(
    "",
    response_model=AccountDeletionStatusResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def request_deletion(
    request: Request,
    payload: AccountDeletionInitiateRequest,
    db: DatabaseSession,
    settings: AppSettings,
    principal: CurrentAuthentication,
) -> AccountDeletionStatusResponse:
    _require_mutation_origin(request, principal, settings)
    try:
        result = initiate_deletion(
            db,
            principal,
            settings,
            password=payload.password,
        )
        return _status_response(result.request)
    except AccountDeletionError as error:
        _raise_account_error(error)
    raise AssertionError("unreachable")


@router.post(
    "/cancel",
    response_model=AccountDeletionStatusResponse,
    status_code=status.HTTP_200_OK,
)
def cancel_requested_deletion(
    request: Request,
    payload: AccountDeletionCancelRequest,
    db: DatabaseSession,
    settings: AppSettings,
    principal: CurrentAuthentication,
) -> AccountDeletionStatusResponse:
    _require_mutation_origin(request, principal, settings)
    try:
        result = cancel_deletion(db, principal.user.id, settings)
        return _status_response(result.request)
    except AccountDeletionError as error:
        _raise_account_error(error)
    raise AssertionError("unreachable")
