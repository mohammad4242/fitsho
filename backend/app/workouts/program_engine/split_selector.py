from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass, replace

from app.exercises.enums import ExerciseType, MovementPattern, MuscleGroup
from app.workouts.program_engine.duration_capacity import (
    CapacityFeasibility,
    PlannedWorkCost,
    SessionCapacity,
    SessionCapacityAssessment,
    assess_session_capacity,
    build_session_capacity,
    estimate_candidate_cost,
)
from app.workouts.program_engine.duration_policy import is_main_training_exercise
from app.workouts.program_engine.enums import (
    CompatibilityLevel,
    Goal,
    SplitType,
    TrainingStatus,
)
from app.workouts.program_engine.focus_topology import (
    MUSCLE_SPECIFIC_UPPER_PRIORITIES,
    FocusAffinity,
    priority_affinity,
)
from app.workouts.program_engine.priority_allocation import PriorityAllocationPolicy
from app.workouts.program_engine.rulesets.resistance_training_v1 import ProgramRuleset
from app.workouts.program_engine.schemas import (
    ExerciseCandidate,
    NormalizedProgramRequest,
    SplitCandidate,
    SplitPlan,
)
from app.workouts.program_engine.session_builder import slots_for_focus
from app.workouts.program_engine.session_coherence import specialization_focus_for_priorities
from app.workouts.program_engine.slot_compatibility import (
    evaluate_candidate_slot_compatibility,
    focus_scope,
)
from app.workouts.program_engine.supplemental_policy import (
    SUPPLEMENTAL_MUSCLES,
    is_supplemental_muscle,
)
from app.workouts.program_engine.topology_preference import (
    is_professional_topology_scope,
    professional_topology_preference,
)
from app.workouts.program_engine.volume_policy import recovery_burden_for_request

_DYNAMIC_FOCUSES = (
    "upper",
    "lower",
    "push",
    "pull",
    "legs",
    "chest_triceps",
    "back_biceps",
    "biceps",
    "triceps",
    "shoulders_traps",
    "quadriceps_calves",
    "posterior_chain_core",
    "full_body",
    "full_body_b",
    "full_body_c",
    "full_body_d",
)

UPPER_REGION_MUSCLES = frozenset(
    {
        MuscleGroup.CHEST,
        MuscleGroup.BACK,
        MuscleGroup.SHOULDERS,
        MuscleGroup.BICEPS,
        MuscleGroup.TRICEPS,
        MuscleGroup.TRAPS,
    }
)
LOWER_REGION_MUSCLES = frozenset(
    {
        MuscleGroup.QUADRICEPS,
        MuscleGroup.HAMSTRINGS,
        MuscleGroup.GLUTES,
        MuscleGroup.CALVES,
        MuscleGroup.ADDUCTORS,
        MuscleGroup.ABDUCTORS,
        MuscleGroup.LEGS,
    }
)


def classify_template_region(muscles: Iterable[MuscleGroup]) -> str | None:
    """Classify a template region using only split-driving muscles."""
    region = frozenset(muscles).difference(SUPPLEMENTAL_MUSCLES)
    if region and region <= UPPER_REGION_MUSCLES:
        return "upper"
    if region and region <= LOWER_REGION_MUSCLES:
        return "lower"
    return None


@dataclass(frozen=True)
class _FocusAvailability:
    focus: str
    candidate_count: int
    preferred_slots: int
    suboptimal_slots: int
    relaxed_slots: int
    required_slots: int
    patterns: frozenset[MovementPattern]
    muscles: frozenset[MuscleGroup]
    compound_count: int
    priority_affinity_score: int
    duration_status: CapacityFeasibility
    required_work_minutes: int
    optional_work_likely_trimmed: int

    @property
    def is_feasible(self) -> bool:
        return (
            self.preferred_slots + self.suboptimal_slots + self.relaxed_slots == self.required_slots
        )


def select_split(request: NormalizedProgramRequest, ruleset: ProgramRuleset) -> SplitPlan:
    return rank_split_candidates(request, ruleset)[0]


