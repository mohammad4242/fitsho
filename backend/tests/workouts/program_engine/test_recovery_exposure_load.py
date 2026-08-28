from dataclasses import replace
from uuid import uuid4

from app.exercises.enums import ExerciseType, MovementPattern, MuscleGroup
from app.workouts.program_engine.engine import generate_program
from app.workouts.program_engine.enums import (
    BodyPosition,
    Goal,
    LoadLimit,
    RecoveryRating,
    SplitType,
    TrainingExperience,
)
from app.workouts.program_engine.normalization import normalize_request
from app.workouts.program_engine.recovery import (
    ExposureLoad,
    classify_muscle_exposures,
    recovery_spacing_is_valid,
    repair_recovery_weekdays,
)
from app.workouts.program_engine.rulesets.resistance_training_v1 import RULESET
from app.workouts.program_engine.schemas import ProgrammedExercise, SplitPlan, WorkoutDay
from app.workouts.program_engine.split_selector import rank_split_candidates
from tests.workouts.program_engine.golden_fixtures import full_catalog, request


def _exercise(
    *,
    sets: int,
    reason_codes: tuple[str, ...] = ("TEST",),
    primary_muscle: MuscleGroup = MuscleGroup.BICEPS,
    secondary_muscles: tuple[MuscleGroup, ...] = (),
    movement_pattern: MovementPattern = MovementPattern.ELBOW_FLEXION,
    body_position: BodyPosition = BodyPosition.STANDING,
    axial_loading_level: LoadLimit = LoadLimit.LOW,
) -> ProgrammedExercise:
    return ProgrammedExercise(
        exercise_id=uuid4(),
        exercise_name="Cable Curl",
        order=1,
        sets=sets,
        rep_min=10,
        rep_max=15,
        target_rir=2,
        rest_seconds=75,
        estimated_minutes=5,
        reason_codes=reason_codes,
        movement_pattern=movement_pattern,
        primary_muscle=primary_muscle,
        secondary_muscles=secondary_muscles,
        body_position=body_position,
        axial_loading_level=axial_loading_level,
        exercise_type=ExerciseType.ISOLATION,
    )


def _day(*, weekday: int, exercise: ProgrammedExercise) -> WorkoutDay:
    return WorkoutDay(
        day_index=weekday + 1,
        weekday=weekday,
        title="Arms",
        focus="upper",
        estimated_duration_minutes=30,
        exercises=(exercise,),
    )


def test_exposure_classification_uses_load_and_primary_strength_role() -> None:
    light = _day(weekday=0, exercise=_exercise(sets=2))
    moderate = _day(weekday=0, exercise=_exercise(sets=3))
    high = _day(
        weekday=0,
        exercise=_exercise(sets=3, reason_codes=("STRENGTH_PRIMARY_COMPOUND",)),
    )

    assert classify_muscle_exposures(light, RULESET)[MuscleGroup.BICEPS] is ExposureLoad.LIGHT
    assert classify_muscle_exposures(moderate, RULESET)[MuscleGroup.BICEPS] is ExposureLoad.MODERATE
    assert classify_muscle_exposures(high, RULESET)[MuscleGroup.BICEPS] is ExposureLoad.HIGH


def test_light_accessory_exposures_can_be_consecutive() -> None:
    days = (
        _day(weekday=0, exercise=_exercise(sets=2)),
        _day(weekday=1, exercise=_exercise(sets=2)),
    )

    assert recovery_spacing_is_valid(days, RULESET)


def test_moderate_exposure_relaxes_only_against_light_follow_up() -> None:
    moderate_then_light = (
        _day(weekday=0, exercise=_exercise(sets=3)),
        _day(weekday=1, exercise=_exercise(sets=2)),
    )
    two_moderate = (
        _day(weekday=0, exercise=_exercise(sets=3)),
        _day(weekday=1, exercise=_exercise(sets=3)),
    )

    assert recovery_spacing_is_valid(moderate_then_light, RULESET)
    assert not recovery_spacing_is_valid(two_moderate, RULESET)


def test_high_exposure_requires_two_day_calendar_spacing() -> None:
    high = _exercise(sets=3, reason_codes=("STRENGTH_PRIMARY_COMPOUND",))

    assert not recovery_spacing_is_valid(
        (_day(weekday=0, exercise=high), _day(weekday=1, exercise=_exercise(sets=2))),
        RULESET,
    )
    assert recovery_spacing_is_valid(
        (_day(weekday=0, exercise=high), _day(weekday=2, exercise=_exercise(sets=2))),
        RULESET,
    )


def test_meaningful_secondary_chest_stress_blocks_next_day_direct_shoulders() -> None:
    chest_day = _day(
        weekday=0,
        exercise=_exercise(
            sets=6,
            primary_muscle=MuscleGroup.CHEST,
            secondary_muscles=(MuscleGroup.SHOULDERS,),
            movement_pattern=MovementPattern.HORIZONTAL_PUSH,
        ),
    )
    shoulder_day = _day(
        weekday=1,
        exercise=_exercise(sets=3, primary_muscle=MuscleGroup.SHOULDERS),
    )

    assert (
        classify_muscle_exposures(chest_day, RULESET)[MuscleGroup.SHOULDERS]
        is ExposureLoad.MODERATE
    )
    assert not recovery_spacing_is_valid((chest_day, shoulder_day), RULESET)
    assert recovery_spacing_is_valid((chest_day, replace(shoulder_day, weekday=2)), RULESET)


