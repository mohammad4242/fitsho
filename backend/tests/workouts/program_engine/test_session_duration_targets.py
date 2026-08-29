from dataclasses import replace

import pytest

from app.exercises.enums import ExerciseType, MovementPattern, MuscleGroup
from app.workouts.program_engine.duration_policy import (
    calculate_main_training_minutes,
    get_session_duration_policy,
)
from app.workouts.program_engine.eligibility import filter_eligible_exercises
from app.workouts.program_engine.engine import generate_program
from app.workouts.program_engine.normalization import normalize_request
from app.workouts.program_engine.prescription import estimate_exercise_minutes
from app.workouts.program_engine.rulesets.resistance_training_v1 import RULESET
from app.workouts.program_engine.schemas import (
    ProgrammedExercise,
    VolumeTarget,
    WeeklyVolumePlan,
    WorkoutDay,
)
from app.workouts.program_engine.session_duration import (
    SessionDurationRepairEvidence,
    repair_session_durations,
)
from app.workouts.program_engine.supplemental_policy import main_exercise_count
from app.workouts.program_engine.validation import validate_program
from app.workouts.program_engine.volume_planner import plan_weekly_volume
from tests.workouts.program_engine.golden_fixtures import full_catalog, request


@pytest.mark.parametrize(
    ("requested", "minimum", "maximum"),
    [(30, 20, 40), (45, 35, 55), (60, 50, 70), (75, 65, 85), (90, 80, 100), (120, 110, 130)],
)
def test_session_duration_policy_has_exact_product_bounds(
    requested: int, minimum: int, maximum: int
) -> None:
    policy = get_session_duration_policy(requested)

    assert (policy.minimum_minutes, policy.maximum_minutes) == (minimum, maximum)


def test_general_warmup_is_outside_the_requested_workout_duration() -> None:
    source = request(session_duration_minutes=60, available_training_days=1)
    result = generate_program(source, full_catalog(), RULESET)
    assert result.program is not None, result.errors
    day = result.program.weekly_schedule[0]
    normal_upper_total = source.session_duration_minutes + 10 + RULESET.general_warmup_minutes
    program = replace(
        result.program,
        weekly_schedule=(replace(day, estimated_duration_minutes=normal_upper_total),),
    )

    report = validate_program(program, source, RULESET)

    assert "SESSION_DURATION_EXCEEDED" not in report.errors
    assert "SESSION_DURATION_OVER_TARGET" not in report.errors


def test_high_quality_fifty_two_minute_workout_satisfies_sixty_minute_request() -> None:
    source = request(session_duration_minutes=60, available_training_days=1)
    result = generate_program(source, full_catalog(), RULESET)
    assert result.program is not None, result.errors
    day = result.program.weekly_schedule[0]
    program = replace(
        result.program,
        weekly_schedule=(
            replace(day, estimated_duration_minutes=52 + RULESET.general_warmup_minutes),
        ),
    )

    report = validate_program(program, source, RULESET)

    assert "SESSION_DURATION_UNDER_TARGET" not in report.errors
    assert "SESSION_DURATION_TARGET_UNSATISFIED" not in report.errors


def test_useful_workload_limit_does_not_force_artificial_rest() -> None:
    source = request(
        session_duration_minutes=75,
        available_training_days=3,
        training_experience="beginner",
        training_age_months=3,
        primary_goal="muscle_gain",
        priority_muscles=["chest"],
    )

    result = generate_program(source, full_catalog(), RULESET, reference_templates=())

    if result.program is None:
        assert "SESSION_DURATION_UNDER_TARGET" in result.errors
        return
    assert result.program is not None
    # In Phase 11.9, finishing under budget with sufficient exercises is SATISFIED, not CONSTRAINED
    assert "SESSION_DURATION_TARGET_UNSATISFIED" not in result.program.warnings
    assert "SESSION_DURATION_CONSTRAINED_BY_USEFUL_WORKLOAD" not in result.program.warnings
    assert all(
        "REST_EXTENDED_FOR_SAFE_DURATION_TARGET" not in exercise.reason_codes
        for day in result.program.weekly_schedule
        for exercise in day.exercises
    )


