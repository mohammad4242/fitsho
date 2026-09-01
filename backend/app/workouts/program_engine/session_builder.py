import warnings
from collections import Counter
from dataclasses import dataclass
from uuid import UUID

from app.exercises.enums import MovementPattern, MuscleGroup
from app.workouts.program_engine.duration_capacity import SessionCapacity
from app.workouts.program_engine.enums import CompatibilityLevel, Goal
from app.workouts.program_engine.exercise_ranker import rank_exercises
from app.workouts.program_engine.exercise_semantics import (
    SEMANTIC_NEAR_DUPLICATE_REASON,
    has_near_equivalent,
    is_primary_working_compound,
)
from app.workouts.program_engine.priority_allocation import PriorityAllocationPolicy
from app.workouts.program_engine.rulesets.resistance_training_v1 import ProgramRuleset
from app.workouts.program_engine.schemas import (
    ExerciseCandidate,
    NormalizedProgramRequest,
    SessionDraft,
    SplitPlan,
    WeeklyVolumePlan,
)
from app.workouts.program_engine.session_coherence import (
    SessionCoherence,
    specialization_focus_for_priorities,
)
from app.workouts.program_engine.session_feasibility import session_count_policy
from app.workouts.program_engine.slot_compatibility import (
    SlotCompatibility,
    evaluate_candidate_slot_compatibility,
    focus_scope,
)
from app.workouts.program_engine.strength_programming import classify_strength_role
from app.workouts.program_engine.substitution_engine import (
    SubstitutionContext,
    rank_substitutions,
)
from app.workouts.program_engine.substitution_policy import (
    CORE_PATTERNS,
    HINGE_PATTERNS,
    KNEE_PATTERNS,
    PULL_PATTERNS,
    PUSH_PATTERNS,
    SHOULDER_PATTERNS,
    SubstitutionCause,
)
from app.workouts.program_engine.supplemental_policy import (
    is_core_or_supplemental_exercise,
    is_main_resistance_exercise,
    is_supplemental_muscle,
    main_exercise_count,
    supplemental_muscle_fits_focus,
    supplemental_reason_codes,
)


@dataclass(frozen=True)
class SlotSpec:
    patterns: frozenset[MovementPattern]
    required: bool
    target_muscle: MuscleGroup | None = None


class SessionConstructionError(ValueError):
    def __init__(
        self,
        day_index: int,
        focus: str,
        slot: SlotSpec,
        *,
        rejection_reasons: tuple[str, ...] = (),
    ) -> None:
        patterns = tuple(sorted(pattern.value for pattern in slot.patterns))
        target = slot.target_muscle.value if slot.target_muscle is not None else None
        self.day_index = day_index
        self.focus = focus
        self.patterns = patterns
        self.target_muscle = target
        self.rejection_reasons = rejection_reasons
        self.reason_codes = (
            "SESSION_CONSTRUCTION_FAILED_REQUIRED_SLOT",
            "REQUIRED_SLOT_HARD_IMPOSSIBILITY",
            f"REQUIRED_SESSION_SLOT_UNAVAILABLE:{focus}",
            f"REQUIRED_PATTERN_UNAVAILABLE:{','.join(patterns)}",
            *((f"REQUIRED_TARGET_MUSCLE_UNAVAILABLE:{target}",) if target is not None else ()),
            *rejection_reasons,
        )
        super().__init__(";".join(self.reason_codes))


