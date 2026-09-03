from decimal import Decimal
from uuid import UUID

from app.nutrition.candidate_selection import evaluate_candidate, select_best_candidate
from app.nutrition.enums import NutritionDietStyle
from app.nutrition.models import NutritionProgram
from app.nutrition.planner_engine import (
    GenerationOutcome,
    NutrientComparison,
    PlannerResult,
)
from app.nutrition.program_selection import ProgramCandidate


def _proposal(code: str, rank: int) -> ProgramCandidate:
    return ProgramCandidate(
        program=NutritionProgram(
            id=UUID(int=rank + 1),
            code=code,
            slug=code.casefold(),
            diet_style=NutritionDietStyle.BALANCED_IRANIAN,
        ),
        preferred_style=True,
        preconstruction_rank=rank,
    )


def _comparison(preferred: str, planned: str) -> NutrientComparison:
    preferred_value = Decimal(preferred)
    planned_value = Decimal(planned)
    return NutrientComparison(
        preferred=preferred_value,
        minimum_or_maximum=None,
        planned=planned_value,
        difference_from_preferred=planned_value - preferred_value,
        difference_from_limit=None,
        status="within_target",
    )


def _success(*, calories: str, cost: str) -> PlannerResult:
    return PlannerResult(
        outcome=GenerationOutcome.SUCCESS,
        reason_codes=("SAFE_FEASIBLE_DRAFT_GENERATED",),
        weekly_cost_irr=Decimal(cost),
        nutrient_comparisons={
            "goal_calories": _comparison("2000", calories),
            "protein": _comparison("100", "100"),
            "carbohydrate": _comparison("220", "220"),
            "total_fat": _comparison("60", "60"),
        },
    )


def test_failed_candidates_cannot_be_selected() -> None:
    failed = evaluate_candidate(
        _proposal("P01", 0),
        PlannerResult(
            outcome=GenerationOutcome.INFEASIBLE,
            reason_codes=("STRICT_BUDGET_EXCEEDED",),
        ),
        weekly_budget_irr=Decimal("100000"),
    )
    successful = evaluate_candidate(
        _proposal("P02", 1),
        _success(calories="2000", cost="90000"),
        weekly_budget_irr=Decimal("100000"),
    )

    selection = select_best_candidate((failed, successful))

    assert selection.selected is successful
    assert selection.first_valid is successful


def test_all_successful_candidates_are_compared_and_nutrition_beats_cost() -> None:
    cheap_worse = evaluate_candidate(
        _proposal("P01", 0),
        _success(calories="1500", cost="1000"),
        weekly_budget_irr=Decimal("100000"),
    )
    expensive_best = evaluate_candidate(
        _proposal("P02", 1),
        _success(calories="2000", cost="99000"),
        weekly_budget_irr=Decimal("100000"),
    )
    later_best = evaluate_candidate(
        _proposal("P03", 2),
        _success(calories="2000", cost="50000"),
        weekly_budget_irr=Decimal("100000"),
    )

    selection = select_best_candidate((cheap_worse, expensive_best, later_best))

    assert len(selection.evaluations) == 3
    assert selection.first_valid is cheap_worse
    assert selection.selected is later_best
    assert selection.selected.quality is not None
    assert selection.first_valid.quality is not None
    assert selection.selected.quality.sort_key() <= selection.first_valid.quality.sort_key()


def test_program_code_is_the_stable_tie_breaker() -> None:
    later_code = evaluate_candidate(
        _proposal("P02", 0),
        _success(calories="2000", cost="50000"),
        weekly_budget_irr=Decimal("100000"),
    )
    earlier_code = evaluate_candidate(
        _proposal("P01", 1),
        _success(calories="2000", cost="50000"),
        weekly_budget_irr=Decimal("100000"),
    )

    selection = select_best_candidate((later_code, earlier_code))

    assert selection.selected is earlier_code


def test_missing_comparison_data_is_not_perfect_quality() -> None:
    missing = evaluate_candidate(
        _proposal("P01", 0),
        PlannerResult(
            outcome=GenerationOutcome.SUCCESS,
            reason_codes=("SAFE_FEASIBLE_DRAFT_GENERATED",),
            weekly_cost_irr=Decimal("1"),
            nutrient_comparisons={},
        ),
        weekly_budget_irr=Decimal("100000"),
    )
    complete = evaluate_candidate(
        _proposal("P02", 1),
        _success(calories="2000", cost="90000"),
        weekly_budget_irr=Decimal("100000"),
    )

    selection = select_best_candidate((missing, complete))

    assert selection.selected is complete
    assert missing.quality is not None
    assert complete.quality is not None
    assert (
        missing.quality.core_nutrition_max_deviation > complete.quality.core_nutrition_max_deviation
    )
