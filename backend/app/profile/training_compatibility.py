from collections.abc import Mapping
from enum import StrEnum
from types import MappingProxyType

from app.profile.enums import ExperienceLevel


class ResistanceTrainingDayStatus(StrEnum):
    RECOMMENDED = "recommended"
    ALLOWED = "allowed"
    UNSUPPORTED = "unsupported"


SUPPORTED_RESISTANCE_TRAINING_DAYS: tuple[int, ...] = (2, 3, 4, 5, 6)

RESISTANCE_TRAINING_DAY_COMPATIBILITY: Mapping[
    ExperienceLevel, Mapping[int, ResistanceTrainingDayStatus]
] = MappingProxyType(
    {
        ExperienceLevel.FIRST_MONTH: MappingProxyType(
            {
                2: ResistanceTrainingDayStatus.RECOMMENDED,
                3: ResistanceTrainingDayStatus.RECOMMENDED,
                4: ResistanceTrainingDayStatus.ALLOWED,
                5: ResistanceTrainingDayStatus.UNSUPPORTED,
                6: ResistanceTrainingDayStatus.UNSUPPORTED,
            }
        ),
        ExperienceLevel.BEGINNER: MappingProxyType(
            {
                2: ResistanceTrainingDayStatus.RECOMMENDED,
                3: ResistanceTrainingDayStatus.RECOMMENDED,
                4: ResistanceTrainingDayStatus.ALLOWED,
                5: ResistanceTrainingDayStatus.UNSUPPORTED,
                6: ResistanceTrainingDayStatus.UNSUPPORTED,
            }
        ),
        ExperienceLevel.INTERMEDIATE: MappingProxyType(
            {
                2: ResistanceTrainingDayStatus.ALLOWED,
                3: ResistanceTrainingDayStatus.RECOMMENDED,
                4: ResistanceTrainingDayStatus.RECOMMENDED,
                5: ResistanceTrainingDayStatus.RECOMMENDED,
                6: ResistanceTrainingDayStatus.ALLOWED,
            }
        ),
        ExperienceLevel.ADVANCED: MappingProxyType(
            {
                2: ResistanceTrainingDayStatus.UNSUPPORTED,
                3: ResistanceTrainingDayStatus.ALLOWED,
                4: ResistanceTrainingDayStatus.RECOMMENDED,
                5: ResistanceTrainingDayStatus.RECOMMENDED,
                6: ResistanceTrainingDayStatus.RECOMMENDED,
            }
        ),
    }
)


class UnsupportedResistanceTrainingCombinationError(ValueError):
    def __init__(self, experience_level: ExperienceLevel, training_days: int) -> None:
        self.experience_level = experience_level
        self.training_days = training_days
        super().__init__(
            f"{experience_level.value} does not support {training_days} resistance-training days"
        )


def resistance_training_day_status(
    experience_level: ExperienceLevel,
    training_days: int,
) -> ResistanceTrainingDayStatus:
    return RESISTANCE_TRAINING_DAY_COMPATIBILITY.get(experience_level, {}).get(
        training_days, ResistanceTrainingDayStatus.UNSUPPORTED
    )


def require_supported_resistance_training_days(
    experience_level: ExperienceLevel,
    training_days: int,
) -> ResistanceTrainingDayStatus:
    status = resistance_training_day_status(experience_level, training_days)
    if status is ResistanceTrainingDayStatus.UNSUPPORTED:
        raise UnsupportedResistanceTrainingCombinationError(experience_level, training_days)
    return status
