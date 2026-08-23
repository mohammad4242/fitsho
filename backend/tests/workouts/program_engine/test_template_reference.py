from dataclasses import replace

from app.exercises.enums import Equipment, MovementPattern, MuscleGroup
from app.workouts.program_engine.engine import _template_rejection_category, generate_program
from app.workouts.program_engine.enums import RecoveryRating, ValidationStatus
from app.workouts.program_engine.normalization import normalize_request
from app.workouts.program_engine.rulesets.resistance_training_v1 import RULESET
from app.workouts.program_engine.schemas import (
    ExerciseCandidate,
    RecentTrainingHistory,
    TemplateReference,
    TemplateReferenceDay,
    TemplateReferenceSlot,
)
from app.workouts.program_engine.template_sessions import build_template_sessions
from tests.workouts.program_engine.golden_fixtures import exercise, full_catalog, request


def template_request(**overrides: object):
    values: dict[str, object] = {
        "available_equipment": [Equipment.BODYWEIGHT, Equipment.DUMBBELL, Equipment.PULL_UP_BAR],
    }
    values.update(overrides)
    return request(**values)


def _four_day_reference() -> TemplateReference:
    return TemplateReference(
        slug="four-day-chest-reference",
        days_per_week=4,
        training_level="intermediate",
        fitness_goal="build_muscle",
        focus_tags=("chest_priority",),
        intensity_methods=("standard",),
        days=tuple(
            TemplateReferenceDay(
                day_number=index,
                title=title,
                focus=muscles,
                slots=(
                    TemplateReferenceSlot(
                        exercise_id=None,
                        exercise_slug_hint=pattern.value,
                        target_muscles=muscles,
                        movement_pattern=pattern,
                        intensity_method="standard",
                        adaptation_priority="core",
                        superset_group=None,
                        sets=3,
                        rep_min=8,
                        rep_max=12,
                        target_rir=2,
                        rest_seconds=90,
                    ),
                )
                + (
                    (
                        TemplateReferenceSlot(
                            exercise_id=None,
                            exercise_slug_hint="lateral_raise",
                            target_muscles=(MuscleGroup.SHOULDERS,),
                            movement_pattern=MovementPattern.SHOULDER_ABDUCTION,
                            intensity_method="standard",
                            adaptation_priority="accessory",
                            superset_group=None,
                            sets=3,
                            rep_min=10,
                            rep_max=15,
                            target_rir=2,
                            rest_seconds=60,
                        ),
                    )
                    if index == 1
                    else ()
                )
                + (
                    (
                        TemplateReferenceSlot(
                            exercise_id=None,
                            exercise_slug_hint="hip_hinge",
                            target_muscles=(MuscleGroup.HAMSTRINGS,),
                            movement_pattern=MovementPattern.HIP_HINGE,
                            intensity_method="standard",
                            adaptation_priority="core",
                            superset_group=None,
                            sets=3,
                            rep_min=8,
                            rep_max=12,
                            target_rir=2,
                            rest_seconds=90,
                        ),
                    )
                    if pattern is MovementPattern.SQUAT
                    else ()
                ),
            )
            for index, (title, muscles, pattern) in enumerate(
                (
                    ("Chest", (MuscleGroup.CHEST,), MovementPattern.HORIZONTAL_PUSH),
                    ("Back", (MuscleGroup.BACK,), MovementPattern.HORIZONTAL_PULL),
                    (
                        "Legs",
                        (MuscleGroup.QUADRICEPS, MuscleGroup.HAMSTRINGS, MuscleGroup.GLUTES),
                        MovementPattern.SQUAT,
                    ),
                    ("Core", (MuscleGroup.ABS,), MovementPattern.CORE_ANTI_EXTENSION),
                ),
                start=1,
            )
        ),
    )