def rank_split_candidates(
    request: NormalizedProgramRequest,
    ruleset: ProgramRuleset,
    *,
    exercises: tuple[ExerciseCandidate, ...] = (),
    session_capacity: SessionCapacity | None = None,
) -> tuple[SplitPlan, ...]:
    available_days = min(request.resistance_training_days, ruleset.max_resistance_days)
    recovery_limited = _recovery_is_limited(request)
    preferred_days = min(
        available_days,
        ruleset.recommended_resistance_days[request.training_status],
    )
    if recovery_limited:
        preferred_days = max(1, preferred_days - ruleset.poor_recovery_session_reduction)
    if request.training_status is TrainingStatus.NOVICE and recovery_limited:
        preferred_days = min(preferred_days, ruleset.maximum_novice_recovery_days)

    candidates = generate_split_candidates(available_days)
    scored = score_split_candidates(
        request,
        candidates,
        ruleset,
        preferred_days,
        exercises=exercises,
        session_capacity=session_capacity,
    )
    ranked: list[SplitPlan] = []
    for candidate in scored:
        reasons = list(candidate.reason_codes)
        if request.source.available_training_days > ruleset.max_resistance_days:
            reasons.append("RESISTANCE_DAYS_CAPPED_AT_RULESET_MAXIMUM")
        if len(candidate.day_focuses) < request.source.available_training_days:
            reasons.append("SPLIT_SELECTED_FOR_APPROPRIATE_SESSION_COUNT")
        ranked.append(replace(candidate, reason_codes=tuple(dict.fromkeys(reasons))))
    return tuple(ranked)


def rank_availability_aware_fallbacks(
    request: NormalizedProgramRequest,
    exercises: tuple[ExerciseCandidate, ...],
    ruleset: ProgramRuleset,
    *,
    weekdays: tuple[int, ...],
    excluded_layouts: frozenset[tuple[str, ...]] = frozenset(),
    limit: int = 12,
    session_capacity: SessionCapacity | None = None,
) -> tuple[SplitPlan, ...]:
    """Rank exact-day layouts that the current safe candidate pool can fill."""

    requested_days = request.resistance_training_days
    if requested_days < 1 or len(weekdays) != requested_days or limit <= 0:
        return ()
    capacity = session_capacity or build_session_capacity(
        request,
        exercises,
        ruleset,
    )
    target_capacity = max(1, capacity.expected_exercise_count_capacity)
    priorities = frozenset(PriorityAllocationPolicy.for_request(request, ruleset).priorities)
    availability = tuple(
        item
        for focus in _DYNAMIC_FOCUSES
        if (
            item := _focus_availability(
                focus,
                exercises,
                priorities,
                request,
                ruleset,
                capacity,
            )
        ).is_feasible
        and item.candidate_count
        >= max(1, min(ruleset.minimum_exercises_per_session, target_capacity) - 2)
    )
    if not availability:
        return ()

    beam: list[tuple[str, ...]] = [()]
    beam_width = max(limit * 24, 96)
    for _position in range(requested_days):
        expanded: list[tuple[str, ...]] = []
        for partial in beam:
            for item in availability:
                if partial and partial[-1] == item.focus:
                    continue
                candidate = (*partial, item.focus)
                if _has_short_gap_overlap(candidate, weekdays, availability, final=False):
                    continue
                expanded.append(candidate)
        beam = sorted(
            set(expanded),
            key=lambda layout: _dynamic_layout_sort_key(
                layout,
                availability,
                request,
                target_capacity,
            ),
        )[:beam_width]
        if not beam:
            return ()

    excluded_signatures = {_layout_signature(layout) for layout in excluded_layouts}
    layouts = [
        layout
        for layout in beam
        if _layout_signature(layout) not in excluded_signatures
        and not _has_short_gap_overlap(layout, weekdays, availability, final=True)
    ]
    ranked = sorted(
        layouts,
        key=lambda layout: _dynamic_layout_sort_key(
            layout,
            availability,
            request,
            target_capacity,
        ),
    )[:limit]
    return tuple(
        SplitPlan(
            split_type=SplitType.DYNAMIC_FALLBACK,
            day_focuses=layout,
            weekdays=weekdays,
            score=-1000 - index,
            reason_codes=(
                "DYNAMIC_EXACT_N_FALLBACK",
                "DYNAMIC_LAYOUT_RANKED_FROM_ELIGIBLE_POOL",
                "DYNAMIC_LAYOUT_RECOVERY_SPACING_SCREENED",
                "DYNAMIC_LAYOUT_DURATION_CAPACITY_SCREENED",
            ),
        )
        for index, layout in enumerate(ranked)
    )


