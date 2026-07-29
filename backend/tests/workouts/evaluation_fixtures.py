from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from uuid import NAMESPACE_URL, uuid5

from app.exercises.enums import (
    Difficulty,
    Equipment,
    ExerciseCautionTag,
    ExerciseType,
    MovementPattern,
    MuscleGroup,
)
from app.profile.enums import (
    ExperienceLevel,
    FitnessGoal,
    HomeTrainingSetup,
    Sex,
    TrainingCaution,
    TrainingLocation,
)
from app.workouts.schemas import CandidateSet, WorkoutExerciseCandidate, WorkoutGenerationProfile
from app.workouts.signature import hash_candidate_set
from app.workouts.time_budget import WorkoutGenerationPolicy


@dataclass(frozen=True)
class WorkoutEvaluationFixture:
    name: str
    profile: WorkoutGenerationProfile
    candidates: CandidateSet
    policy: WorkoutGenerationPolicy


def evaluation_fixtures() -> tuple[WorkoutEvaluationFixture, ...]:
    return (
        _fixture(
            "beginner_3_day_gym_60_muscle_gain",
            _profile(
                goal=FitnessGoal.BUILD_MUSCLE,
                experience=ExperienceLevel.BEGINNER,
                days=3,
                location=TrainingLocation.GYM,
                setup=None,
                minutes=60,
                weeks=4,
            ),
            _gym_candidates(),
        ),
        _fixture(
            "beginner_3_day_bodyweight_home_30_general_fitness",
            _profile(
                goal=FitnessGoal.IMPROVE_FITNESS,
                experience=ExperienceLevel.BEGINNER,
                days=3,
                location=TrainingLocation.HOME,
                setup=HomeTrainingSetup.BODYWEIGHT_ONLY,
                minutes=30,
                weeks=4,
            ),
            _bodyweight_candidates(),
        ),
        _fixture(
            "intermediate_4_day_gym_75_fat_loss",
            _profile(
                goal=FitnessGoal.LOSE_WEIGHT,
                experience=ExperienceLevel.INTERMEDIATE,
                days=4,
                location=TrainingLocation.GYM,
                setup=None,
                minutes=75,
                weeks=6,
            ),
            _gym_candidates(Difficulty.INTERMEDIATE),
        ),
        _fixture(
            "intermediate_3_day_dumbbell_home_45_muscle_gain",
            _profile(
                goal=FitnessGoal.BUILD_MUSCLE,
                experience=ExperienceLevel.INTERMEDIATE,
                days=3,
                location=TrainingLocation.HOME,
                setup=HomeTrainingSetup.DUMBBELLS_AVAILABLE,
                minutes=45,
                weeks=6,
            ),
            _dumbbell_candidates(),
        ),
        _fixture(
            "beginner_2_day_gym_45_lower_back_caution",
            _profile(
                goal=FitnessGoal.IMPROVE_FITNESS,
                experience=ExperienceLevel.BEGINNER,
                days=2,
                location=TrainingLocation.GYM,
                setup=None,
                minutes=45,
                weeks=4,
                cautions=(TrainingCaution.LOWER_BACK,),
            ),
            _gym_candidates(exclude_tags={ExerciseCautionTag.LOWER_BACK_LOADING}),
        ),
        _fixture(
            "intermediate_5_day_gym_90_shoulder_caution",
            _profile(
                goal=FitnessGoal.BUILD_MUSCLE,
                experience=ExperienceLevel.INTERMEDIATE,
                days=5,
                location=TrainingLocation.GYM,
                setup=None,
                minutes=90,
                weeks=8,
                cautions=(TrainingCaution.SHOULDER,),
            ),
            _gym_candidates(
                Difficulty.INTERMEDIATE,
                exclude_tags={
                    ExerciseCautionTag.OVERHEAD_POSITION,
                    ExerciseCautionTag.SHOULDER_INTERNAL_ROTATION,
                },
            ),
        ),
    )


def _fixture(
    name: str,
    profile: WorkoutGenerationProfile,
    candidates: tuple[WorkoutExerciseCandidate, ...],
) -> WorkoutEvaluationFixture:
    return WorkoutEvaluationFixture(
        name=name,
        profile=profile,
        candidates=CandidateSet(
            exercises=candidates,
            candidate_set_hash=hash_candidate_set(candidates),
            soft_cautions=(),
            minimum_candidate_count=min(3, profile.training_days_per_week),
        ),
        policy=WorkoutGenerationPolicy.for_session_duration(profile.session_duration_minutes),
    )


