from dataclasses import replace

from app.exercises.enums import (
    ExerciseCautionTag,
    ExerciseLabel,
    ExerciseType,
    MovementPattern,
    MuscleGroup,
)
from app.workouts.program_engine.cardio import add_cardio
from app.workouts.program_engine.eligibility import filter_eligible_exercises
from app.workouts.program_engine.engine import generate_program
from app.workouts.program_engine.enums import (
    GenerationErrorCode,
    ImpactLimit,
    SkillDemand,
    SplitType,
    StabilityDemand,
    TrainingExperience,
)
from app.workouts.program_engine.exercise_ranker import rank_exercises
from app.workouts.program_engine.normalization import normalize_request
from app.workouts.program_engine.rulesets.resistance_training_v1 import RULESET
from app.workouts.program_engine.schemas import (
    TemplateReference,
    TemplateReferenceDay,
    TemplateReferenceSlot,
    WorkoutDay,
)
from app.workouts.program_engine.session_builder import KNEE_PATTERNS, build_sessions
from app.workouts.program_engine.split_selector import (
    generate_split_candidates,
    score_split_candidates,
)
from app.workouts.program_engine.template_sessions import build_template_sessions
from app.workouts.program_engine.volume_planner import plan_weekly_volume
from tests.workouts.program_engine.golden_fixtures import exercise, full_catalog, request


def _direct_muscles(day: WorkoutDay) -> set[MuscleGroup]:
    return {
        item.primary_muscle
        for item in day.exercises
        if item.primary_muscle is not None and item.counts_toward_volume
    }


def test_required_muscle_without_any_safe_coverage_is_structured_unsatisfied() -> None:
    catalog = [item for item in full_catalog() if item.primary_muscle is not MuscleGroup.CHEST]

    result = generate_program(
        request(available_training_days=3),
        catalog,
        RULESET,
    )

    assert result.program is not None
    for day in result.program.weekly_schedule:
        for ex in day.exercises:
            assert "HARD_INCOMPATIBLE" not in ex.reason_codes


def test_safe_layout_recovery_omits_hard_blocked_required_pattern() -> None:
    source = request(
        age=46,
        primary_goal="lose_weight",
        available_training_days=4,
        session_duration_minutes=75,
        blocked_caution_tags=[ExerciseCautionTag.DEEP_KNEE_FLEXION],
    )
    normalized = normalize_request(source, RULESET)
    catalog = [
        replace(
            item,
            caution_tags=item.caution_tags | {ExerciseCautionTag.DEEP_KNEE_FLEXION},
        )
        if item.movement_pattern in KNEE_PATTERNS
        else item
        for item in full_catalog()
    ]
    eligibility = filter_eligible_exercises(normalized, catalog)
    split = next(
        item
        for item in score_split_candidates(
            normalized,
            generate_split_candidates(4),
            RULESET,
        )
        if item.split_type is SplitType.UPPER_LOWER
    )

    sessions = build_sessions(
        normalized,
        split,
        plan_weekly_volume(normalized, split, RULESET),
        eligibility.eligible,
        RULESET,
        rejected_slot_candidates=tuple(
            (candidate, rejected.reason_codes)
            for candidate in catalog
            for rejected in eligibility.rejected
            if rejected.exercise_id == candidate.id
        ),
    )

    assert len(sessions) == 4
    assert all(
        any("RECOVERY_APPLIED_REQUIRED_SLOT_RELAXATION" in code for code in day.reason_codes)
        for day in sessions
        if day.focus == "lower"
    )
    assert all(
        item.movement_pattern not in KNEE_PATTERNS for day in sessions for item in day.exercises
    )


