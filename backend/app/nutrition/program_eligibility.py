"""Pure hard eligibility checks for nutrition programs."""

from dataclasses import dataclass

from app.nutrition.models import NutritionProgram
from app.nutrition.nutrition_request import NormalizedNutritionRequest


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
) -> ProgramEligibilityResult:
    del request
    reasons: list[str] = []
    if program.is_active is False:
        reasons.append("PROGRAM_INACTIVE")

    if reasons:
        return ProgramEligibilityResult(eligible=False, reason_codes=tuple(reasons))
    return ProgramEligibilityResult(eligible=True, reason_codes=())
