import pytest

from app.exercises.enums import ExerciseType, MovementPattern, MuscleFocus, MuscleGroup
from app.workouts.program_engine.enums import BodyPosition, CompatibilityLevel, Goal, Laterality
from app.workouts.program_engine.exercise_semantics import ExerciseRoleSignature
from app.workouts.program_engine.strength_programming import StrengthExerciseRole
from app.workouts.program_engine.substitution_policy import (
    SubstitutionCause,
    SubstitutionPolicyContext,
    allowed_movement_patterns,
    evaluate_substitution_policy,
)


def role(
    pattern: MovementPattern,
    muscle: MuscleGroup,
    *,
    focus: MuscleFocus | None = None,
    exercise_type: ExerciseType = ExerciseType.COMPOUND,
) -> ExerciseRoleSignature:
    return ExerciseRoleSignature(
        movement_pattern=pattern,
        primary_muscle=muscle,
        muscle_focus=focus,
        exercise_type=exercise_type,
        secondary_muscles=(),
        body_position=BodyPosition.STANDING,
        laterality=Laterality.BILATERAL,
        substitution_group=None,
    )


@pytest.mark.parametrize(
    ("pattern", "muscles", "expected"),
    [
        (
            MovementPattern.HORIZONTAL_PULL,
            frozenset({MuscleGroup.BACK}),
            frozenset({MovementPattern.HORIZONTAL_PULL, MovementPattern.VERTICAL_PULL}),
        ),
        (
            MovementPattern.VERTICAL_PULL,
            frozenset({MuscleGroup.BACK}),
            frozenset({MovementPattern.HORIZONTAL_PULL, MovementPattern.VERTICAL_PULL}),
        ),
        (
            MovementPattern.SQUAT,
            frozenset({MuscleGroup.QUADRICEPS}),
            frozenset({MovementPattern.SQUAT, MovementPattern.LUNGE}),
        ),
        (
            MovementPattern.LUNGE,
            frozenset({MuscleGroup.QUADRICEPS}),
            frozenset({MovementPattern.SQUAT, MovementPattern.LUNGE}),
        ),
        (
            MovementPattern.HIP_HINGE,
            frozenset({MuscleGroup.HAMSTRINGS, MuscleGroup.GLUTES}),
            frozenset(
                {
                    MovementPattern.HIP_HINGE,
                    MovementPattern.HIP_EXTENSION,
                    MovementPattern.KNEE_FLEXION,
                }
            ),
        ),
        (
            MovementPattern.HIP_EXTENSION,
            frozenset({MuscleGroup.GLUTES}),
            frozenset(
                {
                    MovementPattern.HIP_HINGE,
                    MovementPattern.HIP_EXTENSION,
                    MovementPattern.KNEE_FLEXION,
                }
            ),
        ),
        (
            MovementPattern.KNEE_FLEXION,
            frozenset({MuscleGroup.HAMSTRINGS}),
            frozenset(
                {
                    MovementPattern.HIP_HINGE,
                    MovementPattern.HIP_EXTENSION,
                    MovementPattern.KNEE_FLEXION,
                }
            ),
        ),
        (
            MovementPattern.CORE_ANTI_EXTENSION,
            frozenset({MuscleGroup.ABS}),
            frozenset(
                {
                    MovementPattern.CORE_ANTI_EXTENSION,
                    MovementPattern.CORE_ANTI_ROTATION,
                    MovementPattern.CORE_ANTI_LATERAL_FLEXION,
                }
            ),
        ),
        (
            MovementPattern.CORE_ANTI_ROTATION,
            frozenset({MuscleGroup.ABS}),
            frozenset(
                {
                    MovementPattern.CORE_ANTI_EXTENSION,
                    MovementPattern.CORE_ANTI_ROTATION,
                    MovementPattern.CORE_ANTI_LATERAL_FLEXION,
                }
            ),
        ),
        (
            MovementPattern.CORE_ANTI_LATERAL_FLEXION,
            frozenset({MuscleGroup.ABS}),
            frozenset(
                {
                    MovementPattern.CORE_ANTI_EXTENSION,
                    MovementPattern.CORE_ANTI_ROTATION,
                    MovementPattern.CORE_ANTI_LATERAL_FLEXION,
                }
            ),
        ),
    ],
)
def test_allowed_conservative_movement_families(
    pattern: MovementPattern,
    muscles: frozenset[MuscleGroup],
    expected: frozenset[MovementPattern],
) -> None:
    assert allowed_movement_patterns(pattern, muscles) == expected


