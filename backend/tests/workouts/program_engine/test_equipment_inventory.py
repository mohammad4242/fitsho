import pytest

from app.exercises.enums import Equipment
from app.profile.enums import HomeTrainingSetup, TrainingLocation
from app.workouts.program_engine.equipment import resolve_available_equipment


def test_explicit_inventory_is_canonical() -> None:
    assert resolve_available_equipment(
        TrainingLocation.HOME,
        HomeTrainingSetup.DUMBBELLS_AVAILABLE,
        (Equipment.BODYWEIGHT, Equipment.RESISTANCE_BAND, Equipment.BENCH),
    ) == frozenset(
        {
            Equipment.BODYWEIGHT,
            Equipment.RESISTANCE_BAND,
            Equipment.BENCH,
            Equipment.PULL_UP_BAR,
        }
    )


@pytest.mark.parametrize(
    ("setup", "expected"),
    [
        (
            HomeTrainingSetup.BODYWEIGHT_ONLY,
            {Equipment.BODYWEIGHT, Equipment.PULL_UP_BAR},
        ),
        (
            HomeTrainingSetup.DUMBBELLS_AVAILABLE,
            {Equipment.BODYWEIGHT, Equipment.DUMBBELL, Equipment.PULL_UP_BAR},
        ),
        (
            HomeTrainingSetup.RESISTANCE_BANDS_AVAILABLE,
            {Equipment.BODYWEIGHT, Equipment.RESISTANCE_BAND, Equipment.PULL_UP_BAR},
        ),
        (
            HomeTrainingSetup.DUMBBELLS_AND_RESISTANCE_BANDS_AVAILABLE,
            {
                Equipment.BODYWEIGHT,
                Equipment.DUMBBELL,
                Equipment.RESISTANCE_BAND,
                Equipment.PULL_UP_BAR,
            },
        ),
    ],
)
def test_home_setup_maps_to_canonical_inventory(
    setup: HomeTrainingSetup, expected: set[Equipment]
) -> None:
    assert resolve_available_equipment(TrainingLocation.HOME, setup, None) == frozenset(expected)


def test_legacy_home_inventory_remains_backward_compatible() -> None:
    assert resolve_available_equipment(
        TrainingLocation.HOME,
        HomeTrainingSetup.BODYWEIGHT_ONLY,
        None,
    ) == frozenset({Equipment.BODYWEIGHT, Equipment.PULL_UP_BAR})
    assert resolve_available_equipment(
        TrainingLocation.HOME,
        HomeTrainingSetup.DUMBBELLS_AVAILABLE,
        None,
    ) == frozenset({Equipment.BODYWEIGHT, Equipment.DUMBBELL, Equipment.PULL_UP_BAR})


@pytest.mark.parametrize(
    ("explicit_inventory", "expected"),
    [
        (
            (Equipment.BODYWEIGHT,),
            {Equipment.BODYWEIGHT, Equipment.PULL_UP_BAR},
        ),
        (
            (Equipment.BODYWEIGHT, Equipment.DUMBBELL),
            {Equipment.BODYWEIGHT, Equipment.DUMBBELL, Equipment.PULL_UP_BAR},
        ),
        (
            (Equipment.BODYWEIGHT, Equipment.RESISTANCE_BAND),
            {Equipment.BODYWEIGHT, Equipment.RESISTANCE_BAND, Equipment.PULL_UP_BAR},
        ),
    ],
)
def test_explicit_bodyweight_inventory_always_adds_pull_up_bar(
    explicit_inventory: tuple[Equipment, ...], expected: set[Equipment]
) -> None:
    assert resolve_available_equipment(
        TrainingLocation.HOME,
        HomeTrainingSetup.BODYWEIGHT_ONLY,
        explicit_inventory,
    ) == frozenset(expected)


def test_legacy_gym_inventory_excludes_uncategorized_equipment() -> None:
    available = resolve_available_equipment(TrainingLocation.GYM, None, None)

    assert Equipment.OTHER not in available
    assert available == frozenset(item for item in Equipment if item is not Equipment.OTHER)
