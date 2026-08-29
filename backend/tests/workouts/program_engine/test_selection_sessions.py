from uuid import UUID, uuid4

import pytest

from app.exercises.enums import (
    Difficulty,
    Equipment,
    ExerciseCautionTag,
    ExerciseType,
    MovementPattern,
    MuscleFocus,
    MuscleGroup,
)
from app.profile.enums import TrainingLocation
from app.workouts.program_engine.duration_policy import get_session_exercise_count_policy
from app.workouts.program_engine.eligibility import filter_eligible_exercises
from app.workouts.program_engine.enums import (
    BalanceAbility,
    BodyPosition,
    Goal,
    ImpactLimit,
    LoadLimit,
    SkillDemand,
    SplitType,
    StabilityDemand,
    TrainingExperience,
)
from app.workouts.program_engine.exercise_ranker import rank_exercises
from app.workouts.program_engine.normalization import normalize_request
from app.workouts.program_engine.replacement_ranker import rank_replacement_exercises
from app.workouts.program_engine.rulesets.resistance_training_v1 import RULESET
from app.workouts.program_engine.schemas import (
    ExerciseCandidate,
    NormalizedProgramRequest,
    ProgramGenerationRequest,
    RecentTrainingHistory,
    SplitPlan,
)
from app.workouts.program_engine.session_builder import SessionConstructionError, build_sessions
from app.workouts.program_engine.split_selector import generate_split_candidates, select_split
from app.workouts.program_engine.supplemental_policy import main_exercise_count
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


@pytest.mark.parametrize(
    ("blocked_tags", "exercise_values"),
    [
        (
            frozenset({ExerciseCautionTag.WRIST_LOADING}),
            {"movement_pattern": MovementPattern.HORIZONTAL_PUSH},
        ),
        (
            frozenset({ExerciseCautionTag.NECK_LOADING}),
            {"movement_pattern": MovementPattern.SHRUG, "primary_muscle": MuscleGroup.TRAPS},
        ),
        (
            frozenset({ExerciseCautionTag.SHOULDER_INTERNAL_ROTATION}),
            {
                "movement_pattern": MovementPattern.HORIZONTAL_PULL,
                "primary_muscle": MuscleGroup.SHOULDERS,
                "equipment": frozenset({Equipment.DUMBBELL}),
            },
        ),
        (
            frozenset({ExerciseCautionTag.DEEP_KNEE_FLEXION}),
            {"movement_pattern": MovementPattern.SQUAT},
        ),
        (
            frozenset({ExerciseCautionTag.LOWER_BACK_LOADING}),
            {"movement_pattern": MovementPattern.HIP_HINGE},
        ),
    ],
)
def test_existing_metadata_derives_conservative_caution_tags_before_ranking(
    blocked_tags: frozenset[ExerciseCautionTag],
    exercise_values: dict[str, object],
) -> None:
    request = normalized(blocked_caution_tags=blocked_tags)
    values = dict(exercise_values)
    pattern = values.pop("movement_pattern")
    muscle = values.pop("primary_muscle", MuscleGroup.CHEST)
    unsafe = candidate("metadata unsafe", pattern, muscle, **values)  # type: ignore[arg-type]

    result = filter_eligible_exercises(request, [unsafe])

    assert not result.eligible
    assert "EXERCISE_REJECTED_BLOCKED_CAUTION_TAG" in result.rejected[0].reason_codes


def test_multiple_cautions_apply_the_union_of_existing_caution_tags() -> None:
    request = normalized(
        blocked_caution_tags=[
            ExerciseCautionTag.SHOULDER_INTERNAL_ROTATION,
            ExerciseCautionTag.NECK_LOADING,
        ]
    )
    unsafe = candidate(
        "metadata shoulder shrug",
        MovementPattern.SHRUG,
        MuscleGroup.SHOULDERS,
        equipment=frozenset({Equipment.DUMBBELL}),
        caution_tags=frozenset({ExerciseCautionTag.SHOULDER_INTERNAL_ROTATION}),
    )

    result = filter_eligible_exercises(request, [unsafe])

    assert not result.eligible
    assert result.rejected[0].reason_codes.count("EXERCISE_REJECTED_BLOCKED_CAUTION_TAG") == 1


def test_lower_back_and_wrist_constraints_intersect_for_one_candidate() -> None:
    request = normalized(
        blocked_caution_tags=[
            ExerciseCautionTag.LOWER_BACK_LOADING,
            ExerciseCautionTag.WRIST_LOADING,
        ]
    )
    unsafe = candidate(
        "metadata combined risk",
        MovementPattern.HORIZONTAL_PUSH,
        MuscleGroup.CHEST,
        caution_tags=frozenset({ExerciseCautionTag.LOWER_BACK_LOADING}),
    )

    result = filter_eligible_exercises(request, [unsafe])

    assert not result.eligible
    assert "EXERCISE_REJECTED_BLOCKED_CAUTION_TAG" in result.rejected[0].reason_codes


