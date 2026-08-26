from dataclasses import replace
from uuid import NAMESPACE_URL, uuid5

import pytest

from app.exercises.enums import (
    Equipment,
    ExerciseCautionTag,
    ExerciseType,
    MovementPattern,
    MuscleGroup,
)
from app.workouts.program_engine.duration_policy import get_session_duration_policy
from app.workouts.program_engine.engine import generate_program
from app.workouts.program_engine.enums import Goal, SplitType
from app.workouts.program_engine.normalization import normalize_request
from app.workouts.program_engine.priority_allocation import PriorityAllocationPolicy
from app.workouts.program_engine.rulesets.resistance_training_v1 import RULESET
from app.workouts.program_engine.schemas import (
    BodyAnalysisInfluence,
    BodyAnalysisPriority,
    NormalizedProgramRequest,
    ProgrammedExercise,
    SplitPlan,
    WorkoutDay,
)
from app.workouts.program_engine.session_duration import _repair_overfill
from app.workouts.program_engine.session_structure import (
    SUPPLEMENTAL_MUSCLES,
    finalize_session_structure,
    main_exercise_count,
    main_session_title,
    session_structure_errors,
    supplemental_reason_codes,
)
from app.workouts.program_engine.split_selector import select_split
from app.workouts.program_engine.supersets import apply_duration_pressure_superset
from app.workouts.program_engine.supplemental_policy import is_supplemental_muscle
from app.workouts.program_engine.validation import validate_program
from app.workouts.program_engine.volume_planner import plan_weekly_volume
from tests.workouts.program_engine.golden_fixtures import exercise, full_catalog, request


def _programmed(
    name: str,
    muscle: MuscleGroup,
    exercise_type: ExerciseType,
    *,
    pattern: MovementPattern,
    order: int,
    reasons: tuple[str, ...] = ("TEST",),
    superset_group: str | None = None,
) -> ProgrammedExercise:
    return ProgrammedExercise(
        exercise_id=uuid5(NAMESPACE_URL, f"https://fitsho.test/session-structure/{name}"),
        exercise_name=name,
        order=order,
        sets=3,
        rep_min=8,
        rep_max=12,
        target_rir=2,
        rest_seconds=75,
        estimated_minutes=6,
        reason_codes=reasons,
        movement_pattern=pattern,
        primary_muscle=muscle,
        equipment=frozenset({Equipment.CABLE}),
        exercise_type=exercise_type,
        superset_group=superset_group,
    )


def _day(
    focus: str,
    exercises: tuple[ProgrammedExercise, ...],
    *,
    title: str = "Test",
    template_target_muscles: tuple[MuscleGroup, ...] = (),
    template_structure_focus: str = "full_body",
) -> WorkoutDay:
    return WorkoutDay(
        day_index=1,
        weekday=0,
        title=title,
        focus=focus,
        estimated_duration_minutes=5 + sum(item.estimated_minutes for item in exercises),
        exercises=exercises,
        template_target_muscles=template_target_muscles,
        template_structure_focus=template_structure_focus,
    )


def _normalized(**overrides: object) -> NormalizedProgramRequest:
    return normalize_request(request(**overrides), RULESET)


@pytest.mark.parametrize(
    ("focus", "title"),
    [
        ("chest_triceps", "Test"),
        ("template_reference_1", "Chest + Triceps"),
    ],
)
def test_dynamic_and_template_chest_triceps_use_the_same_strict_block(
    focus: str,
    title: str,
) -> None:
    triceps = _programmed(
        "Triceps Extension",
        MuscleGroup.TRICEPS,
        ExerciseType.ISOLATION,
        pattern=MovementPattern.ELBOW_EXTENSION,
        order=1,
    )
    fly = _programmed(
        "Cable Fly",
        MuscleGroup.CHEST,
        ExerciseType.ISOLATION,
        pattern=MovementPattern.HORIZONTAL_PUSH,
        order=2,
    )
    bench = _programmed(
        "Bench Press",
        MuscleGroup.CHEST,
        ExerciseType.COMPOUND,
        pattern=MovementPattern.HORIZONTAL_PUSH,
        order=3,
    )

    finalized = finalize_session_structure(
        (
            _day(
                focus,
                (triceps, fly, bench),
                title=title,
                template_target_muscles=(MuscleGroup.CHEST, MuscleGroup.TRICEPS)
                if focus.startswith("template_reference")
                else (),
                template_structure_focus="chest_triceps"
                if focus.startswith("template_reference")
                else "full_body",
            ),
        ),
        _normalized(priority_muscles=[MuscleGroup.TRICEPS]),
        RULESET,
    )[0]

    assert [item.exercise_name for item in finalized.exercises] == [
        "Bench Press",
        "Cable Fly",
        "Triceps Extension",
    ]