def build_sessions(
    request: NormalizedProgramRequest,
    split: SplitPlan,
    volume: WeeklyVolumePlan,
    exercises: tuple[ExerciseCandidate, ...],
    ruleset: ProgramRuleset,
    *,
    rejected_slot_candidates: tuple[tuple[ExerciseCandidate, tuple[str, ...]], ...] = (),
    session_capacity: SessionCapacity | None = None,
) -> tuple[SessionDraft, ...]:
    priority_policy = PriorityAllocationPolicy.for_request(request, ruleset)
    effective_priorities = frozenset(priority_policy.priorities)
    usage: Counter[UUID] = Counter()
    sessions: list[SessionDraft] = []
    coverage_muscles = frozenset(
        target.muscle for target in volume.targets if target.minimum_coverage_required
    )
    covered_direct_muscles: set[MuscleGroup] = set()
    short_session = request.source.session_duration_minutes <= ruleset.short_session_minutes
    count_policy = session_count_policy(request.source.session_duration_minutes, ruleset)
    for index, planned_focus in enumerate(split.day_focuses):
        focus = _resolve_focus(planned_focus, request, volume, ruleset)
        coherence = SessionCoherence.from_dynamic_focus(focus)
        slots = slots_for_focus(focus)
        required_slot_count = sum(slot.required for slot in slots)
        day_capacity = session_capacity
        capacity = (
            max(
                required_slot_count,
                min(
                    ruleset.max_exercises_per_session,
                    day_capacity.expected_exercise_count_capacity,
                ),
            )
            if day_capacity is not None
            else max(
                ruleset.minimum_exercises_per_session,
                min(
                    ruleset.max_exercises_per_session,
                    request.source.session_duration_minutes // ruleset.minutes_per_exercise_slot,
                ),
            )
        )
        capacity = min(count_policy.maximum_main_exercises, max(1, capacity))

        # Phase 11.9: duration alone NEVER reduces capacity below 5 for 45+ min sessions.
        if not short_session:
            capacity = max(capacity, count_policy.minimum_main_exercises)

        main_slots = tuple(slot for slot in slots if not _slot_is_supplemental(slot))
        ordered_slots = tuple(slot for slot in main_slots if slot.required) + tuple(
            slot for slot in main_slots if not slot.required
        )
        chosen: list[ExerciseCandidate] = []
        selected_slots: dict[UUID, SlotSpec] = {}
        reasons: dict[UUID, tuple[str, ...]] = {}
        session_reasons: tuple[str, ...] = ()
        if capacity < count_policy.minimum_main_exercises:
            # This can now only happen when short_session is True
            session_reasons = ("DURATION_PLANNED_REDUCED_EXERCISE_COUNT",)
        this_session_relaxed_groups: list[tuple[MovementPattern, ...]] = []
        this_session_relaxed_targets: list[MuscleGroup | None] = []
        main_capacity = min(capacity, ruleset.preferred_main_exercises_per_session)
        for slot in ordered_slots:
            if len(chosen) >= main_capacity:
                if slot.required:
                    raise SessionConstructionError(index + 1, focus, slot)
                break
            chosen_ids = {selected.id for selected in chosen}
            options: list[ExerciseCandidate] = []
            rejected_slot_reasons: list[str] = []
            semantic_redundancy_rejected = False
            comp_levels = {}
            for item in exercises:
                if item.id in chosen_ids:
                    continue
                if not is_main_resistance_exercise(item):
                    continue
                compatibility = evaluate_candidate_slot_compatibility(
                    item,
                    allowed_patterns=slot.patterns,
                    target_muscles=(
                        frozenset({slot.target_muscle}) if slot.target_muscle is not None else None
                    ),
                    day_focus=focus,
                    allow_full_body=focus.startswith("full_body"),
                )
                if compatibility.compatible:
                    if not is_core_or_supplemental_exercise(item) and not coherence.allows_direct(
                        item.primary_muscle
                    ):
                        rejected_slot_reasons.append(
                            f"DIRECT_MUSCLE_OUT_OF_SCOPE:{item.primary_muscle.value}"
                            if item.primary_muscle is not None
                            else "DIRECT_MUSCLE_OUT_OF_SCOPE"
                        )
                        continue
                    if has_near_equivalent(item, chosen):
                        semantic_redundancy_rejected = True
                        continue
                    options.append(item)
                    comp_levels[item.id] = compatibility.level
                else:
                    rejected_slot_reasons.extend(compatibility.reason_codes)
            if not options:
                if slot.required:
                    unique_rejections = tuple(dict.fromkeys(rejected_slot_reasons))
                    if _required_slot_is_relaxable(
                        slot,
                        focus,
                        exercises,
                        chosen,
                        minimum_exercises=max(
                            1,
                            count_policy.minimum_main_exercises - 2,
                        ),
                        rejected_slot_candidates=rejected_slot_candidates,
                    ):
                        relaxed = tuple(sorted(slot.patterns, key=lambda item: item.value))
                        this_session_relaxed_groups.append(relaxed)
                        this_session_relaxed_targets.append(slot.target_muscle)
                        session_reasons = session_reasons + (
                            *unique_rejections,
                            "SESSION_LAYOUT_UNFILLABLE",
                            "REQUIRED_SLOT_RELAXABLE_TRAINING_QUALITY",
                            "RECOVERY_APPLIED_REQUIRED_SLOT_RELAXATION",
                            *(
                                ("REQUIRED_SLOT_RELAXED_FOR_STRUCTURED_LIMITATION",)
                                if request.source.blocked_caution_tags
                                else ()
                            ),
                            *(
                                (f"RECOVERY_RELAXED_TARGET_MUSCLE:{slot.target_muscle.value}",)
                                if slot.target_muscle is not None
                                else ()
                            ),
                        )
                        continue
                    raise SessionConstructionError(
                        index + 1,
                        focus,
                        slot,
                        rejection_reasons=unique_rejections,
                    )
                else:
                    continue
            if semantic_redundancy_rejected:
                session_reasons = session_reasons + (SEMANTIC_NEAR_DUPLICATE_REASON,)
            needed_muscle = slot.target_muscle
            if needed_muscle is None:
                needed_muscle = next(
                    (
                        muscle
                        for muscle in priority_policy.explicit_priorities
                        if any(item.primary_muscle is muscle for item in options)
                    ),
                    (
                        MuscleGroup.HAMSTRINGS
                        if slot.patterns == HINGE_PATTERNS
                        else MuscleGroup.ABS
                        if slot.patterns == CORE_PATTERNS
                        else None
                    ),
                )
            ranked = rank_exercises(
                request,
                options,
                ruleset,
                needed_muscle=needed_muscle,
                compatibility_levels=comp_levels,
            )
            selected = min(
                ranked,
                key=lambda item: (
                    0
                    if (
                        item.exercise.primary_muscle in priority_policy.explicit_priorities
                        and item.exercise.primary_muscle not in covered_direct_muscles
                    )
                    else 1,
                    0
                    if (
                        focus.startswith("full_body")
                        and item.exercise.primary_muscle in coverage_muscles
                        and item.exercise.primary_muscle not in covered_direct_muscles
                    )
                    else 1,
                    coherence.role_rank(item.exercise.primary_muscle),
                    _role_repeated(item.exercise, chosen),
                    item.exercise.primary_muscle not in priority_policy.explicit_priorities,
                    usage[item.exercise.id],
                    -item.score,
                    len(item.exercise.secondary_muscles) if short_session else 0,
                    str(item.exercise.id),
                ),
            )
            chosen.append(selected.exercise)
            selected_slots[selected.exercise.id] = slot
            selection_reasons = list(selected.reason_codes)
            if slot.required and is_primary_working_compound(selected.exercise):
                selection_reasons.append("PRIMARY_WORKING_COMPOUND")
            if _role_repeated(selected.exercise, chosen[:-1]):
                redundancy_reason = (
                    "DELIBERATE_REDUNDANCY_FOR_REQUIRED_PATTERN"
                    if slot.required
                    else "DELIBERATE_REDUNDANCY_FOR_TARGET_VOLUME"
                )
                selection_reasons.append(redundancy_reason)
                session_reasons = session_reasons + (redundancy_reason,)
            if usage[selected.exercise.id]:
                selection_reasons.append("CORE_MOVEMENT_REPEATED_FOR_PROGRESSION")
            reasons[selected.exercise.id] = tuple(selection_reasons)
            usage[selected.exercise.id] += 1

        while main_exercise_count(chosen) < main_capacity:
            options, comp_levels = _compatible_supplements(
                focus,
                exercises,
                chosen,
                allow_role_redundancy=(
                    main_exercise_count(chosen) < count_policy.minimum_main_exercises
                ),
                role_limit=2 if main_capacity >= 7 else 1,
            )
            if not options:
                session_reasons = session_reasons + (
                    "SESSION_MINIMUM_UNSATISFIED_AFTER_SUPPLEMENTS",
                    "INSUFFICIENT_ELIGIBLE_EXERCISES",
                )
                break
            selected = min(
                rank_exercises(request, options, ruleset, compatibility_levels=comp_levels),
                key=lambda item: (
                    *coherence.placement_rank(
                        item.exercise.primary_muscle,
                        existing_exposure=any(
                            chosen_item.primary_muscle is item.exercise.primary_muscle
                            for chosen_item in chosen
                        ),
                        user_priority=(
                            item.exercise.primary_muscle in priority_policy.explicit_priorities
                        ),
                    ),
                    _role_repeated(item.exercise, chosen),
                    usage[item.exercise.id],
                    -item.score,
                    str(item.exercise.id),
                ),
            )
            chosen.append(selected.exercise)
            selection_reasons = [*selected.reason_codes, "COMPATIBLE_SESSION_SUPPLEMENT"]
            if _role_repeated(selected.exercise, chosen[:-1]):
                selection_reasons.append("DELIBERATE_REDUNDANCY_FOR_SESSION_COVERAGE")
                session_reasons = session_reasons + ("DELIBERATE_REDUNDANCY_FOR_SESSION_COVERAGE",)
            if usage[selected.exercise.id]:
                selection_reasons.append("CORE_MOVEMENT_REPEATED_FOR_PROGRESSION")
            reasons[selected.exercise.id] = tuple(selection_reasons)
            usage[selected.exercise.id] += 1
            session_reasons = session_reasons + ("SESSION_SUPPLEMENTED_TO_MINIMUM",)

        chosen_ids = {item.id for item in chosen}
        if any(
            item.id not in chosen_ids and has_near_equivalent(item, chosen) for item in exercises
        ):
            session_reasons = session_reasons + (SEMANTIC_NEAR_DUPLICATE_REASON,)

        supplemental_count = sum(is_core_or_supplemental_exercise(item) for item in chosen)
        while supplemental_count < 2 and main_exercise_count(chosen) >= min(
            main_capacity, count_policy.minimum_main_exercises
        ):
            supplemental_options = _supplemental_options(
                focus,
                exercises,
                chosen,
                priority_policy,
                usage,
            )
            if supplemental_options:
                selected_supplemental = min(
                    supplemental_options,
                    key=lambda item: (
                        0
                        if item.primary_muscle in priority_policy.supplemental_priorities
                        else 1
                        if item.primary_muscle in priority_policy.supplemental_body_priorities
                        else 2,
                        usage[item.id],
                        str(item.id),
                    ),
                )
                chosen.append(selected_supplemental)
                supplemental_muscle = selected_supplemental.primary_muscle
                assert supplemental_muscle is not None
                planned = supplemental_muscle in priority_policy.supplemental_priorities
                reasons[selected_supplemental.id] = supplemental_reason_codes(
                    supplemental_muscle,
                    planned=planned,
                ) + (
                    ("CORE_MOVEMENT_REPEATED_FOR_PROGRESSION",)
                    if usage[selected_supplemental.id]
                    else ()
                )
                usage[selected_supplemental.id] += 1
                supplemental_count += 1
                if not planned:
                    break
            else:
                break

        if request.primary_goal is Goal.STRENGTH:
            chosen.sort(
                key=lambda item: (
                    is_supplemental_muscle(item.primary_muscle),
                    ruleset.strength_role_order[
                        classify_strength_role(item, request, ruleset).role.value
                    ],
                    coherence.role_rank(item.primary_muscle),
                    item.primary_muscle not in effective_priorities,
                    _order_rank(item.movement_pattern, ruleset),
                )
            )
        else:
            chosen.sort(
                key=lambda item: (
                    is_supplemental_muscle(item.primary_muscle),
                    coherence.role_rank(item.primary_muscle),
                    item.primary_muscle not in effective_priorities,
                    _order_rank(item.movement_pattern, ruleset),
                )
            )
        if chosen and chosen[0].primary_muscle in effective_priorities:
            placement_reason = (
                "PRIORITY_MUSCLE_PLACED_FIRST"
                if chosen[0].primary_muscle in request.source.priority_muscles
                else "BODY_ANALYSIS_PRIORITY_PLACED_FIRST"
            )
            reasons[chosen[0].id] = reasons[chosen[0].id] + (placement_reason,)
        substitutions: dict[UUID, tuple[UUID, ...]] = {}
        substitution_decisions = []
        for item in chosen:
            if is_supplemental_muscle(item.primary_muscle):
                substitutions[item.id] = ()
                continue
            decision = rank_substitutions(
                request,
                item,
                list(exercises),
                SubstitutionContext(
                    cause=SubstitutionCause.DISPLAY_ALTERNATIVE,
                    allowed_patterns=(
                        selected_slots[item.id].patterns
                        if item.id in selected_slots
                        else focus_scope(focus)[0]
                    ),
                    target_muscles=frozenset(
                        {
                            (
                                selected_slots[item.id].target_muscle
                                if item.id in selected_slots
                                else None
                            )
                            or item.primary_muscle
                        }
                    )
                    if item.primary_muscle is not None
                    else None,
                    day_focus=focus,
                    allow_full_body=focus.startswith("full_body"),
                ),
                ruleset=ruleset,
                limit=ruleset.substitution_limit,
            )
            substitution_decisions.append(decision)
            substitutions[item.id] = decision.exercise_ids
        if capacity < len(slots):
            session_reasons = session_reasons + ("SESSION_TRIMMED_FOR_TIME_LIMIT",)
        covered_direct_muscles.update(
            item.primary_muscle
            for item in chosen
            if item.primary_muscle is not None and not is_core_or_supplemental_exercise(item)
        )
        sessions.append(
            SessionDraft(
                day_index=index + 1,
                weekday=split.weekdays[index],
                focus=focus,
                exercises=chosen,
                selection_reasons=reasons,
                substitutions=substitutions,
                substitution_decisions=tuple(substitution_decisions),
                reason_codes=tuple(dict.fromkeys(session_reasons)),
                relaxed_required_pattern_groups=tuple(dict.fromkeys(this_session_relaxed_groups)),
                relaxed_required_target_muscles=tuple(this_session_relaxed_targets),
            )
        )
    return tuple(sessions)


