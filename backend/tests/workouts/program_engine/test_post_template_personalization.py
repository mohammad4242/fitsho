from dataclasses import replace
from uuid import uuid4

from app.exercises.enums import Equipment, MovementPattern, MuscleGroup
from app.workouts.program_engine.eligibility import filter_eligible_exercises
from app.workouts.program_engine.engine import generate_program
from app.workouts.program_engine.enums import Goal
from app.workouts.program_engine.normalization import normalize_request
from app.workouts.program_engine.prescription import prescribe_sessions
from app.workouts.program_engine.priority_allocation import PriorityAllocationPolicy
from app.workouts.program_engine.rulesets.resistance_training_v1 import RULESET
from app.workouts.program_engine.schemas import (
    BodyAnalysisInfluence,
    SessionDraft,
    TemplateReference,
    TemplateReferenceDay,
    TemplateReferenceSlot,
    VolumeTarget,
    WeeklyVolumePlan,
)
from app.workouts.program_engine.session_duration import repair_session_durations
from app.workouts.program_engine.split_selector import select_split
from app.workouts.program_engine.template_sessions import build_template_sessions
from app.workouts.program_engine.volume_planner import plan_weekly_volume
from tests.workouts.program_engine.golden_fixtures import exercise, full_catalog, request
from tests.workouts.program_engine.test_template_reference import (
    _upper_lower_reference,
    template_request,
)


def _body_analysis_priorities() -> BodyAnalysisInfluence:
    return BodyAnalysisInfluence.model_validate(
        {
            "analysis_id": uuid4(),
            "result_version_id": uuid4(),
            "analysis_revision": 1,
            "schema_version": "1.0",
            "source": "fully_reviewed",
            "overall_confidence": 0.95,
            "priorities": (
                {
                    "muscle": MuscleGroup.BICEPS,
                    "classification": "mild_lag",
                    "confidence": 0.9,
                    "severity": 0.5,
                },
                {
                    "muscle": MuscleGroup.GLUTES,
                    "classification": "clear_lag",
                    "confidence": 0.9,
                    "severity": 0.9,
                },
            ),
        }
    )


def test_priority_policy_preserves_explicit_then_clear_then_mild_precedence() -> None:
    normalized = normalize_request(
        request(
            priority_muscles=[MuscleGroup.TRICEPS],
            body_analysis_influence=_body_analysis_priorities(),
        ),
        RULESET,
    )

    policy = PriorityAllocationPolicy.for_request(normalized, RULESET)

    assert policy.priorities == (
        MuscleGroup.TRICEPS,
        MuscleGroup.GLUTES,
        MuscleGroup.BICEPS,
    )


def test_template_slot_resolution_uses_profile_ranking_not_catalog_order() -> None:
    original = exercise("blocked-original", MovementPattern.HORIZONTAL_PUSH, MuscleGroup.CHEST)
    preferred = exercise("preferred-press", MovementPattern.HORIZONTAL_PUSH, MuscleGroup.CHEST)
    fallback = exercise("fallback-press", MovementPattern.HORIZONTAL_PUSH, MuscleGroup.CHEST)
    core = exercise("core", MovementPattern.CORE_ANTI_EXTENSION, MuscleGroup.ABS)
    source = request(
        available_training_days=1,
        blocked_exercises=[original.id],
        preferred_exercises=[preferred.id],
    )
    normalized = normalize_request(source, RULESET)
    catalog = (fallback, preferred, original, core)
    eligible = filter_eligible_exercises(normalized, catalog).eligible
    template = TemplateReference(
        slug="ranked-resolution",
        days_per_week=1,
        supported_levels=(source.training_experience.value,),
        focus_tags=("balanced",),
        intensity_methods=("standard",),
        days=(
            TemplateReferenceDay(
                day_number=1,
                title="Push",
                focus=(MuscleGroup.CHEST,),
                slots=(
                    TemplateReferenceSlot(
                        exercise_id=original.id,
                        exercise_slug_hint="blocked-original",
                        target_muscles=(MuscleGroup.CHEST,),
                        movement_pattern=MovementPattern.HORIZONTAL_PUSH,
                        intensity_method="standard",
                        adaptation_priority="core",
                        superset_group=None,
                        superset_exercise_id=None,
        superset_exercise_slug_hint=None,
        sets=3,
                        rep_min=8,
                        rep_max=12,
                        target_rir=2,
                        rest_seconds=90,
                    ),
                ),
            ),
        ),
    )

    build = build_template_sessions(
        normalized,
        template,
        eligible,
        replace(RULESET, minimum_exercises_per_session=1),
        exercise_catalog=catalog,
    )

    assert build.drafts[0].exercises[0].id == preferred.id


