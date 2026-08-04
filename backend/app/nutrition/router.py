from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth.cookies import require_trusted_origin
from app.auth.dependencies import get_current_user
from app.auth.models import User
from app.database.session import get_db
from app.nutrition.exceptions import (
    NutritionOnboardingBlockedError,
    NutritionProfileNotFoundError,
    SafetyDecisionNotFoundError,
    SafetyScreenRequiredError,
    SharedProfileRequiredError,
)
from app.nutrition.schemas import (
    NutritionProfileInput,
    NutritionProfileResponse,
    PhysicianReviewRequirementResponse,
    SafetyDecisionResponse,
    SafetyEvaluationResponse,
    SafetyProfileInput,
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
