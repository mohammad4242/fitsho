from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.ai.schemas import ProviderErrorCode
from app.auth.cookies import require_trusted_origin
from app.auth.models import User
from app.database.session import get_db
from app.exercises.dependencies import require_completed_profile
from app.exercises.models import Exercise
from app.exercises.schemas import ExerciseSummary
from app.workouts.dependencies import WorkoutGenerationServiceDependency
from app.workouts.models import WorkoutPlan, WorkoutPlanExercise
from app.workouts.repository import get_plan_for_user
from app.workouts.schemas import (
    ProgramGenerationOverrides,
    WorkoutDayResponse,
    WorkoutPlanExerciseAlternativeResponse,
    WorkoutPlanExerciseResponse,
    WorkoutPlanGenerateResponse,
    WorkoutPlanResponse,
)
from app.workouts.service import (
    GenerationCooldownError,
    GenerationInProgressError,
    NoEligibleExercisesError,
    ProgramGenerationRejectedError,
    WorkoutGenerationFailedError,
    WorkoutGenerationService,
)

router = APIRouter(prefix="/api/v1/workout-plans", tags=["workout-plans"])
DatabaseSession = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[User, Depends(require_completed_profile)]


@router.get("/active", response_model=WorkoutPlanResponse)
def read_active_plan(
    service: WorkoutGenerationServiceDependency,
    user: CurrentUser,
) -> WorkoutPlanResponse:
    active = service.get_active(user.id)
    if active is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No active workout plan")
    return to_plan_response(active.plan, is_stale=active.is_stale)


@router.post(
    "/generate",
    response_model=WorkoutPlanGenerateResponse,
    dependencies=[Depends(require_trusted_origin)],
)
async def generate_plan(
    service: WorkoutGenerationServiceDependency,
    user: CurrentUser,
    payload: ProgramGenerationOverrides | None = None,
) -> WorkoutPlanGenerateResponse:
    try:
        result = (
            await service.generate(user.id)
            if payload is None
            else await service.generate(user.id, payload)
        )
    except GenerationCooldownError as error:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Workout plan generation is cooling down",
            headers={"Retry-After": str(error.retry_after_seconds)},
        ) from None
    except GenerationInProgressError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Workout plan generation is already in progress",
        ) from None
    except NoEligibleExercisesError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={
                "code": error.error_code,
                "message": "Not enough eligible exercises for a safe workout plan",
            },
        ) from None
    except ProgramGenerationRejectedError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={
                "code": error.error_code,
                "safety_status": error.safety_status,
                "message": "Professional review is required before automatic programming",
            },
        ) from None
    except WorkoutGenerationFailedError as error:
        status_code = _provider_failure_status(error.provider_error_code)
        raise HTTPException(
            status_code=status_code,
            detail="Workout plan generation is temporarily unavailable",
        ) from None
    return WorkoutPlanGenerateResponse(plan=to_plan_response(result.plan), reused=result.reused)


@router.get("/{plan_id}", response_model=WorkoutPlanResponse)
def read_plan(
    plan_id: UUID,
    db: DatabaseSession,
    user: CurrentUser,
) -> WorkoutPlanResponse:
    plan = get_plan_for_user(db, plan_id=plan_id, user_id=user.id)
    if plan is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workout plan not found")
    return to_plan_response(plan)


