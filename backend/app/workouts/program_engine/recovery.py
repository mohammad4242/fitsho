from dataclasses import replace
from itertools import combinations

from app.exercises.enums import MuscleGroup
from app.workouts.program_engine.rulesets.resistance_training_v1 import ProgramRuleset
from app.workouts.program_engine.schemas import SplitPlan, WorkoutDay


def direct_muscles(day: WorkoutDay) -> frozenset[MuscleGroup]:
    return frozenset(
        item.primary_muscle
        for item in day.exercises
        if item.primary_muscle is not None
    )


def recovery_spacing_is_valid(
    days: tuple[WorkoutDay, ...],
    ruleset: ProgramRuleset,
) -> bool:
    scheduled = sorted(
        ((day.weekday, day) for day in days if day.weekday is not None),
        key=lambda item: item[0],
    )
    if len(scheduled) <= 1:
        return True
    circular = scheduled + [(scheduled[0][0] + ruleset.days_per_week, scheduled[0][1])]
    for current, following in zip(circular, circular[1:], strict=False):
        overlap = direct_muscles(current[1]).intersection(direct_muscles(following[1]))
        if overlap and following[0] - current[0] < ruleset.minimum_recovery_gap_days:
            return False
    return True


def repair_recovery_weekdays(
    split: SplitPlan,
    days: tuple[WorkoutDay, ...],
    ruleset: ProgramRuleset,
) -> tuple[SplitPlan, tuple[WorkoutDay, ...], tuple[str, ...]]:
    if recovery_spacing_is_valid(days, ruleset):
        return split, days, ()
    original = tuple(day.weekday for day in days)
    if any(weekday is None for weekday in original):
        return split, days, ("RECOVERY_WEEKDAY_REPAIR_UNAVAILABLE",)
    original_days = tuple(int(weekday) for weekday in original if weekday is not None)
    options: list[tuple[int, tuple[int, ...], tuple[WorkoutDay, ...]]] = []
    for weekdays in combinations(range(ruleset.days_per_week), len(days)):
        scheduled = tuple(
            replace(day, weekday=weekday) for day, weekday in zip(days, weekdays, strict=True)
        )
        if recovery_spacing_is_valid(scheduled, ruleset):
            distance = sum(
                abs(candidate - current)
                for candidate, current in zip(weekdays, original_days, strict=True)
            )
            options.append((distance, weekdays, scheduled))
    if not options:
        return split, days, ("RECOVERY_WEEKDAY_REPAIR_UNAVAILABLE",)
    _, weekdays, scheduled = min(options, key=lambda item: (item[0], item[1]))
    repaired_split = replace(
        split,
        weekdays=weekdays,
        reason_codes=split.reason_codes
        + ("RECOVERY_WEEKDAYS_REARRANGED_FOR_DIRECT_MUSCLE_OVERLAP",),
    )
    return (
        repaired_split,
        scheduled,
        ("RECOVERY_WEEKDAYS_REARRANGED_FOR_DIRECT_MUSCLE_OVERLAP",),
    )
