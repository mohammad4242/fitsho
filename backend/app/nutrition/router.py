from datetime import date
from decimal import Decimal
from typing import Annotated
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    Header,
    HTTPException,
    Request,
    UploadFile,
    status,
)
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.admin.dependencies import AdminUser
from app.auth.cookies import require_trusted_origin
from app.auth.dependencies import get_current_user
from app.auth.models import User
from app.config import Settings, get_settings
from app.database.session import get_db
from app.nutrition.adherence_service import (
    AdherenceError,
    adaptive_preferences,
    adherence_history,
    confirm_target_update,
)
from app.nutrition.clinical_service import (
    ClinicalError,
    claim_review,
    delete_lab,
    list_labs,
    open_lab,
    request_labs,
    review_queue,
    upload_lab,
)
from app.nutrition.estimate_service import (
    create_estimate,
    current_estimate,
    get_structured_exercise,
    save_structured_exercise,
)
from app.nutrition.exceptions import (
    GoalReselectionRequiredDomainError,
    NutritionEstimateBlockedError,
    NutritionEstimateNotFoundError,
    NutritionOnboardingBlockedError,
    NutritionProductModeError,
    NutritionProfileNotFoundError,
    NutritionTargetInfeasibleDomainError,
    SafetyDecisionNotFoundError,
    SafetyScreenRequiredError,
    SharedProfileRequiredError,
    StructuredExerciseRequiredError,
)
from app.nutrition.food_catalogue import (
    list_verified_foods,
    retire_catalogue_food,
    save_catalogue_food,
    save_catalogue_meal,
)
from app.nutrition.food_photo_service import (
    FoodPhotoError,
    confirm_photo,
    delete_photo,
    estimate_photo,
)
from app.nutrition.plan_editing import (
    PlanEditError,
    confirm_remove_meal,
    physician_action,
    physician_remove_meal,
    preview_remove_meal,
    save_feedback,
    set_meal_lock,
    shopping_list,
)
from app.nutrition.plan_service import (
    ActiveWeeklyPlanNotFoundError,
    WeeklyPlanNotFoundError,
    active_weekly_plan,
    generate_weekly_plan,
    latest_weekly_plan,
    weekly_plan_by_id,
    weekly_plan_history,
)
from app.nutrition.schemas import (
    CatalogueConsumptionInput,
    CatalogueFoodResponse,
    CatalogueFoodWrite,
    CatalogueMealResponse,
    CatalogueMealWrite,
    DailyCheckInInput,
    FoodPhotoConfirmInput,
    MealFeedbackInput,
    MealLockInput,
    NutritionEstimateResponse,
    NutritionProfileInput,
    NutritionProfileResponse,
    PhysicianLabRequestInput,
    PhysicianPlanActionInput,
    PhysicianReviewRequirementResponse,
    QuickApproximationInput,
    RemoveMealConfirmationInput,
    SafetyDecisionResponse,
    SafetyEvaluationResponse,
    SafetyProfileInput,
    StructuredExerciseInput,
    StructuredExerciseResponse,
    TargetUpdateConfirmationInput,
    WeeklyPlanGenerationResponse,
    WeeklyPlanHistoryItemResponse,
    WeeklyPlanResponse,
)
from app.nutrition.service import (
    current_safety_decision,
    evaluate_safety_profile,
    get_nutrition_profile,
    nutrition_profile_response,
    physician_review_requirement,
    safety_response,
    save_nutrition_profile,
    save_safety_profile,
)
from app.nutrition.tracking_service import (
    TrackingError,
    add_catalogue_food,
    daily_summary,
    delete_entry,
    history,
    save_quick_approximation,
    submit_check_in,
)

router = APIRouter(prefix="/api/v1/nutrition", tags=["nutrition"])

DatabaseSession = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_user)]
AppSettings = Annotated[Settings, Depends(get_settings)]


def _domain_error(code: str, message: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail={"code": code, "message": message},
    )


