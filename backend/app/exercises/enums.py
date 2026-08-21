from enum import StrEnum


class BodyRegion(StrEnum):
    UPPER_BODY = "upper_body"
    LOWER_BODY = "lower_body"
    CORE = "core"


class ExerciseContentType(StrEnum):
    EXERCISE = "exercise"
    GUIDE = "guide"


class MuscleGroup(StrEnum):
    CHEST = "chest"
    BACK = "back"
    SHOULDERS = "shoulders"
    BICEPS = "biceps"
    TRICEPS = "triceps"
    TRAPS = "traps"
    FOREARMS = "forearms"
    NECK = "neck"
    GLUTES = "glutes"
    QUADRICEPS = "quadriceps"
    HAMSTRINGS = "hamstrings"
    ADDUCTORS = "adductors"
    ABDUCTORS = "abductors"
    LEGS = "legs"
    CALVES = "calves"
    ABS = "abs"
    OBLIQUES = "obliques"
    LOWER_BACK = "lower_back"


class MuscleFocus(StrEnum):
    GENERAL_CHEST = "general_chest"
    UPPER_CHEST = "upper_chest"
    MID_CHEST = "mid_chest"
    LOWER_CHEST = "lower_chest"
    GENERAL_BACK = "general_back"
    LATS = "lats"
    LOWER_BACK = "lower_back"
    MID_BACK_RHOMBOIDS = "mid_back_rhomboids"
    UPPER_BACK = "upper_back"
    GENERAL_SHOULDERS = "general_shoulders"
    FRONT_DELT = "front_delt"
    LATERAL_DELT = "lateral_delt"
    REAR_DELT = "rear_delt"
    GENERAL_BICEPS = "general_biceps"
    BICEPS_BRACHII = "biceps_brachii"
    BRACHIALIS_BRACHIORADIALIS = "brachialis_brachioradialis"
    GENERAL_TRICEPS = "general_triceps"
    TRICEPS_LONG_HEAD = "triceps_long_head"
    TRICEPS_LATERAL_MEDIAL_HEADS = "triceps_lateral_medial_heads"
    UPPER_TRAPS = "upper_traps"
    MID_LOWER_TRAPS = "mid_lower_traps"
    GENERAL_FOREARMS = "general_forearms"
    FOREARM_FLEXORS = "forearm_flexors"
    FOREARM_EXTENSORS = "forearm_extensors"
    NECK_FLEXION = "neck_flexion"
    NECK_LATERAL_EXTENSION = "neck_lateral_extension"
    GLUTE_MAX = "glute_max"
    GLUTE_MEDIUS_MINIMUS = "glute_medius_minimus"
    GENERAL_QUADRICEPS = "general_quadriceps"
    RECTUS_FEMORIS = "rectus_femoris"
    VASTI = "vasti"
    HAMSTRINGS_HIP_EXTENSION = "hamstrings_hip_extension"
    HAMSTRINGS_KNEE_FLEXION = "hamstrings_knee_flexion"
    HIP_ADDUCTION = "hip_adduction"
    ADDUCTOR_MOBILITY = "adductor_mobility"
    GENERAL_CALVES = "general_calves"
    GASTROCNEMIUS = "gastrocnemius"
    SOLEUS = "soleus"
    TRUNK_FLEXION = "trunk_flexion"
    HIP_FLEXION_POSTERIOR_TILT = "hip_flexion_posterior_tilt"
    ANTI_EXTENSION = "anti_extension"
    TRUNK_ROTATION = "trunk_rotation"
    LATERAL_FLEXION = "lateral_flexion"
    ANTI_ROTATION = "anti_rotation"
    LUMBAR_ERECTORS = "lumbar_erectors"
    THORACIC_MOBILITY = "thoracic_mobility"


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


class MediaPresentation(StrEnum):
    MALE = "male"
    FEMALE = "female"
    UNSPECIFIED = "unspecified"


class MediaRole(StrEnum):
    VIDEO = "video"


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


class PrescriptionMode(StrEnum):
    REPS = "reps"
    DURATION = "duration"


class ExerciseLabel(StrEnum):
    FULL_BODY = "full_body"
    CARDIO = "cardio"


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
