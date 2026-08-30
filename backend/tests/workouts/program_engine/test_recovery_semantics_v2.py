from dataclasses import replace
from uuid import uuid4

from app.exercises.enums import ExerciseType, MovementPattern, MuscleGroup
from app.workouts.program_engine import engine
from app.workouts.program_engine.constraint_classification import ConstraintClass
from app.workouts.program_engine.engine import generate_program
from app.workouts.program_engine.enums import (
    BodyPosition,
    Goal,
    LoadLimit,
    SplitType,
    TrainingExperience,
)
from app.workouts.program_engine.normalization import normalize_request
from app.workouts.program_engine.recovery import (
    ExposureLoad,
    ExposureSource,
    _within_session_hard_volume,
    assess_recovery_spacing,
    classify_muscle_exposure_details,
    recovery_spacing_is_valid,
    repair_recovery_accessory_distribution,
    repair_recovery_weekdays,
)
from app.workouts.program_engine.rulesets.resistance_training_v1 import RULESET
from app.workouts.program_engine.schemas import ProgrammedExercise, SplitPlan, WorkoutDay
from app.workouts.program_engine.validation import validate_program
from tests.workouts.program_engine.golden_fixtures import full_catalog, request


def _exercise(
    *,
    sets: int,
    primary: MuscleGroup = MuscleGroup.BICEPS,
    secondary: tuple[MuscleGroup, ...] = (),
    high: bool = False,
) -> ProgrammedExercise:
    return ProgrammedExercise(
        exercise_id=uuid4(),
        exercise_name="Test exercise",
        order=1,
        sets=sets,
        rep_min=8,
        rep_max=12,
        target_rir=2,
        rest_seconds=90,
        estimated_minutes=5,
        reason_codes=("STRENGTH_PRIMARY_COMPOUND",) if high else ("TEST",),
        movement_pattern=MovementPattern.OTHER,
        primary_muscle=primary,
        secondary_muscles=secondary,
        body_position=BodyPosition.STANDING,
        axial_loading_level=LoadLimit.HIGH if high else LoadLimit.LOW,
        exercise_type=ExerciseType.COMPOUND if high else ExerciseType.ISOLATION,
    )


def _day(
    weekday: int,
    *exercises: ProgrammedExercise,
    target_muscles: tuple[MuscleGroup, ...] = (),
    focus: str = "test",
) -> WorkoutDay:
    return WorkoutDay(
        day_index=weekday + 1,
        weekday=weekday,
        title="Test day",
        focus=focus,
        estimated_duration_minutes=30,
        exercises=exercises,
        template_target_muscles=target_muscles,
    )


def _split(*focuses: str) -> SplitPlan:
    weekdays = tuple(range(len(focuses)))
    return SplitPlan(
        split_type=SplitType.BODY_PART_ROTATION,
        day_focuses=focuses,
        weekdays=weekdays,
        score=1,
        reason_codes=(),
    )


def test_detailed_exposure_keeps_direct_and_secondary_sets_separate() -> None:
    details = classify_muscle_exposure_details(
        _day(
            0,
            _exercise(
                sets=4,
                primary=MuscleGroup.CHEST,
                secondary=(MuscleGroup.SHOULDERS,),
            ),
            _exercise(sets=2, primary=MuscleGroup.SHOULDERS),
        ),
        RULESET,
    )[MuscleGroup.SHOULDERS]

    assert details.direct_sets == 2
    assert details.secondary_effective_sets == 2.0
    assert details.total_effective_sets == 4.0
    assert details.source is ExposureSource.MIXED
    assert details.load is ExposureLoad.MODERATE
    assert details.high_load_evidence is False


def test_six_direct_isolation_sets_are_moderate_without_high_fatigue_evidence() -> None:
    details = classify_muscle_exposure_details(
        _day(0, _exercise(sets=6)), RULESET
    )[MuscleGroup.BICEPS]

    assert details.load is ExposureLoad.MODERATE


def test_very_large_direct_isolation_dose_is_still_high() -> None:
    details = classify_muscle_exposure_details(
        _day(0, _exercise(sets=RULESET.recovery_high_direct_sets * 2)), RULESET
    )[MuscleGroup.BICEPS]

    assert details.load is ExposureLoad.HIGH


