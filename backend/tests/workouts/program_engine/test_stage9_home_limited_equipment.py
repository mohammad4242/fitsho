from collections.abc import Iterable
from dataclasses import replace

import pytest

from app.exercises.enums import (
    Equipment,
    ExerciseCautionTag,
    ExerciseType,
    MovementPattern,
    MuscleFocus,
    MuscleGroup,
)
from app.profile.enums import TrainingLocation
from app.workouts.program_engine.eligibility import filter_eligible_exercises
from app.workouts.program_engine.engine import generate_program
from app.workouts.program_engine.enums import (
    BalanceAbility,
    Goal,
    ImpactLimit,
    LoadLimit,
    TrainingExperience,
)
from app.workouts.program_engine.equipment import effective_required_equipment
from app.workouts.program_engine.exercise_semantics import ExerciseRoleSignature
from app.workouts.program_engine.normalization import normalize_request
from app.workouts.program_engine.rulesets.resistance_training_v1 import RULESET
from app.workouts.program_engine.safety import effective_caution_tags
from app.workouts.program_engine.substitution_engine import (
    SubstitutionContext,
    rank_substitutions,
)
from app.workouts.program_engine.substitution_policy import (
    KNEE_PATTERNS,
    SubstitutionCause,
    SubstitutionPolicyContext,
    evaluate_substitution_policy,
)
from tests.workouts.program_engine.golden_fixtures import exercise, full_catalog, request

EQUIPMENT_CASES = (
    pytest.param(
        "bodyweight_only",
        (Equipment.BODYWEIGHT,),
        TrainingExperience.BEGINNER,
        Goal.STRENGTH,
        2,
        True,
        id="bodyweight-only-beginner-strength-2d",
    ),
    pytest.param(
        "dumbbells_only",
        (Equipment.DUMBBELL,),
        TrainingExperience.INTERMEDIATE,
        Goal.MUSCLE_GAIN,
        4,
        False,
        id="dumbbells-only-intermediate-muscle-gain-4d",
    ),
    pytest.param(
        "bodyweight_dumbbells",
        (Equipment.BODYWEIGHT, Equipment.DUMBBELL),
        TrainingExperience.BEGINNER,
        Goal.MUSCLE_GAIN,
        3,
        True,
        id="bodyweight-dumbbells-beginner-muscle-gain-3d",
    ),
    pytest.param(
        "dumbbells_bench",
        (Equipment.DUMBBELL, Equipment.BENCH),
        TrainingExperience.INTERMEDIATE,
        Goal.STRENGTH,
        4,
        False,
        id="dumbbells-bench-intermediate-strength-4d",
    ),
    pytest.param(
        "bands_only",
        (Equipment.RESISTANCE_BAND,),
        TrainingExperience.BEGINNER,
        Goal.STRENGTH,
        3,
        False,
        id="bands-beginner-strength-3d",
    ),
    pytest.param(
        "bands_dumbbells",
        (Equipment.RESISTANCE_BAND, Equipment.DUMBBELL),
        TrainingExperience.INTERMEDIATE,
        Goal.MUSCLE_GAIN,
        2,
        True,
        id="bands-dumbbells-intermediate-muscle-gain-2d",
    ),
    pytest.param(
        "bodyweight_pull_up_bar",
        (Equipment.BODYWEIGHT, Equipment.PULL_UP_BAR),
        TrainingExperience.INTERMEDIATE,
        Goal.STRENGTH,
        4,
        True,
        id="bodyweight-pull-up-bar-intermediate-strength-4d",
    ),
    pytest.param(
        "complete_home",
        (
            Equipment.DUMBBELL,
            Equipment.BENCH,
            Equipment.RESISTANCE_BAND,
            Equipment.PULL_UP_BAR,
        ),
        TrainingExperience.BEGINNER,
        Goal.MUSCLE_GAIN,
        3,
        True,
        id="complete-home-beginner-muscle-gain-3d",
    ),
)


def _build_request(
    equipment: Iterable[Equipment],
    experience: TrainingExperience,
    goal: Goal,
    days: int,
    **overrides: object,
):
    return request(
        available_equipment=list(equipment),
        training_location=TrainingLocation.HOME,
        training_experience=experience,
        training_age_months=36 if experience is TrainingExperience.INTERMEDIATE else 3,
        primary_goal=goal,
        available_training_days=days,
        **overrides,
    )


