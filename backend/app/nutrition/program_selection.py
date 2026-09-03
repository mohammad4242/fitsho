"""Deterministic Nutrition Program proposal ordering from profile signals."""

from collections.abc import Iterable
from dataclasses import dataclass
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


@dataclass(frozen=True)
class ProgramCandidate:
    program: NutritionProgram
    preferred_style: bool
    preconstruction_rank: int


def enumerate_program_candidates(
    programs: Iterable[NutritionProgram],
    context: ProgramSelectionContext,
) -> tuple[ProgramCandidate, ...]:
    """Return every active program in a stable, style-preferred order."""

    preferred_style = _select_style(context)
    active_programs = (program for program in programs if program.is_active is not False)
    ordered = sorted(
        active_programs,
        key=lambda program: (
            0 if program.diet_style is preferred_style else 1,
            program.code,
            str(program.id) if program.id is not None else "",
            program.slug,
        ),
    )
    return tuple(
        ProgramCandidate(
            program=program,
            preferred_style=program.diet_style is preferred_style,
            preconstruction_rank=index,
        )
        for index, program in enumerate(ordered)
    )


def select_program(
    programs: Iterable[NutritionProgram],
    context: ProgramSelectionContext,
    user_id: UUID | None = None,
) -> NutritionProgram:
    """Compatibility wrapper returning the first proposal.

    Weekly generation uses :func:`enumerate_program_candidates` and evaluates
    every proposal. ``user_id`` remains accepted for older callers but has no
    influence on the result.
    """

    del user_id
    candidates = enumerate_program_candidates(programs, context)
    if not candidates:
        raise ValueError("No active Nutrition Program is available")
    return candidates[0].program


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
