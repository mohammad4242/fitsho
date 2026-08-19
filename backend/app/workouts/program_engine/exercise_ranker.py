import hashlib

from app.exercises.enums import ExerciseType, MuscleGroup
from app.workouts.program_engine.body_analysis import eligible_body_analysis_priorities
from app.workouts.program_engine.enums import (
    Goal,
    ImpactLimit,
    SkillDemand,
    StabilityDemand,
    TrainingStatus,
)
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
    body_priorities = {
        item.muscle: item for item in eligible_body_analysis_priorities(request, ruleset)
    }
    for exercise in exercises:
        score = 0
        reasons: list[str] = []
        if needed_muscle is not None and exercise.primary_muscle is needed_muscle:
            score += weights["movement_need"]
            reasons.append("REQUIRED_MOVEMENT_PATTERN")
        if exercise.primary_muscle in request.source.priority_muscles:
            score += weights["priority_muscle"]
            reasons.append("PRIORITY_MUSCLE")
        body_priority = (
            body_priorities.get(exercise.primary_muscle)
            if exercise.primary_muscle is not None
            else None
        )
        if body_priority is not None:
            score += weights[f"body_analysis_{body_priority.classification}"]
            reasons.append(f"BODY_ANALYSIS_{body_priority.classification.upper()}")
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
            if exercise.skill_demand is SkillDemand.LOW:
                score += weights["skill"]
        older_novice = (
            request.source.age >= ruleset.older_adult_modifier_age
            and request.training_status is TrainingStatus.NOVICE
            and request.source.training_age_months < ruleset.novice_training_age_months
        )
        if older_novice:
            demand = (
                _demand_rank(exercise.stability_demand)
                + _demand_rank(exercise.skill_demand)
                + _demand_rank(exercise.impact_level)
                + max(0, exercise.fatigue_cost - 1)
                + max(0, exercise.setup_cost - 1)
            )
            score -= demand * weights["older_novice_demand_penalty"]
            if demand:
                reasons.append("OLDER_NOVICE_DEMAND_PENALTY")
            if (
                exercise.stability_demand is StabilityDemand.LOW
                and exercise.skill_demand is SkillDemand.LOW
                and exercise.impact_level is ImpactLimit.LOW
                and exercise.fatigue_cost <= 2
                and exercise.setup_cost <= 2
            ):
                score += weights["older_novice_suitability"]
                reasons.append("OLDER_NOVICE_SUITABILITY")
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


def _demand_rank(value: StabilityDemand | SkillDemand | ImpactLimit) -> int:
    return {"low": 0, "moderate": 1, "high": 2}[value.value]