def _layout_signature(layout: tuple[str, ...]) -> tuple[str, ...]:
    return tuple("lower" if focus == "legs" else focus for focus in layout)


def _focus_availability(
    focus: str,
    exercises: tuple[ExerciseCandidate, ...],
    priorities: frozenset[MuscleGroup],
    request: NormalizedProgramRequest,
    ruleset: ProgramRuleset,
    session_capacity: SessionCapacity,
) -> _FocusAvailability:
    focus_patterns, focus_muscles = focus_scope(focus)
    compatible = tuple(
        item
        for item in exercises
        if not is_supplemental_muscle(item.primary_muscle)
        and evaluate_candidate_slot_compatibility(
            item,
            allowed_patterns=focus_patterns,
            target_muscles=focus_muscles,
            day_focus=focus,
            allow_full_body=focus.startswith("full_body"),
        ).compatible
    )
    preferred = 0
    suboptimal = 0
    relaxed = 0
    required_slots = tuple(slot for slot in slots_for_focus(focus) if slot.required)
    for slot in required_slots:
        levels = tuple(
            evaluate_candidate_slot_compatibility(
                item,
                allowed_patterns=slot.patterns,
                target_muscles=(
                    frozenset({slot.target_muscle}) if slot.target_muscle is not None else None
                ),
                day_focus=focus,
                allow_full_body=focus.startswith("full_body"),
            ).level
            for item in exercises
        )
        if CompatibilityLevel.PREFERRED in levels:
            preferred += 1
        elif CompatibilityLevel.VALID_BUT_SUBOPTIMAL in levels:
            suboptimal += 1
        elif slot.target_muscle is not None and any(
            item.movement_pattern in slot.patterns for item in exercises
        ):
            relaxed += 1
        elif request.source.blocked_caution_tags and len(compatible) >= max(
            1,
            min(
                ruleset.minimum_exercises_per_session,
                session_capacity.expected_exercise_count_capacity,
            )
            - 2,
        ):
            relaxed += 1
    duration = _focus_duration_assessment(
        request,
        focus,
        exercises,
        ruleset,
        session_capacity,
    )
    return _FocusAvailability(
        focus=focus,
        candidate_count=len(compatible),
        preferred_slots=preferred,
        suboptimal_slots=suboptimal,
        relaxed_slots=relaxed,
        required_slots=len(required_slots),
        patterns=frozenset(item.movement_pattern for item in compatible),
        muscles=frozenset(
            item.primary_muscle for item in compatible if item.primary_muscle is not None
        ),
        compound_count=sum(item.exercise_type is ExerciseType.COMPOUND for item in compatible),
        priority_affinity_score=sum(
            ruleset.priority_affinity_weights[priority_affinity(focus, muscle)]
            for muscle in priorities
        ),
        duration_status=duration.status,
        required_work_minutes=duration.required_work_cost_minutes,
        optional_work_likely_trimmed=duration.optional_work_likely_trimmed,
    )


def _has_short_gap_overlap(
    layout: tuple[str, ...],
    weekdays: tuple[int, ...],
    availability: tuple[_FocusAvailability, ...],
    *,
    final: bool,
) -> bool:
    by_focus = {item.focus: item for item in availability}
    for index in range(1, len(layout)):
        if weekdays[index] - weekdays[index - 1] >= 2:
            continue
        if by_focus[layout[index - 1]].muscles.intersection(by_focus[layout[index]].muscles):
            return True
    if final and len(layout) > 1 and weekdays[0] + 7 - weekdays[-1] < 2:
        return bool(by_focus[layout[-1]].muscles.intersection(by_focus[layout[0]].muscles))
    return False


