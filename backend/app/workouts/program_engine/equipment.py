from collections.abc import Iterable

from app.exercises.enums import Equipment, MovementPattern


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
