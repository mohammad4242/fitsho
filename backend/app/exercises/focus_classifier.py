from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from app.exercises.enums import (
    ExerciseType,
    MovementPattern,
    MuscleFocus,
    MuscleGroup,
)


@dataclass(frozen=True)
class FocusClassification:
    focus: MuscleFocus
    basis: str


CORE_OBLIQUE_NAMES = frozenset(
    {
        "cable standing lift",
        "cable twist up down",
        "dumbbell side bend",
        "landmine 180",
        "pallof press",
        "side plank",
        "spell caster",
    }
)

REVIEWED_MECHANICS: dict[tuple[MuscleGroup, str], MuscleFocus] = {
    (
        MuscleGroup.SHOULDERS,
        "barbell seated behind the neck press",
    ): MuscleFocus.GENERAL_SHOULDERS,
    (MuscleGroup.SHOULDERS, "dumbbell arnold press"): MuscleFocus.FRONT_DELT,
    (MuscleGroup.SHOULDERS, "ez barbell anti gravity press"): MuscleFocus.FRONT_DELT,
    (
        MuscleGroup.TRICEPS,
        "cable standing one arm triceps extension",
    ): MuscleFocus.TRICEPS_LONG_HEAD,
    (MuscleGroup.TRICEPS, "dumbbell close grip press"): MuscleFocus.GENERAL_TRICEPS,
    (MuscleGroup.TRICEPS, "lever triceps extension"): MuscleFocus.TRICEPS_LONG_HEAD,
    (MuscleGroup.CHEST, "resistance band high fly"): MuscleFocus.LOWER_CHEST,
}


def normalize_focus_text(value: str | None) -> str:
    if value is None:
        return ""
    normalized = "".join(character.lower() if character.isalnum() else " " for character in value)
    return " ".join(normalized.split())


def _contains(text: str, *phrases: str) -> bool:
    return any(phrase in text for phrase in phrases)


def refine_primary_muscle(
    primary_muscle: MuscleGroup | None,
    name_en: str,
    movement_pattern: MovementPattern,
) -> MuscleGroup | None:
    if primary_muscle is not MuscleGroup.ABS:
        return primary_muscle
    name = normalize_focus_text(name_en)
    if movement_pattern in {
        MovementPattern.CORE_ANTI_ROTATION,
        MovementPattern.CORE_ANTI_LATERAL_FLEXION,
    } or name in CORE_OBLIQUE_NAMES:
        return MuscleGroup.OBLIQUES
    return primary_muscle


def _classification(focus: MuscleFocus, basis: str) -> FocusClassification:
    return FocusClassification(focus=focus, basis=basis)


