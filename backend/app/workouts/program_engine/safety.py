from app.workouts.program_engine.enums import SafetyStatus
from app.workouts.program_engine.schemas import NormalizedProgramRequest, SafetyAssessment


def screen_safety(request: NormalizedProgramRequest) -> SafetyAssessment:
    source = request.source
    if source.current_pain_or_red_flags or source.reports_uncontrolled_medical_condition:
        return SafetyAssessment(
            status=SafetyStatus.STOP_AND_REFER,
            reason_codes=("PROGRAM_REJECTED_SAFETY_STATUS",),
        )
    if source.pregnancy_or_postpartum:
        return SafetyAssessment(
            status=SafetyStatus.REQUIRES_PROFESSIONAL_REVIEW,
            reason_codes=("SPECIALIST_PATHWAY_REQUIRED",),
        )
    if any(
        not item.stable or not item.has_computable_constraint
        for item in source.injuries_and_limitations
    ):
        return SafetyAssessment(
            status=SafetyStatus.REQUIRES_PROFESSIONAL_REVIEW,
            reason_codes=("LIMITATION_REQUIRES_COMPUTABLE_CONSTRAINTS",),
        )
    if source.injuries_and_limitations or any(
        (
            source.blocked_exercises,
            source.blocked_movement_patterns,
            source.blocked_caution_tags,
        )
    ):
        return SafetyAssessment(
            status=SafetyStatus.CLEAR_WITH_MODIFICATIONS,
            reason_codes=("EXPLICIT_LIMITATIONS_APPLIED",),
        )
    return SafetyAssessment(status=SafetyStatus.CLEAR, reason_codes=("SAFETY_SCREEN_CLEAR",))