def test_direct_high_to_direct_high_is_a_hard_conflict() -> None:
    days = (
        _day(0, _exercise(sets=5, high=True)),
        _day(1, _exercise(sets=5, high=True)),
    )

    assessment = assess_recovery_spacing(days, RULESET)

    assert not assessment.is_valid
    assert assessment.conflicts[0].constraint_class is ConstraintClass.HARD
    assert assessment.conflicts[0].muscle is MuscleGroup.BICEPS
    assert not recovery_spacing_is_valid(days, RULESET)


def test_direct_high_to_direct_moderate_is_repairable() -> None:
    assessment = assess_recovery_spacing(
        (_day(0, _exercise(sets=5, high=True)), _day(1, _exercise(sets=3))), RULESET
    )

    assert not assessment.is_valid
    assert assessment.conflicts[0].constraint_class is ConstraintClass.REPAIRABLE


def test_direct_moderate_to_direct_moderate_is_repairable() -> None:
    assessment = assess_recovery_spacing(
        (_day(0, _exercise(sets=3)), _day(1, _exercise(sets=3))), RULESET
    )

    assert assessment.conflicts[0].constraint_class is ConstraintClass.REPAIRABLE


def test_direct_and_small_secondary_overlap_is_allowed_both_directions() -> None:
    direct = _day(0, _exercise(sets=3))
    secondary = _day(
        1,
        _exercise(sets=2, primary=MuscleGroup.CHEST, secondary=(MuscleGroup.BICEPS,)),
    )

    assert recovery_spacing_is_valid((direct, secondary), RULESET)
    assert recovery_spacing_is_valid((secondary, direct), RULESET)


def test_substantial_secondary_overlap_is_repairable_but_not_hard() -> None:
    days = (
        _day(0, _exercise(sets=8, primary=MuscleGroup.CHEST, secondary=(MuscleGroup.BICEPS,))),
        _day(1, _exercise(sets=3)),
    )

    assessment = assess_recovery_spacing(days, RULESET)

    assert not assessment.is_valid
    assert assessment.conflicts[0].constraint_class is ConstraintClass.REPAIRABLE
    assert assessment.conflicts[0].day_a_secondary_effective_sets == 4.0


def test_secondary_to_secondary_never_independently_hard_rejects() -> None:
    days = (
        _day(0, _exercise(sets=12, primary=MuscleGroup.CHEST, secondary=(MuscleGroup.BICEPS,))),
        _day(
            1,
            _exercise(sets=12, primary=MuscleGroup.QUADRICEPS, secondary=(MuscleGroup.BICEPS,)),
        ),
    )

    assessment = assess_recovery_spacing(days, RULESET)

    assert assessment.is_valid
    assert not assessment.hard_conflicts


def test_recovery_repair_reorders_repairable_overlap_and_preserves_sessions() -> None:
    days = (_day(0, _exercise(sets=3)), _day(1, _exercise(sets=3)))
    split = _split("arms", "arms")

    repaired_split, repaired_days, reasons = repair_recovery_weekdays(split, days, RULESET)

    assert len(repaired_days) == 2
    assert repaired_split.weekdays == tuple(day.weekday for day in repaired_days)
    assert recovery_spacing_is_valid(repaired_days, RULESET)
    assert "RECOVERY_WEEKDAYS_REARRANGED_FOR_EXPOSURE_LOAD" in reasons