def to_plan_response(plan: WorkoutPlan, *, is_stale: bool = False) -> WorkoutPlanResponse:
    return WorkoutPlanResponse(
        id=plan.id,
        status=plan.status,
        created_at=plan.created_at,
        activated_at=plan.activated_at,
        plan_duration_weeks=WorkoutGenerationService.plan_duration_weeks(plan),
        is_stale=is_stale,
        days=[
            WorkoutDayResponse(
                day_number=day.day_number,
                title_en=day.title_en,
                title_fa=day.title_fa,
                estimated_duration_minutes=day.estimated_duration_minutes,
                weekday=day.weekday,
                focus=day.focus,
                cardio=day.cardio,
                exercises=[
                    WorkoutPlanExerciseResponse(
                        order_index=item.order_index,
                        sets=item.sets,
                        reps_min=item.reps_min,
                        reps_max=item.reps_max,
                        rest_seconds=item.rest_seconds,
                        rir=item.rir,
                        estimated_minutes=item.estimated_minutes,
                        notes_en=item.notes_en,
                        notes_fa=item.notes_fa,
                        exercise=to_snapshot_or_live_summary(item.exercise_snapshot, item.exercise),
                        alternatives=to_alternative_responses(plan, item),
                        reason_codes=item.reason_codes,
                        warmup_sets=item.warmup_sets,
                        load_guidance=item.load_guidance,
                        progression_rule=item.progression_rule,
                    )
                    for item in day.exercises
                ],
            )
            for day in plan.days
        ],
        engine_version=plan.engine_version,
        ruleset_version=plan.ruleset_version,
        seed=plan.seed,
        primary_goal=plan.primary_goal,
        secondary_goal=plan.secondary_goal,
        training_status=plan.training_status,
        safety_status=plan.safety_status,
        assumptions=plan.assumptions,
        warnings=plan.warnings,
        validation_report=plan.validation_report,
        aggregate_metrics=plan.aggregate_metrics,
        progression_policy=plan.progression_policy,
        decision_trace=plan.decision_trace,
    )


def to_alternative_responses(
    plan: WorkoutPlan,
    item: WorkoutPlanExercise,
) -> list[WorkoutPlanExerciseAlternativeResponse]:
    substitution_ids = item.substitution_exercise_ids
    catalog = plan.exercise_catalog_snapshot.get("exercises", {})
    if substitution_ids and isinstance(catalog, dict):
        responses: list[WorkoutPlanExerciseAlternativeResponse] = []
        for exercise_id in substitution_ids:
            snapshot = catalog.get(exercise_id)
            if isinstance(snapshot, dict):
                display = snapshot.get("display_snapshot")
                if isinstance(display, dict):
                    responses.append(
                        WorkoutPlanExerciseAlternativeResponse(
                            reason_en="Safe substitution selected by the program rules.",
                            reason_fa="جایگزین ایمن بر اساس قواعد برنامه انتخاب شده است.",
                            exercise=ExerciseSummary.model_validate(display),
                        )
                    )
        return responses
    exercise = item.exercise
    return [
        WorkoutPlanExerciseAlternativeResponse(
            reason_en=alternative.reason_en,
            reason_fa=alternative.reason_fa,
            exercise=to_exercise_summary(alternative.alternative_exercise),
        )
        for alternative in sorted(
            exercise.alternatives,
            key=lambda alternative: alternative.alternative_exercise.slug,
        )
        if alternative.alternative_exercise.is_active
    ]


def to_snapshot_or_live_summary(
    snapshot: dict[str, object],
    exercise: Exercise,
) -> ExerciseSummary:
    display = snapshot.get("display_snapshot")
    if isinstance(display, dict) and display:
        return ExerciseSummary.model_validate(display)
    return to_exercise_summary(exercise)


def to_exercise_summary(exercise: Exercise) -> ExerciseSummary:
    return ExerciseSummary(
        id=exercise.id,
        slug=exercise.slug,
        name_en=exercise.name_en,
        name_fa=exercise.name_fa,
        body_region=exercise.body_region,
        primary_muscle=exercise.primary_muscle,
        labels=[item.label for item in exercise.labels],
        secondary_muscles=[secondary.muscle for secondary in exercise.secondary_muscles],
        equipment=[equipment.equipment for equipment in exercise.equipment_items],
        difficulty=exercise.difficulty,
        media_path=exercise.media_path,
        media_type=exercise.media_type,
    )


def _provider_failure_status(error_code: ProviderErrorCode | None) -> int:
    if error_code is ProviderErrorCode.TIMEOUT:
        return status.HTTP_504_GATEWAY_TIMEOUT
    if error_code in {
        ProviderErrorCode.CONNECTION_FAILURE,
        ProviderErrorCode.PROVIDER_UNAVAILABLE,
        ProviderErrorCode.MALFORMED_RESPONSE,
        ProviderErrorCode.INVALID_OUTPUT,
        ProviderErrorCode.REFUSAL,
    }:
        return status.HTTP_502_BAD_GATEWAY
    return status.HTTP_503_SERVICE_UNAVAILABLE
