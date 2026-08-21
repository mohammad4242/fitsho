from app.exercises.enums import (
    Difficulty,
    ExerciseCautionTag,
    ExerciseLabel,
    ExerciseType,
    MovementPattern,
)
from app.workouts.program_engine.enums import (
    BalanceAbility,
    ImpactLimit,
    LoadLimit,
    StabilityDemand,
    TrainingStatus,
)
from app.workouts.program_engine.safety import effective_caution_tags
from app.workouts.program_engine.schemas import (
    EligibilityResult,
    ExerciseCandidate,
    NormalizedProgramRequest,
    RejectedCandidate,
)

_DIFFICULTY_RANK = {
    Difficulty.BEGINNER: 0,
    Difficulty.INTERMEDIATE: 1,
    Difficulty.ADVANCED: 2,
}
_STATUS_DIFFICULTY = {
    TrainingStatus.NOVICE: 0,
    TrainingStatus.EARLY_INTERMEDIATE: 1,
    TrainingStatus.INTERMEDIATE: 1,
    TrainingStatus.ADVANCED: 2,
}
_LIMIT_RANK = {LoadLimit.NONE: 0, LoadLimit.LOW: 1, LoadLimit.MODERATE: 2, LoadLimit.HIGH: 3}
_IMPACT_RANK = {ImpactLimit.LOW: 0, ImpactLimit.MODERATE: 1, ImpactLimit.HIGH: 2}
_STABILITY_RANK = {
    StabilityDemand.LOW: 0,
    StabilityDemand.MODERATE: 1,
    StabilityDemand.HIGH: 2,
}
_BALANCE_RANK = {
    BalanceAbility.LIMITED: 0,
    BalanceAbility.NORMAL: 1,
    BalanceAbility.HIGH: 2,
}


def _looks_like_mobility_content(exercise_name: str) -> bool:
    normalized = exercise_name.lower().replace("-", " ")
    return any(
        marker in normalized
        for marker in ("stretch", "mobility", " yoga", "yoga ", " pose", "pose ", "asana")
    )


def filter_eligible_exercises(
    request: NormalizedProgramRequest,
    catalog: list[ExerciseCandidate] | tuple[ExerciseCandidate, ...],
) -> EligibilityResult:
    eligible: list[ExerciseCandidate] = []
    cardio_eligible: list[ExerciseCandidate] = []
    rejected: list[RejectedCandidate] = []
    constraints = request.constraints
    for exercise in catalog:
        reasons: list[str] = []
        caution_tags = effective_caution_tags(exercise)
        if not exercise.is_active:
            reasons.append("EXERCISE_REJECTED_INACTIVE")
        if not exercise.is_programmable:
            reasons.append("EXERCISE_REJECTED_NOT_PROGRAMMABLE")
        if exercise.needs_review:
            reasons.append("EXERCISE_REJECTED_NEEDS_REVIEW")
        if not exercise.has_required_metadata:
            reasons.append("EXERCISE_REJECTED_MISSING_METADATA")
        if exercise.id in constraints.blocked_exercises:
            reasons.append("EXERCISE_REJECTED_BLOCKED_EXERCISE")
        if exercise.movement_pattern in constraints.blocked_movement_patterns:
            reasons.append("EXERCISE_REJECTED_BLOCKED_PATTERN")
        if not exercise.equipment.issubset(constraints.available_equipment):
            reasons.append("EXERCISE_REJECTED_MISSING_EQUIPMENT")
        if _DIFFICULTY_RANK[exercise.difficulty] > _STATUS_DIFFICULTY[request.training_status]:
            reasons.append("EXERCISE_REJECTED_SKILL_TOO_HIGH")
        if caution_tags.intersection(constraints.blocked_caution_tags):
            reasons.append("EXERCISE_REJECTED_BLOCKED_CAUTION_TAG")
        if _IMPACT_RANK[exercise.impact_level] > _IMPACT_RANK[constraints.impact_limit]:
            reasons.append("EXERCISE_REJECTED_IMPACT_LIMIT")
        if _LIMIT_RANK[exercise.axial_loading_level] > _LIMIT_RANK[constraints.axial_load_limit]:
            reasons.append("EXERCISE_REJECTED_AXIAL_LOAD_LIMIT")
        if (
            _STABILITY_RANK[exercise.stability_demand]
            > _BALANCE_RANK[constraints.balance_requirement]
        ):
            reasons.append("EXERCISE_REJECTED_BALANCE_DEMAND")
        if (
            exercise.movement_pattern is MovementPattern.VERTICAL_PUSH
            or ExerciseCautionTag.OVERHEAD_POSITION in caution_tags
        ) and constraints.overhead_limit is LoadLimit.NONE:
            reasons.append("EXERCISE_REJECTED_OVERHEAD_LIMIT")
        if constraints.allowed_range_of_motion and (
            not exercise.range_of_motion_profile
            or not exercise.range_of_motion_profile.issubset(constraints.allowed_range_of_motion)
        ):
            reasons.append("EXERCISE_REJECTED_RANGE_OF_MOTION")
        if not reasons and (
            exercise.exercise_type is ExerciseType.MOBILITY
            or _looks_like_mobility_content(exercise.name)
        ):
            reasons.append("EXERCISE_REJECTED_NOT_RESISTANCE_TRAINING")
        if reasons:
            rejected.append(RejectedCandidate(exercise_id=exercise.id, reason_codes=tuple(reasons)))
        elif ExerciseLabel.CARDIO in exercise.labels:
            cardio_eligible.append(exercise)
        elif exercise.exercise_type is ExerciseType.OTHER:
            rejected.append(
                RejectedCandidate(
                    exercise_id=exercise.id,
                    reason_codes=("EXERCISE_REJECTED_NOT_RESISTANCE_TRAINING",),
                )
            )
        else:
            eligible.append(exercise)
    return EligibilityResult(
        eligible=tuple(eligible),
        rejected=tuple(rejected),
        cardio_eligible=tuple(cardio_eligible),
    )