def test_initial_prescription_consumes_planned_direct_set_allocations() -> None:
    chest = tuple(
        candidate for candidate in full_catalog() if candidate.primary_muscle is MuscleGroup.CHEST
    )[:3]
    normalized = normalize_request(
        request(available_training_days=3, session_duration_minutes=60), RULESET
    )
    drafts = tuple(
        SessionDraft(
            day_index=index,
            weekday=(index - 1) * 2,
            focus=f"template_reference_{index}",
            exercises=[candidate],
            selection_reasons={candidate.id: ("TEMPLATE_ADAPTATION_PRIORITY:core",)},
            substitutions={candidate.id: ()},
        )
        for index, candidate in enumerate(chest, start=1)
    )
    volume = WeeklyVolumePlan(
        targets=(
            VolumeTarget(
                muscle=MuscleGroup.CHEST,
                minimum_soft=8,
                target_sets=10,
                maximum_soft=12,
                maximum_hard=12,
                fractional_sets=5,
                effective_target_sets=10,
                minimum_direct_sets=8,
            ),
        ),
        reason_codes=(),
    )

    days = prescribe_sessions(
        normalized,
        drafts,
        volume,
        RULESET,
    )

    assert [day.exercises[0].sets for day in days] == [4, 3, 3]


def test_compact_strength_session_preserves_primary_compound_rest() -> None:
    candidate = next(item for item in full_catalog() if item.name == "Dumbbell Press")
    normalized = normalize_request(
        request(
            primary_goal=Goal.STRENGTH,
            training_experience="advanced",
            training_age_months=72,
            available_training_days=1,
            session_duration_minutes=30,
            available_equipment=[Equipment.BODYWEIGHT, Equipment.DUMBBELL],
        ),
        RULESET,
    )
    draft = SessionDraft(
        day_index=1,
        weekday=0,
        focus="template_reference_1",
        exercises=[candidate],
        selection_reasons={candidate.id: ("TEMPLATE_ADAPTATION_PRIORITY:core",)},
        substitutions={candidate.id: ()},
    )
    volume = WeeklyVolumePlan(
        targets=(
            VolumeTarget(
                muscle=MuscleGroup.CHEST,
                minimum_soft=3,
                target_sets=4,
                maximum_soft=6,
                maximum_hard=8,
                fractional_sets=2,
                effective_target_sets=4,
                minimum_direct_sets=3,
            ),
        ),
        reason_codes=(),
    )

    day = prescribe_sessions(
        normalized,
        (draft,),
        volume,
        RULESET,
    )[0]

    assert (
        day.exercises[0].rest_seconds
        == RULESET.prescription_rules["strength_compound"].rest_seconds
    )


def test_duration_repair_reduces_template_accessory_before_core() -> None:
    source = request(available_training_days=1, session_duration_minutes=30)
    normalized = normalize_request(source, RULESET)
    base = generate_program(
        source.model_copy(update={"session_duration_minutes": 60}),
        full_catalog(),
        RULESET,
    )
    assert base.program is not None, base.errors
    original = base.program.weekly_schedule[0]
    core = replace(
        original.exercises[0],
        sets=4,
        rest_seconds=300,
        estimated_minutes=25,
        reason_codes=("TEMPLATE_ADAPTATION_PRIORITY:core",),
    )
    accessory = replace(
        original.exercises[1],
        sets=4,
        rest_seconds=300,
        estimated_minutes=20,
        reason_codes=("TEMPLATE_ADAPTATION_PRIORITY:accessory",),
    )
    overfilled = replace(
        original,
        focus="template_reference_1",
        exercises=(core, accessory),
        estimated_duration_minutes=50,
        cardio=None,
    )

    repaired, _ = repair_session_durations((overfilled,), normalized, (), RULESET)

    repaired_by_id = {item.exercise_id: item for item in repaired[0].exercises}
    assert repaired_by_id[core.exercise_id].sets == 4
    assert (
        accessory.exercise_id not in repaired_by_id
        or repaired_by_id[accessory.exercise_id].sets < accessory.sets
    )


def test_duration_repair_reduces_non_priority_before_explicit_priority() -> None:
    source = request(
        available_training_days=1,
        session_duration_minutes=30,
        priority_muscles=[MuscleGroup.CHEST],
    )
    normalized = normalize_request(source, RULESET)
    base = generate_program(
        source.model_copy(update={"session_duration_minutes": 60}),
        full_catalog(),
        RULESET,
    )
    assert base.program is not None, base.errors
    original = base.program.weekly_schedule[0]
    priority_ex = replace(
        original.exercises[0],
        sets=4,
        rest_seconds=300,
        estimated_minutes=25,
        primary_muscle=MuscleGroup.CHEST,
        reason_codes=("PRIORITY_TARGET_PARTIALLY_SATISFIED",),
    )
    non_priority_ex = replace(
        original.exercises[1],
        sets=4,
        rest_seconds=300,
        estimated_minutes=25,
        primary_muscle=MuscleGroup.BICEPS,
        reason_codes=(),
    )
    overfilled = replace(
        original,
        focus="template_reference_1",
        exercises=(priority_ex, non_priority_ex),
        estimated_duration_minutes=55,
        cardio=None,
    )

    repaired, _ = repair_session_durations((overfilled,), normalized, (), RULESET)

    repaired_by_id = {item.exercise_id: item for item in repaired[0].exercises}
    assert priority_ex.exercise_id in repaired_by_id
    priority_sets = repaired_by_id[priority_ex.exercise_id].sets
    non_priority_sets = (
        repaired_by_id[non_priority_ex.exercise_id].sets
        if non_priority_ex.exercise_id in repaired_by_id
        else 0
    )
    assert priority_sets > non_priority_sets