def test_without_caution_normal_exercise_remains_eligible() -> None:
    exercise_item = candidate("normal push", MovementPattern.HORIZONTAL_PUSH, MuscleGroup.CHEST)

    result = filter_eligible_exercises(normalized(), [exercise_item])

    assert result.eligible == (exercise_item,)


def test_structurally_incomplete_metadata_fails_closed() -> None:
    incomplete = candidate(
        "incomplete metadata",
        MovementPattern.HORIZONTAL_PUSH,
        MuscleGroup.CHEST,
        equipment=frozenset(),
    )

    result = filter_eligible_exercises(
        normalized(blocked_caution_tags=[ExerciseCautionTag.WRIST_LOADING]),
        [incomplete],
    )

    assert not result.eligible
    assert "EXERCISE_REJECTED_MISSING_METADATA" in result.rejected[0].reason_codes


@pytest.mark.parametrize(
    "available_equipment",
    [
        frozenset({Equipment.BODYWEIGHT}),
        frozenset({Equipment.BODYWEIGHT, Equipment.DUMBBELL}),
    ],
)
def test_home_rejects_bodyweight_vertical_pull_without_pull_up_bar(
    available_equipment: frozenset[Equipment],
) -> None:
    pull_up_with_incomplete_metadata = candidate(
        "metadata pull up",
        MovementPattern.VERTICAL_PULL,
        MuscleGroup.BACK,
        equipment=frozenset({Equipment.BODYWEIGHT}),
    )

    result = filter_eligible_exercises(
        normalized(available_equipment=available_equipment),
        [pull_up_with_incomplete_metadata],
    )

    assert not result.eligible
    assert "EXERCISE_REJECTED_MISSING_EQUIPMENT" in result.rejected[0].reason_codes


def test_multi_equipment_candidate_requires_every_equipment_item() -> None:
    bench_press = candidate(
        "multi equipment press",
        MovementPattern.HORIZONTAL_PUSH,
        MuscleGroup.CHEST,
        equipment=frozenset({Equipment.DUMBBELL, Equipment.BENCH}),
    )

    missing_bench = filter_eligible_exercises(
        normalized(available_equipment=frozenset({Equipment.BODYWEIGHT, Equipment.DUMBBELL})),
        [bench_press],
    )
    with_bench = filter_eligible_exercises(
        normalized(
            available_equipment=frozenset(
                {Equipment.BODYWEIGHT, Equipment.DUMBBELL, Equipment.BENCH}
            )
        ),
        [bench_press],
    )

    assert not missing_bench.eligible
    assert with_bench.eligible == (bench_press,)


def test_gym_keeps_candidates_requiring_supported_gym_equipment() -> None:
    gym_exercise = candidate(
        "gym multi equipment row",
        MovementPattern.HORIZONTAL_PULL,
        MuscleGroup.BACK,
        equipment=frozenset(
            {Equipment.BARBELL, Equipment.CABLE, Equipment.MACHINE, Equipment.PULL_UP_BAR}
        ),
    )

    result = filter_eligible_exercises(
        normalized(
            training_location=TrainingLocation.GYM,
            available_equipment=frozenset(Equipment),
        ),
        [gym_exercise],
    )

    assert result.eligible == (gym_exercise,)


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


def _body_part_catalog() -> tuple[ExerciseCandidate, ...]:
    return (
        candidate("chest press", MovementPattern.HORIZONTAL_PUSH, MuscleGroup.CHEST),
        candidate("triceps extension", MovementPattern.ELBOW_EXTENSION, MuscleGroup.TRICEPS),
        candidate("row", MovementPattern.HORIZONTAL_PULL, MuscleGroup.BACK),
        candidate("curl", MovementPattern.ELBOW_FLEXION, MuscleGroup.BICEPS),
        candidate("shoulder press", MovementPattern.VERTICAL_PUSH, MuscleGroup.SHOULDERS),
        candidate("lateral raise", MovementPattern.SHOULDER_ABDUCTION, MuscleGroup.SHOULDERS),
        candidate("shrug", MovementPattern.SHRUG, MuscleGroup.TRAPS),
        candidate("squat", MovementPattern.SQUAT, MuscleGroup.QUADRICEPS),
        candidate("hinge", MovementPattern.HIP_HINGE, MuscleGroup.HAMSTRINGS),
        candidate("plank", MovementPattern.CORE_ANTI_EXTENSION, MuscleGroup.ABS),
    )


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


