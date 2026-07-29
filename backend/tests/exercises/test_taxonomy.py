from app.exercises.enums import BodyRegion, MuscleGroup
from app.exercises.models import Exercise
from app.exercises.taxonomy import MUSCLES_BY_REGION


def test_upper_body_has_small_forearm_and_neck_groups() -> None:
    assert hasattr(MuscleGroup, "FOREARMS")
    assert hasattr(MuscleGroup, "NECK")
    assert MuscleGroup.FOREARMS in MUSCLES_BY_REGION[BodyRegion.UPPER_BODY]
    assert MuscleGroup.NECK in MUSCLES_BY_REGION[BodyRegion.UPPER_BODY]


def test_exercise_schema_supports_reviewable_unknown_anatomy_and_labels() -> None:
    assert Exercise.__table__.c.body_region.nullable is True
    assert Exercise.__table__.c.primary_muscle.nullable is True
    assert hasattr(Exercise, "labels")
