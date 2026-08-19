from dataclasses import replace
from uuid import uuid4

import pytest

from app.exercises.enums import (
    Difficulty,
    Equipment,
    ExerciseLabel,
    ExerciseType,
    MovementPattern,
    MuscleGroup,
)
from app.profile.enums import TrainingLocation
from app.workouts.program_engine.engine import generate_program
from app.workouts.program_engine.enums import (
    CardioIntensity,
    GenerationErrorCode,
    Goal,
    ImpactLimit,
    RedFlag,
    SafetyStatus,
    TrainingExperience,
)
from app.workouts.program_engine.normalization import normalize_request
from app.workouts.program_engine.prescription import allocate_direct_sets
from app.workouts.program_engine.progression import double_progression_policy
from app.workouts.program_engine.rulesets.resistance_training_v1 import RULESET
from app.workouts.program_engine.schemas import (
    ExerciseCandidate,
    NormalizedProgramRequest,
    ProgramGenerationRequest,
    ProgrammedExercise,
    WorkoutDay,
)
from app.workouts.program_engine.split_selector import select_split
from app.workouts.program_engine.validation import validate_program
from app.workouts.program_engine.volume_planner import plan_weekly_volume
from app.workouts.program_engine.volume_repair import repair_weekly_volume
from tests.workouts.program_engine.golden_fixtures import full_catalog


def request(**overrides: object) -> ProgramGenerationRequest:
    values: dict[str, object] = {
        "user_id": uuid4(),
        "age": 30,
        "height_cm": 175,
        "weight_kg": 75,
        "primary_goal": Goal.GENERAL_FITNESS,
        "training_experience": TrainingExperience.BEGINNER,
        "training_age_months": 3,
        "available_training_days": 1,
        "session_duration_minutes": 45,
        "available_equipment": [Equipment.BODYWEIGHT],
        "training_location": TrainingLocation.HOME,
        "seed_optional": 99,
    }
    values.update(overrides)
    return ProgramGenerationRequest.model_validate(values)


def exercise(
    name: str,
    pattern: MovementPattern,
    muscle: MuscleGroup | None,
    *,
    exercise_type: ExerciseType = ExerciseType.COMPOUND,
    labels: frozenset[ExerciseLabel] = frozenset(),
    impact: ImpactLimit = ImpactLimit.LOW,
) -> ExerciseCandidate:
    return ExerciseCandidate(
        id=uuid4(),
        name=name,
        primary_muscle=muscle,
        secondary_muscles=(),
        movement_pattern=pattern,
        exercise_type=exercise_type,
        equipment=frozenset({Equipment.BODYWEIGHT}),
        difficulty=Difficulty.BEGINNER,
        labels=labels,
        impact_level=impact,
        substitution_group=pattern.value,
    )


def catalog(*, cardio_impact: ImpactLimit = ImpactLimit.LOW) -> list[ExerciseCandidate]:
    return [
        exercise("push-up", MovementPattern.HORIZONTAL_PUSH, MuscleGroup.CHEST),
        exercise("row", MovementPattern.HORIZONTAL_PULL, MuscleGroup.BACK),
        exercise("squat", MovementPattern.SQUAT, MuscleGroup.QUADRICEPS),
        exercise("hinge", MovementPattern.HIP_HINGE, MuscleGroup.HAMSTRINGS),
        exercise(
            "plank",
            MovementPattern.CORE_ANTI_EXTENSION,
            MuscleGroup.ABS,
            exercise_type=ExerciseType.CORE,
        ),
        exercise("calf raise", MovementPattern.CALF_RAISE, MuscleGroup.CALVES),
        exercise(
            "march",
            MovementPattern.OTHER,
            None,
            exercise_type=ExerciseType.OTHER,
            labels=frozenset({ExerciseLabel.CARDIO}),
            impact=cardio_impact,
        ),
    ]


def test_identical_input_catalog_ruleset_and_seed_are_identical() -> None:
    source = request()
    candidates = catalog()

    first = generate_program(source, candidates, RULESET)
    second = generate_program(source, list(reversed(candidates)), RULESET)

    assert first == second
    assert first.is_success


