from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.schemas import ProviderErrorCode
from app.auth.cookies import require_trusted_origin
from app.auth.models import User
from app.database.session import get_db
from app.exercises.dependencies import require_completed_profile
from app.exercises.media_resolver import resolve_primary_media
from app.exercises.models import Exercise
from app.exercises.schemas import ExerciseSummary
from app.profile.models import UserProfile
from app.workout_reviews.enums import WorkoutReviewStatus
from app.workouts.dependencies import WorkoutGenerationServiceDependency
from app.workouts.models import WorkoutDay, WorkoutPlan, WorkoutPlanExercise
from app.workouts.pdf import render_workout_plan_pdf
from app.workouts.program_engine.session_targets import (
    english_session_title_for_targets,
    persian_session_title_for_targets,
    target_muscles_from_values,
)
from app.workouts.program_engine.supplemental_policy import exercise_count_breakdown
from app.workouts.repository import get_plan_for_user, list_plans_for_user
from app.workouts.schemas import (
    ProgramGenerationOverrides,
    WorkoutDayResponse,
    WorkoutPlanCoachReviewResponse,
    WorkoutPlanExerciseAlternativeResponse,
    WorkoutPlanExerciseResponse,
    WorkoutPlanGenerateResponse,
    WorkoutPlanResponse,
    WorkoutPlanVersionSummaryResponse,
)
from app.workouts.service import (
    GenerationCooldownError,
    GenerationInProgressError,
    NoEligibleExercisesError,
    ProgramGenerationRejectedError,
    WorkoutConstructionUnsatisfiedError,
    WorkoutGenerationFailedError,
    WorkoutGenerationService,
)

router = APIRouter(prefix="/api/v1/workout-plans", tags=["workout-plans"])
DatabaseSession = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[User, Depends(require_completed_profile)]


@router.get("/active", response_model=WorkoutPlanResponse)
def read_active_plan(
    service: WorkoutGenerationServiceDependency,
    db: DatabaseSession,
    user: CurrentUser,
) -> WorkoutPlanResponse:
    active = service.get_active(user.id)
    if active is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No active workout plan")
    return to_plan_response(active.plan, is_stale=active.is_stale, db=db)


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
    except WorkoutConstructionUnsatisfiedError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={
                "code": error.error_code,
                "message": "No safe workout layout satisfies all required session constraints",
            },
        ) from None
    except ProgramGenerationRejectedError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={
                "code": error.error_code,
                "safety_status": error.safety_status,
                "message": (
                    "Requested resistance-training days are not supported for this experience level"
                    if error.error_code == "UNSUPPORTED_RESISTANCE_TRAINING_DAYS"
                    else "Professional review is required before automatic programming"
                ),
            },
        ) from None
    except WorkoutGenerationFailedError as error:
        status_code = _provider_failure_status(error.provider_error_code)
        raise HTTPException(
            status_code=status_code,
            detail="Workout plan generation is temporarily unavailable",
        ) from None
    return WorkoutPlanGenerateResponse(plan=to_plan_response(result.plan), reused=result.reused)


@router.get("/history", response_model=list[WorkoutPlanVersionSummaryResponse])
def read_plan_history(
    db: DatabaseSession,
    user: CurrentUser,
) -> list[WorkoutPlanVersionSummaryResponse]:
    return [
        WorkoutPlanVersionSummaryResponse(
            id=plan.id,
            status=plan.status,
            created_at=plan.created_at,
            activated_at=plan.activated_at,
            is_active=plan.status.value == "active",
            coach_review=_coach_review_response(plan, db),
        )
        for plan in list_plans_for_user(db, user.id)
    ]


@router.get(
    "/{plan_id}/pdf",
    response_class=Response,
    responses={status.HTTP_200_OK: {"content": {"application/pdf": {}}}},
)
def download_plan_pdf(
    plan_id: UUID,
    db: DatabaseSession,
    user: CurrentUser,
) -> Response:
    plan = get_plan_for_user(db, plan_id=plan_id, user_id=user.id)
    if plan is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workout plan not found")
    content = render_workout_plan_pdf(to_plan_response(plan, db=db))
    return Response(
        content=content,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="fitsho-workout-plan-{plan.id}.pdf"'
        },
    )


@router.get("/{plan_id}", response_model=WorkoutPlanResponse)
def read_plan(
    plan_id: UUID,
    db: DatabaseSession,
    user: CurrentUser,
) -> WorkoutPlanResponse:
    plan = get_plan_for_user(db, plan_id=plan_id, user_id=user.id)
    if plan is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workout plan not found")
    return to_plan_response(plan, db=db)


