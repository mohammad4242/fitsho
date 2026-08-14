from app.exercises.enums import (
    ExerciseType,
    MovementPattern,
    MuscleFocus,
    MuscleGroup,
)
from app.exercises.focus_classifier import (
    FocusClassification,
    classify_muscle_focus,
    refine_primary_muscle,
)


def classify(
    primary_muscle: MuscleGroup,
    *,
    target: str,
    name: str,
    movement: MovementPattern,
    exercise_type: ExerciseType = ExerciseType.COMPOUND,
) -> FocusClassification | None:
    return classify_muscle_focus(
        primary_muscle=primary_muscle,
        source_target=target,
        source_muscle_group=None,
        secondary_targets=(),
        name_en=name,
        movement_pattern=movement,
        exercise_type=exercise_type,
        instructions_en=(),
    )


def test_exact_source_target_wins_over_name_hint() -> None:
    assert classify(
        MuscleGroup.CHEST,
        target="upper pectorals",
        name="Flat-looking press",
        movement=MovementPattern.HORIZONTAL_PUSH,
    ) == FocusClassification(
        focus=MuscleFocus.UPPER_CHEST,
        basis="source_target:upper pectorals",
    )


def test_explicit_chest_angles_classify_by_mechanics() -> None:
    assert classify(
        MuscleGroup.CHEST,
        target="pectorals",
        name="Dumbbell Incline Bench Press",
        movement=MovementPattern.HORIZONTAL_PUSH,
    ).focus is MuscleFocus.UPPER_CHEST
    assert classify(
        MuscleGroup.CHEST,
        target="pectorals",
        name="Barbell Bench Press",
        movement=MovementPattern.HORIZONTAL_PUSH,
    ).focus is MuscleFocus.MID_CHEST
    assert classify(
        MuscleGroup.CHEST,
        target="pectorals",
        name="Decline Dumbbell Bench Press",
        movement=MovementPattern.HORIZONTAL_PUSH,
    ).focus is MuscleFocus.LOWER_CHEST


def test_shoulder_raise_and_press_mechanics_are_specific() -> None:
    cases = (
        ("Shoulder Press", MovementPattern.VERTICAL_PUSH, MuscleFocus.FRONT_DELT),
        ("Cable Lateral Raise", MovementPattern.SHOULDER_ABDUCTION, MuscleFocus.LATERAL_DELT),
        ("Rear Delt Fly", MovementPattern.HORIZONTAL_PULL, MuscleFocus.REAR_DELT),
    )
    for name, movement, expected in cases:
        result = classify(MuscleGroup.SHOULDERS, target="deltoids", name=name, movement=movement)
        assert result is not None
        assert result.focus is expected


def test_vertical_back_pull_classifies_as_lats() -> None:
    result = classify(
        MuscleGroup.BACK,
        target="back",
        name="Lat Pulldown",
        movement=MovementPattern.VERTICAL_PULL,
    )

    assert result is not None
    assert result.focus is MuscleFocus.LATS


def test_core_rotation_records_move_from_abs_to_obliques() -> None:
    cases = (
        ("Cable Standing Lift", MovementPattern.OTHER),
        ("Cable Twist (up-down)", MovementPattern.SPINAL_FLEXION),
        ("Dumbbell Side Bend", MovementPattern.OTHER),
        ("Landmine 180", MovementPattern.OTHER),
        ("Pallof Press", MovementPattern.CORE_ANTI_ROTATION),
        ("Side Plank", MovementPattern.CORE_ANTI_LATERAL_FLEXION),
        ("Spell Caster", MovementPattern.OTHER),
    )
    for name, movement in cases:
        assert refine_primary_muscle(MuscleGroup.ABS, name, movement) is MuscleGroup.OBLIQUES


def test_unresolved_mechanics_return_none_instead_of_general() -> None:
    assert classify(
        MuscleGroup.CHEST,
        target="pectorals",
        name="Unknown press",
        movement=MovementPattern.OTHER,
        exercise_type=ExerciseType.OTHER,
    ) is None


def test_reviewed_press_and_extension_variants_have_specific_focuses() -> None:
    cases = (
        (
            MuscleGroup.SHOULDERS,
            "Barbell Seated Behind-The-Neck Press",
            MovementPattern.OTHER,
            ExerciseType.OTHER,
            MuscleFocus.GENERAL_SHOULDERS,
        ),
        (
            MuscleGroup.SHOULDERS,
            "Dumbbell Arnold Press",
            MovementPattern.OTHER,
            ExerciseType.OTHER,
            MuscleFocus.FRONT_DELT,
        ),
        (
            MuscleGroup.SHOULDERS,
            "EZ Barbell Anti Gravity Press",
            MovementPattern.OTHER,
            ExerciseType.OTHER,
            MuscleFocus.FRONT_DELT,
        ),
        (
            MuscleGroup.TRICEPS,
            "Cable Standing One Arm Triceps Extension",
            MovementPattern.ELBOW_EXTENSION,
            ExerciseType.ISOLATION,
            MuscleFocus.TRICEPS_LONG_HEAD,
        ),
        (
            MuscleGroup.TRICEPS,
            "Dumbbell Close-Grip Press",
            MovementPattern.ELBOW_EXTENSION,
            ExerciseType.ISOLATION,
            MuscleFocus.GENERAL_TRICEPS,
        ),
        (
            MuscleGroup.TRICEPS,
            "Lever Triceps Extension",
            MovementPattern.ELBOW_EXTENSION,
            ExerciseType.ISOLATION,
            MuscleFocus.TRICEPS_LONG_HEAD,
        ),
        (
            MuscleGroup.CHEST,
            "Resistance Band High Fly",
            MovementPattern.OTHER,
            ExerciseType.ISOLATION,
            MuscleFocus.LOWER_CHEST,
        ),
    )
    for muscle, name, movement, exercise_type, expected in cases:
        result = classify(
            muscle,
            target=muscle.value,
            name=name,
            movement=movement,
            exercise_type=exercise_type,
        )
        assert result is not None
        assert result.focus is expected


def test_quadriceps_does_not_receive_a_focus_subcategory() -> None:
    assert classify(
        MuscleGroup.QUADRICEPS,
        target="quadriceps",
        name="Leg Extension",
        movement=MovementPattern.KNEE_EXTENSION,
        exercise_type=ExerciseType.ISOLATION,
    ) is None