def _dynamic_layout_sort_key(
    layout: tuple[str, ...],
    availability: tuple[_FocusAvailability, ...],
    request: NormalizedProgramRequest,
    target_capacity: int,
) -> tuple[object, ...]:
    by_focus = {item.focus: item for item in availability}
    selected = tuple(by_focus[focus] for focus in layout)
    counts = Counter(layout)
    covered_patterns = frozenset(pattern for item in selected for pattern in item.patterns)
    covered_muscles = frozenset(muscle for item in selected for muscle in item.muscles)
    required_pattern_groups = (
        frozenset({MovementPattern.HORIZONTAL_PUSH, MovementPattern.VERTICAL_PUSH}),
        frozenset({MovementPattern.HORIZONTAL_PULL, MovementPattern.VERTICAL_PULL}),
        frozenset({MovementPattern.SQUAT, MovementPattern.LUNGE, MovementPattern.KNEE_EXTENSION}),
        frozenset({MovementPattern.HIP_HINGE, MovementPattern.HIP_EXTENSION}),
    )
    missing_pattern_groups = sum(
        not covered_patterns.intersection(group) for group in required_pattern_groups
    )
    missing_priorities = sum(
        not any(priority_affinity(focus, muscle) is not FocusAffinity.NONE for focus in layout)
        for muscle in request.source.priority_muscles - SUPPLEMENTAL_MUSCLES
    )
    duration_shortfall = sum(max(0, target_capacity - item.candidate_count) for item in selected)
    duration_infeasible = sum(
        item.duration_status is CapacityFeasibility.PROVABLY_INFEASIBLE for item in selected
    )
    duration_tight = sum(
        item.duration_status is CapacityFeasibility.FEASIBLE_BUT_TIGHT for item in selected
    )
    duration_optional_trim = sum(item.optional_work_likely_trimmed for item in selected)
    suboptimal_slots = sum(item.suboptimal_slots for item in selected)
    relaxed_slots = sum(item.relaxed_slots for item in selected)
    if request.primary_goal is Goal.STRENGTH:
        goal_fit = sum(item.compound_count == 0 for item in selected)
    elif request.primary_goal in {Goal.HYPERTROPHY, Goal.MUSCLE_GAIN}:
        goal_fit = -len(covered_muscles)
    else:
        goal_fit = -len(covered_patterns)
    experience_fit = (
        len(counts)
        if request.training_status is TrainingStatus.NOVICE
        else -len(counts)
        if request.training_status is TrainingStatus.ADVANCED
        else 0
    )
    priority_opportunities = sum(item.priority_affinity_score for item in selected)
    repetition = sum(max(0, count - 1) ** 2 for count in counts.values())
    broad_focuses = sum(focus.startswith("full_body") for focus in layout)
    return (
        missing_pattern_groups,
        missing_priorities,
        duration_infeasible,
        duration_shortfall,
        duration_tight,
        duration_optional_trim,
        goal_fit,
        experience_fit,
        relaxed_slots,
        suboptimal_slots,
        -priority_opportunities,
        repetition,
        broad_focuses,
        -len(counts),
        layout,
    )


def generate_split_candidates(days: int) -> tuple[SplitCandidate, ...]:
    structures: dict[int, tuple[SplitCandidate, ...]] = {
        1: (SplitCandidate(SplitType.FULL_BODY, ("full_body",)),),
        2: (
            SplitCandidate(
                SplitType.FULL_BODY_AB,
                ("full_body_a", "full_body_b"),
            ),
        ),
        3: (
            SplitCandidate(
                SplitType.FULL_BODY_ABC,
                ("full_body_a", "full_body_b", "full_body_c"),
            ),
        ),
        4: (
            SplitCandidate(
                SplitType.UPPER_LOWER,
                ("upper", "lower", "upper", "lower"),
            ),
            SplitCandidate(
                SplitType.UPPER_LOWER_SPECIALIZATION,
                ("upper", "lower", "upper", "specialization"),
            ),
            SplitCandidate(
                SplitType.FULL_BODY_FOUR,
                ("full_body", "full_body_b", "full_body_c", "full_body_d"),
            ),
            SplitCandidate(
                SplitType.UPPER_LOWER_FULL,
                ("upper", "lower", "full_body", "full_body"),
            ),
            SplitCandidate(
                SplitType.PHUL,
                ("upper", "lower", "upper", "lower"),
            ),
            SplitCandidate(
                SplitType.BODY_PART_ROTATION,
                ("chest_triceps", "back_biceps", "legs", "shoulders_traps"),
            ),
        ),
        5: (
            SplitCandidate(
                SplitType.UPPER_LOWER_SPECIALIZATION,
                ("upper", "lower", "upper", "lower", "specialization"),
            ),
            SplitCandidate(
                SplitType.PUSH_PULL_LEGS_UPPER_LOWER,
                ("push", "pull", "legs", "upper", "lower"),
            ),
            SplitCandidate(
                SplitType.BODY_PART_ROTATION,
                ("chest_triceps", "back_biceps", "shoulders_traps", "legs", "specialization"),
            ),
        ),
        6: (
            SplitCandidate(
                SplitType.PUSH_PULL_LEGS_X2,
                ("push", "pull", "legs", "push", "pull", "legs"),
            ),
            SplitCandidate(
                SplitType.UPPER_LOWER_X3,
                ("upper", "lower", "upper", "lower", "upper", "lower"),
            ),
            SplitCandidate(
                SplitType.BODY_PART_ROTATION,
                (
                    "chest_triceps",
                    "back_biceps",
                    "quadriceps_calves",
                    "shoulders_traps",
                    "posterior_chain_core",
                    "specialization",
                ),
            ),
        ),
    }
    if days not in structures:
        raise ValueError("split candidates require one through six resistance days")
    return structures[days]


