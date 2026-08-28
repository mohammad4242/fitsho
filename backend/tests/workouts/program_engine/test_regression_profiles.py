from collections import Counter

from app.exercises.enums import (
    Equipment,
    ExerciseCautionTag,
    ExerciseType,
    MovementPattern,
    MuscleGroup,
    PrescriptionMode,
)
from app.profile.enums import TrainingLocation
from app.workouts.program_engine.duration_capacity import build_session_capacity
from app.workouts.program_engine.duration_policy import (
    calculate_main_training_minutes,
    get_session_duration_policy,
)
from app.workouts.program_engine.engine import generate_program
from app.workouts.program_engine.enums import CompatibilityLevel, Goal, TrainingExperience
from app.workouts.program_engine.normalization import normalize_request
from app.workouts.program_engine.recovery import recovery_spacing_is_valid
from app.workouts.program_engine.rulesets.resistance_training_v1 import RULESET
from app.workouts.program_engine.session_builder import build_sessions
from app.workouts.program_engine.slot_compatibility import (
    evaluate_candidate_slot_compatibility,
    focus_scope,
)
from app.workouts.program_engine.split_selector import (
    _dynamic_layout_sort_key,
    _focus_availability,
    generate_split_candidates,
    rank_availability_aware_fallbacks,
)
from app.workouts.program_engine.supplemental_policy import main_exercise_count
from app.workouts.program_engine.validation import validate_program
from app.workouts.program_engine.volume_planner import plan_weekly_volume
from tests.workouts.program_engine.golden_fixtures import exercise, full_catalog, request


def test_dynamic_fallback_awards_no_priority_credit_to_structural_upper() -> None:
    source = request(
        available_training_days=5,
        training_experience=TrainingExperience.INTERMEDIATE,
        training_age_months=24,
        priority_muscles=[MuscleGroup.CHEST],
    )
    normalized = normalize_request(source, RULESET)
    catalog = tuple(full_catalog())
    capacity = build_session_capacity(normalized, catalog, RULESET)

    upper = _focus_availability(
        "upper", catalog, frozenset({MuscleGroup.CHEST}), normalized, RULESET, capacity
    )
    chest = _focus_availability(
        "chest_triceps",
        catalog,
        frozenset({MuscleGroup.CHEST}),
        normalized,
        RULESET,
        capacity,
    )

    assert upper.priority_affinity_score == 0
    assert chest.priority_affinity_score > 0


def test_dynamic_fallback_does_not_treat_upper_as_priority_coverage() -> None:
    source = request(
        available_training_days=5,
        training_experience=TrainingExperience.INTERMEDIATE,
        training_age_months=24,
        priority_muscles=[MuscleGroup.CHEST],
    )
    normalized = normalize_request(source, RULESET)
    catalog = tuple(full_catalog())
    capacity = build_session_capacity(normalized, catalog, RULESET)
    priorities = frozenset({MuscleGroup.CHEST})
    availability = tuple(
        _focus_availability(focus, catalog, priorities, normalized, RULESET, capacity)
        for focus in ("upper", "lower", "chest_triceps")
    )

    upper_key = _dynamic_layout_sort_key(
        ("upper", "lower"), availability, normalized, capacity.expected_exercise_count_capacity
    )
    dedicated_key = _dynamic_layout_sort_key(
        ("chest_triceps", "lower"),
        availability,
        normalized,
        capacity.expected_exercise_count_capacity,
    )

    assert upper_key[1] == 1
    assert dedicated_key[1] == 0


