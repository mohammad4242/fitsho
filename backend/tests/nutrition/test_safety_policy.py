import pytest

from app.nutrition.enums import MedicalConditionCode, SafetyOutcome
from app.nutrition.safety import SafetyAnswers, evaluate_safety


@pytest.mark.parametrize(
    ("answers", "expected"),
    [
        (SafetyAnswers(), SafetyOutcome.STANDARD_AUTOMATIC),
        (
            SafetyAnswers(conditions=(MedicalConditionCode.CONTROLLED_HYPERTENSION,)),
            SafetyOutcome.AUTOMATIC_DRAFT_REQUIRES_PHYSICIAN_REVIEW,
        ),
        (
            SafetyAnswers(conditions=(MedicalConditionCode.KIDNEY_DISEASE,)),
            SafetyOutcome.PHYSICIAN_MANUAL_PLAN_REQUIRED,
        ),
        (
            SafetyAnswers(emergency_or_danger_symptoms=True),
            SafetyOutcome.UNSUPPORTED_OR_HARD_BLOCKED,
        ),
    ],
)
def test_condition_policy_returns_the_approved_outcome(
    answers: SafetyAnswers,
    expected: SafetyOutcome,
) -> None:
    decision = evaluate_safety(answers)

    assert decision.outcome is expected
    assert decision.policy_version == "medical-condition-v1"
    assert decision.reason_codes


def test_highest_risk_outcome_wins_independent_of_answer_order() -> None:
    decision = evaluate_safety(
        SafetyAnswers(
            conditions=(
                MedicalConditionCode.LIPID_DISORDER,
                MedicalConditionCode.KIDNEY_DISEASE,
            )
        )
    )

    assert decision.outcome is SafetyOutcome.PHYSICIAN_MANUAL_PLAN_REQUIRED
