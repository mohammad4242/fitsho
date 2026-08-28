from dataclasses import replace
from types import SimpleNamespace

import pytest

from app.exercises.enums import ExerciseLabel, ExerciseType
from app.workouts.program_engine.coach_quality import build_coach_quality_metrics
from app.workouts.program_engine.duration_capacity import build_session_capacity
from app.workouts.program_engine.duration_policy import (
    calculate_core_addon_minutes,
    calculate_main_training_minutes,
    calculate_main_training_minutes_from_exercises,
    get_session_duration_policy,
)
from app.workouts.program_engine.engine import generate_program
from app.workouts.program_engine.enums import Goal
from app.workouts.program_engine.final_gate import evaluate_final_program
from app.workouts.program_engine.normalization import normalize_request
from app.workouts.program_engine.prescription import prescribe_sessions
from app.workouts.program_engine.rulesets.resistance_training_v1 import RULESET
from app.workouts.program_engine.schemas import (
    SessionDraft,
    ValidationReport,
    VolumeTarget,
    WeeklyVolumePlan,
)
from app.workouts.program_engine.session_duration import (
    SessionDurationRepairEvidence,
    repair_session_durations,
)
from app.workouts.program_engine.validation import validate_program
from tests.workouts.program_engine.golden_fixtures import full_catalog, request


def _item(exercise_type: ExerciseType | str, minutes: int, *, cardio: bool = False):
    return SimpleNamespace(
        exercise_type=exercise_type,
        estimated_minutes=minutes,
        labels=frozenset({ExerciseLabel.CARDIO}) if cardio else frozenset(),
    )


def test_main_training_excludes_anatomical_core_and_cardio_only() -> None:
    exercises = (
        _item(ExerciseType.COMPOUND, 35),
        _item(ExerciseType.ISOLATION, 25),
        _item(ExerciseType.CORE, 8),
        _item("cardio", 10, cardio=True),
    )

    assert calculate_main_training_minutes_from_exercises(exercises) == 60
    assert calculate_core_addon_minutes(exercises) == 8


def test_day_main_training_is_independent_of_warmup_core_and_cardio_addons() -> None:
    day = SimpleNamespace(
        exercises=(
            _item(ExerciseType.COMPOUND, 35),
            _item(ExerciseType.ISOLATION, 25),
            _item(ExerciseType.CORE, 8),
        ),
        cardio=SimpleNamespace(duration_minutes=10),
        estimated_duration_minutes=83,
    )

    assert calculate_main_training_minutes(day) == 60
    assert calculate_core_addon_minutes(day.exercises) == 8


def test_duration_policy_contains_main_training_bounds() -> None:
    policy = get_session_duration_policy(60)

    assert (policy.minimum_minutes, policy.maximum_minutes) == (50, 70)
    assert [policy.contains(value) for value in (49, 50, 60, 70, 71)] == [
        False,
        True,
        True,
        True,
        False,
    ]


@pytest.mark.parametrize(
    ("duration", "goal", "experience"),
    (
        (30, "fat_loss", "beginner"),
        (45, "muscle_gain", "beginner"),
        (60, "hypertrophy", "intermediate"),
        (75, "strength", "advanced"),
        (90, "fat_loss", "intermediate"),
        (120, "strength", "advanced"),
    ),
)
def test_official_duration_matrix_never_returns_an_invalid_success(
    duration: int,
    goal: str,
    experience: str,
) -> None:
    result = generate_program(
        request(
            session_duration_minutes=duration,
            available_training_days=1,
            primary_goal=goal,
            training_experience=experience,
            training_age_months=30,
        ),
        full_catalog(),
        RULESET,
        reference_templates=(),
    )

    if result.program is None:
        assert "SESSION_DURATION_UNDER_TARGET" in result.errors
        return
    policy = get_session_duration_policy(duration)
    assert all(
        policy.contains(calculate_main_training_minutes(day))
        for day in result.program.weekly_schedule
    )


