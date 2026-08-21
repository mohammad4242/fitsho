from dataclasses import replace
from uuid import uuid4

import pytest

from app.exercises.enums import (
    Difficulty,
    Equipment,
    ExerciseCautionTag,
    ExerciseType,
    MovementPattern,
    MuscleGroup,
)
from app.profile.enums import TrainingLocation
from app.workouts.program_engine.eligibility import filter_eligible_exercises
from app.workouts.program_engine.engine import generate_program
from app.workouts.program_engine.enums import (
    Goal,
    SkillDemand,
    StabilityDemand,
    TrainingExperience,
    TrainingStatus,
)
from app.workouts.program_engine.exercise_ranker import rank_exercises
from app.workouts.program_engine.normalization import normalize_request
from app.workouts.program_engine.prescription import prescription_for
from app.workouts.program_engine.rulesets.resistance_training_v1 import RULESET
from app.workouts.program_engine.schemas import ExerciseCandidate, ProgramGenerationRequest
from app.workouts.program_engine.strength_programming import (
    StrengthExerciseRole,
    classify_strength_role,
)
from tests.workouts.program_engine.golden_fixtures import full_catalog, request


def _candidate(
    name: str,
    *,
    equipment: frozenset[Equipment],
    exercise_type: ExerciseType = ExerciseType.COMPOUND,
    difficulty: Difficulty = Difficulty.INTERMEDIATE,
    skill_demand: SkillDemand = SkillDemand.MODERATE,
    stability_demand: StabilityDemand = StabilityDemand.MODERATE,
    caution_tags: frozenset[ExerciseCautionTag] = frozenset(),
) -> ExerciseCandidate:
    return ExerciseCandidate(
        id=uuid4(),
        name=name,
        primary_muscle=MuscleGroup.CHEST,
        secondary_muscles=(),
        movement_pattern=MovementPattern.HORIZONTAL_PUSH,
        exercise_type=exercise_type,
        equipment=equipment,
        difficulty=difficulty,
        skill_demand=skill_demand,
        stability_demand=stability_demand,
        caution_tags=caution_tags,
        substitution_group="horizontal_push",
    )


def _strength_request(**overrides: object) -> ProgramGenerationRequest:
    values: dict[str, object] = {
        "primary_goal": Goal.STRENGTH,
        "training_experience": TrainingExperience.ADVANCED,
        "training_age_months": 72,
        "available_training_days": 1,
        "session_duration_minutes": 60,
        "training_location": TrainingLocation.GYM,
        "available_equipment": [
            Equipment.BODYWEIGHT,
            Equipment.DUMBBELL,
            Equipment.BARBELL,
            Equipment.BENCH,
            Equipment.CABLE,
            Equipment.MACHINE,
        ],
    }
    values.update(overrides)
    return request(
        **values,
    )


def test_strength_role_is_deterministic_and_conservative() -> None:
    request = normalize_request(_strength_request())
    primary = _candidate(
        "Loaded Press",
        equipment=frozenset({Equipment.BARBELL, Equipment.BENCH}),
        difficulty=Difficulty.ADVANCED,
    )
    ambiguous = replace(
        primary,
        equipment=frozenset({Equipment.BODYWEIGHT}),
        difficulty=Difficulty.BEGINNER,
    )

    first = classify_strength_role(primary, request, RULESET)
    second = classify_strength_role(primary, request, RULESET)
    fallback = classify_strength_role(ambiguous, request, RULESET)

    assert first == second
    assert first.role is StrengthExerciseRole.PRIMARY_STRENGTH
    assert fallback.role is StrengthExerciseRole.SECONDARY_COMPOUND
    assert "STRENGTH_ROLE_CONSERVATIVE_FALLBACK" in fallback.reason_codes


def test_strength_ranking_prefers_suitable_loaded_compound_over_push_up() -> None:
    request = normalize_request(_strength_request())
    loaded = _candidate(
        "Loaded Press",
        equipment=frozenset({Equipment.BARBELL, Equipment.BENCH}),
        difficulty=Difficulty.ADVANCED,
    )
    push_up = _candidate(
        "Push-Up",
        equipment=frozenset({Equipment.BODYWEIGHT}),
        difficulty=Difficulty.BEGINNER,
    )

    ranked = rank_exercises(request, [push_up, loaded], RULESET)

    assert ranked[0].exercise is loaded
    assert "STRENGTH_PRIMARY_COMPOUND" in ranked[0].reason_codes