def test_goal_specific_prescriptions_use_ranges_rir_and_rest() -> None:
    strength = generate_program(request(primary_goal=Goal.STRENGTH), catalog(), RULESET)
    hypertrophy = generate_program(request(primary_goal=Goal.HYPERTROPHY), catalog(), RULESET)
    endurance = generate_program(request(primary_goal=Goal.MUSCULAR_ENDURANCE), catalog(), RULESET)

    assert strength.program is not None
    assert hypertrophy.program is not None
    assert endurance.program is not None
    strength_main = strength.program.weekly_schedule[0].exercises[0]
    hypertrophy_main = hypertrophy.program.weekly_schedule[0].exercises[0]
    endurance_main = endurance.program.weekly_schedule[0].exercises[0]
    assert (strength_main.rep_min, strength_main.rep_max) == (3, 6)
    assert strength_main.rest_seconds >= 120
    assert (hypertrophy_main.rep_min, hypertrophy_main.rep_max) == (6, 12)
    assert (endurance_main.rep_min, endurance_main.rep_max) == (12, 25)
    assert 1 <= hypertrophy_main.target_rir <= 4


def test_no_exact_weight_is_prescribed_without_performance_data() -> None:
    result = generate_program(request(), catalog(), RULESET)

    assert result.program is not None
    assert all(
        "kg" not in item.load_guidance.lower()
        for day in result.program.weekly_schedule
        for item in day.exercises
    )


def test_warmup_sets_do_not_count_toward_working_volume() -> None:
    result = generate_program(request(), catalog(), RULESET)

    assert result.program is not None
    day = result.program.weekly_schedule[0]
    assert day.exercises[0].warmup_sets >= 2
    direct = result.program.aggregate_metrics["weekly_direct_sets_by_muscle"]
    expected = sum(item.sets for item in day.exercises if item.primary_muscle is MuscleGroup.CHEST)
    assert direct[MuscleGroup.CHEST.value] == expected


def test_session_title_lists_direct_targets_but_not_secondary_muscles() -> None:
    candidates = catalog()
    candidates[0] = replace(
        candidates[0],
        secondary_muscles=(MuscleGroup.TRICEPS, MuscleGroup.SHOULDERS),
    )

    result = generate_program(request(), candidates, RULESET)

    assert result.program is not None
    assert result.program.weekly_schedule[0].title == (
        "Day 1: Chest + Back + Quadriceps + Hamstrings + Abs"
    )
    assert "Triceps" not in result.program.weekly_schedule[0].title


def test_direct_sets_are_distributed_exactly_across_exposures() -> None:
    assert allocate_direct_sets(10, 3, RULESET.minimum_working_sets) == (4, 3, 3)
    assert allocate_direct_sets(9, 4, RULESET.minimum_working_sets) == (3, 2, 2, 2)


def test_four_day_program_does_not_round_each_muscle_exposure_up() -> None:
    source = request(
        primary_goal=Goal.HYPERTROPHY,
        training_experience=TrainingExperience.INTERMEDIATE,
        training_age_months=30,
        available_training_days=4,
        available_equipment=[Equipment.BODYWEIGHT, Equipment.DUMBBELL],
    )

    result = generate_program(
        source,
        full_catalog(),
        RULESET,
    )

    assert result.program is not None, result.errors
    direct = result.program.aggregate_metrics["weekly_direct_sets_by_muscle"]
    maximum = RULESET.maximum_sets[result.program.training_status]
    assert all(value <= maximum for value in direct.values())


def test_volume_repair_reduces_hard_excess_before_validation() -> None:
    source = request()
    result = generate_program(source, catalog(), RULESET)
    assert result.program is not None
    day = result.program.weekly_schedule[0]
    chest = next(item for item in day.exercises if item.primary_muscle is MuscleGroup.CHEST)
    excessive_chest = replace(chest, sets=10)
    excessive_day = replace(
        day,
        exercises=tuple(excessive_chest if item is chest else item for item in day.exercises),
    )
    normalized = normalize_request(source, RULESET)
    volume = plan_weekly_volume(normalized, result.program.split, RULESET)

    repaired_days, reasons = repair_weekly_volume((excessive_day,), normalized, volume, RULESET)

    repaired_chest = next(
        item for item in repaired_days[0].exercises if item.primary_muscle is MuscleGroup.CHEST
    )
    assert repaired_chest.sets == min(
        RULESET.maximum_sets[result.program.training_status],
        RULESET.max_sets_per_muscle_per_session,
    )
    assert "VOLUME_REPAIR_REDUCED_SET" in reasons


