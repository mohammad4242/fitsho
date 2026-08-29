from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import cast

from app.exercises.enums import ExerciseLabel, ExerciseType, MuscleGroup

SUPPLEMENTAL_MUSCLES = frozenset(
    {
        MuscleGroup.FOREARMS,
        MuscleGroup.ABS,
        MuscleGroup.OBLIQUES,
        MuscleGroup.LOWER_BACK,
        MuscleGroup.NECK,
    }
)

_SUPPLEMENTAL_CONTEXTS: dict[MuscleGroup, frozenset[str]] = {
    MuscleGroup.FOREARMS: frozenset({"pull", "back_biceps"}),
    MuscleGroup.ABS: frozenset(
        {
            "lower",
            "legs",
            "posterior_chain_core",
            "quadriceps_calves",
        }
    ),
    MuscleGroup.OBLIQUES: frozenset(
        {
            "lower",
            "legs",
            "posterior_chain_core",
            "quadriceps_calves",
        }
    ),
    MuscleGroup.LOWER_BACK: frozenset(
        {"pull", "back_biceps", "lower", "legs", "posterior_chain_core"}
    ),
    MuscleGroup.NECK: frozenset({"upper", "shoulders_traps"}),
}


def is_supplemental_muscle(muscle: MuscleGroup | None) -> bool:
    return muscle in SUPPLEMENTAL_MUSCLES


def _structured_value(item: object, field: str) -> object | None:
    """Read exercise metadata from direct items and response/persistence wrappers."""
    current = item
    for _ in range(3):
        if isinstance(current, Mapping):
            snapshot = current.get("exercise_snapshot")
            value = current.get(field)
            nested = current.get("exercise")
        else:
            snapshot = getattr(current, "exercise_snapshot", None)
            value = getattr(current, field, None)
            nested = getattr(current, "exercise", None)
        if isinstance(snapshot, Mapping) and snapshot and field in snapshot:
            return cast(object, snapshot[field])
        if value is not None:
            return cast(object, value)
        if nested is None or nested is current:
            return None
        current = nested
    return None


def _enum_value(value: object | None) -> object | None:
    return getattr(value, "value", value)


def _is_cardio(item: object) -> bool:
    if _enum_value(_structured_value(item, "exercise_type")) == ExerciseType.CORE.value:
        return False
    labels = _structured_value(item, "labels")
    if not isinstance(labels, Iterable) or isinstance(labels, (str, bytes)):
        return False
    return any(_enum_value(label) == ExerciseLabel.CARDIO.value for label in labels)


def is_main_resistance_exercise(exercise: object) -> bool:
    """Return whether structured exercise metadata classifies an item as MAIN."""
    exercise_type = _enum_value(_structured_value(exercise, "exercise_type"))
    primary_muscle = _enum_value(_structured_value(exercise, "primary_muscle"))
    return (
        exercise_type in {ExerciseType.COMPOUND.value, ExerciseType.ISOLATION.value}
        and primary_muscle is not None
        and primary_muscle not in {muscle.value for muscle in SUPPLEMENTAL_MUSCLES}
        and not _is_cardio(exercise)
    )


def is_core_or_supplemental_exercise(exercise: object) -> bool:
    """Return whether an item is anatomical CORE or supplemental-muscle work."""
    exercise_type = _enum_value(_structured_value(exercise, "exercise_type"))
    primary_muscle = _enum_value(_structured_value(exercise, "primary_muscle"))
    return exercise_type == ExerciseType.CORE.value or primary_muscle in {
        muscle.value for muscle in SUPPLEMENTAL_MUSCLES
    }


@dataclass(frozen=True, slots=True)
class ExerciseCountBreakdown:
    """Canonical counts for a session's structured exercise items."""

    main_count: int
    supplemental_count: int
    total_count: int

    @property
    def main(self) -> int:
        return self.main_count

    @property
    def supplemental(self) -> int:
        return self.supplemental_count

    @property
    def total(self) -> int:
        return self.total_count


def exercise_count_breakdown(exercises: Iterable[object]) -> ExerciseCountBreakdown:
    items = tuple(exercises)
    return ExerciseCountBreakdown(
        main_count=sum(is_main_resistance_exercise(item) for item in items),
        supplemental_count=sum(is_core_or_supplemental_exercise(item) for item in items),
        total_count=len(items),
    )


def main_exercise_count(exercises: Iterable[object]) -> int:
    return exercise_count_breakdown(exercises).main_count


def supplemental_reason_codes(
    muscle: MuscleGroup,
    *,
    planned: bool,
) -> tuple[str, ...]:
    if muscle not in SUPPLEMENTAL_MUSCLES:
        raise ValueError("supplemental reason metadata requires a supplemental muscle")
    return (
        "PLANNED_SUPPLEMENTAL_WORK" if planned else "OPTIONAL_SUPPLEMENTAL_WORK",
        f"SUPPLEMENTAL_MUSCLE:{muscle.value}",
    )


def supplemental_muscle_fits_focus(muscle: MuscleGroup, focus: str) -> bool:
    if muscle not in SUPPLEMENTAL_MUSCLES:
        return False
    if focus.startswith("full_body"):
        return muscle is not MuscleGroup.NECK
    if focus.startswith("lower"):
        return muscle in {
            MuscleGroup.ABS,
            MuscleGroup.OBLIQUES,
            MuscleGroup.LOWER_BACK,
        }
    if focus.startswith("upper"):
        return muscle in {MuscleGroup.FOREARMS, MuscleGroup.NECK}
    return focus in _SUPPLEMENTAL_CONTEXTS[muscle]