def test_strength_prescription_is_role_aware_and_level_aware() -> None:
    advanced_primary = prescription_for(
        Goal.STRENGTH,
        ExerciseType.COMPOUND,
        TrainingStatus.ADVANCED,
        RULESET,
        strength_role=StrengthExerciseRole.PRIMARY_STRENGTH,
    )
    advanced_secondary = prescription_for(
        Goal.STRENGTH,
        ExerciseType.COMPOUND,
        TrainingStatus.ADVANCED,
        RULESET,
        strength_role=StrengthExerciseRole.SECONDARY_COMPOUND,
    )
    accessory = prescription_for(
        Goal.STRENGTH,
        ExerciseType.ISOLATION,
        TrainingStatus.ADVANCED,
        RULESET,
        strength_role=StrengthExerciseRole.ACCESSORY,
    )
    high_fatigue_accessory = prescription_for(
        Goal.STRENGTH,
        ExerciseType.ISOLATION,
        TrainingStatus.ADVANCED,
        RULESET,
        strength_role=StrengthExerciseRole.ACCESSORY,
        fatigue_cost=RULESET.strength_high_fatigue_cost,
    )
    beginner_primary = prescription_for(
        Goal.STRENGTH,
        ExerciseType.COMPOUND,
        TrainingStatus.NOVICE,
        RULESET,
        strength_role=StrengthExerciseRole.PRIMARY_STRENGTH,
    )

    assert advanced_primary.rep_min < advanced_secondary.rep_min < accessory.rep_min
    assert advanced_primary.rest_seconds > advanced_secondary.rest_seconds > accessory.rest_seconds
    assert beginner_primary.rep_min >= advanced_primary.rep_min
    assert high_fatigue_accessory.rest_seconds > accessory.rest_seconds


@pytest.mark.parametrize("blocked_by", ["equipment", "caution"])
def test_strength_ranking_never_resurrects_ineligible_primary_candidate(blocked_by: str) -> None:
    source = _strength_request(
        available_equipment=(
            [Equipment.BODYWEIGHT]
            if blocked_by == "equipment"
            else [
                Equipment.BODYWEIGHT,
                Equipment.DUMBBELL,
                Equipment.BARBELL,
                Equipment.BENCH,
                Equipment.CABLE,
                Equipment.MACHINE,
            ]
        )
    )
    normalized_request = normalize_request(source)
    blocked = _candidate(
        "Loaded Press",
        equipment=frozenset({Equipment.BARBELL}),
        caution_tags=(
            frozenset({ExerciseCautionTag.WRIST_LOADING})
            if blocked_by == "caution"
            else frozenset()
        ),
    )
    safe = _candidate(
        "Push-Up" if blocked_by == "equipment" else "Dumbbell Press",
        equipment=(
            frozenset({Equipment.BODYWEIGHT})
            if blocked_by == "equipment"
            else frozenset({Equipment.DUMBBELL})
        ),
    )
    if blocked_by == "caution":
        normalized_request = normalize_request(
            source.model_copy(
                update={
                    "blocked_caution_tags": frozenset({ExerciseCautionTag.WRIST_LOADING})
                }
            )
        )

    eligible = filter_eligible_exercises(normalized_request, [blocked, safe])

    assert blocked not in eligible.eligible
    assert safe in eligible.eligible
    ranked = rank_exercises(normalized_request, list(eligible.eligible), RULESET)
    assert blocked not in [item.exercise for item in ranked]


def test_beginner_strength_does_not_promote_high_skill_exercise_to_primary() -> None:
    beginner_request = normalize_request(
        _strength_request(
            training_experience=TrainingExperience.BEGINNER,
            training_age_months=2,
        )
    )
    advanced_candidate = _candidate(
        "High Skill Press",
        equipment=frozenset({Equipment.BARBELL, Equipment.BENCH}),
        difficulty=Difficulty.ADVANCED,
        skill_demand=SkillDemand.HIGH,
        stability_demand=StabilityDemand.HIGH,
    )

    decision = classify_strength_role(advanced_candidate, beginner_request, RULESET)

    assert decision.role is StrengthExerciseRole.SECONDARY_COMPOUND
    assert "STRENGTH_ROLE_BEGINNER_DEMAND_LIMIT" in decision.reason_codes


def test_advanced_strength_end_to_end_places_loaded_main_work_before_pushups() -> None:
    source = _strength_request(available_training_days=4)
    loaded = [
        _candidate(
            "Barbell Bench Press",
            equipment=frozenset({Equipment.BARBELL, Equipment.BENCH}),
            difficulty=Difficulty.ADVANCED,
        ),
    ]
    result = generate_program(source, [*full_catalog(), *loaded], RULESET)

    assert result.program is not None, result.errors
    first_day = result.program.weekly_schedule[0]
    assert first_day.exercises[0].exercise_type is ExerciseType.COMPOUND
    assert Equipment.BODYWEIGHT not in first_day.exercises[0].equipment
    assert "STRENGTH_PRIMARY_COMPOUND" in first_day.exercises[0].reason_codes
    assert all(
        not (
            item.exercise_type is ExerciseType.ISOLATION
            and item.rep_min == RULESET.prescription_rules["strength_compound"].rep_min
        )
        for day in result.program.weekly_schedule
        for item in day.exercises
    )
