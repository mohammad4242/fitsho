"""Canonical semantic policy for exercise substitution.

This module decides which role degradation is allowed. It never filters user
constraints, chooses a concrete exercise, or ranks candidates.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum

from app.exercises.enums import ExerciseType, MovementPattern, MuscleGroup
from app.workouts.program_engine.enums import CompatibilityLevel, Goal
from app.workouts.program_engine.exercise_semantics import ExerciseRoleSignature
from app.workouts.program_engine.strength_programming import StrengthExerciseRole

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

_POSTERIOR_CHAIN_PATTERNS = HINGE_PATTERNS | frozenset({MovementPattern.KNEE_FLEXION})
_QUADRICEPS_FALLBACK_PATTERNS = frozenset({MovementPattern.SQUAT, MovementPattern.LUNGE})


class SubstitutionCause(StrEnum):
    MISSING_EQUIPMENT = "missing_equipment"
    AXIAL_LOAD = "axial_load"
    BALANCE = "balance"
    OVERHEAD = "overhead"
    RANGE_OF_MOTION = "range_of_motion"
    SAFETY = "safety"
    USER_PREFERENCE = "user_preference"
    TEMPLATE_RECOVERY = "template_recovery"
    VOLUME_REPAIR = "volume_repair"
    DISPLAY_ALTERNATIVE = "display_alternative"


@dataclass(frozen=True, slots=True)
class SubstitutionPolicyContext:
    goal: Goal
    cause: SubstitutionCause
    target_muscles: frozenset[MuscleGroup]
    day_focus: str | None = None
    strength_role: StrengthExerciseRole | None = None


@dataclass(frozen=True, slots=True)
class SubstitutionPolicyDecision:
    level: CompatibilityLevel
    reason_codes: tuple[str, ...]

    @property
    def compatible(self) -> bool:
        return self.level is not CompatibilityLevel.HARD_INCOMPATIBLE


def allowed_movement_patterns(
    target_pattern: MovementPattern,
    target_muscles: Iterable[MuscleGroup],
    *,
    goal: Goal = Goal.GENERAL_FITNESS,
    strength_role: StrengthExerciseRole | None = None,
    cause: SubstitutionCause = SubstitutionCause.DISPLAY_ALTERNATIVE,
) -> frozenset[MovementPattern]:
    """Return exact intent plus explicitly allowed family fallbacks."""
    del cause
    exact = frozenset({target_pattern})
    if target_pattern is MovementPattern.OTHER:
        return frozenset()
    if goal is Goal.STRENGTH and strength_role is StrengthExerciseRole.PRIMARY_STRENGTH:
        return exact

    targets = frozenset(target_muscles)
    if target_pattern in PULL_PATTERNS and MuscleGroup.BACK in targets:
        return PULL_PATTERNS
    if target_pattern in _QUADRICEPS_FALLBACK_PATTERNS and MuscleGroup.QUADRICEPS in targets:
        return _QUADRICEPS_FALLBACK_PATTERNS
    if target_pattern in _POSTERIOR_CHAIN_PATTERNS and targets.intersection(
        {MuscleGroup.HAMSTRINGS, MuscleGroup.GLUTES}
    ):
        return _POSTERIOR_CHAIN_PATTERNS
    if target_pattern in CORE_PATTERNS and MuscleGroup.ABS in targets:
        return CORE_PATTERNS
    return exact


def evaluate_substitution_policy(
    target: ExerciseRoleSignature,
    candidate: ExerciseRoleSignature,
    context: SubstitutionPolicyContext,
) -> SubstitutionPolicyDecision:
    """Evaluate semantic role preservation without concrete candidate selection."""
    if (
        target.movement_pattern is MovementPattern.OTHER
        or candidate.movement_pattern is MovementPattern.OTHER
    ):
        return _hard("SUBSTITUTION_SEMANTIC_METADATA_INCOMPLETE")

    allowed_patterns = allowed_movement_patterns(
        target.movement_pattern,
        context.target_muscles or _primary_target(target),
        goal=context.goal,
        strength_role=context.strength_role,
        cause=context.cause,
    )
    if candidate.movement_pattern not in allowed_patterns:
        return _hard("SUBSTITUTION_MOVEMENT_PATTERN_INCOMPATIBLE")
    if candidate.exercise_type is not target.exercise_type:
        return _hard("SUBSTITUTION_EXERCISE_TYPE_INCOMPATIBLE")

    effective_targets = context.target_muscles or _primary_target(target)
    same_primary = candidate.primary_muscle is target.primary_muscle
    compatible_primary = candidate.primary_muscle in effective_targets or (
        candidate.exercise_type is ExerciseType.COMPOUND
        and bool(set(candidate.secondary_muscles).intersection(effective_targets))
    )
    if not same_primary and not compatible_primary:
        return _hard("SUBSTITUTION_PRIMARY_MUSCLE_INCOMPATIBLE")

    reasons: list[str] = []
    if candidate.movement_pattern is not target.movement_pattern:
        reasons.append("SUBSTITUTION_MOVEMENT_FAMILY_FALLBACK")
    if not same_primary:
        reasons.append("SUBSTITUTION_PRIMARY_MUSCLE_DEGRADED")
    if candidate.muscle_focus is not target.muscle_focus:
        reasons.append("SUBSTITUTION_MUSCLE_FOCUS_CHANGED")
    if reasons:
        return SubstitutionPolicyDecision(
            CompatibilityLevel.VALID_BUT_SUBOPTIMAL,
            tuple(reasons),
        )
    return SubstitutionPolicyDecision(
        CompatibilityLevel.PREFERRED,
        ("SUBSTITUTION_EXACT_ROLE",),
    )


def _primary_target(role: ExerciseRoleSignature) -> frozenset[MuscleGroup]:
    return frozenset({role.primary_muscle}) if role.primary_muscle is not None else frozenset()


def _hard(reason_code: str) -> SubstitutionPolicyDecision:
    return SubstitutionPolicyDecision(CompatibilityLevel.HARD_INCOMPATIBLE, (reason_code,))
