from dataclasses import dataclass
from datetime import date
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session, selectinload

from app.nutrition.enums import SafetyOutcome
from app.nutrition.models import NutritionProfile, NutritionSafetyDecision
from app.profile.enums import ProductMode, ProfileCompletionState, TrainingLocation
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
from app.profile.models import (
    BodyMeasurement,
    UserProfile,
    UserProfileTrainingCaution,
)
from app.profile.schemas import ProfileCreate, ProfileUpdate, SharedProfileUpsert, calculate_age
from app.workout_cycles.models import WorkoutCycle


@dataclass(frozen=True)
class ProfileSnapshot:
    profile: UserProfile
    measurement: BodyMeasurement


def ensure_supported_age(birth_date: date) -> None:
    age = calculate_age(birth_date, date.today())
    if age < 18:
        raise AgeNotSupportedError
    if age > 100:
        raise AgeOutOfRangeError


def profile_completion_state(
    profile: UserProfile | None,
    nutrition_profile: NutritionProfile | None = None,
    safety_decision: NutritionSafetyDecision | None = None,
) -> ProfileCompletionState:
    if profile is None:
        return ProfileCompletionState.PRODUCT_MODE_NOT_SELECTED
    if profile.display_name is None:
        return ProfileCompletionState.SHARED_PROFILE_INCOMPLETE
    training_complete = all(
        value is not None
        for value in (
            profile.experience_level,
            profile.training_days_per_week,
            profile.training_location,
            profile.session_duration_minutes,
            profile.plan_duration_weeks,
            profile.workout_generation_method,
        )
    )
    if profile.product_mode is ProductMode.TRAINING:
        if not training_complete:
            return ProfileCompletionState.TRAINING_ONBOARDING_INCOMPLETE
        return ProfileCompletionState.TRAINING_READY
    if profile.product_mode is ProductMode.BOTH and not training_complete:
        return ProfileCompletionState.TRAINING_ONBOARDING_INCOMPLETE
    if safety_decision is not None and safety_decision.outcome in {
        SafetyOutcome.AUTOMATIC_DRAFT_REQUIRES_PHYSICIAN_REVIEW,
        SafetyOutcome.PHYSICIAN_MANUAL_PLAN_REQUIRED,
        SafetyOutcome.UNSUPPORTED_OR_HARD_BLOCKED,
    }:
        if nutrition_profile is None:
            return ProfileCompletionState.MEDICAL_REVIEW_INFORMATION_INCOMPLETE
        return ProfileCompletionState.NUTRITION_PENDING_REVIEW
    if nutrition_profile is None:
        return ProfileCompletionState.NUTRITION_ONBOARDING_INCOMPLETE
    if profile.product_mode is ProductMode.BOTH:
        return ProfileCompletionState.BOTH_READY
    return ProfileCompletionState.NUTRITION_DRAFT_READY


def select_product_mode(db: Session, user_id: UUID, product_mode: ProductMode) -> UserProfile:
    profile = db.scalar(select(UserProfile).where(UserProfile.user_id == user_id).with_for_update())
    if profile is None:
        profile = UserProfile(user_id=user_id, product_mode=product_mode)
        db.add(profile)
    else:
        profile.product_mode = product_mode
    try:
        db.commit()
        db.refresh(profile)
    except SQLAlchemyError:
        db.rollback()
        raise
    return profile


def create_profile(
    db: Session,
    user_id: UUID,
    payload: ProfileCreate,
) -> ProfileSnapshot:
    ensure_supported_age(payload.birth_date)
    profile = db.scalar(select(UserProfile).where(UserProfile.user_id == user_id).with_for_update())
    if profile is not None and profile.experience_level is not None:
        raise ProfileAlreadyExistsError
    if profile is None:
        profile = UserProfile(user_id=user_id, product_mode=ProductMode.TRAINING)
        db.add(profile)
    for field_name, value in {
        "display_name": payload.display_name,
        "birth_date": payload.birth_date,
        "sex": payload.sex,
        "height_cm": payload.height_cm,
        "fitness_goal": payload.fitness_goal,
        "experience_level": payload.experience_level,
        "training_age_months": payload.training_age_months,
        "preferred_weekdays": (
            list(payload.preferred_weekdays) if payload.preferred_weekdays is not None else None
        ),
        "priority_muscles": (
            [muscle.value for muscle in payload.priority_muscles]
            if payload.priority_muscles is not None
            else None
        ),
        "training_days_per_week": payload.training_days_per_week,
        "training_location": payload.training_location,
        "home_training_setup": payload.home_training_setup,
        "session_duration_minutes": payload.session_duration_minutes,
        "training_intensity": payload.training_intensity,
        "physical_limitations": payload.physical_limitations,
        "plan_duration_weeks": payload.plan_duration_weeks,
        "workout_generation_method": payload.workout_generation_method,
    }.items():
        setattr(profile, field_name, value)
    profile.training_caution_items[:] = [
        UserProfileTrainingCaution(caution=caution)
        for caution in sorted(payload.training_cautions, key=lambda value: value.value)
    ]
    measurement = db.scalar(
        select(BodyMeasurement)
        .where(BodyMeasurement.user_id == user_id)
        .order_by(BodyMeasurement.measured_at.desc(), BodyMeasurement.id.desc())
    )
    measurement_matches = (
        measurement is not None
        and measurement.weight_kg == payload.current_weight_kg
        and measurement.shoulder_circumference_cm == payload.shoulder_circumference_cm
        and measurement.waist_circumference_cm == payload.waist_circumference_cm
        and measurement.hip_circumference_cm == payload.hip_circumference_cm
    )
    if not measurement_matches:
        measurement = BodyMeasurement(
            user_id=user_id,
            weight_kg=payload.current_weight_kg,
            shoulder_circumference_cm=payload.shoulder_circumference_cm,
            waist_circumference_cm=payload.waist_circumference_cm,
            hip_circumference_cm=payload.hip_circumference_cm,
        )
    assert measurement is not None
    db.add(profile)
    try:
        db.flush()
        if not measurement_matches:
            db.add(measurement)
        db.flush()
        db.refresh(profile)
        db.refresh(measurement)
        _ = profile.training_caution_items
        db.expunge(profile)
        db.expunge(measurement)
        db.commit()
    except IntegrityError as error:
        db.rollback()
        raise ProfileAlreadyExistsError from error
    except SQLAlchemyError:
        db.rollback()
        raise
    return ProfileSnapshot(profile=profile, measurement=measurement)


