from dataclasses import dataclass

from app.exercises.enums import Difficulty, Equipment
from app.workouts.program_engine.enums import (
    BodyPosition,
    SkillDemand,
    StabilityDemand,
    TrainingExperience,
)
from app.workouts.program_engine.schemas import ExerciseCandidate, NormalizedProgramRequest


@dataclass(frozen=True)
class LevelPaletteScore:
    adjustment: int
    reason_codes: tuple[str, ...]


def level_palette_score(
    request: NormalizedProgramRequest,
    exercise: ExerciseCandidate,
) -> LevelPaletteScore:
    """Score safe eligible exercises by the user's declared experience level."""
    experience = request.source.training_experience
    if experience is TrainingExperience.INTERMEDIATE:
        return LevelPaletteScore(0, ())
    if experience is TrainingExperience.ADVANCED:
        adjustment = 0
        reasons: list[str] = []
        if exercise.skill_demand is SkillDemand.HIGH:
            adjustment += 6
            reasons.append("ADVANCED_VARIATION_AVAILABLE")
        if exercise.difficulty is Difficulty.ADVANCED:
            adjustment += 6
            reasons.append("ADVANCED_DIFFICULTY_MATCH")
        if exercise.equipment.intersection(
            {Equipment.BARBELL, Equipment.DUMBBELL, Equipment.PULL_UP_BAR}
        ):
            adjustment += 4
            reasons.append("ADVANCED_FULL_EQUIPMENT_POOL")
        return LevelPaletteScore(adjustment, tuple(reasons))

    first_month = experience is TrainingExperience.FIRST_MONTH
    equipment_scores = (
        {
            Equipment.MACHINE: 60,
            Equipment.CABLE: 45,
            Equipment.DUMBBELL: 15,
            Equipment.BODYWEIGHT: 10,
            Equipment.RESISTANCE_BAND: 10,
            Equipment.BARBELL: -40,
            Equipment.PULL_UP_BAR: -30,
        }
        if first_month
        else {
            Equipment.MACHINE: 34,
            Equipment.CABLE: 28,
            Equipment.DUMBBELL: 16,
            Equipment.BODYWEIGHT: 10,
            Equipment.RESISTANCE_BAND: 10,
            Equipment.BARBELL: -12,
            Equipment.PULL_UP_BAR: -8,
        }
    )
    adjustment = max((equipment_scores.get(item, 0) for item in exercise.equipment), default=0)
    reasons = ["FIRST_MONTH_EQUIPMENT_BIAS" if first_month else "BEGINNER_EQUIPMENT_BIAS"]
    if "smith" in exercise.name.lower():
        adjustment += 10 if first_month else 6
        reasons.append("SMITH_MACHINE_PREFERRED")
    if exercise.stability_demand is StabilityDemand.LOW:
        adjustment += 18 if first_month else 10
        reasons.append("LOW_STABILITY_DEMAND_PREFERRED")
    elif first_month and exercise.stability_demand is StabilityDemand.HIGH:
        adjustment -= 20
    if exercise.skill_demand is SkillDemand.LOW:
        adjustment += 18 if first_month else 10
        reasons.append("LOW_SKILL_DEMAND_PREFERRED")
    elif first_month and exercise.skill_demand is SkillDemand.HIGH:
        adjustment -= 25
    if exercise.body_position in {
        BodyPosition.SUPPORTED,
        BodyPosition.SEATED,
        BodyPosition.LYING,
    }:
        adjustment += 12 if first_month else 6
        reasons.append("SUPPORTED_POSITION_PREFERRED")
    if first_month:
        adjustment -= max(0, exercise.setup_cost - 1) * 3
        adjustment -= max(0, exercise.fatigue_cost - 1) * 3
    return LevelPaletteScore(adjustment, tuple(reasons))