def test_recovery_repair_moves_optional_isolation_without_changing_topology() -> None:
    day_zero = _day(
        0,
        _exercise(sets=5, high=True),
        *(_exercise(sets=3, primary=MuscleGroup.CHEST) for _ in range(6)),
        target_muscles=(MuscleGroup.BICEPS, MuscleGroup.CHEST),
    )
    movable = _exercise(sets=3)
    day_one = _day(
        1,
        movable,
        *(_exercise(sets=3, primary=MuscleGroup.BACK) for _ in range(7)),
        target_muscles=(MuscleGroup.BICEPS, MuscleGroup.BACK),
    )
    recipient = _day(
        4,
        *(_exercise(sets=3, primary=MuscleGroup.BACK) for _ in range(7)),
        target_muscles=(MuscleGroup.BICEPS, MuscleGroup.BACK),
    )
    source = request(
        available_training_days=3,
        session_duration_minutes=45,
        training_age_months=30,
    )
    normalized = normalize_request(source, RULESET)

    repaired, reasons = repair_recovery_accessory_distribution(
        (day_zero, day_one, recipient), normalized, RULESET
    )

    assert recovery_spacing_is_valid(repaired, RULESET)
    assert movable.exercise_id not in {item.exercise_id for item in repaired[1].exercises}
    assert sum(
        movable.exercise_id in {item.exercise_id for item in day.exercises}
        for day in repaired
    ) == 1
    assert tuple(day.focus for day in repaired) == ("test", "test", "test")
    assert "RECOVERY_OPTIONAL_ISOLATION_REDISTRIBUTED" in reasons


def test_recovery_repair_uses_dynamic_focus_when_template_targets_are_empty() -> None:
    day_zero = _day(
        0,
        _exercise(sets=5, high=True),
        *(_exercise(sets=3, primary=MuscleGroup.CHEST) for _ in range(6)),
    )
    movable = _exercise(sets=3)
    day_one = _day(
        1,
        movable,
        *(_exercise(sets=3, primary=MuscleGroup.BACK) for _ in range(7)),
        focus="pull",
    )
    recipient = _day(
        4,
        *(_exercise(sets=3, primary=MuscleGroup.BACK) for _ in range(7)),
        focus="pull",
    )
    normalized = normalize_request(
        request(
            available_training_days=3,
            session_duration_minutes=45,
            training_age_months=30,
        ),
        RULESET,
    )

    repaired, reasons = repair_recovery_accessory_distribution(
        (day_zero, day_one, recipient), normalized, RULESET
    )

    assert recovery_spacing_is_valid(repaired, RULESET)
    assert movable.exercise_id in {item.exercise_id for item in repaired[2].exercises}
    assert "RECOVERY_OPTIONAL_ISOLATION_REDISTRIBUTED" in reasons


def test_recovery_repair_prefers_dedicated_recipient_over_earlier_grouped_day() -> None:
    day_zero = _day(
        0,
        _exercise(sets=5, high=True),
        *(_exercise(sets=3, primary=MuscleGroup.CHEST) for _ in range(6)),
    )
    movable = _exercise(sets=3)
    source = _day(
        1,
        movable,
        *(_exercise(sets=3, primary=MuscleGroup.BACK) for _ in range(6)),
        focus="back_biceps",
    )
    grouped_recipient = _day(
        3,
        *(_exercise(sets=3, primary=MuscleGroup.BACK) for _ in range(6)),
        focus="back_biceps",
    )
    dedicated_recipient = _day(
        5,
        *(_exercise(sets=3, primary=MuscleGroup.TRICEPS) for _ in range(6)),
        focus="arms",
    )
    normalized = normalize_request(
        request(
            available_training_days=4,
            session_duration_minutes=45,
            training_age_months=30,
        ),
        RULESET,
    )

    repaired, reasons = repair_recovery_accessory_distribution(
        (day_zero, source, grouped_recipient, dedicated_recipient), normalized, RULESET
    )

    assert movable.exercise_id not in {item.exercise_id for item in repaired[1].exercises}
    assert movable.exercise_id not in {item.exercise_id for item in repaired[2].exercises}
    assert movable.exercise_id in {item.exercise_id for item in repaired[3].exercises}
    assert sum(
        movable.exercise_id in {item.exercise_id for item in day.exercises}
        for day in repaired
    ) == 1
    assert recovery_spacing_is_valid(repaired, RULESET)
    assert "RECOVERY_OPTIONAL_ISOLATION_REDISTRIBUTED" in reasons


