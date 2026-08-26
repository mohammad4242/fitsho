from uuid import NAMESPACE_URL, uuid5

from app.exercises.enums import Difficulty, Equipment, ExerciseType, MovementPattern, MuscleGroup
from app.workouts.program_engine.enums import (
    Goal,
    SkillDemand,
    StabilityDemand,
    TrainingExperience,
)
from app.workouts.program_engine.exercise_ranker import rank_exercises
from app.workouts.program_engine.normalization import normalize_request
from app.workouts.program_engine.rulesets.resistance_training_v1 import RULESET
from app.workouts.program_engine.schemas import ExerciseCandidate
from tests.workouts.program_engine.golden_fixtures import request


def _candidate(
    slug: str,
    equipment: Equipment,
    *,
    difficulty: Difficulty,
    stability: StabilityDemand,
    skill: SkillDemand,
) -> ExerciseCandidate:
    return ExerciseCandidate(
        id=uuid5(NAMESPACE_URL, f"https://fitsho.test/level-palette/{slug}"),
        name=slug.replace("-", " ").title(),
        primary_muscle=MuscleGroup.CHEST,
        secondary_muscles=(),
        movement_pattern=MovementPattern.HORIZONTAL_PUSH,
        exercise_type=ExerciseType.COMPOUND,
        equipment=frozenset({equipment}),
        difficulty=difficulty,
        stability_demand=stability,
        skill_demand=skill,
        fatigue_cost=1,
        setup_cost=1,
        substitution_group="horizontal-push",
    )


def _palette() -> tuple[ExerciseCandidate, ...]:
    return (
        _candidate(
            "machine-chest-press",
            Equipment.MACHINE,
            difficulty=Difficulty.BEGINNER,
            stability=StabilityDemand.LOW,
            skill=SkillDemand.LOW,
        ),
        _candidate(
            "cable-chest-press",
            Equipment.CABLE,
            difficulty=Difficulty.BEGINNER,
            stability=StabilityDemand.LOW,
            skill=SkillDemand.LOW,
        ),
        _candidate(
            "dumbbell-chest-press",
            Equipment.DUMBBELL,
            difficulty=Difficulty.INTERMEDIATE,
            stability=StabilityDemand.MODERATE,
            skill=SkillDemand.MODERATE,
        ),
        _candidate(
            "barbell-bench-press",
            Equipment.BARBELL,
            difficulty=Difficulty.ADVANCED,
            stability=StabilityDemand.HIGH,
            skill=SkillDemand.HIGH,
        ),
    )


def _ranked_scores(experience: TrainingExperience) -> dict[str, int]:
    normalized = normalize_request(
        request(
            primary_goal=Goal.GENERAL_FITNESS,
            training_experience=experience,
            training_age_months={
                TrainingExperience.FIRST_MONTH: 0,
                TrainingExperience.BEGINNER: 12,
                TrainingExperience.INTERMEDIATE: 24,
                TrainingExperience.ADVANCED: 72,
            }[experience],
            available_equipment=[
                Equipment.BARBELL,
                Equipment.BENCH,
                Equipment.CABLE,
                Equipment.DUMBBELL,
                Equipment.MACHINE,
            ],
        ),
        RULESET,
    )
    return {
        item.exercise.name.lower().replace(" ", "-"): item.score
        for item in rank_exercises(normalized, _palette(), RULESET)
    }


def test_first_month_strongly_prefers_supported_stable_equipment() -> None:
    scores = _ranked_scores(TrainingExperience.FIRST_MONTH)

    assert scores["machine-chest-press"] > scores["dumbbell-chest-press"]
    assert scores["cable-chest-press"] > scores["dumbbell-chest-press"]
    assert scores["dumbbell-chest-press"] > scores["barbell-bench-press"]


def test_beginner_keeps_the_same_palette_bias_but_weaker_than_first_month() -> None:
    first_month = _ranked_scores(TrainingExperience.FIRST_MONTH)
    beginner = _ranked_scores(TrainingExperience.BEGINNER)

    assert beginner["machine-chest-press"] > beginner["barbell-bench-press"]
    assert beginner["cable-chest-press"] > beginner["barbell-bench-press"]
    assert (
        first_month["machine-chest-press"] - first_month["dumbbell-chest-press"]
        > beginner["machine-chest-press"] - beginner["dumbbell-chest-press"]
    )


def test_intermediate_is_neutral_to_equipment_and_skill_demand() -> None:
    scores = _ranked_scores(TrainingExperience.INTERMEDIATE)

    assert scores["barbell-bench-press"] == scores["machine-chest-press"]


def test_advanced_does_not_penalize_high_skill_free_weight_variation() -> None:
    scores = _ranked_scores(TrainingExperience.ADVANCED)

    assert scores["barbell-bench-press"] > scores["machine-chest-press"]
