from dataclasses import replace
from uuid import uuid4

from app.exercises.enums import MovementPattern, MuscleGroup
from app.training_templates.tags import TemplateFocusTag
from app.workouts.program_engine.enums import Goal, TrainingExperience
from app.workouts.program_engine.normalization import normalize_request
from app.workouts.program_engine.rulesets.resistance_training_v1 import RULESET
from app.workouts.program_engine.schemas import (
    BodyAnalysisInfluence,
    TemplateReference,
    TemplateReferenceDay,
    TemplateReferenceSlot,
)
from app.workouts.program_engine.template_scoring import TemplateScore, score_template_reference
from app.workouts.program_engine.template_selector import select_template_reference_result
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
        training_level=training_level,
        fitness_goal="build_muscle",
        focus_tags=focus_tags,
        intensity_methods=("standard",),
        days=(),
    )


def _normalized(**overrides: object):
    values: dict[str, object] = {
        "primary_goal": Goal.HYPERTROPHY,
        "training_experience": TrainingExperience.INTERMEDIATE,
        "training_age_months": 24,
        "available_training_days": 4,
        "session_duration_minutes": 60,
    }
    values.update(overrides)
    return normalize_request(request(**values), RULESET)


def _body_analysis(
    *priorities: tuple[MuscleGroup, str],
) -> BodyAnalysisInfluence:
    return BodyAnalysisInfluence.model_validate(
        {
            "analysis_id": uuid4(),
            "result_version_id": uuid4(),
            "analysis_revision": 1,
            "schema_version": "1.0",
            "source": "fully_reviewed",
            "overall_confidence": 0.9,
            "priorities": [
                {
                    "muscle": muscle,
                    "classification": classification,
                    "confidence": 0.9,
                    "severity": 0.8,
                }
                for muscle, classification in priorities
            ],
        }
    )


def test_trace_contains_every_scored_candidate_and_reuses_ranked_score() -> None:
    normalized = _normalized(priority_muscles=[MuscleGroup.CHEST])
    templates = (
        _template("balanced", TemplateFocusTag.BALANCED),
        _template("chest", TemplateFocusTag.CHEST_PRIORITY),
        _template("upper", TemplateFocusTag.UPPER_PRIORITY),
    )

    selection = select_template_reference_result(
        normalized, tuple(full_catalog()), templates, RULESET
    )
    trace = selection.decision_trace()

    assert selection.selected is selection.candidates[0]
    assert trace["requested_days"] == 4
    assert trace["experience_level"] == "intermediate"
    assert trace["templates_considered"] == 3
    assert [candidate["slug"] for candidate in trace["candidates"]] == [
        item.template.slug for item in selection.candidates
    ]
    assert trace["selected"] == selection.selected.template.slug
    for ranking, candidate_trace in zip(selection.candidates, trace["candidates"], strict=True):
        assert ranking.score == score_template_reference(normalized, ranking.template, RULESET)
        score_trace = candidate_trace["score"]
        assert score_trace["total"] == sum(
            score_trace[key] for key in ("priority", "body_analysis", "goal", "sex", "fallback")
        )


def test_priority_reasons_and_sex_prior_suppression_are_traceable() -> None:
    normalized = _normalized(
        biological_sex_optional="female",
        priority_muscles=[MuscleGroup.CHEST],
    )
    selection = select_template_reference_result(
        normalized,
        tuple(full_catalog()),
        (
            _template("exact", TemplateFocusTag.CHEST_PRIORITY),
            _template("regional", TemplateFocusTag.UPPER_PRIORITY),
        ),
        RULESET,
    )

    reasons = {item.template.slug: item.reason_codes for item in selection.candidates}

    assert reasons["exact"] == (
        "EXPLICIT_PRIORITY_EXACT_MATCH",
        "SEX_PRIOR_DISABLED_BY_EXPLICIT_PRIORITY",
    )
    assert reasons["regional"] == (
        "EXPLICIT_PRIORITY_REGIONAL_MATCH",
        "SEX_PRIOR_DISABLED_BY_EXPLICIT_PRIORITY",
    )
    assert all(item.score.sex_score == 0 for item in selection.candidates)