def test_recovery_repair_does_not_exceed_session_hard_volume() -> None:
    day_zero = _day(
        0,
        _exercise(sets=5, high=True),
        *(_exercise(sets=3, primary=MuscleGroup.CHEST) for _ in range(6)),
    )
    movable = _exercise(sets=3)
    day_one = _day(
        1,
        movable,
        *(_exercise(sets=3, primary=MuscleGroup.BACK) for _ in range(7)),
        focus="pull",
    )
    recipient = _day(
        4,
        _exercise(sets=29, high=True),
        *(_exercise(sets=3, primary=MuscleGroup.BACK) for _ in range(6)),
        focus="pull",
    )
    normalized = normalize_request(
        request(
            available_training_days=3,
            session_duration_minutes=45,
            training_age_months=30,
        ),
        RULESET,
    )

    repaired, reasons = repair_recovery_accessory_distribution(
        (day_zero, day_one, recipient), normalized, RULESET
    )

    assert repaired == (day_zero, day_one, recipient)
    assert reasons == ("RECOVERY_OPTIONAL_ISOLATION_REDISTRIBUTION_UNAVAILABLE",)
    overloaded = replace(
        recipient,
        exercises=(*recipient.exercises, movable),
    )
    assert not _within_session_hard_volume(overloaded, normalized)


def test_four_day_professional_body_part_rotation_is_recovery_feasible() -> None:
    days = tuple(
        _day(weekday, _exercise(sets=4, primary=muscle))
        for weekday, muscle in enumerate(
            (
                MuscleGroup.CHEST,
                MuscleGroup.BACK,
                MuscleGroup.QUADRICEPS,
                MuscleGroup.SHOULDERS,
            )
        )
    )

    assert recovery_spacing_is_valid(days, RULESET)


def test_five_day_body_part_rotation_is_recovery_feasible() -> None:
    days = tuple(
        _day(weekday, _exercise(sets=4, primary=muscle))
        for weekday, muscle in enumerate(
            (
                MuscleGroup.CHEST,
                MuscleGroup.BACK,
                MuscleGroup.QUADRICEPS,
                MuscleGroup.SHOULDERS,
                MuscleGroup.BICEPS,
            )
        )
    )

    assert recovery_spacing_is_valid(days, RULESET)


def test_six_day_ppl_double_is_recovery_feasible_with_secondary_overlap() -> None:
    days = (
        _day(
            0,
            _exercise(sets=4, primary=MuscleGroup.CHEST, secondary=(MuscleGroup.SHOULDERS,)),
        ),
        _day(
            1,
            _exercise(sets=4, primary=MuscleGroup.BACK, secondary=(MuscleGroup.BICEPS,)),
        ),
        _day(2, _exercise(sets=4, primary=MuscleGroup.QUADRICEPS)),
        _day(
            3,
            _exercise(sets=4, primary=MuscleGroup.CHEST, secondary=(MuscleGroup.SHOULDERS,)),
        ),
        _day(
            4,
            _exercise(sets=4, primary=MuscleGroup.BACK, secondary=(MuscleGroup.BICEPS,)),
        ),
        _day(5, _exercise(sets=4, primary=MuscleGroup.QUADRICEPS)),
    )

    assert recovery_spacing_is_valid(days, RULESET)


def test_six_day_arnold_style_split_is_recovery_feasible() -> None:
    days = tuple(
        _day(weekday, _exercise(sets=4, primary=muscle))
        for weekday, muscle in enumerate(
            (
                MuscleGroup.CHEST,
                MuscleGroup.BACK,
                MuscleGroup.SHOULDERS,
                MuscleGroup.CHEST,
                MuscleGroup.BACK,
                MuscleGroup.SHOULDERS,
            )
        )
    )

    assert recovery_spacing_is_valid(days, RULESET)


def test_six_direct_high_exposures_are_genuinely_impossible_to_space() -> None:
    days = tuple(_day(weekday, _exercise(sets=5, high=True)) for weekday in range(6))

    assessment = assess_recovery_spacing(days, RULESET)
    split, repaired_days, reasons = repair_recovery_weekdays(_split(*(["arms"] * 6)), days, RULESET)

    assert not assessment.is_valid
    assert assessment.hard_conflicts
    assert repaired_days == days
    assert split.weekdays == tuple(range(6))
    assert reasons == ("RECOVERY_WEEKDAY_REPAIR_UNAVAILABLE",)


