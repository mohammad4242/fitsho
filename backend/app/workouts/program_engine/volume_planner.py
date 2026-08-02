import math
from collections import Counter

from app.exercises.enums import MuscleGroup
from app.workouts.program_engine.enums import (
    PhysicalJobDemand,
    RecoveryRating,
    SplitType,
    TrainingStatus,
)
from app.workouts.program_engine.rulesets.resistance_training_v1 import ProgramRuleset
from app.workouts.program_engine.schemas import (
    NormalizedProgramRequest,
    SplitPlan,
    VolumeTarget,
    WeeklyVolumePlan,
)

MAJOR_MUSCLES = (
    MuscleGroup.CHEST,
    MuscleGroup.BACK,
    MuscleGroup.SHOULDERS,
    MuscleGroup.GLUTES,
    MuscleGroup.QUADRICEPS,
    MuscleGroup.HAMSTRINGS,
    MuscleGroup.ABS,
    MuscleGroup.CALVES,
)


def plan_weekly_volume(
    request: NormalizedProgramRequest,
    split: SplitPlan,
    ruleset: ProgramRuleset,
) -> WeeklyVolumePlan:
    source = request.source
    minimum = ruleset.minimum_sets[request.training_status]
    maximum = ruleset.maximum_sets[request.training_status]
    base = min(max(ruleset.goal_base_sets[request.primary_goal], minimum), maximum)
    reasons: list[str] = []
    recovery_signals = sum(
        (
            source.sleep_quality is RecoveryRating.POOR,
            source.stress_level is RecoveryRating.POOR,
            source.physical_job_demand is PhysicalJobDemand.HIGH,
            source.recent_training_history.recovery_problems,
        )
    )
    if recovery_signals:
        base = max(
            minimum,
            base - ruleset.poor_recovery_set_reduction * recovery_signals,
        )
        reasons.append("VOLUME_REDUCED_FOR_RECOVERY")
    if source.session_duration_minutes <= ruleset.short_session_minutes:
        base = max(minimum, base - ruleset.contextual_volume_reduction_sets)
        reasons.append("VOLUME_REDUCED_FOR_TIME_LIMIT")
    if source.age >= ruleset.older_adult_modifier_age:
        base = max(minimum, base - ruleset.contextual_volume_reduction_sets)
        reasons.append("VOLUME_REDUCED_FOR_RECOVERY")

    soft_allowance = ruleset.soft_maximum_allowance_sets[request.training_status]
    if recovery_signals:
        soft_allowance = min(soft_allowance, 1)
    elif (
        request.training_status is TrainingStatus.ADVANCED
        and source.sleep_quality is RecoveryRating.GOOD
        and source.stress_level is RecoveryRating.GOOD
        and source.physical_job_demand is not PhysicalJobDemand.HIGH
        and not source.recent_training_history.recovery_problems
    ):
        soft_allowance += ruleset.good_recovery_soft_maximum_bonus_sets

    targets: list[VolumeTarget] = []
    direct_exposures = _direct_exposure_counts(split, source.priority_muscles)
    for muscle in MAJOR_MUSCLES:
        sets = base
        if source.priority_muscles and muscle not in source.priority_muscles:
            sets = max(minimum, sets - ruleset.contextual_volume_reduction_sets)
        if muscle in source.priority_muscles:
            sets = min(maximum, sets + ruleset.priority_muscle_bonus_sets)
            reasons.append("VOLUME_INCREASED_FOR_PRIORITY_MUSCLE")
        previous = source.recent_training_history.previous_weekly_sets_by_muscle.get(muscle)
        if previous is not None and previous > 0:
            increase_limit = max(
                previous,
                math.floor(previous * (1 + ruleset.max_previous_volume_increase)),
            )
            if sets > increase_limit:
                sets = increase_limit
                reasons.append("VOLUME_CAPPED_FOR_PREVIOUS_VOLUME")
        if split.split_type is SplitType.BODY_PART_ROTATION:
            split_maximum = (
                ruleset.max_sets_per_muscle_per_session * direct_exposures[muscle]
            )
            if sets > split_maximum:
                sets = split_maximum
                reasons.append("VOLUME_CAPPED_FOR_SPLIT_FREQUENCY")
        targets.append(
            VolumeTarget(
                muscle=muscle,
                minimum_soft=min(minimum, sets),
                target_sets=sets,
                maximum_soft=min(maximum, sets + soft_allowance),
                maximum_hard=maximum,
                fractional_sets=round(sets * ruleset.secondary_set_credit, 1),
            )
        )
    return WeeklyVolumePlan(targets=tuple(targets), reason_codes=tuple(dict.fromkeys(reasons)))


def _direct_exposure_counts(
    split: SplitPlan,
    priorities: frozenset[MuscleGroup],
) -> Counter[MuscleGroup]:
    if split.split_type is not SplitType.BODY_PART_ROTATION:
        return Counter()
    by_focus = {
        "chest_triceps": (MuscleGroup.CHEST,),
        "back_biceps": (MuscleGroup.BACK,),
        "shoulders_traps": (MuscleGroup.SHOULDERS,),
        "legs": (
            MuscleGroup.QUADRICEPS,
            MuscleGroup.HAMSTRINGS,
            MuscleGroup.GLUTES,
            MuscleGroup.CALVES,
            MuscleGroup.ABS,
        ),
        "quadriceps_calves": (MuscleGroup.QUADRICEPS, MuscleGroup.CALVES),
        "posterior_chain_core": (
            MuscleGroup.HAMSTRINGS,
            MuscleGroup.GLUTES,
            MuscleGroup.ABS,
        ),
    }
    counts: Counter[MuscleGroup] = Counter()
    for focus in split.day_focuses:
        if focus == "specialization":
            focus = _specialization_focus(priorities)
        counts.update(by_focus[focus])
    return counts


def _specialization_focus(priorities: frozenset[MuscleGroup]) -> str:
    for muscle_groups, focus in (
        ((MuscleGroup.CHEST, MuscleGroup.TRICEPS), "chest_triceps"),
        ((MuscleGroup.BACK, MuscleGroup.BICEPS), "back_biceps"),
        ((MuscleGroup.SHOULDERS, MuscleGroup.TRAPS), "shoulders_traps"),
        ((MuscleGroup.QUADRICEPS, MuscleGroup.CALVES), "quadriceps_calves"),
        ((MuscleGroup.HAMSTRINGS, MuscleGroup.GLUTES, MuscleGroup.ABS), "posterior_chain_core"),
    ):
        if priorities.intersection(muscle_groups):
            return focus
    return "chest_triceps"