def test_disallowed_broad_or_wrong_muscle_degradations_stay_exact() -> None:
    assert allowed_movement_patterns(
        MovementPattern.HORIZONTAL_PUSH,
        frozenset({MuscleGroup.CHEST}),
    ) == frozenset({MovementPattern.HORIZONTAL_PUSH})
    assert allowed_movement_patterns(
        MovementPattern.HORIZONTAL_PULL,
        frozenset({MuscleGroup.BICEPS}),
    ) == frozenset({MovementPattern.HORIZONTAL_PULL})
    assert allowed_movement_patterns(
        MovementPattern.HIP_HINGE,
        frozenset({MuscleGroup.LOWER_BACK}),
    ) == frozenset({MovementPattern.HIP_HINGE})


def test_primary_strength_role_disallows_movement_family_degradation() -> None:
    assert allowed_movement_patterns(
        MovementPattern.HORIZONTAL_PULL,
        frozenset({MuscleGroup.BACK}),
        goal=Goal.STRENGTH,
        strength_role=StrengthExerciseRole.PRIMARY_STRENGTH,
        cause=SubstitutionCause.MISSING_EQUIPMENT,
    ) == frozenset({MovementPattern.HORIZONTAL_PULL})


def test_exact_role_is_preferred_and_focus_change_is_suboptimal() -> None:
    target = role(
        MovementPattern.HORIZONTAL_PUSH,
        MuscleGroup.CHEST,
        focus=MuscleFocus.UPPER_CHEST,
    )
    context = SubstitutionPolicyContext(
        goal=Goal.MUSCLE_GAIN,
        cause=SubstitutionCause.DISPLAY_ALTERNATIVE,
        target_muscles=frozenset({MuscleGroup.CHEST}),
    )

    exact = evaluate_substitution_policy(target, target, context)
    changed_focus = evaluate_substitution_policy(
        target,
        role(
            MovementPattern.HORIZONTAL_PUSH,
            MuscleGroup.CHEST,
            focus=MuscleFocus.MID_CHEST,
        ),
        context,
    )

    assert exact.level is CompatibilityLevel.PREFERRED
    assert changed_focus.level is CompatibilityLevel.VALID_BUT_SUBOPTIMAL
    assert "SUBSTITUTION_MUSCLE_FOCUS_CHANGED" in changed_focus.reason_codes


def test_policy_approved_family_fallback_requires_semantic_muscle_and_type() -> None:
    target = role(MovementPattern.HORIZONTAL_PULL, MuscleGroup.BACK)
    context = SubstitutionPolicyContext(
        goal=Goal.GENERAL_FITNESS,
        cause=SubstitutionCause.TEMPLATE_RECOVERY,
        target_muscles=frozenset({MuscleGroup.BACK}),
        day_focus="pull",
    )

    allowed = evaluate_substitution_policy(
        target,
        role(MovementPattern.VERTICAL_PULL, MuscleGroup.BACK),
        context,
    )
    wrong_muscle = evaluate_substitution_policy(
        target,
        role(MovementPattern.VERTICAL_PULL, MuscleGroup.BICEPS),
        context,
    )
    wrong_type = evaluate_substitution_policy(
        target,
        role(
            MovementPattern.VERTICAL_PULL,
            MuscleGroup.BACK,
            exercise_type=ExerciseType.ISOLATION,
        ),
        context,
    )

    assert allowed.level is CompatibilityLevel.VALID_BUT_SUBOPTIMAL
    assert "SUBSTITUTION_MOVEMENT_FAMILY_FALLBACK" in allowed.reason_codes
    assert wrong_muscle.level is CompatibilityLevel.HARD_INCOMPATIBLE
    assert wrong_type.level is CompatibilityLevel.HARD_INCOMPATIBLE


def test_vertical_push_never_degrades_to_horizontal_push() -> None:
    decision = evaluate_substitution_policy(
        role(MovementPattern.VERTICAL_PUSH, MuscleGroup.SHOULDERS),
        role(MovementPattern.HORIZONTAL_PUSH, MuscleGroup.SHOULDERS),
        SubstitutionPolicyContext(
            goal=Goal.MUSCLE_GAIN,
            cause=SubstitutionCause.MISSING_EQUIPMENT,
            target_muscles=frozenset({MuscleGroup.SHOULDERS}),
        ),
    )

    assert decision.level is CompatibilityLevel.HARD_INCOMPATIBLE
    assert decision.reason_codes == ("SUBSTITUTION_MOVEMENT_PATTERN_INCOMPATIBLE",)
