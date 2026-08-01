from app.workouts.program_engine.enums import TrainingStatus
from app.workouts.program_engine.normalization import normalize_request
from app.workouts.program_engine.rulesets.resistance_training_v1 import RULESET, ProgramRuleset
from app.workouts.program_engine.schemas import ProgramGenerationRequest


def classify_training_status(
    request: ProgramGenerationRequest,
    ruleset: ProgramRuleset = RULESET,
) -> TrainingStatus:
    """Classify from label, training age, and recent consistency conservatively."""
    return normalize_request(request, ruleset).training_status
