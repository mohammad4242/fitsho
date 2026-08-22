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