@pytest.mark.parametrize(
    "repair_reason",
    [
        "VOLUME_REPAIR_ADDED_EXERCISE_FOR_MINIMUM_COVERAGE",
        "SESSION_DURATION_REPAIR_APPLIED",
    ],
)
def test_late_repair_cannot_leave_chest_after_triceps(repair_reason: str) -> None:
    bench = _programmed(
        "Bench Press",
        MuscleGroup.CHEST,
        ExerciseType.COMPOUND,
        pattern=MovementPattern.HORIZONTAL_PUSH,
        order=1,
    )
    triceps = _programmed(
        "Triceps Extension",
        MuscleGroup.TRICEPS,
        ExerciseType.ISOLATION,
        pattern=MovementPattern.ELBOW_EXTENSION,
        order=2,
    )
    repaired_fly = _programmed(
        "Repaired Cable Fly",
        MuscleGroup.CHEST,
        ExerciseType.ISOLATION,
        pattern=MovementPattern.HORIZONTAL_PUSH,
        order=3,
        reasons=(repair_reason,),
    )

    finalized = finalize_session_structure(
        (_day("chest_triceps", (bench, triceps, repaired_fly)),),
        _normalized(),
        RULESET,
    )[0]

    assert [item.primary_muscle for item in finalized.exercises] == [
        MuscleGroup.CHEST,
        MuscleGroup.CHEST,
        MuscleGroup.TRICEPS,
    ]


def test_back_biceps_keeps_back_before_direct_biceps() -> None:
    curl = _programmed(
        "Cable Curl",
        MuscleGroup.BICEPS,
        ExerciseType.ISOLATION,
        pattern=MovementPattern.ELBOW_FLEXION,
        order=1,
    )
    row = _programmed(
        "Cable Row",
        MuscleGroup.BACK,
        ExerciseType.COMPOUND,
        pattern=MovementPattern.HORIZONTAL_PULL,
        order=2,
    )

    finalized = finalize_session_structure(
        (_day("back_biceps", (curl, row)),),
        _normalized(priority_muscles=[MuscleGroup.BICEPS]),
        RULESET,
    )[0]

    assert [item.primary_muscle for item in finalized.exercises] == [
        MuscleGroup.BACK,
        MuscleGroup.BICEPS,
    ]


def test_body_analysis_cannot_move_triceps_before_chest_block() -> None:
    influence = BodyAnalysisInfluence.model_validate(
        {
            "analysis_id": uuid5(NAMESPACE_URL, "analysis"),
            "result_version_id": uuid5(NAMESPACE_URL, "analysis-result"),
            "analysis_revision": 1,
            "schema_version": "1.0",
            "source": "fully_reviewed",
            "overall_confidence": 0.95,
            "priorities": (
                BodyAnalysisPriority(
                    muscle=MuscleGroup.TRICEPS,
                    classification="clear_lag",
                    confidence=0.95,
                    severity=0.9,
                ),
            ),
        }
    )
    triceps = _programmed(
        "Triceps Extension",
        MuscleGroup.TRICEPS,
        ExerciseType.ISOLATION,
        pattern=MovementPattern.ELBOW_EXTENSION,
        order=1,
    )
    bench = _programmed(
        "Bench Press",
        MuscleGroup.CHEST,
        ExerciseType.COMPOUND,
        pattern=MovementPattern.HORIZONTAL_PUSH,
        order=2,
    )

    finalized = finalize_session_structure(
        (_day("chest_triceps", (triceps, bench)),),
        _normalized(body_analysis_influence=influence),
        RULESET,
    )[0]

    assert [item.primary_muscle for item in finalized.exercises] == [
        MuscleGroup.CHEST,
        MuscleGroup.TRICEPS,
    ]


