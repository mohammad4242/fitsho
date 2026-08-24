from app.exercises.enums import Equipment
from app.profile.enums import HomeTrainingSetup, TrainingLocation
from app.workouts.program_engine.equipment import resolve_available_equipment


def test_explicit_inventory_is_canonical() -> None:
    assert resolve_available_equipment(
        TrainingLocation.HOME,
        HomeTrainingSetup.DUMBBELLS_AVAILABLE,
        (Equipment.BODYWEIGHT, Equipment.RESISTANCE_BAND, Equipment.BENCH),
    ) == frozenset(
        {Equipment.BODYWEIGHT, Equipment.RESISTANCE_BAND, Equipment.BENCH}
    )


def test_legacy_home_inventory_remains_backward_compatible() -> None:
    assert resolve_available_equipment(
        TrainingLocation.HOME,
        HomeTrainingSetup.BODYWEIGHT_ONLY,
        None,
    ) == frozenset({Equipment.BODYWEIGHT})
    assert resolve_available_equipment(
        TrainingLocation.HOME,
        HomeTrainingSetup.DUMBBELLS_AVAILABLE,
        None,
    ) == frozenset({Equipment.BODYWEIGHT, Equipment.DUMBBELL})


def test_legacy_gym_inventory_excludes_uncategorized_equipment() -> None:
    available = resolve_available_equipment(TrainingLocation.GYM, None, None)

    assert Equipment.OTHER not in available
    assert available == frozenset(item for item in Equipment if item is not Equipment.OTHER)
