from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, get_args

from app.exercises.enums import ExerciseLabel, ExerciseType
from app.profile.schemas import SessionDurationMinutes
from app.workouts.program_engine.rulesets.resistance_training_v1 import ProgramRuleset

if TYPE_CHECKING:
    pass


def _value(item: object, field: str, default: object = None) -> object:
    if isinstance(item, Mapping):
        return item.get(field, default)
    return getattr(item, field, default)


def _exercise_items(value: object) -> Iterable[object]:
    exercises = _value(value, "exercises", value)
    if isinstance(exercises, Iterable) and not isinstance(exercises, (str, bytes)):
        return exercises
    return ()


def _enum_value(value: object) -> object:
    return getattr(value, "value", value)


def is_main_training_exercise(exercise: object) -> bool:
    """Return whether an exercise contributes to the requested main-training time."""
    exercise_type = _enum_value(_value(exercise, "exercise_type"))
    if exercise_type in {ExerciseType.CORE.value, "cardio"}:
        return False
    labels = _value(exercise, "labels", ())
    return not any(_enum_value(label) == ExerciseLabel.CARDIO.value for label in labels)


def calculate_main_training_minutes_from_exercises(exercises: Iterable[object]) -> int:
    """Sum programmed exercise time, excluding only anatomical core and cardio."""
    return sum(
        max(0, int(_value(exercise, "estimated_minutes", 0) or 0))
        for exercise in exercises
        if is_main_training_exercise(exercise)
    )


def calculate_main_training_minutes(day: object) -> int:
    """Return a day's main-training minutes without warm-up, core, or cardio add-ons."""
    return calculate_main_training_minutes_from_exercises(_exercise_items(day))


def calculate_core_addon_minutes(value: object) -> int:
    """Return anatomical core exercise minutes that sit outside main training."""
    return sum(
        max(0, int(_value(exercise, "estimated_minutes", 0) or 0))
        for exercise in _exercise_items(value)
        if _enum_value(_value(exercise, "exercise_type")) == ExerciseType.CORE.value
    )


def calculate_cardio_addon_minutes(day: object) -> int | None:
    """Return attached day-cardio minutes, or ``None`` before cardio is attached."""
    cardio = _value(day, "cardio")
    if cardio is None:
        return None
    return max(0, int(_value(cardio, "duration_minutes", 0) or 0))


def calculate_total_session_minutes(day: object) -> int:
    """Return the stored total session estimate, including all attached add-ons."""
    return max(0, int(_value(day, "estimated_duration_minutes", 0) or 0))


def calculate_total_session_minutes_from_exercises(
    exercises: Iterable[object],
    general_warmup_minutes: int,
    cardio_minutes: int = 0,
) -> int:
    """Build a total session estimate from all programmed work and external add-ons."""
    return max(
        0,
        general_warmup_minutes
        + sum(max(0, int(_value(exercise, "estimated_minutes", 0) or 0)) for exercise in exercises)
        + cardio_minutes,
    )


def calculate_resistance_minutes(day: "Any", general_warmup_minutes: int) -> int:
    """Deprecated compatibility wrapper for main-training minutes."""
    del general_warmup_minutes
    return calculate_main_training_minutes(day)


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