def test_session_selection_rejects_semantic_squat_duplicate_and_uses_quad_complement() -> None:
    request = normalized(
        available_equipment=frozenset({Equipment.BODYWEIGHT, Equipment.DUMBBELL, Equipment.BARBELL})
    )
    squat_one = candidate(
        "barbell squat",
        MovementPattern.SQUAT,
        MuscleGroup.QUADRICEPS,
        muscle_focus=MuscleFocus.GENERAL_QUADRICEPS,
        secondary_muscles=(MuscleGroup.GLUTES,),
        equipment=frozenset({Equipment.BARBELL}),
        substitution_group="squat_free_weight",
    )
    squat_two = candidate(
        "squat",
        MovementPattern.SQUAT,
        MuscleGroup.QUADRICEPS,
        muscle_focus=MuscleFocus.GENERAL_QUADRICEPS,
        secondary_muscles=(MuscleGroup.GLUTES,),
        equipment=frozenset({Equipment.BARBELL}),
        substitution_group="squat_free_weight",
    )
    knee_extension = candidate(
        "leg extension",
        MovementPattern.KNEE_EXTENSION,
        MuscleGroup.QUADRICEPS,
        exercise_type=ExerciseType.ISOLATION,
        equipment=frozenset({Equipment.DUMBBELL}),
        substitution_group="knee_extension",
    )
    catalog = [
        candidate("push", MovementPattern.HORIZONTAL_PUSH, MuscleGroup.CHEST),
        candidate("row", MovementPattern.HORIZONTAL_PULL, MuscleGroup.BACK),
        squat_one,
        squat_two,
        knee_extension,
        candidate("hinge", MovementPattern.HIP_HINGE, MuscleGroup.HAMSTRINGS),
        candidate("calf", MovementPattern.CALF_RAISE, MuscleGroup.CALVES),
    ]

    sessions = build_sessions(
        request,
        select_split(request, RULESET),
        plan_weekly_volume(request, select_split(request, RULESET), RULESET),
        filter_eligible_exercises(request, catalog).eligible,
        RULESET,
    )

    selected = sessions[0].exercises
    assert sum(item.id in {squat_one.id, squat_two.id} for item in selected) == 1
    assert any(item.id == knee_extension.id for item in selected)
    assert "SEMANTIC_NEAR_DUPLICATE_REJECTED" in sessions[0].reason_codes


def test_optional_trunk_work_is_not_forced_or_preference_selected() -> None:
    oblique_id = uuid4()
    request = normalized(preferred_exercises=[oblique_id])
    catalog = [
        candidate("push", MovementPattern.HORIZONTAL_PUSH, MuscleGroup.CHEST),
        candidate("row", MovementPattern.HORIZONTAL_PULL, MuscleGroup.BACK),
        candidate("squat", MovementPattern.SQUAT, MuscleGroup.QUADRICEPS),
        candidate("hinge", MovementPattern.HIP_HINGE, MuscleGroup.HAMSTRINGS),
        candidate(
            "front plank",
            MovementPattern.CORE_ANTI_EXTENSION,
            MuscleGroup.ABS,
            exercise_type=ExerciseType.CORE,
        ),
        candidate(
            "side plank",
            MovementPattern.CORE_ANTI_LATERAL_FLEXION,
            MuscleGroup.OBLIQUES,
            id=oblique_id,
            exercise_type=ExerciseType.CORE,
        ),
    ]
    eligibility = filter_eligible_exercises(request, catalog)
    split = select_split(request, RULESET)

    sessions = build_sessions(
        request,
        split,
        plan_weekly_volume(request, split, RULESET),
        eligibility.eligible,
        RULESET,
    )

    supplemental = tuple(
        item
        for item in sessions[0].exercises
        if item.primary_muscle in {MuscleGroup.ABS, MuscleGroup.OBLIQUES}
    )
    assert len(supplemental) <= 1
    assert not supplemental or supplemental[0].primary_muscle is MuscleGroup.ABS


def test_explicit_glute_priority_owns_repeated_shared_hinge_slots() -> None:
    request = normalized(
        available_training_days=4,
        priority_muscles=[MuscleGroup.GLUTES],
    )
    catalog = [
        candidate("push", MovementPattern.HORIZONTAL_PUSH, MuscleGroup.CHEST),
        candidate("row", MovementPattern.HORIZONTAL_PULL, MuscleGroup.BACK),
        candidate("squat", MovementPattern.SQUAT, MuscleGroup.QUADRICEPS),
        candidate("hamstring hinge", MovementPattern.HIP_HINGE, MuscleGroup.HAMSTRINGS),
        candidate(
            "glute bridge",
            MovementPattern.HIP_EXTENSION,
            MuscleGroup.GLUTES,
            exercise_type=ExerciseType.ISOLATION,
        ),
        candidate(
            "plank",
            MovementPattern.CORE_ANTI_EXTENSION,
            MuscleGroup.ABS,
            exercise_type=ExerciseType.CORE,
        ),
        candidate("leg curl", MovementPattern.KNEE_FLEXION, MuscleGroup.HAMSTRINGS),
        candidate("calf raise", MovementPattern.CALF_RAISE, MuscleGroup.CALVES),
    ]
    eligibility = filter_eligible_exercises(request, catalog)
    split = SplitPlan(
        SplitType.UPPER_LOWER,
        ("upper", "lower", "upper", "lower"),
        (0, 1, 3, 4),
        1,
        (),
    )

    sessions = build_sessions(
        request,
        split,
        plan_weekly_volume(request, split, RULESET),
        eligibility.eligible,
        RULESET,
    )

    lower_sessions = tuple(session for session in sessions if session.focus == "lower")

    assert all(
        any(item.primary_muscle is MuscleGroup.GLUTES for item in session.exercises)
        for session in lower_sessions
    )