def test_optional_template_work_is_removed_before_core_for_duration() -> None:
    source = request(session_duration_minutes=60, available_training_days=1)
    normalized = normalize_request(source, RULESET)
    test_ruleset = replace(RULESET, minimum_exercises_per_session=2)
    result = generate_program(source, full_catalog(), RULESET)
    assert result.program is not None, result.errors
    day = result.program.weekly_schedule[0]
    base = day.exercises[:3]
    assert len(base) == 3
    exercises = tuple(
        replace(
            item,
            sets=RULESET.minimum_working_sets,
            rest_seconds=RULESET.minimum_rest_seconds,
            estimated_minutes=30,
            reason_codes=(
                "TEMPLATE_ADAPTATION_PRIORITY:optional"
                if index == len(base) - 1
                else "TEMPLATE_ADAPTATION_PRIORITY:core",
            ),
        )
        for index, item in enumerate(base)
    )
    overfilled = replace(
        day,
        focus="template_reference_1",
        exercises=exercises,
        cardio=None,
        estimated_duration_minutes=RULESET.general_warmup_minutes
        + sum(item.estimated_minutes for item in exercises),
    )

    repaired, _ = repair_session_durations((overfilled,), normalized, (), test_ruleset)

    assert exercises[-1].exercise_id not in {item.exercise_id for item in repaired[0].exercises}
    assert {item.exercise_id for item in exercises[:-1]}.issubset(
        {item.exercise_id for item in repaired[0].exercises}
    )


def test_template_core_preservation_cannot_break_main_training_maximum() -> None:
    source = request(session_duration_minutes=60, available_training_days=1)
    normalized = normalize_request(source, RULESET)
    result = generate_program(source, full_catalog(), RULESET)
    assert result.program is not None, result.errors
    day = result.program.weekly_schedule[0]
    base = day.exercises[: RULESET.minimum_exercises_per_session]
    exercises = tuple(
        replace(
            item,
            sets=RULESET.minimum_working_sets,
            rest_seconds=RULESET.minimum_rest_seconds,
            estimated_minutes=15,
            reason_codes=("TEMPLATE_ADAPTATION_PRIORITY:core",),
        )
        for item in base
    )
    overfilled = replace(
        day,
        focus="template_reference_1",
        exercises=exercises,
        cardio=None,
        estimated_duration_minutes=RULESET.general_warmup_minutes
        + sum(item.estimated_minutes for item in exercises),
    )

    repaired, reasons = repair_session_durations((overfilled,), normalized, (), RULESET)

    assert repaired[0].exercises == exercises
    assert repaired[0].estimated_duration_minutes == 80
    assert "SESSION_DURATION_EXTENDED_TO_PRESERVE_CORE" not in reasons
    assert "SESSION_DURATION_TARGET_UNSATISFIED" in reasons


def test_template_core_reason_does_not_excuse_main_training_overfill() -> None:
    source = request(session_duration_minutes=60, available_training_days=1)
    result = generate_program(source, full_catalog(), RULESET)
    assert result.program is not None, result.errors
    original_day = result.program.weekly_schedule[0]
    day = replace(
        original_day,
        exercises=(
            replace(original_day.exercises[0], estimated_minutes=71),
            *original_day.exercises[1:],
        ),
    )
    day = replace(
        day,
        estimated_duration_minutes=(
            RULESET.general_warmup_minutes
            + sum(item.estimated_minutes for item in day.exercises)
            + (day.cardio.duration_minutes if day.cardio else 0)
        ),
    )
    trace = tuple(
        {
            **entry,
            "reason_codes": ("SESSION_DURATION_EXTENDED_TO_PRESERVE_CORE",),
            "per_session_evidence": (
                SessionDurationRepairEvidence.from_day(
                    day,
                    ("SESSION_DURATION_EXTENDED_TO_PRESERVE_CORE",),
                ).as_trace(),
            ),
        }
        if entry.get("stage") == "session_duration"
        else entry
        for entry in result.program.decision_trace
    )
    program = replace(result.program, weekly_schedule=(day,), decision_trace=trace)

    report = validate_program(program, source, RULESET)

    assert "SESSION_DURATION_EXTENDED_TO_PRESERVE_CORE" not in report.warnings
    assert "SESSION_DURATION_EXCEEDED" in report.errors