def get_profile(db: Session, user_id: UUID) -> ProfileSnapshot:
    profile = db.scalar(
        select(UserProfile)
        .where(UserProfile.user_id == user_id)
        .options(selectinload(UserProfile.training_caution_items))
    )
    if profile is None:
        raise ProfileNotFoundError

    measurement = db.scalar(
        select(BodyMeasurement)
        .where(BodyMeasurement.user_id == user_id)
        .order_by(BodyMeasurement.measured_at.desc(), BodyMeasurement.id.desc())
    )
    if measurement is None:
        raise ProfileInvariantError
    return ProfileSnapshot(profile=profile, measurement=measurement)


def update_profile(
    db: Session,
    user_id: UUID,
    payload: ProfileUpdate,
) -> ProfileSnapshot:
    if payload.birth_date is not None:
        ensure_supported_age(payload.birth_date)
    profile = db.scalar(
        select(UserProfile)
        .where(UserProfile.user_id == user_id)
        .options(selectinload(UserProfile.training_caution_items))
        .with_for_update()
    )
    if profile is None:
        raise ProfileNotFoundError

    measurement = db.scalar(
        select(BodyMeasurement)
        .where(BodyMeasurement.user_id == user_id)
        .order_by(BodyMeasurement.measured_at.desc(), BodyMeasurement.id.desc())
    )
    if measurement is None:
        raise ProfileInvariantError

    supplied_fields = payload.model_dump(exclude_unset=True)
    cycle_id = supplied_fields.pop("cycle_id", None)
    if cycle_id is not None and db.scalar(
        select(WorkoutCycle).where(
            WorkoutCycle.id == cycle_id,
            WorkoutCycle.user_id == user_id,
        )
    ) is None:
        raise ProfileCycleNotFoundError
    supplied_cautions = supplied_fields.pop("training_cautions", None)
    if "preferred_weekdays" in supplied_fields:
        supplied_fields["preferred_weekdays"] = (
            list(payload.preferred_weekdays) if payload.preferred_weekdays is not None else None
        )
    if "priority_muscles" in supplied_fields:
        supplied_fields["priority_muscles"] = (
            [muscle.value for muscle in payload.priority_muscles]
            if payload.priority_muscles is not None
            else None
        )
    supplied_weight = supplied_fields.pop("current_weight_kg", None)
    circumference_fields = (
        "shoulder_circumference_cm",
        "waist_circumference_cm",
        "hip_circumference_cm",
    )
    supplied_circumferences = {
        field_name: supplied_fields.pop(field_name)
        for field_name in circumference_fields
        if field_name in supplied_fields
    }

    final_location = supplied_fields.get("training_location", profile.training_location)
    final_home_setup = supplied_fields.get("home_training_setup", profile.home_training_setup)
    if final_location == TrainingLocation.GYM:
        supplied_fields["home_training_setup"] = None
    elif final_home_setup is None:
        raise InvalidWorkoutSetupError

    final_training_days = supplied_fields.get(
        "training_days_per_week", profile.training_days_per_week
    )
    final_weekdays = supplied_fields.get("preferred_weekdays", profile.preferred_weekdays)
    if (
        final_weekdays is not None
        and final_training_days is not None
        and len(final_weekdays) > final_training_days
    ):
        raise InvalidProfilePreferencesError

    for field_name, value in supplied_fields.items():
        setattr(profile, field_name, value)

    if "training_cautions" in payload.model_fields_set:
        profile.training_caution_items[:] = [
            UserProfileTrainingCaution(caution=caution)
            for caution in sorted(supplied_cautions or [], key=lambda value: value.value)
        ]

    changed_weight = supplied_weight is not None and supplied_weight != measurement.weight_kg
    changed_circumferences = any(
        value != getattr(measurement, field_name)
        for field_name, value in supplied_circumferences.items()
    )
    if cycle_id is not None or changed_weight or changed_circumferences:
        measurement = BodyMeasurement(
            user_id=user_id,
            cycle_id=cycle_id,
            weight_kg=supplied_weight if changed_weight else measurement.weight_kg,
            shoulder_circumference_cm=supplied_circumferences.get(
                "shoulder_circumference_cm", measurement.shoulder_circumference_cm
            ),
            waist_circumference_cm=supplied_circumferences.get(
                "waist_circumference_cm", measurement.waist_circumference_cm
            ),
            hip_circumference_cm=supplied_circumferences.get(
                "hip_circumference_cm", measurement.hip_circumference_cm
            ),
        )
        db.add(measurement)

    try:
        db.flush()
        db.refresh(profile)
        db.refresh(measurement)
        _ = profile.training_caution_items
        db.expunge(profile)
        db.expunge(measurement)
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        raise
    return ProfileSnapshot(profile=profile, measurement=measurement)


