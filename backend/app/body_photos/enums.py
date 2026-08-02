from enum import StrEnum


class BodyPhotoPurpose(StrEnum):
    INITIAL_PLAN = "initial_plan"
    CYCLE_COMPLETION = "cycle_completion"
    PROGRESS_CHECK = "progress_check"


class BodyPhotoView(StrEnum):
    FRONT = "front"
    SIDE = "side"
    BACK = "back"


class BodyPhotoSessionState(StrEnum):
    DRAFT = "draft"
    AWAITING_CONSENT = "awaiting_consent"
    UPLOADING = "uploading"
    UPLOADED = "uploaded"
    QUEUED = "queued"
    VALIDATING = "validating"
    ANALYZING = "analyzing"
    REVIEW_PENDING = "review_pending"
    COMPLETED = "completed"
    FAILED = "failed"
    DELETED = "deleted"


class BodyPhotoConsentType(StrEnum):
    OPERATIONAL_PROCESSING = "operational_processing"
    MODEL_TRAINING = "model_training"
