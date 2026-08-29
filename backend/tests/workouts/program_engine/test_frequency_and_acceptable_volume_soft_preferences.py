from dataclasses import replace
from uuid import uuid4

import pytest

from app.exercises.enums import (
    Difficulty,
    Equipment,
    ExerciseType,
    MovementPattern,
    MuscleGroup,
    PrescriptionMode,
)
from app.profile.enums import TrainingLocation
from app.workouts.program_engine.duration_policy import SessionDurationPolicy
from app.workouts.program_engine.engine import generate_program
from app.workouts.program_engine.enums import Goal, SplitType, TrainingExperience
from app.workouts.program_engine.final_gate import evaluate_final_program
from app.workouts.program_engine.normalization import normalize_request
from app.workouts.program_engine.rulesets.resistance_training_v1 import RULESET
from app.workouts.program_engine.schemas import (
    ExerciseCandidate,
    ProgramGenerationRequest,
    ProgrammedExercise,
    VolumeTarget,
    WorkoutDay,
)
from app.workouts.program_engine.session_duration import (
    _select_exercise_addition as select_duration_candidate,
)
from app.workouts.program_engine.validation import validate_program
from app.workouts.program_engine.volume_repair import (
    _select_exercise_addition as select_repair_candidate,
)
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
        "available_equipment": [
            Equipment.BODYWEIGHT,
            Equipment.PULL_UP_BAR,
            Equipment.BARBELL,
            Equipment.DUMBBELL,
        ],
        "training_location": TrainingLocation.HOME,
        "seed_optional": 99,
    }
    values.update(overrides)
    return ProgramGenerationRequest.model_validate(values)


def _make_test_candidate(
    name: str,
    pattern: MovementPattern,
    muscle: MuscleGroup,
    exercise_type: ExerciseType = ExerciseType.COMPOUND,
) -> ExerciseCandidate:
    return ExerciseCandidate(
        id=uuid4(),
        name=name,
        primary_muscle=muscle,
        secondary_muscles=(),
        movement_pattern=pattern,
        equipment=(Equipment.BODYWEIGHT,),
        caution_tags=(),
        difficulty=Difficulty.BEGINNER,
        is_active=True,
        is_programmable=True,
        exercise_type=exercise_type,
        substitution_group=pattern.value,
        prescription_mode=PrescriptionMode.REPS,
    )


def _secondary_chest_exercise(order: int) -> ProgrammedExercise:
    return ProgrammedExercise(
        exercise_id=uuid4(),
        exercise_name=f"Biceps secondary {order}",
        order=order,
        sets=4,
        rep_min=8,
        rep_max=12,
        target_rir=2,
        rest_seconds=90,
        estimated_minutes=8,
        reason_codes=("SELECTION",),
        primary_muscle=MuscleGroup.BICEPS,
        secondary_muscles=(MuscleGroup.CHEST,),
        exercise_type=ExerciseType.ISOLATION,
        movement_pattern=MovementPattern.ELBOW_FLEXION,
        prescription_mode=PrescriptionMode.REPS,
    )


def _direct_chest_exercise(order: int, sets: int) -> ProgrammedExercise:
    return ProgrammedExercise(
        exercise_id=uuid4(),
        exercise_name=f"Chest direct {order}",
        order=order,
        sets=sets,
        rep_min=8,
        rep_max=12,
        target_rir=2,
        rest_seconds=90,
        estimated_minutes=8,
        reason_codes=("SELECTION",),
        primary_muscle=MuscleGroup.CHEST,
        secondary_muscles=(),
        exercise_type=ExerciseType.COMPOUND,
        movement_pattern=MovementPattern.HORIZONTAL_PUSH,
        prescription_mode=PrescriptionMode.REPS,
    )


def test_exceeding_direct_frequency_is_warning_and_not_final_gate_rejected() -> None:
    source = request(
        available_training_days=4,
        training_experience=TrainingExperience.INTERMEDIATE,
        training_age_months=24,
    )
    result = generate_program(source, full_catalog(), RULESET)
    assert result.program is not None

    base_day = result.program.weekly_schedule[0]
    repeated_days = tuple(
        replace(base_day, day_index=index, weekday=weekday)
        for index, weekday in enumerate((0, 1, 3, 4), start=1)
    )
    modified_program = replace(
        result.program,
        weekly_schedule=repeated_days,
        split=replace(
            result.program.split,
            split_type=SplitType.UPPER_LOWER,
            day_focuses=tuple(day.focus for day in repeated_days),
            weekdays=(0, 1, 3, 4),
        ),
    )

    report = validate_program(modified_program, source, RULESET)
    assert "MUSCLE_DIRECT_FREQUENCY_EXCEEDED" in report.warnings
    assert "MUSCLE_DIRECT_FREQUENCY_EXCEEDED" not in report.errors

    gate_result = evaluate_final_program(modified_program, source, report, RULESET)
    assert "MUSCLE_DIRECT_FREQUENCY_EXCEEDED" not in gate_result.reason_codes