def test_main_training_overfill_is_invalid_regardless_of_template_reason() -> None:
    source = request(session_duration_minutes=60, available_training_days=1)
    result = generate_program(source, full_catalog(), RULESET)
    assert result.program is not None, result.errors
    original_day = result.program.weekly_schedule[0]
    day = replace(
        original_day,
        exercises=(
            replace(original_day.exercises[0], estimated_minutes=86),
            *original_day.exercises[1:],
        ),
    )
    day = replace(
        day,
        estimated_duration_minutes=(
            RULESET.general_warmup_minutes
            + sum(item.estimated_minutes for item in day.exercises)
            + (day.cardio.duration_minutes if day.cardio else 0)
        ),
    )
    trace = result.program.decision_trace + (
        {
            "stage": "session_duration",
            "reason_codes": ("SESSION_DURATION_EXTENDED_TO_PRESERVE_CORE",),
        },
    )
    program = replace(result.program, weekly_schedule=(day,), decision_trace=trace)

    report = validate_program(program, source, RULESET)

    assert "SESSION_DURATION_EXCEEDED" in report.errors


@pytest.mark.parametrize("requested", [30, 45, 60, 75, 90])
def test_generate_program_keeps_every_session_inside_duration_target(requested: int) -> None:
    source = request(session_duration_minutes=requested, available_training_days=1)

    result = generate_program(source, full_catalog(), RULESET)

    if result.program is None:
        assert "SESSION_DURATION_UNDER_TARGET" in result.errors
        return
    assert result.is_success, result.errors
    policy = get_session_duration_policy(requested)
    assert all(
        policy.contains(calculate_main_training_minutes(day))
        for day in result.program.weekly_schedule
    )


def test_advanced_strength_program_classifies_a_hard_constrained_120_minute_session() -> None:
    source = request(
        session_duration_minutes=120,
        available_training_days=1,
        primary_goal="strength",
        training_experience="advanced",
        training_age_months=72,
    )

    result = generate_program(source, full_catalog(), RULESET)

    if result.program is None:
        assert "SESSION_DURATION_UNDER_TARGET" in result.errors
        return
    assert result.is_success, result.errors
    policy = get_session_duration_policy(120)
    assert policy.contains(calculate_main_training_minutes(result.program.weekly_schedule[0]))


def test_underfilled_session_is_repaired_with_real_estimates() -> None:
    source = request(session_duration_minutes=90, available_training_days=1)
    normalized = normalize_request(source, RULESET)
    eligibility = filter_eligible_exercises(normalized, full_catalog())
    result = generate_program(source, full_catalog(), RULESET)

    if result.program is None:
        assert "SESSION_DURATION_UNDER_TARGET" in result.errors
        return
    original = result.program.weekly_schedule[0]
    reduced_exercises = tuple(
        replace(
            item,
            sets=RULESET.minimum_working_sets,
            estimated_minutes=estimate_exercise_minutes(
                RULESET.minimum_working_sets,
                item.rest_seconds,
                item.warmup_sets,
                RULESET,
            ),
        )
        for item in original.exercises
    )
    cardio_mins = original.cardio.duration_minutes if original.cardio else 0
    underfilled = replace(
        original,
        exercises=reduced_exercises,
        estimated_duration_minutes=RULESET.general_warmup_minutes
        + sum(item.estimated_minutes for item in reduced_exercises)
        + cardio_mins,
    )
    assert (
        underfilled.estimated_duration_minutes < 80 + RULESET.general_warmup_minutes + cardio_mins
    )

    repaired, reasons = repair_session_durations(
        (underfilled,),
        normalized,
        eligibility.eligible,
        RULESET,
    )

    assert get_session_duration_policy(90).contains(calculate_main_training_minutes(repaired[0]))
    assert "SESSION_DURATION_TARGET_SATISFIED" in reasons


def test_short_session_without_capacity_uses_effective_exercise_floor() -> None:
    source = request(session_duration_minutes=30, available_training_days=1)
    normalized = normalize_request(source, RULESET)
    result = generate_program(source, full_catalog(), RULESET)

    assert result.program is not None, result.errors
    day = result.program.weekly_schedule[0]
    underfilled = replace(
        day,
        exercises=day.exercises[:3],
        estimated_duration_minutes=RULESET.general_warmup_minutes
        + sum(item.estimated_minutes for item in day.exercises[:3]),
    )

    repaired, reasons = repair_session_durations(
        (underfilled,), normalized, (), RULESET, session_capacity=None
    )

    assert len(repaired[0].exercises) == 3
    assert "SESSION_DURATION_UNDERFILLED" not in reasons