@router.get("/foods", response_model=list[CatalogueFoodResponse])
def read_verified_foods(db: DatabaseSession, user: CurrentUser) -> list[CatalogueFoodResponse]:
    return list_verified_foods(db)


@router.post(
    "/admin/foods",
    response_model=CatalogueFoodResponse,
    dependencies=[Depends(require_trusted_origin)],
)
def create_or_update_catalogue_food(
    payload: CatalogueFoodWrite,
    db: DatabaseSession,
    admin: AdminUser,
) -> CatalogueFoodResponse:
    del admin
    try:
        return save_catalogue_food(db, payload)
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(error)
        ) from None


@router.post(
    "/admin/meals",
    response_model=CatalogueMealResponse,
    dependencies=[Depends(require_trusted_origin)],
)
def create_catalogue_meal(
    payload: CatalogueMealWrite,
    db: DatabaseSession,
    admin: AdminUser,
) -> CatalogueMealResponse:
    del admin
    try:
        return save_catalogue_meal(db, payload)
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(error)
        ) from None


@router.delete(
    "/admin/foods/{slug}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_trusted_origin)],
)
def retire_food(
    slug: str,
    db: DatabaseSession,
    admin: AdminUser,
) -> None:
    del admin
    try:
        retire_catalogue_food(db, slug)
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from None


@router.post("/safety/evaluate", response_model=SafetyEvaluationResponse)
def preview_safety(payload: SafetyProfileInput) -> SafetyEvaluationResponse:
    return evaluate_safety_profile(payload)


@router.put(
    "/safety",
    response_model=SafetyDecisionResponse,
    dependencies=[Depends(require_trusted_origin)],
)
def update_safety(
    payload: SafetyProfileInput,
    db: DatabaseSession,
    user: CurrentUser,
) -> SafetyDecisionResponse:
    try:
        return safety_response(save_safety_profile(db, user.id, payload))
    except SharedProfileRequiredError:
        raise _domain_error(
            "SHARED_PROFILE_REQUIRED", "ابتدا اطلاعات پایه پروفایل را کامل کنید."
        ) from None


@router.get("/safety", response_model=SafetyDecisionResponse)
def read_safety(db: DatabaseSession, user: CurrentUser) -> SafetyDecisionResponse:
    try:
        return safety_response(current_safety_decision(db, user.id))
    except SafetyDecisionNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "SAFETY_DECISION_NOT_FOUND", "message": "ارزیابی ایمنی ثبت نشده است."},
        ) from None


@router.put(
    "/profile",
    response_model=NutritionProfileResponse,
    dependencies=[Depends(require_trusted_origin)],
)
def update_nutrition_profile(
    payload: NutritionProfileInput,
    db: DatabaseSession,
    user: CurrentUser,
) -> NutritionProfileResponse:
    try:
        return nutrition_profile_response(save_nutrition_profile(db, user.id, payload))
    except SharedProfileRequiredError:
        raise _domain_error(
            "SHARED_PROFILE_REQUIRED", "ابتدا اطلاعات پایه پروفایل را کامل کنید."
        ) from None
    except SafetyScreenRequiredError:
        raise _domain_error(
            "SAFETY_SCREEN_REQUIRED", "پیش از ادامه، ارزیابی ایمنی را کامل کنید."
        ) from None
    except NutritionOnboardingBlockedError:
        raise _domain_error(
            "NUTRITION_ONBOARDING_BLOCKED",
            "برای حفظ ایمنی، ادامه این مسیر فقط با بررسی پزشک ممکن است.",
        ) from None


@router.get("/profile", response_model=NutritionProfileResponse)
def read_nutrition_profile(
    db: DatabaseSession,
    user: CurrentUser,
) -> NutritionProfileResponse:
    try:
        return nutrition_profile_response(get_nutrition_profile(db, user.id))
    except NutritionProfileNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "NUTRITION_PROFILE_NOT_FOUND",
                "message": "پروفایل تغذیه ثبت نشده است.",
            },
        ) from None