def test_actual_exercise_type_places_bench_before_fly_with_the_same_pattern() -> None:
    fly = _programmed(
        "Cable Fly",
        MuscleGroup.CHEST,
        ExerciseType.ISOLATION,
        pattern=MovementPattern.HORIZONTAL_PUSH,
        order=1,
    )
    bench = _programmed(
        "Bench Press",
        MuscleGroup.CHEST,
        ExerciseType.COMPOUND,
        pattern=MovementPattern.HORIZONTAL_PUSH,
        order=2,
    )

    finalized = finalize_session_structure(
        (_day("chest_triceps", (fly, bench)),),
        _normalized(),
        RULESET,
    )[0]

    assert [item.exercise_name for item in finalized.exercises] == ["Bench Press", "Cable Fly"]


def test_strength_primary_lift_stays_first() -> None:
    secondary = _programmed(
        "Secondary Row",
        MuscleGroup.BACK,
        ExerciseType.COMPOUND,
        pattern=MovementPattern.HORIZONTAL_PULL,
        order=1,
        reasons=("STRENGTH_SECONDARY_COMPOUND",),
    )
    primary = _programmed(
        "Primary Bench",
        MuscleGroup.CHEST,
        ExerciseType.COMPOUND,
        pattern=MovementPattern.HORIZONTAL_PUSH,
        order=2,
        reasons=("STRENGTH_PRIMARY_COMPOUND",),
    )

    finalized = finalize_session_structure(
        (_day("upper", (secondary, primary)),),
        _normalized(primary_goal=Goal.STRENGTH),
        RULESET,
    )[0]

    assert finalized.exercises[0].exercise_name == "Primary Bench"


def test_full_body_major_muscle_alternation_is_valid() -> None:
    exercises = (
        _programmed(
            "Bench A",
            MuscleGroup.CHEST,
            ExerciseType.COMPOUND,
            pattern=MovementPattern.HORIZONTAL_PUSH,
            order=1,
        ),
        _programmed(
            "Row A",
            MuscleGroup.BACK,
            ExerciseType.COMPOUND,
            pattern=MovementPattern.HORIZONTAL_PULL,
            order=2,
        ),
        _programmed(
            "Bench B",
            MuscleGroup.CHEST,
            ExerciseType.COMPOUND,
            pattern=MovementPattern.HORIZONTAL_PUSH,
            order=3,
        ),
    )

    assert session_structure_errors(_day("full_body", exercises), Goal.HYPERTROPHY) == ()


def test_valid_superset_pair_stays_atomic_adjacent_and_deterministic() -> None:
    chest = _programmed(
        "Cable Fly",
        MuscleGroup.CHEST,
        ExerciseType.ISOLATION,
        pattern=MovementPattern.HORIZONTAL_PUSH,
        order=3,
        reasons=("SESSION_SIZE_ACCESSORY", "SAFE_TEMPLATE_SUPERSET_PRESERVED"),
        superset_group="chest-back",
    )
    back = _programmed(
        "Cable Row",
        MuscleGroup.BACK,
        ExerciseType.ISOLATION,
        pattern=MovementPattern.HORIZONTAL_PULL,
        order=1,
        reasons=("SESSION_SIZE_ACCESSORY", "SAFE_TEMPLATE_SUPERSET_PRESERVED"),
        superset_group="chest-back",
    )
    squat = _programmed(
        "Squat",
        MuscleGroup.QUADRICEPS,
        ExerciseType.COMPOUND,
        pattern=MovementPattern.SQUAT,
        order=2,
    )
    normalized = _normalized()

    first = finalize_session_structure(
        (_day("full_body", (chest, squat, back)),), normalized, RULESET
    )[0]
    second = finalize_session_structure(
        (_day("full_body", (back, chest, squat)),), normalized, RULESET
    )[0]

    assert first.exercises == second.exercises
    grouped = [index for index, item in enumerate(first.exercises) if item.superset_group]
    assert grouped == [1, 2]


