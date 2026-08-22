import hashlib

from app.workouts.program_engine.constraints import derive_constraints
from app.workouts.program_engine.enums import TrainingExperience, TrainingStatus
from app.workouts.program_engine.rulesets.resistance_training_v1 import RULESET, ProgramRuleset
from app.workouts.program_engine.schemas import NormalizedProgramRequest, ProgramGenerationRequest


def normalize_request(
    request: ProgramGenerationRequest,
    ruleset: ProgramRuleset = RULESET,
) -> NormalizedProgramRequest:
    training_status, assumptions = _classify_status(request, ruleset)
    seed = request.seed_optional
    if seed is None:
        canonical = request.model_dump_json(exclude={"seed_optional"})
        seed = int.from_bytes(hashlib.sha256(canonical.encode()).digest()[:8], "big") % (2**63 - 1)
        assumptions.append("SEED_DERIVED_FROM_NORMALIZED_INPUT")
    resistance_days = min(request.available_training_days, ruleset.max_resistance_days)
    if request.available_training_days > ruleset.max_resistance_days:
        assumptions.append("RESISTANCE_DAYS_CAPPED_AT_RULESET_MAXIMUM")
    return NormalizedProgramRequest(
        source=request,
        primary_goal=request.primary_goal,
        training_status=training_status,
        resistance_training_days=resistance_days,
        seed=seed,
        constraints=derive_constraints(request),
        assumptions=tuple(assumptions),
    )


def _classify_status(
    request: ProgramGenerationRequest,
    ruleset: ProgramRuleset,
) -> tuple[TrainingStatus, list[str]]:
    age_status = (
        TrainingStatus.NOVICE
        if request.training_age_months < ruleset.novice_training_age_months
        else TrainingStatus.EARLY_INTERMEDIATE
        if request.training_age_months < ruleset.early_intermediate_training_age_months
        else TrainingStatus.INTERMEDIATE
        if request.training_age_months < ruleset.intermediate_training_age_months
        else TrainingStatus.ADVANCED
    )
    label_status = {
        TrainingExperience.FIRST_MONTH: TrainingStatus.NOVICE,
        TrainingExperience.BEGINNER: TrainingStatus.NOVICE,
        TrainingExperience.INTERMEDIATE: TrainingStatus.INTERMEDIATE,
        TrainingExperience.ADVANCED: TrainingStatus.ADVANCED,
    }[request.training_experience]
    order = list(TrainingStatus)
    status = min(age_status, label_status, key=order.index)
    assumptions: list[str] = []
    if status is not label_status:
        assumptions.append("TRAINING_STATUS_REDUCED_FOR_TRAINING_AGE")
    if (
        request.recent_training_history.consistent_weeks is not None
        and request.recent_training_history.consistent_weeks
        < ruleset.minimum_consistent_weeks_for_experience
        and status is not TrainingStatus.NOVICE
    ):
        status = TrainingStatus.EARLY_INTERMEDIATE
        assumptions.append("TRAINING_STATUS_REDUCED_FOR_RECENT_CONSISTENCY")
    return status, assumptions
