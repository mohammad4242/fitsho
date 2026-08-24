from typing import Annotated, NoReturn

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.cookies import require_trusted_origin
from app.auth.dependencies import get_current_user
from app.auth.models import User
from app.database.session import get_db
from app.exercises.enums import MuscleGroup
from app.nutrition.models import NutritionProfile, NutritionSafetyDecision
from app.profile.enums import ProfileCompletionState
from app.profile.exceptions import (
    AgeNotSupportedError,
    AgeOutOfRangeError,
    InvalidProfilePreferencesError,
    InvalidWorkoutSetupError,
    ProfileAlreadyExistsError,
    ProfileCycleNotFoundError,
    ProfileInvariantError,
    ProfileNotFoundError,
)
from app.profile.models import UserProfile
from app.profile.schemas import (
    ProductModeSelection,
    ProfileCreate,
    ProfileResponse,
    ProfileStatusResponse,
    ProfileUpdate,
    SharedProfileResponse,
    SharedProfileUpsert,
)
from app.profile.service import (
    ProfileSnapshot,
    create_profile,
    get_profile,
    get_shared_profile,
    profile_completion_state,
    select_product_mode,
    update_profile,
    upsert_shared_profile,
)
from app.profile.training_compatibility import (
    UnsupportedResistanceTrainingCombinationError,
    resistance_training_day_status,
)
from app.workouts.program_engine.equipment import resolve_available_equipment

router = APIRouter(prefix="/api/v1/profile", tags=["profile"])

DatabaseSession = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_user)]


def raise_age_error(error: Exception) -> NoReturn:
    if isinstance(error, AgeNotSupportedError):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={
                "code": "AGE_NOT_SUPPORTED",
                "message": "فیتشو در حال حاضر فقط برای افراد ۱۸ سال و بالاتر ارائه می‌شود.",
            },
        ) from None
    raise HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        detail={"code": "AGE_OUT_OF_RANGE", "message": "تاریخ تولد واردشده پشتیبانی نمی‌شود."},
    ) from None


def completion_state(db: Session, profile: UserProfile | None) -> ProfileCompletionState:
    if profile is None:
        return profile_completion_state(None)
    nutrition_profile = db.get(NutritionProfile, profile.user_id)
    safety_decision = db.scalar(
        select(NutritionSafetyDecision)
        .where(NutritionSafetyDecision.user_id == profile.user_id)
        .order_by(NutritionSafetyDecision.revision.desc())
        .limit(1)
    )
    return profile_completion_state(profile, nutrition_profile, safety_decision)


@router.post(
    "/mode",
    response_model=ProfileStatusResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_trusted_origin)],
)
def select_mode(
    payload: ProductModeSelection,
    db: DatabaseSession,
    user: CurrentUser,
) -> ProfileStatusResponse:
    profile = select_product_mode(db, user.id, payload.product_mode)
    return ProfileStatusResponse(
        user_id=profile.user_id,
        product_mode=profile.product_mode,
        completion_state=completion_state(db, profile),
    )


@router.get("/status", response_model=ProfileStatusResponse)
def read_status(db: DatabaseSession, user: CurrentUser) -> ProfileStatusResponse:
    profile = db.scalar(select(UserProfile).where(UserProfile.user_id == user.id))
    return ProfileStatusResponse(
        user_id=user.id,
        product_mode=profile.product_mode if profile is not None else None,
        completion_state=completion_state(db, profile),
    )


def to_response(snapshot: ProfileSnapshot) -> ProfileResponse:
    profile = snapshot.profile
    measurement = snapshot.measurement
    assert profile.experience_level is not None
    assert profile.training_days_per_week is not None
    assert profile.training_location is not None
    return ProfileResponse(
        user_id=profile.user_id,
        display_name=profile.display_name,
        birth_date=profile.birth_date,
        sex=profile.sex,
        height_cm=profile.height_cm,
        current_weight_kg=float(measurement.weight_kg),
        weight_measured_at=measurement.measured_at,
        shoulder_circumference_cm=(
            float(measurement.shoulder_circumference_cm)
            if measurement.shoulder_circumference_cm is not None
            else None
        ),
        waist_circumference_cm=(
            float(measurement.waist_circumference_cm)
            if measurement.waist_circumference_cm is not None
            else None
        ),
        hip_circumference_cm=(
            float(measurement.hip_circumference_cm)
            if measurement.hip_circumference_cm is not None
            else None
        ),
        circumferences_measured_at=(
            measurement.measured_at
            if any(
                value is not None
                for value in (
                    measurement.shoulder_circumference_cm,
                    measurement.waist_circumference_cm,
                    measurement.hip_circumference_cm,
                )
            )
            else None
        ),
        fitness_goal=profile.fitness_goal,
        experience_level=profile.experience_level,
        training_age_months=profile.training_age_months,
        training_days_per_week=profile.training_days_per_week,
        training_days_compatibility=resistance_training_day_status(
            profile.experience_level, profile.training_days_per_week
        ),
        preferred_weekdays=(
            tuple(profile.preferred_weekdays) if profile.preferred_weekdays is not None else None
        ),
        priority_muscles=(
            tuple(MuscleGroup(value) for value in profile.priority_muscles)
            if profile.priority_muscles is not None
            else None
        ),
        training_location=profile.training_location,
        home_training_setup=profile.home_training_setup,
        available_equipment=tuple(
            sorted(
                resolve_available_equipment(
                    profile.training_location,
                    profile.home_training_setup,
                    profile.available_equipment,
                ),
                key=lambda item: item.value,
            )
        ),
        session_duration_minutes=profile.session_duration_minutes,
        training_intensity=profile.training_intensity,
        physical_limitations=profile.physical_limitations,
        training_cautions=sorted(
            (item.caution for item in profile.training_caution_items),
            key=lambda value: value.value,
        ),
        plan_duration_weeks=profile.plan_duration_weeks,
        workout_generation_method=profile.workout_generation_method,
        created_at=profile.created_at,
        updated_at=profile.updated_at,
    )