def test_volume_target_keeps_effective_target_and_direct_minimum_separate() -> None:
    source = request()
    normalized = normalize_request(source, RULESET)
    volume = plan_weekly_volume(normalized, select_split(normalized, RULESET), RULESET)

    target = next(item for item in volume.targets if item.muscle is MuscleGroup.TRICEPS)

    assert target.effective_target_sets == target.target_sets
    assert target.minimum_direct_sets == target.minimum_soft


def programmed_volume_exercise(
    primary: MuscleGroup,
    secondary: tuple[MuscleGroup, ...],
    sets: int,
) -> ProgrammedExercise:
    return ProgrammedExercise(
        exercise_id=uuid4(),
        exercise_name="volume test exercise",
        order=1,
        sets=sets,
        rep_min=8,
        rep_max=12,
        target_rir=2,
        rest_seconds=90,
        estimated_minutes=8,
        reason_codes=("TEST",),
        movement_pattern=MovementPattern.HORIZONTAL_PUSH,
        primary_muscle=primary,
        secondary_muscles=secondary,
    )


def volume_test_day(exercise: ProgrammedExercise) -> WorkoutDay:
    return WorkoutDay(
        day_index=1,
        weekday=0,
        title="Volume test",
        focus="full_body",
        estimated_duration_minutes=13,
        exercises=(exercise,),
    )


def volume_with_targets(
    normalized: NormalizedProgramRequest,
    *,
    effective_target: dict[MuscleGroup, int],
    minimum_direct: dict[MuscleGroup, int] | None = None,
    maximum_hard: dict[MuscleGroup, int] | None = None,
):
    source = normalized
    volume = plan_weekly_volume(source, select_split(source, RULESET), RULESET)
    minimum_direct = minimum_direct or {}
    maximum_hard = maximum_hard or {}
    return replace(
        volume,
        targets=tuple(
            replace(
                target,
                effective_target_sets=effective_target.get(
                    target.muscle, target.effective_target_sets
                ),
                minimum_direct_sets=minimum_direct.get(target.muscle, target.minimum_direct_sets),
                maximum_hard=maximum_hard.get(target.muscle, target.maximum_hard),
            )
            for target in volume.targets
        ),
    )


def test_volume_repair_does_not_add_sets_when_effective_target_is_satisfied() -> None:
    source = request()
    normalized = normalize_request(source, RULESET)
    volume = volume_with_targets(
        normalized,
        effective_target={muscle: 0 for muscle in MuscleGroup},
    )
    volume = replace(
        volume,
        targets=tuple(
            replace(
                target,
                effective_target_sets=2
                if target.muscle is MuscleGroup.TRICEPS
                else target.effective_target_sets,
            )
            for target in volume.targets
        ),
    )
    day = volume_test_day(programmed_volume_exercise(MuscleGroup.CHEST, (MuscleGroup.TRICEPS,), 4))

    repaired, reasons = repair_weekly_volume((day,), normalized, volume, RULESET)

    assert repaired[0].exercises[0].sets == 4
    assert "VOLUME_REPAIR_ADDED_SET_FOR_EFFECTIVE_TARGET" not in reasons


def test_volume_repair_adds_existing_compound_set_when_effective_volume_is_under_target() -> None:
    source = request()
    normalized = normalize_request(source, RULESET)
    volume = volume_with_targets(
        normalized,
        effective_target={muscle: 0 for muscle in MuscleGroup},
    )
    volume = replace(
        volume,
        targets=tuple(
            replace(
                target,
                effective_target_sets=5
                if target.muscle is MuscleGroup.CHEST
                else target.effective_target_sets,
            )
            for target in volume.targets
        ),
    )
    day = volume_test_day(programmed_volume_exercise(MuscleGroup.CHEST, (), 4))

    repaired, reasons = repair_weekly_volume((day,), normalized, volume, RULESET)

    assert repaired[0].exercises[0].sets == 5
    assert "VOLUME_REPAIR_ADDED_SET_FOR_EFFECTIVE_TARGET" in reasons