@router.put(
    "/structured-exercise",
    response_model=StructuredExerciseResponse,
    dependencies=[Depends(require_trusted_origin)],
)
def update_structured_exercise(
    payload: StructuredExerciseInput,
    db: DatabaseSession,
    user: CurrentUser,
) -> StructuredExerciseResponse:
    try:
        return save_structured_exercise(db, user.id, payload)
    except NutritionProfileNotFoundError:
        raise _domain_error(
            "NUTRITION_PROFILE_REQUIRED",
            "ابتدا اطلاعات تغذیه را کامل کنید.",
        ) from None
    except NutritionProductModeError:
        raise _domain_error(
            "NUTRITION_PRODUCT_MODE_REQUIRED",
            "این اطلاعات فقط در مسیر تغذیه ثبت می‌شود.",
        ) from None


@router.get("/structured-exercise", response_model=StructuredExerciseResponse)
def read_structured_exercise(
    db: DatabaseSession,
    user: CurrentUser,
) -> StructuredExerciseResponse:
    try:
        return get_structured_exercise(db, user.id)
    except (NutritionProfileNotFoundError, StructuredExerciseRequiredError):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "STRUCTURED_EXERCISE_NOT_FOUND",
                "message": "اطلاعات تمرین ساختاریافته ثبت نشده است.",
            },
        ) from None
    except NutritionProductModeError:
        raise _domain_error(
            "NUTRITION_PRODUCT_MODE_REQUIRED",
            "برآورد تغذیه برای این مسیر فعال نیست.",
        ) from None


@router.post(
    "/estimates",
    response_model=NutritionEstimateResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_trusted_origin)],
)
def generate_estimate(
    db: DatabaseSession,
    user: CurrentUser,
) -> NutritionEstimateResponse:
    try:
        return create_estimate(db, user.id)
    except NutritionEstimateBlockedError:
        raise _domain_error(
            "NUTRITION_ESTIMATE_BLOCKED",
            "به‌دلیل وضعیت ایمنی، برآورد عمومی تغذیه برای این حساب مجاز نیست.",
        ) from None
    except GoalReselectionRequiredDomainError:
        raise _domain_error(
            "GOAL_RESELECTION_REQUIRED",
            "برای فردی که تمرین نمی‌کند، هدف عضله‌سازی قابل برآورد نیست.",
        ) from None
    except NutritionTargetInfeasibleDomainError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "TARGET_INFEASIBLE",
                "message": "حداقل‌های علمی در بازه کالری انتخاب‌شده قابل جمع نیستند.",
                "reason_codes": list(error.reason_codes),
            },
        ) from None
    except StructuredExerciseRequiredError:
        raise _domain_error(
            "STRUCTURED_EXERCISE_REQUIRED",
            "اطلاعات تمرین برای محاسبه دقیق انرژی لازم است.",
        ) from None
    except NutritionProfileNotFoundError:
        raise _domain_error(
            "NUTRITION_PROFILE_REQUIRED",
            "اطلاعات لازم برای برآورد تغذیه کامل نیست.",
        ) from None
    except NutritionProductModeError:
        raise _domain_error(
            "NUTRITION_PRODUCT_MODE_REQUIRED",
            "برآورد تغذیه برای این مسیر فعال نیست.",
        ) from None


@router.get("/estimates/current", response_model=NutritionEstimateResponse)
def read_current_estimate(
    db: DatabaseSession,
    user: CurrentUser,
) -> NutritionEstimateResponse:
    try:
        return current_estimate(db, user.id)
    except NutritionEstimateNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "NUTRITION_ESTIMATE_NOT_FOUND",
                "message": "هنوز برآورد تغذیه‌ای ثبت نشده است.",
            },
        ) from None