def _assert_safe_home_program(result, source, catalog) -> None:
    assert result.program is not None
    program = result.program
    assert program.validation_report.is_valid, program.validation_report.errors
    assert len(program.weekly_schedule) == source.available_training_days

    by_id = {item.id: item for item in catalog}
    available = set(source.available_equipment)
    for day in program.weekly_schedule:
        for programmed in day.exercises:
            assert programmed.exercise_type in {
                ExerciseType.COMPOUND,
                ExerciseType.ISOLATION,
                ExerciseType.CORE,
            }
            assert programmed.primary_muscle is not None
            assert programmed.is_active is True
            assert programmed.is_programmable is True
            assert programmed.needs_review is False
            assert not effective_required_equipment(
                programmed.equipment, programmed.movement_pattern
            ).difference(available)
            assert not effective_caution_tags(programmed).intersection(source.blocked_caution_tags)
            assert programmed.movement_pattern not in source.blocked_movement_patterns
            assert not {
                "HARD_INCOMPATIBLE",
                "RECOVERED_INCOMPATIBLE_SEMANTICS",
            }.intersection(programmed.reason_codes)

            replacements = tuple(by_id[item_id] for item_id in programmed.substitution_exercise_ids)
            target = by_id[programmed.exercise_id]
            for replacement in replacements:
                assert replacement.is_active is True
                assert replacement.is_programmable is True
                assert replacement.needs_review is False
                assert not effective_required_equipment(
                    replacement.equipment, replacement.movement_pattern
                ).difference(available)
                assert not effective_caution_tags(replacement).intersection(
                    source.blocked_caution_tags
                )
                assert replacement.movement_pattern not in source.blocked_movement_patterns
                assert evaluate_substitution_policy(
                    ExerciseRoleSignature.from_candidate(target),
                    ExerciseRoleSignature.from_candidate(replacement),
                    SubstitutionPolicyContext(
                        goal=source.primary_goal,
                        cause=SubstitutionCause.DISPLAY_ALTERNATIVE,
                        target_muscles=frozenset({target.primary_muscle})
                        if target.primary_muscle is not None
                        else frozenset(),
                    ),
                ).compatible

            exact_role = tuple(
                candidate
                for candidate in replacements
                if candidate.movement_pattern is programmed.movement_pattern
                and candidate.primary_muscle is programmed.primary_muscle
                and candidate.muscle_focus is target.muscle_focus
                and candidate.exercise_type is programmed.exercise_type
            )
            if exact_role:
                assert replacements[0] is exact_role[0]


@pytest.mark.parametrize(
    ("name", "equipment", "experience", "goal", "days", "expected_success"),
    EQUIPMENT_CASES,
)
def test_home_equipment_matrix_preserves_safe_deterministic_roles(
    name: str,
    equipment: tuple[Equipment, ...],
    experience: TrainingExperience,
    goal: Goal,
    days: int,
    expected_success: bool,
) -> None:
    catalog = full_catalog()
    source = _build_request(equipment, experience, goal, days)
    first = generate_program(source, catalog, RULESET)
    second = generate_program(source, catalog, RULESET)

    if not expected_success:
        assert first.program is None
        assert second.program is None
        assert first.error_code is not None
        assert first.error_code is second.error_code
        assert first.errors == second.errors
        eligible = filter_eligible_exercises(normalize_request(source), catalog).eligible
        if not eligible:
            assert "NO_ELIGIBLE_EXERCISES" in first.errors
        else:
            assert not {item.movement_pattern for item in eligible}.intersection(KNEE_PATTERNS)
            assert "REQUIRED_SLOT_HARD_IMPOSSIBILITY" in first.errors
            assert any("REQUIRED_PATTERN_UNAVAILABLE" in error for error in first.errors)
        return

    assert first.is_success, first.errors
    assert second.is_success, second.errors
    assert first.program is not None and second.program is not None
    assert first.program == second.program
    first_ids = tuple(
        (day.focus, tuple(item.exercise_id for item in day.exercises))
        for day in first.program.weekly_schedule
    )
    second_ids = tuple(
        (day.focus, tuple(item.exercise_id for item in day.exercises))
        for day in second.program.weekly_schedule
    )
    assert first_ids == second_ids
    _assert_safe_home_program(first, source, catalog)