def test_weekly_volume_outside_acceptable_range_is_warning_when_under_hard_maximum() -> None:
    source = request(
        available_training_days=4,
        training_experience=TrainingExperience.INTERMEDIATE,
        training_age_months=24,
    )
    result = generate_program(source, full_catalog(), RULESET)
    assert result.program is not None

    # Set acceptable range higher than actual volume (~10 sets), but below hard max (24)
    ranges = {
        "chest": {
            "acceptable_minimum": 18.0,
            "acceptable_maximum": 20.0,
            "effective_maximum_hard": 24,
            "status": "normal",
        }
    }
    metrics = dict(result.program.aggregate_metrics)
    metrics["volume_ranges_by_muscle"] = ranges
    program_outside_acceptable = replace(result.program, aggregate_metrics=metrics)

    report = validate_program(program_outside_acceptable, source, RULESET)
    assert "WEEKLY_VOLUME_OUTSIDE_ACCEPTABLE_RANGE" in report.warnings
    assert "WEEKLY_VOLUME_OUTSIDE_ACCEPTABLE_RANGE" not in report.errors

    gate_result = evaluate_final_program(program_outside_acceptable, source, report, RULESET)
    assert "WEEKLY_VOLUME_OUTSIDE_ACCEPTABLE_RANGE" not in gate_result.reason_codes


@pytest.mark.parametrize(
    ("training_age_months", "direct_sets", "expect_error"),
    [
        (12, 20, False),
        (12, 25, True),
        (72, 30, False),
        (72, 31, True),
    ],
)
def test_weekly_hard_volume_uses_direct_sets_for_classified_muscles(
    training_age_months: int,
    direct_sets: int,
    expect_error: bool,
) -> None:
    source = request(
        available_training_days=1,
        training_experience=(
            TrainingExperience.INTERMEDIATE
            if training_age_months <= 24
            else TrainingExperience.ADVANCED
        ),
        training_age_months=training_age_months,
    )
    result = generate_program(source, full_catalog(), RULESET)
    assert result.program is not None

    base_day = result.program.weekly_schedule[0]
    base_program = replace(
        result.program,
        weekly_schedule=(
            replace(
                base_day,
                exercises=tuple(
                    item
                    for item in base_day.exercises
                    if item.primary_muscle is not MuscleGroup.CHEST
                ),
            ),
            *result.program.weekly_schedule[1:],
        ),
    )
    chest_exercises: list[ProgrammedExercise] = []
    remaining = direct_sets
    order = 1
    while remaining > 0:
        sets = min(4, remaining)
        chest_exercises.append(_direct_chest_exercise(order, sets))
        remaining -= sets
        order += 1
    secondary_exercises = (
        tuple(_secondary_chest_exercise(order + index) for index in range(3))
        if training_age_months <= 24 and direct_sets == 20
        else ()
    )
    repaired_day = replace(
        base_program.weekly_schedule[0],
        exercises=tuple(chest_exercises) + secondary_exercises,
    )
    program = replace(
        base_program,
        weekly_schedule=(repaired_day, *base_program.weekly_schedule[1:]),
    )

    report = validate_program(program, source, RULESET)

    assert report.metrics["weekly_direct_sets_by_muscle"][MuscleGroup.CHEST.value] == direct_sets
    if training_age_months == 12 and direct_sets == 20:
        assert report.metrics["weekly_effective_sets_by_muscle"][MuscleGroup.CHEST.value] > 24
    assert ("WEEKLY_MUSCLE_VOLUME_EXCEEDED" in report.errors) is expect_error
    gate_result = evaluate_final_program(program, source, report, RULESET)
    assert ("WEEKLY_MUSCLE_VOLUME_EXCEEDED" in gate_result.reason_codes) is expect_error