def test_specialization_session_resolves_to_the_athletes_priority_muscle() -> None:
    request = normalized(
        available_training_days=5,
        priority_muscles=[MuscleGroup.SHOULDERS],
    )
    eligible = filter_eligible_exercises(request, _body_part_catalog()).eligible
    split = SplitPlan(
        SplitType.UPPER_LOWER_SPECIALIZATION,
        ("upper", "lower", "upper", "lower", "specialization"),
        (0, 1, 3, 4, 6),
        1,
        (),
    )

    sessions = build_sessions(
        request,
        split,
        plan_weekly_volume(request, split, RULESET),
        eligible,
        RULESET,
    )

    assert sessions[-1].focus == "shoulders_traps"


@pytest.mark.parametrize(
    "split_type",
    [
        SplitType.UPPER_LOWER,
        SplitType.FULL_BODY_FOUR,
        SplitType.UPPER_LOWER_FULL,
        SplitType.PHUL,
        SplitType.BODY_PART_ROTATION,
    ],
)
def test_each_four_day_candidate_builds_four_sessions(split_type: SplitType) -> None:
    request = normalized(available_training_days=4)
    eligible = filter_eligible_exercises(request, _body_part_catalog()).eligible
    candidate = next(item for item in generate_split_candidates(4) if item.split_type is split_type)
    split = SplitPlan(candidate.split_type, candidate.day_focuses, (0, 1, 3, 4), 1, ())

    sessions = build_sessions(
        request,
        split,
        plan_weekly_volume(request, split, RULESET),
        eligible,
        RULESET,
    )

    assert len(sessions) == 4


@pytest.mark.parametrize(
    "split_type",
    [
        SplitType.UPPER_LOWER_SPECIALIZATION,
        SplitType.PUSH_PULL_LEGS_UPPER_LOWER,
        SplitType.BODY_PART_ROTATION,
    ],
)
def test_each_five_day_candidate_builds_five_sessions(split_type: SplitType) -> None:
    request = normalized(available_training_days=5)
    eligible = filter_eligible_exercises(request, _body_part_catalog()).eligible
    candidate = next(item for item in generate_split_candidates(5) if item.split_type is split_type)
    split = SplitPlan(candidate.split_type, candidate.day_focuses, (0, 1, 2, 4, 5), 1, ())

    sessions = build_sessions(
        request,
        split,
        plan_weekly_volume(request, split, RULESET),
        eligible,
        RULESET,
    )

    assert len(sessions) == 5


@pytest.mark.parametrize(
    "split_type",
    [
        SplitType.PUSH_PULL_LEGS_X2,
        SplitType.UPPER_LOWER_X3,
        SplitType.BODY_PART_ROTATION,
    ],
)
def test_each_six_day_candidate_builds_six_sessions(split_type: SplitType) -> None:
    request = normalized(available_training_days=6)
    eligible = filter_eligible_exercises(request, _body_part_catalog()).eligible
    candidate = next(item for item in generate_split_candidates(6) if item.split_type is split_type)
    split = SplitPlan(candidate.split_type, candidate.day_focuses, (0, 1, 2, 3, 4, 5), 1, ())

    sessions = build_sessions(
        request,
        split,
        plan_weekly_volume(request, split, RULESET),
        eligible,
        RULESET,
    )

    assert len(sessions) == 6


def test_short_session_keeps_the_minimum_exercise_count() -> None:
    request = normalized(session_duration_minutes=30)
    eligible = filter_eligible_exercises(request, _full_body_catalog()).eligible
    split = select_split(request, RULESET)
    volume = plan_weekly_volume(request, split, RULESET)

    sessions = build_sessions(request, split, volume, eligible, RULESET)

    count_policy = get_session_exercise_count_policy(30, RULESET)
    assert count_policy.contains(main_exercise_count(sessions[0].exercises))
    assert "SESSION_TRIMMED_FOR_TIME_LIMIT" in sessions[0].reason_codes


def test_substitutions_are_drawn_only_from_eligible_candidates() -> None:
    request = normalized(blocked_caution_tags=[ExerciseCautionTag.WRIST_LOADING])
    selected = candidate("push", MovementPattern.HORIZONTAL_PUSH, MuscleGroup.CHEST)
    safe_sub = candidate(
        "safe push",
        MovementPattern.HORIZONTAL_PUSH,
        MuscleGroup.CHEST,
        equipment=frozenset({Equipment.DUMBBELL}),
    )
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


def test_replacement_excludes_incompatible_candidate_despite_matching_substitution_group() -> None:
    request = normalized()
    target = candidate(
        "target push",
        MovementPattern.HORIZONTAL_PUSH,
        MuscleGroup.CHEST,
        substitution_group="horizontal-push",
    )
    same_family = candidate(
        "same family pull",
        MovementPattern.HORIZONTAL_PULL,
        MuscleGroup.CHEST,
        substitution_group="horizontal-push",
    )
    same_pattern = candidate(
        "same pattern chest",
        MovementPattern.HORIZONTAL_PUSH,
        MuscleGroup.CHEST,
        substitution_group="shoulder-push",
    )

    ranked = rank_replacement_exercises(request, target, (same_pattern, same_family))

    assert ranked == (same_pattern,)


