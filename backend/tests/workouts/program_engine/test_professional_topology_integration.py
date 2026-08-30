from dataclasses import replace

import pytest

from app.exercises.enums import Equipment, MovementPattern, MuscleGroup
from app.profile.enums import TrainingLocation
from app.training_templates.tags import TemplateFocusTag
from app.workouts.program_engine.duration_capacity import build_session_capacity
from app.workouts.program_engine.engine import generate_program
from app.workouts.program_engine.enums import Goal, SplitType, TrainingExperience
from app.workouts.program_engine.normalization import normalize_request
from app.workouts.program_engine.rulesets.resistance_training_v1 import RULESET
from app.workouts.program_engine.schemas import (
    TemplateReference,
    TemplateReferenceDay,
    TemplateReferenceSlot,
)
from app.workouts.program_engine.split_selector import rank_split_candidates
from tests.workouts.program_engine.golden_fixtures import full_catalog, request


def _normalized(*, days: int, experience: TrainingExperience, **overrides: object):
    values: dict[str, object] = {
        "primary_goal": Goal.HYPERTROPHY,
        "training_experience": experience,
        "training_age_months": 60,
        "available_training_days": days,
        "session_duration_minutes": 60,
    }
    values.update(overrides)
    return normalize_request(request(**values), RULESET)


def _slot(pattern: MovementPattern, muscle: MuscleGroup, *, priority: str = "core"):
    return TemplateReferenceSlot(
        exercise_id=None,
        exercise_slug_hint=pattern.value,
        target_muscles=(muscle,),
        movement_pattern=pattern,
        intensity_method="standard",
        adaptation_priority=priority,
        superset_group=None,
        superset_exercise_id=None,
        superset_exercise_slug_hint=None,
        sets=3,
        rep_min=8,
        rep_max=12,
        target_rir=2,
        rest_seconds=90,
    )


def _reference(
    slug: str,
    tags: tuple[TemplateFocusTag, ...],
    *,
    days_per_week: int = 4,
    level: str = "intermediate",
    empty: bool = False,
) -> TemplateReference:
    days = ()
    if not empty:
        days = (
            TemplateReferenceDay(
                1,
                "Chest",
                (MuscleGroup.CHEST,),
                (
                    _slot(MovementPattern.HORIZONTAL_PUSH, MuscleGroup.CHEST),
                    _slot(
                        MovementPattern.VERTICAL_PUSH,
                        MuscleGroup.SHOULDERS,
                        priority="accessory",
                    ),
                    _slot(
                        MovementPattern.ELBOW_EXTENSION,
                        MuscleGroup.TRICEPS,
                        priority="accessory",
                    ),
                ),
            ),
            TemplateReferenceDay(
                2,
                "Back",
                (MuscleGroup.BACK,),
                (
                    _slot(MovementPattern.HORIZONTAL_PULL, MuscleGroup.BACK),
                    _slot(
                        MovementPattern.VERTICAL_PULL,
                        MuscleGroup.BACK,
                        priority="accessory",
                    ),
                    _slot(
                        MovementPattern.ELBOW_FLEXION,
                        MuscleGroup.BICEPS,
                        priority="accessory",
                    ),
                ),
            ),
            TemplateReferenceDay(
                3,
                "Lower",
                (MuscleGroup.QUADRICEPS, MuscleGroup.HAMSTRINGS),
                (
                    _slot(MovementPattern.SQUAT, MuscleGroup.QUADRICEPS),
                    _slot(MovementPattern.HIP_HINGE, MuscleGroup.HAMSTRINGS),
                    _slot(
                        MovementPattern.CALF_RAISE,
                        MuscleGroup.CALVES,
                        priority="accessory",
                    ),
                ),
            ),
            TemplateReferenceDay(
                4,
                "Shoulders",
                (MuscleGroup.SHOULDERS,),
                (
                    _slot(MovementPattern.VERTICAL_PUSH, MuscleGroup.SHOULDERS),
                    _slot(
                        MovementPattern.SHOULDER_ABDUCTION,
                        MuscleGroup.SHOULDERS,
                        priority="accessory",
                    ),
                    _slot(
                        MovementPattern.SHRUG,
                        MuscleGroup.TRAPS,
                        priority="accessory",
                    ),
                ),
            ),
        )
    return TemplateReference(
        slug=slug,
        days_per_week=days_per_week,
        supported_levels=(level,),
        focus_tags=tags,
        intensity_methods=("standard",),
        days=days,
    )


