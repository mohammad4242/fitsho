from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import CheckConstraint, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.models import User
from app.profile.enums import (
    ExperienceLevel,
    FitnessGoal,
    HomeTrainingSetup,
    Sex,
    TrainingLocation,
)
from app.profile.models import BodyMeasurement, UserProfile


def test_body_measurement_model_defines_weight_range_constraint() -> None:
    constraints = {
        constraint.name: str(constraint.sqltext)
        for constraint in BodyMeasurement.__table__.constraints  # type: ignore[attr-defined]
        if isinstance(constraint, CheckConstraint)
    }

    assert constraints["ck_body_measurements_weight_kg_range"] == ("weight_kg BETWEEN 35 AND 300")


def make_user(db: Session, email: str) -> User:
    user = User(email=email, password_hash="hash")
    db.add(user)
    db.flush()
    return user


def make_profile(user: User) -> UserProfile:
    return UserProfile(
        user_id=user.id,
        display_name="Test User",
        birth_date=date(2000, 1, 1),
        sex=Sex.PREFER_NOT_TO_SAY,
        height_cm=175,
        fitness_goal=FitnessGoal.IMPROVE_FITNESS,
        experience_level=ExperienceLevel.BEGINNER,
        training_days_per_week=3,
        training_location=TrainingLocation.HOME,
        home_training_setup=HomeTrainingSetup.BODYWEIGHT_ONLY,
        session_duration_minutes=60,
        physical_limitations=None,
    )


def test_user_can_have_only_one_profile(db: Session) -> None:
    user = make_user(db, "one-profile@example.com")
    db.add(make_profile(user))
    db.flush()
    db.add(make_profile(user))

    with pytest.raises(IntegrityError):
        db.flush()


def test_first_month_experience_is_stored_in_profile(db: Session) -> None:
    user = make_user(db, "first-month@example.com")
    profile = make_profile(user)
    profile.experience_level = ExperienceLevel.FIRST_MONTH
    db.add(profile)
    db.flush()
    db.expire(profile)

    stored = db.scalar(select(UserProfile).where(UserProfile.user_id == user.id))

    assert stored is not None
    assert stored.experience_level is ExperienceLevel.FIRST_MONTH


def test_training_age_months_is_stored_in_profile(db: Session) -> None:
    user = make_user(db, "training-age@example.com")
    profile = make_profile(user)
    profile.training_age_months = 36
    db.add(profile)
    db.flush()
    db.expire(profile)

    stored = db.scalar(select(UserProfile).where(UserProfile.user_id == user.id))

    assert stored is not None
    assert stored.training_age_months == 36


def test_weight_is_decimal_and_history_is_many_to_one(db: Session) -> None:
    user = make_user(db, "weights@example.com")
    db.add(make_profile(user))
    db.add_all(
        [
            BodyMeasurement(user_id=user.id, weight_kg=Decimal("72.35")),
            BodyMeasurement(user_id=user.id, weight_kg=Decimal("71.90")),
        ]
    )
    db.flush()

    weights = db.scalars(
        select(BodyMeasurement.weight_kg).where(BodyMeasurement.user_id == user.id)
    ).all()
    assert set(weights) == {Decimal("72.35"), Decimal("71.90")}


def test_deleting_user_cascades_profile_and_measurements(db: Session) -> None:
    user = make_user(db, "cascade@example.com")
    profile = make_profile(user)
    measurement = BodyMeasurement(user_id=user.id, weight_kg=Decimal("80.00"))
    db.add_all([profile, measurement])
    db.flush()

    db.delete(user)
    db.flush()

    assert db.scalar(select(UserProfile).where(UserProfile.user_id == user.id)) is None
    assert db.scalar(select(BodyMeasurement).where(BodyMeasurement.id == measurement.id)) is None