def _safe_session_completion_is_possible(
    focus: str,
    exercises: tuple[ExerciseCandidate, ...],
    chosen: list[ExerciseCandidate],
    *,
    minimum_exercises: int,
) -> bool:
    compatible_ids = {item.id for item in chosen if is_main_resistance_exercise(item)}
    compatible_ids.update(
        item.id
        for item in exercises
        if is_main_resistance_exercise(item)
        if evaluate_exercise_focus_compatibility(item, focus).compatible
    )
    return len(compatible_ids) >= minimum_exercises


_RELAXABLE_ELIGIBILITY_REJECTIONS = frozenset(
    {
        "EXERCISE_REJECTED_MISSING_EQUIPMENT",
        "EXERCISE_REJECTED_BLOCKED_EXERCISE",
        "EXERCISE_REJECTED_BLOCKED_PATTERN",
        "EXERCISE_REJECTED_BLOCKED_CAUTION_TAG",
        "EXERCISE_REJECTED_IMPACT_LIMIT",
        "EXERCISE_REJECTED_AXIAL_LOAD_LIMIT",
        "EXERCISE_REJECTED_OVERHEAD_LIMIT",
        "EXERCISE_REJECTED_BALANCE_DEMAND",
        "EXERCISE_REJECTED_SKILL_TOO_HIGH",
        "EXERCISE_REJECTED_RANGE_OF_MOTION",
    }
)