def test_automatic_superset_never_pairs_supplemental_with_main_work() -> None:
    triceps = _programmed(
        "Triceps Extension",
        MuscleGroup.TRICEPS,
        ExerciseType.ISOLATION,
        pattern=MovementPattern.ELBOW_EXTENSION,
        order=1,
    )
    abs_work = _programmed(
        "Pallof Press",
        MuscleGroup.ABS,
        ExerciseType.CORE,
        pattern=MovementPattern.CORE_ANTI_ROTATION,
        order=2,
    )

    exercises, reasons = apply_duration_pressure_superset(
        (triceps, abs_work), _normalized(), RULESET
    )

    assert exercises == (triceps, abs_work)
    assert reasons == ()


def test_supplemental_work_is_last_optional_and_absent_from_title() -> None:
    forearms = _programmed(
        "Wrist Curl",
        MuscleGroup.FOREARMS,
        ExerciseType.ISOLATION,
        pattern=MovementPattern.ELBOW_FLEXION,
        order=1,
        reasons=supplemental_reason_codes(MuscleGroup.FOREARMS, planned=False),
    )
    row = _programmed(
        "Row",
        MuscleGroup.BACK,
        ExerciseType.COMPOUND,
        pattern=MovementPattern.HORIZONTAL_PULL,
        order=2,
    )

    finalized = finalize_session_structure(
        (_day("pull", (forearms, row)),), _normalized(), RULESET
    )[0]

    assert finalized.exercises[-1].primary_muscle is MuscleGroup.FOREARMS
    assert "OPTIONAL_SUPPLEMENTAL_WORK" in finalized.exercises[-1].reason_codes
    assert "SUPPLEMENTAL_MUSCLE:forearms" in finalized.exercises[-1].reason_codes
    assert finalized.title == "Day 1: Back"
    assert main_session_title(1, finalized.exercises) == "Day 1: Back"


def test_supplemental_policy_is_shared_and_does_not_drive_volume_or_split() -> None:
    normalized = _normalized(
        available_training_days=5,
        priority_muscles=[MuscleGroup.ABS],
    )
    policy = PriorityAllocationPolicy.for_request(normalized, RULESET)
    split = SplitPlan(
        SplitType.UPPER_LOWER_SPECIALIZATION,
        ("upper", "lower", "upper", "lower", "specialization"),
        (0, 1, 3, 4, 6),
        1,
        (),
    )
    volume = plan_weekly_volume(normalized, split, RULESET)

    assert SUPPLEMENTAL_MUSCLES == frozenset(
        {
            MuscleGroup.FOREARMS,
            MuscleGroup.ABS,
            MuscleGroup.OBLIQUES,
            MuscleGroup.LOWER_BACK,
            MuscleGroup.NECK,
        }
    )
    assert MuscleGroup.ABS not in policy.priorities
    assert MuscleGroup.ABS in policy.supplemental_priorities
    assert volume.direct_sets_for(MuscleGroup.ABS) == 0
    assert all(target.muscle not in SUPPLEMENTAL_MUSCLES for target in volume.targets)
    selected = select_split(normalized, RULESET)
    baseline = select_split(_normalized(available_training_days=5), RULESET)
    assert selected.split_type is baseline.split_type
    assert selected.day_focuses == baseline.day_focuses
    assert all("abs" not in focus and "core" not in focus for focus in selected.day_focuses)