def to_shared_response(snapshot: ProfileSnapshot) -> SharedProfileResponse:
    return SharedProfileResponse(
        user_id=snapshot.profile.user_id,
        product_mode=snapshot.profile.product_mode,
        display_name=snapshot.profile.display_name,
        birth_date=snapshot.profile.birth_date,
        sex=snapshot.profile.sex,
        height_cm=snapshot.profile.height_cm,
        current_weight_kg=float(snapshot.measurement.weight_kg),
        weight_measured_at=snapshot.measurement.measured_at,
        fitness_goal=snapshot.profile.fitness_goal,
    )


@router.put(
    "/shared",
    response_model=SharedProfileResponse,
    dependencies=[Depends(require_trusted_origin)],
)
def save_shared_profile(
    payload: SharedProfileUpsert,
    db: DatabaseSession,
    user: CurrentUser,
) -> SharedProfileResponse:
    try:
        return to_shared_response(upsert_shared_profile(db, user.id, payload))
    except (AgeNotSupportedError, AgeOutOfRangeError) as error:
        raise_age_error(error)
    except ProfileNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "PRODUCT_MODE_REQUIRED", "message": "ابتدا مسیر فیتشو را انتخاب کنید."},
        ) from None


@router.get("/shared", response_model=SharedProfileResponse)
def read_shared_profile(db: DatabaseSession, user: CurrentUser) -> SharedProfileResponse:
    try:
        return to_shared_response(get_shared_profile(db, user.id))
    except ProfileNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "SHARED_PROFILE_NOT_FOUND", "message": "اطلاعات پایه ثبت نشده است."},
        ) from None
    except ProfileInvariantError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service temporarily unavailable",
        ) from None


@router.post(
    "",
    response_model=ProfileResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_trusted_origin)],
)
def create(
    payload: ProfileCreate,
    db: DatabaseSession,
    user: CurrentUser,
) -> ProfileResponse:
    try:
        return to_response(create_profile(db, user.id, payload))
    except (AgeNotSupportedError, AgeOutOfRangeError) as error:
        raise_age_error(error)
    except ProfileAlreadyExistsError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Fitness profile already exists",
        ) from None
    except UnsupportedResistanceTrainingCombinationError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={
                "code": "UNSUPPORTED_RESISTANCE_TRAINING_DAYS",
                "message": str(error),
            },
        ) from None
    except ProfileInvariantError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service temporarily unavailable",
        ) from None


@router.patch(
    "",
    response_model=ProfileResponse,
    dependencies=[Depends(require_trusted_origin)],
)
def update(
    payload: ProfileUpdate,
    db: DatabaseSession,
    user: CurrentUser,
) -> ProfileResponse:
    try:
        return to_response(update_profile(db, user.id, payload))
    except (AgeNotSupportedError, AgeOutOfRangeError) as error:
        raise_age_error(error)
    except ProfileNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Fitness profile not found",
        ) from None
    except ProfileCycleNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workout cycle not found",
        ) from None
    except InvalidWorkoutSetupError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Home training setup is required for home training",
        ) from None
    except InvalidProfilePreferencesError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Preferred weekdays cannot exceed training days per week",
        ) from None
    except UnsupportedResistanceTrainingCombinationError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={
                "code": "UNSUPPORTED_RESISTANCE_TRAINING_DAYS",
                "message": str(error),
            },
        ) from None
    except ProfileInvariantError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service temporarily unavailable",
        ) from None


@router.get("", response_model=ProfileResponse)
def read(db: DatabaseSession, user: CurrentUser) -> ProfileResponse:
    try:
        return to_response(get_profile(db, user.id))
    except ProfileNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Fitness profile not found",
        ) from None
    except ProfileInvariantError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service temporarily unavailable",
        ) from None
