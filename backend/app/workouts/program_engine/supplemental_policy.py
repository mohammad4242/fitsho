from collections.abc import Iterable

from app.exercises.enums import MuscleGroup

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


def main_exercise_count(exercises: Iterable[object]) -> int:
    return sum(
        (muscle := getattr(exercise, "primary_muscle", None)) is not None
        and not is_supplemental_muscle(muscle)
        for exercise in exercises
    )


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