@pytest.mark.parametrize(
    ("attribute", "invalid_value", "constraint_name"),
    [
        ("display_name", " ", "ck_user_profiles_display_name_length"),
        ("height_cm", 119, "ck_user_profiles_height_cm_range"),
        ("height_cm", 231, "ck_user_profiles_height_cm_range"),
        ("training_days_per_week", 0, "ck_user_profiles_training_days_range"),
        ("training_days_per_week", 8, "ck_user_profiles_training_days_range"),
        ("training_age_months", -1, "ck_user_profiles_training_age_months_range"),
        ("training_age_months", 901, "ck_user_profiles_training_age_months_range"),
        ("session_duration_minutes", 50, "ck_user_profiles_session_duration_values"),
        ("physical_limitations", "x" * 1001, "ck_user_profiles_limitations_length"),
    ],
)
def test_profile_range_constraints_reject_invalid_values(
    db: Session, attribute: str, invalid_value: object, constraint_name: str
) -> None:
    user = make_user(db, f"invalid-{attribute}-{invalid_value!s:.10}@example.com")
    profile = make_profile(user)
    setattr(profile, attribute, invalid_value)
    db.add(profile)

    with pytest.raises(IntegrityError) as error:
        db.flush()

    assert constraint_name in str(error.value)


@pytest.mark.parametrize(
    ("invalid_weight", "constraint_name"),
    [
        (Decimal("34.99"), "ck_body_measurements_weight_kg_range"),
        (Decimal("300.01"), "ck_body_measurements_weight_kg_range"),
    ],
)
def test_weight_range_constraint_rejects_invalid_values(
    db: Session, invalid_weight: Decimal, constraint_name: str
) -> None:
    user = make_user(db, f"invalid-weight-{invalid_weight}@example.com")
    db.add(BodyMeasurement(user_id=user.id, weight_kg=invalid_weight))

    with pytest.raises(IntegrityError) as error:
        db.flush()

    assert constraint_name in str(error.value)


@pytest.mark.parametrize(
    ("column", "constraint_name"),
    [
        ("sex", "ck_user_profiles_sex_values"),
        ("fitness_goal", "ck_user_profiles_fitness_goal_values"),
        ("experience_level", "ck_user_profiles_experience_level_values"),
        ("training_location", "ck_user_profiles_training_location_values"),
        ("home_training_setup", "ck_user_profiles_home_training_setup_values"),
    ],
)
def test_profile_enum_constraints_reject_invalid_database_values(
    db: Session, column: str, constraint_name: str
) -> None:
    user = make_user(db, f"invalid-{column}@example.com")
    values = {
        "user_id": user.id,
        "product_mode": "training",
        "display_name": "Test User",
        "birth_date": date(2000, 1, 1),
        "sex": Sex.PREFER_NOT_TO_SAY.value,
        "height_cm": 175,
        "fitness_goal": FitnessGoal.IMPROVE_FITNESS.value,
        "experience_level": ExperienceLevel.BEGINNER.value,
        "training_days_per_week": 3,
        "training_location": TrainingLocation.HOME.value,
        "home_training_setup": HomeTrainingSetup.BODYWEIGHT_ONLY.value,
        "session_duration_minutes": 60,
        "physical_limitations": None,
    }
    values[column] = "park" if column == "training_location" else "invalid"

    with pytest.raises(IntegrityError) as error:
        db.execute(
            text(
                """
                INSERT INTO user_profiles (
                        user_id, product_mode, display_name, birth_date, sex, height_cm,
                        fitness_goal,
                    experience_level, training_days_per_week, training_location,
                    home_training_setup, session_duration_minutes, physical_limitations
                ) VALUES (
                        :user_id, :product_mode, :display_name, :birth_date, :sex, :height_cm,
                        :fitness_goal,
                    :experience_level, :training_days_per_week, :training_location,
                    :home_training_setup, :session_duration_minutes, :physical_limitations
                )
                """
            ),
            values,
        )

    assert constraint_name in str(error.value)


def test_profile_database_requires_home_setup_and_rejects_it_for_gym(db: Session) -> None:
    home_user = make_user(db, "home-without-setup@example.com")
    home_profile = make_profile(home_user)
    home_profile.home_training_setup = None
    db.add(home_profile)

    with pytest.raises(IntegrityError) as home_error:
        db.flush()

    assert "ck_user_profiles_training_setup_consistency" in str(home_error.value)
    db.rollback()

    gym_user = make_user(db, "gym-with-setup@example.com")
    gym_profile = make_profile(gym_user)
    gym_profile.training_location = TrainingLocation.GYM
    db.add(gym_profile)

    with pytest.raises(IntegrityError) as gym_error:
        db.flush()

    assert "ck_user_profiles_training_setup_consistency" in str(gym_error.value)