def test_meaningful_secondary_glute_stress_blocks_next_day_direct_glutes() -> None:
    quad_day = _day(
        weekday=0,
        exercise=_exercise(
            sets=6,
            primary_muscle=MuscleGroup.QUADRICEPS,
            secondary_muscles=(MuscleGroup.GLUTES,),
            movement_pattern=MovementPattern.SQUAT,
        ),
    )
    glute_day = _day(
        weekday=1,
        exercise=_exercise(sets=3, primary_muscle=MuscleGroup.GLUTES),
    )

    assert classify_muscle_exposures(quad_day, RULESET)[MuscleGroup.GLUTES] is ExposureLoad.MODERATE
    assert not recovery_spacing_is_valid((quad_day, glute_day), RULESET)


def test_recovery_repair_rearranges_days_without_removing_a_session() -> None:
    days = (
        _day(
            weekday=0,
            exercise=_exercise(sets=3, reason_codes=("STRENGTH_PRIMARY_COMPOUND",)),
        ),
        _day(weekday=1, exercise=_exercise(sets=3)),
    )
    split = SplitPlan(
        split_type=SplitType.UPPER_LOWER,
        day_focuses=("upper", "upper"),
        weekdays=(0, 1),
        score=1,
        reason_codes=(),
    )

    repaired_split, repaired_days, reasons = repair_recovery_weekdays(split, days, RULESET)

    assert len(repaired_days) == len(days) == 2
    assert {day.exercises[0].exercise_id for day in repaired_days} == {
        day.exercises[0].exercise_id for day in days
    }
    assert recovery_spacing_is_valid(repaired_days, RULESET)
    assert repaired_split.weekdays == tuple(day.weekday for day in repaired_days)
    assert "RECOVERY_WEEKDAYS_REARRANGED_FOR_EXPOSURE_LOAD" in reasons


def test_poor_recovery_ranking_preserves_requested_resistance_day_count() -> None:
    normalized = normalize_request(
        request(
            available_training_days=6,
            sleep_quality=RecoveryRating.POOR,
        ),
        RULESET,
    )

    ranked = rank_split_candidates(normalized, RULESET)

    assert ranked
    assert all(len(split.day_focuses) == 6 for split in ranked)
    assert all("SPLIT_REDUCED_FOR_RECOVERY" not in split.reason_codes for split in ranked)


def test_production_dense_chest_shoulder_generation_repairs_weekdays_and_preserves_exposure() -> (
    None
):
    catalog = full_catalog()
    expected_weekdays = {
        4: (0, 1, 2, 4),
        5: (0, 1, 2, 3, 4),
        6: (0, 1, 2, 3, 4, 5),
    }
    split_reasons: dict[int, tuple[str, ...]] = {}

    for training_days in (4, 5, 6):
        source = request(
            available_training_days=training_days,
            primary_goal=Goal.HYPERTROPHY,
            training_experience=TrainingExperience.ADVANCED,
            training_age_months=72,
            priority_muscles=[MuscleGroup.CHEST, MuscleGroup.SHOULDERS],
            preferred_weekdays=tuple(range(training_days)),
        )
        result = generate_program(source, catalog, RULESET)
        repeated = generate_program(source, catalog, RULESET)

        assert result.is_success, result.errors
        assert result.program is not None
        assert repeated.program is not None
        program = result.program
        split_reasons[training_days] = program.split.reason_codes
        assert len(program.weekly_schedule) == training_days
        assert (
            tuple(day.weekday for day in program.weekly_schedule)
            == expected_weekdays[training_days]
        )
        assert tuple(day.weekday for day in repeated.program.weekly_schedule) == tuple(
            day.weekday for day in program.weekly_schedule
        )
        assert program.split.reason_codes == repeated.program.split.reason_codes

        chest_days = [
            day
            for day in program.weekly_schedule
            if MuscleGroup.CHEST in classify_muscle_exposures(day, RULESET)
        ]
        shoulder_days = [
            day
            for day in program.weekly_schedule
            if MuscleGroup.SHOULDERS in classify_muscle_exposures(day, RULESET)
        ]
        assert chest_days
        assert shoulder_days
        assert any(
            MuscleGroup.SHOULDERS in exercise.secondary_muscles
            for day in chest_days
            for exercise in day.exercises
            if exercise.primary_muscle is MuscleGroup.CHEST
        )
        assert all(
            classify_muscle_exposures(day, RULESET)[MuscleGroup.SHOULDERS]
            in {ExposureLoad.MODERATE, ExposureLoad.HIGH}
            for day in shoulder_days
        )
        assert recovery_spacing_is_valid(program.weekly_schedule, RULESET)

    assert "RECOVERY_WEEKDAYS_REARRANGED_FOR_EXPOSURE_LOAD" in split_reasons[4]