def test_same_template_strength_and_hypertrophy_have_role_specific_prescriptions() -> None:
    template, catalog = _upper_lower_reference()
    common = {
        "available_training_days": 4,
        "training_experience": "intermediate",
        "training_age_months": 30,
        "session_duration_minutes": 30,
    }

    hypertrophy = generate_program(
        template_request(primary_goal=Goal.HYPERTROPHY, **common),
        catalog,
        RULESET,
        reference_templates=(template,),
    )
    strength = generate_program(
        template_request(primary_goal=Goal.STRENGTH, **common),
        catalog,
        RULESET,
        reference_templates=(template,),
    )

    assert hypertrophy.program is not None, hypertrophy.errors
    assert strength.program is not None, strength.errors
    assert hypertrophy.program.aggregate_metrics["reference_template"] == template.slug
    assert strength.program.aggregate_metrics["reference_template"] == template.slug
    hypertrophy_first = hypertrophy.program.weekly_schedule[0].exercises[0]
    strength_first = strength.program.weekly_schedule[0].exercises[0]
    assert (strength_first.rep_min, strength_first.rest_seconds) != (
        hypertrophy_first.rep_min,
        hypertrophy_first.rest_seconds,
    )
    assert all(
        item.rest_seconds <= RULESET.prescription_rules["strength_isolation"].maximum_rest_seconds
        for day in strength.program.weekly_schedule
        for item in day.exercises
        if item.exercise_type.value == "isolation"
    )
    assert all(
        len(item.reason_codes) == len(set(item.reason_codes))
        for day in strength.program.weekly_schedule
        for item in day.exercises
    )


def test_same_template_gives_explicit_chest_priority_more_final_direct_volume() -> None:
    template, catalog = _upper_lower_reference()
    common = {
        "available_training_days": 4,
        "primary_goal": "build_muscle",
        "training_experience": "intermediate",
        "training_age_months": 24,
        "session_duration_minutes": 30,
    }
    balanced = generate_program(
        template_request(**common),
        catalog,
        RULESET,
        reference_templates=(template,),
    )
    prioritized = generate_program(
        template_request(**common, priority_muscles=[MuscleGroup.CHEST]),
        catalog,
        RULESET,
        reference_templates=(template,),
    )

    assert balanced.program is not None, balanced.errors
    assert prioritized.program is not None, prioritized.errors
    assert balanced.program.aggregate_metrics["reference_template"] == template.slug
    assert prioritized.program.aggregate_metrics["reference_template"] == template.slug
    balanced_chest = balanced.program.aggregate_metrics["weekly_direct_sets_by_muscle"][
        MuscleGroup.CHEST.value
    ]
    priority_chest = prioritized.program.aggregate_metrics["weekly_direct_sets_by_muscle"][
        MuscleGroup.CHEST.value
    ]
    balanced_target = balanced.program.aggregate_metrics["volume_ranges_by_muscle"]["chest"][
        "target_sets"
    ]
    priority_target = prioritized.program.aggregate_metrics["volume_ranges_by_muscle"]["chest"][
        "target_sets"
    ]
    assert priority_target > balanced_target
    assert priority_chest >= balanced_chest
    assert (
        prioritized.program.aggregate_metrics["volume_ranges_by_muscle"]["chest"]["status"]
        == "exact_target"
    )


def test_explicit_chest_priority_dominates_conflicting_body_analysis_lag() -> None:
    source = request(
        primary_goal="build_muscle",
        training_experience="advanced",
        training_age_months=72,
        available_training_days=4,
        session_duration_minutes=60,
        priority_muscles=[MuscleGroup.CHEST],
        body_analysis_influence=_body_analysis_priorities(),
    )

    result = generate_program(source, full_catalog(), RULESET)

    assert result.program is not None, result.errors
    ranges = result.program.aggregate_metrics["volume_ranges_by_muscle"]
    priority_metrics = result.program.aggregate_metrics["priority_metrics"]
    assert ranges[MuscleGroup.CHEST.value]["direct_minimum_required"] is True
    assert ranges[MuscleGroup.GLUTES.value]["direct_minimum_required"] is False
    assert (
        ranges[MuscleGroup.CHEST.value]["actual_direct_volume"]
        > ranges[MuscleGroup.GLUTES.value]["actual_direct_volume"]
    )
    assert priority_metrics[MuscleGroup.CHEST.value]["status"] in {"satisfied", "partial"}


def test_clear_body_lag_has_stronger_volume_target_than_mild_lag() -> None:
    normalized = normalize_request(
        request(
            primary_goal="build_muscle",
            training_experience="intermediate",
            training_age_months=24,
            available_training_days=4,
            session_duration_minutes=60,
            body_analysis_influence=_body_analysis_priorities(),
        ),
        RULESET,
    )

    plan = plan_weekly_volume(normalized, select_split(normalized, RULESET), RULESET)

    assert plan.direct_sets_for(MuscleGroup.GLUTES) > plan.direct_sets_for(MuscleGroup.BICEPS)
