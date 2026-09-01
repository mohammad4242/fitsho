from dataclasses import replace
from uuid import NAMESPACE_URL, uuid5

from app.exercises.enums import Equipment, ExerciseType, MovementPattern, MuscleGroup
from app.workouts.program_engine import engine
from app.workouts.program_engine.engine import generate_program
from app.workouts.program_engine.enums import SplitType
from app.workouts.program_engine.normalization import normalize_request
from app.workouts.program_engine.rulesets.resistance_training_v1 import RULESET
from app.workouts.program_engine.schemas import ProgrammedExercise, WorkoutDay
from app.workouts.program_engine.session_duration import repair_session_durations
from app.workouts.program_engine.session_structure import finalize_session_structure
from app.workouts.program_engine.split_selector import rank_split_candidates
from app.workouts.program_engine.template_sessions import build_template_sessions
from app.workouts.program_engine.validation import validate_program
from tests.workouts.program_engine.golden_fixtures import exercise, full_catalog, request
from tests.workouts.program_engine.test_template_structure_propagation import (
    _chest_triceps_reference,
)


def _programmed(
    name: str,
    muscle: MuscleGroup,
    pattern: MovementPattern,
    *,
    secondary: tuple[MuscleGroup, ...] = (),
    exercise_type: ExerciseType = ExerciseType.COMPOUND,
    order: int = 1,
    reasons: tuple[str, ...] = ("TEST",),
    estimated_minutes: int = 6,
) -> ProgrammedExercise:
    return ProgrammedExercise(
        exercise_id=uuid5(NAMESPACE_URL, f"https://fitsho.test/coherence/{name}"),
        exercise_name=name,
        order=order,
        sets=3,
        rep_min=8,
        rep_max=12,
        target_rir=2,
        rest_seconds=75,
        estimated_minutes=estimated_minutes,
        reason_codes=reasons,
        movement_pattern=pattern,
        primary_muscle=muscle,
        secondary_muscles=secondary,
        equipment=frozenset({Equipment.BODYWEIGHT}),
        exercise_type=exercise_type,
    )


def _day(
    focus: str,
    exercises: tuple[ProgrammedExercise, ...],
    *,
    template_target_muscles: tuple[MuscleGroup, ...] = (),
    template_structure_focus: str = "full_body",
) -> WorkoutDay:
    return WorkoutDay(
        day_index=1,
        weekday=0,
        title="Coherence",
        focus=focus,
        estimated_duration_minutes=5 + sum(item.estimated_minutes for item in exercises),
        exercises=exercises,
        template_target_muscles=template_target_muscles,
        template_structure_focus=template_structure_focus,
    )


def test_template_chest_triceps_redundancy_replacement_never_adds_shoulder() -> None:
    source = normalize_request(
        request(
            training_experience="intermediate",
            available_training_days=1,
            session_duration_minutes=45,
            primary_goal="hypertrophy",
        ),
        RULESET,
    )
    build = build_template_sessions(
        source,
        _chest_triceps_reference(),
        full_catalog(),
        RULESET,
    )
    day = build.drafts[0]
    assert set(day.template_target_muscles) == {MuscleGroup.CHEST, MuscleGroup.TRICEPS}
    assert {
        item.primary_muscle for item in day.exercises if item.primary_muscle is not None
    } <= {MuscleGroup.CHEST, MuscleGroup.TRICEPS}


def test_validation_rejects_template_back_biceps_direct_shoulder_work() -> None:
    day = _day(
        "template_reference_1",
        (
            _programmed("Row", MuscleGroup.BACK, MovementPattern.HORIZONTAL_PULL),
            _programmed(
                "Curl", MuscleGroup.BICEPS, MovementPattern.ELBOW_FLEXION, order=2,
                exercise_type=ExerciseType.ISOLATION,
            ),
            _programmed("Press", MuscleGroup.SHOULDERS, MovementPattern.VERTICAL_PUSH, order=3),
        ),
        template_target_muscles=(MuscleGroup.BACK, MuscleGroup.BICEPS),
        template_structure_focus="back_biceps",
    )
    finalized = finalize_session_structure(
        (day,), normalize_request(request(), RULESET), RULESET
    )[0]
    baseline = generate_program(
        request(available_training_days=1),
        full_catalog(),
        RULESET,
        reference_templates=(),
    )
    assert baseline.program is not None
    report = validate_program(
        replace(baseline.program, weekly_schedule=(finalized,)),
        request(available_training_days=1),
        RULESET,
    )
    assert "SESSION_DIRECT_MUSCLE_OUTSIDE_FOCUS_REJECTED" in report.errors
    assert "SESSION_DIRECT_MUSCLE_OUTSIDE_FOCUS_REJECTED:shoulders" in report.errors


def test_dynamic_specialized_builders_keep_chest_triceps_and_back_biceps_exact() -> None:
    result = generate_program(
        request(
            training_experience="intermediate",
            training_age_months=30,
            available_training_days=4,
            primary_goal="hypertrophy",
        ),
        full_catalog(),
        RULESET,
        reference_templates=(),
    )
    assert result.program is not None, result.errors
    expected = {
        "chest_triceps": {MuscleGroup.CHEST, MuscleGroup.TRICEPS},
        "back_biceps": {MuscleGroup.BACK, MuscleGroup.BICEPS},
    }
    for day in result.program.weekly_schedule:
        if day.focus in expected:
            direct = {item.primary_muscle for item in day.exercises if item.primary_muscle}
            assert direct <= expected[day.focus]


