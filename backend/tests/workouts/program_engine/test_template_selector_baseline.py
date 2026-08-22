from dataclasses import replace

from app.exercises.enums import MovementPattern
from app.workouts.program_engine.engine import generate_program
from app.workouts.program_engine.enums import Goal, TrainingExperience
from app.workouts.program_engine.normalization import normalize_request
from app.workouts.program_engine.rulesets.resistance_training_v1 import RULESET
from app.workouts.program_engine.schemas import (
    TemplateReference,
    TemplateReferenceDay,
    TemplateReferenceSlot,
)
from app.workouts.program_engine.template_selector import (
    eligible_template_references,
    select_template_reference,
)
from tests.workouts.program_engine.golden_fixtures import full_catalog, request


def _template(
    slug: str,
    *,
    days_per_week: int = 4,
    training_level: str = "intermediate",
    fitness_goal: str = "build_muscle",
    focus_tags: tuple[str, ...] = (),
) -> TemplateReference:
    return TemplateReference(
        slug=slug,
        days_per_week=days_per_week,
        training_level=training_level,
        fitness_goal=fitness_goal,
        focus_tags=focus_tags,
        intensity_methods=("standard",),
        days=(),
    )


def _normalized_request():
    return normalize_request(
        request(
            primary_goal=Goal.HYPERTROPHY,
            training_experience=TrainingExperience.INTERMEDIATE,
            training_age_months=24,
            available_training_days=4,
        ),
        RULESET,
    )


def test_selector_ignores_template_goal_for_hard_eligibility() -> None:
    templates = (
        _template("strength-template", fitness_goal="strength"),
        _template("fat-loss-template", fitness_goal="fat_loss"),
        _template("wrong-days", days_per_week=3),
        _template("wrong-level", training_level="advanced"),
    )

    selected_by_goal = []
    for goal in Goal:
        normalized = normalize_request(
            request(
                primary_goal=goal,
                training_experience=TrainingExperience.INTERMEDIATE,
                training_age_months=24,
                available_training_days=4,
            ),
            RULESET,
        )
        selected = select_template_reference(normalized, tuple(full_catalog()), templates, RULESET)
        assert selected is not None
        selected_by_goal.append(selected.slug)

    assert selected_by_goal == ["strength-template"] * len(Goal)


def test_same_days_and_level_have_same_eligible_pool_for_each_goal() -> None:
    templates = (
        _template("build-muscle-template", fitness_goal="build_muscle"),
        _template("fat-loss-template", fitness_goal="fat_loss"),
        _template("strength-template", fitness_goal="strength"),
    )

    pools = []
    for goal in Goal:
        normalized = normalize_request(
            request(
                primary_goal=goal,
                training_experience=TrainingExperience.INTERMEDIATE,
                training_age_months=24,
                available_training_days=4,
            ),
            RULESET,
        )
        pools.append(
            tuple(
                template.slug
                for template in eligible_template_references(
                    normalized, tuple(full_catalog()), templates
                )
            )
        )

    assert pools == [("build-muscle-template", "fat-loss-template", "strength-template")] * len(
        Goal
    )


def test_selector_still_excludes_days_and_level_mismatches() -> None:
    templates = (
        _template("valid", fitness_goal="strength"),
        _template("wrong-days", days_per_week=3),
        _template("wrong-level", training_level="advanced"),
    )

    eligible = eligible_template_references(_normalized_request(), tuple(full_catalog()), templates)
    assert tuple(template.slug for template in eligible) == ("valid",)

    selected = select_template_reference(
        _normalized_request(), tuple(full_catalog()), templates, RULESET
    )

    assert selected is not None
    assert selected.slug == "valid"