def test_five_day_fallback_is_built_from_available_focuses() -> None:
    upper = [
        exercise(f"limited-push-{index}", MovementPattern.HORIZONTAL_PUSH, MuscleGroup.CHEST)
        for index in range(1)
    ] + [
        exercise(f"limited-pull-{index}", MovementPattern.HORIZONTAL_PULL, MuscleGroup.BACK)
        for index in range(4)
    ]
    lower = (
        [
            exercise(f"limited-squat-{index}", MovementPattern.SQUAT, MuscleGroup.QUADRICEPS)
            for index in range(2)
        ]
        + [
            exercise(f"limited-hinge-{index}", MovementPattern.HIP_HINGE, MuscleGroup.HAMSTRINGS)
            for index in range(2)
        ]
        + [
            exercise(f"limited-core-{index}", MovementPattern.CORE_ANTI_EXTENSION, MuscleGroup.ABS)
            for index in range(2)
        ]
    )
    source = request(
        available_training_days=5,
        session_duration_minutes=30,
        primary_goal=Goal.HYPERTROPHY,
        training_experience=TrainingExperience.INTERMEDIATE,
        training_age_months=30,
    )

    result = generate_program(source, [*upper, *lower], RULESET)

    if not result.is_success:
        assert result.error_code.value == "UNSATISFIED_CONSTRAINT"
        assert any(error.startswith("SESSION_DURATION_") for error in result.errors)
        return
    assert result.program is not None
    assert result.program.split.split_type.value in {
        "dynamic_fallback",
        "upper_lower_specialization",
    }
    assert result.program.split.day_focuses != ("upper", "lower", "push", "pull", "legs")
    assert set(result.program.split.day_focuses).issubset(
        {
            "upper",
            "lower",
            "legs",
            "specialization",
            "pull",
            "back_biceps",
            "posterior_chain_core",
        }
    )
    assert len(result.program.weekly_schedule) == 5
    assert all(day.exercises for day in result.program.weekly_schedule)
    assert not validate_program(result.program, source, RULESET).errors

    reversed_result = generate_program(source, [*reversed([*upper, *lower])], RULESET)
    assert reversed_result.program is not None
    assert reversed_result.program.split.day_focuses == result.program.split.day_focuses


def test_six_day_fallback_layouts_are_feasible_distinct_and_deterministic() -> None:
    source = request(
        available_training_days=6,
        primary_goal=Goal.STRENGTH,
        training_experience=TrainingExperience.ADVANCED,
        training_age_months=72,
    )
    normalized = normalize_request(source, RULESET)
    catalog = tuple(full_catalog())
    excluded = frozenset(item.day_focuses for item in generate_split_candidates(6))

    layouts = rank_availability_aware_fallbacks(
        normalized,
        catalog,
        RULESET,
        weekdays=RULESET.default_weekdays[6],
        excluded_layouts=excluded,
    )
    reversed_layouts = rank_availability_aware_fallbacks(
        normalized,
        tuple(reversed(catalog)),
        RULESET,
        weekdays=RULESET.default_weekdays[6],
        excluded_layouts=excluded,
    )

    assert layouts
    assert all(len(item.day_focuses) == 6 for item in layouts)
    assert all(item.day_focuses not in excluded for item in layouts)
    assert tuple(item.day_focuses for item in reversed_layouts) == tuple(
        item.day_focuses for item in layouts
    )
    selected = layouts[0]
    drafts = build_sessions(
        normalized,
        selected,
        plan_weekly_volume(normalized, selected, RULESET),
        catalog,
        RULESET,
    )
    assert len(drafts) == 6
    assert all(draft.exercises for draft in drafts)


