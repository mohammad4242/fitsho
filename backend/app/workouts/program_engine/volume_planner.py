import math
from collections import Counter
from dataclasses import replace

from app.exercises.enums import MuscleGroup
from app.workouts.program_engine.body_analysis import (
    eligible_body_analysis_priorities,
)
from app.workouts.program_engine.duration_capacity import SessionCapacity
from app.workouts.program_engine.enums import Goal, SplitType
from app.workouts.program_engine.priority_allocation import PriorityAllocationPolicy
from app.workouts.program_engine.rulesets.resistance_training_v1 import ProgramRuleset
from app.workouts.program_engine.schemas import (
    NormalizedProgramRequest,
    SplitPlan,
    VolumeTarget,
    WeeklyVolumePlan,
)
from app.workouts.program_engine.session_coherence import (
    SessionCoherence,
    specialization_focus_for_priorities,
)
from app.workouts.program_engine.supplemental_policy import SUPPLEMENTAL_MUSCLES
from app.workouts.program_engine.volume_history import (
    PreviousVolumeBaseline,
    derive_previous_volume_baseline,
)
from app.workouts.program_engine.volume_policy import (
    VOLUME_POLICY,
    recovery_burden_for_request,
    session_hard_volume_cap,
    weekly_direct_volume_range,
)

MAJOR_MUSCLES = (
    MuscleGroup.CHEST,
    MuscleGroup.BACK,
    MuscleGroup.SHOULDERS,
    MuscleGroup.GLUTES,
    MuscleGroup.QUADRICEPS,
    MuscleGroup.HAMSTRINGS,
    MuscleGroup.CALVES,
)
EXPECTED_COMPOUND_SECONDARY_MUSCLES = 2
# Calves remain a soft accessory target unless the user prioritizes them.
MINIMUM_COVERAGE_MUSCLES = frozenset(MAJOR_MUSCLES) - {MuscleGroup.CALVES}
SECONDARY_MUSCLES = (
    MuscleGroup.BICEPS,
    MuscleGroup.TRICEPS,
    MuscleGroup.TRAPS,
)
PLANNED_MUSCLES = MAJOR_MUSCLES + SECONDARY_MUSCLES
TRACKED_MUSCLES = PLANNED_MUSCLES + tuple(
    sorted(SUPPLEMENTAL_MUSCLES, key=lambda muscle: muscle.value)
)


