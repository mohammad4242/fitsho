from uuid import uuid4

from app.body_analysis.enums import BodyAnalysisResultSource
from app.body_analysis.schemas import NormalizedBodyAnalysis
from app.body_analysis.service import EffectiveBodyAnalysisResult
from app.exercises.enums import MuscleGroup
from app.workouts.body_analysis_resolver import to_body_analysis_influence


def normalized_result() -> NormalizedBodyAnalysis:
    return NormalizedBodyAnalysis.model_validate(
        {
            "schema_version": "1.0",
            "overall_confidence": 0.88,
            "findings": [
                {
                    "body_area": "shoulders",
                    "classification": "clear_lag",
                    "severity": 0.8,
                    "confidence": 0.9,
                    "supporting_views": ["front", "back"],
                    "explanation": "Visibly less developed relative to nearby areas.",
                    "limitations": [],
                    "suggested_training_emphasis": [
                        "lateral_deltoid",
                        "rear_deltoid",
                    ],
                    "medical_review_recommended": False,
                },
                {
                    "body_area": "hamstrings",
                    "classification": "uncertain",
                    "severity": None,
                    "confidence": 0.35,
                    "supporting_views": ["side"],
                    "explanation": "The area is not visible clearly enough.",
                    "limitations": ["clothing_occlusion"],
                    "suggested_training_emphasis": [],
                    "medical_review_recommended": False,
                },
            ],
            "summary": {
                "visible_strengths": [],
                "priority_areas": ["shoulders"],
                "moderate_attention_areas": [],
                "uncertain_areas": ["hamstrings"],
            },
            "requires_coach_review": True,
            "requires_doctor_review": True,
        }
    )


def effective(*, version: int = 1, coach: bool = False, doctor: bool = False):
    return EffectiveBodyAnalysisResult(
        analysis_id=uuid4(),
        result_version_id=uuid4(),
        version=version,
        normalized_result=normalized_result(),
        source=BodyAnalysisResultSource.AI,
        coach_approved=coach,
        doctor_approved=doctor,
    )


def test_maps_only_explicit_lag_emphasis_and_drops_uncertain_findings() -> None:
    result = effective()

    influence = to_body_analysis_influence(result, analysis_revision=2)

    assert influence.analysis_revision == 2
    assert influence.source == "ai_provisional"
    assert [item.muscle for item in influence.priorities] == [MuscleGroup.SHOULDERS]
    assert influence.priorities[0].emphasis == ("lateral_deltoid", "rear_deltoid")


def test_both_specialist_approvals_mark_exact_result_fully_reviewed() -> None:
    result = effective(coach=True, doctor=True)

    influence = to_body_analysis_influence(result, analysis_revision=1)

    assert influence.source == "fully_reviewed"
    assert influence.result_version_id == result.result_version_id
