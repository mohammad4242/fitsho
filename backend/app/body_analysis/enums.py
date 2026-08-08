from enum import StrEnum


class BodyArea(StrEnum):
    SHOULDERS = "shoulders"
    CHEST = "chest"
    BACK = "back"
    LATS = "lats"
    ARMS = "arms"
    FOREARMS = "forearms"
    WAIST_MIDSECTION = "waist_midsection"
    GLUTES = "glutes"
    QUADS = "quads"
    HAMSTRINGS = "hamstrings"
    CALVES = "calves"
    SYMMETRY = "symmetry"
    VISIBLE_ALIGNMENT_OR_POSTURE = "visible_alignment_or_posture"


class BodyAnalysisClassification(StrEnum):
    STRENGTH = "strength"
    MILD_LAG = "mild_lag"
    CLEAR_LAG = "clear_lag"
    UNCERTAIN = "uncertain"
    NEUTRAL = "neutral"


class BodyAnalysisStatus(StrEnum):
    QUEUED = "queued"
    VALIDATING = "validating"
    ANALYZING = "analyzing"
    REVIEW_PENDING = "review_pending"
    COMPLETED = "completed"
    FAILED = "failed"


class BodyAnalysisResultSource(StrEnum):
    AI = "ai"
    COACH = "coach"
    DOCTOR = "doctor"


class BodyAnalysisReviewerRole(StrEnum):
    COACH = "coach"
    DOCTOR = "doctor"


class BodyAnalysisReviewDecision(StrEnum):
    APPROVED = "approved"
    CHANGES_REQUIRED = "changes_required"
    REJECTED = "rejected"


class SpecialistRole(StrEnum):
    COACH = "coach"
    DOCTOR = "doctor"
    PHYSICIAN = "physician"


class TrainingEmphasis(StrEnum):
    LATERAL_DELTOID = "lateral_deltoid"
    REAR_DELTOID = "rear_deltoid"
    CHEST = "chest"
    UPPER_CHEST = "upper_chest"
    BACK_WIDTH = "back_width"
    BACK_THICKNESS = "back_thickness"
    BICEPS = "biceps"
    TRICEPS = "triceps"
    FOREARMS = "forearms"
    WAIST_MIDSECTION = "waist_midsection"
    GLUTES = "glutes"
    QUADS = "quads"
    HAMSTRINGS = "hamstrings"
    CALVES = "calves"


class AnalysisLimitation(StrEnum):
    BLUR = "blur"
    CLOTHING_OCCLUSION = "clothing_occlusion"
    EXCESSIVE_BACKGROUND_CLUTTER = "excessive_background_clutter"
    INCOMPLETE_VIEW = "incomplete_view"
    INCONSISTENT_POSE = "inconsistent_pose"
    LIGHTING = "lighting"
    LOW_RESOLUTION = "low_resolution"
    OCCLUSION = "occlusion"
    PERSPECTIVE = "perspective"
    POSE = "pose"
    VISIBILITY = "visibility"
