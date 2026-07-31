from decimal import Decimal
from uuid import NAMESPACE_URL, UUID, uuid5

from app.exercises.enums import Difficulty, ExerciseType, MovementPattern, MuscleGroup
from app.profile.enums import ExperienceLevel, FitnessGoal, TrainingLocation
from app.workouts.deterministic_generator import DeterministicWorkoutPlanGenerator
from app.workouts.schemas import CandidateSet, WorkoutExerciseCandidate, WorkoutGenerationProfile
from app.workouts.time_budget import WorkoutGenerationPolicy
from app.workouts.validator import WorkoutPlanValidator


def _candidates() -> CandidateSet:
    patterns = [
        (MovementPattern.HORIZONTAL_PUSH, MuscleGroup.CHEST),
        (MovementPattern.HORIZONTAL_PULL, MuscleGroup.BACK),
        (MovementPattern.SQUAT, MuscleGroup.QUADRICEPS),
        (MovementPattern.HIP_HINGE, MuscleGroup.HAMSTRINGS),
        (MovementPattern.VERTICAL_PUSH, MuscleGroup.SHOULDERS),
        (MovementPattern.VERTICAL_PULL, MuscleGroup.BACK),
    ]
    exercises = tuple(
        WorkoutExerciseCandidate(
            id=uuid5(NAMESPACE_URL, pattern.value),
            primary_muscle=muscle,
            secondary_muscles=(),
            movement_pattern=pattern,
            exercise_type=ExerciseType.COMPOUND,
            equipment=(),
            difficulty=Difficulty.BEGINNER,
            caution_tags=(),
        )
        for pattern, muscle in patterns
    )
    return CandidateSet(
        exercises=exercises,
        candidate_set_hash="test-candidates",
        soft_cautions=(),
        minimum_candidate_count=4,
        minimum_movement_pattern_count=2,
    )


def test_deterministic_generator_returns_repeatable_validator_approved_plan() -> None:
    profile = WorkoutGenerationProfile(
        fitness_goal=FitnessGoal.BUILD_MUSCLE,
        experience_level=ExperienceLevel.BEGINNER,
        training_days_per_week=3,
        training_location=TrainingLocation.GYM,
        home_training_setup=None,
        session_duration_minutes=45,
        plan_duration_weeks=4,
        training_cautions=(),
        physical_limitations=None,
        current_weight_kg=Decimal("75"),
    )
    candidates = _candidates()
    policy = WorkoutGenerationPolicy.for_session_duration(45)
    generator = DeterministicWorkoutPlanGenerator()

    first = generator.generate(profile, candidates, policy)
    second = generator.generate(profile, candidates, policy)

    assert first == second
    assert len(first.days) == 3
    signatures = [tuple(item.exercise_id for item in day.exercises) for day in first.days]
    assert len(set(signatures)) == 3
    assert {exercise_id for day in signatures for exercise_id in day}.issubset(set(candidates.ids))
    WorkoutPlanValidator(
        candidates=candidates,
        policy=policy,
        required_day_count=3,
    ).validate(first)


def test_deterministic_generator_balances_an_uneven_candidate_catalogue() -> None:
    profile = WorkoutGenerationProfile(
        fitness_goal=FitnessGoal.BUILD_MUSCLE,
        experience_level=ExperienceLevel.INTERMEDIATE,
        training_days_per_week=4,
        training_location=TrainingLocation.GYM,
        home_training_setup=None,
        session_duration_minutes=60,
        plan_duration_weeks=4,
        training_cautions=(),
        physical_limitations=None,
        current_weight_kg=Decimal("75"),
    )
    muscles = [MuscleGroup.BACK] * 8 + [
        MuscleGroup.CHEST,
        MuscleGroup.QUADRICEPS,
        MuscleGroup.HAMSTRINGS,
        MuscleGroup.SHOULDERS,
        MuscleGroup.GLUTES,
        MuscleGroup.BICEPS,
        MuscleGroup.TRICEPS,
        MuscleGroup.ABS,
    ]
    exercises = tuple(
        WorkoutExerciseCandidate(
            id=UUID(int=index + 1),
            primary_muscle=muscle,
            secondary_muscles=(),
            movement_pattern=MovementPattern.HORIZONTAL_PULL,
            exercise_type=ExerciseType.COMPOUND,
            equipment=(),
            difficulty=Difficulty.INTERMEDIATE,
            caution_tags=(),
        )
        for index, muscle in enumerate(muscles)
    )
    candidates = CandidateSet(
        exercises=exercises,
        candidate_set_hash="uneven-candidates",
        soft_cautions=(),
        minimum_candidate_count=5,
        minimum_movement_pattern_count=2,
    )
    policy = WorkoutGenerationPolicy.for_session_duration(60)

    plan = DeterministicWorkoutPlanGenerator().generate(profile, candidates, policy)

    WorkoutPlanValidator(
        candidates=candidates,
        policy=policy,
        required_day_count=4,
    ).validate(plan)
