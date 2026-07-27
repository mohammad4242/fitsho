from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.profile.exceptions import (
    ProfileAlreadyExistsError,
    ProfileInvariantError,
    ProfileNotFoundError,
)
from app.profile.models import BodyMeasurement, UserProfile
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
        physical_limitations=payload.physical_limitations,
    )
    measurement = BodyMeasurement(
        user_id=user_id,
        weight_kg=payload.current_weight_kg,
    )
    db.add(profile)
    try:
        db.flush()
        db.add(measurement)
        db.flush()
        db.refresh(profile)
        db.refresh(measurement)
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
    profile = db.scalar(select(UserProfile).where(UserProfile.user_id == user_id))
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
    profile = db.scalar(select(UserProfile).where(UserProfile.user_id == user_id).with_for_update())
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
    supplied_weight = supplied_fields.pop("current_weight_kg", None)
    for field_name, value in supplied_fields.items():
        setattr(profile, field_name, value)

    if supplied_weight is not None and supplied_weight != measurement.weight_kg:
        measurement = BodyMeasurement(user_id=user_id, weight_kg=supplied_weight)
        db.add(measurement)

    try:
        db.flush()
        db.refresh(profile)
        db.refresh(measurement)
        db.expunge(profile)
        db.expunge(measurement)
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        raise
    return ProfileSnapshot(profile=profile, measurement=measurement)
