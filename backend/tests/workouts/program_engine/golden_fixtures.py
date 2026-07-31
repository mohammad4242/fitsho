from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

from app.exercises.enums import (
    Difficulty,
    Equipment,
    ExerciseCautionTag,
    ExerciseLabel,
    ExerciseType,
    MovementPattern,
    MuscleGroup,
)
from app.profile.enums import TrainingLocation
from app.workouts.program_engine.enums import (
    Goal,
    ImpactLimit,
    PhysicalJobDemand,
    RecoveryRating,
    RedFlag,
    TrainingExperience,
)
from app.workouts.program_engine.schemas import (
    ExerciseCandidate,
    ProgramGenerationRequest,
    RecentTrainingHistory,
)


def exercise(
    slug: str,
    pattern: MovementPattern,
    muscle: MuscleGroup | None,
    *,
    equipment: frozenset[Equipment] = frozenset({Equipment.BODYWEIGHT}),
    secondary: tuple[MuscleGroup, ...] = (),
    exercise_type: ExerciseType = ExerciseType.COMPOUND,
    caution_tags: frozenset[ExerciseCautionTag] = frozenset(),
    labels: frozenset[ExerciseLabel] = frozenset(),
    impact: ImpactLimit = ImpactLimit.LOW,
    needs_review: bool = False,
) -> ExerciseCandidate:
    return ExerciseCandidate(
        id=uuid5(NAMESPACE_URL, f"https://fitsho.test/golden/{slug}"),
        name=slug.replace("-", " ").title(),
        primary_muscle=muscle,
        secondary_muscles=secondary,
        movement_pattern=pattern,
        exercise_type=exercise_type,
        equipment=equipment,
        difficulty=Difficulty.BEGINNER,
        caution_tags=caution_tags,
        labels=labels,
        impact_level=impact,
        fatigue_cost=1 if exercise_type is ExerciseType.ISOLATION else 2,
        substitution_group=pattern.value,
        needs_review=needs_review,
    )


def full_catalog() -> list[ExerciseCandidate]:
    bodyweight = frozenset({Equipment.BODYWEIGHT})
    dumbbell = frozenset({Equipment.DUMBBELL})
    return [
        exercise(
            "push-up",
            MovementPattern.HORIZONTAL_PUSH,
            MuscleGroup.CHEST,
            secondary=(MuscleGroup.TRICEPS, MuscleGroup.SHOULDERS),
        ),
        exercise(
            "bodyweight-row",
            MovementPattern.HORIZONTAL_PULL,
            MuscleGroup.BACK,
            secondary=(MuscleGroup.BICEPS,),
        ),
        exercise(
            "bodyweight-squat",
            MovementPattern.SQUAT,
            MuscleGroup.QUADRICEPS,
            secondary=(MuscleGroup.GLUTES,),
            caution_tags=frozenset({ExerciseCautionTag.DEEP_KNEE_FLEXION}),
        ),
        exercise(
            "bodyweight-hinge",
            MovementPattern.HIP_HINGE,
            MuscleGroup.HAMSTRINGS,
            secondary=(MuscleGroup.GLUTES,),
        ),
        exercise(
            "reverse-lunge",
            MovementPattern.LUNGE,
            MuscleGroup.GLUTES,
            secondary=(MuscleGroup.QUADRICEPS,),
            caution_tags=frozenset({ExerciseCautionTag.DEEP_KNEE_FLEXION}),
        ),
        exercise("wall-knee-extension", MovementPattern.KNEE_EXTENSION, MuscleGroup.QUADRICEPS),
        exercise("calf-raise", MovementPattern.CALF_RAISE, MuscleGroup.CALVES),
        exercise(
            "plank",
            MovementPattern.CORE_ANTI_EXTENSION,
            MuscleGroup.ABS,
            exercise_type=ExerciseType.CORE,
        ),
        exercise(
            "dead-bug",
            MovementPattern.CORE_ANTI_EXTENSION,
            MuscleGroup.ABS,
            exercise_type=ExerciseType.CORE,
        ),
        exercise(
            "crunch",
            MovementPattern.SPINAL_FLEXION,
            MuscleGroup.ABS,
            exercise_type=ExerciseType.CORE,
            caution_tags=frozenset({ExerciseCautionTag.SPINAL_FLEXION}),
        ),
        exercise(
            "dumbbell-press",
            MovementPattern.HORIZONTAL_PUSH,
            MuscleGroup.CHEST,
            equipment=dumbbell,
            secondary=(MuscleGroup.TRICEPS,),
        ),
        exercise(
            "dumbbell-row",
            MovementPattern.HORIZONTAL_PULL,
            MuscleGroup.BACK,
            equipment=dumbbell,
            secondary=(MuscleGroup.BICEPS,),
        ),
        exercise(
            "dumbbell-rdl",
            MovementPattern.HIP_HINGE,
            MuscleGroup.HAMSTRINGS,
            equipment=dumbbell,
            secondary=(MuscleGroup.GLUTES,),
        ),
        exercise(
            "dumbbell-overhead-press",
            MovementPattern.VERTICAL_PUSH,
            MuscleGroup.SHOULDERS,
            equipment=dumbbell,
            caution_tags=frozenset({ExerciseCautionTag.OVERHEAD_POSITION}),
        ),
        exercise(
            "lateral-raise",
            MovementPattern.SHOULDER_ABDUCTION,
            MuscleGroup.SHOULDERS,
            equipment=dumbbell,
            exercise_type=ExerciseType.ISOLATION,
        ),
        exercise(
            "dumbbell-curl",
            MovementPattern.ELBOW_FLEXION,
            MuscleGroup.BICEPS,
            equipment=dumbbell,
            exercise_type=ExerciseType.ISOLATION,
        ),
        exercise(
            "dumbbell-triceps-extension",
            MovementPattern.ELBOW_EXTENSION,
            MuscleGroup.TRICEPS,
            equipment=dumbbell,
            exercise_type=ExerciseType.ISOLATION,
        ),
        exercise(
            "march",
            MovementPattern.OTHER,
            None,
            labels=frozenset({ExerciseLabel.CARDIO}),
            exercise_type=ExerciseType.OTHER,
        ),
        exercise(
            "jumping-jacks",
            MovementPattern.OTHER,
            None,
            labels=frozenset({ExerciseLabel.CARDIO}),
            exercise_type=ExerciseType.OTHER,
            impact=ImpactLimit.HIGH,
        ),
        exercise(
            "review-pending-push",
            MovementPattern.HORIZONTAL_PUSH,
            MuscleGroup.CHEST,
            equipment=bodyweight,
            needs_review=True,
        ),
    ]


