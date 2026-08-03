from uuid import uuid4

from app.exercises.enums import ExerciseCautionTag, MuscleGroup
from app.workouts.program_engine.eligibility import filter_eligible_exercises
from app.workouts.program_engine.engine import generate_program
from app.workouts.program_engine.exercise_ranker import rank_exercises
from app.workouts.program_engine.normalization import normalize_request
from app.workouts.program_engine.rulesets.resistance_training_v1 import RULESET
from app.workouts.program_engine.schemas import (
    BodyAnalysisInfluence,
    ProgramGenerationRequest,
    TemplateReference,
)
from app.workouts.program_engine.split_selector import select_split
from app.workouts.program_engine.template_selector import select_template_reference
from app.workouts.program_engine.volume_planner import plan_weekly_volume
from workouts.program_engine.golden_fixtures import full_catalog, request


def influence(
    muscle: MuscleGroup,
    *,
    classification: str = "clear_lag",
    confidence: float = 0.9,
    source: str = "ai_provisional",
) -> BodyAnalysisInfluence:
    return BodyAnalysisInfluence.model_validate(
        {
            "analysis_id": uuid4(),
            "result_version_id": uuid4(),
            "analysis_revision": 1,
            "schema_version": "1.0",
            "source": source,
            "overall_confidence": 0.9,
            "priorities": [
                {
                    "muscle": muscle,
                    "classification": classification,
                    "confidence": confidence,
                    "severity": 0.8,
                    "emphasis": [muscle.value],
                }
            ],
        }
    )


def normalized_with(influence_value: BodyAnalysisInfluence):
    source = request(
        primary_goal="build_muscle",
        training_experience="intermediate",
        training_age_months=24,
        available_training_days=4,
        session_duration_minutes=60,
        body_analysis_influence=influence_value,
    )
    return normalize_request(source, RULESET)


def test_high_confidence_lag_boosts_only_eligible_exercises() -> None:
    normalized = normalized_with(influence(MuscleGroup.SHOULDERS))
    catalog = full_catalog()
    eligibility = filter_eligible_exercises(normalized, catalog)

    ranked = rank_exercises(normalized, eligibility.eligible, RULESET)
    shoulder = next(
        item for item in ranked if item.exercise.primary_muscle is MuscleGroup.SHOULDERS
    )

    assert "BODY_ANALYSIS_CLEAR_LAG" in shoulder.reason_codes
    assert shoulder.exercise.id in {item.id for item in eligibility.eligible}


def test_safety_exclusion_cannot_be_reversed_by_body_priority() -> None:
    source = request(
        primary_goal="build_muscle",
        training_experience="intermediate",
        training_age_months=24,
        available_training_days=4,
        session_duration_minutes=60,
        blocked_caution_tags=[ExerciseCautionTag.OVERHEAD_POSITION],
        body_analysis_influence=influence(MuscleGroup.SHOULDERS),
    )
    normalized = normalize_request(source, RULESET)

    eligibility = filter_eligible_exercises(normalized, full_catalog())

    assert all(
        ExerciseCautionTag.OVERHEAD_POSITION not in item.caution_tags
        for item in eligibility.eligible
    )
    assert any(
        "EXERCISE_REJECTED_BLOCKED_CAUTION_TAG" in item.reason_codes
        for item in eligibility.rejected
    )


def test_low_confidence_body_priority_does_not_change_volume() -> None:
    low_confidence = normalized_with(influence(MuscleGroup.SHOULDERS, confidence=0.4))
    baseline_source: ProgramGenerationRequest = low_confidence.source.model_copy(
        update={"body_analysis_influence": None}
    )
    baseline = normalize_request(baseline_source, RULESET)

    low_plan = plan_weekly_volume(low_confidence, select_split(low_confidence, RULESET), RULESET)
    baseline_plan = plan_weekly_volume(baseline, select_split(baseline, RULESET), RULESET)

    assert low_plan.direct_sets_for(MuscleGroup.SHOULDERS) == baseline_plan.direct_sets_for(
        MuscleGroup.SHOULDERS
    )
    assert "VOLUME_INCREASED_FOR_BODY_ANALYSIS" not in low_plan.reason_codes


def test_clear_lag_volume_boost_stays_inside_hard_ruleset_limit() -> None:
    source = request(
        primary_goal="build_muscle",
        training_experience="intermediate",
        training_age_months=24,
        available_training_days=5,
        session_duration_minutes=60,
        body_analysis_influence=influence(MuscleGroup.SHOULDERS),
    )
    normalized = normalize_request(source, RULESET)
    baseline = normalize_request(
        source.model_copy(update={"body_analysis_influence": None}), RULESET
    )

    plan = plan_weekly_volume(normalized, select_split(normalized, RULESET), RULESET)
    baseline_plan = plan_weekly_volume(baseline, select_split(baseline, RULESET), RULESET)
    target = next(item for item in plan.targets if item.muscle is MuscleGroup.SHOULDERS)

    assert target.target_sets > baseline_plan.direct_sets_for(MuscleGroup.SHOULDERS)
    assert target.target_sets <= target.maximum_hard
    assert target.maximum_hard == RULESET.maximum_sets[normalized.training_status]
    assert "VOLUME_INCREASED_FOR_BODY_ANALYSIS" in plan.reason_codes


def test_reference_template_path_scores_body_analysis_emphasis_tags() -> None:
    normalized = normalized_with(influence(MuscleGroup.SHOULDERS))
    templates = (
        TemplateReference(
            slug="z-classic",
            days_per_week=4,
            training_level="intermediate",
            fitness_goal="build_muscle",
            focus_tags=("classic",),
            intensity_methods=("standard",),
            days=(),
        ),
        TemplateReference(
            slug="a-shoulders",
            days_per_week=4,
            training_level="intermediate",
            fitness_goal="build_muscle",
            focus_tags=("shoulders_priority",),
            intensity_methods=("standard",),
            days=(),
        ),
    )

    selected = select_template_reference(normalized, tuple(full_catalog()), templates, RULESET)

    assert selected is not None
    assert selected.slug == "a-shoulders"


def test_program_trace_preserves_provisional_analysis_version() -> None:
    body_influence = influence(MuscleGroup.CHEST, source="ai_provisional")

    result = generate_program(
        request(
            primary_goal="build_muscle",
            body_analysis_influence=body_influence,
            session_duration_minutes=60,
        ),
        full_catalog(),
        RULESET,
    )

    assert result.program is not None, result.errors
    assert result.program.body_analysis_provenance == {
        "analysis_id": str(body_influence.analysis_id),
        "result_version_id": str(body_influence.result_version_id),
        "analysis_revision": 1,
        "schema_version": "1.0",
        "source": "ai_provisional",
        "provisional": True,
        "mapping_version": "body_analysis_training_map_v1",
    }
    assert any(
        item["stage"] == "body_analysis_influence"
        and item["source"] == "ai_provisional"
        and item["applied_muscles"] == ["chest"]
        for item in result.program.decision_trace
    )
    assert "BODY_ANALYSIS_NOT_FULLY_REVIEWED" in result.program.warnings
