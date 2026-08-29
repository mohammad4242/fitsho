from dataclasses import replace

import pytest

from app.exercises.enums import MuscleGroup
from app.training_templates.tags import TemplateFocusTag
from app.workouts.program_engine.enums import Goal, TrainingExperience
from app.workouts.program_engine.normalization import normalize_request
from app.workouts.program_engine.rulesets.resistance_training_v1 import RULESET
from app.workouts.program_engine.schemas import TemplateReference
from app.workouts.program_engine.template_scoring import (
    TemplateScore,
    score_template_reference_result,
)
from app.workouts.program_engine.template_selector import (
    rank_template_references,
    select_template_reference_result,
)
from tests.workouts.program_engine.golden_fixtures import full_catalog, request


def _template(
    slug: str,
    *focus_tags: TemplateFocusTag,
    days_per_week: int = 4,
    training_level: str = "intermediate",
) -> TemplateReference:
    return TemplateReference(
        slug=slug,
        days_per_week=days_per_week,
        supported_levels=(training_level,),
        focus_tags=focus_tags,
        intensity_methods=("standard",),
        days=(),
    )


def _normalized(*, days: int, experience: TrainingExperience):
    return normalize_request(
        request(
            primary_goal=Goal.HYPERTROPHY,
            training_experience=experience,
            training_age_months=60,
            available_training_days=days,
            session_duration_minutes=60,
        ),
        RULESET,
    )


@pytest.mark.parametrize(
    "experience", [TrainingExperience.INTERMEDIATE, TrainingExperience.ADVANCED]
)
@pytest.mark.parametrize("days", [4, 5, 6])
def test_professional_topology_tiers_apply_only_to_normalized_professional_scope(
    experience: TrainingExperience, days: int
) -> None:
    normalized = _normalized(days=days, experience=experience)
    templates = (
        _template("tagless", days_per_week=days),
        _template("upper-lower", TemplateFocusTag.UPPER_LOWER, days_per_week=days),
        _template(
            "ppl-upper-lower",
            TemplateFocusTag.PUSH_PULL_LEGS,
            TemplateFocusTag.UPPER_LOWER,
            days_per_week=days,
        ),
        _template("ppl", TemplateFocusTag.PUSH_PULL_LEGS, days_per_week=days),
        _template("body-part", TemplateFocusTag.BODY_PART_ROTATION, days_per_week=days),
    )

    results = [
        score_template_reference_result(normalized, template, RULESET) for template in templates
    ]

    assert [result.score.professional_structure_score for result in results] == [0, 0, 30, 40, 50]
    assert results[2].reason_codes == ("PROFESSIONAL_TOPOLOGY_HYBRID_PREFERENCE",)
    assert results[3].reason_codes == ("PROFESSIONAL_TOPOLOGY_PPL_PREFERENCE",)
    assert results[4].reason_codes == ("PROFESSIONAL_TOPOLOGY_BODY_PART_PREFERENCE",)


def test_matching_specialization_is_a_sixty_point_tier_and_nonmatch_keeps_body_part_tier() -> None:
    normalized = _normalized(days=5, experience=TrainingExperience.INTERMEDIATE)
    matching = _template(
        "matching",
        TemplateFocusTag.BODY_PART_ROTATION,
        TemplateFocusTag.ARMS_PRIORITY,
        TemplateFocusTag.SPECIALIZATION,
        days_per_week=5,
    )
    nonmatching = _template(
        "nonmatching",
        TemplateFocusTag.BODY_PART_ROTATION,
        TemplateFocusTag.CHEST_PRIORITY,
        TemplateFocusTag.SPECIALIZATION,
        days_per_week=5,
    )

    priority_request = replace(
        normalized,
        source=normalized.source.model_copy(update={"priority_muscles": [MuscleGroup.BICEPS]}),
    )
    matching_result = score_template_reference_result(
        priority_request,
        matching,
        RULESET,
    )
    nonmatching_result = score_template_reference_result(
        priority_request,
        nonmatching,
        RULESET,
    )

    assert matching_result.score.professional_structure_score == 60
    assert matching_result.reason_codes == (
        "EXPLICIT_PRIORITY_EXACT_MATCH",
        "SEX_PRIOR_DISABLED_BY_EXPLICIT_PRIORITY",
        "PROFESSIONAL_TOPOLOGY_MATCHING_SPECIALIZATION_PREFERENCE",
    )
    assert nonmatching_result.score.professional_structure_score == 50
    assert "PROFESSIONAL_TOPOLOGY_BODY_PART_PREFERENCE" in nonmatching_result.reason_codes


def test_template_score_and_trace_include_professional_structure_in_six_component_total() -> None:
    normalized = _normalized(days=4, experience=TrainingExperience.INTERMEDIATE)
    template = _template("body-part", TemplateFocusTag.BODY_PART_ROTATION, days_per_week=4)
    score = score_template_reference_result(normalized, template, RULESET).score
    selection = select_template_reference_result(
        normalized, tuple(full_catalog()), (template,), RULESET
    )
    score_trace = selection.decision_trace()["candidates"][0]["score"]

    assert score == TemplateScore(0, 0, 0, 0, 0, 50)
    assert score.total == 50
    assert score_trace["professional_structure"] == 50
    assert score_trace["total"] == sum(
        score_trace[key]
        for key in (
            "priority",
            "body_analysis",
            "goal",
            "sex",
            "fallback",
            "professional_structure",
        )
    )


def test_professional_structure_ranks_above_generic_upper_lower_without_rejecting_it() -> None:
    normalized = _normalized(days=5, experience=TrainingExperience.ADVANCED)
    upper_lower = _template(
        "upper-lower", TemplateFocusTag.UPPER_LOWER, days_per_week=5, training_level="advanced"
    )
    professional = _template(
        "body-part", TemplateFocusTag.BODY_PART_ROTATION, days_per_week=5, training_level="advanced"
    )

    ranked = rank_template_references(
        normalized, tuple(full_catalog()), (upper_lower, professional), RULESET
    )
    selection = select_template_reference_result(
        normalized, tuple(full_catalog()), (upper_lower, professional), RULESET
    )

    assert tuple(item.template for item in ranked) == (professional, upper_lower)
    assert {item.template for item in selection.candidates} == {upper_lower, professional}
    assert all(rejection.slug != upper_lower.slug for rejection in selection.hard_rejections)