def apply_profile_update_without_commit(
    db: Session,
    user_id: UUID,
    payload: ProfileUpdate,
) -> UserProfile | None:
    """Apply an already-confirmed profile update inside the caller's transaction."""
    profile = db.scalar(
        select(UserProfile)
        .where(UserProfile.user_id == user_id)
        .options(selectinload(UserProfile.training_caution_items))
        .with_for_update()
    )
    if profile is None:
        return None

    supplied_fields = payload.model_dump(exclude_unset=True)
    supplied_fields.pop("cycle_id", None)
    supplied_fields.pop("current_weight_kg", None)
    for field_name in (
        "shoulder_circumference_cm",
        "waist_circumference_cm",
        "hip_circumference_cm",
    ):
        supplied_fields.pop(field_name, None)
    supplied_fields.pop("training_cautions", None)
    if "preferred_weekdays" in supplied_fields:
        supplied_fields["preferred_weekdays"] = (
            list(payload.preferred_weekdays) if payload.preferred_weekdays is not None else None
        )

    final_location = supplied_fields.get("training_location", profile.training_location)
    final_home_setup = supplied_fields.get("home_training_setup", profile.home_training_setup)
    if final_location == TrainingLocation.GYM:
        supplied_fields["home_training_setup"] = None
    elif final_location == TrainingLocation.HOME and final_home_setup is None:
        raise InvalidWorkoutSetupError

    final_training_days = supplied_fields.get(
        "training_days_per_week", profile.training_days_per_week
    )
    final_weekdays = supplied_fields.get("preferred_weekdays", profile.preferred_weekdays)
    if (
        final_weekdays is not None
        and final_training_days is not None
        and len(final_weekdays) > final_training_days
    ):
        raise InvalidProfilePreferencesError

    for field_name, value in supplied_fields.items():
        setattr(profile, field_name, value)
    db.flush()
    return profile


def upsert_shared_profile(
    db: Session,
    user_id: UUID,
    payload: SharedProfileUpsert,
) -> ProfileSnapshot:
    ensure_supported_age(payload.birth_date)
    profile = db.scalar(select(UserProfile).where(UserProfile.user_id == user_id).with_for_update())
    if profile is None:
        raise ProfileNotFoundError

    profile.display_name = payload.display_name
    profile.birth_date = payload.birth_date
    profile.sex = payload.sex
    profile.height_cm = payload.height_cm
    profile.fitness_goal = payload.fitness_goal
    latest = db.scalar(
        select(BodyMeasurement)
        .where(BodyMeasurement.user_id == user_id)
        .order_by(BodyMeasurement.measured_at.desc(), BodyMeasurement.id.desc())
    )
    if latest is None or latest.weight_kg != payload.current_weight_kg:
        latest = BodyMeasurement(user_id=user_id, weight_kg=payload.current_weight_kg)
        db.add(latest)
    try:
        db.flush()
        db.refresh(profile)
        db.refresh(latest)
        db.expunge(profile)
        db.expunge(latest)
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        raise
    return ProfileSnapshot(profile=profile, measurement=latest)


def get_shared_profile(db: Session, user_id: UUID) -> ProfileSnapshot:
    profile = db.get(UserProfile, user_id)
    if (
        profile is None
        or profile.display_name is None
        or profile.birth_date is None
        or profile.sex is None
        or profile.height_cm is None
        or profile.fitness_goal is None
    ):
        raise ProfileNotFoundError
    measurement = db.scalar(
        select(BodyMeasurement)
        .where(BodyMeasurement.user_id == user_id)
        .order_by(BodyMeasurement.measured_at.desc(), BodyMeasurement.id.desc())
    )
    if measurement is None:
        raise ProfileInvariantError
    return ProfileSnapshot(profile=profile, measurement=measurement)