def score_split_candidates(
    request: NormalizedProgramRequest,
    candidates: tuple[SplitCandidate, ...],
    ruleset: ProgramRuleset,
    preferred_days: int | None = None,
    *,
    exercises: tuple[ExerciseCandidate, ...] = (),
    session_capacity: SessionCapacity | None = None,
) -> tuple[SplitPlan, ...]:
    weights = ruleset.split_weights
    capacity = (
        session_capacity
        if exercises and session_capacity is not None
        else build_session_capacity(
            request,
            exercises,
            ruleset,
        )
        if exercises
        else None
    )
    scored: list[tuple[SplitPlan, int, tuple[int, int, int, int]]] = []
    recovery_limited = _recovery_is_limited(request)
    priority_policy = PriorityAllocationPolicy.for_request(request, ruleset)
    goal_specific = request.primary_goal in {
        Goal.HYPERTROPHY,
        Goal.MUSCLE_GAIN,
        Goal.STRENGTH,
    }
    for candidate in candidates:
        complexity = ruleset.split_complexity[candidate.split_type]
        score = weights["base"] - complexity
        reasons: list[str] = []
        professional_topology = professional_topology_preference(
            request,
            candidate.split_type,
            ruleset,
        )
        score += professional_topology.score
        reasons.extend(professional_topology.reason_codes)
        if preferred_days is not None:
            score -= (
                abs(len(candidate.day_focuses) - preferred_days)
                * ruleset.session_count_distance_penalty
            )
        full_body = candidate.split_type in {
            SplitType.FULL_BODY,
            SplitType.FULL_BODY_AB,
            SplitType.FULL_BODY_ABC,
            SplitType.FULL_BODY_FOUR,
        }
        if request.training_status is TrainingStatus.NOVICE and full_body:
            score += weights["simplicity"]
            reasons.append("SPLIT_SIMPLIFIED_FOR_NOVICE")
        if full_body and len(candidate.day_focuses) <= 3:
            reasons.append("SPLIT_FULL_BODY_FOR_LOW_FREQUENCY")
        if candidate.split_type in {
            SplitType.UPPER_LOWER,
            SplitType.UPPER_LOWER_SPECIALIZATION,
            SplitType.PUSH_PULL_LEGS_UPPER_LOWER,
            SplitType.PUSH_PULL_LEGS_X2,
            SplitType.UPPER_LOWER_X3,
            SplitType.PHUL,
        }:
            score += weights["twice_weekly_frequency"]
            reasons.append("SPLIT_SELECTED_FOR_TWICE_WEEKLY_EXPOSURE")
        if goal_specific and candidate.split_type in {
            SplitType.UPPER_LOWER_FULL,
            SplitType.UPPER_LOWER,
            SplitType.UPPER_LOWER_SPECIALIZATION,
            SplitType.PUSH_PULL_LEGS_UPPER_LOWER,
            SplitType.PUSH_PULL_LEGS_X2,
            SplitType.PHUL,
        }:
            score += weights["goal_specificity"]
            reasons.append("SPLIT_SELECTED_FOR_GOAL_SPECIFICITY")
        if (
            priority_policy.explicit_priorities
            and candidate.split_type is SplitType.UPPER_LOWER_SPECIALIZATION
            and (
                len(candidate.day_focuses) == 5
                or (
                    len(candidate.day_focuses) == 4
                    and any(
                        muscle in MUSCLE_SPECIFIC_UPPER_PRIORITIES
                        for muscle in priority_policy.explicit_priorities
                    )
                )
            )
        ):
            score += weights["priority_specialization"]
            reasons.append("SPLIT_SELECTED_FOR_PRIORITY_MUSCLE")
        if (
            request.source.session_duration_minutes <= ruleset.short_session_minutes
            and candidate.split_type is SplitType.FULL_BODY_FOUR
        ):
            score += weights["short_session_full_body"]
            reasons.append("SPLIT_SELECTED_FOR_SHORT_SESSIONS")
        if recovery_limited:
            score -= complexity * weights["recovery_complexity_penalty"]
        if (
            request.training_status is not TrainingStatus.ADVANCED
            and candidate.split_type is SplitType.UPPER_LOWER_X3
        ):
            score += weights["simplicity"]
        if (
            request.training_status is TrainingStatus.ADVANCED
            and candidate.split_type is SplitType.PUSH_PULL_LEGS_X2
            and not recovery_limited
        ):
            score += weights["goal_specificity"]
            reasons.append("SPLIT_SELECTED_FOR_ADVANCED_STATUS")
        if (
            candidate.split_type is SplitType.PHUL
            and request.primary_goal
            in {
                Goal.HYPERTROPHY,
                Goal.MUSCLE_GAIN,
                Goal.STRENGTH,
            }
            and request.training_status is TrainingStatus.ADVANCED
        ):
            score += ruleset.phul_bonus
            reasons.append("SPLIT_SELECTED_FOR_PERIODIZED_UPPER_LOWER")
        if (
            not is_professional_topology_scope(request)
            and candidate.split_type is SplitType.BODY_PART_ROTATION
            and (
                len(candidate.day_focuses) < 6
                or (request.training_status is TrainingStatus.ADVANCED and not recovery_limited)
            )
        ):
            score += ruleset.body_part_rotation_bonus
            reasons.append("SPLIT_SELECTED_FOR_SPECIALIZED_DIRECT_TARGETS")
        if (
            priority_policy.explicit_priorities
            and candidate.split_type is SplitType.BODY_PART_ROTATION
            and len(candidate.day_focuses) == 6
        ):
            score += weights["priority_specialization"]
            reasons.append("SPLIT_SELECTED_FOR_PRIORITY_MUSCLE")

        priority_adjustment, priority_reasons = priority_policy.split_adjustment(
            candidate.day_focuses, ruleset
        )
        score += priority_adjustment
        reasons.extend(priority_reasons)

        weekdays = _select_weekdays(
            len(candidate.day_focuses),
            request.source.preferred_weekdays,
            candidate.day_focuses,
            ruleset,
        )
        if len(request.source.preferred_weekdays) >= len(
            candidate.day_focuses
        ) and weekdays != tuple(
            sorted(request.source.preferred_weekdays[: len(candidate.day_focuses)])
        ):
            reasons.append("SPLIT_PREFERRED_DAYS_ADJUSTED_FOR_RECOVERY")
        duration_key = (0, 0, 0, 0)
        if capacity is not None:
            assessments = tuple(
                _focus_duration_assessment(
                    request,
                    _capacity_focus(focus, request, ruleset),
                    exercises,
                    ruleset,
                    capacity,
                )
                for focus in candidate.day_focuses
            )
            infeasible_days = sum(
                item.status is CapacityFeasibility.PROVABLY_INFEASIBLE for item in assessments
            )
            tight_days = sum(
                item.status is CapacityFeasibility.FEASIBLE_BUT_TIGHT for item in assessments
            )
            optional_trim = sum(item.optional_work_likely_trimmed for item in assessments)
            required_minutes = sum(item.required_work_cost_minutes for item in assessments)
            duration_key = (infeasible_days, tight_days, optional_trim, required_minutes)
            status = "INFEASIBLE" if infeasible_days else "TIGHT" if tight_days else "COMFORTABLE"
            reasons.append(f"SPLIT_DURATION_CAPACITY_{status}")
        scored.append(
            (
                SplitPlan(
                    split_type=candidate.split_type,
                    day_focuses=candidate.day_focuses,
                    weekdays=weekdays,
                    score=score,
                    reason_codes=tuple(dict.fromkeys(reasons)),
                ),
                complexity,
                duration_key,
            )
        )
    scored.sort(
        key=lambda item: (
            item[2][0],
            -item[0].score,
            *item[2][1:],
            item[1],
            item[0].split_type.value,
        )
    )
    return tuple(item[0] for item in scored)


