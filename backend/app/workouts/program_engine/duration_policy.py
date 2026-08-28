from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, get_args

from app.profile.schemas import SessionDurationMinutes
from app.workouts.program_engine.rulesets.resistance_training_v1 import ProgramRuleset

if TYPE_CHECKING:
    pass


def calculate_resistance_minutes(day: "Any", general_warmup_minutes: int) -> int:
    cardio_minutes = day.cardio.duration_minutes if day.cardio else 0
    return int(max(0, day.estimated_duration_minutes - general_warmup_minutes - cardio_minutes))


SESSION_DURATION_TOLERANCE_MINUTES = 10
CORE_PRESERVATION_EXTENSION_MINUTES = 20
SHORT_SESSION_MINIMUM_MAIN_EXERCISES = 3

# Official supported resistance-session durations.
# `session_duration_minutes` means: available time for the resistance-training
# portion of the session — it does NOT include general warm-up, cardio, or
# general cooldown.
OFFICIAL_SESSION_DURATIONS: tuple[int, ...] = get_args(SessionDurationMinutes)


def is_official_session_duration(minutes: int) -> bool:
    """Return True if *minutes* is an officially supported resistance-session duration."""
    return minutes in OFFICIAL_SESSION_DURATIONS


def validate_session_duration(minutes: int) -> int:
    """Return *minutes* unchanged, or raise ValueError for unsupported values."""
    if not is_official_session_duration(minutes):
        supported = ", ".join(str(v) for v in OFFICIAL_SESSION_DURATIONS)
        raise ValueError(
            f"session_duration_minutes={minutes} is not an official supported value. "
            f"Supported values: {supported}"
        )
    return minutes


def effective_main_exercise_floor(
    session_duration_minutes: int,
    ruleset: ProgramRuleset,
) -> int:
    return (
        SHORT_SESSION_MINIMUM_MAIN_EXERCISES
        if session_duration_minutes <= ruleset.short_session_minutes
        else ruleset.minimum_exercises_per_session
    )


@dataclass(frozen=True)
class SessionDurationPolicy:
    requested_minutes: int
    minimum_minutes: int
    maximum_minutes: int

    def contains(self, estimated_minutes: int) -> bool:
        return self.minimum_minutes <= estimated_minutes <= self.maximum_minutes

    @property
    def core_preservation_maximum_minutes(self) -> int:
        return self.requested_minutes + CORE_PRESERVATION_EXTENSION_MINUTES

    def workout_minutes(self, estimated_total_minutes: int, general_warmup_minutes: int) -> int:
        return max(0, estimated_total_minutes - general_warmup_minutes)

    def contains_total(self, estimated_total_minutes: int, general_warmup_minutes: int) -> bool:
        return self.contains(self.workout_minutes(estimated_total_minutes, general_warmup_minutes))

    def minimum_total_minutes(self, general_warmup_minutes: int) -> int:
        return self.minimum_minutes + general_warmup_minutes

    def maximum_total_minutes(self, general_warmup_minutes: int) -> int:
        return self.maximum_minutes + general_warmup_minutes

    def core_preservation_maximum_total_minutes(self, general_warmup_minutes: int) -> int:
        return self.core_preservation_maximum_minutes + general_warmup_minutes


def get_session_duration_policy(
    requested_minutes: int,
) -> SessionDurationPolicy:
    tolerance = SESSION_DURATION_TOLERANCE_MINUTES
    return SessionDurationPolicy(
        requested_minutes=requested_minutes,
        minimum_minutes=requested_minutes - tolerance,
        maximum_minutes=requested_minutes + tolerance,
    )
