from dataclasses import dataclass, field

from app.workouts.program_engine.enums import Goal, TrainingStatus


@dataclass(frozen=True)
class ProgramRuleset:
    version: str = "resistance_training_v1"
    engine_version: str = "program_engine_v1"
    max_resistance_days: int = 6
    duration_tolerance_minutes: int = 5
    general_warmup_minutes: int = 5
    primary_set_credit: float = 1.0
    secondary_set_credit: float = 0.5
    minimum_sets: dict[TrainingStatus, int] = field(
        default_factory=lambda: {
            TrainingStatus.NOVICE: 4,
            TrainingStatus.EARLY_INTERMEDIATE: 6,
            TrainingStatus.INTERMEDIATE: 8,
            TrainingStatus.ADVANCED: 10,
        }
    )
    maximum_sets: dict[TrainingStatus, int] = field(
        default_factory=lambda: {
            TrainingStatus.NOVICE: 8,
            TrainingStatus.EARLY_INTERMEDIATE: 10,
            TrainingStatus.INTERMEDIATE: 12,
            TrainingStatus.ADVANCED: 16,
        }
    )
    goal_base_sets: dict[Goal, int] = field(
        default_factory=lambda: {
            Goal.FAT_LOSS: 6,
            Goal.HYPERTROPHY: 9,
            Goal.STRENGTH: 7,
            Goal.MUSCLE_GAIN: 9,
            Goal.BODY_RECOMPOSITION: 8,
            Goal.GENERAL_FITNESS: 6,
            Goal.MUSCULAR_ENDURANCE: 7,
        }
    )
    priority_muscle_bonus_sets: int = 2
    poor_recovery_set_reduction: int = 2
    max_previous_volume_increase: float = 0.2
    max_sets_per_muscle_per_session: int = 6
    max_exercises_per_session: int = 8
    selection_weights: dict[str, int] = field(
        default_factory=lambda: {
            "goal_specificity": 20,
            "priority_muscle": 18,
            "movement_need": 16,
            "beginner_friendly": 12,
            "preference": 10,
            "stability": 8,
            "time_efficiency": 6,
            "fatigue_cost": 4,
            "dislike": -12,
        }
    )


RULESET = ProgramRuleset()