def test_generic_push_slot_does_not_create_cross_push_equivalence() -> None:
    request = normalized()
    target = candidate(
        "target overhead press",
        MovementPattern.VERTICAL_PUSH,
        MuscleGroup.SHOULDERS,
    )
    horizontal = candidate(
        "horizontal shoulder press",
        MovementPattern.HORIZONTAL_PUSH,
        MuscleGroup.SHOULDERS,
    )

    ranked = rank_replacement_exercises(
        request,
        target,
        (horizontal,),
        allowed_patterns=frozenset(
            {MovementPattern.VERTICAL_PUSH, MovementPattern.HORIZONTAL_PUSH}
        ),
        target_muscles=frozenset({MuscleGroup.SHOULDERS}),
    )

    assert ranked == ()


def test_replacement_ranking_excludes_unavailable_and_unsafe_candidates() -> None:
    blocked_id = uuid4()
    request = normalized(
        blocked_exercises=[blocked_id],
        blocked_caution_tags=[ExerciseCautionTag.WRIST_LOADING],
    )
    target = candidate(
        "target push",
        MovementPattern.HORIZONTAL_PUSH,
        MuscleGroup.CHEST,
        substitution_group="push",
    )
    unavailable = candidate(
        "barbell push",
        MovementPattern.HORIZONTAL_PUSH,
        MuscleGroup.CHEST,
        equipment=frozenset({Equipment.BARBELL}),
        substitution_group="push",
    )
    blocked = candidate(
        "blocked push",
        MovementPattern.HORIZONTAL_PUSH,
        MuscleGroup.CHEST,
        id=blocked_id,
        substitution_group="push",
    )
    unsafe = candidate(
        "wrist unsafe push",
        MovementPattern.HORIZONTAL_PUSH,
        MuscleGroup.CHEST,
        caution_tags=frozenset({ExerciseCautionTag.WRIST_LOADING}),
        substitution_group="push",
    )

    ranked = rank_replacement_exercises(request, target, (unavailable, blocked, unsafe))

    assert ranked == ()


def test_exact_curated_replacement_wins_before_user_dislike() -> None:
    exact_id = uuid4()
    request = normalized(disliked_exercises=[exact_id])
    target = candidate(
        "target incline press",
        MovementPattern.HORIZONTAL_PUSH,
        MuscleGroup.CHEST,
        substitution_group="horizontal_press_incline",
    )
    exact = candidate(
        "disliked exact incline press",
        MovementPattern.HORIZONTAL_PUSH,
        MuscleGroup.CHEST,
        id=exact_id,
        substitution_group="horizontal_press_incline",
    )
    metadata_fallback = candidate(
        "preferred flat press",
        MovementPattern.HORIZONTAL_PUSH,
        MuscleGroup.CHEST,
        substitution_group="horizontal_press_flat",
    )

    ranked = rank_replacement_exercises(request, target, (metadata_fallback, exact))

    assert ranked[0] is exact


def test_unsafe_preferred_exact_group_never_beats_safe_metadata_fallback() -> None:
    unsafe_id = uuid4()
    request = normalized(
        preferred_exercises=[unsafe_id],
        blocked_exercises=[unsafe_id],
    )
    target = candidate(
        "target press",
        MovementPattern.HORIZONTAL_PUSH,
        MuscleGroup.CHEST,
        substitution_group="horizontal_press_flat",
    )
    unsafe_exact = candidate(
        "unsafe exact press",
        MovementPattern.HORIZONTAL_PUSH,
        MuscleGroup.CHEST,
        id=unsafe_id,
        substitution_group="horizontal_press_flat",
    )
    safe_fallback = candidate(
        "safe fallback press",
        MovementPattern.HORIZONTAL_PUSH,
        MuscleGroup.CHEST,
        substitution_group=None,
    )

    ranked = rank_replacement_exercises(request, target, (unsafe_exact, safe_fallback))

    assert ranked == (safe_fallback,)


def test_metadata_fallback_preserves_movement_role_without_curated_group() -> None:
    request = normalized()
    target = candidate(
        "romanian deadlift",
        MovementPattern.HIP_HINGE,
        MuscleGroup.HAMSTRINGS,
        substitution_group=None,
    )
    valid_hinge = candidate(
        "dumbbell romanian deadlift",
        MovementPattern.HIP_HINGE,
        MuscleGroup.HAMSTRINGS,
        substitution_group=None,
    )
    wrong_role = candidate(
        "lying leg curl",
        MovementPattern.KNEE_FLEXION,
        MuscleGroup.HAMSTRINGS,
        substitution_group="knee_flexion_leg_curl",
    )

    ranked = rank_replacement_exercises(request, target, (wrong_role, valid_hinge))

    assert ranked == (valid_hinge,)