def request(**overrides: object) -> ProgramGenerationRequest:
    values: dict[str, object] = {
        "user_id": uuid4(),
        "age": 30,
        "height_cm": 175,
        "weight_kg": 75,
        "primary_goal": Goal.GENERAL_FITNESS,
        "training_experience": TrainingExperience.BEGINNER,
        "training_age_months": 3,
        "available_training_days": 3,
        "session_duration_minutes": 45,
        "available_equipment": [Equipment.BODYWEIGHT, Equipment.DUMBBELL],
        "training_location": TrainingLocation.HOME,
        "seed_optional": 1234,
    }
    values.update(overrides)
    return ProgramGenerationRequest.model_validate(values)


INTERMEDIATE_HISTORY = RecentTrainingHistory(consistent_weeks=24, completed_session_ratio=0.9)
ADVANCED_HISTORY = RecentTrainingHistory(consistent_weeks=80, completed_session_ratio=0.95)


def golden_scenarios() -> dict[str, ProgramGenerationRequest]:
    return {
        "novice_1_day_45_general": request(available_training_days=1),
        "novice_2_days_35_general": request(
            available_training_days=2, session_duration_minutes=35
        ),
        "novice_3_days_fat_loss_low_impact": request(
            primary_goal=Goal.FAT_LOSS, impact_limit=ImpactLimit.LOW
        ),
        "intermediate_4_days_hypertrophy": request(
            primary_goal=Goal.HYPERTROPHY,
            training_experience=TrainingExperience.INTERMEDIATE,
            training_age_months=30,
            available_training_days=4,
            recent_training_history=INTERMEDIATE_HISTORY,
        ),
        "intermediate_5_days_shoulder_priority": request(
            primary_goal=Goal.HYPERTROPHY,
            training_experience=TrainingExperience.INTERMEDIATE,
            training_age_months=30,
            available_training_days=5,
            priority_muscles=[MuscleGroup.SHOULDERS],
            recent_training_history=INTERMEDIATE_HISTORY,
        ),
        "advanced_4_days_strength": request(
            primary_goal=Goal.STRENGTH,
            training_experience=TrainingExperience.ADVANCED,
            training_age_months=72,
            available_training_days=4,
            recent_training_history=ADVANCED_HISTORY,
        ),
        "home_dumbbells_only": request(
            available_equipment=[Equipment.BODYWEIGHT, Equipment.DUMBBELL]
        ),
        "bodyweight_only": request(available_equipment=[Equipment.BODYWEIGHT]),
        "no_overhead": request(
            blocked_movement_patterns=[MovementPattern.VERTICAL_PUSH],
            blocked_caution_tags=[ExerciseCautionTag.OVERHEAD_POSITION],
        ),
        "limited_knee_flexion": request(
            blocked_movement_patterns=[MovementPattern.SQUAT, MovementPattern.LUNGE],
            blocked_caution_tags=[ExerciseCautionTag.DEEP_KNEE_FLEXION],
        ),
        "no_spinal_flexion": request(
            blocked_movement_patterns=[MovementPattern.SPINAL_FLEXION],
            blocked_caution_tags=[ExerciseCautionTag.SPINAL_FLEXION],
        ),
        "high_job_poor_recovery": request(
            available_training_days=6,
            sleep_quality=RecoveryRating.POOR,
            stress_level=RecoveryRating.POOR,
            physical_job_demand=PhysicalJobDemand.HIGH,
        ),
        "short_25_minutes": request(session_duration_minutes=25),
        "safety_red_flag": request(current_pain_or_red_flags=[RedFlag.CHEST_PAIN]),
    }


def impossible_equipment_request() -> tuple[ProgramGenerationRequest, list[ExerciseCandidate]]:
    source = request(available_equipment=[Equipment.BODYWEIGHT])
    barbell = exercise(
        "barbell-only",
        MovementPattern.SQUAT,
        MuscleGroup.QUADRICEPS,
        equipment=frozenset({Equipment.BARBELL}),
    )
    return source, [barbell]


def ids(items: list[ExerciseCandidate], slugs: set[str]) -> set[UUID]:
    return {item.id for item in items if item.name.lower().replace(" ", "-") in slugs}