def plan_weekly_volume(
    request: NormalizedProgramRequest,
    split: SplitPlan,
    ruleset: ProgramRuleset,
    *,
    previous_volume: PreviousVolumeBaseline | None = None,
    direct_exposure_counts: Counter[MuscleGroup] | None = None,
    session_capacity: SessionCapacity | None = None,
) -> WeeklyVolumePlan:
    source = request.source
    minimum = ruleset.minimum_sets[request.training_status]
    maximum = ruleset.maximum_sets[request.training_status]
    secondary_minimum = ruleset.secondary_muscle_minimum_sets[request.training_status]
    secondary_maximum = ruleset.secondary_muscle_maximum_sets[request.training_status]
    reasons: list[str] = []
    common_constraint_reasons: list[str] = []
    recovery_burden = recovery_burden_for_request(request)
    if recovery_burden.reason_code is not None:
        reasons.extend(("VOLUME_REDUCED_FOR_RECOVERY", recovery_burden.reason_code))
        common_constraint_reasons.extend(
            ("VOLUME_REDUCED_FOR_RECOVERY", recovery_burden.reason_code)
        )
    if source.session_duration_minutes <= ruleset.short_session_minutes:
        reasons.append("VOLUME_REDUCED_FOR_TIME_LIMIT")
        common_constraint_reasons.append("VOLUME_REDUCED_FOR_TIME_LIMIT")
    if source.age >= ruleset.older_adult_modifier_age:
        reasons.append("VOLUME_REDUCED_FOR_RECOVERY")
        common_constraint_reasons.append("VOLUME_REDUCED_FOR_RECOVERY")

    targets: list[VolumeTarget] = []
    body_priorities = {
        item.muscle: item for item in eligible_body_analysis_priorities(request, ruleset)
    }
    priority_policy = PriorityAllocationPolicy.for_request(request, ruleset)
    effective_priorities = frozenset(priority_policy.priorities)
    explicit_priorities = frozenset(priority_policy.explicit_priorities)
    baseline_sets: dict[MuscleGroup, int] = {}
    for muscle in PLANNED_MUSCLES:
        is_secondary = muscle in SECONDARY_MUSCLES
        range_limit = weekly_direct_volume_range(muscle, request.source.training_age_months)
        if range_limit:
            muscle_minimum = range_limit.minimum
            muscle_maximum = range_limit.maximum
        else:
            muscle_minimum = secondary_minimum if is_secondary else minimum
            muscle_maximum = secondary_maximum if is_secondary else maximum
        target = VOLUME_POLICY.preferred_target(
            muscle,
            request.training_status,
            request.primary_goal,
        )
        target -= recovery_burden.reduction_sets
        if source.session_duration_minutes <= ruleset.short_session_minutes:
            target -= ruleset.contextual_volume_reduction_sets
        if source.age >= ruleset.older_adult_modifier_age:
            target -= ruleset.contextual_volume_reduction_sets
        baseline_sets[muscle] = min(max(target, muscle_minimum), muscle_maximum)
    if explicit_priorities:

        def _get_min(m: MuscleGroup) -> int:
            r = weekly_direct_volume_range(m, request.source.training_age_months)
            return r.minimum if r else (secondary_minimum if m in SECONDARY_MUSCLES else minimum)

        baseline_sets = {
            muscle: (
                sets
                if muscle in explicit_priorities
                else max(
                    _get_min(muscle),
                    sets - ruleset.contextual_volume_reduction_sets,
                )
            )
            for muscle, sets in baseline_sets.items()
        }

    def _get_max(m: MuscleGroup) -> int:
        r = weekly_direct_volume_range(m, request.source.training_age_months)
        return r.maximum if r else (secondary_maximum if m in SECONDARY_MUSCLES else maximum)

    hard_maximums = {muscle: _get_max(muscle) for muscle in PLANNED_MUSCLES}
    priority_bonuses = priority_policy.volume_bonuses(
        baseline_sets,
        hard_maximums,
        ruleset,
    )
    if len(priority_policy.explicit_priorities) > 1:
        reasons.append("PRIORITY_EMPHASIS_BUDGET_SHARED")
    if len(priority_policy.explicit_priorities) > len(ruleset.priority_emphasis_budgets):
        reasons.append("PRIORITY_EMPHASIS_BUDGET_CAPPED")
    direct_exposures = (
        direct_exposure_counts
        if direct_exposure_counts is not None
        else _direct_exposure_counts(split, effective_priorities)
    )
    previous_volume = previous_volume or derive_previous_volume_baseline(
        source.recent_training_history
    )
    positive_history_support = _positive_history_supports_soft_cap_override(
        request,
        previous_volume,
        ruleset,
    )
    reasons.extend(previous_volume.reason_codes)
    for muscle in PLANNED_MUSCLES:
        constraint_reasons = list(common_constraint_reasons)
        is_secondary = muscle in SECONDARY_MUSCLES
        range_limit = weekly_direct_volume_range(muscle, request.source.training_age_months)
        if range_limit:
            muscle_minimum = range_limit.minimum
            muscle_maximum = range_limit.maximum
        else:
            muscle_minimum = secondary_minimum if is_secondary else minimum
            muscle_maximum = secondary_maximum if is_secondary else maximum
        safe_maximum = muscle_maximum
        acceptable_ceiling = muscle_maximum
        sets = baseline_sets[muscle]
        if muscle in explicit_priorities:
            bonus = priority_bonuses[muscle]
            sets = min(muscle_maximum, sets + bonus)
            if bonus:
                reasons.append("VOLUME_INCREASED_FOR_PRIORITY_MUSCLE")
                reasons.append("PRIORITY_VOLUME_INCREASED")
        body_priority = body_priorities.get(muscle)
        if body_priority is not None and muscle in explicit_priorities:
            reasons.append("BODY_ANALYSIS_SUPPORTS_EXPLICIT_PRIORITY")
        elif body_priority is not None:
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
            reason = (
                "VOLUME_CAPPED_FOR_PREVIOUS_EFFECTIVE_VOLUME"
                if previous_effective is not None
                else "VOLUME_CAPPED_FOR_PREVIOUS_VOLUME"
            )
            if sets > increase_limit and positive_history_support:
                sets = min(
                    sets,
                    increase_limit + VOLUME_POLICY.supported_previous_volume_override_sets,
                )
                acceptable_ceiling = min(acceptable_ceiling, sets)
                reasons.append("PREVIOUS_VOLUME_SOFT_CAP_OVERRIDDEN_WITH_POSITIVE_HISTORY")
                constraint_reasons.append(
                    "PREVIOUS_VOLUME_SOFT_CAP_OVERRIDDEN_WITH_POSITIVE_HISTORY"
                )
            elif sets > increase_limit:
                sets = increase_limit
                acceptable_ceiling = min(acceptable_ceiling, increase_limit)
            if increase_limit < muscle_maximum and not positive_history_support:
                reasons.append(reason)
                constraint_reasons.append(reason)
        if split.split_type is SplitType.BODY_PART_ROTATION and direct_exposures[muscle] > 0:
            feasible_exposures = max(
                direct_exposures[muscle],
                (priority_policy.preferred_frequency if muscle in effective_priorities else 0),
            )
            session_cap = session_hard_volume_cap(request.source.training_age_months)
            split_maximum = session_cap * feasible_exposures
            if sets > split_maximum:
                sets = split_maximum
            if split_maximum < muscle_maximum:
                reasons.append("VOLUME_CAPPED_FOR_SPLIT_FREQUENCY")
                constraint_reasons.append("VOLUME_CAPPED_FOR_SPLIT_FREQUENCY")
            safe_maximum = min(safe_maximum, split_maximum)
            acceptable_ceiling = min(acceptable_ceiling, split_maximum)
        if recovery_burden.reduction_sets or source.age >= ruleset.older_adult_modifier_age:
            acceptable_ceiling = min(acceptable_ceiling, sets)
        flexibility = VOLUME_POLICY.flexibility_sets(sets)
        minimum_useful = VOLUME_POLICY.minimum_useful_target(
            muscle,
            request.training_status,
        )
        acceptable_minimum = max(
            min(muscle_minimum, sets),
            min(minimum_useful, sets),
            sets - flexibility,
        )
        acceptable_maximum = min(
            safe_maximum,
            acceptable_ceiling,
            sets + flexibility,
        )
        # Secondary muscles (biceps, triceps, traps, forearms) as priorities in 1-2 day
        # full-body programs cannot realistically satisfy a direct-only minimum — compounds
        # in those sessions cover them effectively.  Only enforce the hard direct minimum
        # when the program has ≥3 days (enough room for dedicated work) or the muscle is
        # a primary major muscle group.
        has_dedicated_exposure = (
            split.split_type is SplitType.BODY_PART_ROTATION and direct_exposures[muscle] > 0
        )
        is_explicit_priority = muscle in explicit_priorities
        direct_min_required = is_explicit_priority and (
            muscle not in SECONDARY_MUSCLES or has_dedicated_exposure or len(split.day_focuses) >= 3
        )
        # For secondary muscles without a dedicated session, coverage via compound secondary
        # stimulation is sufficient — don't enforce a hard coverage requirement.
        secondary_without_session = muscle in SECONDARY_MUSCLES and not has_dedicated_exposure
        coverage_required = muscle in MINIMUM_COVERAGE_MUSCLES or (
            is_explicit_priority and not secondary_without_session
        )
        # Use the soft coverage minimum (not the full muscle_minimum) for secondary muscles
        # without dedicated sessions so that compound secondary stimulation can satisfy it.
        effective_minimum = (
            ruleset.minimum_coverage_sets[request.training_status]
            if secondary_without_session and muscle in effective_priorities
            else (
                muscle_minimum
                if is_explicit_priority
                else ruleset.minimum_coverage_sets[request.training_status]
            )
        )
        targets.append(
            VolumeTarget(
                muscle=muscle,
                minimum_soft=acceptable_minimum,
                target_sets=sets,
                maximum_soft=acceptable_maximum,
                maximum_hard=safe_maximum,
                fractional_sets=round(sets * ruleset.secondary_set_credit, 1),
                effective_target_sets=sets,
                minimum_direct_sets=min(muscle_minimum, sets),
                minimum_effective_sets=min(effective_minimum, sets),
                minimum_coverage_required=coverage_required,
                direct_minimum_required=direct_min_required,
                constraint_reason_codes=tuple(dict.fromkeys(constraint_reasons)),
            )
        )
    plan = WeeklyVolumePlan(
        targets=tuple(targets),
        reason_codes=tuple(dict.fromkeys(reasons)),
    )
    if session_capacity is None:
        return plan
    return _limit_volume_to_duration_capacity(
        plan,
        request,
        split,
        ruleset,
        session_capacity,
        baseline_sets,
        {muscle: item.classification for muscle, item in body_priorities.items()},
    )


