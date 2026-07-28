from enum import StrEnum


class BodyRegion(StrEnum):
    UPPER_BODY = "upper_body"
    LOWER_BODY = "lower_body"
    CORE = "core"


class MuscleGroup(StrEnum):
    CHEST = "chest"
    BACK = "back"
    SHOULDERS = "shoulders"
    BICEPS = "biceps"
    TRICEPS = "triceps"
    TRAPS = "traps"
    GLUTES = "glutes"
    QUADRICEPS = "quadriceps"
    HAMSTRINGS = "hamstrings"
    ADDUCTORS = "adductors"
    CALVES = "calves"
    ABS = "abs"
    OBLIQUES = "obliques"
    LOWER_BACK = "lower_back"


class Equipment(StrEnum):
    BODYWEIGHT = "bodyweight"
    DUMBBELL = "dumbbell"
    BARBELL = "barbell"
    CABLE = "cable"
    MACHINE = "machine"
    RESISTANCE_BAND = "resistance_band"
    BENCH = "bench"
    PULL_UP_BAR = "pull_up_bar"
    OTHER = "other"


class Difficulty(StrEnum):
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"


class MediaType(StrEnum):
    IMAGE = "image"
    ANIMATED_WEBP = "animated_webp"
    GIF = "gif"
    VIDEO = "video"
    PLACEHOLDER = "placeholder"


class MovementPattern(StrEnum):
    HORIZONTAL_PUSH = "horizontal_push"
    VERTICAL_PUSH = "vertical_push"
    HORIZONTAL_PULL = "horizontal_pull"
    VERTICAL_PULL = "vertical_pull"
    SQUAT = "squat"
    HIP_HINGE = "hip_hinge"
    LUNGE = "lunge"
    KNEE_EXTENSION = "knee_extension"
    KNEE_FLEXION = "knee_flexion"
    HIP_EXTENSION = "hip_extension"
    HIP_ABDUCTION = "hip_abduction"
    HIP_ADDUCTION = "hip_adduction"
    CALF_RAISE = "calf_raise"
    ELBOW_FLEXION = "elbow_flexion"
    ELBOW_EXTENSION = "elbow_extension"
    SHOULDER_ABDUCTION = "shoulder_abduction"
    SHOULDER_EXTERNAL_ROTATION = "shoulder_external_rotation"
    SHRUG = "shrug"
    SPINAL_FLEXION = "spinal_flexion"
    CORE_ANTI_EXTENSION = "core_anti_extension"
    CORE_ANTI_ROTATION = "core_anti_rotation"
    CORE_ANTI_LATERAL_FLEXION = "core_anti_lateral_flexion"
    OTHER = "other"


class ExerciseType(StrEnum):
    COMPOUND = "compound"
    ISOLATION = "isolation"
    CORE = "core"
    MOBILITY = "mobility"
    OTHER = "other"


class ExerciseCautionTag(StrEnum):
    LOWER_BACK_LOADING = "lower_back_loading"
    SPINAL_FLEXION = "spinal_flexion"
    DEEP_KNEE_FLEXION = "deep_knee_flexion"
    OVERHEAD_POSITION = "overhead_position"
    SHOULDER_INTERNAL_ROTATION = "shoulder_internal_rotation"
    SHOULDER_EXTERNAL_ROTATION = "shoulder_external_rotation"
    WRIST_LOADING = "wrist_loading"
    NECK_LOADING = "neck_loading"
    BALANCE_DEMAND = "balance_demand"
    OTHER = "other"
