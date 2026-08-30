from dataclasses import replace
from uuid import uuid4

import pytest

from app.exercises.enums import ExerciseType, MovementPattern, MuscleGroup
from app.workouts.program_engine.duration_policy import get_session_exercise_count_policy
from app.workouts.program_engine.eligibility import filter_eligible_exercises
from app.workouts.program_engine.engine import generate_program
from app.workouts.program_engine.normalization import normalize_request
from app.workouts.program_engine.rulesets.resistance_training_v1 import RULESET
from app.workouts.program_engine.schemas import (
    TemplateReference,
    TemplateReferenceDay,
    TemplateReferenceSlot,
    WorkoutDay,
)
from app.workouts.program_engine.session_builder import build_sessions
from app.workouts.program_engine.session_duration import repair_session_durations
from app.workouts.program_engine.split_selector import select_split
from app.workouts.program_engine.supplemental_policy import (
    is_main_resistance_exercise,
    main_exercise_count,
)
from app.workouts.program_engine.template_sessions import (
    TemplateConstructionError,
    build_template_sessions,
)
from app.workouts.program_engine.volume_planner import plan_weekly_volume
from tests.workouts.program_engine.golden_fixtures import exercise, full_catalog, request


def test_dynamic_builder_caps_short_session_main_exercises_at_canonical_ceiling() -> None:
    source = request(session_duration_minutes=30)
    normalized = normalize_request(source, RULESET)
    eligible = filter_eligible_exercises(normalized, full_catalog()).eligible
    split = select_split(normalized, RULESET)
    volume = plan_weekly_volume(normalized, split, RULESET)

    sessions = build_sessions(normalized, split, volume, eligible, RULESET)

    policy = get_session_exercise_count_policy(30, RULESET)
    assert main_exercise_count(sessions[0].exercises) <= policy.maximum_main_exercises


def test_duration_repair_keeps_core_and_adds_fifth_main_when_safe_capacity_exists() -> None:
    source = request(session_duration_minutes=45, available_training_days=1)
    normalized = normalize_request(source, RULESET)
    baseline_result = generate_program(source, full_catalog(), RULESET, reference_templates=())
    assert baseline_result.program is not None, baseline_result.errors
    baseline = baseline_result.program.weekly_schedule[0]
    main = tuple(item for item in baseline.exercises if is_main_resistance_exercise(item))[:4]
    core = tuple(
        replace(
            main[0],
            exercise_id=uuid4(),
            exercise_name=f"core-{index}",
            exercise_type=ExerciseType.CORE,
            primary_muscle=MuscleGroup.CHEST,
            estimated_minutes=1,
            counts_toward_volume=False,
            sets=1,
            reason_codes=("OPTIONAL_SUPPLEMENTAL_WORK",),
        )
        for index in range(6)
    )
    day = WorkoutDay(
        day_index=1,
        weekday=0,
        title="Repair",
        focus="upper",
        estimated_duration_minutes=5 + sum(item.estimated_minutes for item in (*main, *core)),
        exercises=(*main, *core),
    )
    candidate = exercise(
        "repair-biceps",
        MovementPattern.ELBOW_FLEXION,
        MuscleGroup.BICEPS,
        exercise_type=ExerciseType.ISOLATION,
    )

    result = repair_session_durations((day,), normalized, (candidate,), RULESET)

    assert main_exercise_count(result.days[0].exercises) == 5
    assert {item.exercise_id for item in core}.issubset(
        {item.exercise_id for item in result.days[0].exercises}
    )


def test_duration_repair_trims_in_range_short_session_main_overflow_without_set_changes() -> None:
    source = request(session_duration_minutes=60, available_training_days=1)
    baseline_result = generate_program(source, full_catalog(), RULESET, reference_templates=())
    assert baseline_result.program is not None, baseline_result.errors
    baseline_main = tuple(
        item
        for item in baseline_result.program.weekly_schedule[0].exercises
        if is_main_resistance_exercise(item)
    )[:5]
    main = tuple(
        replace(item, estimated_minutes=6, reason_codes=("SESSION_SIZE_ACCESSORY",))
        for item in baseline_main
    )
    core = replace(
        main[0],
        exercise_id=uuid4(),
        exercise_name="Core",
        exercise_type=ExerciseType.CORE,
        primary_muscle=MuscleGroup.CHEST,
        estimated_minutes=5,
        reason_codes=("OPTIONAL_SUPPLEMENTAL_WORK",),
    )
    day = WorkoutDay(
        day_index=1,
        weekday=0,
        title="Short overflow",
        focus="full_body",
        estimated_duration_minutes=5 + sum(item.estimated_minutes for item in (*main, core)),
        exercises=(*main, core),
    )
    normalized = normalize_request(request(session_duration_minutes=30), RULESET)

    result = repair_session_durations((day,), normalized, (), RULESET)

    repaired = result.days[0]
    assert main_exercise_count(repaired.exercises) == 4
    assert core.exercise_id in {item.exercise_id for item in repaired.exercises}
    original_by_id = {item.exercise_id: item for item in main}
    for item in repaired.exercises:
        if is_main_resistance_exercise(item):
            original = original_by_id[item.exercise_id]
            assert (item.sets, item.rest_seconds) == (original.sets, original.rest_seconds)


