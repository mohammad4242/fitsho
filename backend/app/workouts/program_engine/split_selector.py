from app.workouts.program_engine.enums import (
    PhysicalJobDemand,
    RecoveryRating,
    SplitType,
    TrainingStatus,
)
from app.workouts.program_engine.rulesets.resistance_training_v1 import ProgramRuleset
from app.workouts.program_engine.schemas import NormalizedProgramRequest, SplitPlan


def select_split(request: NormalizedProgramRequest, ruleset: ProgramRuleset) -> SplitPlan:
    days = min(request.resistance_training_days, ruleset.max_resistance_days)
    reasons: list[str] = []
    source = request.source
    recovery_limited = (
        source.sleep_quality is RecoveryRating.POOR
        or source.stress_level is RecoveryRating.POOR
        or source.physical_job_demand is PhysicalJobDemand.HIGH
        or source.recent_training_history.recovery_problems
    )
    if (
        request.training_status is TrainingStatus.NOVICE
        and recovery_limited
        and days > ruleset.maximum_novice_recovery_days
    ):
        days = ruleset.maximum_novice_recovery_days
        reasons.append("SPLIT_REDUCED_FOR_RECOVERY")

    split_type, focuses = _structure(days, request.training_status)
    if days <= 3 and request.training_status is TrainingStatus.NOVICE:
        reasons.append("SPLIT_SIMPLIFIED_FOR_NOVICE")
    if split_type in {SplitType.FULL_BODY, SplitType.FULL_BODY_AB, SplitType.FULL_BODY_ABC}:
        reasons.append("SPLIT_FULL_BODY_FOR_LOW_FREQUENCY")
    if days >= 4:
        reasons.append("SPLIT_SELECTED_FOR_TWICE_WEEKLY_EXPOSURE")
    weekdays = _select_weekdays(days, source.preferred_weekdays, focuses, ruleset)
    if len(source.preferred_weekdays) >= days and weekdays != tuple(
        sorted(source.preferred_weekdays[:days])
    ):
        reasons.append("SPLIT_PREFERRED_DAYS_ADJUSTED_FOR_RECOVERY")
    return SplitPlan(
        split_type=split_type,
        day_focuses=focuses,
        weekdays=weekdays,
        score=100 - (10 if recovery_limited and days > 4 else 0),
        reason_codes=tuple(reasons),
    )


def _structure(days: int, status: TrainingStatus) -> tuple[SplitType, tuple[str, ...]]:
    if days == 1:
        return SplitType.FULL_BODY, ("full_body",)
    if days == 2:
        return SplitType.FULL_BODY_AB, ("full_body_a", "full_body_b")
    if days == 3:
        if status in {TrainingStatus.INTERMEDIATE, TrainingStatus.ADVANCED}:
            return SplitType.UPPER_LOWER_FULL, ("upper", "lower", "full_body")
        return SplitType.FULL_BODY_ABC, ("full_body_a", "full_body_b", "full_body_c")
    if days == 4:
        return SplitType.UPPER_LOWER, ("upper", "lower", "upper", "lower")
    if days == 5:
        return SplitType.UPPER_LOWER_SPECIALIZATION, (
            "upper",
            "lower",
            "upper",
            "lower",
            "specialization",
        )
    if status is TrainingStatus.ADVANCED:
        return SplitType.PUSH_PULL_LEGS_X2, ("push", "pull", "legs", "push", "pull", "legs")
    return SplitType.UPPER_LOWER_X3, ("upper", "lower", "upper", "lower", "upper", "lower")


def _select_weekdays(
    days: int,
    preferred: tuple[int, ...],
    focuses: tuple[str, ...],
    ruleset: ProgramRuleset,
) -> tuple[int, ...]:
    if len(preferred) >= days:
        selected = tuple(sorted(preferred[:days]))
        if _spacing_is_acceptable(selected, focuses):
            return selected
    return ruleset.default_weekdays[days]


def _spacing_is_acceptable(weekdays: tuple[int, ...], focuses: tuple[str, ...]) -> bool:
    if len(weekdays) <= 1:
        return True
    ordered = sorted(zip(weekdays, focuses, strict=True))
    circular = ordered + [(ordered[0][0] + 7, ordered[0][1])]
    for current, following in zip(circular, circular[1:], strict=False):
        gap = following[0] - current[0]
        recovery_sensitive = (
            current[1].startswith("full_body")
            or following[1].startswith("full_body")
            or current[1] == following[1]
        )
        if recovery_sensitive and gap < 2:
            return False
    return True