def test_body_analysis_goal_sex_and_fallback_reasons_follow_existing_scores() -> None:
    body_request = _normalized(
        body_analysis_influence=_body_analysis(
            (MuscleGroup.CHEST, "clear_lag"),
            (MuscleGroup.BACK, "mild_lag"),
        )
    )
    body_selection = select_template_reference_result(
        body_request,
        tuple(full_catalog()),
        (
            _template("chest", TemplateFocusTag.CHEST_PRIORITY),
            _template("back", TemplateFocusTag.BACK_PRIORITY),
        ),
        RULESET,
    )
    body_reasons = {item.template.slug: item.reason_codes for item in body_selection.candidates}
    assert body_reasons["chest"] == ("BODY_ANALYSIS_CLEAR_LAG_MATCH",)
    assert body_reasons["back"] == ("BODY_ANALYSIS_MILD_LAG_MATCH",)

    supported = select_template_reference_result(
        _normalized(primary_goal=Goal.STRENGTH, biological_sex_optional="female"),
        tuple(full_catalog()),
        (
            _template(
                "strength-glute",
                TemplateFocusTag.STRENGTH_BIAS,
                TemplateFocusTag.COMPOUND_FOCUS,
                TemplateFocusTag.GLUTE_PRIORITY,
            ),
            _template("balanced", TemplateFocusTag.BALANCED),
        ),
        RULESET,
    )
    supported_reasons = {item.template.slug: item.reason_codes for item in supported.candidates}
    assert supported_reasons["strength-glute"] == (
        "GOAL_STRENGTH_BIAS_MATCH",
        "GOAL_COMPOUND_FOCUS_MATCH",
        "SEX_PRIOR_GLUTE_MATCH",
    )
    assert supported_reasons["balanced"] == ("BALANCED_FALLBACK",)


def test_hard_rejections_never_receive_template_scores() -> None:
    unresolvable = replace(
        _template("unresolvable"),
        days=(
            TemplateReferenceDay(
                day_number=1,
                title="Missing core",
                focus=(MuscleGroup.CHEST,),
                slots=(
                    TemplateReferenceSlot(
                        exercise_id=None,
                        exercise_slug_hint="missing",
                        target_muscles=(MuscleGroup.CHEST,),
                        movement_pattern=MovementPattern.SHOULDER_EXTERNAL_ROTATION,
                        intensity_method="standard",
                        adaptation_priority="core",
                        superset_group=None,
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
    selection = select_template_reference_result(
        _normalized(),
        (),
        (
            _template("eligible"),
            _template("wrong-days", days_per_week=3),
            _template("wrong-level", training_level="advanced"),
            unresolvable,
        ),
        RULESET,
    )
    trace = selection.decision_trace()

    assert {item["slug"]: item["reason_codes"] for item in trace["hard_rejections"]} == {
        "unresolvable": ("CORE_SLOT_UNRESOLVABLE",),
        "wrong-days": ("DAYS_MISMATCH",),
        "wrong-level": ("EXPERIENCE_LEVEL_MISMATCH",),
    }
    assert [item["slug"] for item in trace["candidates"]] == ["eligible"]
    assert all("score" not in item for item in trace["hard_rejections"])


def test_unresolvable_core_has_a_concrete_rejection_category() -> None:
    template = replace(
        _template("unresolvable"),
        days=(
            TemplateReferenceDay(
                day_number=1,
                title="Missing core",
                focus=(MuscleGroup.CHEST,),
                slots=(
                    TemplateReferenceSlot(
                        exercise_id=None,
                        exercise_slug_hint="missing",
                        target_muscles=(MuscleGroup.CHEST,),
                        movement_pattern=MovementPattern.SHOULDER_EXTERNAL_ROTATION,
                        intensity_method="standard",
                        adaptation_priority="core",
                        superset_group=None,
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

    trace = select_template_reference_result(
        _normalized(), (), (template,), RULESET
    ).decision_trace()

    assert trace["selected"] is None
    assert trace["rejection_category"] == "CORE_SLOT_UNRESOLVED"


def test_equal_scores_record_deterministic_slug_tie_break() -> None:
    normalized = _normalized()
    templates = (_template("a-template"), _template("z-template"))

    first = select_template_reference_result(normalized, tuple(full_catalog()), templates, RULESET)
    second = select_template_reference_result(normalized, tuple(full_catalog()), templates, RULESET)

    assert first == second
    assert first.decision_trace() == second.decision_trace()
    assert first.decision_trace()["selected"] == "z-template"
    assert first.decision_trace()["tie_break"] == {
        "score": 0,
        "tied_slugs": ("z-template", "a-template"),
        "selected_by": "slug_descending",
        "selected": "z-template",
    }


def test_session_duration_is_not_present_in_template_score_trace() -> None:
    template = _template("balanced", TemplateFocusTag.BALANCED)
    short = select_template_reference_result(
        _normalized(session_duration_minutes=30), tuple(full_catalog()), (template,), RULESET
    )
    long = select_template_reference_result(
        _normalized(session_duration_minutes=120), tuple(full_catalog()), (template,), RULESET
    )

    assert short.candidates[0].score == long.candidates[0].score == TemplateScore(0, 0, 0, 0, 5)
    assert tuple(short.decision_trace()["candidates"][0]["score"]) == (
        "priority",
        "body_analysis",
        "goal",
        "sex",
        "fallback",
        "total",
    )
