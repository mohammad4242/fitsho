from dataclasses import replace

import pytest

from app.exercises.enums import ExerciseType, MuscleGroup
from app.workouts.program_engine.engine import generate_program
from app.workouts.program_engine.enums import Goal
from app.workouts.program_engine.normalization import normalize_request
from app.workouts.program_engine.prescription import prescribe_sessions
from app.workouts.program_engine.rulesets.resistance_training_v1 import RULESET
from app.workouts.program_engine.schemas import (
    SessionDraft,
    VolumeTarget,
    WeeklyVolumePlan,
)
from app.workouts.program_engine.session_structure import (
    finalize_session_structure,
    session_structure_errors,
)
from app.workouts.program_engine.supplemental_policy import (
    is_main_resistance_exercise,
)
from app.workouts.program_engine.validation import validate_program
from tests.workouts.program_engine.golden_fixtures import full_catalog, request

CORE_SUPPLEMENTAL_MUSCLES = (
    MuscleGroup.ABS,
    MuscleGroup.OBLIQUES,
    MuscleGroup.LOWER_BACK,
    MuscleGroup.FOREARMS,
    MuscleGroup.NECK,
)


def _prescribed_core(
    muscle: MuscleGroup,
    exercise_type: ExerciseType,
    *,
    with_direct_target: bool = False,
):
    source = request(available_training_days=1, session_duration_minutes=45)
    normalized = normalize_request(source, RULESET)
    catalog = full_catalog()
    main = next(item for item in catalog if is_main_resistance_exercise(item))
    core = next(item for item in catalog if item.exercise_type is ExerciseType.CORE)
    core = replace(core, primary_muscle=muscle, exercise_type=exercise_type)
    draft = SessionDraft(
        day_index=1,
        weekday=0,
        focus="full_body",
        exercises=[main, core],
        selection_reasons={main.id: (), core.id: ()},
        substitutions={main.id: (), core.id: ()},
    )
    volume = WeeklyVolumePlan(
        targets=(
            VolumeTarget(
                muscle=muscle,
                minimum_soft=0,
                target_sets=2,
                maximum_soft=2,
                maximum_hard=2,
                fractional_sets=0,
                effective_target_sets=2,
                minimum_direct_sets=0,
            ),
        )
        if with_direct_target
        else (),
        reason_codes=(),
    )
    day = prescribe_sessions(normalized, (draft,), volume, RULESET)[0]
    return day, core.id


@pytest.mark.parametrize("muscle", CORE_SUPPLEMENTAL_MUSCLES)
def test_each_supplemental_muscle_can_receive_two_working_sets(muscle: MuscleGroup) -> None:
    day, core_id = _prescribed_core(muscle, ExerciseType.ISOLATION)

    core = next(item for item in day.exercises if item.exercise_id == core_id)

    assert core.sets == 2


def test_exercise_type_core_can_receive_two_working_sets() -> None:
    day, core_id = _prescribed_core(MuscleGroup.CHEST, ExerciseType.CORE)

    core = next(item for item in day.exercises if item.exercise_id == core_id)

    assert core.sets == 2


def test_two_set_core_allocation_is_not_rounded_up_to_three() -> None:
    day, core_id = _prescribed_core(
        MuscleGroup.ABS,
        ExerciseType.CORE,
        with_direct_target=True,
    )

    core = next(item for item in day.exercises if item.exercise_id == core_id)

    assert core.sets == 2


def _program_with_replaced_core(
    *,
    sets: int,
    muscle: MuscleGroup,
    exercise_type: ExerciseType,
):
    source = request(available_training_days=1, session_duration_minutes=45)
    result = generate_program(source, full_catalog(), RULESET, reference_templates=())
    assert result.program is not None, result.errors
    program = result.program
    day = program.weekly_schedule[0]
    original = next(item for item in day.exercises if item.exercise_type is ExerciseType.CORE)
    replacement = replace(
        original,
        sets=sets,
        primary_muscle=muscle,
        exercise_type=exercise_type,
    )
    updated_day = replace(
        day,
        exercises=tuple(replacement if item is original else item for item in day.exercises),
    )
    return source, replace(program, weekly_schedule=(updated_day,))


@pytest.mark.parametrize(
    "muscle",
    (*CORE_SUPPLEMENTAL_MUSCLES, MuscleGroup.CHEST),
)
def test_validator_accepts_two_sets_only_for_core_or_supplemental_work(
    muscle: MuscleGroup,
) -> None:
    exercise_type = ExerciseType.CORE if muscle is MuscleGroup.CHEST else ExerciseType.ISOLATION
    source, program = _program_with_replaced_core(
        sets=2,
        muscle=muscle,
        exercise_type=exercise_type,
    )

    report = validate_program(program, source, RULESET)

    assert "INVALID_EXERCISE_PRESCRIPTION" not in report.errors, report.errors


def test_validator_still_rejects_one_set_core_work() -> None:
    source, program = _program_with_replaced_core(
        sets=1,
        muscle=MuscleGroup.ABS,
        exercise_type=ExerciseType.CORE,
    )

    report = validate_program(program, source, RULESET)

    assert "INVALID_EXERCISE_PRESCRIPTION" in report.errors


@pytest.mark.parametrize(
    "muscle",
    (MuscleGroup.CHEST, MuscleGroup.BACK, MuscleGroup.QUADRICEPS, MuscleGroup.CALVES),
)
def test_validator_does_not_lower_ordinary_resistance_minimum_for_short_sessions(
    muscle: MuscleGroup,
) -> None:
    source, program = _program_with_replaced_core(
        sets=2,
        muscle=muscle,
        exercise_type=ExerciseType.ISOLATION,
    )

    report = validate_program(program, source, RULESET)

    assert "INVALID_EXERCISE_PRESCRIPTION" in report.errors


def test_core_items_are_ordered_after_main_items_and_excluded_from_title() -> None:
    source = request(available_training_days=1, session_duration_minutes=45)
    normalized = normalize_request(source, RULESET)
    result = generate_program(source, full_catalog(), RULESET, reference_templates=())
    assert result.program is not None, result.errors
    original_day = result.program.weekly_schedule[0]
    main = next(
        item
        for item in original_day.exercises
        if is_main_resistance_exercise(item) and item.primary_muscle is MuscleGroup.CHEST
    )
    core = next(item for item in original_day.exercises if item.exercise_type is ExerciseType.CORE)
    core = replace(
        core,
        order=1,
        sets=2,
        primary_muscle=MuscleGroup.CHEST,
        exercise_type=ExerciseType.CORE,
    )
    main = replace(main, order=2)
    day = replace(original_day, exercises=(core, main))

    finalized = finalize_session_structure((day,), normalized, RULESET)[0]

    assert [item.exercise_id for item in finalized.exercises] == [
        main.exercise_id,
        core.exercise_id,
    ]
    assert finalized.title == "Day 1: Chest"
    assert session_structure_errors(finalized, Goal.GENERAL_FITNESS, normalized) == ()
