from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth.cookies import require_trusted_origin
from app.auth.dependencies import get_current_user
from app.auth.models import User
from app.database.session import get_db
from app.workout_cycles.body_progress_schemas import (
    WorkoutCycleBodyProgressComparisonResponse,
    WorkoutCycleFeedbackBodyProgressContext,
)
from app.workout_cycles.body_progress_service import (
    WorkoutCycleBodyProgressComparisonNotFoundError,
    compare_cycle_body_progress,
)
from app.workout_cycles.models import WorkoutCycle, WorkoutCycleWeeklyCheckIn
from app.workout_cycles.schemas import (
    CompletionFeedbackInput,
    WorkoutCycleCompletionFeedbackResponse,
    WorkoutCycleCurrentResponse,
    WorkoutCycleExerciseFeedbackSuggestionsResponse,
    WorkoutCycleWeeklyCheckInPainFollowUpResponse,
    WorkoutCycleWeeklyCheckInResponse,
    WorkoutCycleWeeklyCheckInUpsertRequest,
    WorkoutExerciseReplacementCreateRequest,
    WorkoutExerciseReplacementResponse,
)
from app.workout_cycles.service import (
    WorkoutCycleCompletionFeedbackNotDueError,
    WorkoutCycleCompletionFeedbackNotFoundError,
    WorkoutCycleNotFoundError,
    WorkoutCycleWeeklyCheckInNoActiveCycleError,
    WorkoutCycleWeeklyCheckInNotFoundError,
    WorkoutCycleWeeklyCheckInPainExerciseNotFoundError,
    WorkoutCycleWeeklyCheckInPainExerciseRequiredError,
    WorkoutCycleWeeklyCheckInPainFollowUpNotAllowedError,
    WorkoutCycleWeeklyCheckInSessionsOutOfRangeError,
    WorkoutExerciseReplacementAlternativeNotAllowedError,
    WorkoutExerciseReplacementNoActiveCycleError,
    WorkoutExerciseReplacementPlanExerciseNotFoundError,
    WorkoutExerciseReplacementSelfError,
    calculate_current_week,
    completion_feedback_input,
    cycle_has_reached_nominal_end,
    get_current_active_cycle_for_user,
    get_current_completion_feedback_cycle,
    get_current_weekly_check_in,
    get_cycle_exercise_feedback_suggestions,
    get_cycle_feedback_body_progress_context,
    record_exercise_replacement,
    submit_current_completion_feedback,
    upsert_current_weekly_check_in,
)

router = APIRouter(prefix="/api/v1/workout-cycles", tags=["workout-cycles"])
DatabaseSession = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_user)]


@router.get("/current", response_model=WorkoutCycleCurrentResponse)
def read_current_cycle(
    db: DatabaseSession,
    user: CurrentUser,
) -> WorkoutCycleCurrentResponse:
    cycle = get_current_active_cycle_for_user(db, user_id=user.id)
    if cycle is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active workout cycle",
        )
    return WorkoutCycleCurrentResponse(
        cycle_id=cycle.id,
        workout_plan_id=cycle.workout_plan_id,
        started_at=cycle.started_at,
        duration_weeks=cycle.duration_weeks,
        status=cycle.status,
        current_week=calculate_current_week(cycle.started_at, cycle.duration_weeks),
    )


def _completion_feedback_response(
    cycle: WorkoutCycle,
) -> WorkoutCycleCompletionFeedbackResponse:
    feedback = cycle.completion_feedback
    return WorkoutCycleCompletionFeedbackResponse(
        cycle_id=cycle.id,
        status=cycle.status,
        duration_weeks=cycle.duration_weeks,
        current_week=calculate_current_week(cycle.started_at, cycle.duration_weeks),
        is_due=cycle.status.value == "active" and cycle_has_reached_nominal_end(cycle),
        feedback_id=feedback.id if feedback is not None else None,
        feedback=completion_feedback_input(feedback),
        submitted_at=feedback.submitted_at if feedback is not None else None,
    )


