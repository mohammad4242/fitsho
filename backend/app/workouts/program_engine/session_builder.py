from collections import Counter
from dataclasses import dataclass
from uuid import UUID

from app.exercises.enums import MovementPattern, MuscleGroup
from app.workouts.program_engine.body_analysis import body_analysis_priority_muscles
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


@dataclass(frozen=True)
class SlotSpec:
    patterns: frozenset[MovementPattern]
    required: bool
    target_muscle: MuscleGroup | None = None


def build_sessions(
    request: NormalizedProgramRequest,
    split: SplitPlan,
    volume: WeeklyVolumePlan,
    exercises: tuple[ExerciseCandidate, ...],
    ruleset: ProgramRuleset,
) -> tuple[SessionDraft, ...]:
    by_pattern = _by_pattern(exercises)
    effective_priorities = request.source.priority_muscles | body_analysis_priority_muscles(
        request, ruleset
    )
    usage: Counter[UUID] = Counter()
    sessions: list[SessionDraft] = []
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
        slots = _slots_for_focus(focus)
        chosen: list[ExerciseCandidate] = []
        reasons: dict[UUID, tuple[str, ...]] = {}
        for slot in slots:
            if len(chosen) >= capacity:
                break
            options = [
                item
                for pattern in slot.patterns
                for item in by_pattern.get(pattern, ())
                if item.id not in {selected.id for selected in chosen}
                and (slot.target_muscle is None or item.primary_muscle is slot.target_muscle)
            ]
            if not options:
                if slot.required:
                    missing = sorted(pattern.value for pattern in slot.patterns)
                    raise ValueError(f"NO_SAFE_EXERCISE_FOR_PATTERN:{missing}")
                continue
            ranked = rank_exercises(
                request,
                options,
                ruleset,
                needed_muscle=slot.target_muscle,
            )
            selected = min(
                ranked,
                key=lambda item: (
                    usage[item.exercise.id],
                    -item.score,
                    str(item.exercise.id),
                ),
            )
            chosen.append(selected.exercise)
            selection_reasons = list(selected.reason_codes)
            if usage[selected.exercise.id]:
                selection_reasons.append("CORE_MOVEMENT_REPEATED_FOR_PROGRESSION")
            reasons[selected.exercise.id] = tuple(selection_reasons)
            usage[selected.exercise.id] += 1

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
                )
            )
            for item in chosen
        }
        session_reasons = ("SESSION_TRIMMED_FOR_TIME_LIMIT",) if capacity < len(slots) else ()
        sessions.append(
            SessionDraft(
                day_index=index + 1,
                weekday=split.weekdays[index],
                focus=focus,
                exercises=chosen,
                selection_reasons=reasons,
                substitutions=substitutions,
                reason_codes=session_reasons,
            )
        )
    return tuple(sessions)


def _by_pattern(
    exercises: tuple[ExerciseCandidate, ...],
) -> dict[MovementPattern, tuple[ExerciseCandidate, ...]]:
    return {
        pattern: tuple(item for item in exercises if item.movement_pattern is pattern)
        for pattern in MovementPattern
    }


def _slots_for_focus(focus: str) -> tuple[SlotSpec, ...]:
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
            SlotSpec(PUSH_PATTERNS, False),
            SlotSpec(CORE_PATTERNS, False),
            SlotSpec(frozenset({MovementPattern.CALF_RAISE}), False),
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
            SlotSpec(CORE_PATTERNS, False),
            SlotSpec(frozenset({MovementPattern.CALF_RAISE}), False),
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
            SlotSpec(frozenset({MovementPattern.KNEE_FLEXION}), False),
            SlotSpec(frozenset({MovementPattern.KNEE_EXTENSION}), False),
            SlotSpec(frozenset({MovementPattern.CALF_RAISE}), False),
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
    if focus == "shoulders_traps":
        return (
            SlotSpec(SHOULDER_PATTERNS, True, MuscleGroup.SHOULDERS),
            SlotSpec(frozenset({MovementPattern.SHOULDER_ABDUCTION}), False, MuscleGroup.SHOULDERS),
            SlotSpec(frozenset({MovementPattern.HORIZONTAL_PULL}), False, MuscleGroup.SHOULDERS),
            SlotSpec(frozenset({MovementPattern.SHRUG}), False, MuscleGroup.TRAPS),
            SlotSpec(frozenset({MovementPattern.SHRUG}), False, MuscleGroup.TRAPS),
        )
    return (
        SlotSpec(PUSH_PATTERNS, True),
        SlotSpec(PULL_PATTERNS, True),
        SlotSpec(KNEE_PATTERNS, True),
        SlotSpec(HINGE_PATTERNS, False),
        SlotSpec(CORE_PATTERNS, False),
    )


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