def _profile(
    *,
    goal: FitnessGoal,
    experience: ExperienceLevel,
    days: int,
    location: TrainingLocation,
    setup: HomeTrainingSetup | None,
    minutes: int,
    weeks: int,
    cautions: tuple[TrainingCaution, ...] = (),
) -> WorkoutGenerationProfile:
    return WorkoutGenerationProfile(
        fitness_goal=goal,
        experience_level=experience,
        training_days_per_week=days,
        training_location=location,
        home_training_setup=setup,
        session_duration_minutes=minutes,
        plan_duration_weeks=weeks,
        training_cautions=cautions,
        physical_limitations=None,
        current_weight_kg=Decimal("70"),
        age=29,
        sex=Sex.PREFER_NOT_TO_SAY,
        height_cm=170,
    )


def _candidate(
    name: str,
    muscle: MuscleGroup,
    pattern: MovementPattern,
    equipment: tuple[Equipment, ...],
    *,
    difficulty: Difficulty = Difficulty.BEGINNER,
    caution_tags: tuple[ExerciseCautionTag, ...] = (),
) -> WorkoutExerciseCandidate:
    return WorkoutExerciseCandidate(
        id=uuid5(NAMESPACE_URL, f"fitsho-evaluation/{name}"),
        primary_muscle=muscle,
        secondary_muscles=(),
        movement_pattern=pattern,
        exercise_type=ExerciseType.COMPOUND,
        equipment=equipment,
        difficulty=difficulty,
        caution_tags=caution_tags,
    )


def _bodyweight_candidates() -> tuple[WorkoutExerciseCandidate, ...]:
    return (
        _candidate(
            "push-up", MuscleGroup.CHEST, MovementPattern.HORIZONTAL_PUSH, (Equipment.BODYWEIGHT,)
        ),
        _candidate(
            "split-squat", MuscleGroup.QUADRICEPS, MovementPattern.LUNGE, (Equipment.BODYWEIGHT,)
        ),
        _candidate(
            "glute-bridge",
            MuscleGroup.GLUTES,
            MovementPattern.HIP_EXTENSION,
            (Equipment.BODYWEIGHT,),
        ),
        _candidate(
            "calf-raise", MuscleGroup.CALVES, MovementPattern.CALF_RAISE, (Equipment.BODYWEIGHT,)
        ),
    )


def _dumbbell_candidates() -> tuple[WorkoutExerciseCandidate, ...]:
    return _bodyweight_candidates() + (
        _candidate(
            "dumbbell-floor-press",
            MuscleGroup.CHEST,
            MovementPattern.HORIZONTAL_PUSH,
            (Equipment.DUMBBELL,),
        ),
        _candidate(
            "dumbbell-row", MuscleGroup.BACK, MovementPattern.HORIZONTAL_PULL, (Equipment.DUMBBELL,)
        ),
        _candidate(
            "goblet-squat", MuscleGroup.QUADRICEPS, MovementPattern.SQUAT, (Equipment.DUMBBELL,)
        ),
    )


def _gym_candidates(
    difficulty: Difficulty = Difficulty.BEGINNER,
    *,
    exclude_tags: set[ExerciseCautionTag] | None = None,
) -> tuple[WorkoutExerciseCandidate, ...]:
    candidates = (
        _candidate(
            "machine-chest-press",
            MuscleGroup.CHEST,
            MovementPattern.HORIZONTAL_PUSH,
            (Equipment.MACHINE,),
            difficulty=difficulty,
        ),
        _candidate(
            "cable-row",
            MuscleGroup.BACK,
            MovementPattern.HORIZONTAL_PULL,
            (Equipment.CABLE,),
            difficulty=difficulty,
        ),
        _candidate(
            "leg-press",
            MuscleGroup.QUADRICEPS,
            MovementPattern.SQUAT,
            (Equipment.MACHINE,),
            difficulty=difficulty,
        ),
        _candidate(
            "leg-curl",
            MuscleGroup.HAMSTRINGS,
            MovementPattern.KNEE_FLEXION,
            (Equipment.MACHINE,),
            difficulty=difficulty,
        ),
        _candidate(
            "cable-curl",
            MuscleGroup.BICEPS,
            MovementPattern.ELBOW_FLEXION,
            (Equipment.CABLE,),
            difficulty=difficulty,
        ),
        _candidate(
            "rope-extension",
            MuscleGroup.TRICEPS,
            MovementPattern.ELBOW_EXTENSION,
            (Equipment.CABLE,),
            difficulty=difficulty,
        ),
        _candidate(
            "back-extension",
            MuscleGroup.LOWER_BACK,
            MovementPattern.HIP_HINGE,
            (Equipment.MACHINE,),
            difficulty=difficulty,
            caution_tags=(ExerciseCautionTag.LOWER_BACK_LOADING,),
        ),
        _candidate(
            "shoulder-press",
            MuscleGroup.SHOULDERS,
            MovementPattern.VERTICAL_PUSH,
            (Equipment.MACHINE,),
            difficulty=difficulty,
            caution_tags=(ExerciseCautionTag.OVERHEAD_POSITION,),
        ),
    )
    excluded = exclude_tags or set()
    return tuple(item for item in candidates if not set(item.caution_tags).intersection(excluded))
