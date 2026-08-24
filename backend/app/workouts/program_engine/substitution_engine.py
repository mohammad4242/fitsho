"""Authoritative hard-safe ranking for concrete exercise substitutions."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID

from app.exercises.enums import MovementPattern, MuscleGroup
from app.workouts.program_engine.eligibility import filter_eligible_exercises
from app.workouts.program_engine.enums import (
    BodyPosition,
    CompatibilityLevel,
    Goal,
    ImpactLimit,
    Laterality,
    LoadLimit,
    SkillDemand,
    StabilityDemand,
)
from app.workouts.program_engine.equipment import effective_required_equipment
from app.workouts.program_engine.exercise_semantics import ExerciseRoleSignature
from app.workouts.program_engine.rulesets.resistance_training_v1 import ProgramRuleset
from app.workouts.program_engine.schemas import ExerciseCandidate, NormalizedProgramRequest
from app.workouts.program_engine.slot_compatibility import (
    evaluate_candidate_slot_compatibility,
)
from app.workouts.program_engine.strength_programming import (
    StrengthExerciseRole,
    classify_strength_role,
)
from app.workouts.program_engine.substitution_policy import (
    SubstitutionCause,
    SubstitutionPolicyContext,
    allowed_movement_patterns,
    evaluate_substitution_policy,
)


class SubstitutionTier(StrEnum):
    A = "A"
    B = "B"
    C = "C"
    D = "D"


@dataclass(frozen=True, slots=True)
class SubstitutionContext:
    cause: SubstitutionCause
    allowed_patterns: frozenset[MovementPattern] | None = None
    target_muscles: frozenset[MuscleGroup] | None = None
    day_focus: str | None = None
    allow_full_body: bool = False
    strength_role: StrengthExerciseRole | None = None


@dataclass(frozen=True, slots=True)
class SubstitutionOption:
    exercise: ExerciseCandidate
    tier: SubstitutionTier
    reason_codes: tuple[str, ...]
    compatibility_level: CompatibilityLevel


@dataclass(frozen=True, slots=True)
class SubstitutionDecision:
    target_exercise_id: UUID
    cause: SubstitutionCause
    options: tuple[SubstitutionOption, ...]
    reason_codes: tuple[str, ...]

    @property
    def exercise_ids(self) -> tuple[UUID, ...]:
        return tuple(option.exercise.id for option in self.options)

    @property
    def observability_metrics(self) -> dict[str, int]:
        from app.workouts.program_engine.substitution_observability import (
            substitution_observability,
        )

        return substitution_observability(self)

    def decision_trace_entry(self) -> dict[str, object]:
        from app.workouts.program_engine.substitution_observability import (
            substitution_trace_entry,
        )

        return substitution_trace_entry(self)


@dataclass(frozen=True, slots=True)
class _RankableOption:
    option: SubstitutionOption
    candidate_strength_role: StrengthExerciseRole | None


_TIER_RANK = {
    SubstitutionTier.A: 0,
    SubstitutionTier.B: 1,
    SubstitutionTier.C: 2,
    SubstitutionTier.D: 3,
}
_IMPACT_RANK = {ImpactLimit.LOW: 0, ImpactLimit.MODERATE: 1, ImpactLimit.HIGH: 2}
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
_SKILL_RANK = {SkillDemand.LOW: 0, SkillDemand.MODERATE: 1, SkillDemand.HIGH: 2}


def rank_substitutions(
    request: NormalizedProgramRequest,
    target: ExerciseCandidate,
    candidates: tuple[ExerciseCandidate, ...] | list[ExerciseCandidate],
    context: SubstitutionContext,
    *,
    ruleset: ProgramRuleset | None = None,
    limit: int = 3,
) -> SubstitutionDecision:
    """Return deterministic hard-safe substitution options and explanations."""
    if limit <= 0:
        return _no_replacement(target, context)

    target_role = ExerciseRoleSignature.from_candidate(target)
    target_muscles = context.target_muscles or (
        frozenset({target.primary_muscle}) if target.primary_muscle is not None else frozenset()
    )
    target_strength_role = context.strength_role or _strength_role(target, request, ruleset)
    policy_patterns = allowed_movement_patterns(
        target.movement_pattern,
        target_muscles,
        goal=request.primary_goal,
        strength_role=target_strength_role,
        cause=context.cause,
    )
    slot_patterns = policy_patterns.intersection(
        context.allowed_patterns or frozenset({target.movement_pattern})
    )
    policy_context = SubstitutionPolicyContext(
        goal=request.primary_goal,
        cause=context.cause,
        target_muscles=target_muscles,
        day_focus=context.day_focus,
        strength_role=target_strength_role,
    )

    eligible = filter_eligible_exercises(request, tuple(candidates)).eligible
    rankable: list[_RankableOption] = []
    for candidate in eligible:
        if candidate.id == target.id:
            continue
        policy = evaluate_substitution_policy(
            target_role,
            ExerciseRoleSignature.from_candidate(candidate),
            policy_context,
        )
        if not policy.compatible:
            continue
        slot = evaluate_candidate_slot_compatibility(
            candidate,
            allowed_patterns=slot_patterns,
            target_muscles=target_muscles or None,
            day_focus=context.day_focus,
            allow_full_body=context.allow_full_body,
        )
        if not slot.compatible:
            continue
        tier = _semantic_tier(target, candidate, policy.level)
        if tier is None:
            continue
        candidate_strength_role = _strength_role(candidate, request, ruleset)
        rankable.append(
            _RankableOption(
                option=SubstitutionOption(
                    exercise=candidate,
                    tier=tier,
                    reason_codes=_reason_codes(
                        target,
                        candidate,
                        tier=tier,
                        cause=context.cause,
                        target_strength_role=target_strength_role,
                        candidate_strength_role=candidate_strength_role,
                    ),
                    compatibility_level=policy.level,
                ),
                candidate_strength_role=candidate_strength_role,
            )
        )

    ranked = sorted(
        rankable,
        key=lambda item: _sort_key(
            request,
            target,
            item,
            context=context,
            target_strength_role=target_strength_role,
        ),
    )
    options = tuple(item.option for item in ranked[:limit])
    options = tuple(
        option
        for option in options
        if not substitution_option_invariant_errors(
            request,
            target,
            option.exercise,
            context,
            ruleset=ruleset,
        )
    )
    if not options:
        return _no_replacement(target, context)
    return SubstitutionDecision(
        target_exercise_id=target.id,
        cause=context.cause,
        options=options,
        reason_codes=(),
    )


def _semantic_tier(
    target: ExerciseCandidate,
    candidate: ExerciseCandidate,
    policy_level: CompatibilityLevel,
) -> SubstitutionTier | None:
    same_pattern = candidate.movement_pattern is target.movement_pattern
    same_primary = candidate.primary_muscle is target.primary_muscle
    same_focus = candidate.muscle_focus is target.muscle_focus
    same_type = candidate.exercise_type is target.exercise_type
    exact_role = same_pattern and same_primary and same_focus and same_type
    curated_or_group = candidate.id in target.curated_alternative_ids or (
        target.substitution_group is not None
        and candidate.substitution_group == target.substitution_group
    )
    if exact_role and curated_or_group:
        return SubstitutionTier.A
    if exact_role:
        return SubstitutionTier.B
    if same_pattern and same_primary and same_type:
        return SubstitutionTier.C
    if (
        candidate.movement_pattern is not target.movement_pattern
        and policy_level is CompatibilityLevel.VALID_BUT_SUBOPTIMAL
    ):
        return SubstitutionTier.D
    return None


def _sort_key(
    request: NormalizedProgramRequest,
    target: ExerciseCandidate,
    item: _RankableOption,
    *,
    context: SubstitutionContext,
    target_strength_role: StrengthExerciseRole | None,
) -> tuple[object, ...]:
    candidate = item.option.exercise
    target_secondary = set(target.secondary_muscles)
    secondary_overlap = len(target_secondary.intersection(candidate.secondary_muscles))
    same_group = (
        target.substitution_group is not None
        and candidate.substitution_group == target.substitution_group
    )
    same_strength_role = (
        target_strength_role is not None and item.candidate_strength_role is target_strength_role
    )
    rom_distance = len(
        target.range_of_motion_profile.symmetric_difference(candidate.range_of_motion_profile)
    )
    return (
        _TIER_RANK[item.option.tier],
        candidate.id not in target.curated_alternative_ids,
        not same_group,
        candidate.muscle_focus is not target.muscle_focus,
        candidate.primary_muscle is not target.primary_muscle,
        candidate.exercise_type is not target.exercise_type,
        not same_strength_role,
        -secondary_overlap,
        *_cause_sort_key(target, candidate, context.cause),
        candidate.body_position is not target.body_position,
        candidate.laterality is not target.laterality,
        rom_distance,
        abs(_STABILITY_RANK[target.stability_demand] - _STABILITY_RANK[candidate.stability_demand]),
        abs(_SKILL_RANK[target.skill_demand] - _SKILL_RANK[candidate.skill_demand]),
        _IMPACT_RANK[candidate.impact_level],
        _LOAD_RANK[candidate.axial_loading_level],
        abs(target.fatigue_cost - candidate.fatigue_cost),
        abs(target.setup_cost - candidate.setup_cost),
        candidate.id not in request.source.preferred_exercises,
        candidate.id in request.source.disliked_exercises,
        str(candidate.id),
    )


def _cause_sort_key(
    target: ExerciseCandidate,
    candidate: ExerciseCandidate,
    cause: SubstitutionCause,
) -> tuple[int, ...]:
    if cause is SubstitutionCause.MISSING_EQUIPMENT:
        target_equipment = effective_required_equipment(target.equipment, target.movement_pattern)
        candidate_equipment = effective_required_equipment(
            candidate.equipment, candidate.movement_pattern
        )
        return (
            len(target_equipment.symmetric_difference(candidate_equipment)),
            len(candidate_equipment),
        )
    if cause is SubstitutionCause.AXIAL_LOAD:
        return (
            _LOAD_RANK[candidate.axial_loading_level],
            candidate.body_position is not BodyPosition.SUPPORTED,
        )
    if cause is SubstitutionCause.BALANCE:
        return (
            _STABILITY_RANK[candidate.stability_demand],
            candidate.body_position is not BodyPosition.SUPPORTED,
            candidate.laterality is not Laterality.BILATERAL,
        )
    return (0,)


def _reason_codes(
    target: ExerciseCandidate,
    candidate: ExerciseCandidate,
    *,
    tier: SubstitutionTier,
    cause: SubstitutionCause,
    target_strength_role: StrengthExerciseRole | None,
    candidate_strength_role: StrengthExerciseRole | None,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if candidate.id in target.curated_alternative_ids:
        reasons.append("SUBSTITUTION_CURATED_ALTERNATIVE")
    if (
        target.substitution_group is not None
        and candidate.substitution_group == target.substitution_group
    ):
        reasons.append("SUBSTITUTION_SAME_GROUP")
    if tier in {SubstitutionTier.A, SubstitutionTier.B}:
        reasons.append("SUBSTITUTION_EXACT_ROLE")
    if candidate.muscle_focus is target.muscle_focus:
        reasons.append("SUBSTITUTION_MUSCLE_FOCUS_PRESERVED")
    if target_strength_role is not None and candidate_strength_role is target_strength_role:
        reasons.append("SUBSTITUTION_STRENGTH_ROLE_PRESERVED")
    if tier is SubstitutionTier.C:
        reasons.append("SUBSTITUTION_ROLE_PRESERVED_FOCUS_DEGRADED")
    if cause is SubstitutionCause.MISSING_EQUIPMENT and candidate.equipment != target.equipment:
        reasons.append("SUBSTITUTION_EQUIPMENT_ADAPTED")
    if cause in {
        SubstitutionCause.AXIAL_LOAD,
        SubstitutionCause.BALANCE,
        SubstitutionCause.OVERHEAD,
        SubstitutionCause.RANGE_OF_MOTION,
        SubstitutionCause.SAFETY,
    }:
        reasons.append("SUBSTITUTION_CONSTRAINT_ADAPTED")
    if tier is SubstitutionTier.D:
        reasons.append("SUBSTITUTION_MOVEMENT_FAMILY_FALLBACK")
    if tier in {SubstitutionTier.C, SubstitutionTier.D}:
        reasons.append("SUBSTITUTION_ROLE_DEGRADED")
    return tuple(dict.fromkeys(reasons))


def _strength_role(
    exercise: ExerciseCandidate,
    request: NormalizedProgramRequest,
    ruleset: ProgramRuleset | None,
) -> StrengthExerciseRole | None:
    if request.primary_goal is not Goal.STRENGTH or ruleset is None:
        return None
    return classify_strength_role(exercise, request, ruleset).role


def _no_replacement(
    target: ExerciseCandidate,
    context: SubstitutionContext,
) -> SubstitutionDecision:
    return SubstitutionDecision(
        target_exercise_id=target.id,
        cause=context.cause,
        options=(),
        reason_codes=("SUBSTITUTION_NO_VALID_REPLACEMENT",),
    )


def substitution_option_invariant_errors(
    request: NormalizedProgramRequest,
    target: ExerciseCandidate,
    candidate: ExerciseCandidate,
    context: SubstitutionContext,
    *,
    ruleset: ProgramRuleset | None = None,
) -> tuple[str, ...]:
    """Validate every hard invariant required before surfacing an alternative."""
    errors: list[str] = []
    if not candidate.is_active:
        errors.append("SUBSTITUTION_ALTERNATIVE_INACTIVE")
    if not candidate.is_programmable:
        errors.append("SUBSTITUTION_ALTERNATIVE_NOT_PROGRAMMABLE")
    if candidate.needs_review:
        errors.append("SUBSTITUTION_ALTERNATIVE_NEEDS_REVIEW")
    if not effective_required_equipment(candidate.equipment, candidate.movement_pattern).issubset(
        request.constraints.available_equipment
    ):
        errors.append("SUBSTITUTION_ALTERNATIVE_EQUIPMENT_INVALID")
    if candidate not in filter_eligible_exercises(request, (candidate,)).eligible:
        errors.append("SUBSTITUTION_ALTERNATIVE_CONSTRAINT_INVALID")
    target_muscles = context.target_muscles or (
        frozenset({target.primary_muscle}) if target.primary_muscle is not None else frozenset()
    )
    target_strength_role = context.strength_role or _strength_role(target, request, ruleset)
    allowed_patterns = allowed_movement_patterns(
        target.movement_pattern,
        target_muscles,
        goal=request.primary_goal,
        strength_role=target_strength_role,
        cause=context.cause,
    )
    slot_patterns = allowed_patterns.intersection(
        context.allowed_patterns or frozenset({target.movement_pattern})
    )
    policy = evaluate_substitution_policy(
        ExerciseRoleSignature.from_candidate(target),
        ExerciseRoleSignature.from_candidate(candidate),
        SubstitutionPolicyContext(
            goal=request.primary_goal,
            cause=context.cause,
            target_muscles=target_muscles,
            day_focus=context.day_focus,
            strength_role=target_strength_role,
        ),
    )
    if not policy.compatible:
        errors.append("SUBSTITUTION_ALTERNATIVE_POLICY_INCOMPATIBLE")
    slot = evaluate_candidate_slot_compatibility(
        candidate,
        allowed_patterns=slot_patterns,
        target_muscles=target_muscles or None,
        day_focus=context.day_focus,
        allow_full_body=context.allow_full_body,
    )
    if not slot.compatible:
        errors.append("SUBSTITUTION_ALTERNATIVE_SLOT_INCOMPATIBLE")
    return tuple(errors)
