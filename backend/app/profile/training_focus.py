from collections.abc import Iterable

from app.exercises.enums import MuscleGroup

MAX_USER_PRIORITY_MUSCLES = 1

# This is a product choice, not a mirror of the internal MuscleGroup enum.
USER_SELECTABLE_PRIORITY_MUSCLES: tuple[MuscleGroup, ...] = (
    MuscleGroup.CHEST,
    MuscleGroup.BACK,
    MuscleGroup.SHOULDERS,
    MuscleGroup.BICEPS,
    MuscleGroup.TRICEPS,
    MuscleGroup.GLUTES,
    MuscleGroup.QUADRICEPS,
    MuscleGroup.HAMSTRINGS,
    MuscleGroup.CALVES,
)
USER_SELECTABLE_PRIORITY_MUSCLE_SET = frozenset(USER_SELECTABLE_PRIORITY_MUSCLES)


def validate_user_priority_muscles(
    values: Iterable[MuscleGroup | str] | None,
) -> tuple[MuscleGroup, ...] | None:
    if values is None:
        return None

    normalized: list[MuscleGroup] = []
    for value in values:
        try:
            muscle = value if isinstance(value, MuscleGroup) else MuscleGroup(value)
        except ValueError as error:
            raise ValueError("Priority muscles must contain valid muscle values") from error
        normalized.append(muscle)

    if len(normalized) != len(set(normalized)):
        raise ValueError("Priority muscles must be unique")
    if len(normalized) > MAX_USER_PRIORITY_MUSCLES:
        raise ValueError("At most one priority muscle may be selected")
    if any(muscle not in USER_SELECTABLE_PRIORITY_MUSCLE_SET for muscle in normalized):
        raise ValueError("Priority muscle is not user-selectable")
    if not normalized:
        return None
    return tuple(sorted(normalized, key=lambda muscle: muscle.value))