def test_volume_repair_reduces_effective_secondary_cap() -> None:
    source = request()
    normalized = normalize_request(source, RULESET)
    volume = volume_with_targets(
        normalized,
        effective_target={muscle: 0 for muscle in MuscleGroup},
        minimum_direct={muscle: 0 for muscle in MuscleGroup},
        maximum_hard={MuscleGroup.TRICEPS: 1},
    )
    day = volume_test_day(programmed_volume_exercise(MuscleGroup.CHEST, (MuscleGroup.TRICEPS,), 4))

    repaired, reasons = repair_weekly_volume((day,), normalized, volume, RULESET)

    assert repaired[0].exercises[0].sets == 2
    assert "VOLUME_REPAIR_REDUCED_SET" in reasons


def test_validator_rejects_hard_weekly_volume_excess() -> None:
    source = request()
    result = generate_program(source, catalog(), RULESET)
    assert result.program is not None
    day = result.program.weekly_schedule[0]
    chest = next(item for item in day.exercises if item.primary_muscle is MuscleGroup.CHEST)
    invalid_day = replace(
        day,
        exercises=tuple(
            replace(item, sets=14) if item is chest else item for item in day.exercises
        ),
    )
    invalid = replace(result.program, weekly_schedule=(invalid_day,))

    report = validate_program(invalid, source, RULESET)

    assert "WEEKLY_MUSCLE_VOLUME_EXCEEDED" in report.errors


def test_validator_uses_effective_target_without_hiding_direct_work_requirement() -> None:
    candidates = catalog()
    candidates[0] = replace(
        candidates[0],
        secondary_muscles=(MuscleGroup.TRICEPS,),
    )
    result = generate_program(request(), candidates, RULESET)

    assert result.program is not None, result.errors
    actual_effective = result.program.aggregate_metrics["weekly_effective_sets_by_muscle"][
        MuscleGroup.TRICEPS.value
    ]
    actual_direct = result.program.aggregate_metrics["weekly_direct_sets_by_muscle"][
        MuscleGroup.TRICEPS.value
    ]
    assert actual_effective > 0
    assert actual_direct == 0

    ranges = dict(result.program.aggregate_metrics["volume_ranges_by_muscle"])
    ranges = {
        muscle: {
            **values,
            "effective_target_sets": int(
                result.program.aggregate_metrics["weekly_effective_sets_by_muscle"].get(muscle, 0)
            ),
        }
        for muscle, values in ranges.items()
    }
    ranges[MuscleGroup.TRICEPS.value] = {
        **ranges[MuscleGroup.TRICEPS.value],
        "minimum_direct_sets": 1,
    }
    program = replace(
        result.program,
        aggregate_metrics={
            **result.program.aggregate_metrics,
            "volume_ranges_by_muscle": ranges,
        },
    )

    report = validate_program(program, request(), RULESET)

    assert "EFFECTIVE_VOLUME_BELOW_TARGET" not in report.warnings
    assert "DIRECT_VOLUME_BELOW_MINIMUM" in report.warnings


def test_fat_loss_retains_resistance_and_adds_separate_cardio() -> None:
    result = generate_program(request(primary_goal=Goal.FAT_LOSS), catalog(), RULESET)

    assert result.program is not None
    day = result.program.weekly_schedule[0]
    assert day.exercises
    assert day.cardio is not None
    assert day.cardio.intensity is CardioIntensity.MODERATE


def test_low_impact_requirement_rejects_high_impact_cardio() -> None:
    result = generate_program(
        request(primary_goal=Goal.FAT_LOSS, impact_limit=ImpactLimit.LOW),
        catalog(cardio_impact=ImpactLimit.HIGH),
        RULESET,
    )

    assert result.program is not None
    assert all(day.cardio is None for day in result.program.weekly_schedule)


def test_double_progression_requires_two_qualifying_sessions() -> None:
    policy = double_progression_policy()

    assert policy["qualifying_sessions"] == 2
    assert policy["increase_volume_and_load_together"] is False


def test_safety_state_prevents_generation() -> None:
    result = generate_program(
        request(current_pain_or_red_flags=[RedFlag.CHEST_PAIN]), catalog(), RULESET
    )

    assert not result.is_success
    assert result.error_code is GenerationErrorCode.PROGRAM_REJECTED_SAFETY_STATUS
    assert result.safety_status is SafetyStatus.STOP_AND_REFER