def _upper_lower_reference() -> tuple[TemplateReference, list[ExerciseCandidate]]:
    catalog = full_catalog()
    by_name = {candidate.name: candidate for candidate in catalog}
    upper_focus = (MuscleGroup.CHEST, MuscleGroup.BACK)
    lower_focus = (
        MuscleGroup.QUADRICEPS,
        MuscleGroup.HAMSTRINGS,
        MuscleGroup.GLUTES,
        MuscleGroup.ABS,
    )

    def slot(
        name: str,
        focus: tuple[MuscleGroup, ...],
        *,
        priority: str = "core",
    ) -> TemplateReferenceSlot:
        candidate = by_name[name]
        return TemplateReferenceSlot(
            exercise_id=candidate.id,
            exercise_slug_hint=name,
            target_muscles=focus,
            movement_pattern=candidate.movement_pattern,
            intensity_method="rest_pause" if name == "Dumbbell Press" else "standard",
            adaptation_priority=priority,
            superset_group=None,
            sets=4,
            rep_min=8,
            rep_max=10,
            target_rir=1,
            rest_seconds=75,
        )

    template = TemplateReference(
        slug="four-day-upper-lower-reference",
        days_per_week=4,
        training_level="intermediate",
        fitness_goal="build_muscle",
        focus_tags=("chest_priority", "back_priority"),
        intensity_methods=("standard", "rest_pause"),
        days=(
            TemplateReferenceDay(
                1,
                "Upper A",
                upper_focus,
                (
                    slot("Push Up", upper_focus),
                    slot("Bodyweight Row", upper_focus),
                    slot("Incline Push Up", upper_focus, priority="accessory"),
                ),
            ),
            TemplateReferenceDay(
                2,
                "Lower A",
                lower_focus,
                (slot("Bodyweight Squat", lower_focus), slot("Bodyweight Hinge", lower_focus)),
            ),
            TemplateReferenceDay(
                3,
                "Upper B",
                upper_focus,
                (
                    slot("Dumbbell Press", upper_focus),
                    slot("Dumbbell Row", upper_focus),
                    slot("Decline Push Up", upper_focus, priority="accessory"),
                ),
            ),
            TemplateReferenceDay(
                4,
                "Lower B",
                lower_focus,
                (slot("Wall Knee Extension", lower_focus), slot("Dumbbell Rdl", lower_focus)),
            ),
        ),
    )
    return template, catalog


def test_safe_core_substitution_can_repeat_across_sessions_deterministically() -> None:
    by_name = {candidate.name: candidate for candidate in full_catalog()}
    catalog = [
        by_name[name]
        for name in (
            "Bodyweight Hinge",
            "Push Up",
            "Bodyweight Row",
            "Bodyweight Squat",
            "Calf Raise",
            "Incline Push Up",
            "Dumbbell Row",
            "Wall Knee Extension",
            "Plank",
        )
    ]
    hinge = by_name["Bodyweight Hinge"]

    def slot(candidate: ExerciseCandidate, *, priority: str = "core") -> TemplateReferenceSlot:
        return TemplateReferenceSlot(
            exercise_id=None if candidate is hinge else candidate.id,
            exercise_slug_hint=candidate.name,
            target_muscles=(candidate.primary_muscle,) if candidate.primary_muscle else (),
            movement_pattern=candidate.movement_pattern,
            intensity_method="standard",
            adaptation_priority=priority,
            superset_group=None,
            sets=3,
            rep_min=8,
            rep_max=12,
            target_rir=2,
            rest_seconds=60,
        )

    reference = TemplateReference(
        slug="two-day-shared-hinge-substitution",
        days_per_week=2,
        training_level="beginner",
        fitness_goal="general_fitness",
        focus_tags=("full_body", "balanced"),
        intensity_methods=("standard",),
        days=(
            TemplateReferenceDay(
                1,
                "A",
                (),
                (
                    slot(hinge, priority="core"),
                    slot(by_name["Push Up"]),
                    slot(by_name["Bodyweight Row"]),
                    slot(by_name["Bodyweight Squat"]),
                    slot(by_name["Calf Raise"]),
                ),
            ),
            TemplateReferenceDay(
                2,
                "B",
                (),
                (
                    slot(hinge, priority="core"),
                    slot(by_name["Incline Push Up"]),
                    slot(by_name["Dumbbell Row"]),
                    slot(by_name["Wall Knee Extension"]),
                    slot(by_name["Plank"]),
                ),
            ),
        ),
    )
    normalized = normalize_request(
        template_request(
            available_training_days=2,
            training_experience="beginner",
            training_age_months=6,
        ),
        RULESET,
    )

    first = build_template_sessions(normalized, reference, tuple(catalog), RULESET)
    second = build_template_sessions(normalized, reference, tuple(reversed(catalog)), RULESET)

    assert [draft.exercises[0].id for draft in first.drafts] == [hinge.id, hinge.id]
    assert [draft.exercises[0].id for draft in second.drafts] == [hinge.id, hinge.id]


