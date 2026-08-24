"""Backward-compatible forwarding wrapper for the unified substitution engine."""

from collections.abc import Iterable

from app.exercises.enums import MovementPattern, MuscleGroup
from app.workouts.program_engine.schemas import ExerciseCandidate, NormalizedProgramRequest
from app.workouts.program_engine.substitution_engine import (
    SubstitutionContext,
    rank_substitutions,
)
from app.workouts.program_engine.substitution_policy import SubstitutionCause


def rank_replacement_exercises(
    request: NormalizedProgramRequest,
    target: ExerciseCandidate,
    candidates: Iterable[ExerciseCandidate],
    *,
    limit: int = 3,
    allowed_patterns: frozenset[MovementPattern] | None = None,
    target_muscles: frozenset[MuscleGroup] | None = None,
    day_focus: str | None = None,
) -> tuple[ExerciseCandidate, ...]:
    """Forward legacy callers to the only concrete substitution ranker."""
    decision = rank_substitutions(
        request,
        target,
        list(candidates),
        SubstitutionContext(
            cause=SubstitutionCause.DISPLAY_ALTERNATIVE,
            allowed_patterns=allowed_patterns,
            target_muscles=target_muscles,
            day_focus=day_focus,
            allow_full_body=bool(day_focus and day_focus.startswith("full_body")),
        ),
        limit=limit,
    )
    return tuple(option.exercise for option in decision.options)
