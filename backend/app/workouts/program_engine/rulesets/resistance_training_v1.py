from dataclasses import dataclass, field

from app.workouts.program_engine.enums import Goal, SplitType, TrainingStatus

MINIMUM_EXERCISES_PER_SESSION = 5
MAXIMUM_EXERCISES_PER_SESSION = 9


@dataclass(frozen=True)
class PrescriptionRule:
    rep_min: int
    rep_max: int
    rest_seconds: int


@dataclass(frozen=True)
class ProgramRuleset:
    version: str = "resistance_training_v2"
    engine_version: str = "program_engine_v1"
    max_resistance_days: int = 6
    days_per_week: int = 7
    minimum_recovery_gap_days: int = 2
    novice_training_age_months: int = 6
    early_intermediate_training_age_months: int = 18
    intermediate_training_age_months: int = 48
    minimum_consistent_weeks_for_experience: int = 4
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
    minimum_coverage_sets: dict[TrainingStatus, int] = field(
        default_factory=lambda: {
            TrainingStatus.NOVICE: 1,
            TrainingStatus.EARLY_INTERMEDIATE: 2,
            TrainingStatus.INTERMEDIATE: 2,
            TrainingStatus.ADVANCED: 3,
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
    secondary_muscle_minimum_sets: dict[TrainingStatus, int] = field(
        default_factory=lambda: {
            TrainingStatus.NOVICE: 2,
            TrainingStatus.EARLY_INTERMEDIATE: 3,
            TrainingStatus.INTERMEDIATE: 4,
            TrainingStatus.ADVANCED: 5,
        }
    )
    secondary_muscle_maximum_sets: dict[TrainingStatus, int] = field(
        default_factory=lambda: {
            TrainingStatus.NOVICE: 8,
            TrainingStatus.EARLY_INTERMEDIATE: 10,
            TrainingStatus.INTERMEDIATE: 12,
            TrainingStatus.ADVANCED: 14,
        }
    )
    soft_maximum_allowance_sets: dict[TrainingStatus, int] = field(
        default_factory=lambda: {
            TrainingStatus.NOVICE: 1,
            TrainingStatus.EARLY_INTERMEDIATE: 1,
            TrainingStatus.INTERMEDIATE: 2,
            TrainingStatus.ADVANCED: 2,
        }
    )
    good_recovery_soft_maximum_bonus_sets: int = 1
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
    secondary_muscle_goal_base_sets: dict[Goal, int] = field(
        default_factory=lambda: {
            Goal.FAT_LOSS: 4,
            Goal.HYPERTROPHY: 6,
            Goal.STRENGTH: 5,
            Goal.MUSCLE_GAIN: 6,
            Goal.BODY_RECOMPOSITION: 5,
            Goal.GENERAL_FITNESS: 4,
            Goal.MUSCULAR_ENDURANCE: 5,
        }
    )
    priority_muscle_bonus_sets: int = 2
    body_analysis_minimum_confidence: float = 0.7
    body_analysis_mild_lag_bonus_sets: int = 1
    body_analysis_clear_lag_bonus_sets: int = 2
    body_analysis_mild_lag_template_boost: int = 20
    body_analysis_clear_lag_template_boost: int = 35
    poor_recovery_set_reduction: int = 2
    max_previous_volume_increase: float = 0.2
    adaptation_min_adherence_for_progression: float = 0.8
    adaptation_min_volume_confidence_for_progression: float = 0.8
    adaptation_max_volume_increase_ratio: float = 0.1
    adaptation_lagging_muscle_volume_delta_sets: int = 1
    adaptation_lagging_muscle_priority_delta: int = 1
    adaptation_repeated_poor_recovery_weeks: int = 2
    adaptation_repeated_too_hard_weeks: int = 2
    adaptation_repeated_replacement_count: int = 2
    adaptation_max_replacement_preference_strength: int = 5
    adaptation_repeated_pain_signal_count: int = 2
    max_sets_per_muscle_per_session: int = 6
    maximum_direct_sessions_per_muscle_per_week: int = 2
    max_exercises_per_session: int = MAXIMUM_EXERCISES_PER_SESSION
    minimum_exercises_per_session: int = MINIMUM_EXERCISES_PER_SESSION
    minutes_per_exercise_slot: int = 7
    minimum_session_work_minutes: int = 10
    minimum_exercise_budget_minutes: int = 3
    default_untracked_muscle_sets: int = 2
    substitution_limit: int = 3
    maximum_novice_recovery_days: int = 3
    recommended_resistance_days: dict[TrainingStatus, int] = field(
        default_factory=lambda: {
            TrainingStatus.NOVICE: 3,
            TrainingStatus.EARLY_INTERMEDIATE: 4,
            TrainingStatus.INTERMEDIATE: 5,
            TrainingStatus.ADVANCED: 6,
        }
    )
    poor_recovery_session_reduction: int = 2
    session_count_distance_penalty: int = 12
    body_part_rotation_bonus: int = 30
    phul_bonus: int = 8
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
    minimum_cardio_minutes: int = 5
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
    split_weights: dict[str, int] = field(
        default_factory=lambda: {
            "base": 100,
            "simplicity": 16,
            "goal_specificity": 12,
            "twice_weekly_frequency": 6,
            "priority_specialization": 10,
            "short_session_full_body": 8,
            "recovery_complexity_penalty": 8,
        }
    )
    split_complexity: dict[SplitType, int] = field(
        default_factory=lambda: {
            SplitType.FULL_BODY: 0,
            SplitType.FULL_BODY_AB: 0,
            SplitType.FULL_BODY_ABC: 0,
            SplitType.FULL_BODY_FOUR: 1,
            SplitType.UPPER_LOWER_FULL: 1,
            SplitType.UPPER_LOWER: 2,
            SplitType.UPPER_LOWER_SPECIALIZATION: 3,
            SplitType.PUSH_PULL_LEGS_UPPER_LOWER: 4,
            SplitType.UPPER_LOWER_X3: 4,
            SplitType.PUSH_PULL_LEGS_X2: 6,
            SplitType.PHUL: 3,
            SplitType.BODY_PART_ROTATION: 4,
        }
    )
    exercise_order_rank: dict[str, int] = field(
        default_factory=lambda: {
            "primary_compound": 0,
            "accessory": 1,
            "trunk": 2,
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
            "body_analysis_mild_lag": 10,
            "body_analysis_clear_lag": 18,
            "movement_need": 16,
            "beginner_friendly": 12,
            "preference": 10,
            "stability": 8,
            "skill": 8,
            "older_novice_suitability": 18,
            "older_novice_demand_penalty": 4,
            "time_efficiency": 6,
            "fatigue_cost": 4,
            "dislike": -12,
        }
    )


RULESET = ProgramRuleset()
