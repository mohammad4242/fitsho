import pytest

from app.workouts.program_engine.enums import Goal, TrainingExperience
from app.workouts.program_engine.normalization import normalize_request
from app.workouts.program_engine.rulesets.resistance_training_v1 import RULESET
from app.workouts.program_engine.schemas import TemplateReference
from app.workouts.program_engine.template_selector import (
    _matches_goal,
    select_template_reference,
)
from tests.workouts.program_engine.golden_fixtures import full_catalog, request


@pytest.mark.parametrize(
    ("goal", "template_goal", "expected"),
    [
        (Goal.HYPERTROPHY, "build_muscle", True),
        (Goal.MUSCLE_GAIN, "build_muscle", True),
        (Goal.FAT_LOSS, "fat_loss", True),
        (Goal.STRENGTH, "strength", True),
        (Goal.BODY_RECOMPOSITION, "body_recomposition", True),
        (Goal.BODY_RECOMPOSITION, "build_muscle", True),
        (Goal.GENERAL_FITNESS, "improve_fitness", True),
        (Goal.GENERAL_FITNESS, "maintain_weight", True),
        (Goal.MUSCULAR_ENDURANCE, "improve_fitness", True),
        (Goal.HYPERTROPHY, "strength", False),
        (Goal.FAT_LOSS, "build_muscle", False),
        (Goal.STRENGTH, "fat_loss", False),
    ],
)
def test_current_goal_to_template_mapping_is_characterized(
    goal: Goal,
    template_goal: str,
    expected: bool,
) -> None:
    assert _matches_goal(goal, template_goal) is expected


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


def test_selector_keeps_days_level_and_goal_as_hard_filters() -> None:
    templates = (
        _template("valid"),
        _template("wrong-days", days_per_week=3),
        _template("wrong-level", training_level="advanced"),
        _template("wrong-goal", fitness_goal="strength"),
    )

    selected = select_template_reference(
        _normalized_request(), tuple(full_catalog()), templates, RULESET
    )

    assert selected is not None
    assert selected.slug == "valid"


def test_selector_breaks_equal_scores_by_template_slug() -> None:
    templates = (_template("a-template"), _template("z-template"))

    selected = select_template_reference(
        _normalized_request(), tuple(full_catalog()), templates, RULESET
    )

    assert selected is not None
    assert selected.slug == "z-template"


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
