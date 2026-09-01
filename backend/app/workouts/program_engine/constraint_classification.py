"""Stable, behavior-neutral classification of engine reason codes.

This module is deliberately independent from generation and validation.  It
provides shared vocabulary for traces and future repair orchestration without
changing any existing decision path.
"""

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType


class ConstraintClass(StrEnum):
    HARD = "hard"
    REPAIRABLE = "repairable"
    SOFT = "soft"


_HARD_REASONS = frozenset(
    {
        "BLOCKED_EXERCISE_SELECTED",
        "SAFETY_STATUS_DISALLOWS_GENERATION",
        "BLOCKED_MOVEMENT_PATTERN_SELECTED",
        "BLOCKED_CAUTION_TAG_SELECTED",
        "EXERCISE_REJECTED_BLOCKED_CAUTION_TAG",
        "INACTIVE_EXERCISE_SELECTED",
        "NONPROGRAMMABLE_EXERCISE_SELECTED",
        "REVIEW_PENDING_EXERCISE_SELECTED",
        "UNAVAILABLE_EQUIPMENT_SELECTED",
        "EXERCISE_REJECTED_MISSING_EQUIPMENT",
        "REQUIRED_MOVEMENT_PATTERN_MISSING",
        "FULL_BODY_COVERAGE_UNSATISFIED",
        "FULL_BODY_PATTERN_MISSING",
        "NO_SAFE_EXERCISE_FOR_PATTERN",
        "REQUIRED_PATTERN_UNAVAILABLE",
        "REQUIRED_SLOT_HARD_IMPOSSIBILITY",
        "TEMPLATE_CORE_SLOT_UNRESOLVABLE",
        "TEMPLATE_CORE_SEMANTIC_DUPLICATE_UNRESOLVABLE",
        "TEMPLATE_CORE_STRUCTURE_EXCEEDS_SESSION_CAPACITY",
        "INVALID_EXERCISE_PRESCRIPTION",
        "SEMANTIC_NEAR_DUPLICATE_EXERCISE",
        "UNJUSTIFIED_DUPLICATE_EXERCISE",
        "TRAINING_DAY_COUNT_MISMATCH",
        "REQUESTED_TRAINING_DAYS_UNSATISFIED",
        "REQUESTED_TRAINING_DAYS_MISMATCH",
        "UNSUPPORTED_RESISTANCE_TRAINING_DAYS",
        "NO_EXACT_DAY_SPLIT_AVAILABLE",
        "PROGRAM_CONSTRUCTION_ALTERNATIVES_EXHAUSTED",
        "EXACT_DAY_SPLIT_ALTERNATIVES_EXHAUSTED",
        "TEMPLATE_ALTERNATIVES_EXHAUSTED",
        "WEEKLY_MUSCLE_VOLUME_EXCEEDED",
        "RESISTANCE_WORK_EXCLUDED_FROM_VOLUME",
        "VOLUME_REPAIR_HARD_MINIMUM_UNSATISFIED",
        "PER_SESSION_MUSCLE_VOLUME_EXCEEDED",
        "PER_EXERCISE_SET_CAP_EXCEEDED",
        "RECOVERY_DIRECT_HIGH_UNSAFE",
    }
)
_REPAIRABLE_REASONS = frozenset(
    {
        "RECOVERY_SPACING_INVALID",
        "RECOVERY_WEEKDAY_CONFLICT",
        "RECOVERY_WEEKDAYS_REARRANGED_FOR_DIRECT_MUSCLE_OVERLAP",
        "RECOVERY_WEEKDAY_REPAIR_UNAVAILABLE",
        "RECOVERY_OPTIONAL_ISOLATION_REDISTRIBUTION_UNAVAILABLE",
        "RECOVERY_OPTIONAL_ISOLATION_REDISTRIBUTED",
        "SESSION_EXERCISE_COUNT_OUT_OF_RANGE",
        "TEMPLATE_SESSION_EXERCISE_COUNT_UNSATISFIED",
        "TEMPLATE_MAIN_COUNT_OUT_OF_RANGE",
        "TEMPLATE_SESSION_COUNT_CONSTRAINED_BY_SAFE_CAPACITY",
        "INITIAL_TEMPLATE_REJECTED_UNFILLABLE",
        "TEMPLATE_SEMANTIC_DUPLICATE_OMITTED",
        "SEMANTIC_NEAR_DUPLICATE_REJECTED",
        "TEMPLATE_SUPERSET_REJECTED_UNSAFE",
        "SUPERSET_GROUP_INVALID_SIZE",
        "SUPERSET_GROUP_NOT_ADJACENT",
        "UNSAFE_SUPERSET_PAIR",
        "SESSION_EXERCISE_ORDER_INVALID",
        "SUPPLEMENTAL_WORK_NOT_AT_SESSION_END",
        "SUPPLEMENTAL_EXERCISE_LIMIT_EXCEEDED",
        "EXERCISE_TYPE_SEQUENCE_INVALID",
        "STRICT_MUSCLE_BLOCK_ORDER_INVALID",
        "STRENGTH_PRIMARY_NOT_FIRST",
        "SEMANTIC_OPENER_CONFLICT",
        "PUSH_UP_OPENER_ORDER_INVALID",
        "PULL_UP_OPENER_ORDER_INVALID",
        "LEG_EXTENSION_PRIMER_ORDER_INVALID",
        "SESSION_DURATION_UNDERFILLED",
        "SESSION_DURATION_REPAIR_APPLIED",
        "SESSION_DURATION_EXCEEDED",
        "SESSION_DURATION_OVER_TARGET",
        "SESSION_DURATION_TARGET_UNSATISFIED",
    }
)
_SOFT_REASONS = frozenset(
    {
        "BODY_ANALYSIS_NOT_FULLY_REVIEWED",
        "CARDIO_LOWER_BODY_RECOVERY_CONFLICT",
        "DIRECT_VOLUME_BELOW_SOFT_TARGET",
        "DURATION_CAPACITY_LIMITED_VOLUME",
        "FULL_BODY_COVERAGE_CONSTRAINED",
        "FULL_BODY_COVERAGE_UNAVAILABLE",
        "MINIMUM_DIRECT_MUSCLE_COVERAGE_UNSATISFIED",
        "MINIMUM_MUSCLE_COVERAGE_UNSATISFIED",
        "PRIORITY_TARGET_CONSTRAINED",
        "PRIORITY_TARGET_PARTIALLY_SATISFIED",
        "RECOVERY_REPAIRABLE_OVERLAP_REMAINS",
        "SESSION_DURATION_CONSTRAINED_BY_HARD_VOLUME_LIMITS",
        "SESSION_DURATION_CONSTRAINED_BY_USEFUL_WORKLOAD",
        "SESSION_EXERCISE_COUNT_CONSTRAINED_BY_SAFE_CAPACITY",
        "EFFECTIVE_VOLUME_BELOW_ACCEPTABLE_RANGE",
        "SOFT_WEEKLY_VOLUME_EXCEEDED",
        "MUSCLE_DIRECT_FREQUENCY_EXCEEDED",
        "SEMANTIC_SLOT_MISMATCH_SELECTED",
        "DURATION_PLANNED_REDUCED_EXERCISE_COUNT",
        "PLANNED_SOFT_VOLUME_REDUCED_DURING_SESSION_FIT",
        "SESSION_DURATION_UNDER_TARGET",
        "VOLUME_REDUCED_FOR_DURATION_CAPACITY",
        "WEEKLY_VOLUME_CONSTRAINED",
        "WEEKLY_VOLUME_OUTSIDE_ACCEPTABLE_RANGE",
    }
)
_HARD_AFTER_REPAIR_EXHAUSTION = frozenset(
    {
        "RECOVERY_SPACING_INVALID",
        "SESSION_EXERCISE_COUNT_OUT_OF_RANGE",
        "TEMPLATE_SESSION_EXERCISE_COUNT_UNSATISFIED",
        "TEMPLATE_MAIN_COUNT_OUT_OF_RANGE",
        "INITIAL_TEMPLATE_REJECTED_UNFILLABLE",
        "SUPERSET_GROUP_INVALID_SIZE",
        "SUPERSET_GROUP_NOT_ADJACENT",
        "UNSAFE_SUPERSET_PAIR",
        "SESSION_EXERCISE_ORDER_INVALID",
        "SUPPLEMENTAL_WORK_NOT_AT_SESSION_END",
        "SUPPLEMENTAL_EXERCISE_LIMIT_EXCEEDED",
        "EXERCISE_TYPE_SEQUENCE_INVALID",
        "STRICT_MUSCLE_BLOCK_ORDER_INVALID",
        "STRENGTH_PRIMARY_NOT_FIRST",
        "SEMANTIC_OPENER_CONFLICT",
        "PUSH_UP_OPENER_ORDER_INVALID",
        "PULL_UP_OPENER_ORDER_INVALID",
        "LEG_EXTENSION_PRIMER_ORDER_INVALID",
        "SESSION_DURATION_EXCEEDED",
        "SESSION_DURATION_OVER_TARGET",
        "SESSION_DURATION_TARGET_UNSATISFIED",
    }
)
_CLASS_BY_REASON = MappingProxyType(
    {
        **{reason: ConstraintClass.HARD for reason in _HARD_REASONS},
        **{reason: ConstraintClass.REPAIRABLE for reason in _REPAIRABLE_REASONS},
        **{reason: ConstraintClass.SOFT for reason in _SOFT_REASONS},
    }
)