def test_range_of_motion_similarity_precedes_skill_and_stability_tie_breaks() -> None:
    request = normalized(
        training_experience="advanced",
        training_age_months=72,
        balance_requirement=BalanceAbility.HIGH,
    )
    target = candidate(
        "target squat",
        MovementPattern.SQUAT,
        MuscleGroup.QUADRICEPS,
        substitution_group=None,
        range_of_motion_profile=frozenset({"deep_knee_flexion"}),
    )
    same_rom = candidate(
        "same rom squat",
        MovementPattern.SQUAT,
        MuscleGroup.QUADRICEPS,
        substitution_group=None,
        range_of_motion_profile=frozenset({"deep_knee_flexion"}),
        stability_demand=StabilityDemand.HIGH,
        skill_demand=SkillDemand.HIGH,
    )
    lower_demand_wrong_rom = candidate(
        "shortened squat",
        MovementPattern.SQUAT,
        MuscleGroup.QUADRICEPS,
        substitution_group=None,
        range_of_motion_profile=frozenset({"shortened"}),
        stability_demand=StabilityDemand.LOW,
        skill_demand=SkillDemand.LOW,
    )

    ranked = rank_replacement_exercises(
        request,
        target,
        (lower_demand_wrong_rom, same_rom),
    )

    assert ranked[0] is same_rom


def test_lower_risk_compatible_replacement_outranks_riskier_candidate() -> None:
    request = normalized(
        impact_limit=ImpactLimit.HIGH,
        axial_load_limit=LoadLimit.HIGH,
        balance_requirement=BalanceAbility.HIGH,
    )
    target = candidate(
        "target squat",
        MovementPattern.SQUAT,
        MuscleGroup.QUADRICEPS,
        substitution_group="squat",
    )
    lower_risk = candidate(
        "supported squat",
        MovementPattern.SQUAT,
        MuscleGroup.QUADRICEPS,
        substitution_group="squat",
        impact_level=ImpactLimit.LOW,
        axial_loading_level=LoadLimit.LOW,
        stability_demand=StabilityDemand.LOW,
        skill_demand=SkillDemand.LOW,
    )
    riskier = candidate(
        "heavy squat",
        MovementPattern.SQUAT,
        MuscleGroup.QUADRICEPS,
        substitution_group="squat",
        impact_level=ImpactLimit.HIGH,
        axial_loading_level=LoadLimit.HIGH,
        stability_demand=StabilityDemand.HIGH,
        skill_demand=SkillDemand.HIGH,
    )

    ranked = rank_replacement_exercises(request, target, (riskier, lower_risk))

    assert ranked[0] is lower_risk


def test_lower_back_caution_rejects_unsupported_row_but_keeps_supported_row() -> None:
    request = normalized(
        blocked_caution_tags=[ExerciseCautionTag.LOWER_BACK_LOADING],
    )
    unsupported = candidate(
        "standing row",
        MovementPattern.HORIZONTAL_PULL,
        MuscleGroup.BACK,
        body_position=BodyPosition.STANDING,
        axial_loading_level=LoadLimit.MODERATE,
    )
    supported = candidate(
        "chest supported row",
        MovementPattern.HORIZONTAL_PULL,
        MuscleGroup.BACK,
        body_position=BodyPosition.SUPPORTED,
        axial_loading_level=LoadLimit.LOW,
    )

    result = filter_eligible_exercises(request, [unsupported, supported])

    assert result.eligible == (supported,)
    assert result.rejected[0].exercise_id == unsupported.id
    assert "EXERCISE_REJECTED_AXIAL_LOAD_LIMIT" in result.rejected[0].reason_codes


def test_dislike_applies_after_semantic_fit_and_order_remains_deterministic() -> None:
    disliked_id = uuid4()
    request = normalized(disliked_exercises=[disliked_id])
    target = candidate(
        "target row",
        MovementPattern.HORIZONTAL_PULL,
        MuscleGroup.BACK,
        substitution_group="row",
    )
    disliked_family = candidate(
        "disliked family row",
        MovementPattern.HORIZONTAL_PULL,
        MuscleGroup.BACK,
        id=disliked_id,
        substitution_group="row",
    )
    safe_fallback = candidate(
        "safe fallback row",
        MovementPattern.HORIZONTAL_PULL,
        MuscleGroup.BACK,
        substitution_group="different-row",
    )

    forward = rank_replacement_exercises(request, target, (disliked_family, safe_fallback))
    reverse = rank_replacement_exercises(request, target, (safe_fallback, disliked_family))

    assert forward[0] is disliked_family
    assert tuple(item.id for item in forward) == tuple(item.id for item in reverse)


def test_forward_curated_alternative_precedes_otherwise_better_role_match() -> None:
    request = normalized()
    curated_id = uuid4()
    target = candidate(
        "target press",
        MovementPattern.HORIZONTAL_PUSH,
        MuscleGroup.CHEST,
        exercise_type=ExerciseType.COMPOUND,
        id=uuid4(),
        curated_alternative_ids=(curated_id,),
    )
    curated = candidate(
        "curated press",
        MovementPattern.HORIZONTAL_PUSH,
        MuscleGroup.CHEST,
        id=curated_id,
        exercise_type=ExerciseType.COMPOUND,
        substitution_group=None,
    )
    fallback = candidate(
        "same-group press",
        MovementPattern.HORIZONTAL_PUSH,
        MuscleGroup.CHEST,
        exercise_type=ExerciseType.COMPOUND,
        substitution_group=target.substitution_group,
    )

    assert rank_replacement_exercises(request, target, (fallback, curated))[0] is curated


