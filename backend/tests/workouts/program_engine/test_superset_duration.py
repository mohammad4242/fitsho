from dataclasses import replace
from uuid import uuid4

from app.exercises.enums import Equipment, ExerciseType, MovementPattern, MuscleGroup
from app.workouts.program_engine.enums import LoadLimit
from app.workouts.program_engine.normalization import normalize_request
from app.workouts.program_engine.rulesets.resistance_training_v1 import RULESET
from app.workouts.program_engine.schemas import ProgrammedExercise, WorkoutDay
from app.workouts.program_engine.session_duration import repair_session_durations
from app.workouts.program_engine.supersets import (
    apply_duration_pressure_superset,
    apply_template_supersets,
    superset_structure_errors,
)
from tests.workouts.program_engine.golden_fixtures import request


def _exercise(
    *,
    name: str,
    muscle: MuscleGroup,
    pattern: MovementPattern,
    equipment: Equipment = Equipment.CABLE,
    order: int = 1,
    reason_codes: tuple[str, ...] = ("SESSION_SIZE_ACCESSORY",),
    exercise_type: ExerciseType = ExerciseType.ISOLATION,
    axial_loading_level: LoadLimit = LoadLimit.LOW,
) -> ProgrammedExercise:
    return ProgrammedExercise(
        exercise_id=uuid4(),
        exercise_name=name,
        order=order,
        sets=3,
        rep_min=10,
        rep_max=15,
        target_rir=1,
        rest_seconds=75,
        estimated_minutes=6,
        reason_codes=reason_codes,
        movement_pattern=pattern,
        primary_muscle=muscle,
        equipment=frozenset({equipment}),
        exercise_type=exercise_type,
        axial_loading_level=axial_loading_level,
    )


def test_safe_curated_superset_saves_time_deterministically() -> None:
    normalized = normalize_request(request(available_training_days=1), RULESET)
    curl = _exercise(
        name="Cable Curl",
        muscle=MuscleGroup.BICEPS,
        pattern=MovementPattern.ELBOW_FLEXION,
        order=1,
    )
    extension = _exercise(
        name="Cable Triceps Extension",
        muscle=MuscleGroup.TRICEPS,
        pattern=MovementPattern.ELBOW_EXTENSION,
        order=2,
    )

    first, first_reasons = apply_duration_pressure_superset((curl, extension), normalized, RULESET)
    second, second_reasons = apply_duration_pressure_superset(
        (curl, extension), normalized, RULESET
    )

    assert first == second
    assert first_reasons == second_reasons == ("SAFE_SUPERSET_APPLIED_FOR_DURATION",)
    assert first[0].superset_group == first[1].superset_group
    assert first[0].superset_group is not None
    assert sum(item.estimated_minutes for item in first) < 12
    assert [item.order for item in first] == [1, 2]


def test_primary_strength_compound_is_never_supersetted() -> None:
    normalized = normalize_request(request(available_training_days=1), RULESET)
    press = _exercise(
        name="Bench Press",
        muscle=MuscleGroup.CHEST,
        pattern=MovementPattern.HORIZONTAL_PUSH,
        order=1,
        reason_codes=("STRENGTH_PRIMARY_COMPOUND",),
        exercise_type=ExerciseType.COMPOUND,
    )
    row = _exercise(
        name="Cable Row",
        muscle=MuscleGroup.BACK,
        pattern=MovementPattern.HORIZONTAL_PULL,
        order=2,
        exercise_type=ExerciseType.COMPOUND,
    )

    exercises, reasons = apply_duration_pressure_superset((press, row), normalized, RULESET)

    assert exercises == (press, row)
    assert reasons == ()
    assert all(item.superset_group is None for item in exercises)


def test_two_heavy_lower_compounds_are_never_supersetted() -> None:
    normalized = normalize_request(request(available_training_days=1), RULESET)
    squat = _exercise(
        name="Back Squat",
        muscle=MuscleGroup.QUADRICEPS,
        pattern=MovementPattern.SQUAT,
        order=1,
        exercise_type=ExerciseType.COMPOUND,
        axial_loading_level=LoadLimit.HIGH,
    )
    hinge = _exercise(
        name="Romanian Deadlift",
        muscle=MuscleGroup.HAMSTRINGS,
        pattern=MovementPattern.HIP_HINGE,
        order=2,
        exercise_type=ExerciseType.COMPOUND,
        axial_loading_level=LoadLimit.HIGH,
    )

    exercises, reasons = apply_duration_pressure_superset((squat, hinge), normalized, RULESET)

    assert exercises == (squat, hinge)
    assert reasons == ()


def test_shared_bench_does_not_hide_unsafe_equipment_transition() -> None:
    normalized = normalize_request(request(available_training_days=1), RULESET)
    curl = replace(
        _exercise(
            name="Dumbbell Curl",
            muscle=MuscleGroup.BICEPS,
            pattern=MovementPattern.ELBOW_FLEXION,
            order=1,
        ),
        equipment=frozenset({Equipment.DUMBBELL, Equipment.BENCH}),
    )
    extension = replace(
        _exercise(
            name="Barbell Triceps Extension",
            muscle=MuscleGroup.TRICEPS,
            pattern=MovementPattern.ELBOW_EXTENSION,
            order=2,
        ),
        equipment=frozenset({Equipment.BARBELL, Equipment.BENCH}),
    )

    exercises, reasons = apply_duration_pressure_superset((curl, extension), normalized, RULESET)

    assert exercises == (curl, extension)
    assert reasons == ()