def test_duration_repair_cannot_add_hidden_or_per_session_volume() -> None:
    source = request(session_duration_minutes=60, available_training_days=1)
    normalized = normalize_request(source, RULESET)
    result = generate_program(source, full_catalog(), RULESET)
    assert result.program is not None
    chest = next(
        item
        for item in result.program.weekly_schedule[0].exercises
        if item.primary_muscle is not None and item.primary_muscle.value == "chest"
    )
    exercises = (replace(chest, sets=3), replace(chest, exercise_id=full_catalog()[1].id, sets=3))
    day = replace(
        result.program.weekly_schedule[0],
        exercises=exercises,
        estimated_duration_minutes=RULESET.general_warmup_minutes
        + sum(item.estimated_minutes for item in exercises),
    )
    volume = plan_weekly_volume(normalized, result.program.split, RULESET)
    chest_candidates = tuple(
        item for item in full_catalog() if item.primary_muscle is chest.primary_muscle
    )

    repaired, _ = repair_session_durations(
        (day,),
        normalized,
        chest_candidates,
        RULESET,
        volume=volume,
    )

    repaired_chest = tuple(
        item for item in repaired[0].exercises if item.primary_muscle is chest.primary_muscle
    )
    assert sum(item.sets for item in repaired_chest) <= RULESET.max_sets_per_muscle_per_session
    assert all(item.counts_toward_volume for item in repaired[0].exercises)


def test_overfilled_session_is_repaired_without_fake_duration() -> None:
    source = request(session_duration_minutes=45, available_training_days=1)
    normalized = normalize_request(source, RULESET)
    eligibility = filter_eligible_exercises(normalized, full_catalog())
    result = generate_program(source, full_catalog(), RULESET)

    assert result.program is not None
    day = result.program.weekly_schedule[0]
    exercises = tuple(
        replace(
            item,
            sets=RULESET.max_working_sets_for_exercise(
                training_status=normalized.training_status,
                goal=source.primary_goal,
                exercise_type=item.exercise_type,
                is_priority=False,
                weekly_exposure_count=1,
            ),
            estimated_minutes=estimate_exercise_minutes(
                RULESET.max_working_sets_for_exercise(
                    training_status=normalized.training_status,
                    goal=source.primary_goal,
                    exercise_type=item.exercise_type,
                    is_priority=False,
                    weekly_exposure_count=1,
                ),
                item.rest_seconds,
                item.warmup_sets,
                RULESET,
            ),
        )
        for item in day.exercises
    )
    overfilled = replace(
        day,
        exercises=exercises,
        estimated_duration_minutes=RULESET.general_warmup_minutes
        + sum(item.estimated_minutes for item in exercises),
    )
    assert overfilled.estimated_duration_minutes > 40

    repaired, reasons = repair_session_durations(
        (overfilled,),
        normalized,
        eligibility.eligible,
        RULESET,
    )

    assert calculate_main_training_minutes(repaired[0]) <= 55
    assert repaired[0].estimated_duration_minutes >= 35 + RULESET.general_warmup_minutes
    assert "SESSION_DURATION_REPAIR_APPLIED" in reasons


def test_unsupported_target_fails_explicitly_instead_of_returning_short_session() -> None:
    from pydantic import ValidationError

    with pytest.raises(ValidationError) as exc_info:
        request(session_duration_minutes=180, available_training_days=1)

    assert "Input should be" in str(exc_info.value)
    assert "30, 45" in str(exc_info.value)


def test_final_validator_rejects_underfilled_session() -> None:
    source = request(session_duration_minutes=45, available_training_days=1)
    result = generate_program(source, full_catalog(), RULESET)

    assert result.program is not None
    day = result.program.weekly_schedule[0]
    # Phase 11.9: A session is only invalid under-budget if it ALSO misses the exercise floor.
    invalid = replace(
        result.program,
        weekly_schedule=(
            replace(
                day,
                exercises=day.exercises[:2],
                estimated_duration_minutes=15,
            ),
        ),
    )

    report = validate_program(invalid, source, RULESET)

    assert "SESSION_DURATION_UNDER_TARGET" in report.errors
    assert "SESSION_DURATION_TARGET_UNSATISFIED" in report.errors


def _duration_fixture_exercise(candidate, *, order: int, sets: int = 3, minutes: int = 8):
    return ProgrammedExercise(
        exercise_id=candidate.id,
        exercise_name=candidate.name,
        order=order,
        sets=sets,
        rep_min=8,
        rep_max=12,
        target_rir=2,
        rest_seconds=90,
        estimated_minutes=minutes,
        reason_codes=("TEMPLATE_REFERENCE_EXERCISE",),
        movement_pattern=candidate.movement_pattern,
        primary_muscle=candidate.primary_muscle,
        secondary_muscles=candidate.secondary_muscles,
        equipment=candidate.equipment,
        exercise_type=candidate.exercise_type,
    )