def test_regression_profiles() -> None:
    profiles = [
        # 1. Beginner, Home Bodyweight, 3 days, 45 min
        {
            "training_experience": TrainingExperience.BEGINNER,
            "training_location": TrainingLocation.HOME,
            "available_equipment": [Equipment.BODYWEIGHT],
            "available_training_days": 3,
            "session_duration_minutes": 45,
            "primary_goal": Goal.GENERAL_FITNESS,
        },
        # 2. Intermediate, Gym, 4 days, 60 min, Hypertrophy
        {
            "training_experience": TrainingExperience.INTERMEDIATE,
            "training_location": TrainingLocation.GYM,
            "available_equipment": list(Equipment),
            "available_training_days": 4,
            "session_duration_minutes": 60,
            "primary_goal": Goal.HYPERTROPHY,
        },
        # 3. Advanced, Gym, 6 days, 75 min, Strength
        {
            "training_experience": TrainingExperience.ADVANCED,
            "training_location": TrainingLocation.GYM,
            "available_equipment": list(Equipment),
            "available_training_days": 6,
            "session_duration_minutes": 75,
            "primary_goal": Goal.STRENGTH,
        },
        # 4. Beginner, Home Dumbbells, 2 days, 30 min, Fat loss
        {
            "training_experience": TrainingExperience.BEGINNER,
            "training_location": TrainingLocation.HOME,
            "available_equipment": [Equipment.BODYWEIGHT, Equipment.DUMBBELL],
            "available_training_days": 2,
            "session_duration_minutes": 30,
            "primary_goal": Goal.FAT_LOSS,
        },
        # 5. Intermediate, Home, 4 days, 60 min, Muscle Gain, Single Caution
        {
            "training_experience": TrainingExperience.INTERMEDIATE,
            "training_location": TrainingLocation.HOME,
            "available_equipment": [
                Equipment.BODYWEIGHT,
                Equipment.DUMBBELL,
                Equipment.RESISTANCE_BAND,
            ],
            "available_training_days": 4,
            "session_duration_minutes": 60,
            "primary_goal": Goal.MUSCLE_GAIN,
            "blocked_caution_tags": [ExerciseCautionTag.LOWER_BACK_LOADING],
        },
        # 6. Advanced, Gym, 3 days, 60 min, Body Recomposition, Multiple Cautions
        {
            "training_experience": TrainingExperience.ADVANCED,
            "training_location": TrainingLocation.GYM,
            "available_equipment": list(Equipment),
            "available_training_days": 3,
            "session_duration_minutes": 60,
            "primary_goal": Goal.BODY_RECOMPOSITION,
            "blocked_caution_tags": [
                ExerciseCautionTag.SHOULDER_INTERNAL_ROTATION,
                ExerciseCautionTag.DEEP_KNEE_FLEXION,
            ],
        },
        # 7. Beginner, Gym, 4 days, 45 min, General Fitness
        {
            "training_experience": TrainingExperience.BEGINNER,
            "training_location": TrainingLocation.GYM,
            "available_equipment": list(Equipment),
            "available_training_days": 4,
            "session_duration_minutes": 45,
            "primary_goal": Goal.GENERAL_FITNESS,
        },
        # 8. Intermediate, Home Bodyweight, 6 days, 30 min (high frequency short)
        {
            "training_experience": TrainingExperience.INTERMEDIATE,
            "training_location": TrainingLocation.HOME,
            "available_equipment": [Equipment.BODYWEIGHT],
            "available_training_days": 6,
            "session_duration_minutes": 30,
            "primary_goal": Goal.GENERAL_FITNESS,
        },
        # 9. Advanced, Home Dumbbells, 4 days, 60 min, Strength
        {
            "training_experience": TrainingExperience.ADVANCED,
            "training_location": TrainingLocation.HOME,
            "available_equipment": [Equipment.BODYWEIGHT, Equipment.DUMBBELL],
            "available_training_days": 4,
            "session_duration_minutes": 60,
            "primary_goal": Goal.STRENGTH,
        },
    ]

    impossible_profile = {
        "training_experience": TrainingExperience.ADVANCED,
        "training_location": TrainingLocation.HOME,
        "available_equipment": [Equipment.BODYWEIGHT],
        "available_training_days": 7,
        "session_duration_minutes": 120,  # Very long bodyweight sessions, 7 days
        "primary_goal": Goal.MUSCLE_GAIN,
    }

    catalog = full_catalog()
    catalog_by_id = {item.id: item for item in catalog}
    for profile in profiles:
        req = request(**profile)
        result = generate_program(req, catalog, RULESET)
        if not result.is_success:
            assert result.error_code.value == "UNSATISFIED_CONSTRAINT"
            assert any(error.startswith("SESSION_DURATION_") for error in result.errors)
            continue
        program = result.program
        assert program is not None

        # Verify final validator has zero errors
        validation_report = validate_program(program, req, RULESET)
        assert not validation_report.errors, f"Validation errors found: {validation_report.errors}"

        # Verify exact requested days
        assert len(program.weekly_schedule) == req.available_training_days
        assert recovery_spacing_is_valid(program.weekly_schedule, RULESET)

        for day in program.weekly_schedule:
            # Verify no empty days
            assert len(day.exercises) > 0
            per_session_sets = Counter(
                item.primary_muscle
                for item in day.exercises
                for _set in range(item.sets)
                if item.primary_muscle is not None
            )
            assert all(
                sets <= RULESET.max_sets_per_muscle_per_session
                for sets in per_session_sets.values()
            )

            policy = get_session_duration_policy(req.session_duration_minutes)
            assert policy.contains(calculate_main_training_minutes(day))
            exercise_floor = (
                3
                if req.session_duration_minutes <= RULESET.short_session_minutes
                else RULESET.minimum_exercises_per_session
            )
            assert (
                main_exercise_count(day.exercises) >= exercise_floor
                or "SESSION_EXERCISE_COUNT_OUT_OF_RANGE" in program.validation_report.warnings
            )

            for ex in day.exercises:
                # No unavailable equipment
                for eq in ex.equipment:
                    if eq != Equipment.BODYWEIGHT:
                        assert eq in req.available_equipment, f"Unavailable eq {eq}"

                # No blocked caution tags
                if req.blocked_caution_tags:
                    for tag in ex.caution_tags:
                        assert tag not in req.blocked_caution_tags, f"Blocked tag {tag}"

                # No HARD_INCOMPATIBLE selected
                assert "RECOVERED_INCOMPATIBLE_SEMANTICS" not in ex.reason_codes
                assert "HARD_INCOMPATIBLE" not in ex.reason_codes

                # No inactive/non-programmable exercise
                assert ex.is_active is True
                assert ex.is_programmable is True

                target = catalog_by_id[ex.exercise_id]
                focus_patterns, _focus_muscles = focus_scope(day.focus)
                for replacement_id in ex.substitution_exercise_ids:
                    replacement = catalog_by_id[replacement_id]
                    compatibility = evaluate_candidate_slot_compatibility(
                        replacement,
                        allowed_patterns=focus_patterns,
                        target_muscles=(
                            frozenset({target.primary_muscle})
                            if target.primary_muscle is not None
                            else None
                        ),
                        day_focus=day.focus,
                        allow_full_body=day.focus.startswith("full_body"),
                    )
                    assert compatibility.level is not CompatibilityLevel.HARD_INCOMPATIBLE

                # Valid reps-vs-duration prescription
                if ex.prescription_mode == PrescriptionMode.REPS:
                    assert ex.rep_min is not None and ex.rep_max is not None
                    assert 1 <= ex.rep_min <= ex.rep_max <= 100
                    assert ex.duration_min_seconds is None and ex.duration_max_seconds is None
                elif ex.prescription_mode == PrescriptionMode.DURATION:
                    assert ex.duration_min_seconds is not None
                    assert ex.duration_max_seconds is not None
                    assert 1 <= ex.duration_min_seconds <= ex.duration_max_seconds <= 3600
                    assert ex.rep_min is None and ex.rep_max is None

                # Verify that we don't dump 5 sets (unless explicitly strength and compound)
                if ex.sets >= 5:
                    assert req.primary_goal == Goal.STRENGTH, (
                        f"5 sets dumped on non-strength profile for {ex.exercise_name}"
                    )
                    assert ex.exercise_type == ExerciseType.COMPOUND, (
                        f"5 sets dumped on non-compound exercise {ex.exercise_name}"
                    )
                    assert "STRENGTH_PRIMARY_COMPOUND" in ex.reason_codes, (
                        f"5 sets dumped on non-primary strength work {ex.exercise_name} "
                        f"(reasons: {ex.reason_codes})"
                    )

        ranges = program.aggregate_metrics["volume_ranges_by_muscle"]
        effective = program.aggregate_metrics["weekly_effective_sets_by_muscle"]
        assert all(
            sets <= ranges[muscle]["effective_maximum_hard"]
            for muscle, sets in effective.items()
            if muscle in ranges
        )

    req_imp = request(**impossible_profile)
    res_imp = generate_program(req_imp, catalog, RULESET)
    assert res_imp.error_code is not None