@pytest.mark.parametrize(
    "experience", [TrainingExperience.INTERMEDIATE, TrainingExperience.ADVANCED]
)
@pytest.mark.parametrize("days", [4, 5, 6])
def test_professional_dynamic_topology_outranks_generic_upper_lower(
    experience: TrainingExperience, days: int
) -> None:
    normalized = _normalized(days=days, experience=experience)
    ranked = rank_split_candidates(normalized, RULESET)
    by_type = {candidate.split_type: candidate for candidate in ranked}

    upper = next(
        (
            by_type[split_type]
            for split_type in (
                SplitType.UPPER_LOWER,
                SplitType.UPPER_LOWER_SPECIALIZATION,
                SplitType.UPPER_LOWER_X3,
            )
            if split_type in by_type
        ),
        None,
    )
    assert upper is not None

    if days == 4:
        body_part = by_type[SplitType.BODY_PART_ROTATION]
        assert body_part.score > upper.score
        assert "PROFESSIONAL_TOPOLOGY_BODY_PART_PREFERENCE" in body_part.reason_codes
    elif days == 5:
        hybrid = by_type[SplitType.PUSH_PULL_LEGS_UPPER_LOWER]
        body_part = by_type[SplitType.BODY_PART_ROTATION]
        assert hybrid.score > upper.score
        assert body_part.score > hybrid.score
        assert "PROFESSIONAL_TOPOLOGY_HYBRID_PREFERENCE" in hybrid.reason_codes
        assert "PROFESSIONAL_TOPOLOGY_BODY_PART_PREFERENCE" in body_part.reason_codes
    else:
        ppl = by_type[SplitType.PUSH_PULL_LEGS_X2]
        body_part = by_type[SplitType.BODY_PART_ROTATION]
        assert ppl.score > upper.score
        assert body_part.score > upper.score
        assert "PROFESSIONAL_TOPOLOGY_PPL_PREFERENCE" in ppl.reason_codes
        assert "PROFESSIONAL_TOPOLOGY_BODY_PART_PREFERENCE" in body_part.reason_codes


def test_dynamic_professional_body_part_tier_replaces_legacy_bonus_in_scope() -> None:
    normalized = _normalized(days=5, experience=TrainingExperience.INTERMEDIATE)
    without_legacy = replace(RULESET, body_part_rotation_bonus=0)
    with_legacy = replace(RULESET, body_part_rotation_bonus=999)

    body_without = next(
        item
        for item in rank_split_candidates(normalized, without_legacy)
        if item.split_type is SplitType.BODY_PART_ROTATION
    )
    body_with = next(
        item
        for item in rank_split_candidates(normalized, with_legacy)
        if item.split_type is SplitType.BODY_PART_ROTATION
    )

    assert body_with.score == body_without.score


def test_legacy_body_part_bonus_remains_unchanged_outside_professional_scope() -> None:
    normalized = _normalized(days=4, experience=TrainingExperience.BEGINNER)
    without_legacy = replace(RULESET, body_part_rotation_bonus=0)
    with_legacy = replace(RULESET, body_part_rotation_bonus=RULESET.body_part_rotation_bonus)

    body_without = next(
        item
        for item in rank_split_candidates(normalized, without_legacy)
        if item.split_type is SplitType.BODY_PART_ROTATION
    )
    body_with = next(
        item
        for item in rank_split_candidates(normalized, with_legacy)
        if item.split_type is SplitType.BODY_PART_ROTATION
    )

    assert body_with.score - body_without.score == RULESET.body_part_rotation_bonus


def test_duration_infeasibility_remains_a_sort_key_before_professional_score() -> None:
    normalized = _normalized(days=4, experience=TrainingExperience.INTERMEDIATE)
    catalog = tuple(
        item for item in full_catalog() if item.primary_muscle is not MuscleGroup.SHOULDERS
    )
    capacity = build_session_capacity(normalized, catalog, RULESET)
    ranked = rank_split_candidates(
        normalized,
        RULESET,
        exercises=catalog,
        session_capacity=capacity,
    )
    body_part_index = next(
        index
        for index, item in enumerate(ranked)
        if item.split_type is SplitType.BODY_PART_ROTATION
    )
    upper_lower_index = next(
        index for index, item in enumerate(ranked) if item.split_type is SplitType.UPPER_LOWER
    )
    body_part = ranked[body_part_index]
    upper_lower = ranked[upper_lower_index]

    assert body_part.score > upper_lower.score
    assert "SPLIT_DURATION_CAPACITY_INFEASIBLE" in body_part.reason_codes
    assert "SPLIT_DURATION_CAPACITY_COMFORTABLE" in upper_lower.reason_codes
    assert body_part_index > upper_lower_index