def _repeated_core_reference() -> tuple[TemplateReference, list[ExerciseCandidate]]:
    template, catalog = _upper_lower_reference()
    repeated_id = template.days[0].slots[0].exercise_id
    repeated_slot = replace(
        template.days[2].slots[0],
        exercise_id=repeated_id,
        exercise_slug_hint="intentional-repeated-push-up",
    )
    repeated_day = replace(
        template.days[2],
        slots=(repeated_slot, template.days[2].slots[1]),
    )
    return (
        replace(
            template,
            slug="four-day-repeated-core-reference",
            days=(template.days[0], template.days[1], repeated_day, template.days[3]),
        ),
        catalog,
    )


def test_safe_matching_template_becomes_deterministic_program_reference() -> None:
    catalog = full_catalog()
    template = _four_day_reference()

    result = generate_program(
        template_request(
            available_training_days=4,
            primary_goal="build_muscle",
            training_experience="intermediate",
            training_age_months=24,
            session_duration_minutes=60,
        ),
        catalog,
        RULESET,
        reference_templates=(template,),
    )

    assert result.program is not None, result.errors
    assert result.program.aggregate_metrics["reference_template"] == template.slug
    template_trace = next(
        entry for entry in result.program.decision_trace if entry["stage"] == "template_reference"
    )
    assert template_trace["selected"] == template.slug
    assert template_trace["hard_eligibility"] == (
        "days",
        "training_level",
        "core_slots_resolvable",
    )
    assert template_trace["goal_used_for_exclusion"] is False
    assert [entry["stage"] for entry in result.program.decision_trace] == [
        "template_selection",
        "normalization",
        "safety",
        "eligibility",
        "template_reference",
        "template_adaptation",
        "day_count_invariant",
        "volume",
        "volume_repair",
        "session_duration",
        "template_attempt",
        "final_construction",
        "coach_quality",
    ]
    quality = result.program.decision_trace[-1]["metrics"]
    assert quality["template_preservation"] == {
        "satisfied": 6.0,
        "total": 6.0,
        "percentage": 100.0,
    }
    selection_trace = result.program.decision_trace[0]
    assert selection_trace["selected"] == template.slug
    assert len(selection_trace["candidates"]) == 1
    candidate_trace = selection_trace["candidates"][0]
    assert candidate_trace["rank"] == 1
    assert candidate_trace["slug"] == template.slug
    assert candidate_trace["score"] == {
        "priority": 0,
        "body_analysis": 0,
        "goal": 0,
        "sex": 0,
        "fallback": 0,
        "total": 0,
    }
    assert candidate_trace["feasibility"]["resolvable_slots"] == 6
    assert candidate_trace["feasibility"]["unresolved_non_core_slots"] == 0
    assert candidate_trace["reason_codes"] == ()


def test_template_priority_soft_shortfall_is_valid_with_constraints() -> None:
    reference, catalog = _upper_lower_reference()
    result = generate_program(
        template_request(
            available_training_days=4,
            primary_goal="build_muscle",
            training_experience="intermediate",
            training_age_months=24,
            session_duration_minutes=30,
            priority_muscles=[MuscleGroup.CHEST],
        ),
        catalog,
        RULESET,
        reference_templates=(reference,),
    )

    assert result.program is not None, result.errors
    assert result.program.aggregate_metrics["reference_template"] == reference.slug
    metric = result.program.aggregate_metrics["volume_ranges_by_muscle"]["chest"]
    assert metric["actual_effective_volume"] < metric["preferred_weekly_target"]
    assert result.program.validation_report.status is ValidationStatus.VALID_WITH_CONSTRAINTS
    assert result.program.validation_report.is_valid