@router.get(
    "/review-requirement",
    response_model=PhysicianReviewRequirementResponse,
)
def read_review_requirement(
    db: DatabaseSession,
    user: CurrentUser,
) -> PhysicianReviewRequirementResponse:
    try:
        return physician_review_requirement(db, user.id)
    except SafetyDecisionNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "SAFETY_DECISION_NOT_FOUND", "message": "ارزیابی ایمنی ثبت نشده است."},
        ) from None


@router.post(
    "/plans",
    response_model=WeeklyPlanGenerationResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_trusted_origin)],
)
def generate_plan(
    db: DatabaseSession,
    user: CurrentUser,
) -> WeeklyPlanGenerationResponse:
    try:
        return generate_weekly_plan(db, user.id)
    except SafetyDecisionNotFoundError:
        raise _domain_error(
            "SAFETY_SCREEN_REQUIRED", "پیش از ساخت برنامه، ارزیابی ایمنی را کامل کنید."
        ) from None
    except StructuredExerciseRequiredError:
        raise _domain_error(
            "STRUCTURED_EXERCISE_REQUIRED",
            "اطلاعات تمرین برای محاسبه برنامه لازم است.",
        ) from None


@router.get("/plans/latest", response_model=WeeklyPlanResponse)
def read_latest_plan(db: DatabaseSession, user: CurrentUser) -> WeeklyPlanResponse:
    try:
        return latest_weekly_plan(db, user.id)
    except WeeklyPlanNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "NUTRITION_PLAN_NOT_FOUND",
                "message": "هنوز برنامه غذایی هفتگی ساخته نشده است.",
            },
        ) from None


@router.get("/plans/active", response_model=WeeklyPlanResponse)
def read_active_plan(db: DatabaseSession, user: CurrentUser) -> WeeklyPlanResponse:
    try:
        return active_weekly_plan(db, user.id)
    except ActiveWeeklyPlanNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "ACTIVE_NUTRITION_PLAN_NOT_FOUND",
                "message": "هنوز برنامه تأییدشده و فعالی وجود ندارد.",
            },
        ) from None


@router.get("/plans/history", response_model=list[WeeklyPlanHistoryItemResponse])
def read_plan_history(
    db: DatabaseSession, user: CurrentUser
) -> list[WeeklyPlanHistoryItemResponse]:
    return weekly_plan_history(db, user.id)


@router.get("/plans/{plan_id}", response_model=WeeklyPlanResponse)
def read_plan_revision(
    plan_id: str,
    db: DatabaseSession,
    user: CurrentUser,
) -> WeeklyPlanResponse:
    try:
        return weekly_plan_by_id(db, user.id, UUID(plan_id))
    except (ValueError, WeeklyPlanNotFoundError):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "NUTRITION_PLAN_NOT_FOUND",
                "message": "نسخه برنامه غذایی پیدا نشد.",
            },
        ) from None


def _plan_edit_error(error: PlanEditError) -> HTTPException:
    status_code = (
        status.HTTP_404_NOT_FOUND if error.code.endswith("NOT_FOUND") else status.HTTP_409_CONFLICT
    )
    if error.code == "PHYSICIAN_ROLE_REQUIRED":
        status_code = status.HTTP_403_FORBIDDEN
    return HTTPException(status_code=status_code, detail={"code": error.code})


@router.get("/plans/{plan_id}/shopping-list")
def read_shopping_list(plan_id: UUID, db: DatabaseSession, user: CurrentUser) -> dict[str, object]:
    try:
        return shopping_list(db, user.id, plan_id)
    except PlanEditError as error:
        raise _plan_edit_error(error) from None


@router.put("/plans/{plan_id}/meals/{meal_id}/lock", dependencies=[Depends(require_trusted_origin)])
def update_meal_lock(
    plan_id: UUID, meal_id: UUID, payload: MealLockInput, db: DatabaseSession, user: CurrentUser
) -> dict[str, object]:
    try:
        return set_meal_lock(db, user.id, plan_id, meal_id, payload.is_locked)
    except PlanEditError as error:
        raise _plan_edit_error(error) from None