def to_plan_response(
    plan: WorkoutPlan,
    *,
    is_stale: bool = False,
    db: Session | None = None,
) -> WorkoutPlanResponse:
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
                title_en=_day_titles(plan, day)[0],
                title_fa=_day_titles(plan, day)[1],
                estimated_duration_minutes=day.estimated_duration_minutes,
                **_day_count_fields(day.exercises),
                weekday=day.weekday,
                focus=day.focus,
                cardio=day.cardio,
                ai_coach_explanation_fa=day.ai_coach_explanation_fa,
                exercises=[
                    WorkoutPlanExerciseResponse(
                        id=item.id,
                        order_index=item.order_index,
                        sets=item.sets,
                        prescription_mode=item.prescription_mode,
                        reps_min=item.reps_min,
                        reps_max=item.reps_max,
                        duration_min_seconds=item.duration_min_seconds,
                        duration_max_seconds=item.duration_max_seconds,
                        rest_seconds=item.rest_seconds,
                        rir=item.rir,
                        estimated_minutes=item.estimated_minutes,
                        superset_group=item.superset_group,
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
        validation_report=_public_validation_report(plan.validation_report),
        aggregate_metrics=plan.aggregate_metrics,
        progression_policy=plan.progression_policy,
        body_analysis_provenance=plan.body_analysis_provenance,
        ai_coach_template_slug=plan.ai_coach_template_slug,
        ai_coach_program_explanation_fa=plan.ai_coach_program_explanation_fa,
        coach_review=_coach_review_response(plan, db),
    )


def _day_count_fields(exercises: list[WorkoutPlanExercise]) -> dict[str, int]:
    counts = exercise_count_breakdown(exercises)
    return {
        "main_exercise_count": counts.main_count,
        "supplemental_exercise_count": counts.supplemental_count,
        "total_exercise_count": counts.total_count,
    }


def _public_validation_report(report: dict[str, object]) -> dict[str, object]:
    return {key: value for key, value in report.items() if key != "decision_trace"}


def _coach_review_response(
    plan: WorkoutPlan,
    db: Session | None,
) -> WorkoutPlanCoachReviewResponse:
    approval = plan.approval_review
    if approval is not None and approval.status is WorkoutReviewStatus.APPROVED:
        return WorkoutPlanCoachReviewResponse(
            state="coach_approved",
            coach_display_name=_coach_display_name(db, approval.claimed_by_user_id),
            coach_note=approval.coach_note,
            approved_at=approval.approved_at,
        )
    source = plan.source_review
    if source is None:
        return WorkoutPlanCoachReviewResponse(state="none")
    if source.status in {WorkoutReviewStatus.PENDING, WorkoutReviewStatus.CLAIMED}:
        return WorkoutPlanCoachReviewResponse(state="pending_coach_review")
    if source.status is WorkoutReviewStatus.APPROVED:
        return WorkoutPlanCoachReviewResponse(
            state="initial_generated",
            coach_display_name=_coach_display_name(db, source.claimed_by_user_id),
            approved_at=source.approved_at,
        )
    return WorkoutPlanCoachReviewResponse(state="none")


def _coach_display_name(db: Session | None, coach_id: UUID | None) -> str | None:
    if db is None or coach_id is None:
        return None
    return db.scalar(select(UserProfile.display_name).where(UserProfile.user_id == coach_id))


def _day_titles(plan: WorkoutPlan, day: WorkoutDay) -> tuple[str, str]:
    if plan.engine_version != "program_engine_v1":
        return day.title_en, day.title_fa
    targets = target_muscles_from_values(
        item.exercise_snapshot.get("primary_muscle")
        if item.exercise_snapshot
        else item.exercise.primary_muscle
        for item in day.exercises
    )
    if not targets:
        return day.title_en, day.title_fa
    return (
        english_session_title_for_targets(day.day_number, targets),
        persian_session_title_for_targets(day.day_number, targets),
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
    primary_media = resolve_primary_media(exercise)
    return ExerciseSummary(
        id=exercise.id,
        slug=exercise.slug,
        name_en=exercise.name_en,
        name_fa=exercise.name_fa,
        content_type=exercise.content_type,
        body_region=exercise.body_region,
        primary_muscle=exercise.primary_muscle,
        muscle_focus=exercise.muscle_focus,
        labels=[item.label for item in exercise.labels],
        secondary_muscles=[secondary.muscle for secondary in exercise.secondary_muscles],
        equipment=[equipment.equipment for equipment in exercise.equipment_items],
        difficulty=exercise.difficulty,
        media_path=primary_media.path,
        media_type=primary_media.media_type,
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
