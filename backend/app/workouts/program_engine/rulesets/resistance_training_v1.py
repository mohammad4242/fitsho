from dataclasses import dataclass, field

from app.workouts.program_engine.enums import Goal, TrainingStatus


@dataclass(frozen=True)
class PrescriptionRule:
    rep_min: int
    rep_max: int
    rest_seconds: int


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
    minimum_exercises_per_session: int = 3
    minutes_per_exercise_slot: int = 7
    maximum_novice_recovery_days: int = 3
    short_session_minutes: int = 30
    older_adult_modifier_age: int = 60
    contextual_volume_reduction_sets: int = 1
    minimum_working_sets: int = 2
    novice_target_rir: int = 3
    experienced_target_rir: int = 2
    first_compound_warmup_sets: int = 2
    strength_compound_warmup_sets: int = 3
    set_execution_minutes: float = 0.6
    warmup_set_minutes: float = 0.75
    exercise_transition_minutes: int = 1
    minimum_exercise_estimate_minutes: int = 3
    minimum_rest_seconds: int = 30
    maximum_target_rir: int = 5
    cardio_start_minutes: int = 10
    fat_loss_cardio_days: int = 2
    maintenance_cardio_days: int = 1
    double_progression_qualifying_sessions: int = 2
    upper_body_load_increase_percent: tuple[float, float] = (2.5, 5.0)
    lower_body_load_increase_percent: tuple[float, float] = (5.0, 10.0)
    deload_volume_reduction_percent: tuple[int, int] = (30, 50)
    deload_load_reduction_percent: tuple[int, int] = (5, 10)
    default_weekdays: dict[int, tuple[int, ...]] = field(
        default_factory=lambda: {
            1: (0,),
            2: (0, 3),
            3: (0, 2, 4),
            4: (0, 1, 3, 4),
            5: (0, 1, 2, 4, 5),
            6: (0, 1, 2, 3, 4, 5),
        }
    )
    prescription_rules: dict[str, PrescriptionRule] = field(
        default_factory=lambda: {
            "strength_compound": PrescriptionRule(3, 6, 180),
            "strength_accessory": PrescriptionRule(6, 12, 120),
            "hypertrophy_compound": PrescriptionRule(6, 12, 120),
            "hypertrophy_isolation": PrescriptionRule(10, 20, 90),
            "muscular_endurance": PrescriptionRule(12, 25, 60),
            "fat_loss": PrescriptionRule(8, 15, 90),
            "general_fitness": PrescriptionRule(6, 15, 90),
        }
    )
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