def test_curated_alternative_direction_is_not_implied_in_reverse() -> None:
    request = normalized()
    alternative_id = uuid4()
    target_a = candidate(
        "target a press",
        MovementPattern.HORIZONTAL_PUSH,
        MuscleGroup.CHEST,
        exercise_type=ExerciseType.COMPOUND,
        muscle_focus=MuscleFocus.UPPER_CHEST,
        substitution_group="target-a",
        id=uuid4(),
        curated_alternative_ids=(alternative_id,),
    )
    target_b = candidate(
        "target b press",
        MovementPattern.HORIZONTAL_PUSH,
        MuscleGroup.CHEST,
        exercise_type=ExerciseType.COMPOUND,
        muscle_focus=MuscleFocus.UPPER_CHEST,
        substitution_group="target-b",
        id=alternative_id,
        curated_alternative_ids=(),
    )
    reverse_fallback = candidate(
        "reverse role press",
        MovementPattern.HORIZONTAL_PUSH,
        MuscleGroup.CHEST,
        exercise_type=ExerciseType.COMPOUND,
        muscle_focus=MuscleFocus.UPPER_CHEST,
        substitution_group="target-b",
    )

    forward = rank_replacement_exercises(request, target_a, (reverse_fallback, target_b))
    reverse = rank_replacement_exercises(request, target_b, (target_a, reverse_fallback))

    assert forward[0] is target_b
    assert reverse[0] is reverse_fallback


def test_curated_alternative_still_requires_eligibility_and_slot_compatibility() -> None:
    blocked_id = uuid4()
    request = normalized(
        blocked_exercises=[blocked_id],
        blocked_caution_tags=[ExerciseCautionTag.WRIST_LOADING],
    )
    blocked = candidate(
        "blocked curated push",
        MovementPattern.HORIZONTAL_PUSH,
        MuscleGroup.CHEST,
        id=blocked_id,
    )
    unsafe_id = uuid4()
    unsafe = candidate(
        "unsafe curated push",
        MovementPattern.HORIZONTAL_PUSH,
        MuscleGroup.CHEST,
        id=unsafe_id,
        caution_tags=frozenset({ExerciseCautionTag.WRIST_LOADING}),
    )
    incompatible_id = uuid4()
    incompatible = candidate(
        "incompatible curated pull",
        MovementPattern.HORIZONTAL_PULL,
        MuscleGroup.BACK,
        id=incompatible_id,
    )
    unavailable_id = uuid4()
    unavailable = candidate(
        "unavailable curated push",
        MovementPattern.HORIZONTAL_PUSH,
        MuscleGroup.CHEST,
        id=unavailable_id,
        equipment=frozenset({Equipment.BARBELL}),
    )
    target = candidate(
        "target push",
        MovementPattern.HORIZONTAL_PUSH,
        MuscleGroup.CHEST,
        curated_alternative_ids=(blocked_id, unsafe_id, incompatible_id, unavailable_id),
    )

    assert (
        rank_replacement_exercises(request, target, (blocked, unsafe, incompatible, unavailable))
        == ()
    )


def test_missing_required_slot_rejects_session_before_supplements() -> None:
    request = normalized()
    eligible = filter_eligible_exercises(
        request,
        [
            candidate("push one", MovementPattern.HORIZONTAL_PUSH, MuscleGroup.CHEST),
            candidate("push two", MovementPattern.HORIZONTAL_PUSH, MuscleGroup.CHEST),
        ],
    ).eligible
    split = select_split(request, RULESET)

    with pytest.raises(SessionConstructionError) as error:
        build_sessions(
            request,
            split,
            plan_weekly_volume(request, split, RULESET),
            eligible,
            RULESET,
        )

    assert error.value.reason_codes[0] == "SESSION_CONSTRUCTION_FAILED_REQUIRED_SLOT"
    assert any(
        code.startswith("REQUIRED_PATTERN_UNAVAILABLE:") for code in error.value.reason_codes
    )


def test_supplements_are_added_only_after_required_slots_are_satisfied() -> None:
    request = normalized()
    eligible = filter_eligible_exercises(
        request,
        [
            candidate("push one", MovementPattern.HORIZONTAL_PUSH, MuscleGroup.CHEST),
            candidate("push two", MovementPattern.HORIZONTAL_PUSH, MuscleGroup.CHEST),
            candidate("push three", MovementPattern.HORIZONTAL_PUSH, MuscleGroup.CHEST),
            candidate("row", MovementPattern.HORIZONTAL_PULL, MuscleGroup.BACK),
            candidate("squat", MovementPattern.SQUAT, MuscleGroup.QUADRICEPS),
        ],
    ).eligible
    split = select_split(request, RULESET)

    sessions = build_sessions(
        request,
        split,
        plan_weekly_volume(request, split, RULESET),
        eligible,
        RULESET,
    )

    patterns = {item.movement_pattern for item in sessions[0].exercises}
    assert {
        MovementPattern.HORIZONTAL_PUSH,
        MovementPattern.HORIZONTAL_PULL,
        MovementPattern.SQUAT,
    }.issubset(patterns)
    assert len(sessions[0].exercises) == RULESET.minimum_exercises_per_session
    assert "SESSION_SUPPLEMENTED_TO_MINIMUM" in sessions[0].reason_codes