def test_final_validation_warns_for_unresolved_repairable_overlap() -> None:
    source = request(available_training_days=2, session_duration_minutes=30)
    result = generate_program(source, full_catalog(), RULESET)
    assert result.program is not None, result.errors
    first, second = result.program.weekly_schedule
    schedule = (
        replace(first, weekday=0, exercises=(_exercise(sets=5, high=True),)),
        replace(second, weekday=1, exercises=(_exercise(sets=3),)),
    )

    report = validate_program(replace(result.program, weekly_schedule=schedule), source, RULESET)

    assert "RECOVERY_SPACING_INVALID" not in report.errors
    assert "RECOVERY_REPAIRABLE_OVERLAP_REMAINS" in report.warnings


def test_final_validation_keeps_adjacent_direct_high_exposure_hard() -> None:
    source = request(available_training_days=2, session_duration_minutes=30)
    result = generate_program(source, full_catalog(), RULESET)
    assert result.program is not None, result.errors
    first, second = result.program.weekly_schedule
    schedule = (
        replace(first, weekday=0, exercises=(_exercise(sets=5, high=True),)),
        replace(second, weekday=1, exercises=(_exercise(sets=5, high=True),)),
    )

    report = validate_program(replace(result.program, weekly_schedule=schedule), source, RULESET)

    assert "RECOVERY_SPACING_INVALID" in report.errors


def test_recovery_diagnostics_include_source_dose_gap_and_repair_outcome() -> None:
    assessment = assess_recovery_spacing(
        (_day(0, _exercise(sets=5, high=True)), _day(1, _exercise(sets=3))), RULESET
    )

    trace = assessment.decision_trace(
        repair_attempts=("reorder_weekdays", "move_isolation"),
        final_result="rejected",
    )

    assert trace["status"] == "repairable_conflict"
    assert trace["repair_attempts"] == ("reorder_weekdays", "move_isolation")
    assert trace["final_result"] == "rejected"
    assert trace["conflicts"] == (
        {
            "muscle": "biceps",
            "day_a": 0,
            "day_b": 1,
            "day_a_exposure": "high",
            "day_b_exposure": "moderate",
            "day_a_source": "direct",
            "day_b_source": "direct",
            "day_a_direct_sets": 5.0,
            "day_b_direct_sets": 3.0,
            "day_a_secondary_effective_sets": 0.0,
            "day_b_secondary_effective_sets": 0.0,
            "actual_gap_days": 1,
            "required_gap_days": 2,
            "constraint_class": "repairable",
        },
    )


def test_recovery_trace_lists_only_operations_that_were_attempted() -> None:
    before = (_day(0, _exercise(sets=5, high=True)), _day(1, _exercise(sets=3)))

    weekday_only = engine._recovery_repair_trace(
        before,
        before,
        ("RECOVERY_WEEKDAY_REPAIR_UNAVAILABLE",),
        RULESET,
    )
    with_accessory = engine._recovery_repair_trace(
        before,
        before,
        (
            "RECOVERY_WEEKDAY_REPAIR_UNAVAILABLE",
            "RECOVERY_OPTIONAL_ISOLATION_REDISTRIBUTION_UNAVAILABLE",
        ),
        RULESET,
    )

    assert weekday_only["repair_attempts"] == ("reorder_weekdays",)
    assert with_accessory["repair_attempts"] == (
        "reorder_weekdays",
        "move_optional_isolation",
    )


def test_generate_program_emits_exact_recovery_assessment_trace() -> None:
    result = generate_program(
        request(
            primary_goal=Goal.HYPERTROPHY,
            training_experience=TrainingExperience.ADVANCED,
            training_age_months=72,
            available_training_days=4,
            session_duration_minutes=30,
        ),
        full_catalog(),
        RULESET,
    )

    assert result.program is not None, result.errors
    trace = next(
        item for item in result.program.decision_trace if item.get("stage") == "recovery_repair"
    )
    assert trace["constraint_class"] in {"hard", "repairable", "soft", None}
    assert trace["before"]["status"] in {
        "valid",
        "soft_warning",
        "repairable_conflict",
        "hard_conflict",
    }
    assert trace["after"]["final_result"] in {
        "repaired",
        "accepted_with_warning",
        "rejected",
    }
    assert isinstance(trace["repair_attempts"], tuple)
