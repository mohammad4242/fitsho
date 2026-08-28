from types import SimpleNamespace

from app.exercises.enums import ExerciseLabel, ExerciseType
from app.workouts.program_engine.duration_capacity import build_session_capacity
from app.workouts.program_engine.duration_policy import (
    calculate_core_addon_minutes,
    calculate_main_training_minutes,
    calculate_main_training_minutes_from_exercises,
    get_session_duration_policy,
)
from app.workouts.program_engine.enums import Goal
from app.workouts.program_engine.normalization import normalize_request
from app.workouts.program_engine.prescription import prescribe_sessions
from app.workouts.program_engine.rulesets.resistance_training_v1 import RULESET
from app.workouts.program_engine.schemas import SessionDraft, VolumeTarget, WeeklyVolumePlan
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
