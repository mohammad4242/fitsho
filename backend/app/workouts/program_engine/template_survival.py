"""Exact post-construction feasibility for ranked template candidates."""

from dataclasses import dataclass
from enum import StrEnum

from app.workouts.program_engine.constraint_classification import (
    ConstraintClass,
    classify_constraint,
)


class CandidateSurvivalStatus(StrEnum):
    COMFORTABLY_FEASIBLE = "comfortably_feasible"
    REPAIRABLE = "repairable"
    TIGHT = "tight"
    PROVABLY_INFEASIBLE = "provably_infeasible"


@dataclass(frozen=True, slots=True)
class CandidateSurvival:
    status: CandidateSurvivalStatus
    repair_cost: int
    repair_events: tuple[str, ...]
    reason_codes: tuple[str, ...]
    hard_reason_codes: tuple[str, ...]
    is_success: bool

    def decision_trace(self) -> dict[str, object]:
        return {
            "status": self.status.value,
            "repair_cost": self.repair_cost,
            "repair_events": self.repair_events,
            "reason_codes": self.reason_codes,
            "hard_reason_codes": self.hard_reason_codes,
            "constraints": tuple(
                {
                    "reason_code": reason,
                    "constraint_class": (
                        classification.value if classification is not None else None
                    ),
                }
                for reason in self.reason_codes
                for classification in (
                    classify_constraint(reason, repair_exhausted=not self.is_success),
                )
            ),
        }


def assess_candidate_survival(
    *,
    is_success: bool,
    reason_codes: tuple[str, ...],
    repair_events: tuple[str, ...],
) -> CandidateSurvival:
    """Classify a candidate after it has run through the real engine pipeline."""

    unique_reasons = tuple(dict.fromkeys(reason_codes))
    recorded_repairs = tuple(repair_events)
    hard_reasons = tuple(
        reason
        for reason in unique_reasons
        if classify_constraint(reason, repair_exhausted=not is_success) is ConstraintClass.HARD
    )
    repair_cost = len(recorded_repairs)
    if not is_success:
        status = CandidateSurvivalStatus.PROVABLY_INFEASIBLE
    elif repair_cost == 0:
        status = CandidateSurvivalStatus.COMFORTABLY_FEASIBLE
    elif repair_cost <= 3:
        status = CandidateSurvivalStatus.REPAIRABLE
    else:
        status = CandidateSurvivalStatus.TIGHT
    return CandidateSurvival(
        status=status,
        repair_cost=repair_cost,
        repair_events=recorded_repairs,
        reason_codes=unique_reasons,
        hard_reason_codes=hard_reasons,
        is_success=is_success,
    )


def candidate_survival_sort_key(
    assessment: CandidateSurvival,
    *,
    product_score: int,
) -> tuple[int, int, int, int]:
    """Keep validity hard and charge one score point per real repair event."""

    repair_adjusted_score = product_score - assessment.repair_cost
    return (
        int(assessment.is_success),
        repair_adjusted_score,
        product_score,
        -assessment.repair_cost,
    )