def test_generate_program_ranks_and_attempts_feasible_professional_reference_first() -> None:
    source = request(
        primary_goal=Goal.HYPERTROPHY,
        training_experience=TrainingExperience.INTERMEDIATE,
        training_age_months=24,
        available_training_days=4,
        session_duration_minutes=45,
        available_equipment=[Equipment.BODYWEIGHT, Equipment.DUMBBELL],
        training_location=TrainingLocation.HOME,
    )
    generic = _reference("z-generic-upper-lower", (TemplateFocusTag.UPPER_LOWER,))
    professional = _reference("a-professional-body-part", (TemplateFocusTag.BODY_PART_ROTATION,))

    result = generate_program(
        source,
        full_catalog(),
        RULESET,
        reference_templates=(generic, professional),
    )

    assert result.program is not None, result.errors
    selection = result.program.decision_trace[0]
    assert selection["stage"] == "template_selection"
    assert selection["candidates"][0]["slug"] == professional.slug
    assert selection["selected"] == professional.slug
    attempt = next(
        item for item in result.program.decision_trace if item.get("stage") == "template_attempt"
    )
    assert attempt["slug"] == professional.slug
    assert attempt["rank"] == 1
    assert attempt["status"] == "succeeded"
    assert attempt["post_construction_feasibility"]["status"] in {
        "comfortably_feasible",
        "repairable",
        "tight",
    }
    assert attempt["post_construction_feasibility"]["hard_reason_codes"] == ()
    assert result.program.aggregate_metrics["reference_template"] == professional.slug


def test_generate_program_keeps_upper_lower_when_professional_reference_is_ineligible() -> None:
    source = request(
        primary_goal=Goal.HYPERTROPHY,
        training_experience=TrainingExperience.INTERMEDIATE,
        training_age_months=24,
        available_training_days=4,
        session_duration_minutes=45,
    )
    generic = _reference("generic-upper-lower", (TemplateFocusTag.UPPER_LOWER,))
    professional = _reference(
        "professional-five-day-body-part",
        (TemplateFocusTag.BODY_PART_ROTATION,),
        days_per_week=5,
    )

    result = generate_program(
        source,
        full_catalog(),
        RULESET,
        reference_templates=(professional, generic),
    )

    assert result.program is not None, result.errors
    selection = result.program.decision_trace[0]
    assert selection["selected"] == generic.slug
    rejection = next(
        item for item in selection["hard_rejections"] if item["slug"] == professional.slug
    )
    assert "DAYS_MISMATCH" in rejection["reason_codes"]
    assert result.program.aggregate_metrics["reference_template"] == generic.slug


def test_generate_program_falls_back_to_generic_after_professional_construction_failure() -> None:
    source = request(
        primary_goal=Goal.HYPERTROPHY,
        training_experience=TrainingExperience.INTERMEDIATE,
        training_age_months=24,
        available_training_days=4,
        session_duration_minutes=45,
    )
    generic = _reference("z-generic-upper-lower", (TemplateFocusTag.UPPER_LOWER,))
    professional = _reference(
        "a-professional-unfillable-body-part",
        (TemplateFocusTag.BODY_PART_ROTATION,),
        empty=True,
    )

    result = generate_program(
        source,
        full_catalog(),
        RULESET,
        reference_templates=(professional, generic),
    )

    assert result.program is not None, result.errors
    selection = result.program.decision_trace[0]
    assert selection["candidates"][0]["slug"] == professional.slug
    attempts = [
        item for item in result.program.decision_trace if item.get("stage") == "template_attempt"
    ]
    assert attempts[0]["slug"] == professional.slug
    assert attempts[0]["status"] == "rejected"
    assert (
        attempts[0]["post_construction_feasibility"]["status"]
        == "provably_infeasible"
    )
    assert attempts[1]["slug"] == generic.slug
    assert attempts[1]["status"] == "succeeded"
    assert result.program.aggregate_metrics["reference_template"] == generic.slug