def _required_slot_is_relaxable(
    slot: SlotSpec,
    focus: str,
    exercises: tuple[ExerciseCandidate, ...],
    chosen: list[ExerciseCandidate],
    *,
    minimum_exercises: int,
    rejected_slot_candidates: tuple[tuple[ExerciseCandidate, tuple[str, ...]], ...],
) -> bool:
    if not _safe_session_completion_is_possible(
        focus,
        exercises,
        chosen,
        minimum_exercises=minimum_exercises,
    ):
        return False
    if slot.target_muscle is not None and any(
        item.movement_pattern in slot.patterns for item in exercises
    ):
        return True
    for item, reasons in rejected_slot_candidates:
        if not reasons or not all(
            reason in _RELAXABLE_ELIGIBILITY_REJECTIONS for reason in reasons
        ):
            continue
        compatibility = evaluate_candidate_slot_compatibility(
            item,
            allowed_patterns=slot.patterns,
            target_muscles=(
                frozenset({slot.target_muscle}) if slot.target_muscle is not None else None
            ),
            day_focus=focus,
            allow_full_body=focus.startswith("full_body"),
        )
        if compatibility.compatible:
            return True
    return False


def _compatible_supplements(
    focus: str,
    exercises: tuple[ExerciseCandidate, ...],
    chosen: list[ExerciseCandidate],
    *,
    allow_role_redundancy: bool,
    role_limit: int,
) -> tuple[list[ExerciseCandidate], dict[UUID, CompatibilityLevel]]:
    chosen_ids = {item.id for item in chosen}
    options = []
    levels: dict[UUID, CompatibilityLevel] = {}
    for item in exercises:
        if (
            item.id not in chosen_ids
            and is_main_resistance_exercise(item)
            and not has_near_equivalent(item, chosen)
            and (
                (allow_role_redundancy and focus.startswith("full_body"))
                or _role_occurrence_count(item, chosen) < min(role_limit, _session_role_limit(item))
                or (
                    item.movement_pattern is not MovementPattern.SHRUG
                    and not _has_complementary_option(focus, item, exercises, chosen)
                )
            )
        ):
            comp = evaluate_exercise_focus_compatibility(item, focus)
            if comp.compatible:
                options.append(item)
                levels[item.id] = comp.level
    return options, levels


