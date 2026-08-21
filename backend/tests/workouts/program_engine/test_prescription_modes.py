from uuid import uuid4

import pytest

from app.exercises.enums import (
    Difficulty,
    Equipment,
    ExerciseType,
    MovementPattern,
    MuscleGroup,
    PrescriptionMode,
)
from app.profile.enums import TrainingLocation
from app.workouts.program_engine.engine import generate_program
from app.workouts.program_engine.enums import Goal, TrainingExperience
from app.workouts.program_engine.rulesets.resistance_training_v1 import RULESET
from app.workouts.program_engine.schemas import (
    ExerciseCandidate,
    ProgramGenerationRequest,
    ProgrammedExercise,
)
from app.workouts.schemas import WorkoutPlanExerciseResponse
from tests.workouts.program_engine.test_prescription_validation import catalog


def _duration_candidate(
    *,
    name: str = "Front Plank",
    pattern: MovementPattern = MovementPattern.CORE_ANTI_EXTENSION,
) -> ExerciseCandidate:
    return ExerciseCandidate(
        id=uuid4(),
        name=name,
        primary_muscle=MuscleGroup.ABS,
        secondary_muscles=(),
        movement_pattern=pattern,
        exercise_type=ExerciseType.CORE,
        equipment=frozenset({Equipment.BODYWEIGHT}),
        difficulty=Difficulty.BEGINNER,
        prescription_mode=PrescriptionMode.DURATION,
        duration_min_seconds=20,
        duration_max_seconds=40,
    )


def _request() -> ProgramGenerationRequest:
    return ProgramGenerationRequest.model_validate(
        {
            "user_id": uuid4(),
            "age": 30,
            "height_cm": 175,
            "weight_kg": 75,
            "primary_goal": Goal.GENERAL_FITNESS,
            "training_experience": TrainingExperience.BEGINNER,
            "training_age_months": 3,
            "available_training_days": 1,
            "session_duration_minutes": 45,
            "available_equipment": [Equipment.BODYWEIGHT],
            "training_location": TrainingLocation.HOME,
            "seed_optional": 99,
        }
    )


def test_duration_programmed_exercise_has_no_repetition_or_rir_values() -> None:
    exercise = ProgrammedExercise(
        exercise_id=uuid4(),
        exercise_name="Front Plank",
        order=1,
        sets=2,
        rep_min=None,
        rep_max=None,
        duration_min_seconds=20,
        duration_max_seconds=40,
        prescription_mode=PrescriptionMode.DURATION,
        target_rir=None,
        rest_seconds=60,
        estimated_minutes=4,
        reason_codes=("TEST",),
    )

    assert exercise.prescription_mode is PrescriptionMode.DURATION
    assert (exercise.duration_min_seconds, exercise.duration_max_seconds) == (20, 40)
    assert exercise.rep_min is None
    assert exercise.rep_max is None
    assert exercise.target_rir is None


def test_duration_prescription_uses_catalog_metadata_in_generate_program() -> None:
    candidates = catalog()
    candidates[4] = _duration_candidate()

    result = generate_program(_request(), candidates, RULESET)

    assert result.program is not None, result.errors
    plank = next(
        item
        for day in result.program.weekly_schedule
        for item in day.exercises
        if item.exercise_id == candidates[4].id
    )
    assert plank.prescription_mode is PrescriptionMode.DURATION
    assert (plank.duration_min_seconds, plank.duration_max_seconds) == (20, 40)
    assert plank.rep_min is None
    assert plank.rep_max is None
    assert plank.target_rir is None


def test_side_plank_is_duration_based_in_generate_program() -> None:
    candidates = catalog()
    candidates[4] = _duration_candidate(
        name="Side Plank",
        pattern=MovementPattern.CORE_ANTI_LATERAL_FLEXION,
    )

    result = generate_program(_request(), candidates, RULESET)

    assert result.program is not None, result.errors
    plank = next(
        item
        for day in result.program.weekly_schedule
        for item in day.exercises
        if item.exercise_id == candidates[4].id
    )
    assert plank.prescription_mode is PrescriptionMode.DURATION
    assert (plank.duration_min_seconds, plank.duration_max_seconds) == (20, 40)
    assert plank.rep_min is None
    assert plank.rep_max is None
    assert plank.target_rir is None


def test_rep_based_programmed_exercise_keeps_existing_contract() -> None:
    exercise = ProgrammedExercise(
        exercise_id=uuid4(),
        exercise_name="Squat",
        order=1,
        sets=3,
        rep_min=8,
        rep_max=12,
        prescription_mode=PrescriptionMode.REPS,
        target_rir=2,
        rest_seconds=90,
        estimated_minutes=5,
        reason_codes=("TEST",),
    )

    assert exercise.prescription_mode is PrescriptionMode.REPS
    assert (exercise.rep_min, exercise.rep_max) == (8, 12)
    assert exercise.duration_min_seconds is None
    assert exercise.duration_max_seconds is None
    assert exercise.target_rir == 2


def test_programmed_exercise_rejects_mixed_mode_values() -> None:
    with pytest.raises(ValueError, match="duration prescriptions"):
        ProgrammedExercise(
            exercise_id=uuid4(),
            exercise_name="Front Plank",
            order=1,
            sets=2,
            rep_min=8,
            rep_max=None,
            duration_min_seconds=20,
            duration_max_seconds=40,
            prescription_mode=PrescriptionMode.DURATION,
            target_rir=None,
            rest_seconds=60,
            estimated_minutes=4,
            reason_codes=("TEST",),
        )


def test_api_schema_serializes_duration_prescription() -> None:
    response = WorkoutPlanExerciseResponse.model_validate(
        {
                "id": str(uuid4()),
                "order_index": 1,
                "sets": 2,
                "prescription_mode": "duration",
                "reps_min": None,
                "reps_max": None,
                "duration_min_seconds": 20,
                "duration_max_seconds": 40,
                "rest_seconds": 60,
                "rir": None,
                "estimated_minutes": 4,
                "notes_en": None,
                "notes_fa": None,
                "exercise": {
                    "id": str(uuid4()),
                    "slug": "front-plank",
                    "name_en": "Front Plank",
                    "name_fa": "پلانک جلو",
                    "body_region": "core",
                    "primary_muscle": "abs",
                    "muscle_focus": "anti_extension",
                    "labels": [],
                    "secondary_muscles": [],
                    "equipment": ["bodyweight"],
                    "difficulty": "beginner",
                    "media_path": "/media/front-plank.gif",
                    "media_type": "gif",
                },
                "alternatives": [],
        }
    )

    assert response.prescription_mode == "duration"
    assert response.duration_min_seconds == 20
    assert response.duration_max_seconds == 40
    assert response.reps_min is None
    assert response.reps_max is None
    assert response.rir is None