def classify_constraint(
    reason_code: str,
    *,
    repair_exhausted: bool = False,
) -> ConstraintClass | None:
    """Return the explicit class for a stable reason code, or ``None``.

    Structured details after ``:`` do not change the base classification.
    Repairable final-contract failures become hard only after the bounded repair
    path has been exhausted.
    """

    base_code = reason_code.partition(":")[0]
    if repair_exhausted and base_code in _HARD_AFTER_REPAIR_EXHAUSTION:
        return ConstraintClass.HARD
    return _CLASS_BY_REASON.get(base_code)


@dataclass(frozen=True, slots=True)
class ConstraintTrace:
    reason_code: str
    constraint_class: ConstraintClass | None
    metadata: Mapping[str, object] = field(default_factory=dict)

    def as_trace(self) -> dict[str, object]:
        return {
            "reason_code": self.reason_code,
            "constraint_class": (
                self.constraint_class.value if self.constraint_class is not None else None
            ),
            "metadata": dict(self.metadata),
        }


def constraint_trace(
    reason_code: str, metadata: Mapping[str, object] | None = None
) -> ConstraintTrace:
    """Create an immutable-enough trace payload without affecting decisions."""

    return ConstraintTrace(
        reason_code=reason_code,
        constraint_class=classify_constraint(reason_code),
        metadata=dict(metadata or {}),
    )