def test_safe_template_superset_is_preserved_and_time_adjusted() -> None:
    curl = replace(
        _exercise(
            name="Cable Curl",
            muscle=MuscleGroup.BICEPS,
            pattern=MovementPattern.ELBOW_FLEXION,
            order=1,
        ),
        superset_group="template-arms",
    )
    extension = replace(
        _exercise(
            name="Cable Triceps Extension",
            muscle=MuscleGroup.TRICEPS,
            pattern=MovementPattern.ELBOW_EXTENSION,
            order=2,
        ),
        superset_group="template-arms",
    )

    exercises, reasons = apply_template_supersets((curl, extension))

    assert [item.superset_group for item in exercises] == ["template-arms", "template-arms"]
    assert sum(item.estimated_minutes for item in exercises) < 12
    assert reasons == ("SAFE_TEMPLATE_SUPERSET_PRESERVED",)


def test_unsafe_template_superset_is_cleared() -> None:
    press = replace(
        _exercise(
            name="Bench Press",
            muscle=MuscleGroup.CHEST,
            pattern=MovementPattern.HORIZONTAL_PUSH,
            order=1,
            reason_codes=("STRENGTH_PRIMARY_COMPOUND",),
            exercise_type=ExerciseType.COMPOUND,
        ),
        superset_group="unsafe-primary",
    )
    row = replace(
        _exercise(
            name="Cable Row",
            muscle=MuscleGroup.BACK,
            pattern=MovementPattern.HORIZONTAL_PULL,
            order=2,
            exercise_type=ExerciseType.COMPOUND,
        ),
        superset_group="unsafe-primary",
    )

    exercises, reasons = apply_template_supersets((press, row))

    assert all(item.superset_group is None for item in exercises)
    assert reasons == ("TEMPLATE_SUPERSET_REJECTED_UNSAFE",)


def test_incomplete_superset_group_is_invalid() -> None:
    incomplete = replace(
        _exercise(
            name="Cable Curl",
            muscle=MuscleGroup.BICEPS,
            pattern=MovementPattern.ELBOW_FLEXION,
        ),
        superset_group="incomplete",
    )

    assert superset_structure_errors((incomplete,)) == ("SUPERSET_GROUP_INVALID_SIZE",)


def test_underfilled_session_does_not_inflate_rest_to_consume_time() -> None:
    normalized = normalize_request(
        request(session_duration_minutes=60, available_training_days=1), RULESET
    )
    exercises = tuple(
        replace(item, sets=4)
        for item in (
            _exercise(
                name="Cable Curl",
                muscle=MuscleGroup.BICEPS,
                pattern=MovementPattern.ELBOW_FLEXION,
                order=1,
            ),
            _exercise(
                name="Cable Triceps Extension",
                muscle=MuscleGroup.TRICEPS,
                pattern=MovementPattern.ELBOW_EXTENSION,
                order=2,
            ),
        )
    )
    day = WorkoutDay(
        day_index=1,
        weekday=None,
        title="Arms",
        focus="upper",
        estimated_duration_minutes=RULESET.general_warmup_minutes
        + sum(item.estimated_minutes for item in exercises),
        exercises=exercises,
    )

    repaired, _ = repair_session_durations((day,), normalized, (), RULESET)

    assert [item.rest_seconds for item in repaired[0].exercises] == [75, 75]
    assert all(
        "SESSION_DURATION_REPAIR_EXTENDED_REST" not in item.reason_codes
        for item in repaired[0].exercises
    )


def test_overfill_uses_safe_superset_before_reducing_rest() -> None:
    normalized = normalize_request(
        request(session_duration_minutes=60, available_training_days=1), RULESET
    )
    test_ruleset = replace(RULESET, minimum_exercises_per_session=2)
    curl = replace(
        _exercise(
            name="Cable Curl",
            muscle=MuscleGroup.BICEPS,
            pattern=MovementPattern.ELBOW_FLEXION,
            order=1,
            reason_codes=("REQUIRED_ARM_SLOT",),
        ),
        estimated_minutes=36,
    )
    extension = replace(
        _exercise(
            name="Cable Triceps Extension",
            muscle=MuscleGroup.TRICEPS,
            pattern=MovementPattern.ELBOW_EXTENSION,
            order=2,
            reason_codes=("REQUIRED_ARM_SLOT",),
        ),
        estimated_minutes=36,
    )
    day = WorkoutDay(
        day_index=1,
        weekday=None,
        title="Arms",
        focus="upper",
        estimated_duration_minutes=77,
        exercises=(curl, extension),
    )

    repaired, reasons = repair_session_durations((day,), normalized, (), test_ruleset)

    assert repaired[0].estimated_duration_minutes == 74
    assert [item.rest_seconds for item in repaired[0].exercises] == [75, 75]
    assert repaired[0].exercises[0].superset_group == repaired[0].exercises[1].superset_group
    assert "SAFE_SUPERSET_APPLIED_FOR_DURATION" in reasons
