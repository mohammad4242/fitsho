from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.exercises.enums import Equipment, ExerciseCautionTag, MovementPattern
from app.profile.enums import TrainingLocation
from app.workouts.program_engine.enums import (
    Goal,
    MedicalClearanceStatus,
    RedFlag,
    SafetyStatus,
    TrainingExperience,
    TrainingStatus,
)
from app.workouts.program_engine.normalization import normalize_request
from app.workouts.program_engine.safety import screen_safety
from app.workouts.program_engine.schemas import Limitation, ProgramGenerationRequest


def request(**overrides: object) -> ProgramGenerationRequest:
    values: dict[str, object] = {
        "user_id": uuid4(),
        "age": 30,
        "height_cm": 175,
        "weight_kg": 75,
        "primary_goal": Goal.GENERAL_FITNESS,
        "training_experience": TrainingExperience.BEGINNER,
        "training_age_months": 2,
        "available_training_days": 3,
        "session_duration_minutes": 45,
        "available_equipment": [Equipment.BODYWEIGHT],
        "training_location": TrainingLocation.HOME,
    }
    values.update(overrides)
    return ProgramGenerationRequest.model_validate(values)


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("weight_loss", Goal.FAT_LOSS),
        ("lose_weight", Goal.FAT_LOSS),
        ("weight_gain", Goal.MUSCLE_GAIN),
        ("build_muscle", Goal.MUSCLE_GAIN),
        ("improve_fitness", Goal.GENERAL_FITNESS),
    ],
)
def test_goal_aliases_are_normalized(source: str, expected: Goal) -> None:
    assert request(primary_goal=source).primary_goal is expected


@pytest.mark.parametrize(
    ("field", "value"),
    [("age", 17), ("height_cm", 80), ("weight_kg", 20), ("available_training_days", 0)],
)
def test_impossible_values_are_rejected(field: str, value: object) -> None:
    with pytest.raises(ValidationError):
        request(**{field: value})


def test_conflicting_experience_is_classified_conservatively() -> None:
    normalized = normalize_request(
        request(
            training_experience=TrainingExperience.ADVANCED,
            training_age_months=4,
        )
    )

    assert normalized.training_status is TrainingStatus.NOVICE
    assert "TRAINING_STATUS_REDUCED_FOR_TRAINING_AGE" in normalized.assumptions


@pytest.mark.parametrize("red_flag", list(RedFlag))
def test_red_flags_stop_automatic_generation(red_flag: RedFlag) -> None:
    assessment = screen_safety(normalize_request(request(current_pain_or_red_flags=[red_flag])))

    assert assessment.status is SafetyStatus.STOP_AND_REFER
    assert "PROGRAM_REJECTED_SAFETY_STATUS" in assessment.reason_codes


def test_ambiguous_limitation_requires_professional_review() -> None:
    assessment = screen_safety(
        normalize_request(
            request(injuries_and_limitations=[Limitation(name="old shoulder issue", stable=True)])
        )
    )

    assert assessment.status is SafetyStatus.REQUIRES_PROFESSIONAL_REVIEW


def test_stable_limitation_with_computable_constraints_is_allowed_with_modifications() -> None:
    normalized = normalize_request(
        request(
            injuries_and_limitations=[
                Limitation(
                    name="assessed shoulder limitation",
                    stable=True,
                    blocked_movement_patterns=[MovementPattern.VERTICAL_PUSH],
                    blocked_caution_tags=[ExerciseCautionTag.OVERHEAD_POSITION],
                )
            ]
        )
    )
    assessment = screen_safety(normalized)

    assert assessment.status is SafetyStatus.CLEAR_WITH_MODIFICATIONS
    assert MovementPattern.VERTICAL_PUSH in normalized.constraints.blocked_movement_patterns


def test_missing_medical_clearance_for_reported_condition_requires_review() -> None:
    assessment = screen_safety(
        normalize_request(
            request(
                medical_clearance_status=MedicalClearanceStatus.UNKNOWN,
                reports_uncontrolled_medical_condition=True,
            )
        )
    )

    assert assessment.status is SafetyStatus.STOP_AND_REFER


def test_pregnancy_or_postpartum_requires_specialist_pathway() -> None:
    assessment = screen_safety(normalize_request(request(pregnancy_or_postpartum=True)))

    assert assessment.status is SafetyStatus.REQUIRES_PROFESSIONAL_REVIEW
    assert assessment.reason_codes == ("SPECIALIST_PATHWAY_REQUIRED",)