@router.get(
    "/current/completion-feedback",
    response_model=WorkoutCycleCompletionFeedbackResponse,
)
def read_current_completion_feedback(
    db: DatabaseSession,
    user: CurrentUser,
) -> WorkoutCycleCompletionFeedbackResponse:
    try:
        cycle = get_current_completion_feedback_cycle(db, user_id=user.id)
    except WorkoutCycleCompletionFeedbackNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No workout cycle available",
        ) from None
    return _completion_feedback_response(cycle)


@router.put(
    "/current/completion-feedback",
    response_model=WorkoutCycleCompletionFeedbackResponse,
    dependencies=[Depends(require_trusted_origin)],
)
def submit_current_completion_feedback_route(
    payload: CompletionFeedbackInput,
    db: DatabaseSession,
    user: CurrentUser,
) -> WorkoutCycleCompletionFeedbackResponse:
    try:
        cycle = submit_current_completion_feedback(
            db,
            user_id=user.id,
            feedback=payload,
        )
    except WorkoutCycleCompletionFeedbackNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No workout cycle available",
        ) from None
    except WorkoutCycleCompletionFeedbackNotDueError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Workout cycle has not reached its end",
        ) from None
    return _completion_feedback_response(cycle)


def _weekly_check_in_response(
    check_in: WorkoutCycleWeeklyCheckIn,
) -> WorkoutCycleWeeklyCheckInResponse:
    pain_follow_up = check_in.pain_limitation
    return WorkoutCycleWeeklyCheckInResponse(
        id=check_in.id,
        user_id=check_in.user_id,
        cycle_id=check_in.cycle_id,
        week_number=check_in.week_number,
        sessions_completed=check_in.sessions_completed,
        perceived_difficulty=check_in.perceived_difficulty,
        recovery_rating=check_in.recovery_rating,
        has_pain_or_limitation=check_in.has_pain_or_limitation,
        pain_follow_up=(
            WorkoutCycleWeeklyCheckInPainFollowUpResponse.model_validate(pain_follow_up)
            if pain_follow_up is not None
            else None
        ),
        note_optional=check_in.note_optional,
        submitted_at=check_in.submitted_at,
        created_at=check_in.created_at,
        updated_at=check_in.updated_at,
    )


@router.get(
    "/current/weekly-check-in",
    response_model=WorkoutCycleWeeklyCheckInResponse,
)
def read_current_weekly_check_in(
    db: DatabaseSession,
    user: CurrentUser,
) -> WorkoutCycleWeeklyCheckInResponse:
    try:
        check_in = get_current_weekly_check_in(db, user_id=user.id)
    except WorkoutCycleWeeklyCheckInNoActiveCycleError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active workout cycle",
        ) from None
    except WorkoutCycleWeeklyCheckInNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No weekly check-in for current week",
        ) from None
    return _weekly_check_in_response(check_in)


@router.put(
    "/current/weekly-check-in",
    response_model=WorkoutCycleWeeklyCheckInResponse,
    dependencies=[Depends(require_trusted_origin)],
)
def upsert_current_weekly_check_in_route(
    payload: WorkoutCycleWeeklyCheckInUpsertRequest,
    db: DatabaseSession,
    user: CurrentUser,
) -> WorkoutCycleWeeklyCheckInResponse:
    try:
        check_in = upsert_current_weekly_check_in(
            db,
            user_id=user.id,
            sessions_completed=payload.sessions_completed,
            perceived_difficulty=payload.perceived_difficulty,
            recovery_rating=payload.recovery_rating,
            has_pain_or_limitation=payload.has_pain_or_limitation,
            note_optional=payload.note_optional,
            pain_workout_plan_exercise_id=(
                payload.pain_follow_up.workout_plan_exercise_id
                if payload.pain_follow_up is not None
                else None
            ),
            pain_note_optional=(
                payload.pain_follow_up.note_optional if payload.pain_follow_up is not None else None
            ),
        )
    except WorkoutCycleWeeklyCheckInNoActiveCycleError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active workout cycle",
        ) from None
    except WorkoutCycleWeeklyCheckInPainExerciseNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workout plan exercise not found in current cycle",
        ) from None
    except WorkoutCycleWeeklyCheckInSessionsOutOfRangeError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(error),
        ) from None
    except (
        WorkoutCycleWeeklyCheckInPainExerciseRequiredError,
        WorkoutCycleWeeklyCheckInPainFollowUpNotAllowedError,
        ValueError,
    ) as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(error),
        ) from None
    return _weekly_check_in_response(check_in)


