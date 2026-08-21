from dataclasses import dataclass
from enum import StrEnum

from app.exercises.enums import Difficulty, ExerciseType
from app.workouts.program_engine.enums import SkillDemand, StabilityDemand, TrainingStatus
from app.workouts.program_engine.equipment import effective_required_equipment
from app.workouts.program_engine.rulesets.resistance_training_v1 import ProgramRuleset
from app.workouts.program_engine.safety import effective_caution_tags
from app.workouts.program_engine.schemas import ExerciseCandidate, NormalizedProgramRequest


class StrengthExerciseRole(StrEnum):
    PRIMARY_STRENGTH = "primary_strength"
    SECONDARY_COMPOUND = "secondary_compound"
    ACCESSORY = "accessory"


@dataclass(frozen=True)
class StrengthRoleDecision:
    role: StrengthExerciseRole
    reason_codes: tuple[str, ...]


_DIFFICULTY_RANK = {
    Difficulty.BEGINNER: 0,
    Difficulty.INTERMEDIATE: 1,
    Difficulty.ADVANCED: 2,
}
_DEMAND_RANK = {
    SkillDemand.LOW: 0,
    SkillDemand.MODERATE: 1,
    SkillDemand.HIGH: 2,
}
_STABILITY_RANK = {
    StabilityDemand.LOW: 0,
    StabilityDemand.MODERATE: 1,
    StabilityDemand.HIGH: 2,
}


def classify_strength_role(
    exercise: ExerciseCandidate,
    request: NormalizedProgramRequest,
    ruleset: ProgramRuleset,
) -> StrengthRoleDecision:
    if exercise.exercise_type is not ExerciseType.COMPOUND:
        return StrengthRoleDecision(
            StrengthExerciseRole.ACCESSORY,
            ("STRENGTH_ROLE_ACCESSORY_TYPE",),
        )

    constraints = request.constraints
    if (
        exercise.id in constraints.blocked_exercises
        or exercise.movement_pattern in constraints.blocked_movement_patterns
        or not effective_required_equipment(exercise.equipment, exercise.movement_pattern).issubset(
            constraints.available_equipment
        )
        or effective_caution_tags(exercise).intersection(constraints.blocked_caution_tags)
    ):
        return StrengthRoleDecision(
            StrengthExerciseRole.SECONDARY_COMPOUND,
            ("STRENGTH_ROLE_CONSERVATIVE_FALLBACK",),
        )

    if exercise.primary_muscle is None or not exercise.equipment:
        return StrengthRoleDecision(
            StrengthExerciseRole.SECONDARY_COMPOUND,
            ("STRENGTH_ROLE_CONSERVATIVE_FALLBACK",),
        )

    high_demand = _is_high_demand(exercise)
    if request.training_status is TrainingStatus.NOVICE and high_demand:
        return StrengthRoleDecision(
            StrengthExerciseRole.SECONDARY_COMPOUND,
            ("STRENGTH_ROLE_BEGINNER_DEMAND_LIMIT",),
        )

    equipment_score = max(
        (ruleset.strength_equipment_scores.get(equipment, 0) for equipment in exercise.equipment),
        default=0,
    )
    if equipment_score < ruleset.strength_primary_minimum_equipment_score:
        return StrengthRoleDecision(
            StrengthExerciseRole.SECONDARY_COMPOUND,
            ("STRENGTH_ROLE_CONSERVATIVE_FALLBACK",),
        )
    if high_demand and not ruleset.strength_primary_allows_high_demand[request.training_status]:
        return StrengthRoleDecision(
            StrengthExerciseRole.SECONDARY_COMPOUND,
            ("STRENGTH_ROLE_DEMAND_LIMIT",),
        )

    return StrengthRoleDecision(
        StrengthExerciseRole.PRIMARY_STRENGTH,
        ("STRENGTH_PRIMARY_COMPOUND",),
    )


def _is_high_demand(exercise: ExerciseCandidate) -> bool:
    return (
        _DIFFICULTY_RANK[exercise.difficulty] >= _DIFFICULTY_RANK[Difficulty.ADVANCED]
        or _DEMAND_RANK[exercise.skill_demand] >= _DEMAND_RANK[SkillDemand.HIGH]
        or _STABILITY_RANK[exercise.stability_demand] >= _STABILITY_RANK[StabilityDemand.HIGH]
    )
