from collections import Counter
from uuid import uuid4

from app.exercises.enums import ExerciseType, MovementPattern, MuscleGroup
from app.workouts.program_engine.normalization import normalize_request
from app.workouts.program_engine.rulesets.resistance_training_v1 import RULESET
from app.workouts.program_engine.schemas import ProgrammedExercise, WorkoutDay
from app.workouts.program_engine.session_structure import finalize_session_structure
from app.workouts.program_engine.supplemental_policy import main_exercise_count
from tests.workouts.program_engine.golden_fixtures import request


def _day(index: int, count: int) -> WorkoutDay:
    exercises = tuple(
        ProgrammedExercise(
            exercise_id=uuid4(),
            exercise_name=f"Exercise {index}-{order}",
            order=order,
            sets=2,
            rep_min=8,
            rep_max=12,
            target_rir=2,
            rest_seconds=90,
            estimated_minutes=5,
            reason_codes=("TEST",),
            movement_pattern=MovementPattern.HORIZONTAL_PUSH,
            primary_muscle=MuscleGroup.CHEST,
            exercise_type=ExerciseType.COMPOUND,
        )
        for order in range(1, count + 1)
    )
    return WorkoutDay(
        day_index=index,
        weekday=index,
        title=f"Day {index}",
        focus="full_body_a",
        estimated_duration_minutes=30,
        exercises=exercises,
    )


def test_unequal_valid_main_counts_are_preserved_by_session_boundary() -> None:
    days = tuple(_day(index, count) for index, count in enumerate((5, 7, 6, 5), start=1))
    before_counts = tuple(main_exercise_count(day.exercises) for day in days)
    before_ids = Counter(item.exercise_id for day in days for item in day.exercises)

    finalized = finalize_session_structure(
        days,
        normalize_request(request(available_training_days=4), RULESET),
        RULESET,
    )

    assert before_counts == (5, 7, 6, 5)
    assert tuple(main_exercise_count(day.exercises) for day in finalized) == before_counts
    assert Counter(item.exercise_id for day in finalized for item in day.exercises) == before_ids
