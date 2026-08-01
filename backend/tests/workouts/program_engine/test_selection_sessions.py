from uuid import UUID, uuid4

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
from app.workouts.program_engine.enums import (
    BalanceAbility,
    Goal,
    ImpactLimit,
    LoadLimit,
    StabilityDemand,
    TrainingExperience,
)
from app.workouts.program_engine.exercise_ranker import rank_exercises
from app.workouts.program_engine.normalization import normalize_request
from app.workouts.program_engine.rulesets.resistance_training_v1 import RULESET
from app.workouts.program_engine.schemas import (
    ExerciseCandidate,
    NormalizedProgramRequest,
    ProgramGenerationRequest,
)
from app.workouts.program_engine.session_builder import build_sessions
from app.workouts.program_engine.split_selector import select_split
from app.workouts.program_engine.volume_planner import plan_weekly_volume


def normalized(**overrides: object) -> NormalizedProgramRequest:
    values: dict[str, object] = {
        "user_id": uuid4(),
        "age": 31,
        "height_cm": 175,
        "weight_kg": 76,
        "primary_goal": Goal.GENERAL_FITNESS,
        "training_experience": TrainingExperience.BEGINNER,
        "training_age_months": 3,
        "available_training_days": 1,
        "session_duration_minutes": 45,
        "available_equipment": [Equipment.BODYWEIGHT, Equipment.DUMBBELL],
        "training_location": TrainingLocation.HOME,
        "seed_optional": 42,
    }
    values.update(overrides)
    return normalize_request(ProgramGenerationRequest.model_validate(values))


def candidate(
    name: str,
    pattern: MovementPattern,
    muscle: MuscleGroup,
    **overrides: object,
) -> ExerciseCandidate:
    values: dict[str, object] = {
        "id": uuid4(),
        "name": name,
        "primary_muscle": muscle,
        "secondary_muscles": (),
        "movement_pattern": pattern,
        "exercise_type": ExerciseType.COMPOUND,
        "equipment": frozenset({Equipment.BODYWEIGHT}),
        "difficulty": Difficulty.BEGINNER,
        "substitution_group": pattern.value,
    }
    values.update(overrides)
    return ExerciseCandidate(**values)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("changes", "reason"),
    [
        ({"is_active": False}, "EXERCISE_REJECTED_INACTIVE"),
        ({"is_programmable": False}, "EXERCISE_REJECTED_NOT_PROGRAMMABLE"),
        ({"needs_review": True}, "EXERCISE_REJECTED_NEEDS_REVIEW"),
        ({"primary_muscle": None}, "EXERCISE_REJECTED_MISSING_METADATA"),
        ({"equipment": frozenset({Equipment.BARBELL})}, "EXERCISE_REJECTED_MISSING_EQUIPMENT"),
        ({"difficulty": Difficulty.ADVANCED}, "EXERCISE_REJECTED_SKILL_TOO_HIGH"),
        (
            {"caution_tags": frozenset({ExerciseCautionTag.WRIST_LOADING})},
            "EXERCISE_REJECTED_BLOCKED_CAUTION_TAG",
        ),
        ({"impact_level": ImpactLimit.HIGH}, "EXERCISE_REJECTED_IMPACT_LIMIT"),
        ({"axial_loading_level": LoadLimit.HIGH}, "EXERCISE_REJECTED_AXIAL_LOAD_LIMIT"),
        ({"stability_demand": StabilityDemand.HIGH}, "EXERCISE_REJECTED_BALANCE_DEMAND"),
    ],
)
def test_each_hard_constraint_rejects_candidate(changes: dict[str, object], reason: str) -> None:
    request = normalized(
        blocked_caution_tags=[ExerciseCautionTag.WRIST_LOADING],
        impact_limit=ImpactLimit.LOW,
        axial_load_limit=LoadLimit.LOW,
        balance_requirement=BalanceAbility.LIMITED,
    )
    item = candidate("unsafe", MovementPattern.SQUAT, MuscleGroup.QUADRICEPS, **changes)

    result = filter_eligible_exercises(request, [item])

    assert not result.eligible
    assert reason in result.rejected[0].reason_codes


def test_blocked_exercise_and_pattern_are_hard_filters() -> None:
    blocked_id = uuid4()
    request = normalized(
        blocked_exercises=[blocked_id],
        blocked_movement_patterns=[MovementPattern.VERTICAL_PUSH],
    )
    blocked_exercise = candidate(
        "blocked", MovementPattern.SQUAT, MuscleGroup.QUADRICEPS, id=blocked_id
    )
    blocked_pattern = candidate("overhead", MovementPattern.VERTICAL_PUSH, MuscleGroup.SHOULDERS)

    result = filter_eligible_exercises(request, [blocked_exercise, blocked_pattern])

    reasons = {reason for item in result.rejected for reason in item.reason_codes}
    assert "EXERCISE_REJECTED_BLOCKED_EXERCISE" in reasons
    assert "EXERCISE_REJECTED_BLOCKED_PATTERN" in reasons