def _capacity_focus(
    focus: str,
    request: NormalizedProgramRequest,
    ruleset: ProgramRuleset,
) -> str:
    if focus != "specialization":
        return focus
    policy = PriorityAllocationPolicy.for_request(request, ruleset)
    priorities = frozenset(policy.explicit_priorities or policy.priorities)
    return specialization_focus_for_priorities(priorities)


def _focus_duration_assessment(
    request: NormalizedProgramRequest,
    focus: str,
    exercises: tuple[ExerciseCandidate, ...],
    ruleset: ProgramRuleset,
    session_capacity: SessionCapacity,
) -> SessionCapacityAssessment:
    required: list[PlannedWorkCost] = []
    optional: list[PlannedWorkCost] = []
    used_ids: set[object] = set()
    first_compound_pending = True
    for slot in slots_for_focus(focus):
        compatible = tuple(
            item
            for item in exercises
            if item.id not in used_ids
            and not is_supplemental_muscle(item.primary_muscle)
            and evaluate_candidate_slot_compatibility(
                item,
                allowed_patterns=slot.patterns,
                target_muscles=(
                    frozenset({slot.target_muscle}) if slot.target_muscle is not None else None
                ),
                day_focus=focus,
                allow_full_body=focus.startswith("full_body"),
            ).compatible
        )
        candidate = min(
            compatible,
            key=lambda item: (
                estimate_candidate_cost(request, item, ruleset).minutes,
                str(item.id),
            ),
            default=None,
        )
        if candidate is None:
            if slot.required:
                required.append(
                    PlannedWorkCost(
                        minutes=session_capacity.maximum_resistance_work_minutes + 1,
                        working_sets=0,
                        exercise_count=0,
                    )
                )
            continue
        first_compound = first_compound_pending and candidate.exercise_type is ExerciseType.COMPOUND
        cost = estimate_candidate_cost(
            request,
            candidate,
            ruleset,
            is_first_compound=first_compound,
        )
        if first_compound:
            first_compound_pending = False
        used_ids.add(candidate.id)
        planned = (
            PlannedWorkCost(minutes=cost.minutes, working_sets=cost.working_sets)
            if is_main_training_exercise(candidate)
            else PlannedWorkCost(minutes=0, working_sets=0, exercise_count=0)
        )
        (required if slot.required else optional).append(planned)
    return assess_session_capacity(
        session_capacity,
        required_work=tuple(required),
        optional_work=tuple(optional),
    )


def _recovery_is_limited(request: NormalizedProgramRequest) -> bool:
    return recovery_burden_for_request(request).level != "normal"


def _select_weekdays(
    days: int,
    preferred: tuple[int, ...],
    focuses: tuple[str, ...],
    ruleset: ProgramRuleset,
) -> tuple[int, ...]:
    if len(preferred) >= days:
        selected = tuple(sorted(preferred[:days]))
        if _spacing_is_acceptable(selected, focuses, ruleset):
            return selected
    return ruleset.default_weekdays[days]


def _spacing_is_acceptable(
    weekdays: tuple[int, ...],
    focuses: tuple[str, ...],
    ruleset: ProgramRuleset,
) -> bool:
    if len(weekdays) <= 1:
        return True
    ordered = sorted(zip(weekdays, focuses, strict=True))
    circular = ordered + [(ordered[0][0] + ruleset.days_per_week, ordered[0][1])]
    for current, following in zip(circular, circular[1:], strict=False):
        gap = following[0] - current[0]
        recovery_sensitive = (
            current[1].startswith("full_body")
            or following[1].startswith("full_body")
            or current[1] == following[1]
        )
        if recovery_sensitive and gap < ruleset.minimum_recovery_gap_days:
            return False
    return True