def test_exact_valid_knee_caution_profile_recovers_without_unsafe_exercises() -> None:
    source = request(
        age=46,
        primary_goal="lose_weight",
        training_experience=TrainingExperience.BEGINNER,
        training_age_months=3,
        available_training_days=4,
        session_duration_minutes=75,
        blocked_caution_tags=[ExerciseCautionTag.DEEP_KNEE_FLEXION],
    )

    catalog = [
        replace(
            item,
            caution_tags=item.caution_tags | {ExerciseCautionTag.DEEP_KNEE_FLEXION},
        )
        if item.movement_pattern in KNEE_PATTERNS
        else item
        for item in full_catalog()
    ]
    result = generate_program(source, catalog, RULESET)

    assert result.program is not None, result.errors
    assert result.program.validation_report.is_valid
    assert all(
        item.movement_pattern not in KNEE_PATTERNS
        for day in result.program.weekly_schedule
        for item in day.exercises
    )
    assert all(
        item.equipment.issubset(source.available_equipment)
        and item.caution_tags.isdisjoint(source.blocked_caution_tags)
        for day in result.program.weekly_schedule
        for item in day.exercises
    )
    recovery = next(
        entry
        for entry in result.program.decision_trace
        if entry["stage"] == "construction_recovery"
    )
    assert "RECOVERY_APPLIED_REQUIRED_SLOT_RELAXATION" in recovery["reason_codes"]
    final = next(
        entry for entry in result.program.decision_trace if entry["stage"] == "final_construction"
    )
    assert final["reason_codes"] == ("FINAL_CONSTRUCTION_SUCCEEDED",)


def test_constructible_major_coverage_is_repaired_before_success() -> None:
    source = request(
        age=62,
        training_experience=TrainingExperience.BEGINNER,
        training_age_months=2,
        available_training_days=2,
        session_duration_minutes=45,
    )

    result = generate_program(source, full_catalog(), RULESET)

    assert result.program is not None, result.errors
    ranges = result.program.aggregate_metrics["volume_ranges_by_muscle"]
    actual = result.program.aggregate_metrics["weekly_effective_sets_by_muscle"]
    for muscle, values in ranges.items():
        if values["minimum_coverage_required"]:
            assert actual[muscle] >= values["minimum_effective_sets"]
    repair = next(
        item for item in result.program.decision_trace if item["stage"] == "volume_repair"
    )
    assert any(reason.startswith("VOLUME_REPAIR_") for reason in repair["reasons"])


def test_dynamic_sessions_use_actual_direct_muscles_for_recovery_spacing() -> None:
    result = generate_program(
        request(
            primary_goal="body_recomposition",
            training_experience=TrainingExperience.INTERMEDIATE,
            training_age_months=24,
            available_training_days=5,
            session_duration_minutes=60,
            priority_muscles=[MuscleGroup.GLUTES, MuscleGroup.HAMSTRINGS],
        ),
        full_catalog(),
        RULESET,
    )

    assert result.program is not None, result.errors
    scheduled = sorted(result.program.weekly_schedule, key=lambda day: day.weekday or 0)
    circular = scheduled + [replace(scheduled[0], weekday=(scheduled[0].weekday or 0) + 7)]
    for current, following in zip(circular, circular[1:], strict=False):
        overlap = _direct_muscles(current).intersection(_direct_muscles(following))
        gap = (following.weekday or 0) - (current.weekday or 0)
        assert not overlap or gap >= RULESET.minimum_recovery_gap_days
    assert result.program.validation_report.is_valid


def test_valid_three_day_recovery_schedule_still_passes() -> None:
    result = generate_program(request(available_training_days=3), full_catalog(), RULESET)

    assert result.program is not None, result.errors
    assert result.program.validation_report.is_valid


def test_body_part_sessions_prefer_complementary_roles_over_near_duplicates() -> None:
    normalized = normalize_request(
        request(
            primary_goal="build_muscle",
            training_experience=TrainingExperience.INTERMEDIATE,
            training_age_months=30,
            available_training_days=4,
            session_duration_minutes=60,
        ),
        RULESET,
    )
    split = next(
        item
        for item in score_split_candidates(
            normalized,
            generate_split_candidates(4),
            RULESET,
        )
        if item.split_type.value == "body_part_rotation"
    )
    volume = plan_weekly_volume(normalized, split, RULESET)
    sessions = build_sessions(normalized, split, volume, tuple(full_catalog()), RULESET)
    chest = next(day for day in sessions if day.focus == "chest_triceps")
    shoulders = next(day for day in sessions if day.focus == "shoulders_traps")
    assert (
        sum(item.movement_pattern is MovementPattern.HORIZONTAL_PUSH for item in chest.exercises)
        <= 2
    )
    assert sum(item.movement_pattern is MovementPattern.SHRUG for item in shoulders.exercises) <= 1
    assert len({item.movement_pattern for item in chest.exercises}) >= 2


