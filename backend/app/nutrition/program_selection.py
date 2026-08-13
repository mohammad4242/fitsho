"""Deterministic Nutrition Program selection from existing profile signals."""

from typing import NamedTuple
from uuid import UUID

from app.nutrition.enums import NutritionDietStyle
from app.nutrition.models import NutritionProgram


class ProgramSelectionContext(NamedTuple):
    fitness_goal: str
    trains: bool
    exercise_type: str | None
    plan_style: str
    budget_style: str
    cooking_skill: str
    maximum_cooking_time_minutes: int
    meal_preparation_preference: str
    preferred_variety: str


def select_program(
    programs: list[NutritionProgram],
    context: ProgramSelectionContext,
    user_id: UUID,
) -> NutritionProgram:
    style = _select_style(context)
    candidates = sorted(
        (
            program
            for program in programs
            if program.is_active is not False and program.diet_style is style
        ),
        key=lambda program: program.code,
    )
    if not candidates:
        raise ValueError(f"No active Nutrition Program is available for {style.value}")
    return candidates[user_id.int % len(candidates)]


def _select_style(context: ProgramSelectionContext) -> NutritionDietStyle:
    if (
        context.fitness_goal in {"build_muscle", "body_recomposition"}
        and context.trains
        and context.exercise_type in {"resistance", "mixed"}
    ):
        return NutritionDietStyle.HIGH_PROTEIN_GYM
    if context.plan_style == "economical":
        return NutritionDietStyle.ECONOMY
    if (
        context.plan_style == "simple"
        or context.cooking_skill == "none"
        or context.maximum_cooking_time_minutes <= 20
        or context.meal_preparation_preference == "no_cooking"
    ):
        return NutritionDietStyle.QUICK_EASY
    if context.preferred_variety == "high" and context.budget_style == "flexible":
        return NutritionDietStyle.PREMIUM_VARIED
    return NutritionDietStyle.BALANCED_IRANIAN
