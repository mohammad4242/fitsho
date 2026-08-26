from collections import Counter, defaultdict
from dataclasses import replace
from enum import StrEnum
from itertools import combinations

from app.exercises.enums import MuscleGroup
from app.workouts.program_engine.enums import LoadLimit
from app.workouts.program_engine.rulesets.resistance_training_v1 import ProgramRuleset
from app.workouts.program_engine.schemas import SplitPlan, WorkoutDay
from app.workouts.program_engine.supplemental_policy import is_supplemental_muscle


class ExposureLoad(StrEnum):
    LIGHT = "light"
    MODERATE = "moderate"
    HIGH = "high"


def direct_muscles(day: WorkoutDay) -> frozenset[MuscleGroup]:
    return frozenset(
        item.primary_muscle
        for item in day.exercises
        if item.primary_muscle is not None and not is_supplemental_muscle(item.primary_muscle)
    )


def classify_muscle_exposures(
    day: WorkoutDay,
    ruleset: ProgramRuleset,
) -> dict[MuscleGroup, ExposureLoad]:
    direct_sets: Counter[MuscleGroup] = Counter()
    effective_sets: defaultdict[MuscleGroup, float] = defaultdict(float)
    high_load_muscles: set[MuscleGroup] = set()
    for exercise in day.exercises:
        if exercise.primary_muscle is not None and not is_supplemental_muscle(
            exercise.primary_muscle
        ):
            direct_sets[exercise.primary_muscle] += exercise.sets
            effective_sets[exercise.primary_muscle] += exercise.sets
            if "STRENGTH_PRIMARY_COMPOUND" in exercise.reason_codes or (
                exercise.axial_loading_level is LoadLimit.HIGH
            ):
                high_load_muscles.add(exercise.primary_muscle)
        for muscle in exercise.secondary_muscles:
            if is_supplemental_muscle(muscle):
                continue
            effective_sets[muscle] += exercise.sets * ruleset.secondary_set_credit
    exposures: dict[MuscleGroup, ExposureLoad] = {}
    for muscle in sorted(effective_sets, key=lambda item: item.value):
        direct = direct_sets[muscle]
        effective = effective_sets[muscle]
        if (
            muscle in high_load_muscles
            or direct >= ruleset.recovery_high_direct_sets
            or effective >= ruleset.recovery_high_effective_sets
        ):
            exposures[muscle] = ExposureLoad.HIGH
        elif (
            direct > ruleset.recovery_light_max_direct_sets
            or effective >= ruleset.recovery_moderate_effective_sets
        ):
            exposures[muscle] = ExposureLoad.MODERATE
        else:
            exposures[muscle] = ExposureLoad.LIGHT
    return exposures


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
        current_exposures = classify_muscle_exposures(current[1], ruleset)
        following_exposures = classify_muscle_exposures(following[1], ruleset)
        for muscle in sorted(
            set(current_exposures).intersection(following_exposures),
            key=lambda item: item.value,
        ):
            if following[0] - current[0] < _required_gap_days(
                current_exposures[muscle],
                following_exposures[muscle],
                ruleset,
            ):
                return False
    return True


def _required_gap_days(
    current: ExposureLoad,
    following: ExposureLoad,
    ruleset: ProgramRuleset,
) -> int:
    if ExposureLoad.HIGH in {current, following}:
        return ruleset.minimum_recovery_gap_days
    if current is ExposureLoad.MODERATE and following is ExposureLoad.MODERATE:
        return ruleset.minimum_recovery_gap_days
    return ruleset.recovery_light_gap_days


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
        + (
            "RECOVERY_WEEKDAYS_REARRANGED_FOR_DIRECT_MUSCLE_OVERLAP",
            "RECOVERY_WEEKDAYS_REARRANGED_FOR_EXPOSURE_LOAD",
        ),
    )
    return (
        repaired_split,
        scheduled,
        (
            "RECOVERY_WEEKDAYS_REARRANGED_FOR_DIRECT_MUSCLE_OVERLAP",
            "RECOVERY_WEEKDAYS_REARRANGED_FOR_EXPOSURE_LOAD",
        ),
    )
