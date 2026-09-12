from collections.abc import Iterable

from app.exercises.enums import Equipment, MovementPattern
from app.profile.enums import HomeTrainingSetup, TrainingLocation

HOME_TRAINING_SETUP_EQUIPMENT: dict[HomeTrainingSetup, frozenset[Equipment]] = {
    HomeTrainingSetup.BODYWEIGHT_ONLY: frozenset(
        {Equipment.BODYWEIGHT, Equipment.PULL_UP_BAR}
    ),
    HomeTrainingSetup.DUMBBELLS_AVAILABLE: frozenset(
        {Equipment.BODYWEIGHT, Equipment.PULL_UP_BAR, Equipment.DUMBBELL}
    ),
    HomeTrainingSetup.RESISTANCE_BANDS_AVAILABLE: frozenset(
        {Equipment.BODYWEIGHT, Equipment.PULL_UP_BAR, Equipment.RESISTANCE_BAND}
    ),
    HomeTrainingSetup.DUMBBELLS_AND_RESISTANCE_BANDS_AVAILABLE: frozenset(
        {
            Equipment.BODYWEIGHT,
            Equipment.PULL_UP_BAR,
            Equipment.DUMBBELL,
            Equipment.RESISTANCE_BAND,
        }
    ),
}


def equipment_for_home_training_setup(setup: HomeTrainingSetup) -> frozenset[Equipment]:
    return HOME_TRAINING_SETUP_EQUIPMENT[setup]


def derive_home_training_setup(
    equipment: Iterable[Equipment | str] | None,
) -> HomeTrainingSetup | None:
    if equipment is None:
        return None
    normalized = {Equipment(item) for item in equipment}
    if Equipment.DUMBBELL in normalized and Equipment.RESISTANCE_BAND in normalized:
        return HomeTrainingSetup.DUMBBELLS_AND_RESISTANCE_BANDS_AVAILABLE
    if Equipment.RESISTANCE_BAND in normalized:
        return HomeTrainingSetup.RESISTANCE_BANDS_AVAILABLE
    if Equipment.DUMBBELL in normalized:
        return HomeTrainingSetup.DUMBBELLS_AVAILABLE
    if normalized and normalized <= {Equipment.BODYWEIGHT, Equipment.PULL_UP_BAR}:
        return HomeTrainingSetup.BODYWEIGHT_ONLY
    return None


def normalize_home_equipment(equipment: Iterable[Equipment | str]) -> frozenset[Equipment]:
    normalized = {Equipment(item) for item in equipment}
    if Equipment.BODYWEIGHT in normalized:
        normalized.add(Equipment.PULL_UP_BAR)
    return frozenset(normalized)


def ordered_available_equipment(
    equipment: Iterable[Equipment | str],
) -> tuple[Equipment, ...]:
    selected = {Equipment(item) for item in equipment}
    return tuple(item for item in Equipment if item in selected)


def resolve_available_equipment(
    training_location: TrainingLocation,
    home_training_setup: HomeTrainingSetup | None,
    explicit_inventory: Iterable[Equipment | str] | None,
) -> frozenset[Equipment]:
    """Resolve the one effective equipment inventory used by workout paths."""
    if explicit_inventory is not None:
        explicit = frozenset(Equipment(item) for item in explicit_inventory)
        return (
            normalize_home_equipment(explicit)
            if training_location is TrainingLocation.HOME
            else explicit
        )
    if training_location is TrainingLocation.GYM:
        return frozenset(item for item in Equipment if item is not Equipment.OTHER)
    if home_training_setup is not None:
        return equipment_for_home_training_setup(home_training_setup)
    return equipment_for_home_training_setup(HomeTrainingSetup.BODYWEIGHT_ONLY)


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