def test_required_slot_recovery_uses_target_muscle_not_global_pattern_presence() -> None:
    request = normalized()
    split = SplitPlan(
        split_type=SplitType.BODY_PART_ROTATION,
        day_focuses=("shoulders_traps",),
        weekdays=(1,),
        score=0,
        reason_codes=(),
    )
    globally_matching_but_wrong_target = candidate(
        "chest vertical press",
        MovementPattern.VERTICAL_PUSH,
        MuscleGroup.CHEST,
    )
    safe_focus_accessories = [
        candidate(f"trap row {index}", MovementPattern.HORIZONTAL_PULL, MuscleGroup.TRAPS)
        for index in range(RULESET.minimum_exercises_per_session)
    ]

    sessions = build_sessions(
        request,
        split,
        plan_weekly_volume(request, split, RULESET),
        tuple((globally_matching_but_wrong_target, *safe_focus_accessories)),
        RULESET,
    )

    assert len(sessions[0].exercises) == RULESET.minimum_exercises_per_session
    assert globally_matching_but_wrong_target not in sessions[0].exercises
    assert "RECOVERY_APPLIED_REQUIRED_SLOT_RELAXATION" in sessions[0].reason_codes
    assert "SLOT_SEMANTIC_MISMATCH" in sessions[0].reason_codes


def test_required_slot_uses_valid_suboptimal_candidate_before_relaxing() -> None:
    request = normalized()
    split = SplitPlan(
        split_type=SplitType.BODY_PART_ROTATION,
        day_focuses=("shoulders_traps",),
        weekdays=(1,),
        score=0,
        reason_codes=(),
    )
    suboptimal_press = candidate(
        "compound chest press with shoulder target",
        MovementPattern.VERTICAL_PUSH,
        MuscleGroup.CHEST,
        secondary_muscles=(MuscleGroup.SHOULDERS,),
    )
    accessories = [
        candidate(f"shoulder trap row {index}", MovementPattern.HORIZONTAL_PULL, MuscleGroup.TRAPS)
        for index in range(RULESET.minimum_exercises_per_session)
    ]

    sessions = build_sessions(
        request,
        split,
        plan_weekly_volume(request, split, RULESET),
        tuple((suboptimal_press, *accessories)),
        RULESET,
    )

    assert suboptimal_press in sessions[0].exercises
    assert "VALID_BUT_SUBOPTIMAL_SEMANTICS" in sessions[0].selection_reasons[suboptimal_press.id]
    assert "RECOVERY_APPLIED_REQUIRED_SLOT_RELAXATION" not in sessions[0].reason_codes


def test_body_part_rotation_places_chest_and_direct_triceps_in_one_session() -> None:
    request = normalized(
        priority_muscles=[MuscleGroup.CHEST],
        training_experience=TrainingExperience.ADVANCED,
        training_age_months=72,
        recent_training_history=RecentTrainingHistory(consistent_weeks=40),
    )
    split = SplitPlan(
        SplitType.BODY_PART_ROTATION,
        ("chest_triceps",),
        (0,),
        1,
        (),
    )

    sessions = build_sessions(
        request,
        split,
        plan_weekly_volume(request, split, RULESET),
        _body_part_catalog(),
        RULESET,
    )

    muscles = {item.primary_muscle for item in sessions[0].exercises}
    assert {MuscleGroup.CHEST, MuscleGroup.TRICEPS}.issubset(muscles)
    assert sessions[0].exercises[0].primary_muscle is MuscleGroup.CHEST


def test_body_part_rotation_places_priority_shoulders_first() -> None:
    request = normalized(priority_muscles=[MuscleGroup.SHOULDERS])
    split = SplitPlan(
        SplitType.BODY_PART_ROTATION,
        ("shoulders_traps",),
        (0,),
        1,
        (),
    )

    sessions = build_sessions(
        request,
        split,
        plan_weekly_volume(request, split, RULESET),
        _body_part_catalog(),
        RULESET,
    )

    assert sessions[0].exercises[0].primary_muscle is MuscleGroup.SHOULDERS


def test_specialization_day_resolves_to_priority_muscle_group() -> None:
    request = normalized(
        priority_muscles=[MuscleGroup.BACK],
        training_experience=TrainingExperience.INTERMEDIATE,
        training_age_months=30,
        recent_training_history=RecentTrainingHistory(consistent_weeks=20),
    )
    split = SplitPlan(SplitType.BODY_PART_ROTATION, ("specialization",), (0,), 1, ())
    sessions = build_sessions(
        request,
        split,
        plan_weekly_volume(request, split, RULESET),
        _body_part_catalog(),
        RULESET,
    )

    assert sessions[0].focus == "back_biceps"
    assert {item.primary_muscle for item in sessions[0].exercises}.issuperset(
        {MuscleGroup.BACK, MuscleGroup.BICEPS}
    )
