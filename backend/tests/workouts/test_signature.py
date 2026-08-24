from decimal import Decimal
from typing import Any, cast

from app.exercises.enums import Equipment
from app.profile.enums import (
    ExperienceLevel,
    HomeTrainingSetup,
    Sex,
    TrainingCaution,
    TrainingLocation,
)
from app.workouts.schemas import GenerationSignatureContext
from app.workouts.signature import build_generation_signature


def context(**changes: object) -> GenerationSignatureContext:
    values: dict[str, object] = {
        "fitness_goal": "build_muscle",
        "experience_level": ExperienceLevel.BEGINNER,
        "training_days_per_week": 3,
        "training_location": TrainingLocation.HOME,
        "home_training_setup": HomeTrainingSetup.DUMBBELLS_AVAILABLE,
        "session_duration_minutes": 60,
        "plan_duration_weeks": 4,
        "training_cautions": (TrainingCaution.KNEE,),
        "physical_limitations": "  avoid   sudden loading ",
        "current_weight_kg": Decimal("74.9"),
        "candidate_set_hash": "a" * 64,
        "catalog_programming_version": "catalog-v1",
        "model_id": "model-a",
        "prompt_version": "prompt-v1",
        "generation_policy_version": "policy-v1",
        "sex": Sex.MALE,
    }
    values.update(changes)
    return GenerationSignatureContext(**cast(Any, values))


def test_irrelevant_identity_fields_do_not_affect_generation_signature() -> None:
    assert build_generation_signature(context()) == build_generation_signature(
        context(display_name="Other", age=40, height_cm=190)
    )


def test_relevant_conditions_and_candidate_set_change_generation_signature() -> None:
    baseline = build_generation_signature(context())

    assert baseline != build_generation_signature(context(training_days_per_week=4))
    assert baseline != build_generation_signature(context(candidate_set_hash="b" * 64))
    assert baseline != build_generation_signature(context(current_weight_kg=Decimal("75.0")))
    assert baseline != build_generation_signature(context(sex=Sex.FEMALE))
    assert baseline != build_generation_signature(
        context(available_equipment=frozenset({Equipment.BODYWEIGHT}))
    )


def test_limitations_normalization_ignores_unicode_form_and_control_character_changes() -> None:
    baseline = build_generation_signature(context(physical_limitations="avoid shoulder load"))

    assert baseline == build_generation_signature(
        context(physical_limitations="avoid\u0000  shoulder\tload")
    )