@pytest.mark.parametrize(
    ("existing_names", "expected_count"),
    [
        (("bodyweight hinge", "hamstring walkout"), 2),
        (("bodyweight hinge", "hamstring walkout", "bodyweight squat"), 3),
    ],
)
def test_template_underfill_keeps_explicit_constraint_when_no_hard_volume_room_exists(
    existing_names: tuple[str, ...], expected_count: int
) -> None:
    source = request(
        session_duration_minutes=45,
        available_training_days=1,
        training_experience="beginner",
    )
    normalized = normalize_request(source, RULESET)
    catalog = tuple(full_catalog())
    by_name = {item.name.lower(): item for item in catalog}
    existing = tuple(
        _duration_fixture_exercise(by_name[name], order=index, sets=4)
        for index, name in enumerate(existing_names, start=1)
    )
    day = WorkoutDay(
        day_index=1,
        weekday=0,
        title="Lower template",
        focus="template_reference_2",
        estimated_duration_minutes=5 + sum(item.estimated_minutes for item in existing),
        exercises=existing,
        template_target_muscles=(MuscleGroup.HAMSTRINGS,),
        template_structure_focus="lower",
    )
    volume = WeeklyVolumePlan(
        targets=(
            VolumeTarget(
                muscle=MuscleGroup.HAMSTRINGS,
                minimum_soft=0,
                target_sets=6,
                maximum_soft=8,
                maximum_hard=8,
                fractional_sets=0,
                effective_target_sets=6,
                minimum_direct_sets=0,
            ),
        ),
        reason_codes=(),
    )

    repaired, reasons = repair_session_durations(
        (day,),
        normalized,
        (
            replace(
                by_name["dumbbell rdl"],
                movement_pattern=MovementPattern.KNEE_FLEXION,
                substitution_group="duration_test_hamstring_curl",
            ),
        ),
        RULESET,
        volume=volume,
        prefer_acceptable_volume_for_minimum_fill=True,
    )

    assert len(repaired[0].exercises) == expected_count
    assert "SESSION_DURATION_TARGET_UNSATISFIED" in reasons
    assert "SESSION_DURATION_CONSTRAINED_BY_USEFUL_WORKLOAD" in reasons
    assert all(item.counts_toward_volume for item in repaired[0].exercises)


def test_focus_rejection_does_not_claim_hard_volume_constraint() -> None:
    source = request(session_duration_minutes=45, available_training_days=1)
    normalized = normalize_request(source, RULESET)
    catalog = tuple(full_catalog())
    day = WorkoutDay(
        day_index=1,
        weekday=0,
        title="Upper template",
        focus="upper",
        estimated_duration_minutes=5,
        exercises=(),
        template_target_muscles=(MuscleGroup.CHEST,),
        template_structure_focus="upper",
    )
    volume = WeeklyVolumePlan(
        targets=(
            VolumeTarget(
                muscle=MuscleGroup.CHEST,
                minimum_soft=0,
                target_sets=6,
                maximum_soft=8,
                maximum_hard=8,
                fractional_sets=0,
                effective_target_sets=6,
                minimum_direct_sets=0,
            ),
        ),
        reason_codes=(),
    )

    repaired, reasons = repair_session_durations(
        (day,),
        normalized,
        (next(item for item in catalog if item.name.lower() == "dumbbell rdl"),),
        RULESET,
        volume=volume,
        prefer_acceptable_volume_for_minimum_fill=True,
    )

    assert repaired[0].exercises == ()
    assert "SESSION_DURATION_TARGET_UNSATISFIED" in reasons
    assert "SESSION_DURATION_CONSTRAINED_BY_USEFUL_WORKLOAD" in reasons
    assert "SESSION_DURATION_CONSTRAINED_BY_HARD_VOLUME_LIMITS" not in reasons