def _has_complementary_option(
    focus: str,
    exercise: ExerciseCandidate,
    exercises: tuple[ExerciseCandidate, ...],
    chosen: list[ExerciseCandidate],
) -> bool:
    chosen_ids = {item.id for item in chosen}
    return any(
        item.id not in chosen_ids
        and is_main_resistance_exercise(item)
        and not has_near_equivalent(item, chosen)
        and (
            item.primary_muscle is not exercise.primary_muscle
            or item.movement_pattern is not exercise.movement_pattern
        )
        and evaluate_exercise_focus_compatibility(item, focus).compatible
        for item in exercises
    )


def evaluate_exercise_focus_compatibility(
    exercise: ExerciseCandidate, focus: str
) -> SlotCompatibility:
    patterns, muscles = _supplement_scope(focus)
    return evaluate_candidate_slot_compatibility(
        exercise,
        allowed_patterns=patterns,
        target_muscles=muscles,
        day_focus=focus,
        allow_full_body=focus.startswith("full_body"),
    )


def exercise_fits_focus(exercise: ExerciseCandidate, focus: str) -> bool:
    return evaluate_exercise_focus_compatibility(exercise, focus).compatible


def _role_repeated(
    exercise: ExerciseCandidate,
    chosen: list[ExerciseCandidate],
) -> bool:
    return has_near_equivalent(exercise, chosen) or any(
        item.primary_muscle is exercise.primary_muscle
        and item.movement_pattern is exercise.movement_pattern
        for item in chosen
    )


