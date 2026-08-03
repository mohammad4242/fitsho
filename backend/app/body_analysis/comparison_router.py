from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.auth.models import User
from app.body_analysis.comparison_models import BodyProgressComparison
from app.body_analysis.comparison_schemas import BodyProgressComparisonResponse
from app.body_analysis.comparison_service import (
    BodyProgressComparisonNotFoundError,
    BodyProgressComparisonService,
)
from app.database.session import get_db

router = APIRouter(prefix="/api/v1/body-photo-sessions", tags=["body-progress"])

DatabaseSession = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_user)]


def _response(comparison: BodyProgressComparison) -> BodyProgressComparisonResponse:
    return BodyProgressComparisonResponse(
        id=comparison.id,
        previous_session_id=comparison.previous_session_id,
        current_session_id=comparison.current_session_id,
        previous_result_version_id=comparison.previous_result_version_id,
        current_result_version_id=comparison.current_result_version_id,
        comparison_version=comparison.comparison_version,
        schema_version=comparison.schema_version,
        normalized_result=comparison.normalized_result,
        quality_snapshot=comparison.quality_snapshot,
        context_snapshot=comparison.context_snapshot,
        created_at=comparison.created_at,
    )


@router.get(
    "/{session_id}/comparison",
    response_model=BodyProgressComparisonResponse | None,
)
def get_session_comparison(
    session_id: UUID,
    db: DatabaseSession,
    user: CurrentUser,
) -> BodyProgressComparisonResponse | None:
    try:
        comparison = BodyProgressComparisonService(db).create_for_session(session_id, user.id)
    except BodyProgressComparisonNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Body photo session not found",
        ) from None
    return _response(comparison) if comparison is not None else None