def test_supplemental_work_cannot_satisfy_main_exercise_floor() -> None:
    main = _programmed(
        "Row",
        MuscleGroup.BACK,
        ExerciseType.COMPOUND,
        pattern=MovementPattern.HORIZONTAL_PULL,
        order=1,
    )
    supplements = tuple(
        _programmed(
            muscle.value,
            muscle,
            (
                ExerciseType.CORE
                if muscle in {MuscleGroup.ABS, MuscleGroup.OBLIQUES}
                else ExerciseType.ISOLATION
            ),
            pattern=(
                MovementPattern.CORE_ANTI_ROTATION
                if muscle in {MuscleGroup.ABS, MuscleGroup.OBLIQUES}
                else MovementPattern.ELBOW_FLEXION
            ),
            order=index,
        )
        for index, muscle in enumerate(SUPPLEMENTAL_MUSCLES, start=2)
    )

    assert len((main, *supplements)) >= RULESET.minimum_exercises_per_session
    assert main_exercise_count((main, *supplements)) == 1
    assert main_exercise_count((main, replace(main, primary_muscle=None))) == 1


def test_duration_pressure_trims_planned_supplemental_before_main_work() -> None:
    main_work = tuple(
        _programmed(
            f"Main {index}",
            muscle,
            ExerciseType.COMPOUND,
            pattern=pattern,
            order=index,
        )
        for index, (muscle, pattern) in enumerate(
            (
                (MuscleGroup.CHEST, MovementPattern.HORIZONTAL_PUSH),
                (MuscleGroup.BACK, MovementPattern.HORIZONTAL_PULL),
                (MuscleGroup.QUADRICEPS, MovementPattern.SQUAT),
                (MuscleGroup.HAMSTRINGS, MovementPattern.HIP_HINGE),
                (MuscleGroup.SHOULDERS, MovementPattern.VERTICAL_PUSH),
            ),
            start=1,
        )
    )
    planned_forearms = replace(
        _programmed(
            "Planned Wrist Curl",
            MuscleGroup.FOREARMS,
            ExerciseType.ISOLATION,
            pattern=MovementPattern.ELBOW_FLEXION,
            order=6,
            reasons=supplemental_reason_codes(MuscleGroup.FOREARMS, planned=True),
        ),
        estimated_minutes=50,
    )
    normalized = _normalized(
        session_duration_minutes=30,
        priority_muscles=[MuscleGroup.FOREARMS],
    )

    repaired, reasons = _repair_overfill(
        _day("full_body", (*main_work, planned_forearms)),
        normalized,
        get_session_duration_policy(30),
        RULESET,
        minimum_exercises=5,
    )

    assert main_exercise_count(repaired.exercises) == 5
    assert all(item.primary_muscle is not MuscleGroup.FOREARMS for item in repaired.exercises)
    assert "SUPPLEMENTAL_WORK_TRIMMED_FOR_DURATION" in reasons


def test_final_orders_are_dense_and_input_order_independent() -> None:
    exercises = (
        _programmed(
            "Fly",
            MuscleGroup.CHEST,
            ExerciseType.ISOLATION,
            pattern=MovementPattern.HORIZONTAL_PUSH,
            order=9,
        ),
        _programmed(
            "Bench",
            MuscleGroup.CHEST,
            ExerciseType.COMPOUND,
            pattern=MovementPattern.HORIZONTAL_PUSH,
            order=2,
        ),
        _programmed(
            "Extension",
            MuscleGroup.TRICEPS,
            ExerciseType.ISOLATION,
            pattern=MovementPattern.ELBOW_EXTENSION,
            order=7,
        ),
    )
    normalized = _normalized()

    first = finalize_session_structure((_day("chest_triceps", exercises),), normalized, RULESET)[0]
    second = finalize_session_structure(
        (_day("chest_triceps", tuple(reversed(exercises))),), normalized, RULESET
    )[0]

    assert first.exercises == second.exercises
    assert [item.order for item in first.exercises] == [1, 2, 3]


