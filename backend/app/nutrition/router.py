from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.admin.dependencies import AdminUser
from app.auth.cookies import require_trusted_origin
from app.auth.dependencies import get_current_user
from app.auth.models import User
from app.database.session import get_db
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
from app.nutrition.schemas import (
    CatalogueFoodResponse,
    CatalogueFoodWrite,
    CatalogueMealResponse,
    CatalogueMealWrite,
    NutritionEstimateResponse,
    NutritionProfileInput,
    NutritionProfileResponse,
    PhysicianReviewRequirementResponse,
    SafetyDecisionResponse,
    SafetyEvaluationResponse,
    SafetyProfileInput,
    StructuredExerciseInput,
    StructuredExerciseResponse,
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

router = APIRouter(prefix="/api/v1/nutrition", tags=["nutrition"])

DatabaseSession = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_user)]


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