def test_session_duration_selects_candidate_exceeding_frequency_when_necessary() -> None:
    source = request(
        available_training_days=4,
        training_experience=TrainingExperience.INTERMEDIATE,
        training_age_months=24,
        session_duration_minutes=60,
    )
    normalized = normalize_request(source, RULESET)
    policy = SessionDurationPolicy(requested_minutes=60, minimum_minutes=50, maximum_minutes=70)

    # Day 1, 2, 3 already expose chest (frequency = 3, frequency_cap for 4-day is 2)
    chest_cand = _make_test_candidate(
        "Chest Press", MovementPattern.HORIZONTAL_PUSH, MuscleGroup.CHEST
    )
    day1_ex = ProgrammedExercise(
        exercise_id=chest_cand.id,
        exercise_name=chest_cand.name,
        order=1,
        sets=3,
        rep_min=8,
        rep_max=12,
        duration_min_seconds=None,
        duration_max_seconds=None,
        prescription_mode=PrescriptionMode.REPS,
        target_rir=2,
        rest_seconds=90,
        estimated_minutes=8,
        reason_codes=(),
        substitution_exercise_ids=(),
        movement_pattern=MovementPattern.HORIZONTAL_PUSH,
        primary_muscle=MuscleGroup.CHEST,
        secondary_muscles=(),
        equipment=(Equipment.BODYWEIGHT,),
        caution_tags=(),
        range_of_motion_profile=None,
        impact_level=None,
        axial_loading_level=None,
        stability_demand=None,
        muscle_focus=None,
        body_position=None,
        laterality=None,
        substitution_group="horizontal_push",
        is_active=True,
        is_programmable=True,
        needs_review=False,
        exercise_type=ExerciseType.COMPOUND,
    )
    other_days = (
        WorkoutDay(
            day_index=1,
            weekday=0,
            title="Day 1",
            focus="full_body",
            exercises=(day1_ex,),
            estimated_duration_minutes=45,
        ),
        WorkoutDay(
            day_index=2,
            weekday=1,
            title="Day 2",
            focus="full_body",
            exercises=(day1_ex,),
            estimated_duration_minutes=45,
        ),
        WorkoutDay(
            day_index=3,
            weekday=3,
            title="Day 3",
            focus="full_body",
            exercises=(day1_ex,),
            estimated_duration_minutes=45,
        ),
    )
    current_day = WorkoutDay(
        day_index=4,
        weekday=4,
        title="Day 4",
        focus="full_body",
        exercises=(),
        estimated_duration_minutes=45,
    )

    chest_cand2 = _make_test_candidate(
        "Incline Pushup", MovementPattern.HORIZONTAL_PUSH, MuscleGroup.CHEST
    )

    selected = select_duration_candidate(
        day=current_day,
        exercises=[],
        request=normalized,
        candidates=(chest_cand2,),
        policy=policy,
        ruleset=RULESET,
        other_days=other_days,
        volume=None,
        prefer_acceptable_volume_for_minimum_fill=False,
        minimum_exercises=4,
    )
    assert selected is not None
    assert selected.exercise_id == chest_cand2.id


def test_session_duration_prefers_candidate_within_frequency_when_available() -> None:
    source = request(
        available_training_days=4,
        training_experience=TrainingExperience.INTERMEDIATE,
        training_age_months=24,
        session_duration_minutes=60,
    )
    normalized = normalize_request(source, RULESET)
    policy = SessionDurationPolicy(requested_minutes=60, minimum_minutes=50, maximum_minutes=70)

    # 3 days already have chest exposure
    chest_cand = _make_test_candidate(
        "Chest Press", MovementPattern.HORIZONTAL_PUSH, MuscleGroup.CHEST
    )
    back_cand = _make_test_candidate(
        "Inverted Row", MovementPattern.HORIZONTAL_PULL, MuscleGroup.BACK
    )

    day1_ex = ProgrammedExercise(
        exercise_id=chest_cand.id,
        exercise_name=chest_cand.name,
        order=1,
        sets=3,
        rep_min=8,
        rep_max=12,
        duration_min_seconds=None,
        duration_max_seconds=None,
        prescription_mode=PrescriptionMode.REPS,
        target_rir=2,
        rest_seconds=90,
        estimated_minutes=8,
        reason_codes=(),
        substitution_exercise_ids=(),
        movement_pattern=MovementPattern.HORIZONTAL_PUSH,
        primary_muscle=MuscleGroup.CHEST,
        secondary_muscles=(),
        equipment=(Equipment.BODYWEIGHT,),
        caution_tags=(),
        range_of_motion_profile=None,
        impact_level=None,
        axial_loading_level=None,
        stability_demand=None,
        muscle_focus=None,
        body_position=None,
        laterality=None,
        substitution_group="horizontal_push",
        is_active=True,
        is_programmable=True,
        needs_review=False,
        exercise_type=ExerciseType.COMPOUND,
    )
    other_days = (
        WorkoutDay(
            day_index=1,
            weekday=0,
            title="Day 1",
            focus="full_body",
            exercises=(day1_ex,),
            estimated_duration_minutes=45,
        ),
        WorkoutDay(
            day_index=2,
            weekday=1,
            title="Day 2",
            focus="full_body",
            exercises=(day1_ex,),
            estimated_duration_minutes=45,
        ),
        WorkoutDay(
            day_index=3,
            weekday=3,
            title="Day 3",
            focus="full_body",
            exercises=(day1_ex,),
            estimated_duration_minutes=45,
        ),
    )
    current_day = WorkoutDay(
        day_index=4,
        weekday=4,
        title="Day 4",
        focus="full_body",
        exercises=(),
        estimated_duration_minutes=45,
    )

    chest_cand2 = _make_test_candidate(
        "Incline Pushup", MovementPattern.HORIZONTAL_PUSH, MuscleGroup.CHEST
    )

    selected = select_duration_candidate(
        day=current_day,
        exercises=[],
        request=normalized,
        candidates=(chest_cand2, back_cand),
        policy=policy,
        ruleset=RULESET,
        other_days=other_days,
        volume=None,
        prefer_acceptable_volume_for_minimum_fill=False,
        minimum_exercises=4,
    )
    assert selected is not None
    assert selected.exercise_id == back_cand.id


