from uuid import UUID, uuid4

from app.ai.schemas import (
    WorkoutPlanDayOutput,
    WorkoutPlanExerciseOutput,
    WorkoutPlanModelOutput,
)
from app.exercises.enums import Difficulty, Equipment, ExerciseType, MovementPattern, MuscleGroup
from app.workouts.normalizer import normalize_workout_plan
from app.workouts.schemas import CandidateSet, WorkoutExerciseCandidate


def _candidate(exercise_id: UUID, exercise_type: ExerciseType) -> WorkoutExerciseCandidate:
    return WorkoutExerciseCandidate(
        id=exercise_id,
        primary_muscle=MuscleGroup.CHEST,
        secondary_muscles=(),
        movement_pattern=MovementPattern.HORIZONTAL_PUSH,
        exercise_type=exercise_type,
        equipment=(Equipment.BODYWEIGHT,),
        difficulty=Difficulty.BEGINNER,
        caution_tags=(),
    )


def _exercise(exercise_id: UUID) -> WorkoutPlanExerciseOutput:
    return WorkoutPlanExerciseOutput(
        exercise_id=exercise_id,
        sets=3,
        reps_min=8,
        reps_max=12,
        rest_seconds=90,
        rir=2,
        estimated_minutes=8,
        notes_en=None,
        notes_fa=None,
    )


def test_normalizer_moves_compounds_first_and_preserves_group_order() -> None:
    isolation_one, compound_one, core, compound_two, isolation_two = (
        uuid4(),
        uuid4(),
        uuid4(),
        uuid4(),
        uuid4(),
    )
    candidates = CandidateSet(
        exercises=(
            _candidate(isolation_one, ExerciseType.ISOLATION),
            _candidate(compound_one, ExerciseType.COMPOUND),
            _candidate(core, ExerciseType.CORE),
            _candidate(compound_two, ExerciseType.COMPOUND),
            _candidate(isolation_two, ExerciseType.ISOLATION),
        ),
        candidate_set_hash="a" * 64,
        soft_cautions=(),
        minimum_candidate_count=1,
    )
    plan = WorkoutPlanModelOutput(
        days=[
            WorkoutPlanDayOutput(
                day_number=1,
                title_en="Mixed",
                title_fa="ترکیبی",
                estimated_duration_minutes=40,
                exercises=[
                    _exercise(isolation_one),
                    _exercise(compound_one),
                    _exercise(core),
                    _exercise(compound_two),
                    _exercise(isolation_two),
                ],
            )
        ]
    )

    normalized = normalize_workout_plan(plan, candidates)

    assert [item.exercise_id for item in normalized.days[0].exercises] == [
        compound_one,
        compound_two,
        isolation_one,
        core,
        isolation_two,
    ]
    assert [item.exercise_id for item in plan.days[0].exercises] == [
        isolation_one,
        compound_one,
        core,
        compound_two,
        isolation_two,
    ]