def test_anatomical_core_does_not_create_or_reduce_main_capacity() -> None:
    normalized = normalize_request(
        request(
            primary_goal=Goal.HYPERTROPHY,
            session_duration_minutes=60,
            available_training_days=3,
            training_experience="intermediate",
            training_age_months=30,
        ),
        RULESET,
    )
    core = next(item for item in full_catalog() if item.exercise_type is ExerciseType.CORE)

    without_core = build_session_capacity(normalized, (), RULESET)
    with_core = build_session_capacity(normalized, (core,), RULESET)

    assert (
        with_core.expected_exercise_count_capacity
        == without_core.expected_exercise_count_capacity
    )
    assert with_core.expected_working_set_capacity == without_core.expected_working_set_capacity
    assert with_core.representative_exercise_minutes == without_core.representative_exercise_minutes


def test_prescription_budget_counts_main_exercises_not_anatomical_core() -> None:
    normalized = normalize_request(
        request(
            primary_goal=Goal.HYPERTROPHY,
            session_duration_minutes=60,
            available_training_days=1,
            training_experience="intermediate",
            training_age_months=30,
        ),
        RULESET,
    )
    main = tuple(
        item
        for item in full_catalog()
        if item.exercise_type is not ExerciseType.CORE
    )[:5]
    core = next(item for item in full_catalog() if item.exercise_type is ExerciseType.CORE)
    volume = WeeklyVolumePlan(
        targets=tuple(
            VolumeTarget(
                muscle=item.primary_muscle,
                minimum_soft=8,
                target_sets=16,
                maximum_soft=20,
                maximum_hard=24,
                fractional_sets=8,
                effective_target_sets=16,
                minimum_direct_sets=8,
            )
            for item in main
        ),
        reason_codes=(),
    )

    def draft(exercises):
        return SessionDraft(
            day_index=1,
            weekday=0,
            focus="template_reference_1",
            exercises=list(exercises),
            selection_reasons={item.id: () for item in exercises},
            substitutions={item.id: () for item in exercises},
        )

    without_core = prescribe_sessions(normalized, (draft(main),), volume, RULESET)[0]
    with_core = prescribe_sessions(normalized, (draft((*main, core)),), volume, RULESET)[0]

    assert tuple(item.sets for item in with_core.exercises[:-1]) == tuple(
        item.sets for item in without_core.exercises
    )
    assert with_core.exercises[-1].exercise_type is ExerciseType.CORE
    assert with_core.exercises[-1].estimated_minutes > 0


def _generated_program():
    result = generate_program(
        request(session_duration_minutes=60, available_training_days=1),
        full_catalog(),
        RULESET,
    )
    assert result.program is not None, result.errors
    return result.program


def _duration_day(day, main_minutes: int, core_minutes: int = 0):
    main = [item for item in day.exercises if item.exercise_type is not ExerciseType.CORE]
    assert main
    updated = [replace(item, estimated_minutes=0) for item in main]
    updated[0] = replace(updated[0], estimated_minutes=main_minutes)
    if core_minutes:
        core = next(
            (item for item in day.exercises if item.exercise_type is ExerciseType.CORE),
            None,
        )
        if core is None:
            core = replace(updated.pop(), exercise_type=ExerciseType.CORE)
        exercises = (*updated, replace(core, estimated_minutes=core_minutes))
    else:
        exercises = tuple(updated)
    cardio_minutes = day.cardio.duration_minutes if day.cardio else 0
    return replace(
        day,
        exercises=exercises,
        estimated_duration_minutes=(
            RULESET.general_warmup_minutes + main_minutes + core_minutes + cardio_minutes
        ),
    )


def _with_duration_trace(program, day, reason_codes: tuple[str, ...]):
    evidence = SessionDurationRepairEvidence.from_day(day, reason_codes).as_trace()
    trace = tuple(
        {
            **entry,
            "reason_codes": reason_codes,
            "per_session_evidence": (evidence,),
        }
        if entry.get("stage") == "session_duration"
        else entry
        for entry in program.decision_trace
    )
    return replace(program, weekly_schedule=(day,), decision_trace=trace)