def test_duration_underfill_adds_only_allowed_direct_muscles_and_prefers_primary_block() -> None:
    source = normalize_request(request(session_duration_minutes=45), RULESET)
    chest = _programmed("Bench", MuscleGroup.CHEST, MovementPattern.HORIZONTAL_PUSH)
    triceps = _programmed(
        "Extension", MuscleGroup.TRICEPS, MovementPattern.ELBOW_EXTENSION,
        exercise_type=ExerciseType.ISOLATION, order=2,
    )
    day = _day("chest_triceps", (chest, triceps))
    candidates = (
        exercise("shoulder-fill", MovementPattern.VERTICAL_PUSH, MuscleGroup.SHOULDERS),
        exercise("chest-fill", MovementPattern.HORIZONTAL_PUSH, MuscleGroup.CHEST),
    )
    result = repair_session_durations((day,), source, candidates, RULESET)
    direct = {item.primary_muscle for item in result.days[0].exercises if item.primary_muscle}
    assert direct <= {MuscleGroup.CHEST, MuscleGroup.TRICEPS}
    assert sum(
        item.sets
        for item in result.days[0].exercises
        if item.primary_muscle is MuscleGroup.CHEST
    ) >= sum(item.sets for item in (chest,))


def test_lower_duration_hierarchy_places_major_muscles_before_calves() -> None:
    calves = _programmed(
        "Calf Raise", MuscleGroup.CALVES, MovementPattern.CALF_RAISE,
        exercise_type=ExerciseType.ISOLATION,
    )
    quads = _programmed("Squat", MuscleGroup.QUADRICEPS, MovementPattern.SQUAT, order=2)
    hamstrings = _programmed("Hinge", MuscleGroup.HAMSTRINGS, MovementPattern.HIP_HINGE, order=3)
    finalized = finalize_session_structure(
        (_day("lower", (calves, quads, hamstrings)),),
        normalize_request(request(), RULESET), RULESET
    )[0]
    calf_index = next(
        i
        for i, item in enumerate(finalized.exercises)
        if item.primary_muscle is MuscleGroup.CALVES
    )
    assert all(
        i < calf_index
        for i, item in enumerate(finalized.exercises)
        if item.primary_muscle in {MuscleGroup.QUADRICEPS, MuscleGroup.HAMSTRINGS}
    )


def test_volume_repair_deepens_existing_intended_day_before_second_exposure(monkeypatch) -> None:
    source = request(
        training_experience="intermediate",
        training_age_months=30,
        available_training_days=4,
        primary_goal="hypertrophy",
        priority_muscles=[MuscleGroup.CHEST],
    )
    body_part_split = next(
        split
        for split in rank_split_candidates(normalize_request(source, RULESET), RULESET)
        if split.split_type is SplitType.BODY_PART_ROTATION
    )
    monkeypatch.setattr(engine, "rank_split_candidates", lambda *args, **kwargs: (body_part_split,))
    result = generate_program(
        source,
        full_catalog(),
        RULESET,
        reference_templates=(),
    )
    assert result.program is not None, result.errors
    chest_days = [
        day for day in result.program.weekly_schedule
        if any(item.primary_muscle is MuscleGroup.CHEST for item in day.exercises)
    ]
    assert len(chest_days) == 1


def test_shoulder_priority_may_use_shoulder_push_but_never_back_or_leg(monkeypatch) -> None:
    source = request(
        training_experience="intermediate",
        training_age_months=30,
        available_training_days=4,
        primary_goal="hypertrophy",
        priority_muscles=[MuscleGroup.SHOULDERS],
    )
    body_part_split = next(
        split
        for split in rank_split_candidates(normalize_request(source, RULESET), RULESET)
        if split.split_type is SplitType.BODY_PART_ROTATION
    )
    monkeypatch.setattr(engine, "rank_split_candidates", lambda *args, **kwargs: (body_part_split,))
    result = generate_program(
        source,
        full_catalog(),
        RULESET,
        reference_templates=(),
    )
    assert result.program is not None, result.errors
    shoulder_day = next(
        day for day in result.program.weekly_schedule if day.focus == "shoulders_traps"
    )
    direct = {item.primary_muscle for item in shoulder_day.exercises if item.primary_muscle}
    assert direct <= {MuscleGroup.SHOULDERS, MuscleGroup.TRAPS}


def test_bench_secondary_shoulder_recruitment_is_not_an_illegal_direct_group() -> None:
    bench = _programmed(
        "Bench", MuscleGroup.CHEST, MovementPattern.HORIZONTAL_PUSH,
        secondary=(MuscleGroup.SHOULDERS, MuscleGroup.TRICEPS),
    )
    day = _day("chest_triceps", (bench,))
    finalized = finalize_session_structure(
        (day,), normalize_request(request(), RULESET), RULESET
    )[0]
    baseline = generate_program(
        request(available_training_days=1),
        full_catalog(),
        RULESET,
        reference_templates=(),
    )
    assert baseline.program is not None
    report = validate_program(
        replace(
            baseline.program,
            weekly_schedule=(finalized,),
        ),
        request(available_training_days=1),
        RULESET,
    )
    assert "SESSION_DIRECT_MUSCLE_OUTSIDE_FOCUS_REJECTED" not in report.errors
    assert "SESSION_DIRECT_MUSCLE_OUTSIDE_FOCUS_REJECTED:shoulders" not in report.errors
