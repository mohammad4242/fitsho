from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session, selectinload

from app.profile.enums import TrainingLocation
from app.profile.exceptions import (
    InvalidWorkoutSetupError,
    ProfileAlreadyExistsError,
    ProfileInvariantError,
    ProfileNotFoundError,
)
from app.profile.models import (
    BodyMeasurement,
    UserProfile,
    UserProfileTrainingCaution,
)
from app.profile.schemas import ProfileCreate, ProfileUpdate


@dataclass(frozen=True)
class ProfileSnapshot:
    profile: UserProfile
    measurement: BodyMeasurement


def create_profile(
    db: Session,
    user_id: UUID,
    payload: ProfileCreate,
) -> ProfileSnapshot:
    profile = UserProfile(
        user_id=user_id,
        display_name=payload.display_name,
        birth_date=payload.birth_date,
        sex=payload.sex,
        height_cm=payload.height_cm,
        fitness_goal=payload.fitness_goal,
        experience_level=payload.experience_level,
        training_days_per_week=payload.training_days_per_week,
        training_location=payload.training_location,
        home_training_setup=payload.home_training_setup,
        session_duration_minutes=payload.session_duration_minutes,
        physical_limitations=payload.physical_limitations,
        plan_duration_weeks=payload.plan_duration_weeks,
        workout_generation_method=payload.workout_generation_method,
        training_caution_items=[
            UserProfileTrainingCaution(caution=caution)
            for caution in sorted(payload.training_cautions, key=lambda value: value.value)
        ],
    )
    measurement = BodyMeasurement(
        user_id=user_id,
        weight_kg=payload.current_weight_kg,
        shoulder_circumference_cm=payload.shoulder_circumference_cm,
        waist_circumference_cm=payload.waist_circumference_cm,
        hip_circumference_cm=payload.hip_circumference_cm,
    )
    db.add(profile)
    try:
        db.flush()
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
    supplied_cautions = supplied_fields.pop("training_cautions", None)
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
    if changed_weight or changed_circumferences:
        measurement = BodyMeasurement(
            user_id=user_id,
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
