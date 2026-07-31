from collections import Counter
from uuid import UUID

from app.exercises.enums import MovementPattern
from app.workouts.program_engine.exercise_ranker import rank_exercises
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


def build_sessions(
    request: NormalizedProgramRequest,
    split: SplitPlan,
    volume: WeeklyVolumePlan,
    exercises: tuple[ExerciseCandidate, ...],
    ruleset: ProgramRuleset,
) -> tuple[SessionDraft, ...]:
    del volume
    by_pattern = _by_pattern(exercises)
    usage: Counter[UUID] = Counter()
    sessions: list[SessionDraft] = []
    for index, focus in enumerate(split.day_focuses):
        capacity = max(
            3,
            min(
                ruleset.max_exercises_per_session,
                (request.source.session_duration_minutes - ruleset.general_warmup_minutes) // 7,
            ),
        )
        slots = _slots_for_focus(focus)
        chosen: list[ExerciseCandidate] = []
        reasons: dict[UUID, tuple[str, ...]] = {}
        for patterns, required in slots:
            if len(chosen) >= capacity:
                break
            options = [
                item
                for pattern in patterns
                for item in by_pattern.get(pattern, ())
                if item.id not in {selected.id for selected in chosen}
                and not _duplicates_substitution_group(item, chosen)
            ]
            if not options:
                if required:
                    missing = sorted(pattern.value for pattern in patterns)
                    raise ValueError(f"NO_SAFE_EXERCISE_FOR_PATTERN:{missing}")
                continue
            ranked = rank_exercises(request, options, ruleset)
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
                item.primary_muscle not in request.source.priority_muscles,
                _order_rank(item.movement_pattern),
            )
        )
        if chosen and chosen[0].primary_muscle in request.source.priority_muscles:
            reasons[chosen[0].id] = reasons[chosen[0].id] + ("PRIORITY_MUSCLE_PLACED_FIRST",)
        substitutions = {
            item.id: tuple(
                alternative.id
                for alternative in exercises
                if alternative.id != item.id
                and alternative.movement_pattern is item.movement_pattern
                and (
                    alternative.substitution_group == item.substitution_group
                    or item.substitution_group is None
                )
            )[:3]
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


def _slots_for_focus(
    focus: str,
) -> tuple[tuple[frozenset[MovementPattern], bool], ...]:
    if focus.startswith("full_body"):
        return (
            (PUSH_PATTERNS, True),
            (PULL_PATTERNS, True),
            (KNEE_PATTERNS, True),
            (HINGE_PATTERNS, False),
            (CORE_PATTERNS, False),
            (frozenset({MovementPattern.CALF_RAISE}), False),
        )
    if focus == "upper":
        return (
            (PUSH_PATTERNS, True),
            (PULL_PATTERNS, True),
            (frozenset({MovementPattern.VERTICAL_PUSH}), False),
            (frozenset({MovementPattern.VERTICAL_PULL}), False),
            (frozenset({MovementPattern.ELBOW_FLEXION}), False),
            (frozenset({MovementPattern.ELBOW_EXTENSION}), False),
        )
    if focus in {"lower", "legs"}:
        return (
            (KNEE_PATTERNS, True),
            (HINGE_PATTERNS, True),
            (frozenset({MovementPattern.KNEE_FLEXION}), False),
            (frozenset({MovementPattern.KNEE_EXTENSION}), False),
            (frozenset({MovementPattern.CALF_RAISE}), False),
            (CORE_PATTERNS, False),
        )
    if focus == "push":
        return (
            (PUSH_PATTERNS, True),
            (frozenset({MovementPattern.HORIZONTAL_PUSH}), False),
            (frozenset({MovementPattern.VERTICAL_PUSH}), False),
            (frozenset({MovementPattern.ELBOW_EXTENSION}), False),
        )
    if focus == "pull":
        return (
            (PULL_PATTERNS, True),
            (frozenset({MovementPattern.HORIZONTAL_PULL}), False),
            (frozenset({MovementPattern.VERTICAL_PULL}), False),
            (frozenset({MovementPattern.ELBOW_FLEXION}), False),
        )
    return (
        (PUSH_PATTERNS, True),
        (PULL_PATTERNS, True),
        (KNEE_PATTERNS, True),
        (HINGE_PATTERNS, False),
        (CORE_PATTERNS, False),
    )


def _duplicates_substitution_group(
    candidate: ExerciseCandidate,
    selected: list[ExerciseCandidate],
) -> bool:
    return bool(
        candidate.substitution_group
        and any(item.substitution_group == candidate.substitution_group for item in selected)
    )


def _order_rank(pattern: MovementPattern) -> int:
    if pattern in PUSH_PATTERNS | PULL_PATTERNS | KNEE_PATTERNS | HINGE_PATTERNS:
        return 0
    if pattern in CORE_PATTERNS:
        return 2
    return 1
