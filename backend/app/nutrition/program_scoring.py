"""Pure deterministic preconstruction scoring for nutrition programs."""

from dataclasses import dataclass

from app.nutrition.enums import NutritionDietStyle
from app.nutrition.models import NutritionProgram
from app.nutrition.nutrition_request import NormalizedNutritionRequest


@dataclass(frozen=True)
class ProgramScore:
    budget_score: int
    goal_score: int
    training_score: int
    meal_structure_score: int
    preference_score: int
    total: int


@dataclass(frozen=True)
class ProgramScoringResult:
    score: ProgramScore
    reason_codes: tuple[str, ...]


def select_preferred_diet_style(request: NormalizedNutritionRequest) -> NutritionDietStyle:
    if (
        request.fitness_goal in {"build_muscle", "body_recomposition"}
        and request.trains
        and request.exercise_type in {"resistance", "mixed"}
    ):
        return NutritionDietStyle.HIGH_PROTEIN_GYM
    if request.plan_style == "economical":
        return NutritionDietStyle.ECONOMY
    if (
        request.plan_style == "simple"
        or request.cooking_skill == "none"
        or (
            request.maximum_cooking_time_minutes is not None
            and request.maximum_cooking_time_minutes <= 20
        )
        or request.meal_preparation_preference == "no_cooking"
    ):
        return NutritionDietStyle.QUICK_EASY
    if request.preferred_variety == "high" and request.budget_style == "flexible":
        return NutritionDietStyle.PREMIUM_VARIED
    return NutritionDietStyle.BALANCED_IRANIAN


def score_program(
    program: NutritionProgram,
    request: NormalizedNutritionRequest,
) -> ProgramScoringResult:
    preferred_style = select_preferred_diet_style(request)
    is_preferred = program.diet_style is preferred_style
    preference_score = 100 if is_preferred else 0
    total = preference_score

    reason_codes: list[str] = []
    if is_preferred:
        reason_codes.append("PREFERRED_DIET_STYLE")

    return ProgramScoringResult(
        score=ProgramScore(
            budget_score=0,
            goal_score=0,
            training_score=0,
            meal_structure_score=0,
            preference_score=preference_score,
            total=total,
        ),
        reason_codes=tuple(reason_codes),
    )
