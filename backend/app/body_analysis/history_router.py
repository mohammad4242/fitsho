from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.auth.models import User
from app.body_analysis.history_schemas import BodyProgressTimelineResponse
from app.body_analysis.history_service import BodyProgressHistoryService
from app.database.session import get_db

router = APIRouter(prefix="/api/v1/body-progress", tags=["body-progress"])

DatabaseSession = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_user)]


@router.get("/timeline", response_model=BodyProgressTimelineResponse)
def get_body_progress_timeline(
    db: DatabaseSession,
    user: CurrentUser,
) -> BodyProgressTimelineResponse:
    return BodyProgressHistoryService(db).timeline(user.id)
