from uuid import UUID

from app.ai.schemas import WorkoutPlanModelOutput
from app.exercises.enums import ExerciseType
from app.workouts.schemas import CandidateSet


def normalize_workout_plan(
    plan: WorkoutPlanModelOutput,
    candidates: CandidateSet,
) -> WorkoutPlanModelOutput:
    candidate_by_id = {candidate.id: candidate for candidate in candidates.exercises}

    def order_rank(exercise_id: UUID) -> int:
        candidate = candidate_by_id.get(exercise_id)
        is_compound = candidate is not None and candidate.exercise_type is ExerciseType.COMPOUND
        return 0 if is_compound else 1

    return plan.model_copy(
        update={
            "days": [
                day.model_copy(
                    update={
                        "exercises": sorted(
                            day.exercises,
                            key=lambda exercise: order_rank(exercise.exercise_id),
                        )
                    }
                )
                for day in plan.days
            ]
        }
    )