@router.post(
    "/current/replacements",
    response_model=WorkoutExerciseReplacementResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_trusted_origin)],
)
def create_current_cycle_replacement(
    payload: WorkoutExerciseReplacementCreateRequest,
    db: DatabaseSession,
    user: CurrentUser,
) -> WorkoutExerciseReplacementResponse:
    try:
        replacement = record_exercise_replacement(
            db,
            user_id=user.id,
            workout_plan_exercise_id=payload.workout_plan_exercise_id,
            replacement_exercise_id=payload.replacement_exercise_id,
            reason=payload.reason,
            scope=payload.scope,
        )
    except WorkoutExerciseReplacementNoActiveCycleError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active workout cycle",
        ) from None
    except WorkoutExerciseReplacementPlanExerciseNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workout plan exercise not found in current cycle",
        ) from None
    except WorkoutExerciseReplacementSelfError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Replacement exercise must differ from original exercise",
        ) from None
    except WorkoutExerciseReplacementAlternativeNotAllowedError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Replacement exercise is not an allowed alternative",
        ) from None
    return WorkoutExerciseReplacementResponse.model_validate(replacement)


@router.get(
    "/{cycle_id}/exercise-feedback-suggestions",
    response_model=WorkoutCycleExerciseFeedbackSuggestionsResponse,
)
def read_cycle_exercise_feedback_suggestions(
    cycle_id: UUID,
    db: DatabaseSession,
    user: CurrentUser,
) -> WorkoutCycleExerciseFeedbackSuggestionsResponse:
    try:
        suggestions = get_cycle_exercise_feedback_suggestions(
            db,
            user_id=user.id,
            cycle_id=cycle_id,
        )
    except WorkoutCycleNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workout cycle not found",
        ) from None
    return WorkoutCycleExerciseFeedbackSuggestionsResponse(
        cycle_id=cycle_id,
        suggestions=suggestions,
    )


@router.get(
    "/{cycle_id}/body-progress-comparison",
    response_model=WorkoutCycleBodyProgressComparisonResponse,
)
def read_cycle_body_progress_comparison(
    cycle_id: UUID,
    db: DatabaseSession,
    user: CurrentUser,
) -> WorkoutCycleBodyProgressComparisonResponse:
    try:
        comparison = compare_cycle_body_progress(db, user_id=user.id, cycle_id=cycle_id)
    except WorkoutCycleBodyProgressComparisonNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workout cycle not found",
        ) from None
    return WorkoutCycleBodyProgressComparisonResponse(
        id=comparison.id,
        cycle_id=comparison.cycle_id,
        result=comparison.comparison_result,
        created_at=comparison.created_at,
        updated_at=comparison.updated_at,
    )


@router.get(
    "/{cycle_id}/feedback/body-progress",
    response_model=WorkoutCycleFeedbackBodyProgressContext,
)
def read_cycle_feedback_body_progress_context(
    cycle_id: UUID,
    db: DatabaseSession,
    user: CurrentUser,
) -> WorkoutCycleFeedbackBodyProgressContext:
    try:
        context = get_cycle_feedback_body_progress_context(
            db,
            cycle_id=cycle_id,
            user_id=user.id,
        )
    except WorkoutCycleNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workout cycle not found",
        ) from None
    if context is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cycle feedback not found",
        )
    return context
