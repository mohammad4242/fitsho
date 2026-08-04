from dataclasses import dataclass

from app.nutrition.enums import MedicalConditionCode, SafetyOutcome

MEDICAL_CONDITION_POLICY_VERSION = "medical-condition-v1"

_REVIEW_CONDITIONS = {
    MedicalConditionCode.CONTROLLED_HYPERTENSION,
    MedicalConditionCode.LIPID_DISORDER,
    MedicalConditionCode.TYPE_2_DIABETES_NON_INSULIN,
    MedicalConditionCode.STABLE_GASTROINTESTINAL,
}
_MANUAL_CONDITIONS = {
    MedicalConditionCode.KIDNEY_DISEASE,
    MedicalConditionCode.DIALYSIS,
    MedicalConditionCode.LIVER_DISEASE,
    MedicalConditionCode.INSULIN_TREATED_DIABETES,
}


@dataclass(frozen=True)
class SafetyAnswers:
    conditions: tuple[MedicalConditionCode, ...] = ()
    dangerous_food_reaction_history: bool = False
    pregnant: bool = False
    breastfeeding: bool = False
    eating_disorder_diagnosed: bool = False
    eating_disorder_active_symptoms: bool = False
    emergency_or_danger_symptoms: bool = False
    physician_dietary_restrictions: bool = False
    other_relevant_condition: bool = False
    complex_medication_food_interaction: bool = False


@dataclass(frozen=True)
class SafetyEvaluation:
    outcome: SafetyOutcome
    policy_version: str
    reason_codes: tuple[str, ...]


def evaluate_safety(answers: SafetyAnswers) -> SafetyEvaluation:
    conditions = set(answers.conditions)
    if answers.emergency_or_danger_symptoms:
        return _result(SafetyOutcome.UNSUPPORTED_OR_HARD_BLOCKED, "danger_symptoms_declared")
    if answers.other_relevant_condition or MedicalConditionCode.OTHER in conditions:
        return _result(SafetyOutcome.UNSUPPORTED_OR_HARD_BLOCKED, "condition_not_supported")

    manual_reasons = [
        code.value for code in sorted(conditions & _MANUAL_CONDITIONS, key=lambda item: item.value)
    ]
    if answers.pregnant:
        manual_reasons.append("pregnancy")
    if answers.breastfeeding:
        manual_reasons.append("breastfeeding")
    if answers.eating_disorder_diagnosed or answers.eating_disorder_active_symptoms:
        manual_reasons.append("eating_disorder")
    if answers.complex_medication_food_interaction:
        manual_reasons.append("complex_medication_food_interaction")
    if manual_reasons:
        return SafetyEvaluation(
            outcome=SafetyOutcome.PHYSICIAN_MANUAL_PLAN_REQUIRED,
            policy_version=MEDICAL_CONDITION_POLICY_VERSION,
            reason_codes=tuple(manual_reasons),
        )

    review_reasons = [
        code.value for code in sorted(conditions & _REVIEW_CONDITIONS, key=lambda item: item.value)
    ]
    if answers.physician_dietary_restrictions:
        review_reasons.append("physician_dietary_restriction")
    if answers.dangerous_food_reaction_history:
        review_reasons.append("dangerous_food_reaction_history")
    if review_reasons:
        return SafetyEvaluation(
            outcome=SafetyOutcome.AUTOMATIC_DRAFT_REQUIRES_PHYSICIAN_REVIEW,
            policy_version=MEDICAL_CONDITION_POLICY_VERSION,
            reason_codes=tuple(review_reasons),
        )
    return _result(SafetyOutcome.STANDARD_AUTOMATIC, "no_review_condition_declared")


def _result(outcome: SafetyOutcome, reason_code: str) -> SafetyEvaluation:
    return SafetyEvaluation(
        outcome=outcome,
        policy_version=MEDICAL_CONDITION_POLICY_VERSION,
        reason_codes=(reason_code,),
    )