def test_capacity_trim_preserves_optional_core_when_main_capacity_is_full() -> None:
    source = request(session_duration_minutes=60, available_training_days=1)
    normalized = normalize_request(source, RULESET)
    catalog = tuple(full_catalog())
    main = tuple(
        _duration_fixture_exercise(item, order=index, minutes=6)
        for index, item in enumerate(catalog[:9], start=1)
    )
    optional = replace(
        _duration_fixture_exercise(catalog[7], order=10, minutes=5),
        reason_codes=("OPTIONAL_SUPPLEMENTAL_WORK",),
        primary_muscle=MuscleGroup.ABS,
        exercise_type=ExerciseType.CORE,
        movement_pattern=MovementPattern.CORE_ANTI_EXTENSION,
    )
    day = WorkoutDay(
        day_index=1,
        weekday=0,
        title="Full session",
        focus="full_body_a",
        estimated_duration_minutes=5 + sum(item.estimated_minutes for item in (*main, optional)),
        exercises=(*main, optional),
    )

    repaired, reasons = repair_session_durations((day,), normalized, catalog, RULESET)

    assert len(repaired[0].exercises) == RULESET.max_exercises_per_session + 1
    assert main_exercise_count(repaired[0].exercises) == main_exercise_count(main)
    assert calculate_main_training_minutes(repaired[0]) <= get_session_duration_policy(
        60
    ).maximum_minutes
    assert "SUPPLEMENTAL_WORK_TRIMMED_FOR_DURATION" not in reasons
    assert optional.exercise_id in {item.exercise_id for item in repaired[0].exercises}


@pytest.mark.parametrize(
    ("profile_number", "underfilled_day"),
    [(5, 2), (10, 3)],
)
def test_batch2_profile_underfill_is_hard_volume_constrained(
    profile_number: int,
    underfilled_day: int,
) -> None:
    """Exercise the same catalog/template/service path as the Batch2 production run."""
    import scripts.generate_e2e_report_batch2 as batch2
    from app.workouts.program_engine import session_duration as duration_module

    profiles = batch2.TEST_PROFILES_BATCH2
    original_profiles = profiles[:]
    profiles[:] = [profile for profile in original_profiles if profile["num"] == profile_number]
    original_selector = duration_module._select_exercise_addition
    original_hard_check = duration_module._within_weekly_hard_volume
    strict_attempts: list[dict[str, int]] = []
    active_attempt: dict[str, int] | None = None

    def record_hard_check(*args, **kwargs):
        result = original_hard_check(*args, **kwargs)
        if active_attempt is not None:
            active_attempt["checks"] += 1
            active_attempt["safe"] += int(result)
        return result

    def record_selector(*args, **kwargs):
        nonlocal active_attempt
        strict = not kwargs["prefer_acceptable_volume_for_minimum_fill"]
        if not strict:
            return original_selector(*args, **kwargs)
        day, exercises, normalized_request = args[:3]
        active_attempt = {
            "day": day.day_index,
            "existing": len(exercises),
            "checks": 0,
            "safe": 0,
            "duration": normalized_request.source.session_duration_minutes,
        }
        try:
            return original_selector(*args, **kwargs)
        finally:
            strict_attempts.append(active_attempt)
            active_attempt = None

    duration_module._select_exercise_addition = record_selector
    duration_module._within_weekly_hard_volume = record_hard_check
    try:
        results = batch2.run_batch2_profiles()
    finally:
        profiles[:] = original_profiles
        duration_module._select_exercise_addition = original_selector
        duration_module._within_weekly_hard_volume = original_hard_check

    assert len(results) == 1
    _, result = results[0]
    if result["success"] is not True:
        assert result["error_code"] == "UNSATISFIED_CONSTRAINT"
        assert "SESSION_DURATION_UNDER_TARGET" in result["errors"]
        return
    plan = result["plan"]
    assert plan is not None
    day = plan.days[underfilled_day - 1]

    assert day.exercises
    assert day.estimated_duration_minutes > 0
    assert all(exercise.sets >= RULESET.minimum_working_sets for exercise in day.exercises)
    assert all(exercise.exercise.content_type.value == "exercise" for exercise in day.exercises)

    hard_attempt = next(attempt for attempt in strict_attempts if attempt["day"] == underfilled_day)
    assert hard_attempt["duration"] == 45
    assert hard_attempt["existing"] >= 1
    assert hard_attempt["checks"] > 0
    assert 0 <= hard_attempt["safe"] <= hard_attempt["checks"]

    ranges = plan.aggregate_metrics["volume_ranges_by_muscle"]
    assert any(
        values["actual_effective_volume"] >= values["acceptable_maximum"]
        and values["actual_effective_volume"] <= values["maximum_hard"]
        for values in ranges.values()
    )