def test_short_template_with_five_required_main_slots_fails_count_capacity() -> None:
    source = request(session_duration_minutes=30, available_training_days=1)
    normalized = normalize_request(source, RULESET)
    catalog = tuple(full_catalog())
    slots = tuple(
        TemplateReferenceSlot(
            exercise_id=item.id,
            exercise_slug_hint=item.name,
            target_muscles=(item.primary_muscle,),
            movement_pattern=item.movement_pattern,
            intensity_method="standard",
            adaptation_priority="core",
            superset_group=None,
            superset_exercise_id=None,
            superset_exercise_slug_hint=None,
            sets=3,
            rep_min=8,
            rep_max=12,
            target_rir=2,
            rest_seconds=60,
        )
        for item in catalog
        if is_main_resistance_exercise(item)
    )[:5]
    template = TemplateReference(
        slug="short-five-required-main",
        days_per_week=1,
        supported_levels=(normalized.source.training_experience.value,),
        focus_tags=("full_body",),
        intensity_methods=("standard",),
        days=(
            TemplateReferenceDay(
                1,
                "Short",
                tuple(slot.target_muscles[0] for slot in slots),
                slots,
            ),
        ),
    )

    with pytest.raises(TemplateConstructionError) as error:
        build_template_sessions(normalized, template, catalog, RULESET)

    assert "TEMPLATE_SESSION_EXERCISE_COUNT_UNSATISFIED" in error.value.reason_codes


def test_template_retains_core_candidate_with_non_core_slot_metadata() -> None:
    source = request(session_duration_minutes=30, available_training_days=1)
    normalized = normalize_request(source, RULESET)
    main = tuple(item for item in full_catalog() if is_main_resistance_exercise(item))[:4]
    core = replace(
        main[0],
        id=uuid4(),
        name="Chest Core",
        exercise_type=ExerciseType.CORE,
        primary_muscle=MuscleGroup.CHEST,
        movement_pattern=MovementPattern.SHOULDER_ABDUCTION,
    )
    catalog = (*main, core)
    slots = tuple(
        TemplateReferenceSlot(
            exercise_id=item.id,
            exercise_slug_hint=item.name,
            target_muscles=(item.primary_muscle,),
            movement_pattern=item.movement_pattern,
            intensity_method="standard",
            adaptation_priority="core",
            superset_group=None,
            superset_exercise_id=None,
            superset_exercise_slug_hint=None,
            sets=3,
            rep_min=8,
            rep_max=12,
            target_rir=2,
            rest_seconds=60,
        )
        for item in main
    ) + (
        TemplateReferenceSlot(
            exercise_id=core.id,
            exercise_slug_hint=core.name,
            target_muscles=(MuscleGroup.CHEST,),
            movement_pattern=MovementPattern.SHOULDER_ABDUCTION,
            intensity_method="standard",
            adaptation_priority="core",
            superset_group=None,
            superset_exercise_id=None,
            superset_exercise_slug_hint=None,
            sets=1,
            rep_min=8,
            rep_max=12,
            target_rir=2,
            rest_seconds=30,
        ),
    )
    template = TemplateReference(
        slug="short-core-candidate-metadata",
        days_per_week=1,
        supported_levels=(normalized.source.training_experience.value,),
        focus_tags=("full_body",),
        intensity_methods=("standard",),
        days=(TemplateReferenceDay(1, "Short", (MuscleGroup.CHEST,), slots),),
    )

    build = build_template_sessions(normalized, template, catalog, RULESET)

    exercises = build.drafts[0].exercises
    assert main_exercise_count(exercises) == 4
    assert core.id in {item.id for item in exercises}