@router.put(
    "/plans/{plan_id}/meals/{meal_id}/feedback", dependencies=[Depends(require_trusted_origin)]
)
def update_meal_feedback(
    plan_id: UUID, meal_id: UUID, payload: MealFeedbackInput, db: DatabaseSession, user: CurrentUser
) -> dict[str, object]:
    try:
        return save_feedback(db, user.id, plan_id, meal_id, payload.feedback_type, payload.notes)
    except PlanEditError as error:
        raise _plan_edit_error(error) from None


@router.post("/plans/{plan_id}/edits/remove-meal/preview")
def preview_meal_removal(
    plan_id: UUID, meal_id: UUID, db: DatabaseSession, user: CurrentUser
) -> dict[str, object]:
    try:
        return preview_remove_meal(db, user.id, plan_id, meal_id)
    except PlanEditError as error:
        raise _plan_edit_error(error) from None


@router.post(
    "/plans/{plan_id}/edits/remove-meal/confirm",
    response_model=WeeklyPlanResponse,
    dependencies=[Depends(require_trusted_origin)],
)
def confirm_meal_removal(
    plan_id: UUID, payload: RemoveMealConfirmationInput, db: DatabaseSession, user: CurrentUser
) -> WeeklyPlanResponse:
    try:
        return confirm_remove_meal(
            db, user.id, plan_id, payload.expected_plan_revision_id, payload.meal_id
        )
    except PlanEditError as error:
        raise _plan_edit_error(error) from None


@router.post(
    "/physician/plans/{plan_id}/action",
    response_model=WeeklyPlanResponse,
    dependencies=[Depends(require_trusted_origin)],
)
def review_plan(
    plan_id: UUID, payload: PhysicianPlanActionInput, db: DatabaseSession, user: CurrentUser
) -> WeeklyPlanResponse:
    try:
        return physician_action(
            db, user.id, plan_id, payload.expected_plan_revision_id, payload.action, payload.notes
        )
    except PlanEditError as error:
        raise _plan_edit_error(error) from None


@router.post(
    "/physician/plans/{plan_id}/edits/remove-meal",
    response_model=WeeklyPlanResponse,
    dependencies=[Depends(require_trusted_origin)],
)
def physician_edit_remove_meal(
    plan_id: UUID,
    payload: RemoveMealConfirmationInput,
    db: DatabaseSession,
    user: CurrentUser,
) -> WeeklyPlanResponse:
    try:
        return physician_remove_meal(
            db, user.id, plan_id, payload.expected_plan_revision_id, payload.meal_id
        )
    except PlanEditError as error:
        raise _plan_edit_error(error) from None


def _tracking_error(error: TrackingError) -> HTTPException:
    error_status = (
        status.HTTP_404_NOT_FOUND if error.code.endswith("NOT_FOUND") else status.HTTP_409_CONFLICT
    )
    return HTTPException(status_code=error_status, detail={"code": error.code})


@router.put("/tracking/check-in", dependencies=[Depends(require_trusted_origin)])
def update_daily_check_in(
    payload: DailyCheckInInput, db: DatabaseSession, user: CurrentUser
) -> dict[str, object]:
    try:
        return submit_check_in(db, user.id, payload.entry_date, payload.status, payload.note)
    except TrackingError as error:
        raise _tracking_error(error) from None


@router.post(
    "/tracking/entries/catalogue",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_trusted_origin)],
)
def create_catalogue_consumption(
    payload: CatalogueConsumptionInput, db: DatabaseSession, user: CurrentUser
) -> dict[str, object]:
    try:
        return add_catalogue_food(
            db,
            user.id,
            payload.entry_date,
            payload.food_id,
            Decimal(str(payload.grams)),
            payload.note,
        )
    except TrackingError as error:
        raise _tracking_error(error) from None


@router.post(
    "/tracking/entries/quick",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_trusted_origin)],
)
def create_quick_consumption(
    payload: QuickApproximationInput, db: DatabaseSession, user: CurrentUser
) -> dict[str, object]:
    return save_quick_approximation(
        db,
        user.id,
        payload.entry_date,
        payload.display_name,
        Decimal(str(payload.calories)),
        Decimal(str(payload.protein_g)) if payload.protein_g is not None else None,
    )