def _limit_volume_to_duration_capacity(
    plan: WeeklyVolumePlan,
    request: NormalizedProgramRequest,
    split: SplitPlan,
    ruleset: ProgramRuleset,
    session_capacity: SessionCapacity,
    baseline_sets: dict[MuscleGroup, int],
    body_classifications: dict[MuscleGroup, str],
) -> WeeklyVolumePlan:
    explicit_priorities = request.source.priority_muscles - SUPPLEMENTAL_MUSCLES
    weekly_working_set_capacity = session_capacity.expected_working_set_capacity * len(
        split.day_focuses
    )
    secondary_credit_slots = (
        EXPECTED_COMPOUND_SECONDARY_MUSCLES
        if request.primary_goal in {Goal.HYPERTROPHY, Goal.MUSCLE_GAIN, Goal.STRENGTH}
        else 1
    )
    effective_capacity = math.floor(
        weekly_working_set_capacity * (1 + secondary_credit_slots * ruleset.secondary_set_credit)
    )
    floors = {
        target.muscle: min(
            target.target_sets,
            max(
                target.minimum_direct_sets if target.direct_minimum_required else 0,
                target.minimum_effective_sets,
            ),
        )
        for target in plan.targets
    }
    budget = max(effective_capacity, sum(floors.values()))
    total_preferred = sum(target.target_sets for target in plan.targets)
    if budget >= total_preferred:
        return plan

    units: list[tuple[int, str, int, MuscleGroup]] = []
    for target in plan.targets:
        muscle = target.muscle
        baseline = min(baseline_sets[muscle], target.target_sets)
        classification = body_classifications.get(muscle)
        for set_number in range(floors[muscle] + 1, target.target_sets + 1):
            if muscle in explicit_priorities:
                rank = 900
            elif set_number <= baseline and muscle in MAJOR_MUSCLES:
                rank = 600
            elif classification == "clear_lag":
                rank = 500
            elif classification == "mild_lag":
                rank = 400
            elif set_number <= baseline:
                rank = 200
            else:
                rank = 100
            units.append((-rank, muscle.value, set_number, muscle))
    allocated = Counter(floors)
    for _rank, _muscle_name, _set_number, muscle in sorted(units)[
        : max(0, budget - sum(floors.values()))
    ]:
        allocated[muscle] += 1

    targets: list[VolumeTarget] = []
    for target in plan.targets:
        preferred = allocated[target.muscle]
        if preferred >= target.target_sets:
            targets.append(target)
            continue
        flexibility = VOLUME_POLICY.flexibility_sets(preferred) if preferred else 0
        minimum_soft = max(floors[target.muscle], preferred - flexibility)
        maximum_soft = min(
            target.maximum_hard,
            target.maximum_soft,
            preferred + flexibility,
        )
        targets.append(
            replace(
                target,
                minimum_soft=minimum_soft,
                target_sets=preferred,
                maximum_soft=max(minimum_soft, maximum_soft),
                fractional_sets=round(preferred * ruleset.secondary_set_credit, 1),
                effective_target_sets=preferred,
                minimum_direct_sets=min(target.minimum_direct_sets, preferred),
                minimum_effective_sets=min(target.minimum_effective_sets, preferred),
                constraint_reason_codes=tuple(
                    dict.fromkeys(
                        (*target.constraint_reason_codes, "DURATION_CAPACITY_LIMITED_VOLUME")
                    )
                ),
            )
        )
    return WeeklyVolumePlan(
        targets=tuple(targets),
        reason_codes=tuple(
            dict.fromkeys((*plan.reason_codes, "VOLUME_REDUCED_FOR_DURATION_CAPACITY"))
        ),
    )


def _positive_history_supports_soft_cap_override(
    request: NormalizedProgramRequest,
    previous_volume: PreviousVolumeBaseline,
    ruleset: ProgramRuleset,
) -> bool:
    history = request.source.recent_training_history
    performance_trend = (history.performance_trend or "").strip().lower()
    return (
        previous_volume.confidence >= ruleset.adaptation_min_volume_confidence_for_progression
        and history.completed_session_ratio >= ruleset.adaptation_min_adherence_for_progression
        and not history.recovery_problems
        and performance_trend in {"stable", "improving"}
    )


def _direct_exposure_counts(
    split: SplitPlan,
    priorities: frozenset[MuscleGroup],
) -> Counter[MuscleGroup]:
    if split.split_type is not SplitType.BODY_PART_ROTATION:
        return Counter()
    counts: Counter[MuscleGroup] = Counter()
    for focus in split.day_focuses:
        if focus == "specialization":
            focus = specialization_focus_for_priorities(priorities)
        counts.update(SessionCoherence.from_dynamic_focus(focus).allowed_direct_muscles)
    return counts


def _specialization_focus(priorities: frozenset[MuscleGroup]) -> str:
    return specialization_focus_for_priorities(priorities)
