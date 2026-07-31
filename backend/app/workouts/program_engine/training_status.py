from app.workouts.program_engine.enums import TrainingStatus
from app.workouts.program_engine.normalization import normalize_request
from app.workouts.program_engine.schemas import ProgramGenerationRequest


def classify_training_status(request: ProgramGenerationRequest) -> TrainingStatus:
    """Classify from label, training age, and recent consistency conservatively."""
    return normalize_request(request).training_status