def test_selector_excludes_unresolvable_core_structure() -> None:
    template = _template(
        "unresolvable",
        fitness_goal="strength",
    )
    template = replace(
        template,
        days=(
            TemplateReferenceDay(
                day_number=1,
                title="Unresolvable",
                focus=(),
                slots=(
                    TemplateReferenceSlot(
                        exercise_id=None,
                        exercise_slug_hint="missing",
                        target_muscles=(),
                        movement_pattern=MovementPattern.HORIZONTAL_PUSH,
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

    assert select_template_reference(_normalized_request(), (), (template,), RULESET) is None


def test_selector_breaks_equal_scores_by_template_slug() -> None:
    templates = (_template("a-template"), _template("z-template"))

    selected = select_template_reference(
        _normalized_request(), tuple(full_catalog()), templates, RULESET
    )

    assert selected is not None
    assert selected.slug == "z-template"


def test_dynamic_fallback_retains_the_template_selection_rejection_trace() -> None:
    source = request(
        primary_goal=Goal.HYPERTROPHY,
        training_experience=TrainingExperience.INTERMEDIATE,
        training_age_months=24,
        available_training_days=4,
    )
    wrong_days = _template("wrong-days", days_per_week=3)

    result = generate_program(
        source,
        tuple(full_catalog()),
        RULESET,
        reference_templates=(wrong_days,),
    )

    assert result.program is not None, result.errors
    selection_trace = next(
        item for item in result.program.decision_trace if item["stage"] == "template_selection"
    )
    assert selection_trace["selected"] is None
    assert selection_trace["candidates"] == ()
    assert selection_trace["hard_rejections"] == (
        {"slug": "wrong-days", "reason_codes": ("DAYS_MISMATCH",)},
    )


def test_first_month_and_beginner_select_distinct_template_levels() -> None:
    templates = (
        _template("first-month-template", training_level="first_month"),
        _template("beginner-template", training_level="beginner"),
    )
    first_month = normalize_request(
        request(
            primary_goal=Goal.HYPERTROPHY,
            training_experience=TrainingExperience.FIRST_MONTH,
            training_age_months=24,
            available_training_days=4,
        ),
        RULESET,
    )
    beginner = normalize_request(
        request(
            primary_goal=Goal.HYPERTROPHY,
            training_experience=TrainingExperience.BEGINNER,
            training_age_months=24,
            available_training_days=4,
        ),
        RULESET,
    )

    first_month_selected = select_template_reference(
        first_month, tuple(full_catalog()), templates, RULESET
    )
    beginner_selected = select_template_reference(
        beginner, tuple(full_catalog()), templates, RULESET
    )

    assert first_month.training_status.value == "novice"
    assert beginner.training_status.value == "novice"
    assert first_month_selected is not None
    assert beginner_selected is not None
    assert first_month_selected.slug == "first-month-template"
    assert beginner_selected.slug == "beginner-template"


def test_training_age_reduction_does_not_change_intermediate_template_level() -> None:
    normalized = normalize_request(
        request(
            primary_goal=Goal.HYPERTROPHY,
            training_experience=TrainingExperience.INTERMEDIATE,
            training_age_months=1,
            available_training_days=4,
        ),
        RULESET,
    )
    template = _template("intermediate-template", training_level="intermediate")

    selected = select_template_reference(normalized, tuple(full_catalog()), (template,), RULESET)

    assert normalized.training_status.value == "novice"
    assert normalized.source.training_experience is TrainingExperience.INTERMEDIATE
    assert selected is not None
    assert selected.slug == "intermediate-template"


def test_first_month_normalization_and_selection_are_deterministic() -> None:
    source = request(
        primary_goal=Goal.HYPERTROPHY,
        training_experience=TrainingExperience.FIRST_MONTH,
        training_age_months=0,
        available_training_days=4,
        seed_optional=77,
    )
    templates = (_template("first-month-template", training_level="first_month"),)

    first = normalize_request(source, RULESET)
    second = normalize_request(source, RULESET)

    assert first == second
    assert select_template_reference(first, tuple(full_catalog()), templates, RULESET) == (
        select_template_reference(second, tuple(full_catalog()), templates, RULESET)
    )


def test_first_month_program_generation_remains_deterministic() -> None:
    source = request(
        primary_goal=Goal.HYPERTROPHY,
        training_experience=TrainingExperience.FIRST_MONTH,
        training_age_months=0,
        available_training_days=3,
        seed_optional=77,
    )
    catalog = tuple(full_catalog())

    first = generate_program(source, catalog, RULESET)
    second = generate_program(source, catalog, RULESET)

    assert first.program is not None, first.errors
    assert second.program is not None, second.errors
    assert first.program == second.program