def test_malformed_strict_block_and_supplemental_tail_are_rejected() -> None:
    chest_a = _programmed(
        "Bench",
        MuscleGroup.CHEST,
        ExerciseType.COMPOUND,
        pattern=MovementPattern.HORIZONTAL_PUSH,
        order=1,
    )
    triceps = _programmed(
        "Extension",
        MuscleGroup.TRICEPS,
        ExerciseType.ISOLATION,
        pattern=MovementPattern.ELBOW_EXTENSION,
        order=2,
    )
    chest_b = _programmed(
        "Fly",
        MuscleGroup.CHEST,
        ExerciseType.ISOLATION,
        pattern=MovementPattern.HORIZONTAL_PUSH,
        order=3,
    )
    forearms = _programmed(
        "Wrist Curl",
        MuscleGroup.FOREARMS,
        ExerciseType.ISOLATION,
        pattern=MovementPattern.ELBOW_FLEXION,
        order=1,
    )
    row = _programmed(
        "Row",
        MuscleGroup.BACK,
        ExerciseType.COMPOUND,
        pattern=MovementPattern.HORIZONTAL_PULL,
        order=2,
    )

    assert "STRICT_MUSCLE_BLOCK_ORDER_INVALID" in session_structure_errors(
        _day("chest_triceps", (chest_a, triceps, chest_b)), Goal.HYPERTROPHY
    )
    assert "SUPPLEMENTAL_WORK_NOT_AT_SESSION_END" in session_structure_errors(
        _day("pull", (forearms, row)), Goal.HYPERTROPHY
    )


@pytest.mark.parametrize("supplemental_count", (0, 1, 2))
def test_zero_to_two_supplemental_exercises_are_valid_and_last(
    supplemental_count: int,
) -> None:
    row = _programmed(
        "Row",
        MuscleGroup.BACK,
        ExerciseType.COMPOUND,
        pattern=MovementPattern.HORIZONTAL_PULL,
        order=1,
    )
    supplemental = (
        _programmed(
            "Wrist Curl",
            MuscleGroup.FOREARMS,
            ExerciseType.ISOLATION,
            pattern=MovementPattern.ELBOW_FLEXION,
            order=2,
        ),
        _programmed(
            "Ab Crunch",
            MuscleGroup.ABS,
            ExerciseType.CORE,
            pattern=MovementPattern.CORE_ANTI_EXTENSION,
            order=3,
        ),
    )
    exercises = (row, *supplemental[:supplemental_count])

    assert session_structure_errors(_day("pull", exercises), Goal.HYPERTROPHY) == ()
    if supplemental_count:
        assert all(
            is_supplemental_muscle(item.primary_muscle)
            for item in exercises[-supplemental_count:]
        )


def test_three_supplemental_exercises_are_invalid() -> None:
    row = _programmed(
        "Row",
        MuscleGroup.BACK,
        ExerciseType.COMPOUND,
        pattern=MovementPattern.HORIZONTAL_PULL,
        order=1,
    )
    exercises = (
        row,
        _programmed(
            "Wrist Curl",
            MuscleGroup.FOREARMS,
            ExerciseType.ISOLATION,
            pattern=MovementPattern.ELBOW_FLEXION,
            order=2,
        ),
        _programmed(
            "Ab Crunch",
            MuscleGroup.ABS,
            ExerciseType.CORE,
            pattern=MovementPattern.CORE_ANTI_EXTENSION,
            order=3,
        ),
        _programmed(
            "Neck Curl",
            MuscleGroup.NECK,
            ExerciseType.ISOLATION,
            pattern=MovementPattern.SHRUG,
            order=4,
        ),
    )

    assert "SUPPLEMENTAL_EXERCISE_LIMIT_EXCEEDED" in session_structure_errors(
        _day("pull", exercises), Goal.HYPERTROPHY
    )


