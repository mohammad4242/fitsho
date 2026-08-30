from enum import IntEnum

from app.exercises.enums import MuscleGroup
from app.workouts.program_engine.session_coherence import SessionCoherence, SessionMuscleRole


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
    # Generic structural sessions remain compatibility contexts, not explicit-priority
    # contexts.  Their direct scope/hierarchy still comes from SessionCoherence.
    if focus.startswith("upper") or focus.startswith("full_body"):
        return FocusAffinity.NONE
    role = SessionCoherence.from_dynamic_focus(focus).role_for(muscle)
    if role is SessionMuscleRole.DISALLOWED:
        return FocusAffinity.NONE
    if focus in {"push", "pull", "lower", "legs"}:
        return FocusAffinity.GROUPED
    if role is SessionMuscleRole.PRIMARY:
        return FocusAffinity.DEDICATED
    return FocusAffinity.GROUPED