@router.get("/tracking/days/{entry_date}")
def read_daily_tracking(
    entry_date: date, db: DatabaseSession, user: CurrentUser
) -> dict[str, object]:
    return daily_summary(db, user.id, entry_date)


@router.get("/tracking/history")
def read_tracking_history(
    start: date, end: date, db: DatabaseSession, user: CurrentUser
) -> list[dict[str, object]]:
    if end < start or (end - start).days > 366:
        raise HTTPException(status_code=422, detail={"code": "INVALID_DATE_RANGE"})
    return history(db, user.id, start, end)


@router.delete(
    "/tracking/entries/{entry_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_trusted_origin)],
)
def remove_consumption_entry(entry_id: UUID, db: DatabaseSession, user: CurrentUser) -> None:
    try:
        delete_entry(db, user.id, entry_id)
    except TrackingError as error:
        raise _tracking_error(error) from None


def _food_photo_error(error: FoodPhotoError) -> HTTPException:
    error_status = (
        status.HTTP_404_NOT_FOUND if error.code.endswith("NOT_FOUND") else status.HTTP_409_CONFLICT
    )
    if error.code in {"INVALID_FOOD_PHOTO", "FOOD_PHOTO_TOO_LARGE"}:
        error_status = status.HTTP_422_UNPROCESSABLE_CONTENT
    if error.code == "FOOD_PHOTO_PROVIDER_UNAVAILABLE":
        error_status = status.HTTP_503_SERVICE_UNAVAILABLE
    return HTTPException(status_code=error_status, detail={"code": error.code})


@router.post(
    "/tracking/photo-estimates",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_trusted_origin)],
)
async def create_food_photo_estimate(
    request: Request,
    db: DatabaseSession,
    user: CurrentUser,
    settings: AppSettings,
    file: Annotated[UploadFile, File()],
    consent: Annotated[bool, Header(alias="X-Fitsho-Food-Photo-Consent")],
) -> dict[str, object]:
    try:
        return await estimate_photo(
            db, user.id, file, consent, settings, request.app.state.ai_http_client
        )
    except FoodPhotoError as error:
        raise _food_photo_error(error) from None


@router.post(
    "/tracking/photo-estimates/{estimate_id}/confirm",
    dependencies=[Depends(require_trusted_origin)],
)
def confirm_food_photo_estimate(
    estimate_id: UUID,
    payload: FoodPhotoConfirmInput,
    db: DatabaseSession,
    user: CurrentUser,
) -> list[dict[str, object]]:
    try:
        return confirm_photo(db, user.id, estimate_id, payload.entry_date)
    except FoodPhotoError as error:
        raise _food_photo_error(error) from None


@router.delete(
    "/tracking/photo-estimates/{estimate_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_trusted_origin)],
)
def remove_food_photo_estimate(
    estimate_id: UUID, db: DatabaseSession, user: CurrentUser, settings: AppSettings
) -> None:
    try:
        delete_photo(db, user.id, estimate_id, settings)
    except FoodPhotoError as error:
        raise _food_photo_error(error) from None


@router.get("/adherence")
def read_adherence(
    start: date, end: date, db: DatabaseSession, user: CurrentUser
) -> dict[str, object]:
    if end < start or (end - start).days > 366:
        raise HTTPException(status_code=422, detail={"code": "INVALID_DATE_RANGE"})
    return adherence_history(db, user.id, start, end)


@router.get("/adaptive-preferences")
def read_adaptive_preferences(db: DatabaseSession, user: CurrentUser) -> dict[str, object]:
    return adaptive_preferences(db, user.id)