def test_eight_main_and_two_supplemental_report_eight_main_and_keep_tail() -> None:
    main = tuple(
        _programmed(
            f"Main {index}",
            MuscleGroup.BACK,
            ExerciseType.COMPOUND,
            pattern=MovementPattern.HORIZONTAL_PULL,
            order=index,
        )
        for index in range(1, 9)
    )
    supplements = (
        _programmed(
            "Wrist Curl",
            MuscleGroup.FOREARMS,
            ExerciseType.ISOLATION,
            pattern=MovementPattern.ELBOW_FLEXION,
            order=9,
        ),
        _programmed(
            "Ab Crunch",
            MuscleGroup.ABS,
            ExerciseType.CORE,
            pattern=MovementPattern.CORE_ANTI_EXTENSION,
            order=10,
        ),
    )
    exercises = (*main, *supplements)

    assert main_exercise_count(exercises) == 8
    assert session_structure_errors(_day("full_body", exercises), Goal.HYPERTROPHY) == ()
    assert all(is_supplemental_muscle(item.primary_muscle) for item in exercises[-2:])


def test_validator_rejects_malformed_final_muscle_block() -> None:
    source = request()
    result = generate_program(source, full_catalog(), RULESET)
    assert result.program is not None, result.errors
    malformed = _day(
        "chest_triceps",
        (
            _programmed(
                "Bench",
                MuscleGroup.CHEST,
                ExerciseType.COMPOUND,
                pattern=MovementPattern.HORIZONTAL_PUSH,
                order=1,
            ),
            _programmed(
                "Extension",
                MuscleGroup.TRICEPS,
                ExerciseType.ISOLATION,
                pattern=MovementPattern.ELBOW_EXTENSION,
                order=2,
            ),
            _programmed(
                "Fly",
                MuscleGroup.CHEST,
                ExerciseType.ISOLATION,
                pattern=MovementPattern.HORIZONTAL_PUSH,
                order=3,
            ),
        ),
    )
    invalid = replace(
        result.program,
        weekly_schedule=(malformed, *result.program.weekly_schedule[1:]),
    )

    report = validate_program(invalid, source, RULESET)

    assert "STRICT_MUSCLE_BLOCK_ORDER_INVALID" in report.errors


def test_lower_back_constraints_filter_supplemental_candidate() -> None:
    lower_back = exercise(
        "back-extension",
        MovementPattern.HIP_EXTENSION,
        MuscleGroup.LOWER_BACK,
        exercise_type=ExerciseType.ISOLATION,
    )
    source = request(blocked_caution_tags=[ExerciseCautionTag.LOWER_BACK_LOADING])

    result = generate_program(source, [*full_catalog(), lower_back], RULESET)

    assert result.program is not None, result.errors
    assert all(
        item.primary_muscle is not MuscleGroup.LOWER_BACK
        for day in result.program.weekly_schedule
        for item in day.exercises
    )


def test_neck_is_never_auto_added() -> None:
    neck = exercise(
        "neck-flexion",
        MovementPattern.SHRUG,
        MuscleGroup.NECK,
        exercise_type=ExerciseType.ISOLATION,
        caution_tags=frozenset({ExerciseCautionTag.NECK_LOADING}),
    )

    result = generate_program(request(), [*full_catalog(), neck], RULESET)

    assert result.program is not None, result.errors
    assert all(
        item.primary_muscle is not MuscleGroup.NECK
        for day in result.program.weekly_schedule
        for item in day.exercises
    )


def test_warmup_recalculated_after_final_sequencing() -> None:
    isolation = replace(
        _programmed(
            "Fly",
            MuscleGroup.CHEST,
            ExerciseType.ISOLATION,
            pattern=MovementPattern.HORIZONTAL_PUSH,
            order=1,
        ),
        warmup_sets=RULESET.first_compound_warmup_sets,
        sets=3,
        rest_seconds=60,
    )
    compound = replace(
        _programmed(
            "Bench",
            MuscleGroup.CHEST,
            ExerciseType.COMPOUND,
            pattern=MovementPattern.HORIZONTAL_PUSH,
            order=2,
        ),
        warmup_sets=0,
        sets=3,
        rest_seconds=60,
    )

    normalized = _normalized(primary_goal=Goal.HYPERTROPHY)

    finalized = finalize_session_structure(
        (_day("chest_triceps", (isolation, compound)),),
        normalized,
        RULESET,
    )[0]

    assert finalized.exercises[0].exercise_name == "Bench"
    assert finalized.exercises[0].warmup_sets == RULESET.first_compound_warmup_sets
    assert finalized.exercises[1].exercise_name == "Fly"
    assert finalized.exercises[1].warmup_sets == 0
    assert finalized.estimated_duration_minutes > 0


