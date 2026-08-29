from uuid import uuid4

import pytest

from app.exercises.enums import MuscleGroup
from app.training_templates.tags import TemplateFocusTag
from app.workouts.program_engine.enums import SplitType, TrainingExperience, TrainingStatus
from app.workouts.program_engine.normalization import normalize_request
from app.workouts.program_engine.rulesets.resistance_training_v1 import RULESET
from app.workouts.program_engine.schemas import BodyAnalysisInfluence, NormalizedProgramRequest
from app.workouts.program_engine.topology_preference import professional_topology_preference
from tests.workouts.program_engine.golden_fixtures import (
    ADVANCED_HISTORY,
    INTERMEDIATE_HISTORY,
    request,
)


def _normalized(**overrides: object) -> NormalizedProgramRequest:
    values: dict[str, object] = {
        "training_experience": TrainingExperience.INTERMEDIATE,
        "training_age_months": 30,
        "available_training_days": 4,
        "recent_training_history": INTERMEDIATE_HISTORY,
    }
    values.update(overrides)
    return normalize_request(request(**values), RULESET)


def _score(
    normalized: NormalizedProgramRequest,
    split_type: SplitType,
    *,
    template_tags: frozenset[TemplateFocusTag] | None = None,
) -> int:
    return professional_topology_preference(
        normalized,
        split_type,
        RULESET,
        template_tags=template_tags,
    ).score


@pytest.mark.parametrize(
    ("experience", "training_age_months", "expected_status"),
    [
        (TrainingExperience.FIRST_MONTH, 24, TrainingStatus.NOVICE),
        (TrainingExperience.BEGINNER, 24, TrainingStatus.NOVICE),
        (TrainingExperience.INTERMEDIATE, 1, TrainingStatus.NOVICE),
        (TrainingExperience.ADVANCED, 10, TrainingStatus.EARLY_INTERMEDIATE),
    ],
)
def test_professional_topology_uses_normalized_status_scope(
    experience: TrainingExperience,
    training_age_months: int,
    expected_status: TrainingStatus,
) -> None:
    normalized = _normalized(
        training_experience=experience,
        training_age_months=training_age_months,
        available_training_days=4,
    )

    assert normalized.training_status is expected_status
    assert _score(normalized, SplitType.BODY_PART_ROTATION) == 0


@pytest.mark.parametrize("days", [1, 2, 3])
def test_professional_topology_requires_four_through_six_resistance_days(days: int) -> None:
    normalized = _normalized(available_training_days=days)

    assert _score(normalized, SplitType.BODY_PART_ROTATION) == 0


@pytest.mark.parametrize(
    ("split_type", "expected"),
    [
        (SplitType.FULL_BODY, 0),
        (SplitType.FULL_BODY_AB, 0),
        (SplitType.FULL_BODY_ABC, 0),
        (SplitType.FULL_BODY_FOUR, 0),
        (SplitType.UPPER_LOWER_FULL, 0),
        (SplitType.UPPER_LOWER, 0),
        (SplitType.UPPER_LOWER_SPECIALIZATION, 0),
        (SplitType.UPPER_LOWER_X3, 0),
        (SplitType.PHUL, 0),
        (SplitType.PUSH_PULL_LEGS_UPPER_LOWER, 30),
        (SplitType.PUSH_PULL_LEGS, 40),
        (SplitType.PUSH_PULL_LEGS_X2, 40),
        (SplitType.BODY_PART_ROTATION, 50),
    ],
)
def test_professional_topology_has_single_dynamic_split_tier(
    split_type: SplitType, expected: int
) -> None:
    assert _score(_normalized(), split_type) == expected


def test_specialization_matching_explicit_priority_is_a_single_sixty_point_tier() -> None:
    normalized = _normalized(priority_muscles=[MuscleGroup.BICEPS])

    assert (
        _score(
            normalized,
            SplitType.BODY_PART_ROTATION,
            template_tags=frozenset(
                {
                    TemplateFocusTag.BODY_PART_ROTATION,
                    TemplateFocusTag.ARMS_PRIORITY,
                    TemplateFocusTag.SPECIALIZATION,
                }
            ),
        )
        == 60
    )


def test_non_matching_specialization_keeps_body_part_base_tier() -> None:
    normalized = _normalized(priority_muscles=[MuscleGroup.QUADRICEPS])

    assert (
        _score(
            normalized,
            SplitType.BODY_PART_ROTATION,
            template_tags=frozenset(
                {
                    TemplateFocusTag.BODY_PART_ROTATION,
                    TemplateFocusTag.ARMS_PRIORITY,
                    TemplateFocusTag.SPECIALIZATION,
                }
            ),
        )
        == 50
    )


def test_matching_specialization_tag_does_not_promote_generic_upper_lower() -> None:
    normalized = _normalized(priority_muscles=[MuscleGroup.BICEPS])

    assert (
        _score(
            normalized,
            SplitType.UPPER_LOWER,
            template_tags=frozenset(
                {
                    TemplateFocusTag.UPPER_LOWER,
                    TemplateFocusTag.ARMS_PRIORITY,
                    TemplateFocusTag.SPECIALIZATION,
                }
            ),
        )
        == 0
    )


def test_specialization_matches_eligible_body_analysis_priority() -> None:
    influence = BodyAnalysisInfluence.model_validate(
        {
            "analysis_id": uuid4(),
            "result_version_id": uuid4(),
            "analysis_revision": 1,
            "schema_version": "1.0",
            "source": "fully_reviewed",
            "overall_confidence": 0.9,
            "priorities": [
                {
                    "muscle": MuscleGroup.GLUTES,
                    "classification": "clear_lag",
                    "confidence": 0.9,
                    "severity": 0.8,
                }
            ],
        }
    )
    normalized = _normalized(body_analysis_influence=influence)

    assert (
        _score(
            normalized,
            SplitType.BODY_PART_ROTATION,
            template_tags=frozenset(
                {
                    TemplateFocusTag.BODY_PART_ROTATION,
                    TemplateFocusTag.GLUTE_PRIORITY,
                    TemplateFocusTag.SPECIALIZATION,
                }
            ),
        )
        == 60
    )


def test_template_tags_force_semantic_primary_structure_and_prevent_body_part_fallback() -> None:
    normalized = _normalized()

    assert (
        _score(
            normalized,
            SplitType.BODY_PART_ROTATION,
            template_tags=frozenset(),
        )
        == 0
    )


def test_template_tags_classify_only_primary_structure_not_slug_or_name() -> None:
    normalized = _normalized()

    assert (
        _score(
            normalized,
            SplitType.BODY_PART_ROTATION,
            template_tags=frozenset({TemplateFocusTag.UPPER_LOWER}),
        )
        == 0
    )


def test_recent_consistency_downgrade_disables_professional_topology() -> None:
    normalized = _normalized(
        training_experience=TrainingExperience.ADVANCED,
        training_age_months=72,
        recent_training_history=INTERMEDIATE_HISTORY.model_copy(update={"consistent_weeks": 2}),
    )

    assert normalized.training_status is TrainingStatus.EARLY_INTERMEDIATE
    assert _score(normalized, SplitType.BODY_PART_ROTATION) == 0


def test_advanced_normalized_request_receives_professional_topology() -> None:
    normalized = _normalized(
        training_experience=TrainingExperience.ADVANCED,
        training_age_months=72,
        recent_training_history=ADVANCED_HISTORY,
        available_training_days=6,
    )

    assert normalized.training_status is TrainingStatus.ADVANCED
    assert _score(normalized, SplitType.PUSH_PULL_LEGS_X2) == 40