def _role_occurrence_count(
    exercise: ExerciseCandidate,
    chosen: list[ExerciseCandidate],
) -> int:
    return sum(
        item.primary_muscle is exercise.primary_muscle
        and item.movement_pattern is exercise.movement_pattern
        for item in chosen
    )


def _session_role_limit(exercise: ExerciseCandidate) -> int:
    return 1 if exercise.movement_pattern is MovementPattern.SHRUG else 2


def _supplement_scope(
    focus: str,
) -> tuple[frozenset[MovementPattern], frozenset[MuscleGroup] | None]:
    return focus_scope(focus)


def slots_for_focus(focus: str) -> tuple[SlotSpec, ...]:
    if focus == "full_body_b":
        return (
            SlotSpec(HINGE_PATTERNS, True),
            SlotSpec(CORE_PATTERNS, False),
            SlotSpec(PUSH_PATTERNS, True),
            SlotSpec(PULL_PATTERNS, False),
            SlotSpec(KNEE_PATTERNS, False),
            SlotSpec(frozenset({MovementPattern.CALF_RAISE}), False),
        )
    if focus == "full_body_c":
        return (
            SlotSpec(PULL_PATTERNS, True),
            SlotSpec(KNEE_PATTERNS, True),
            SlotSpec(HINGE_PATTERNS, True),
            SlotSpec(frozenset({MovementPattern.CALF_RAISE}), False),
            SlotSpec(PUSH_PATTERNS, False),
            SlotSpec(CORE_PATTERNS, False),
        )
    if focus == "full_body_d":
        return (
            SlotSpec(CORE_PATTERNS, False),
            SlotSpec(PUSH_PATTERNS, True),
            SlotSpec(PULL_PATTERNS, True),
            SlotSpec(KNEE_PATTERNS, False),
            SlotSpec(HINGE_PATTERNS, False),
            SlotSpec(frozenset({MovementPattern.CALF_RAISE}), False),
        )
    if focus.startswith("full_body"):
        return (
            SlotSpec(PUSH_PATTERNS, True),
            SlotSpec(PULL_PATTERNS, True),
            SlotSpec(KNEE_PATTERNS, True),
            SlotSpec(HINGE_PATTERNS, False),
            SlotSpec(frozenset({MovementPattern.CALF_RAISE}), False),
            SlotSpec(CORE_PATTERNS, False),
        )
    if focus.startswith("upper"):
        return (
            SlotSpec(PUSH_PATTERNS, True),
            SlotSpec(PULL_PATTERNS, True),
            SlotSpec(frozenset({MovementPattern.VERTICAL_PUSH}), False),
            SlotSpec(frozenset({MovementPattern.VERTICAL_PULL}), False),
            SlotSpec(frozenset({MovementPattern.ELBOW_FLEXION}), False),
            SlotSpec(frozenset({MovementPattern.ELBOW_EXTENSION}), False),
        )
    if focus == "quadriceps_calves":
        return (
            SlotSpec(KNEE_PATTERNS, True, MuscleGroup.QUADRICEPS),
            SlotSpec(frozenset({MovementPattern.SQUAT}), False, MuscleGroup.QUADRICEPS),
            SlotSpec(frozenset({MovementPattern.KNEE_EXTENSION}), False, MuscleGroup.QUADRICEPS),
            SlotSpec(frozenset({MovementPattern.CALF_RAISE}), False, MuscleGroup.CALVES),
            SlotSpec(frozenset({MovementPattern.CALF_RAISE}), False, MuscleGroup.CALVES),
        )
    if focus == "posterior_chain_core":
        return (
            SlotSpec(HINGE_PATTERNS, True, MuscleGroup.HAMSTRINGS),
            SlotSpec(frozenset({MovementPattern.HIP_EXTENSION}), False, MuscleGroup.GLUTES),
            SlotSpec(frozenset({MovementPattern.KNEE_FLEXION}), False, MuscleGroup.HAMSTRINGS),
            SlotSpec(CORE_PATTERNS, False, MuscleGroup.ABS),
            SlotSpec(CORE_PATTERNS, False, MuscleGroup.ABS),
        )
    if focus.startswith("lower") or focus == "legs":
        return (
            SlotSpec(KNEE_PATTERNS, True),
            SlotSpec(HINGE_PATTERNS, True),
            SlotSpec(CORE_PATTERNS, False),
            SlotSpec(frozenset({MovementPattern.CALF_RAISE}), False),
            SlotSpec(frozenset({MovementPattern.KNEE_FLEXION}), False),
            SlotSpec(frozenset({MovementPattern.KNEE_EXTENSION}), False),
        )
    if focus == "push":
        return (
            SlotSpec(PUSH_PATTERNS, True),
            SlotSpec(frozenset({MovementPattern.HORIZONTAL_PUSH}), False),
            SlotSpec(frozenset({MovementPattern.VERTICAL_PUSH}), False),
            SlotSpec(frozenset({MovementPattern.ELBOW_EXTENSION}), False),
            SlotSpec(frozenset({MovementPattern.ELBOW_EXTENSION}), False),
        )
    if focus == "pull":
        return (
            SlotSpec(PULL_PATTERNS, True),
            SlotSpec(frozenset({MovementPattern.HORIZONTAL_PULL}), False),
            SlotSpec(frozenset({MovementPattern.VERTICAL_PULL}), False),
            SlotSpec(frozenset({MovementPattern.ELBOW_FLEXION}), False),
            SlotSpec(frozenset({MovementPattern.ELBOW_FLEXION}), False),
        )
    if focus == "chest_triceps":
        return (
            SlotSpec(frozenset({MovementPattern.HORIZONTAL_PUSH}), True, MuscleGroup.CHEST),
            SlotSpec(frozenset({MovementPattern.HORIZONTAL_PUSH}), False, MuscleGroup.CHEST),
            SlotSpec(frozenset({MovementPattern.ELBOW_EXTENSION}), False, MuscleGroup.TRICEPS),
            SlotSpec(frozenset({MovementPattern.ELBOW_EXTENSION}), False, MuscleGroup.TRICEPS),
        )
    if focus == "back_biceps":
        return (
            SlotSpec(PULL_PATTERNS, True, MuscleGroup.BACK),
            SlotSpec(frozenset({MovementPattern.HORIZONTAL_PULL}), False, MuscleGroup.BACK),
            SlotSpec(frozenset({MovementPattern.VERTICAL_PULL}), False, MuscleGroup.BACK),
            SlotSpec(frozenset({MovementPattern.ELBOW_FLEXION}), False, MuscleGroup.BICEPS),
            SlotSpec(frozenset({MovementPattern.ELBOW_FLEXION}), False, MuscleGroup.BICEPS),
        )
    if focus == "biceps":
        return (
            SlotSpec(frozenset({MovementPattern.ELBOW_FLEXION}), True, MuscleGroup.BICEPS),
            SlotSpec(frozenset({MovementPattern.ELBOW_FLEXION}), False, MuscleGroup.BICEPS),
            SlotSpec(frozenset({MovementPattern.ELBOW_FLEXION}), False, MuscleGroup.BICEPS),
        )
    if focus == "triceps":
        return (
            SlotSpec(frozenset({MovementPattern.ELBOW_EXTENSION}), True, MuscleGroup.TRICEPS),
            SlotSpec(frozenset({MovementPattern.ELBOW_EXTENSION}), False, MuscleGroup.TRICEPS),
            SlotSpec(frozenset({MovementPattern.ELBOW_EXTENSION}), False, MuscleGroup.TRICEPS),
        )
    if focus == "shoulders_traps":
        return (
            SlotSpec(SHOULDER_PATTERNS, True, MuscleGroup.SHOULDERS),
            SlotSpec(frozenset({MovementPattern.SHOULDER_ABDUCTION}), False, MuscleGroup.SHOULDERS),
            SlotSpec(frozenset({MovementPattern.HORIZONTAL_PULL}), False, MuscleGroup.SHOULDERS),
            SlotSpec(frozenset({MovementPattern.SHRUG}), False, MuscleGroup.TRAPS),
            SlotSpec(
                frozenset({MovementPattern.SHOULDER_EXTERNAL_ROTATION}),
                False,
                MuscleGroup.SHOULDERS,
            ),
        )
    warnings.warn(
        f"Unrecognized session focus {focus!r}; falling back to full_body slot layout.",
        UserWarning,
        stacklevel=2,
    )
    return (
        SlotSpec(PUSH_PATTERNS, True),
        SlotSpec(PULL_PATTERNS, True),
        SlotSpec(KNEE_PATTERNS, True),
        SlotSpec(HINGE_PATTERNS, False),
        SlotSpec(CORE_PATTERNS, False),
    )