def test_home_equipment_substitution_preserves_available_muscle_focus() -> None:
    target = replace(
        exercise(
            "barbell-upper-chest-press",
            MovementPattern.HORIZONTAL_PUSH,
            MuscleGroup.CHEST,
            equipment=frozenset({Equipment.BARBELL}),
        ),
        muscle_focus=MuscleFocus.UPPER_CHEST,
    )
    exact_focus = replace(
        exercise(
            "dumbbell-upper-chest-press",
            MovementPattern.HORIZONTAL_PUSH,
            MuscleGroup.CHEST,
            equipment=frozenset({Equipment.DUMBBELL}),
        ),
        muscle_focus=MuscleFocus.UPPER_CHEST,
    )
    degraded_focus = replace(
        exercise(
            "dumbbell-general-chest-press",
            MovementPattern.HORIZONTAL_PUSH,
            MuscleGroup.CHEST,
            equipment=frozenset({Equipment.DUMBBELL}),
        ),
        muscle_focus=MuscleFocus.GENERAL_CHEST,
    )
    source = normalize_request(
        _build_request(
            (Equipment.DUMBBELL,),
            TrainingExperience.BEGINNER,
            Goal.MUSCLE_GAIN,
            2,
        )
    )

    decision = rank_substitutions(
        source,
        target,
        (degraded_focus, exact_focus),
        SubstitutionContext(cause=SubstitutionCause.MISSING_EQUIPMENT),
        ruleset=RULESET,
    )

    assert decision.exercise_ids == (exact_focus.id, degraded_focus.id)


@pytest.mark.parametrize(
    ("name", "equipment", "overrides"),
    (
        pytest.param(
            "no_overhead",
            (Equipment.BODYWEIGHT,),
            {
                "blocked_movement_patterns": (MovementPattern.VERTICAL_PUSH,),
                "blocked_caution_tags": (ExerciseCautionTag.OVERHEAD_POSITION,),
                "overhead_limit": LoadLimit.NONE,
            },
            id="bodyweight-no-overhead",
        ),
        pytest.param(
            "no_deep_knee_flexion",
            (Equipment.BODYWEIGHT, Equipment.DUMBBELL),
            {
                "blocked_movement_patterns": (
                    MovementPattern.SQUAT,
                    MovementPattern.LUNGE,
                ),
                "blocked_caution_tags": (ExerciseCautionTag.DEEP_KNEE_FLEXION,),
                "impact_limit": ImpactLimit.LOW,
                "balance_requirement": BalanceAbility.NORMAL,
            },
            id="dumbbells-no-deep-knee-flexion",
        ),
        pytest.param(
            "no_loaded_hinge",
            (Equipment.BODYWEIGHT, Equipment.RESISTANCE_BAND, Equipment.DUMBBELL),
            {
                "blocked_movement_patterns": (MovementPattern.HIP_HINGE,),
                "blocked_caution_tags": (ExerciseCautionTag.LOWER_BACK_LOADING,),
                "axial_load_limit": LoadLimit.LOW,
            },
            id="bands-dumbbells-no-loaded-hinge",
        ),
    ),
)
def test_home_limitation_matrix_never_weakens_safety(
    name: str,
    equipment: tuple[Equipment, ...],
    overrides: dict[str, object],
) -> None:
    source = _build_request(
        equipment,
        TrainingExperience.INTERMEDIATE,
        Goal.MUSCLE_GAIN,
        3,
        **overrides,
    )
    result = generate_program(source, full_catalog(), RULESET)
    assert result.is_success, (name, result.errors)
    _assert_safe_home_program(result, source, full_catalog())


def test_historical_bodyweight_home_paths_keep_exact_days_and_no_pull_up_bar_leak() -> None:
    catalog = full_catalog()
    source = _build_request(
        (Equipment.BODYWEIGHT,),
        TrainingExperience.INTERMEDIATE,
        Goal.GENERAL_FITNESS,
        6,
    )
    result = generate_program(source, catalog, RULESET)

    assert result.is_success, result.errors
    _assert_safe_home_program(result, source, catalog)
    assert all(
        Equipment.PULL_UP_BAR
        not in effective_required_equipment(item.equipment, item.movement_pattern)
        for day in result.program.weekly_schedule
        for item in day.exercises
    )
