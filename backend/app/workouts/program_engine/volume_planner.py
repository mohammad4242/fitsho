import math
from collections import Counter

from app.exercises.enums import MuscleGroup
from app.workouts.program_engine.body_analysis import (
    body_analysis_priority_muscles,
    eligible_body_analysis_priorities,
)
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
from app.workouts.program_engine.volume_history import (
    PreviousVolumeBaseline,
    derive_previous_volume_baseline,
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
# Calves remain a soft accessory target unless the user prioritizes them.
MINIMUM_COVERAGE_MUSCLES = frozenset(MAJOR_MUSCLES) - {MuscleGroup.CALVES}
SECONDARY_MUSCLES = (
    MuscleGroup.BICEPS,
    MuscleGroup.TRICEPS,
    MuscleGroup.TRAPS,
    MuscleGroup.FOREARMS,
)
TRACKED_MUSCLES = MAJOR_MUSCLES + SECONDARY_MUSCLES


def plan_weekly_volume(
    request: NormalizedProgramRequest,
    split: SplitPlan,
    ruleset: ProgramRuleset,
    *,
    previous_volume: PreviousVolumeBaseline | None = None,
    direct_exposure_counts: Counter[MuscleGroup] | None = None,
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

    secondary_minimum = ruleset.secondary_muscle_minimum_sets[request.training_status]
    secondary_maximum = ruleset.secondary_muscle_maximum_sets[request.training_status]
    secondary_base = min(
        max(ruleset.secondary_muscle_goal_base_sets[request.primary_goal], secondary_minimum),
        secondary_maximum,
    )
    if recovery_signals:
        secondary_base = max(
            secondary_minimum,
            secondary_base - ruleset.poor_recovery_set_reduction * recovery_signals,
        )
    if source.session_duration_minutes <= ruleset.short_session_minutes:
        secondary_base = max(
            secondary_minimum, secondary_base - ruleset.contextual_volume_reduction_sets
        )
    if source.age >= ruleset.older_adult_modifier_age:
        secondary_base = max(
            secondary_minimum, secondary_base - ruleset.contextual_volume_reduction_sets
        )

    targets: list[VolumeTarget] = []
    body_priorities = {
        item.muscle: item for item in eligible_body_analysis_priorities(request, ruleset)
    }
    effective_priorities = source.priority_muscles | body_analysis_priority_muscles(
        request, ruleset
    )
    direct_exposures = (
        direct_exposure_counts
        if direct_exposure_counts is not None
        else _direct_exposure_counts(split, effective_priorities)
    )
    previous_volume = previous_volume or derive_previous_volume_baseline(
        source.recent_training_history
    )
    reasons.extend(previous_volume.reason_codes)
    for muscle in TRACKED_MUSCLES:
        is_secondary = muscle in SECONDARY_MUSCLES
        muscle_minimum = secondary_minimum if is_secondary else minimum
        muscle_maximum = secondary_maximum if is_secondary else maximum
        sets = secondary_base if is_secondary else base
        if source.priority_muscles and muscle not in source.priority_muscles:
            sets = max(muscle_minimum, sets - ruleset.contextual_volume_reduction_sets)
        if muscle in source.priority_muscles:
            sets = min(muscle_maximum, sets + ruleset.priority_muscle_bonus_sets)
            reasons.append("VOLUME_INCREASED_FOR_PRIORITY_MUSCLE")
        body_priority = body_priorities.get(muscle)
        if body_priority is not None:
            bonus = (
                ruleset.body_analysis_clear_lag_bonus_sets
                if body_priority.classification == "clear_lag"
                else ruleset.body_analysis_mild_lag_bonus_sets
            )
            sets = min(muscle_maximum, sets + bonus)
            reasons.append("VOLUME_INCREASED_FOR_BODY_ANALYSIS")
        previous_effective = previous_volume.effective_sets_by_muscle.get(muscle)
        previous_direct = previous_volume.direct_sets_by_muscle.get(muscle)
        previous = previous_effective or previous_direct
        if previous is not None and previous > 0:
            increase_limit = math.floor(previous * (1 + ruleset.max_previous_volume_increase))
            if previous_effective is not None:
                increase_limit = max(muscle_minimum, increase_limit)
            if sets > increase_limit:
                sets = increase_limit
                reasons.append(
                    "VOLUME_CAPPED_FOR_PREVIOUS_EFFECTIVE_VOLUME"
                    if previous_effective is not None
                    else "VOLUME_CAPPED_FOR_PREVIOUS_VOLUME"
                )
        if split.split_type is SplitType.BODY_PART_ROTATION and direct_exposures[muscle] > 0:
            split_maximum = ruleset.max_sets_per_muscle_per_session * direct_exposures[muscle]
            if sets > split_maximum:
                sets = split_maximum
                reasons.append("VOLUME_CAPPED_FOR_SPLIT_FREQUENCY")
        targets.append(
            VolumeTarget(
                muscle=muscle,
                minimum_soft=min(muscle_minimum, sets),
                target_sets=sets,
                maximum_soft=min(muscle_maximum, sets + soft_allowance),
                maximum_hard=muscle_maximum,
                fractional_sets=round(sets * ruleset.secondary_set_credit, 1),
                effective_target_sets=sets,
                minimum_direct_sets=min(muscle_minimum, sets),
                minimum_effective_sets=min(
                    (
                        muscle_minimum
                        if muscle in effective_priorities
                        else ruleset.minimum_coverage_sets[request.training_status]
                    ),
                    sets,
                ),
                minimum_coverage_required=(
                    muscle in MINIMUM_COVERAGE_MUSCLES or muscle in effective_priorities
                ),
                direct_minimum_required=muscle in effective_priorities,
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
        "chest_triceps": (MuscleGroup.CHEST, MuscleGroup.TRICEPS),
        "back_biceps": (MuscleGroup.BACK, MuscleGroup.BICEPS),
        "shoulders_traps": (MuscleGroup.SHOULDERS, MuscleGroup.TRAPS),
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
