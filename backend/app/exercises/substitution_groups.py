"""Curated exact-equivalence groups for deterministic exercise substitution."""

import re

from app.exercises.enums import ExerciseType, MovementPattern, MuscleGroup

LEGACY_BROAD_SUBSTITUTION_GROUPS = frozenset(
    pattern.value for pattern in MovementPattern if pattern is not MovementPattern.OTHER
)


def curated_substitution_group(
    *,
    name_en: str,
    movement_pattern: MovementPattern,
    primary_muscle: MuscleGroup | None,
    exercise_type: ExerciseType,
) -> str | None:
    """Return a conservative exact-role group, or ``None`` for metadata fallback."""

    if primary_muscle is None or exercise_type in {ExerciseType.MOBILITY, ExerciseType.OTHER}:
        return None
    name = _normalized_name(name_en)

    if movement_pattern is MovementPattern.HORIZONTAL_PUSH:
        if "dip" in name:
            if primary_muscle is MuscleGroup.CHEST:
                return "horizontal_push_dip_chest"
            if primary_muscle is MuscleGroup.TRICEPS:
                return "horizontal_push_dip_triceps"
            return None
        if primary_muscle is MuscleGroup.TRICEPS:
            return "horizontal_press_triceps" if "press" in name or "push up" in name else None
        if primary_muscle is not MuscleGroup.CHEST:
            return None
        if "push up" in name:
            return "horizontal_press_push_up"
        if "incline" in name:
            return "horizontal_press_incline"
        if "decline" in name:
            return "horizontal_press_decline"
        if "press" in name:
            return "horizontal_press_flat"
        return None

    if movement_pattern is MovementPattern.VERTICAL_PUSH:
        if primary_muscle is not MuscleGroup.SHOULDERS:
            return None
        if "clean" in name:
            return "vertical_press_power"
        if "press" in name:
            return "vertical_press_shoulder"
        return None

    if movement_pattern is MovementPattern.HORIZONTAL_PULL:
        if "face pull" in name:
            return "horizontal_pull_face_pull"
        if "upright row" in name:
            return "horizontal_pull_upright_row"
        if primary_muscle is MuscleGroup.SHOULDERS or _contains(name, "rear delt", "reverse fly"):
            return "horizontal_pull_rear_delt"
        if primary_muscle is not MuscleGroup.BACK or "row" not in name:
            return None
        if _contains(name, "inverted row", "ring high row", "with straps", "between chairs"):
            return "horizontal_pull_row_bodyweight"
        if _contains(name, "seated", "incline", "lying", "lever", "t bar"):
            return "horizontal_pull_row_supported"
        return "horizontal_pull_row_unsupported"

    if movement_pattern is MovementPattern.VERTICAL_PULL:
        if primary_muscle is not MuscleGroup.BACK:
            return None
        if _contains(name, "straight arm", "pullover"):
            return "vertical_pull_straight_arm"
        if _contains(name, "pull up", "chin up", "bench pull up", "commando"):
            return "vertical_pull_bodyweight"
        if "pulldown" in name or "pull down" in name:
            return "vertical_pull_pulldown"
        return None

    if movement_pattern is MovementPattern.SQUAT:
        if primary_muscle not in {
            MuscleGroup.QUADRICEPS,
            MuscleGroup.ADDUCTORS,
            MuscleGroup.ABDUCTORS,
            MuscleGroup.GLUTES,
        }:
            return None
        if "leg press" in name:
            return "leg_press_knee_dominant"
        if _contains(name, "hack squat", "smith chair squat"):
            return "squat_supported_machine"
        if "sissy squat" in name:
            return "squat_sissy"
        if "sumo" in name or "wide stance" in name:
            return "squat_wide_stance"
        if "squat" in name:
            return "squat_free_weight"
        return None

    if movement_pattern is MovementPattern.LUNGE:
        if primary_muscle not in {MuscleGroup.QUADRICEPS, MuscleGroup.GLUTES}:
            return None
        if "step up" in name:
            return "lunge_step_up"
        if "lunge" in name or "split squat" in name:
            return "lunge_split_stance"
        return None

    if movement_pattern is MovementPattern.HIP_HINGE:
        if primary_muscle not in {MuscleGroup.HAMSTRINGS, MuscleGroup.GLUTES}:
            return None
        if _contains(name, "romanian", "straight leg", "stiff leg"):
            return "hip_hinge_romanian_deadlift"
        if "reverse hyperextension" in name:
            return "hip_hinge_reverse_hyperextension"
        if "deadlift" in name:
            return "hip_hinge_deadlift"
        if "good morning" in name:
            return "hip_hinge_good_morning"
        return None

    if movement_pattern is MovementPattern.HIP_EXTENSION:
        if primary_muscle is not MuscleGroup.GLUTES:
            return None
        if _contains(name, "hip thrust", "glute bridge", "hip lift", "bridge pose"):
            return "hip_extension_bridge"
        if _contains(name, "kickback", "rear kick", "donkey kick", "hip extension"):
            return "hip_extension_kickback"
        if "pull through" in name:
            return "hip_extension_pull_through"
        return None

    if movement_pattern is MovementPattern.KNEE_FLEXION:
        if primary_muscle is MuscleGroup.HAMSTRINGS and "curl" in name:
            return "knee_flexion_leg_curl"
        return None

    if movement_pattern is MovementPattern.KNEE_EXTENSION:
        if primary_muscle is not MuscleGroup.QUADRICEPS:
            return None
        if "leg press" in name:
            return "leg_press_knee_dominant"
        if "leg extension" in name:
            return "knee_extension"
        return None

    if movement_pattern is MovementPattern.ELBOW_FLEXION:
        if primary_muscle is MuscleGroup.FOREARMS:
            if "reverse wrist curl" in name:
                return "forearm_wrist_extension"
            if "wrist curl" in name or "standing curl" in name:
                return "forearm_wrist_flexion"
            return None
        if primary_muscle is not MuscleGroup.BICEPS:
            return None
        if _contains(name, "hammer", "neutral", "cross body"):
            return "elbow_flexion_neutral"
        if _contains(name, "reverse", "zottman", "pronate"):
            return "elbow_flexion_pronated"
        if "preacher" in name:
            return "elbow_flexion_preacher"
        if _contains(name, "incline", "prone", "supine"):
            return "elbow_flexion_lengthened"
        if "curl" in name:
            return "elbow_flexion_supinated"
        return None

    if movement_pattern is MovementPattern.ELBOW_EXTENSION:
        if primary_muscle is not MuscleGroup.TRICEPS:
            return None
        if "pushdown" in name:
            return "elbow_extension_pushdown"
        if "overhead" in name or "seated triceps extension" in name:
            return "elbow_extension_overhead"
        if _contains(name, "lying", "skull"):
            return "elbow_extension_lying"
        if "kickback" in name:
            return "elbow_extension_kickback"
        if "extension" in name:
            return "elbow_extension_general"
        return None

    if movement_pattern is MovementPattern.SHOULDER_ABDUCTION:
        if primary_muscle not in {MuscleGroup.SHOULDERS, MuscleGroup.TRAPS}:
            return None
        if _contains(name, "rear", "bent over"):
            return "shoulder_raise_rear"
        if _contains(name, "front raise", "y raise"):
            return "shoulder_raise_front"
        if "lateral raise" in name:
            return "shoulder_raise_lateral"
        return None

    if movement_pattern is MovementPattern.CALF_RAISE:
        if primary_muscle is not MuscleGroup.CALVES:
            return None
        if "seated" in name:
            return "calf_raise_seated"
        if "press" in name:
            return "calf_raise_leg_press"
        if "raise" in name:
            return "calf_raise_standing"
        return None

    if movement_pattern is MovementPattern.SHRUG:
        return "scapular_elevation_shrug" if primary_muscle is MuscleGroup.TRAPS else None

    if movement_pattern is MovementPattern.HIP_ABDUCTION:
        return (
            "hip_abduction"
            if primary_muscle in {MuscleGroup.GLUTES, MuscleGroup.ABDUCTORS}
            else None
        )

    if movement_pattern is MovementPattern.HIP_ADDUCTION:
        return "hip_adduction" if primary_muscle is MuscleGroup.ADDUCTORS else None

    core_groups = {
        MovementPattern.CORE_ANTI_EXTENSION: "core_anti_extension",
        MovementPattern.CORE_ANTI_ROTATION: "core_anti_rotation",
        MovementPattern.CORE_ANTI_LATERAL_FLEXION: "core_anti_lateral_flexion",
    }
    if movement_pattern in core_groups and exercise_type is ExerciseType.CORE:
        return core_groups[movement_pattern]

    if movement_pattern is MovementPattern.SPINAL_FLEXION and exercise_type is ExerciseType.CORE:
        if _contains(name, "twist", "bicycle"):
            return "core_rotation"
        if _contains(name, "leg raise", "jackknife", "reverse crunch"):
            return "core_hip_flexion"
        if _contains(name, "crunch", "sit up"):
            return "core_spinal_flexion"
    return None


def effective_substitution_group(
    *,
    name_en: str,
    movement_pattern: MovementPattern,
    primary_muscle: MuscleGroup | None,
    exercise_type: ExerciseType,
    persisted_group: str | None,
) -> str | None:
    """Preserve explicit curated values and replace legacy pattern-wide groups."""

    if persisted_group and persisted_group not in LEGACY_BROAD_SUBSTITUTION_GROUPS:
        return persisted_group
    return curated_substitution_group(
        name_en=name_en,
        movement_pattern=movement_pattern,
        primary_muscle=primary_muscle,
        exercise_type=exercise_type,
    )


def _normalized_name(value: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9]+", " ", value.lower()).split())


def _contains(value: str, *terms: str) -> bool:
    return any(term in value for term in terms)
