from dataclasses import replace

import pytest

from app.profile.enums import ExperienceLevel
from app.workouts.program_engine.engine import generate_program
from app.workouts.program_engine.enums import (
    GenerationErrorCode,
    TrainingExperience,
    TrainingStatus,
)
from app.workouts.program_engine.normalization import normalize_request
from app.workouts.program_engine.rulesets.resistance_training_v1 import RULESET
from tests.workouts.program_engine.golden_fixtures import full_catalog, request


@pytest.mark.parametrize(
    ("experience", "days"),
    [
        (TrainingExperience.FIRST_MONTH, 5),
        (TrainingExperience.FIRST_MONTH, 6),
        (TrainingExperience.BEGINNER, 5),
        (TrainingExperience.BEGINNER, 6),
        (TrainingExperience.ADVANCED, 2),
    ],
)
def test_engine_rejects_unsupported_resistance_training_combinations(
    experience: TrainingExperience, days: int
) -> None:
    result = generate_program(
        request(training_experience=experience, available_training_days=days),
        full_catalog(),
        RULESET,
    )

    assert result.program is None
    assert result.error_code is GenerationErrorCode.UNSUPPORTED_RESISTANCE_TRAINING_DAYS
    assert result.errors == ("UNSUPPORTED_RESISTANCE_TRAINING_DAYS",)


def test_ruleset_capacity_rejects_instead_of_silently_reducing_day_count() -> None:
    result = generate_program(
        request(
            training_experience=TrainingExperience.INTERMEDIATE,
            available_training_days=5,
        ),
        full_catalog(),
        replace(RULESET, max_resistance_days=4),
    )

    assert result.program is None
    assert result.error_code is GenerationErrorCode.UNSUPPORTED_RESISTANCE_TRAINING_DAYS


@pytest.mark.parametrize(
    ("experience", "days"),
    [
        (TrainingExperience.FIRST_MONTH, 2),
        (TrainingExperience.BEGINNER, 4),
        (TrainingExperience.INTERMEDIATE, 6),
        (TrainingExperience.ADVANCED, 3),
    ],
)
def test_supported_generation_preserves_requested_resistance_day_count(
    experience: TrainingExperience, days: int
) -> None:
    result = generate_program(
        request(training_experience=experience, available_training_days=days),
        full_catalog(),
        RULESET,
    )

    assert result.is_success, result.errors
    assert result.program is not None
    assert len(result.program.weekly_schedule) == days


def test_training_age_changes_training_status_not_template_level() -> None:
    normalized = normalize_request(
        request(
            training_experience=TrainingExperience.INTERMEDIATE,
            training_age_months=1,
            available_training_days=3,
        )
    )

    assert normalized.source.training_experience is TrainingExperience.INTERMEDIATE
    assert normalized.training_status is TrainingStatus.NOVICE
    assert (
        ExperienceLevel(normalized.source.training_experience.value) is ExperienceLevel.INTERMEDIATE
    )
