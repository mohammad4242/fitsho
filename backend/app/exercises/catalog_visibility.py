from sqlalchemy.sql.elements import ColumnElement

from app.exercises.enums import ExerciseLabel, ExerciseType
from app.exercises.models import Exercise, ExerciseLabelItem

SPECIAL_LABELS = (ExerciseLabel.CARDIO, ExerciseLabel.FULL_BODY)


def should_exclude_special_categories(
    labels: list[ExerciseLabel] | None,
    exercise_type: ExerciseType | None,
) -> bool:
    return not labels and exercise_type is not ExerciseType.MOBILITY


def normal_catalog_exclusion_conditions() -> tuple[ColumnElement[bool], ...]:
    return (
        ~Exercise.labels.any(ExerciseLabelItem.label.in_(SPECIAL_LABELS)),
        Exercise.exercise_type != ExerciseType.MOBILITY,
    )
