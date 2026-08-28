from enum import IntEnum

from app.exercises.enums import MuscleGroup


class FocusAffinity(IntEnum):
    NONE = 0
    GROUPED = 1
    DEDICATED = 2


MUSCLE_SPECIFIC_UPPER_PRIORITIES = frozenset(
    {
        MuscleGroup.CHEST,
        MuscleGroup.BACK,
        MuscleGroup.SHOULDERS,
        MuscleGroup.BICEPS,
        MuscleGroup.TRICEPS,
    }
)


def priority_affinity(focus: str, muscle: MuscleGroup) -> FocusAffinity:
    """Return explicit-priority affinity; session compatibility is a separate concern."""
    if focus.startswith("upper"):
        return FocusAffinity.NONE

    if focus.startswith("full_body"):
        return FocusAffinity.GROUPED if muscle in {
            MuscleGroup.QUADRICEPS,
            MuscleGroup.HAMSTRINGS,
            MuscleGroup.GLUTES,
            MuscleGroup.CALVES,
        } else FocusAffinity.NONE

    affinities: dict[str, dict[MuscleGroup, FocusAffinity]] = {
        "chest_triceps": {
            MuscleGroup.CHEST: FocusAffinity.DEDICATED,
            MuscleGroup.TRICEPS: FocusAffinity.GROUPED,
        },
        "push": {
            MuscleGroup.CHEST: FocusAffinity.GROUPED,
            MuscleGroup.SHOULDERS: FocusAffinity.GROUPED,
            MuscleGroup.TRICEPS: FocusAffinity.GROUPED,
        },
        "back_biceps": {
            MuscleGroup.BACK: FocusAffinity.DEDICATED,
            MuscleGroup.BICEPS: FocusAffinity.GROUPED,
        },
        "pull": {
            MuscleGroup.BACK: FocusAffinity.GROUPED,
            MuscleGroup.BICEPS: FocusAffinity.GROUPED,
        },
        "shoulders_traps": {
            MuscleGroup.SHOULDERS: FocusAffinity.DEDICATED,
            MuscleGroup.TRAPS: FocusAffinity.GROUPED,
        },
        "biceps": {MuscleGroup.BICEPS: FocusAffinity.DEDICATED},
        "triceps": {MuscleGroup.TRICEPS: FocusAffinity.DEDICATED},
        "quadriceps_calves": {
            MuscleGroup.QUADRICEPS: FocusAffinity.DEDICATED,
            MuscleGroup.CALVES: FocusAffinity.GROUPED,
        },
        "posterior_chain_core": {
            MuscleGroup.HAMSTRINGS: FocusAffinity.DEDICATED,
            MuscleGroup.GLUTES: FocusAffinity.GROUPED,
            MuscleGroup.ABS: FocusAffinity.GROUPED,
        },
        "lower": {
            MuscleGroup.QUADRICEPS: FocusAffinity.GROUPED,
            MuscleGroup.HAMSTRINGS: FocusAffinity.GROUPED,
            MuscleGroup.GLUTES: FocusAffinity.GROUPED,
            MuscleGroup.CALVES: FocusAffinity.GROUPED,
            MuscleGroup.ABS: FocusAffinity.GROUPED,
        },
        "legs": {
            MuscleGroup.QUADRICEPS: FocusAffinity.GROUPED,
            MuscleGroup.HAMSTRINGS: FocusAffinity.GROUPED,
            MuscleGroup.GLUTES: FocusAffinity.GROUPED,
            MuscleGroup.CALVES: FocusAffinity.GROUPED,
            MuscleGroup.ABS: FocusAffinity.GROUPED,
        },
    }
    return affinities.get(focus, {}).get(muscle, FocusAffinity.NONE)