_slots_for_focus = slots_for_focus


def _resolve_focus(
    focus: str,
    request: NormalizedProgramRequest,
    volume: WeeklyVolumePlan,
    ruleset: ProgramRuleset,
) -> str:
    if focus != "specialization":
        return focus
    policy = PriorityAllocationPolicy.for_request(request, ruleset)
    priorities = frozenset(policy.explicit_priorities or policy.priorities)
    highest_target = max(volume.targets, key=lambda target: target.target_sets).muscle
    return specialization_focus_for_priorities(priorities, highest_target=highest_target)


def _order_rank(pattern: MovementPattern, ruleset: ProgramRuleset) -> int:
    if pattern in PUSH_PATTERNS | PULL_PATTERNS | KNEE_PATTERNS | HINGE_PATTERNS:
        return ruleset.exercise_order_rank["primary_compound"]
    if pattern in CORE_PATTERNS:
        return ruleset.exercise_order_rank["trunk"]
    return ruleset.exercise_order_rank["accessory"]


def _slot_is_supplemental(slot: SlotSpec) -> bool:
    return (
        is_supplemental_muscle(slot.target_muscle)
        or bool(slot.patterns)
        and slot.patterns.issubset(CORE_PATTERNS)
    )


def _supplemental_options(
    focus: str,
    exercises: tuple[ExerciseCandidate, ...],
    chosen: list[ExerciseCandidate],
    policy: PriorityAllocationPolicy,
    usage: Counter[UUID],
) -> tuple[ExerciseCandidate, ...]:
    chosen_ids = {item.id for item in chosen}
    if sum(is_supplemental_muscle(item.primary_muscle) for item in chosen) >= 2:
        return ()
    return tuple(
        item
        for item in exercises
        if item.id not in chosen_ids
        and item.primary_muscle is not None
        and is_supplemental_muscle(item.primary_muscle)
        and (not usage[item.id] or item.primary_muscle in policy.supplemental_priorities)
        and supplemental_muscle_fits_focus(item.primary_muscle, focus)
        and (
            item.primary_muscle is not MuscleGroup.NECK
            or item.primary_muscle in policy.supplemental_priorities
        )
    )