def test_template_uses_shared_volume_and_prescription_rules() -> None:
    result = generate_program(
        template_request(
            available_training_days=4,
            primary_goal="build_muscle",
            training_experience="intermediate",
            training_age_months=24,
            session_duration_minutes=60,
        ),
        full_catalog(),
        RULESET,
        reference_templates=(_four_day_reference(),),
    )

    assert result.program is not None, result.errors
    first_exercise = result.program.weekly_schedule[0].exercises[0]
    assert (
        first_exercise.rest_seconds
        == RULESET.prescription_rules["hypertrophy_compound"].rest_seconds
    )
    assert any(entry["stage"] == "volume" for entry in result.program.decision_trace)
    assert any(entry["stage"] == "volume_repair" for entry in result.program.decision_trace)


def test_safe_template_superset_group_reaches_programmed_exercises() -> None:
    template, catalog = _upper_lower_reference()
    grouped_slots = tuple(
        replace(slot, adaptation_priority="accessory", superset_group="upper-a")
        if index < 2
        else slot
        for index, slot in enumerate(template.days[0].slots)
    )
    grouped_template = replace(
        template,
        days=(replace(template.days[0], slots=grouped_slots), *template.days[1:]),
    )

    result = generate_program(
        template_request(
            available_training_days=4,
            primary_goal="build_muscle",
            training_experience="intermediate",
            training_age_months=24,
            session_duration_minutes=90,
        ),
        catalog,
        RULESET,
        reference_templates=(grouped_template,),
    )

    assert result.program is not None, result.errors
    grouped = tuple(
        item for item in result.program.weekly_schedule[0].exercises if item.superset_group
    )
    assert len(grouped) == 2
    assert {item.superset_group for item in grouped} == {"upper-a"}


def test_same_template_personalizes_weekly_volume_targets_for_different_priorities() -> None:
    template, catalog = _upper_lower_reference()

    chest_result = generate_program(
        template_request(
            available_training_days=4,
            primary_goal="build_muscle",
            training_experience="intermediate",
            training_age_months=24,
            session_duration_minutes=60,
            priority_muscles=[MuscleGroup.CHEST],
        ),
        catalog,
        RULESET,
        reference_templates=(template,),
    )
    back_result = generate_program(
        template_request(
            available_training_days=4,
            primary_goal="build_muscle",
            training_experience="intermediate",
            training_age_months=24,
            session_duration_minutes=60,
            priority_muscles=[MuscleGroup.BACK],
        ),
        catalog,
        RULESET,
        reference_templates=(template,),
    )

    assert chest_result.program is not None, chest_result.errors
    assert back_result.program is not None, back_result.errors
    chest_volume = chest_result.program.aggregate_metrics["weekly_direct_sets_by_muscle"]
    back_volume = back_result.program.aggregate_metrics["weekly_direct_sets_by_muscle"]
    chest_ranges = chest_result.program.aggregate_metrics["volume_ranges_by_muscle"]
    back_ranges = back_result.program.aggregate_metrics["volume_ranges_by_muscle"]
    assert (
        chest_ranges["chest"]["preferred_weekly_target"]
        > back_ranges["chest"]["preferred_weekly_target"]
    )
    assert (
        back_ranges["back"]["preferred_weekly_target"]
        > chest_ranges["back"]["preferred_weekly_target"]
    )
    assert chest_volume["chest"] >= chest_ranges["chest"]["acceptable_minimum"]
    assert back_volume["back"] >= back_ranges["back"]["acceptable_minimum"]
    for result in (chest_result, back_result):
        ranges = result.program.aggregate_metrics["volume_ranges_by_muscle"]
        assert all(
            values["acceptable_minimum"]
            <= values["actual_effective_volume"]
            <= values["acceptable_maximum"]
            or values["status"] == "constrained"
            for values in ranges.values()
        )
    for day_index in (0, 2):
        expected_core_ids = {slot.exercise_id for slot in template.days[day_index].slots}
        actual_core = chest_result.program.weekly_schedule[day_index].exercises[:3]
        assert {exercise.exercise_id for exercise in actual_core} == expected_core_ids
        assert all("TEMPLATE_REFERENCE_EXERCISE" in item.reason_codes for item in actual_core)


