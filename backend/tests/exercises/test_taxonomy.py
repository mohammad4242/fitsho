from app.exercises.enums import BodyRegion, MuscleFocus, MuscleGroup
from app.exercises.models import Exercise
from app.exercises.taxonomy import (
    FOCUSES_BY_MUSCLE,
    MUSCLE_FOCUS_CATEGORIES,
    MUSCLES_BY_REGION,
    is_compatible_muscle_focus,
)


def test_upper_body_has_small_forearm_and_neck_groups() -> None:
    assert hasattr(MuscleGroup, "FOREARMS")
    assert hasattr(MuscleGroup, "NECK")
    assert MuscleGroup.FOREARMS in MUSCLES_BY_REGION[BodyRegion.UPPER_BODY]
    assert MuscleGroup.NECK in MUSCLES_BY_REGION[BodyRegion.UPPER_BODY]


def test_exercise_schema_supports_reviewable_unknown_anatomy_and_labels() -> None:
    assert Exercise.__table__.c.body_region.nullable is True
    assert Exercise.__table__.c.primary_muscle.nullable is True
    assert hasattr(Exercise, "labels")


def test_chest_focuses_are_ordered_for_catalogue() -> None:
    assert FOCUSES_BY_MUSCLE[MuscleGroup.CHEST] == (
        MuscleFocus.GENERAL_CHEST,
        MuscleFocus.UPPER_CHEST,
        MuscleFocus.MID_CHEST,
        MuscleFocus.LOWER_CHEST,
    )


def test_every_muscle_focus_has_a_bilingual_category() -> None:
    categories = {
        category.value: (category.name_en, category.name_fa)
        for values in MUSCLE_FOCUS_CATEGORIES.values()
        for category in values
    }
    assert set(categories) == set(MuscleFocus)
    assert all(name_en and name_fa for name_en, name_fa in categories.values())


def test_focus_compatibility_is_bound_to_primary_muscle() -> None:
    assert is_compatible_muscle_focus(MuscleGroup.CHEST, MuscleFocus.UPPER_CHEST)
    assert not is_compatible_muscle_focus(MuscleGroup.SHOULDERS, MuscleFocus.UPPER_CHEST)
    assert is_compatible_muscle_focus(None, None)
    assert not is_compatible_muscle_focus(MuscleGroup.CHEST, None)
    assert not is_compatible_muscle_focus(None, MuscleFocus.UPPER_CHEST)
