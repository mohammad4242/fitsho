"""Pure hard eligibility checks for nutrition programs."""

from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING

from app.nutrition.models import NutritionProgram
from app.nutrition.nutrition_request import NormalizedNutritionRequest

if TYPE_CHECKING:
    from app.nutrition.program_costing import ProgramCostEstimate


@dataclass(frozen=True)
class ProgramHardRejection:
    program_code: str
    reason_codes: tuple[str, ...]


@dataclass(frozen=True)
class ProgramEligibilityResult:
    eligible: bool
    reason_codes: tuple[str, ...]


def check_program_eligibility(
    program: NutritionProgram,
    request: NormalizedNutritionRequest,
    *,
    cost_estimate: "ProgramCostEstimate | None" = None,
) -> ProgramEligibilityResult:
    reasons: list[str] = []
    if program.is_active is False:
        reasons.append("PROGRAM_INACTIVE")

    if (
        cost_estimate is not None
        and cost_estimate.minimum_adapted_monthly_cost_irr is not None
        and request.monthly_budget_irr is not None
        and (
            cost_estimate.minimum_adapted_monthly_cost_irr
            > Decimal(str(request.monthly_budget_irr))
        )
    ):
        reasons.append("PROGRAM_BUDGET_PROVABLY_INFEASIBLE")

    if reasons:
        return ProgramEligibilityResult(eligible=False, reason_codes=tuple(reasons))
    return ProgramEligibilityResult(eligible=True, reason_codes=())