def test_template_volume_uses_recovery_history_and_short_session_prescription() -> None:
    template, catalog = _upper_lower_reference()
    history = RecentTrainingHistory(
        completed_session_ratio=1.0,
        previous_weekly_direct_sets_by_muscle={MuscleGroup.CHEST: 5.0},
        previous_volume_source="prescribed_plan",
        recovery_problems=True,
    )

    baseline = generate_program(
        template_request(
            available_training_days=4,
            primary_goal="build_muscle",
            training_experience="intermediate",
            training_age_months=24,
            session_duration_minutes=60,
            priority_muscles=[MuscleGroup.CHEST],
        ),
        catalog,
        RULESET,
        reference_templates=(template,),
    )
    constrained = generate_program(
        template_request(
            available_training_days=4,
            primary_goal="build_muscle",
            training_experience="intermediate",
            training_age_months=24,
            session_duration_minutes=30,
            priority_muscles=[MuscleGroup.CHEST],
            sleep_quality=RecoveryRating.POOR,
            recent_training_history=history,
        ),
        catalog,
        RULESET,
        reference_templates=(template,),
    )

    assert baseline.program is not None, baseline.errors
    assert constrained.program is not None, constrained.errors
    baseline_target = baseline.program.aggregate_metrics["planned_direct_sets_by_muscle"]["chest"]
    constrained_target = constrained.program.aggregate_metrics["planned_direct_sets_by_muscle"][
        "chest"
    ]
    baseline_sets = baseline.program.aggregate_metrics["weekly_direct_sets_by_muscle"]["chest"]
    constrained_sets = constrained.program.aggregate_metrics["weekly_direct_sets_by_muscle"][
        "chest"
    ]
    assert constrained_sets < baseline_sets
    assert constrained_target < baseline_target
    assert "VOLUME_CAPPED_FOR_PREVIOUS_VOLUME" in next(
        entry["reasons"]
        for entry in constrained.program.decision_trace
        if entry["stage"] == "volume"
    )
    assert constrained.program.weekly_schedule[0].exercises[0].rest_seconds >= (
        RULESET.minimum_rest_seconds + RULESET.duration_repair_rest_increment_seconds
    )
    assert constrained.program.aggregate_metrics["previous_volume_baseline"]["source"] == (
        "prescribed_plan"
    )
    volume_trace = next(
        entry for entry in constrained.program.decision_trace if entry["stage"] == "volume"
    )
    assert "VOLUME_REDUCED_FOR_RECOVERY" in volume_trace["reasons"]
    assert "VOLUME_CAPPED_FOR_PREVIOUS_VOLUME" in volume_trace["reasons"]


def test_unsafe_template_exercise_is_substituted_and_trace_is_auditable() -> None:
    template, catalog = _upper_lower_reference()
    catalog.append(
        exercise(
            "extra-safe-chest-press",
            MovementPattern.HORIZONTAL_PUSH,
            MuscleGroup.CHEST,
        )
    )
    unsafe_id = template.days[0].slots[0].exercise_id
    assert unsafe_id is not None

    result = generate_program(
        template_request(
            available_training_days=4,
            primary_goal="build_muscle",
            training_experience="intermediate",
            training_age_months=24,
            session_duration_minutes=60,
            blocked_exercises=[unsafe_id],
        ),
        catalog,
        RULESET,
        reference_templates=(template,),
    )

    assert result.program is not None, result.errors
    programmed = [exercise for day in result.program.weekly_schedule for exercise in day.exercises]
    assert unsafe_id not in {exercise.exercise_id for exercise in programmed}
    assert all(
        item.equipment.issubset({Equipment.BODYWEIGHT, Equipment.DUMBBELL, Equipment.PULL_UP_BAR})
        for item in programmed
    )
    assert all(not item.needs_review for item in programmed)
    adaptation_trace = next(
        entry for entry in result.program.decision_trace if entry["stage"] == "template_adaptation"
    )
    assert any(
        item["requested_exercise_id"] == str(unsafe_id)
        for item in adaptation_trace["substitutions"]
    )
    assert adaptation_trace["prescription_changes"]
    quality = result.program.decision_trace[-1]["metrics"]
    assert quality["substitution_count"] >= 1


