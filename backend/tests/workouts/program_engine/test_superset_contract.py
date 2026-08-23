from uuid import uuid4

from app.exercises.enums import ExerciseType, MovementPattern, MuscleGroup
from app.workouts.models import WorkoutPlanExercise
from app.workouts.program_engine.schemas import ProgrammedExercise
from app.workouts.schemas import WorkoutPlanExerciseResponse


def _programmed_exercise(*, superset_group: str | None) -> ProgrammedExercise:
    return ProgrammedExercise(
        exercise_id=uuid4(),
        exercise_name="Cable Curl",
        order=1,
        sets=3,
        rep_min=10,
        rep_max=15,
        target_rir=1,
        rest_seconds=75,
        estimated_minutes=5,
        reason_codes=("TEST",),
        movement_pattern=MovementPattern.ELBOW_FLEXION,
        primary_muscle=MuscleGroup.BICEPS,
        exercise_type=ExerciseType.ISOLATION,
        superset_group=superset_group,
    )


def test_programmed_exercise_exposes_nullable_superset_group() -> None:
    grouped = _programmed_exercise(superset_group="pair-a")
    straight_sets = _programmed_exercise(superset_group=None)

    assert grouped.superset_group == "pair-a"
    assert straight_sets.superset_group is None


def test_persistence_model_has_nullable_superset_group_column() -> None:
    column = WorkoutPlanExercise.__table__.columns["superset_group"]

    assert column.nullable is True
    assert column.type.length == 32


def test_api_schema_serializes_superset_group() -> None:
    response = WorkoutPlanExerciseResponse.model_validate(
        {
            "id": str(uuid4()),
            "order_index": 1,
            "sets": 3,
            "prescription_mode": "reps",
            "reps_min": 10,
            "reps_max": 15,
            "rest_seconds": 75,
            "rir": 1,
            "estimated_minutes": 5,
            "notes_en": None,
            "notes_fa": None,
            "superset_group": "pair-a",
            "exercise": {
                "id": str(uuid4()),
                "slug": "cable-curl",
                "name_en": "Cable Curl",
                "name_fa": "جلو بازو سیم کش",
                "body_region": "upper_body",
                "primary_muscle": "biceps",
                "secondary_muscles": [],
                "equipment": ["cable"],
                "difficulty": "beginner",
                "media_path": "/media/cable-curl.gif",
                "media_type": "gif",
            },
            "alternatives": [],
        }
    )

    assert response.superset_group == "pair-a"
