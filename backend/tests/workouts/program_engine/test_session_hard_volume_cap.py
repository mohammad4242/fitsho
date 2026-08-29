from dataclasses import replace
from uuid import uuid4

import pytest

from app.exercises.enums import ExerciseType, MovementPattern, MuscleGroup, PrescriptionMode
from app.workouts.program_engine.engine import generate_program
from app.workouts.program_engine.enums import TrainingExperience
from app.workouts.program_engine.normalization import normalize_request
from app.workouts.program_engine.rulesets.resistance_training_v1 import RULESET
from app.workouts.program_engine.schemas import (
    ProgramGenerationRequest,
    ProgrammedExercise,
    VolumeTarget,
    WeeklyVolumePlan,
    WorkoutDay,
    WorkoutProgram,
)
from app.workouts.program_engine.validation import validate_program
from app.workouts.program_engine.volume_repair import repair_weekly_volume
from tests.workouts.program_engine.golden_fixtures import full_catalog
from tests.workouts.program_engine.golden_fixtures import request as golden_request


def make_request(
    training_age_months: int,
    experience: TrainingExperience = TrainingExperience.BEGINNER,
) -> ProgramGenerationRequest:
    return golden_request(
        training_experience=experience,
        training_age_months=training_age_months,
        session_duration_minutes=45,
        available_training_days=1,
    )


def make_program(
    req: ProgramGenerationRequest,
    sets_count: int,
    muscle: MuscleGroup = MuscleGroup.CHEST,
) -> WorkoutProgram:
    base_result = generate_program(req, full_catalog(), RULESET)
    assert base_result.program is not None

    exercises: list[ProgrammedExercise] = []
    remaining = sets_count
    idx = 1
    while remaining > 0:
        exercise_sets = min(4, remaining)
        exercises.append(
            ProgrammedExercise(
                exercise_id=uuid4(),
                exercise_name=f"Chest Exercise {idx}",
                order=idx,
                sets=exercise_sets,
                rep_min=8,
                rep_max=12,
                target_rir=2,
                rest_seconds=90,
                estimated_minutes=exercise_sets * 2,
                reason_codes=("SELECTION",),
                primary_muscle=muscle,
                secondary_muscles=(),
                exercise_type=ExerciseType.COMPOUND,
                movement_pattern=MovementPattern.HORIZONTAL_PUSH,
                prescription_mode=PrescriptionMode.REPS,
            )
        )
        remaining -= exercise_sets
        idx += 1

    day = replace(
        base_result.program.weekly_schedule[0],
        exercises=tuple(exercises),
        estimated_duration_minutes=sum(e.estimated_minutes for e in exercises),
    )
    return replace(
        base_result.program,
        weekly_schedule=(day, *base_result.program.weekly_schedule[1:]),
    )


@pytest.mark.parametrize(
    ("training_age", "experience", "valid_sets", "invalid_sets"),
    [
        (0, TrainingExperience.BEGINNER, 12, 13),
        (5, TrainingExperience.BEGINNER, 12, 13),
        (6, TrainingExperience.INTERMEDIATE, 20, 21),
        (24, TrainingExperience.INTERMEDIATE, 20, 21),
        (25, TrainingExperience.ADVANCED, 30, 31),
    ],
)
def test_session_hard_volume_cap_validation_boundaries(
    training_age: int,
    experience: TrainingExperience,
    valid_sets: int,
    invalid_sets: int,
) -> None:
    req = make_request(training_age_months=training_age, experience=experience)

    # Valid program at boundary
    prog_valid = make_program(req, sets_count=valid_sets)
    report_valid = validate_program(prog_valid, req, RULESET)
    assert "PER_SESSION_MUSCLE_VOLUME_EXCEEDED" not in report_valid.errors

    # Invalid program exceeding boundary by 1 set
    prog_invalid = make_program(req, sets_count=invalid_sets)
    report_invalid = validate_program(prog_invalid, req, RULESET)
    assert "PER_SESSION_MUSCLE_VOLUME_EXCEEDED" in report_invalid.errors


def test_intermediate_with_14_sets_not_rejected_by_old_cap() -> None:
    req = make_request(training_age_months=12, experience=TrainingExperience.INTERMEDIATE)
    prog = make_program(req, sets_count=14)
    report = validate_program(prog, req, RULESET)
    assert "PER_SESSION_MUSCLE_VOLUME_EXCEEDED" not in report.errors


def test_advanced_with_22_sets_not_rejected_by_old_cap() -> None:
    req = make_request(training_age_months=36, experience=TrainingExperience.ADVANCED)
    prog = make_program(req, sets_count=22)
    report = validate_program(prog, req, RULESET)
    assert "PER_SESSION_MUSCLE_VOLUME_EXCEEDED" not in report.errors


def test_volume_repair_respects_dynamic_session_cap_for_advanced() -> None:
    req = make_request(training_age_months=30, experience=TrainingExperience.ADVANCED)
    normalized = normalize_request(req, RULESET)

    # 4 exercises of 4 sets = 16 sets direct chest in 1 session
    exercises = tuple(
        ProgrammedExercise(
            exercise_id=uuid4(),
            exercise_name=f"Chest {i}",
            order=i + 1,
            sets=4,
            rep_min=8,
            rep_max=12,
            target_rir=2,
            rest_seconds=90,
            warmup_sets=0,
            estimated_minutes=8,
            reason_codes=("SELECTION",),
            primary_muscle=MuscleGroup.CHEST,
            secondary_muscles=(),
            exercise_type=ExerciseType.COMPOUND,
            movement_pattern=MovementPattern.HORIZONTAL_PUSH,
            prescription_mode=PrescriptionMode.REPS,
        )
        for i in range(4)
    )
    day = WorkoutDay(
        day_index=1,
        weekday=0,
        title="Day 1",
        focus="chest",
        estimated_duration_minutes=32,
        exercises=exercises,
    )
    volume_plan = WeeklyVolumePlan(
        targets=(
            VolumeTarget(
                muscle=MuscleGroup.CHEST,
                minimum_soft=10,
                target_sets=16,
                maximum_soft=20,
                maximum_hard=25,
                fractional_sets=0.0,
                effective_target_sets=16,
                minimum_direct_sets=16,
                minimum_effective_sets=16,
            ),
        ),
        reason_codes=(),
    )
    repaired_days, _ = repair_weekly_volume(
        (day,),
        normalized,
        volume_plan,
        RULESET,
    )
    chest_sets = sum(
        item.sets for item in repaired_days[0].exercises if item.primary_muscle is MuscleGroup.CHEST
    )
    # Advanced cap is 30, so 16 sets are preserved (not clamped to 12)
    assert chest_sets == 16