def test_unadaptable_template_falls_back_to_dynamic_generation_with_trace() -> None:
    base = _four_day_reference()
    unadaptable = TemplateReference(
        slug="unadaptable-repeated-chest-reference",
        days_per_week=4,
        training_level="intermediate",
        fitness_goal="build_muscle",
        focus_tags=("balanced",),
        intensity_methods=("standard",),
        days=(base.days[0],) * 4,
    )

    result = generate_program(
        template_request(
            available_training_days=4,
            primary_goal="build_muscle",
            training_experience="intermediate",
            training_age_months=24,
            session_duration_minutes=60,
        ),
        full_catalog(),
        RULESET,
        reference_templates=(unadaptable,),
    )

    assert result.program is not None, result.errors
    assert result.program.aggregate_metrics.get("reference_template") is None
    rejection = next(
        entry
        for entry in result.program.decision_trace
        if entry["stage"] == "template_reference" and entry.get("status") == "rejected"
    )
    assert rejection["selected"] == unadaptable.slug
    assert rejection["reason_codes"]
    assert "INITIAL_TEMPLATE_REJECTED_UNFILLABLE" in rejection["reason_codes"]
    assert rejection["rejection_category"] == "ADAPTATION_EXHAUSTED"


def test_template_rejection_categories_are_specific_and_stable() -> None:
    assert (
        _template_rejection_category(("TEMPLATE_PRIORITY_HARD_MINIMUM_UNSATISFIED:glutes",))
        == "HARD_PRIORITY_MINIMUM_FAILURE"
    )
    assert (
        _template_rejection_category(("RECOVERY_SPACING_INVALID",))
        == "DURATION_RECOVERY_HARD_IMPOSSIBILITY"
    )
    assert (
        _template_rejection_category(("REQUIRED_MOVEMENT_PATTERN_MISSING",)) == "VALIDATION_FAILURE"
    )
    assert _template_rejection_category(("UNKNOWN_ADAPTATION_FAILURE",)) == "ADAPTATION_EXHAUSTED"


def test_unadaptable_five_day_template_recovers_without_dropping_days() -> None:
    base = _four_day_reference()
    unadaptable = replace(
        base,
        slug="unadaptable-five-day-reference",
        days_per_week=5,
        training_level="intermediate",
        days=tuple(replace(base.days[0], day_number=day_number) for day_number in range(1, 6)),
    )

    result = generate_program(
        template_request(
            available_training_days=5,
            primary_goal="build_muscle",
            training_experience="intermediate",
            training_age_months=24,
            session_duration_minutes=45,
        ),
        full_catalog(),
        RULESET,
        reference_templates=(unadaptable,),
    )

    assert result.program is not None, result.errors
    assert len(result.program.weekly_schedule) == 5
    assert all(day.exercises for day in result.program.weekly_schedule)
    recovery = next(
        entry
        for entry in result.program.decision_trace
        if entry["stage"] == "construction_recovery"
    )
    assert recovery["selected_split"] in {"body_part_rotation", "upper_lower_specialization"}


def test_template_priority_volume_is_repaired_when_safe_capacity_exists() -> None:
    template = _four_day_reference()

    result = generate_program(
        template_request(
            available_training_days=4,
            primary_goal="build_muscle",
            training_experience="intermediate",
            training_age_months=24,
            session_duration_minutes=60,
            priority_muscles=[MuscleGroup.SHOULDERS],
        ),
        full_catalog(),
        RULESET,
        reference_templates=(template,),
    )

    assert result.program is not None, result.errors
    assert result.program.aggregate_metrics.get("reference_template") == template.slug
    repair = next(
        entry for entry in result.program.decision_trace if entry["stage"] == "volume_repair"
    )
    assert "VOLUME_REPAIR_ADDED_EXERCISE_FOR_MINIMUM_COVERAGE" in repair["reasons"]


def test_template_generation_is_deterministic_and_strictly_valid() -> None:
    template, catalog = _upper_lower_reference()
    source = template_request(
        available_training_days=4,
        primary_goal="build_muscle",
        training_experience="intermediate",
        training_age_months=24,
        session_duration_minutes=45,
        priority_muscles=[MuscleGroup.CHEST],
    )

    first = generate_program(source, catalog, RULESET, reference_templates=(template,))
    second = generate_program(source, catalog, RULESET, reference_templates=(template,))

    assert first.program is not None, first.errors
    assert second.program is not None, second.errors
    assert first.program == second.program
    assert first.program.validation_report.is_valid
    assert all(
        day.estimated_duration_minutes - RULESET.general_warmup_minutes
        <= source.session_duration_minutes + 10
        for day in first.program.weekly_schedule
    )
    primary_by_id = {candidate.id: candidate.primary_muscle for candidate in catalog}
    original_chest_sets = sum(
        slot.sets
        for day in template.days
        for slot in day.slots
        if primary_by_id.get(slot.exercise_id) is MuscleGroup.CHEST
    )
    assert (
        first.program.aggregate_metrics["planned_direct_sets_by_muscle"]["chest"]
        != original_chest_sets
    )


