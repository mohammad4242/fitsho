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
        "BLOCKED_MOVEMENT_PATTERN_SELECTED",
        "BLOCKED_CAUTION_TAG_SELECTED",
        "EXERCISE_REJECTED_BLOCKED_CAUTION_TAG",
        "INACTIVE_EXERCISE_SELECTED",
        "NONPROGRAMMABLE_EXERCISE_SELECTED",
        "REVIEW_PENDING_EXERCISE_SELECTED",
        "UNAVAILABLE_EQUIPMENT_SELECTED",
        "EXERCISE_REJECTED_MISSING_EQUIPMENT",
        "REQUIRED_MOVEMENT_PATTERN_MISSING",
        "TEMPLATE_CORE_SLOT_UNRESOLVABLE",
        "TEMPLATE_CORE_STRUCTURE_EXCEEDS_SESSION_CAPACITY",
        "REQUESTED_TRAINING_DAYS_UNSATISFIED",
        "REQUESTED_TRAINING_DAYS_MISMATCH",
        "WEEKLY_MUSCLE_VOLUME_EXCEEDED",
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
        "SESSION_EXERCISE_COUNT_OUT_OF_RANGE",
        "TEMPLATE_SESSION_EXERCISE_COUNT_UNSATISFIED",
        "SESSION_DURATION_UNDERFILLED",
        "SESSION_DURATION_REPAIR_APPLIED",
        "SESSION_DURATION_UNDER_TARGET",
        "SESSION_DURATION_EXCEEDED",
        "SESSION_DURATION_OVER_TARGET",
        "SESSION_DURATION_TARGET_UNSATISFIED",
    }
)
_SOFT_REASONS = frozenset(
    {
        "EFFECTIVE_VOLUME_BELOW_ACCEPTABLE_RANGE",
        "SOFT_WEEKLY_VOLUME_EXCEEDED",
        "MUSCLE_DIRECT_FREQUENCY_EXCEEDED",
        "SEMANTIC_SLOT_MISMATCH_SELECTED",
        "DURATION_PLANNED_REDUCED_EXERCISE_COUNT",
        "PLANNED_SOFT_VOLUME_REDUCED_DURING_SESSION_FIT",
    }
)
_HARD_AFTER_REPAIR_EXHAUSTION = frozenset(
    {
        "RECOVERY_SPACING_INVALID",
        "SESSION_EXERCISE_COUNT_OUT_OF_RANGE",
        "TEMPLATE_SESSION_EXERCISE_COUNT_UNSATISFIED",
        "SESSION_DURATION_UNDER_TARGET",
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
