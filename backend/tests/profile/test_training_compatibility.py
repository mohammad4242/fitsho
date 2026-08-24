import pytest
from pydantic import ValidationError

from app.profile.enums import ExperienceLevel
from app.profile.schemas import ProfileCreate, ProfileUpdate
from app.profile.training_compatibility import (
    ResistanceTrainingDayStatus,
    resistance_training_day_status,
)

MATRIX = {
    ExperienceLevel.FIRST_MONTH: (
        ResistanceTrainingDayStatus.RECOMMENDED,
        ResistanceTrainingDayStatus.RECOMMENDED,
        ResistanceTrainingDayStatus.ALLOWED,
        ResistanceTrainingDayStatus.UNSUPPORTED,
        ResistanceTrainingDayStatus.UNSUPPORTED,
    ),
    ExperienceLevel.BEGINNER: (
        ResistanceTrainingDayStatus.RECOMMENDED,
        ResistanceTrainingDayStatus.RECOMMENDED,
        ResistanceTrainingDayStatus.ALLOWED,
        ResistanceTrainingDayStatus.UNSUPPORTED,
        ResistanceTrainingDayStatus.UNSUPPORTED,
    ),
    ExperienceLevel.INTERMEDIATE: (
        ResistanceTrainingDayStatus.ALLOWED,
        ResistanceTrainingDayStatus.RECOMMENDED,
        ResistanceTrainingDayStatus.RECOMMENDED,
        ResistanceTrainingDayStatus.RECOMMENDED,
        ResistanceTrainingDayStatus.ALLOWED,
    ),
    ExperienceLevel.ADVANCED: (
        ResistanceTrainingDayStatus.UNSUPPORTED,
        ResistanceTrainingDayStatus.ALLOWED,
        ResistanceTrainingDayStatus.RECOMMENDED,
        ResistanceTrainingDayStatus.RECOMMENDED,
        ResistanceTrainingDayStatus.RECOMMENDED,
    ),
}


def profile_payload(**overrides: object) -> dict[str, object]:
    return {
        "display_name": "Mohammad",
        "birth_date": "2000-05-14",
        "sex": "male",
        "height_cm": 178,
        "current_weight_kg": 76.5,
        "fitness_goal": "build_muscle",
        "experience_level": "beginner",
        "training_days_per_week": 3,
        "training_location": "gym",
        "session_duration_minutes": 60,
        **overrides,
    }


@pytest.mark.parametrize("experience_level,expected", MATRIX.items())
def test_official_matrix_is_explicit_and_queryable(
    experience_level: ExperienceLevel,
    expected: tuple[ResistanceTrainingDayStatus, ...],
) -> None:
    assert (
        tuple(resistance_training_day_status(experience_level, days) for days in range(2, 7))
        == expected
    )


@pytest.mark.parametrize(
    ("experience_level", "days"),
    [
        (level, days)
        for level, statuses in MATRIX.items()
        for days, status in zip(range(2, 7), statuses, strict=True)
        if status is ResistanceTrainingDayStatus.UNSUPPORTED
    ],
)
def test_profile_create_rejects_every_unsupported_matrix_cell(
    experience_level: ExperienceLevel, days: int
) -> None:
    with pytest.raises(ValidationError, match="resistance-training days"):
        ProfileCreate.model_validate(
            profile_payload(experience_level=experience_level, training_days_per_week=days)
        )


@pytest.mark.parametrize(
    ("experience_level", "days"),
    [
        (level, days)
        for level, statuses in MATRIX.items()
        for days, status in zip(range(2, 7), statuses, strict=True)
        if status is not ResistanceTrainingDayStatus.UNSUPPORTED
    ],
)
def test_profile_create_accepts_every_supported_matrix_cell(
    experience_level: ExperienceLevel, days: int
) -> None:
    profile = ProfileCreate.model_validate(
        profile_payload(experience_level=experience_level, training_days_per_week=days)
    )

    assert profile.experience_level is experience_level
    assert profile.training_days_per_week == days


def test_profile_update_validates_a_pair_when_both_fields_are_supplied() -> None:
    with pytest.raises(ValidationError, match="resistance-training days"):
        ProfileUpdate.model_validate({"experience_level": "advanced", "training_days_per_week": 2})

    update = ProfileUpdate.model_validate(
        {"experience_level": "first_month", "training_days_per_week": 4}
    )
    assert update.experience_level is ExperienceLevel.FIRST_MONTH