def test_no_overhead_limit_blocks_vertical_press() -> None:
    request = normalized(overhead_limit=LoadLimit.NONE)
    overhead = candidate("press", MovementPattern.VERTICAL_PUSH, MuscleGroup.SHOULDERS)

    result = filter_eligible_exercises(request, [overhead])

    assert "EXERCISE_REJECTED_OVERHEAD_LIMIT" in result.rejected[0].reason_codes


def test_ranking_is_stable_explainable_and_seeded_for_ties() -> None:
    preferred_id = UUID("00000000-0000-0000-0000-000000000001")
    preferred = candidate(
        "preferred", MovementPattern.HORIZONTAL_PUSH, MuscleGroup.CHEST, id=preferred_id
    )
    other = candidate(
        "other",
        MovementPattern.HORIZONTAL_PUSH,
        MuscleGroup.CHEST,
        id=UUID("00000000-0000-0000-0000-000000000002"),
    )
    request = normalized(preferred_exercises=[preferred_id])

    first = rank_exercises(request, [other, preferred], RULESET)
    second = rank_exercises(request, [preferred, other], RULESET)

    assert [item.exercise.id for item in first] == [item.exercise.id for item in second]
    assert first[0].exercise.id == preferred_id
    assert "USER_PREFERRED" in first[0].reason_codes


def _full_body_catalog() -> list[ExerciseCandidate]:
    return [
        candidate("push", MovementPattern.HORIZONTAL_PUSH, MuscleGroup.CHEST),
        candidate("row", MovementPattern.HORIZONTAL_PULL, MuscleGroup.BACK),
        candidate("squat", MovementPattern.SQUAT, MuscleGroup.QUADRICEPS),
        candidate("hinge", MovementPattern.HIP_HINGE, MuscleGroup.HAMSTRINGS),
        candidate(
            "plank",
            MovementPattern.CORE_ANTI_EXTENSION,
            MuscleGroup.ABS,
            exercise_type=ExerciseType.CORE,
        ),
        candidate("calf", MovementPattern.CALF_RAISE, MuscleGroup.CALVES),
    ]


def test_full_body_session_covers_required_patterns_and_priority_is_first() -> None:
    request = normalized(priority_muscles=[MuscleGroup.BACK])
    eligibility = filter_eligible_exercises(request, _full_body_catalog())
    split = select_split(request, RULESET)
    volume = plan_weekly_volume(request, split, RULESET)

    sessions = build_sessions(request, split, volume, eligibility.eligible, RULESET)

    patterns = {item.movement_pattern for item in sessions[0].exercises}
    assert MovementPattern.HORIZONTAL_PUSH in patterns
    assert MovementPattern.HORIZONTAL_PULL in patterns
    assert MovementPattern.SQUAT in patterns
    assert sessions[0].exercises[0].primary_muscle is MuscleGroup.BACK
    assert (
        "PRIORITY_MUSCLE_PLACED_FIRST" in sessions[0].selection_reasons[sessions[0].exercises[0].id]
    )


def test_short_session_is_trimmed_to_realistic_exercise_count() -> None:
    request = normalized(session_duration_minutes=25)
    eligible = filter_eligible_exercises(request, _full_body_catalog()).eligible
    split = select_split(request, RULESET)
    volume = plan_weekly_volume(request, split, RULESET)

    sessions = build_sessions(request, split, volume, eligible, RULESET)

    assert len(sessions[0].exercises) <= 3
    assert "SESSION_TRIMMED_FOR_TIME_LIMIT" in sessions[0].reason_codes


def test_substitutions_are_drawn_only_from_eligible_candidates() -> None:
    request = normalized(blocked_caution_tags=[ExerciseCautionTag.WRIST_LOADING])
    selected = candidate("push", MovementPattern.HORIZONTAL_PUSH, MuscleGroup.CHEST)
    safe_sub = candidate("safe push", MovementPattern.HORIZONTAL_PUSH, MuscleGroup.CHEST)
    unsafe_sub = candidate(
        "unsafe push",
        MovementPattern.HORIZONTAL_PUSH,
        MuscleGroup.CHEST,
        caution_tags=frozenset({ExerciseCautionTag.WRIST_LOADING}),
    )
    catalog = _full_body_catalog() + [selected, safe_sub, unsafe_sub]
    eligible = filter_eligible_exercises(request, catalog).eligible
    split = select_split(request, RULESET)

    sessions = build_sessions(
        request,
        split,
        plan_weekly_volume(request, split, RULESET),
        eligible,
        RULESET,
    )

    substitutions = {item for values in sessions[0].substitutions.values() for item in values}
    assert unsafe_sub.id not in substitutions


def test_missing_required_safe_pattern_returns_structured_domain_error() -> None:
    request = normalized()
    eligible = filter_eligible_exercises(
        request,
        [candidate("push", MovementPattern.HORIZONTAL_PUSH, MuscleGroup.CHEST)],
    ).eligible
    split = select_split(request, RULESET)

    with pytest.raises(ValueError, match="NO_SAFE_EXERCISE_FOR_PATTERN"):
        build_sessions(
            request,
            split,
            plan_weekly_volume(request, split, RULESET),
            eligible,
            RULESET,
        )
