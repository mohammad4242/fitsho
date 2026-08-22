"""Deterministic ranking for safe exercise replacements."""

from collections.abc import Iterable
from uuid import UUID

from app.exercises.enums import MovementPattern, MuscleGroup
from app.workouts.program_engine.eligibility import filter_eligible_exercises
from app.workouts.program_engine.enums import (
    CompatibilityLevel,
    ImpactLimit,
    LoadLimit,
    SkillDemand,
    StabilityDemand,
)
from app.workouts.program_engine.schemas import (
    ExerciseCandidate,
    NormalizedProgramRequest,
)
from app.workouts.program_engine.slot_compatibility import (
    SlotCompatibility,
    evaluate_candidate_slot_compatibility,
)

_IMPACT_RANK = {
    ImpactLimit.LOW: 0,
    ImpactLimit.MODERATE: 1,
    ImpactLimit.HIGH: 2,
}
_LOAD_RANK = {
    LoadLimit.NONE: 0,
    LoadLimit.LOW: 1,
    LoadLimit.MODERATE: 2,
    LoadLimit.HIGH: 3,
}
_STABILITY_RANK = {
    StabilityDemand.LOW: 0,
    StabilityDemand.MODERATE: 1,
    StabilityDemand.HIGH: 2,
}
_SKILL_RANK = {
    SkillDemand.LOW: 0,
    SkillDemand.MODERATE: 1,
    SkillDemand.HIGH: 2,
}


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
    """Return safe replacements ordered by semantic fit and deterministic tie-breaks.

    Eligibility is intentionally applied before ranking, so blocked, unavailable, or
    otherwise unsafe candidates cannot be surfaced by a strong semantic match.
    """

    if limit <= 0:
        return ()

    eligible = filter_eligible_exercises(request, tuple(candidates)).eligible
    disliked = request.source.disliked_exercises
    semantic_scope = allowed_patterns or frozenset({target.movement_pattern})
    semantic_targets = target_muscles or (
        frozenset({target.primary_muscle}) if target.primary_muscle is not None else None
    )
    compatible = tuple(
        (candidate, compatibility)
        for candidate in eligible
        if candidate.id != target.id
        and (
            compatibility := _replacement_compatibility(
                target,
                candidate,
                allowed_patterns=semantic_scope,
                target_muscles=semantic_targets,
                day_focus=day_focus,
            )
        ).compatible
    )
    ranked = sorted(
        compatible,
        key=lambda item: _replacement_sort_key(
            target,
            item[0],
            compatibility=item[1],
            disliked=disliked,
        ),
    )
    return tuple(candidate for candidate, _compatibility in ranked[:limit])


def _replacement_compatibility(
    target: ExerciseCandidate,
    candidate: ExerciseCandidate,
    *,
    allowed_patterns: frozenset[MovementPattern],
    target_muscles: frozenset[MuscleGroup] | None,
    day_focus: str | None,
) -> SlotCompatibility:
    compatibility = evaluate_candidate_slot_compatibility(
        candidate,
        allowed_patterns=allowed_patterns,
        target_muscles=target_muscles,
        day_focus=day_focus,
        allow_full_body=bool(day_focus and day_focus.startswith("full_body")),
    )
    if not compatibility.compatible:
        return compatibility
    if (
        compatibility.level is CompatibilityLevel.PREFERRED
        and candidate.movement_pattern is target.movement_pattern
        and candidate.primary_muscle is target.primary_muscle
        and candidate.exercise_type is target.exercise_type
    ):
        return compatibility
    return SlotCompatibility(
        CompatibilityLevel.VALID_BUT_SUBOPTIMAL,
        tuple(dict.fromkeys((*compatibility.reason_codes, "REPLACEMENT_ROLE_SUBOPTIMAL"))),
    )


def _replacement_sort_key(
    target: ExerciseCandidate,
    candidate: ExerciseCandidate,
    *,
    compatibility: SlotCompatibility,
    disliked: frozenset[UUID],
) -> tuple[object, ...]:
    target_secondary = set(target.secondary_muscles)
    candidate_secondary = set(candidate.secondary_muscles)
    same_group = (
        target.substitution_group is not None
        and candidate.substitution_group == target.substitution_group
    )
    same_primary = (
        target.primary_muscle is not None and candidate.primary_muscle is target.primary_muscle
    )
    same_laterality = candidate.laterality is target.laterality
    same_pattern = candidate.movement_pattern is target.movement_pattern
    secondary_overlap = len(target_secondary.intersection(candidate_secondary))
    risk_score = (
        _IMPACT_RANK[candidate.impact_level]
        + _LOAD_RANK[candidate.axial_loading_level]
        + _STABILITY_RANK[candidate.stability_demand]
        + _SKILL_RANK[candidate.skill_demand]
    )
    return (
        compatibility.level is not CompatibilityLevel.PREFERRED,
        candidate.id in disliked,
        not same_group,
        not same_primary,
        -secondary_overlap,
        risk_score,
        not same_pattern,
        not same_laterality,
        candidate.fatigue_cost,
        candidate.setup_cost,
        str(candidate.id),
    )