def classify_muscle_focus(
    *,
    primary_muscle: MuscleGroup | None,
    source_target: str | None,
    source_muscle_group: str | None,
    secondary_targets: Sequence[str],
    name_en: str,
    movement_pattern: MovementPattern,
    exercise_type: ExerciseType,
    instructions_en: Sequence[str],
) -> FocusClassification | None:
    if primary_muscle is None:
        return None

    target = normalize_focus_text(source_target)
    source_group = normalize_focus_text(source_muscle_group)
    name = normalize_focus_text(name_en)
    instructions = normalize_focus_text(" ".join(instructions_en))
    secondary = " ".join(normalize_focus_text(value) for value in secondary_targets)
    source_basis = f"source_target:{target}"
    reviewed = REVIEWED_MECHANICS.get((primary_muscle, name))
    if reviewed is not None:
        return _classification(reviewed, "reviewed_movement_mechanics")

    if primary_muscle is MuscleGroup.CHEST:
        if target == "upper pectorals" or "clavicular" in source_group:
            return _classification(MuscleFocus.UPPER_CHEST, source_basis)
        if "incline" in name and "push up" not in name:
            return _classification(MuscleFocus.UPPER_CHEST, "mechanics:incline")
        if _contains(name, "decline", "chest dip"):
            return _classification(MuscleFocus.LOWER_CHEST, "mechanics:decline_or_dip")
        if exercise_type is ExerciseType.MOBILITY:
            return _classification(MuscleFocus.GENERAL_CHEST, "mechanics:mobility")
        if movement_pattern is MovementPattern.HORIZONTAL_PUSH or _contains(
            name, "flat", "lying", "pec deck", "dumbbell fly", "cable standing fly"
        ):
            return _classification(MuscleFocus.MID_CHEST, "mechanics:horizontal_or_flat")
        return None

    if primary_muscle is MuscleGroup.BACK:
        if target == "rhomboids" or target == "middle back":
            return _classification(MuscleFocus.MID_BACK_RHOMBOIDS, source_basis)
        if target == "upper back":
            return _classification(MuscleFocus.UPPER_BACK, source_basis)
        if target == "lats":
            return _classification(MuscleFocus.LATS, source_basis)
        if "pullover" in name or movement_pattern is MovementPattern.VERTICAL_PULL:
            return _classification(MuscleFocus.LATS, "mechanics:vertical_pull_or_extension")
        if movement_pattern is MovementPattern.HORIZONTAL_PULL:
            return _classification(MuscleFocus.GENERAL_BACK, "mechanics:broad_row")
        return None

    if primary_muscle is MuscleGroup.SHOULDERS:
        if _contains(target, "anterior deltoid") or _contains(source_group, "deltoid anterior"):
            return _classification(MuscleFocus.FRONT_DELT, source_basis)
        if _contains(target, "posterior deltoid", "rear deltoid") or _contains(
            secondary, "posterior deltoid", "rear deltoid"
        ):
            return _classification(MuscleFocus.REAR_DELT, source_basis)
        if _contains(name, "rear", "reverse fly", "face pull"):
            return _classification(MuscleFocus.REAR_DELT, "mechanics:horizontal_abduction")
        if _contains(name, "front raise") or movement_pattern is MovementPattern.VERTICAL_PUSH:
            return _classification(MuscleFocus.FRONT_DELT, "mechanics:shoulder_flexion")
        if _contains(name, "lateral raise", "upright row", "iron cross"):
            return _classification(MuscleFocus.LATERAL_DELT, "mechanics:shoulder_abduction")
        if exercise_type is ExerciseType.MOBILITY or name == "battling ropes":
            return _classification(MuscleFocus.GENERAL_SHOULDERS, "mechanics:broad_shoulders")
        return None

    if primary_muscle is MuscleGroup.BICEPS:
        if _contains(name, "hammer", "neutral", "zottman", "reverse curl"):
            return _classification(
                MuscleFocus.BRACHIALIS_BRACHIORADIALIS,
                "mechanics:neutral_or_pronated_grip",
            )
        if movement_pattern is MovementPattern.ELBOW_FLEXION:
            return _classification(MuscleFocus.BICEPS_BRACHII, "mechanics:supinated_curl")
        return None

    if primary_muscle is MuscleGroup.TRICEPS:
        if _contains(name, "overhead", "lying", "incline", "skull", "kneeling triceps stretch"):
            return _classification(MuscleFocus.TRICEPS_LONG_HEAD, "mechanics:shoulder_flexed")
        if _contains(name, "pushdown", "kickback", "pronate", "reverse extensions"):
            return _classification(
                MuscleFocus.TRICEPS_LATERAL_MEDIAL_HEADS,
                "mechanics:arm_at_side",
            )
        if movement_pattern is MovementPattern.HORIZONTAL_PUSH:
            return _classification(MuscleFocus.GENERAL_TRICEPS, "mechanics:compound_press")
        if movement_pattern is MovementPattern.ELBOW_EXTENSION and _contains(
            instructions, "overhead", "behind your head", "behind the head"
        ):
            return _classification(MuscleFocus.TRICEPS_LONG_HEAD, "instructions:shoulder_flexed")
        return None

    if primary_muscle is MuscleGroup.TRAPS:
        if name == "dumbbell incline shrug" or name == "scapula dips":
            return _classification(
                MuscleFocus.MID_LOWER_TRAPS,
                "mechanics:scapular_retraction_depression",
            )
        if movement_pattern is MovementPattern.SHRUG:
            return _classification(MuscleFocus.UPPER_TRAPS, "mechanics:scapular_elevation")
        return None

    if primary_muscle is MuscleGroup.FOREARMS:
        if "extensor" in target or "reverse wrist curl" in name:
            return _classification(MuscleFocus.FOREARM_EXTENSORS, source_basis)
        if "flexor" in source_group and "extensor" not in source_group:
            return _classification(MuscleFocus.FOREARM_FLEXORS, "source_muscle_group:flexors")
        if "wrist curl" in name and "reverse" not in name:
            return _classification(MuscleFocus.FOREARM_FLEXORS, "mechanics:wrist_flexion")
        if exercise_type is ExerciseType.MOBILITY or "wrist circles" in name:
            return _classification(MuscleFocus.GENERAL_FOREARMS, "mechanics:broad_forearm")
        return None

    if primary_muscle is MuscleGroup.NECK:
        if "flexor" in target or "chin to chest" in name:
            return _classification(MuscleFocus.NECK_FLEXION, source_basis)
        if _contains(name, "side", "extension"):
            return _classification(
                MuscleFocus.NECK_LATERAL_EXTENSION,
                "mechanics:lateral_or_extension",
            )
        return None

    if primary_muscle is MuscleGroup.GLUTES:
        if "gluteus medius" in target or movement_pattern is MovementPattern.HIP_ABDUCTION:
            return _classification(MuscleFocus.GLUTE_MEDIUS_MINIMUS, source_basis)
        if movement_pattern in {
            MovementPattern.HIP_EXTENSION,
            MovementPattern.HIP_HINGE,
            MovementPattern.LUNGE,
            MovementPattern.SQUAT,
        }:
            return _classification(MuscleFocus.GLUTE_MAX, "mechanics:hip_extension")
        return None

    if primary_muscle is MuscleGroup.QUADRICEPS:
        return None

    if primary_muscle is MuscleGroup.HAMSTRINGS:
        if movement_pattern is MovementPattern.KNEE_FLEXION:
            return _classification(MuscleFocus.HAMSTRINGS_KNEE_FLEXION, "mechanics:knee_flexion")
        if movement_pattern is MovementPattern.HIP_HINGE or exercise_type is ExerciseType.MOBILITY:
            return _classification(
                MuscleFocus.HAMSTRINGS_HIP_EXTENSION,
                "mechanics:hip_hinge_or_stretch",
            )
        return None

    if primary_muscle is MuscleGroup.ADDUCTORS:
        return None

    if primary_muscle is MuscleGroup.CALVES:
        if "seated" in name:
            return _classification(MuscleFocus.SOLEUS, "mechanics:flexed_knee")
        if exercise_type is ExerciseType.MOBILITY:
            if "soleus" in source_group and "gastrocnemius" in source_group:
                return _classification(MuscleFocus.GENERAL_CALVES, "source_muscle_group:mixed_calf")
            return _classification(MuscleFocus.GASTROCNEMIUS, "mechanics:straight_knee_stretch")
        if movement_pattern is MovementPattern.CALF_RAISE:
            return _classification(MuscleFocus.GASTROCNEMIUS, "mechanics:straight_knee_raise")
        return None

    if primary_muscle is MuscleGroup.ABS:
        if movement_pattern is MovementPattern.CORE_ANTI_EXTENSION or _contains(
            name, "wheel rollout", "pilates hundred"
        ):
            return _classification(MuscleFocus.ANTI_EXTENSION, "mechanics:anti_extension")
        if _contains(name, "leg raise", "hip raise", "jackknife", "v up", "corkscrew"):
            return _classification(
                MuscleFocus.HIP_FLEXION_POSTERIOR_TILT,
                "mechanics:hip_flexion_or_posterior_tilt",
            )
        if movement_pattern is MovementPattern.SPINAL_FLEXION or _contains(
            name, "sit up", "crunch", "otis up", "chest lift"
        ):
            return _classification(MuscleFocus.TRUNK_FLEXION, "mechanics:trunk_flexion")
        return None

    if primary_muscle is MuscleGroup.OBLIQUES:
        if movement_pattern is MovementPattern.CORE_ANTI_ROTATION or "pallof" in name:
            return _classification(MuscleFocus.ANTI_ROTATION, "mechanics:anti_rotation")
        if movement_pattern is MovementPattern.CORE_ANTI_LATERAL_FLEXION or "side plank" in name:
            return _classification(MuscleFocus.LATERAL_FLEXION, "mechanics:anti_lateral_flexion")
        if _contains(name, "side bend", "lateral stretch", "iron cross stretch"):
            return _classification(MuscleFocus.LATERAL_FLEXION, "mechanics:lateral_flexion")
        if _contains(name, "twist", "rotation", "lift", "landmine", "spell caster", "bicycle"):
            return _classification(MuscleFocus.TRUNK_ROTATION, "mechanics:trunk_rotation")
        return None

    if primary_muscle is MuscleGroup.LOWER_BACK:
        if target == "thoracic spine" or "thoracic" in source_group:
            return _classification(MuscleFocus.THORACIC_MOBILITY, source_basis)
        if "spinal stretch" in name:
            return _classification(MuscleFocus.THORACIC_MOBILITY, "mechanics:spinal_mobility")
        if _contains(target, "erector", "spine") or _contains(source_group, "erector", "glutes"):
            return _classification(MuscleFocus.LUMBAR_ERECTORS, source_basis)
        return None

    return None