def test_template_muscle_blocks_must_use_structure_focus() -> None:
    # 1) explicit chest_triceps template gets chest_triceps strict block
    triceps = _programmed(
        "Extension",
        MuscleGroup.TRICEPS,
        ExerciseType.ISOLATION,
        pattern=MovementPattern.ELBOW_EXTENSION,
        order=1,
    )
    chest = _programmed(
        "Fly",
        MuscleGroup.CHEST,
        ExerciseType.ISOLATION,
        pattern=MovementPattern.HORIZONTAL_PUSH,
        order=2,
    )

    normalized = _normalized()
    day = _day("template_reference_1", (triceps, chest))
    day_strict = replace(
        day, template_structure_focus="chest_triceps", title="Weird Name with no matching words"
    )

    # 4) renamed/localized titles do not affect behavior
    # triceps is 1, chest is 2
    # but chest_triceps block forces chest before triceps
    finalized = finalize_session_structure((day_strict,), normalized, RULESET)[0]
    assert finalized.exercises[0].exercise_name == "Fly"
    assert finalized.exercises[1].exercise_name == "Extension"

    # 2) Full Body with CHEST + TRICEPS does NOT
    day_full_body = replace(
        day,
        template_structure_focus="full_body",
        template_target_muscles=(MuscleGroup.CHEST, MuscleGroup.TRICEPS, MuscleGroup.QUADRICEPS),
        title="Full Body",
    )
    finalized_fb = finalize_session_structure((day_full_body,), normalized, RULESET)[0]
    # Without strict block, they maintain original order: triceps first, chest second
    assert finalized_fb.exercises[0].exercise_name == "Extension"
    assert finalized_fb.exercises[1].exercise_name == "Fly"

    # 3) Full Body with HAMSTRINGS + GLUTES does NOT
    hamstrings = _programmed(
        "Leg Curl",
        MuscleGroup.HAMSTRINGS,
        ExerciseType.ISOLATION,
        pattern=MovementPattern.KNEE_FLEXION,
        order=2,
    )
    glutes = _programmed(
        "Glute Bridge",
        MuscleGroup.GLUTES,
        ExerciseType.ISOLATION,
        pattern=MovementPattern.HIP_EXTENSION,
        order=1,
    )
    day_posterior = _day("template_reference_2", (glutes, hamstrings))
    day_posterior_fb = replace(
        day_posterior,
        template_structure_focus="full_body",
        template_target_muscles=(MuscleGroup.HAMSTRINGS, MuscleGroup.GLUTES, MuscleGroup.CHEST),
        title="Full Body Posterior",
    )
    finalized_fb_post = finalize_session_structure((day_posterior_fb,), normalized, RULESET)[0]
    assert finalized_fb_post.exercises[0].exercise_name == "Glute Bridge"
    assert finalized_fb_post.exercises[1].exercise_name == "Leg Curl"


def test_dynamic_chest_triceps_behavior_remains_unchanged() -> None:
    # 5) dynamic chest_triceps/back_biceps behavior remains unchanged
    triceps = _programmed(
        "Extension",
        MuscleGroup.TRICEPS,
        ExerciseType.ISOLATION,
        pattern=MovementPattern.ELBOW_EXTENSION,
        order=1,
    )
    chest = _programmed(
        "Fly",
        MuscleGroup.CHEST,
        ExerciseType.ISOLATION,
        pattern=MovementPattern.HORIZONTAL_PUSH,
        order=2,
    )

    normalized = _normalized()
    # dynamic uses day.focus == "chest_triceps"
    day = _day("chest_triceps", (triceps, chest))
    finalized = finalize_session_structure((day,), normalized, RULESET)[0]

    # chest is forced before triceps
    assert finalized.exercises[0].exercise_name == "Fly"
    assert finalized.exercises[1].exercise_name == "Extension"