def test_volume_repair_selects_candidate_exceeding_frequency_when_needed() -> None:
    source = request(
        available_training_days=4,
        training_experience=TrainingExperience.INTERMEDIATE,
        training_age_months=24,
    )
    normalized = normalize_request(source, RULESET)

    chest_cand = _make_test_candidate("Pushup", MovementPattern.HORIZONTAL_PUSH, MuscleGroup.CHEST)
    chest_cand2 = _make_test_candidate("Dips", MovementPattern.VERTICAL_PUSH, MuscleGroup.CHEST)

    programmed_chest = ProgrammedExercise(
        exercise_id=chest_cand.id,
        exercise_name=chest_cand.name,
        order=1,
        sets=2,
        rep_min=8,
        rep_max=12,
        duration_min_seconds=None,
        duration_max_seconds=None,
        prescription_mode=PrescriptionMode.REPS,
        target_rir=2,
        rest_seconds=90,
        estimated_minutes=8,
        reason_codes=(),
        substitution_exercise_ids=(),
        movement_pattern=MovementPattern.HORIZONTAL_PUSH,
        primary_muscle=MuscleGroup.CHEST,
        secondary_muscles=(),
        equipment=(Equipment.BODYWEIGHT,),
        caution_tags=(),
        range_of_motion_profile=None,
        impact_level=None,
        axial_loading_level=None,
        stability_demand=None,
        muscle_focus=None,
        body_position=None,
        laterality=None,
        substitution_group="horizontal_push",
        is_active=True,
        is_programmable=True,
        needs_review=False,
        exercise_type=ExerciseType.COMPOUND,
    )
    days = [
        [programmed_chest],
        [programmed_chest],
        [],
        [],
    ]
    originals = (
        WorkoutDay(
            day_index=1,
            weekday=0,
            title="Day 1",
            focus="full_body",
            exercises=(),
            estimated_duration_minutes=45,
        ),
        WorkoutDay(
            day_index=2,
            weekday=1,
            title="Day 2",
            focus="full_body",
            exercises=(),
            estimated_duration_minutes=45,
        ),
        WorkoutDay(
            day_index=3,
            weekday=3,
            title="Day 3",
            focus="full_body",
            exercises=(),
            estimated_duration_minutes=45,
        ),
        WorkoutDay(
            day_index=4,
            weekday=4,
            title="Day 4",
            focus="full_body",
            exercises=(),
            estimated_duration_minutes=45,
        ),
    )
    targets = {
        MuscleGroup.CHEST: VolumeTarget(
            muscle=MuscleGroup.CHEST,
            target_sets=10,
            minimum_soft=8,
            maximum_soft=12,
            maximum_hard=20,
            fractional_sets=0.0,
            effective_target_sets=10,
            minimum_direct_sets=8,
            minimum_effective_sets=8,
            minimum_coverage_required=True,
            direct_minimum_required=True,
        )
    }

    result = select_repair_candidate(
        days=days,
        originals=originals,
        direct_under={MuscleGroup.CHEST},
        effective_under={MuscleGroup.CHEST},
        candidates=(chest_cand2,),
        request=normalized,
        targets=targets,
        ruleset=RULESET,
        use_hard_maximums=True,
    )
    assert result is not None
    day_idx, programmed, _ = result
    assert programmed.exercise_id == chest_cand2.id