def test_core_and_cardio_are_additive_to_a_valid_main_training_duration() -> None:
    program = _generated_program()
    day = _duration_day(program.weekly_schedule[0], main_minutes=60, core_minutes=8)

    assert calculate_main_training_minutes(day) == 60
    assert calculate_core_addon_minutes(day) == 8
    assert day.estimated_duration_minutes == 83
    report = validate_program(
        replace(program, weekly_schedule=(day,)),
        request(session_duration_minutes=60, available_training_days=1),
        RULESET,
    )

    assert not {
        "SESSION_DURATION_EXCEEDED",
        "SESSION_DURATION_OVER_TARGET",
        "SESSION_DURATION_UNDER_TARGET",
    }.intersection(report.errors)


def test_underfilled_main_training_is_invalid_even_when_addons_make_total_long() -> None:
    program = _generated_program()
    day = _duration_day(program.weekly_schedule[0], main_minutes=47, core_minutes=10)
    mutated = replace(program, weekly_schedule=(day,))

    report = validate_program(
        mutated,
        request(session_duration_minutes=60, available_training_days=1),
        RULESET,
    )

    assert "SESSION_DURATION_UNDER_TARGET" in report.errors
    assert "SESSION_DURATION_TARGET_UNSATISFIED" in report.errors


def test_underfill_repair_adds_main_work_without_using_core_or_rest() -> None:
    program = _generated_program()
    day = _duration_day(program.weekly_schedule[0], main_minutes=47, core_minutes=10)
    normalized = normalize_request(
        request(session_duration_minutes=60, available_training_days=1),
        RULESET,
    )
    original_main = calculate_main_training_minutes(day)
    original_core = calculate_core_addon_minutes(day)
    original_rests = tuple(item.rest_seconds for item in day.exercises)

    result = repair_session_durations(
        (day,),
        normalized,
        full_catalog(),
        RULESET,
    )
    repaired = result.days[0]

    assert original_main == 47
    assert original_core == 10
    assert calculate_main_training_minutes(repaired) >= 50
    assert calculate_core_addon_minutes(repaired) == original_core
    assert tuple(item.rest_seconds for item in repaired.exercises) == original_rests


def test_template_core_reason_cannot_excuse_main_training_overfill() -> None:
    program = _generated_program()
    day = _duration_day(program.weekly_schedule[0], main_minutes=71)
    first = day.exercises[0]
    day = replace(
        day,
        exercises=(
            replace(first, reason_codes=("TEMPLATE_ADAPTATION_PRIORITY:core",)),
            *day.exercises[1:],
        ),
    )
    mutated = _with_duration_trace(
        program,
        day,
        ("SESSION_DURATION_EXTENDED_TO_PRESERVE_CORE",),
    )

    report = validate_program(
        mutated,
        request(session_duration_minutes=60, available_training_days=1),
        RULESET,
    )

    assert "SESSION_DURATION_OVER_TARGET" in report.errors


def test_coach_duration_fit_requires_both_main_training_bounds() -> None:
    program = _generated_program()
    day = _duration_day(program.weekly_schedule[0], main_minutes=47, core_minutes=10)
    mutated = replace(program, weekly_schedule=(day,))
    report = ValidationReport((), (), mutated.assumptions, mutated.aggregate_metrics, ())

    metrics = build_coach_quality_metrics(
        mutated,
        request(session_duration_minutes=60, available_training_days=1),
        report,
        RULESET,
    )

    assert metrics["duration_fit"]["percentage"] < 100


def test_final_gate_rejects_main_training_outside_bounds_without_duration_codes() -> None:
    program = _generated_program()
    day = _duration_day(program.weekly_schedule[0], main_minutes=71)
    mutated = replace(program, weekly_schedule=(day,))
    report = ValidationReport((), (), mutated.assumptions, mutated.aggregate_metrics, ())

    decision = evaluate_final_program(
        mutated,
        request(session_duration_minutes=60, available_training_days=1),
        report,
        RULESET,
    )

    assert not decision.is_accepted
