import warnings
from collections import Counter
from dataclasses import dataclass
from uuid import UUID

from app.exercises.enums import MovementPattern, MuscleGroup
from app.workouts.program_engine.body_analysis import body_analysis_priority_muscles
from app.workouts.program_engine.enums import CompatibilityLevel, Goal
from app.workouts.program_engine.exercise_ranker import rank_exercises
from app.workouts.program_engine.replacement_ranker import rank_replacement_exercises
from app.workouts.program_engine.rulesets.resistance_training_v1 import ProgramRuleset
from app.workouts.program_engine.schemas import (
    ExerciseCandidate,
    NormalizedProgramRequest,
    SessionDraft,
    SplitPlan,
    WeeklyVolumePlan,
)
from app.workouts.program_engine.slot_compatibility import (
    SlotCompatibility,
    evaluate_candidate_slot_compatibility,
    focus_scope,
)
from app.workouts.program_engine.strength_programming import classify_strength_role

PUSH_PATTERNS = frozenset({MovementPattern.HORIZONTAL_PUSH, MovementPattern.VERTICAL_PUSH})
PULL_PATTERNS = frozenset({MovementPattern.HORIZONTAL_PULL, MovementPattern.VERTICAL_PULL})
KNEE_PATTERNS = frozenset(
    {MovementPattern.SQUAT, MovementPattern.LUNGE, MovementPattern.KNEE_EXTENSION}
)
HINGE_PATTERNS = frozenset({MovementPattern.HIP_HINGE, MovementPattern.HIP_EXTENSION})
CORE_PATTERNS = frozenset(
    {
        MovementPattern.CORE_ANTI_EXTENSION,
        MovementPattern.CORE_ANTI_ROTATION,
        MovementPattern.CORE_ANTI_LATERAL_FLEXION,
    }
)
SHOULDER_PATTERNS = frozenset({MovementPattern.VERTICAL_PUSH, MovementPattern.SHOULDER_ABDUCTION})
ARM_PATTERNS = frozenset({MovementPattern.ELBOW_FLEXION, MovementPattern.ELBOW_EXTENSION})
LOWER_ACCESSORY_PATTERNS = frozenset({MovementPattern.KNEE_FLEXION, MovementPattern.CALF_RAISE})


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
) -> tuple[SessionDraft, ...]:
    effective_priorities = request.source.priority_muscles | body_analysis_priority_muscles(
        request, ruleset
    )
    usage: Counter[UUID] = Counter()
    sessions: list[SessionDraft] = []
    short_session = request.source.session_duration_minutes <= ruleset.short_session_minutes
    for index, planned_focus in enumerate(split.day_focuses):
        focus = _resolve_focus(planned_focus, request, volume, ruleset)
        capacity = max(
            ruleset.minimum_exercises_per_session,
            min(
                ruleset.max_exercises_per_session,
                (request.source.session_duration_minutes - ruleset.general_warmup_minutes)
                // ruleset.minutes_per_exercise_slot,
            ),
        )
        slots = slots_for_focus(focus)
        ordered_slots = tuple(slot for slot in slots if slot.required) + tuple(
            slot for slot in slots if not slot.required
        )
        chosen: list[ExerciseCandidate] = []
        selected_slots: dict[UUID, SlotSpec] = {}
        reasons: dict[UUID, tuple[str, ...]] = {}
        session_reasons: tuple[str, ...] = ()
        this_session_relaxed_groups: list[tuple[MovementPattern, ...]] = []
        this_session_relaxed_targets: list[MuscleGroup | None] = []
        for slot in ordered_slots:
            if len(chosen) >= capacity:
                if slot.required:
                    raise SessionConstructionError(index + 1, focus, slot)
                break
            chosen_ids = {selected.id for selected in chosen}
            options: list[ExerciseCandidate] = []
            rejected_slot_reasons: list[str] = []
            comp_levels = {}
            for item in exercises:
                if item.id in chosen_ids:
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
                            ruleset.minimum_exercises_per_session - 2,
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
            needed_muscle = slot.target_muscle
            if needed_muscle is None and slot.patterns == HINGE_PATTERNS:
                needed_muscle = MuscleGroup.HAMSTRINGS
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
                    _role_repeated(item.exercise, chosen),
                    usage[item.exercise.id],
                    -item.score,
                    len(item.exercise.secondary_muscles) if short_session else 0,
                    str(item.exercise.id),
                ),
            )
            chosen.append(selected.exercise)
            selected_slots[selected.exercise.id] = slot
            selection_reasons = list(selected.reason_codes)
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

        while len(chosen) < min(capacity, ruleset.minimum_exercises_per_session):
            options, comp_levels = _compatible_supplements(focus, exercises, chosen)
            if not options:
                session_reasons = session_reasons + (
                    "SESSION_MINIMUM_UNSATISFIED_AFTER_SUPPLEMENTS",
                )
                break
            selected = min(
                rank_exercises(request, options, ruleset, compatibility_levels=comp_levels),
                key=lambda item: (
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

        if request.primary_goal is Goal.STRENGTH:
            chosen.sort(
                key=lambda item: (
                    ruleset.strength_role_order[
                        classify_strength_role(item, request, ruleset).role.value
                    ],
                    item.primary_muscle not in effective_priorities,
                    _order_rank(item.movement_pattern, ruleset),
                )
            )
        else:
            chosen.sort(
                key=lambda item: (
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
        substitutions = {
            item.id: tuple(
                alternative.id
                for alternative in rank_replacement_exercises(
                    request,
                    item,
                    exercises,
                    limit=ruleset.substitution_limit,
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
                )
            )
            for item in chosen
        }
        if capacity < len(slots):
            session_reasons = session_reasons + ("SESSION_TRIMMED_FOR_TIME_LIMIT",)
        sessions.append(
            SessionDraft(
                day_index=index + 1,
                weekday=split.weekdays[index],
                focus=focus,
                exercises=chosen,
                selection_reasons=reasons,
                substitutions=substitutions,
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
    compatible_ids = {item.id for item in chosen}
    compatible_ids.update(
        item.id
        for item in exercises
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
) -> tuple[list[ExerciseCandidate], dict[UUID, CompatibilityLevel]]:
    chosen_ids = {item.id for item in chosen}
    options = []
    levels: dict[UUID, CompatibilityLevel] = {}
    for item in exercises:
        if item.id not in chosen_ids:
            comp = evaluate_exercise_focus_compatibility(item, focus)
            if comp.compatible:
                options.append(item)
                levels[item.id] = comp.level
    return options, levels


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
    return any(
        item.primary_muscle is exercise.primary_muscle
        and item.movement_pattern is exercise.movement_pattern
        for item in chosen
    )


def _supplement_scope(
    focus: str,
) -> tuple[frozenset[MovementPattern], frozenset[MuscleGroup] | None]:
    return focus_scope(focus)


def slots_for_focus(focus: str) -> tuple[SlotSpec, ...]:
    if focus == "full_body_b":
        return (
            SlotSpec(HINGE_PATTERNS, True),
            SlotSpec(CORE_PATTERNS, True),
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
            SlotSpec(CORE_PATTERNS, True),
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
            SlotSpec(CORE_PATTERNS, True),
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
            SlotSpec(frozenset({MovementPattern.VERTICAL_PUSH}), False, MuscleGroup.SHOULDERS),
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
    priorities = request.source.priority_muscles | body_analysis_priority_muscles(request, ruleset)
    for muscle_group, specialized_focus in (
        ((MuscleGroup.CHEST, MuscleGroup.TRICEPS), "chest_triceps"),
        ((MuscleGroup.BACK, MuscleGroup.BICEPS), "back_biceps"),
        ((MuscleGroup.SHOULDERS, MuscleGroup.TRAPS), "shoulders_traps"),
        ((MuscleGroup.QUADRICEPS, MuscleGroup.CALVES), "quadriceps_calves"),
        ((MuscleGroup.HAMSTRINGS, MuscleGroup.GLUTES, MuscleGroup.ABS), "posterior_chain_core"),
    ):
        if priorities.intersection(muscle_group):
            return specialized_focus
    highest_target = max(volume.targets, key=lambda target: target.target_sets).muscle
    if highest_target in {MuscleGroup.BACK}:
        return "back_biceps"
    if highest_target in {MuscleGroup.SHOULDERS}:
        return "shoulders_traps"
    if highest_target in {MuscleGroup.QUADRICEPS, MuscleGroup.CALVES}:
        return "quadriceps_calves"
    if highest_target in {MuscleGroup.HAMSTRINGS, MuscleGroup.GLUTES, MuscleGroup.ABS}:
        return "posterior_chain_core"
    return "chest_triceps"


def _order_rank(pattern: MovementPattern, ruleset: ProgramRuleset) -> int:
    if pattern in PUSH_PATTERNS | PULL_PATTERNS | KNEE_PATTERNS | HINGE_PATTERNS:
        return ruleset.exercise_order_rank["primary_compound"]
    if pattern in CORE_PATTERNS:
        return ruleset.exercise_order_rank["trunk"]
    return ruleset.exercise_order_rank["accessory"]