def test_missing_safe_candidates_returns_structured_failure() -> None:
    result = generate_program(
        request(blocked_movement_patterns=[MovementPattern.HORIZONTAL_PULL]),
        catalog(),
        RULESET,
    )

    assert not result.is_success
    assert result.error_code is GenerationErrorCode.NO_SAFE_EXERCISE_FOR_PATTERN


def test_every_successful_program_passes_independent_validator() -> None:
    source = request(primary_goal=Goal.HYPERTROPHY)
    candidates = catalog()
    result = generate_program(source, candidates, RULESET)

    assert result.program is not None
    report = validate_program(result.program, source, RULESET)
    assert report.is_valid
    assert result.program.validation_report.is_valid


def test_validator_rejects_duration_overrun() -> None:
    source = request(session_duration_minutes=45)
    result = generate_program(source, catalog(), RULESET)
    assert result.program is not None
    day = result.program.weekly_schedule[0]
    invalid_day = replace(day, estimated_duration_minutes=99)
    invalid = replace(result.program, weekly_schedule=(invalid_day,))

    report = validate_program(invalid, source, RULESET)

    assert "SESSION_DURATION_EXCEEDED" in report.errors


@pytest.mark.parametrize("exercise_count", (4, 10))
def test_validator_rejects_session_exercise_counts_outside_the_ruleset(
    exercise_count: int,
) -> None:
    source = request()
    result = generate_program(source, catalog(), RULESET)
    assert result.program is not None
    day = result.program.weekly_schedule[0]
    invalid_exercises = (day.exercises * exercise_count)[:exercise_count]
    invalid_day = replace(day, exercises=invalid_exercises)
    invalid = replace(result.program, weekly_schedule=(invalid_day,))

    report = validate_program(invalid, source, RULESET)

    assert "SESSION_EXERCISE_COUNT_OUT_OF_RANGE" in report.errors


def test_validator_rejects_adjacent_full_body_sessions() -> None:
    source = request(available_training_days=3)
    result = generate_program(source, catalog(), RULESET)
    assert result.program is not None
    adjacent_days = tuple(
        replace(day, weekday=index) for index, day in enumerate(result.program.weekly_schedule)
    )
    invalid = replace(result.program, weekly_schedule=adjacent_days)

    report = validate_program(invalid, source, RULESET)

    assert "RECOVERY_SPACING_INVALID" in report.errors


def test_validator_rejects_a_third_direct_weekly_muscle_exposure_for_four_day_programs() -> None:
    source = request(available_training_days=4)
    result = generate_program(source, catalog(), RULESET)
    assert result.program is not None

    base_day = result.program.weekly_schedule[0]
    repeated_days = tuple(
        replace(base_day, day_index=index, weekday=weekday)
        for index, weekday in enumerate((0, 1, 3), start=1)
    )
    fourth_day = replace(
        base_day,
        day_index=4,
        weekday=4,
        exercises=(),
        estimated_duration_minutes=RULESET.general_warmup_minutes,
    )
    weekly_schedule = (*repeated_days, fourth_day)
    invalid = replace(
        result.program,
        weekly_schedule=weekly_schedule,
        split=replace(
            result.program.split,
            day_focuses=tuple(day.focus for day in weekly_schedule),
            weekdays=(0, 1, 3, 4),
        ),
    )

    report = validate_program(invalid, source, RULESET)

    assert "MUSCLE_DIRECT_FREQUENCY_EXCEEDED" in report.errors
    assert report.metrics["direct_session_frequency_by_muscle"]["chest"] == 3


def test_validator_rejects_program_without_trunk_pattern() -> None:
    source = request()
    result = generate_program(source, catalog(), RULESET)
    assert result.program is not None
    day = result.program.weekly_schedule[0]
    without_trunk = replace(
        day,
        exercises=tuple(
            item
            for item in day.exercises
            if item.movement_pattern is not MovementPattern.CORE_ANTI_EXTENSION
        ),
    )
    invalid = replace(result.program, weekly_schedule=(without_trunk,))

    report = validate_program(invalid, source, RULESET)

    assert "REQUIRED_MOVEMENT_PATTERN_MISSING" in report.errors
