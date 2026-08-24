from collections.abc import Iterable

from app.exercises.enums import Equipment, MovementPattern
from app.profile.enums import HomeTrainingSetup, TrainingLocation


def resolve_available_equipment(
    training_location: TrainingLocation,
    home_training_setup: HomeTrainingSetup | None,
    explicit_inventory: Iterable[Equipment | str] | None,
) -> frozenset[Equipment]:
    """Resolve the one effective equipment inventory used by workout paths."""
    if explicit_inventory is not None:
        return frozenset(Equipment(item) for item in explicit_inventory)
    if training_location is TrainingLocation.GYM:
        return frozenset(item for item in Equipment if item is not Equipment.OTHER)
    if home_training_setup is HomeTrainingSetup.DUMBBELLS_AVAILABLE:
        return frozenset({Equipment.BODYWEIGHT, Equipment.DUMBBELL})
    return frozenset({Equipment.BODYWEIGHT})


def effective_required_equipment(
    equipment: Iterable[Equipment],
    movement_pattern: MovementPattern,
) -> frozenset[Equipment]:
    """Return catalog equipment plus conservative requirements for known gaps."""
    required = set(equipment)
    if (
        movement_pattern is MovementPattern.VERTICAL_PULL
        and Equipment.BODYWEIGHT in required
        and Equipment.PULL_UP_BAR not in required
    ):
        required.add(Equipment.PULL_UP_BAR)
    return frozenset(required)