@router.post(
    "/targets/confirm-update",
    dependencies=[Depends(require_trusted_origin)],
)
def update_confirmed_target(
    payload: TargetUpdateConfirmationInput, db: DatabaseSession, user: CurrentUser
) -> dict[str, object]:
    try:
        return confirm_target_update(db, user.id, payload.requested_goal, payload.confirmed)
    except AdherenceError as error:
        raise HTTPException(status_code=409, detail={"code": error.code}) from None


def _clinical_error(error: ClinicalError) -> HTTPException:
    error_status = (
        status.HTTP_404_NOT_FOUND if error.code.endswith("NOT_FOUND") else status.HTTP_409_CONFLICT
    )
    if error.code == "PHYSICIAN_ROLE_REQUIRED":
        error_status = status.HTTP_403_FORBIDDEN
    if error.code in {"INVALID_LAB_DOCUMENT", "LAB_DOCUMENT_TOO_LARGE"}:
        error_status = status.HTTP_422_UNPROCESSABLE_CONTENT
    return HTTPException(status_code=error_status, detail={"code": error.code})


@router.post(
    "/labs",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_trusted_origin)],
)
async def create_lab_document(
    db: DatabaseSession,
    user: CurrentUser,
    settings: AppSettings,
    file: Annotated[UploadFile, File()],
    test_date: Annotated[date | None, Form()] = None,
    laboratory_name: Annotated[str | None, Form()] = None,
    user_note: Annotated[str | None, Form()] = None,
    category: Annotated[str | None, Form()] = None,
    request_id: Annotated[UUID | None, Form()] = None,
) -> dict[str, object]:
    try:
        return await upload_lab(
            db,
            user.id,
            file,
            settings,
            test_date=test_date,
            laboratory_name=laboratory_name,
            user_note=user_note,
            category=category,
            request_id=request_id,
        )
    except ClinicalError as error:
        raise _clinical_error(error) from None


@router.get("/labs")
def read_lab_documents(db: DatabaseSession, user: CurrentUser) -> list[dict[str, object]]:
    return list_labs(db, user.id)


@router.get("/labs/{document_id}/file")
def download_lab_document(
    document_id: UUID, db: DatabaseSession, user: CurrentUser, settings: AppSettings
) -> StreamingResponse:
    try:
        handle, content_type, filename = open_lab(db, user.id, document_id, settings)
    except ClinicalError as error:
        raise _clinical_error(error) from None
    return StreamingResponse(
        handle,
        media_type=content_type,
        headers={"Content-Disposition": f'inline; filename="{filename}"'},
    )


@router.delete(
    "/labs/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_trusted_origin)],
)
def remove_lab_document(
    document_id: UUID, db: DatabaseSession, user: CurrentUser, settings: AppSettings
) -> None:
    try:
        delete_lab(db, user.id, document_id, settings)
    except ClinicalError as error:
        raise _clinical_error(error) from None


@router.get("/physician/reviews")
def read_physician_queue(db: DatabaseSession, user: CurrentUser) -> list[dict[str, object]]:
    try:
        return review_queue(db, user.id)
    except ClinicalError as error:
        raise _clinical_error(error) from None


@router.post(
    "/physician/reviews/{review_id}/claim",
    dependencies=[Depends(require_trusted_origin)],
)
def claim_physician_review(
    review_id: UUID, db: DatabaseSession, user: CurrentUser
) -> dict[str, object]:
    try:
        return claim_review(db, user.id, review_id)
    except ClinicalError as error:
        raise _clinical_error(error) from None


@router.post(
    "/physician/plans/{plan_id}/request-labs",
    dependencies=[Depends(require_trusted_origin)],
)
def create_physician_lab_request(
    plan_id: UUID,
    payload: PhysicianLabRequestInput,
    db: DatabaseSession,
    user: CurrentUser,
) -> dict[str, object]:
    try:
        return request_labs(
            db,
            user.id,
            plan_id,
            payload.expected_plan_revision_id,
            payload.requested_tests,
            payload.user_visible_reason,
        )
    except ClinicalError as error:
        raise _clinical_error(error) from None