def test_template_with_adjacent_direct_muscle_overlap_is_rearranged() -> None:
    template, catalog = _upper_lower_reference()
    unsafe = replace(
        template,
        slug="adjacent-upper-lower-reference",
        days=(template.days[0], template.days[2], template.days[1], template.days[3]),
    )

    result = generate_program(
        template_request(
            available_training_days=4,
            primary_goal="build_muscle",
            training_experience="intermediate",
            training_age_months=24,
            session_duration_minutes=60,
        ),
        catalog,
        RULESET,
        reference_templates=(unsafe,),
    )

    assert result.program is not None, result.errors
    assert result.program.aggregate_metrics.get("reference_template") == unsafe.slug
    assert "RECOVERY_WEEKDAYS_REARRANGED_FOR_DIRECT_MUSCLE_OVERLAP" in (
        result.program.split.reason_codes
    )


def test_template_with_alternating_direct_muscles_keeps_valid_recovery_spacing() -> None:
    template, catalog = _upper_lower_reference()

    result = generate_program(
        template_request(
            available_training_days=4,
            primary_goal="build_muscle",
            training_experience="intermediate",
            training_age_months=24,
            session_duration_minutes=60,
        ),
        catalog,
        RULESET,
        reference_templates=(template,),
    )

    assert result.program is not None, result.errors
    assert result.program.aggregate_metrics["reference_template"] == template.slug
    assert result.program.validation_report.is_valid


def test_intentional_repeated_safe_template_core_is_preserved_deterministically() -> None:
    template, catalog = _repeated_core_reference()
    repeated_id = template.days[0].slots[0].exercise_id
    source = template_request(
        available_training_days=4,
        primary_goal="build_muscle",
        training_experience="intermediate",
        training_age_months=24,
        session_duration_minutes=60,
    )

    first = generate_program(source, catalog, RULESET, reference_templates=(template,))
    second = generate_program(source, catalog, RULESET, reference_templates=(template,))

    assert first.program is not None, first.errors
    assert second.program is not None, second.errors
    assert first.program == second.program
    occurrences = [
        item
        for day in first.program.weekly_schedule
        for item in day.exercises
        if item.exercise_id == repeated_id
    ]
    assert len(occurrences) == 2
    assert "CORE_MOVEMENT_REPEATED_FOR_PROGRESSION" in occurrences[1].reason_codes
    assert first.program.validation_report.is_valid


def test_repeated_blocked_template_core_uses_distinct_safe_substitutions() -> None:
    template, catalog = _repeated_core_reference()
    repeated_id = template.days[0].slots[0].exercise_id
    assert repeated_id is not None
    catalog.append(
        exercise(
            "extra-repeat-safe-chest-press",
            MovementPattern.HORIZONTAL_PUSH,
            MuscleGroup.CHEST,
        )
    )

    result = generate_program(
        template_request(
            available_training_days=4,
            primary_goal="build_muscle",
            training_experience="intermediate",
            training_age_months=24,
            session_duration_minutes=60,
            blocked_exercises=[repeated_id],
        ),
        catalog,
        RULESET,
        reference_templates=(template,),
    )

    assert result.program is not None, result.errors
    assert result.program.aggregate_metrics["reference_template"] == template.slug
    programmed_ids = [
        item.exercise_id for day in result.program.weekly_schedule for item in day.exercises
    ]
    assert repeated_id not in programmed_ids
    adaptation_trace = next(
        entry for entry in result.program.decision_trace if entry["stage"] == "template_adaptation"
    )
    substitutions = [
        item
        for item in adaptation_trace["substitutions"]
        if item["requested_exercise_id"] == str(repeated_id)
    ]
    assert len(substitutions) == 2
    assert len({item["selected_exercise_id"] for item in substitutions}) == 2