def test_template_session_replaces_excess_redundancy_with_complementary_role() -> None:
    catalog = full_catalog()
    by_name = {candidate.name: candidate for candidate in catalog}
    names = (
        "Push Up",
        "Incline Push Up",
        "Decline Push Up",
        "Close Grip Push Up",
        "Bodyweight Triceps Extension",
    )
    slots = tuple(
        TemplateReferenceSlot(
            exercise_id=by_name[name].id,
            exercise_slug_hint=name,
            target_muscles=(MuscleGroup.CHEST, MuscleGroup.TRICEPS),
            movement_pattern=by_name[name].movement_pattern,
            intensity_method="standard",
            adaptation_priority="core",
            superset_group=None,
            sets=3,
            rep_min=8,
            rep_max=12,
            target_rir=2,
            rest_seconds=90,
        )
        for name in names
    )
    template = TemplateReference(
        slug="redundant-chest-template",
        days_per_week=1,
        training_level="intermediate",
        fitness_goal="build_muscle",
        focus_tags=("chest",),
        intensity_methods=("standard",),
        days=(
            TemplateReferenceDay(
                day_number=1,
                title="Chest",
                focus=(MuscleGroup.CHEST, MuscleGroup.TRICEPS),
                slots=slots,
            ),
        ),
    )
    normalized = normalize_request(
        request(
            available_training_days=1,
            training_experience=TrainingExperience.INTERMEDIATE,
            training_age_months=24,
        ),
        RULESET,
    )

    build = build_template_sessions(normalized, template, tuple(catalog), RULESET)

    roles = [
        (candidate.primary_muscle, candidate.movement_pattern)
        for candidate in build.drafts[0].exercises
    ]
    assert roles.count((MuscleGroup.CHEST, MovementPattern.HORIZONTAL_PUSH)) <= 2
    assert any(muscle is MuscleGroup.SHOULDERS for muscle, _pattern in roles)
    assert "TEMPLATE_REDUNDANCY_REPLACED_WITH_COMPLEMENTARY_ROLE" in build.reason_codes


def test_older_novice_suitability_strongly_prefers_simple_stable_movements() -> None:
    simple = replace(
        exercise("supported-row", MovementPattern.HORIZONTAL_PULL, MuscleGroup.BACK),
        stability_demand=StabilityDemand.LOW,
        skill_demand=SkillDemand.LOW,
        fatigue_cost=1,
        setup_cost=1,
    )
    demanding = replace(
        exercise("inverted-row-between-chairs", MovementPattern.HORIZONTAL_PULL, MuscleGroup.BACK),
        stability_demand=StabilityDemand.HIGH,
        skill_demand=SkillDemand.HIGH,
        fatigue_cost=4,
        setup_cost=4,
    )
    normalized = normalize_request(
        request(
            age=62,
            training_experience=TrainingExperience.BEGINNER,
            training_age_months=2,
        ),
        RULESET,
    )

    ranked = rank_exercises(normalized, [demanding, simple], RULESET)

    assert ranked[0].exercise is simple
    assert "OLDER_NOVICE_SUITABILITY" in ranked[0].reason_codes
    assert {item.exercise.id for item in ranked} == {simple.id, demanding.id}


def test_mobility_and_cardio_content_cannot_fill_resistance_slots() -> None:
    mobility = replace(
        exercise("side-lunge-stretch", MovementPattern.LUNGE, MuscleGroup.ADDUCTORS),
        exercise_type=ExerciseType.MOBILITY,
    )
    cardio = replace(
        exercise("burpee", MovementPattern.SQUAT, MuscleGroup.QUADRICEPS),
        exercise_type=ExerciseType.OTHER,
        labels=frozenset({ExerciseLabel.CARDIO}),
    )
    mislabeled_yoga = exercise(
        "yoga-bridge-pose",
        MovementPattern.HIP_EXTENSION,
        MuscleGroup.GLUTES,
    )
    mislabeled_stretch = exercise(
        "plyometric-side-lunge-stretch",
        MovementPattern.LUNGE,
        MuscleGroup.GLUTES,
    )
    normalized = normalize_request(request(), RULESET)
    eligibility = filter_eligible_exercises(
        normalized,
        [mobility, mislabeled_yoga, mislabeled_stretch],
    )
    assert not eligibility.eligible
    assert len(eligibility.rejected) == 3
    assert all(
        "EXERCISE_REJECTED_NOT_RESISTANCE_TRAINING" in item.reason_codes
        for item in eligibility.rejected
    )

    catalog = [
        item
        for item in full_catalog()
        if item.movement_pattern
        not in {MovementPattern.SQUAT, MovementPattern.LUNGE, MovementPattern.KNEE_EXTENSION}
    ]
    catalog.append(cardio)
    result = generate_program(request(), catalog, RULESET)
    assert result.program is None
    assert result.error_code in {
        GenerationErrorCode.NO_SAFE_EXERCISE_FOR_PATTERN,
        GenerationErrorCode.UNSATISFIED_CONSTRAINT,
    }


