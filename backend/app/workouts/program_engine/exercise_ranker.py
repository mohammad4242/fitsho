import hashlib

from app.exercises.enums import ExerciseType, MuscleGroup
from app.workouts.program_engine.enums import Goal, StabilityDemand, TrainingStatus
from app.workouts.program_engine.rulesets.resistance_training_v1 import ProgramRuleset
from app.workouts.program_engine.schemas import (
    ExerciseCandidate,
    NormalizedProgramRequest,
    RankedCandidate,
)


def rank_exercises(
    request: NormalizedProgramRequest,
    exercises: list[ExerciseCandidate] | tuple[ExerciseCandidate, ...],
    ruleset: ProgramRuleset,
    *,
    needed_muscle: MuscleGroup | None = None,
) -> tuple[RankedCandidate, ...]:
    ranked: list[tuple[RankedCandidate, str]] = []
    weights = ruleset.selection_weights
    for exercise in exercises:
        score = 0
        reasons: list[str] = []
        if needed_muscle is not None and exercise.primary_muscle is needed_muscle:
            score += weights["movement_need"]
            reasons.append("REQUIRED_MOVEMENT_PATTERN")
        if exercise.primary_muscle in request.source.priority_muscles:
            score += weights["priority_muscle"]
            reasons.append("PRIORITY_MUSCLE")
        if exercise.id in request.source.preferred_exercises:
            score += weights["preference"]
            reasons.append("USER_PREFERRED")
        if exercise.id in request.source.disliked_exercises:
            score += weights["dislike"]
            reasons.append("USER_DISLIKED")
        if request.training_status is TrainingStatus.NOVICE:
            if exercise.stability_demand is StabilityDemand.LOW:
                score += weights["stability"]
                reasons.append("BEGINNER_FRIENDLY")
            if exercise.difficulty.value == "beginner":
                score += weights["beginner_friendly"]
        if request.primary_goal in {Goal.STRENGTH, Goal.GENERAL_FITNESS} and (
            exercise.exercise_type is ExerciseType.COMPOUND
        ):
            score += weights["goal_specificity"]
            reasons.append("GOAL_SPECIFIC")
        if request.primary_goal in {Goal.HYPERTROPHY, Goal.MUSCLE_GAIN}:
            score += weights["goal_specificity"] - exercise.fatigue_cost
            reasons.append("HIGH_STIMULUS_LOW_FATIGUE")
        score += max(0, weights["time_efficiency"] - exercise.setup_cost)
        reasons.extend(("EQUIPMENT_MATCH", "TIME_EFFICIENT"))
        tie_key = hashlib.sha256(f"{request.seed}:{exercise.id}".encode()).hexdigest()
        ranked.append(
            (
                RankedCandidate(
                    exercise=exercise,
                    score=score,
                    reason_codes=tuple(dict.fromkeys(reasons)),
                ),
                tie_key,
            )
        )
    ranked.sort(key=lambda item: (-item[0].score, item[1], str(item[0].exercise.id)))
    return tuple(item[0] for item in ranked)
