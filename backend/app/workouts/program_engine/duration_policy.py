from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import cast, get_args

from app.exercises.enums import ExerciseLabel, ExerciseType
from app.profile.schemas import SessionDurationMinutes
from app.workouts.program_engine.rulesets.resistance_training_v1 import ProgramRuleset


def _value(item: object, field: str, default: object = None) -> object:
    if isinstance(item, Mapping):
        return item.get(field, default)
    return getattr(item, field, default)


def _minutes(value: object) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int | float):
        return int(value)
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return 0
    return 0


def _exercise_items(value: object) -> Iterable[object]:
    exercises = _value(value, "exercises", value)
    if isinstance(exercises, Iterable) and not isinstance(exercises, (str, bytes)):
        return exercises
    return ()


def _enum_value(value: object) -> object:
    return getattr(value, "value", value)


def _is_cardio_exercise(exercise: object) -> bool:
    if _enum_value(_value(exercise, "exercise_type")) == "cardio":
        return True
    labels = _value(exercise, "labels", ())
    if not isinstance(labels, Iterable) or isinstance(labels, (str, bytes)):
        return False
    return any(
        _enum_value(label) == ExerciseLabel.CARDIO.value for label in cast(Iterable[object], labels)
    )


def is_main_training_exercise(exercise: object) -> bool:
    """Return whether an exercise contributes to the requested main-training time."""
    exercise_type = _enum_value(_value(exercise, "exercise_type"))
    if exercise_type == ExerciseType.CORE.value or _is_cardio_exercise(exercise):
        return False
    return True


def calculate_main_training_minutes_from_exercises(exercises: Iterable[object]) -> int:
    """Sum programmed exercise time, excluding only anatomical core and cardio."""
    return sum(
        max(0, _minutes(_value(exercise, "estimated_minutes", 0)))
        for exercise in exercises
        if is_main_training_exercise(exercise)
    )


def calculate_main_training_minutes(day: object) -> int:
    """Return a day's main-training minutes without warm-up, core, or cardio add-ons."""
    return calculate_main_training_minutes_from_exercises(_exercise_items(day))


def calculate_core_addon_minutes(value: object) -> int:
    """Return anatomical core exercise minutes that sit outside main training."""
    return sum(
        max(0, _minutes(_value(exercise, "estimated_minutes", 0)))
        for exercise in _exercise_items(value)
        if _enum_value(_value(exercise, "exercise_type")) == ExerciseType.CORE.value
    )


def calculate_cardio_addon_minutes(day: object) -> int | None:
    """Return attached or embedded cardio minutes, or ``None`` before attachment."""
    cardio = _value(day, "cardio")
    embedded_minutes = sum(
        max(0, _minutes(_value(exercise, "estimated_minutes", 0)))
        for exercise in _exercise_items(day)
        if _is_cardio_exercise(exercise)
    )
    if cardio is None and embedded_minutes == 0:
        return None
    attached_minutes = (
        0 if cardio is None else max(0, _minutes(_value(cardio, "duration_minutes", 0)))
    )
    return attached_minutes + embedded_minutes


def calculate_total_session_minutes(day: object) -> int:
    """Return the stored total session estimate, including all attached add-ons."""
    return max(0, _minutes(_value(day, "estimated_duration_minutes", 0)))


def calculate_total_session_minutes_from_exercises(
    exercises: Iterable[object],
    general_warmup_minutes: int,
    cardio_minutes: int = 0,
) -> int:
    """Build a total session estimate from all programmed work and external add-ons."""
    return max(
        0,
        general_warmup_minutes
        + sum(max(0, _minutes(_value(exercise, "estimated_minutes", 0))) for exercise in exercises)
        + cardio_minutes,
    )


SESSION_DURATION_TOLERANCE_MINUTES = 10
SHORT_SESSION_MINIMUM_MAIN_EXERCISES = 3
SHORT_SESSION_MAXIMUM_MAIN_EXERCISES = 4

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
    return get_session_exercise_count_policy(
        session_duration_minutes, ruleset
    ).minimum_main_exercises


def effective_main_exercise_ceiling(
    session_duration_minutes: int,
    ruleset: ProgramRuleset,
) -> int:
    return get_session_exercise_count_policy(
        session_duration_minutes, ruleset
    ).maximum_main_exercises


@dataclass(frozen=True)
class SessionExerciseCountPolicy:
    requested_minutes: int
    minimum_main_exercises: int
    maximum_main_exercises: int

    def contains(self, main_count: int) -> bool:
        return self.minimum_main_exercises <= main_count <= self.maximum_main_exercises


def get_session_exercise_count_policy(
    requested_minutes: int,
    ruleset: ProgramRuleset | None = None,
) -> SessionExerciseCountPolicy:
    """Return hard MAIN exercise bounds for a supported session duration."""
    effective_ruleset = ruleset or ProgramRuleset()
    short_session = requested_minutes <= effective_ruleset.short_session_minutes
    return SessionExerciseCountPolicy(
        requested_minutes=requested_minutes,
        minimum_main_exercises=(
            SHORT_SESSION_MINIMUM_MAIN_EXERCISES
            if short_session
            else effective_ruleset.minimum_exercises_per_session
        ),
        maximum_main_exercises=(
            SHORT_SESSION_MAXIMUM_MAIN_EXERCISES
            if short_session
            else effective_ruleset.max_exercises_per_session
        ),
    )


@dataclass(frozen=True)
class SessionDurationPolicy:
    requested_minutes: int
    minimum_minutes: int
    maximum_minutes: int

    def below_preferred_minimum(self, estimated_minutes: int) -> bool:
        """Return whether the session is below the preferred lower target."""
        return estimated_minutes < self.minimum_minutes

    def exceeds_hard_maximum(self, estimated_minutes: int) -> bool:
        """Return whether the session exceeds the hard upper target."""
        return estimated_minutes > self.maximum_minutes

    def within_preferred_range(self, estimated_minutes: int) -> bool:
        """Return whether the session fits the preferred diagnostic range."""
        return not (
            self.below_preferred_minimum(estimated_minutes)
            or self.exceeds_hard_maximum(estimated_minutes)
        )

    def contains(self, estimated_minutes: int) -> bool:
        """Compatibility alias for preferred-range quality diagnostics."""
        return self.within_preferred_range(estimated_minutes)


def under_target_message_fa(actual_minutes: int) -> str:
    return f"برنامه اصولی با توجه به سطح و شرایط شما در {actual_minutes} دقیقه ساخته شد."


def get_session_duration_policy(
    requested_minutes: int,
) -> SessionDurationPolicy:
    # Long sessions have a wider lower bound so legitimate programming is not
    # rejected for modest underfill, while the upper hard limit remains +10.
    lower_tolerance = {
        75: 15,
        90: 25,
    }.get(requested_minutes, SESSION_DURATION_TOLERANCE_MINUTES)
    return SessionDurationPolicy(
        requested_minutes=requested_minutes,
        minimum_minutes=requested_minutes - lower_tolerance,
        maximum_minutes=requested_minutes + SESSION_DURATION_TOLERANCE_MINUTES,
    )