def test_cardio_reason_code_matches_selected_high_impact_modality() -> None:
    source = normalize_request(request(primary_goal="fat_loss"), RULESET)
    burpee = replace(
        exercise(
            "burpee",
            MovementPattern.OTHER,
            None,
            labels=frozenset({ExerciseLabel.CARDIO}),
            exercise_type=ExerciseType.OTHER,
            impact=ImpactLimit.HIGH,
        ),
        fatigue_cost=0,
        setup_cost=0,
    )
    base = generate_program(request(primary_goal="fat_loss"), full_catalog(), RULESET)
    assert base.program is not None
    days = tuple(replace(day, cardio=None) for day in base.program.weekly_schedule)

    updated = add_cardio(source, days, (burpee,), RULESET)

    selected = next(day.cardio for day in updated if day.cardio is not None)
    assert "LOW_IMPACT_CARDIO_SELECTED" not in selected.reason_codes
    assert "CARDIO_MODALITY_SELECTED" in selected.reason_codes


def test_conventional_low_impact_cardio_is_preferred_when_available() -> None:
    source = normalize_request(request(primary_goal="fat_loss"), RULESET)
    generic = replace(
        exercise(
            "cardio-exercise",
            MovementPattern.OTHER,
            None,
            labels=frozenset({ExerciseLabel.CARDIO}),
            exercise_type=ExerciseType.OTHER,
            impact=ImpactLimit.MODERATE,
        ),
        fatigue_cost=1,
        setup_cost=1,
    )
    elliptical = replace(
        exercise(
            "elliptical-trainer",
            MovementPattern.OTHER,
            None,
            labels=frozenset({ExerciseLabel.CARDIO}),
            exercise_type=ExerciseType.OTHER,
            impact=ImpactLimit.LOW,
        ),
        fatigue_cost=2,
        setup_cost=2,
    )
    base = generate_program(request(primary_goal="fat_loss"), full_catalog(), RULESET)
    assert base.program is not None
    days = tuple(replace(day, cardio=None) for day in base.program.weekly_schedule)

    updated = add_cardio(source, days, (generic, elliptical), RULESET)

    selected = next(day.cardio for day in updated if day.cardio is not None)
    assert selected.modality_name == "Elliptical Trainer"
    assert "LOW_IMPACT_CARDIO_SELECTED" in selected.reason_codes


def test_older_novice_omits_nonspecific_or_high_impact_cardio() -> None:
    source = normalize_request(
        request(
            age=62,
            training_experience=TrainingExperience.BEGINNER,
            training_age_months=2,
        ),
        RULESET,
    )
    generic = exercise(
        "cardio-exercise",
        MovementPattern.OTHER,
        None,
        labels=frozenset({ExerciseLabel.CARDIO}),
        exercise_type=ExerciseType.OTHER,
        impact=ImpactLimit.MODERATE,
    )
    running = exercise(
        "running",
        MovementPattern.OTHER,
        None,
        labels=frozenset({ExerciseLabel.CARDIO}),
        exercise_type=ExerciseType.OTHER,
        impact=ImpactLimit.HIGH,
    )
    base = generate_program(request(), full_catalog(), RULESET)
    assert base.program is not None
    days = tuple(replace(day, cardio=None) for day in base.program.weekly_schedule)

    updated = add_cardio(source, days, (generic, running), RULESET)

    assert all(day.cardio is None for day in updated)


def test_generated_output_remains_deterministic_with_reversed_catalog() -> None:
    source = request(
        primary_goal="build_muscle",
        training_experience=TrainingExperience.INTERMEDIATE,
        training_age_months=30,
        available_training_days=4,
    )
    catalog = full_catalog()

    first = generate_program(source, catalog, RULESET)
    second = generate_program(source, list(reversed(catalog)), RULESET)

    assert first.program is not None, first.errors
    assert second.program == first.program
