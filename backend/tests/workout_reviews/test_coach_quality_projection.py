from app.workout_reviews.coach_quality import build_coach_quality_projection


def test_coach_quality_projection_accepts_only_well_formed_trace_metrics() -> None:
    metrics = {
        "template_preservation": {"satisfied": 3, "total": 4, "percentage": 75.0},
        "priority_target_satisfaction": {"satisfied": 8, "total": 10, "percentage": 80.0},
        "body_analysis_target_satisfaction": {
            "satisfied": 0,
            "total": 0,
            "percentage": None,
        },
        "volume_fit": {"satisfied": 10, "total": 12, "percentage": 83.3},
        "duration_fit": {"satisfied": 4, "total": 4, "percentage": 100.0},
        "recovery_fit": {"satisfied": 1, "total": 1, "percentage": 100.0},
        "substitution_count": 1,
        "constraint_count": 2,
        "hard_validation_status": "VALID_WITH_CONSTRAINTS",
        "schema_version": "coach_quality_v2",
        "selection_quality": {
            "coverage_state": "satisfied",
            "coverage_percentage": 100.0,
        },
    }

    projection = build_coach_quality_projection([{"stage": "coach_quality", "metrics": metrics}])

    assert projection is not None
    assert projection.template_preservation.percentage == 75.0
    assert projection.hard_validation_status == "VALID_WITH_CONSTRAINTS"


def test_coach_quality_projection_rejects_missing_or_malformed_trace() -> None:
    assert build_coach_quality_projection([]) is None
    assert (
        build_coach_quality_projection(
            [{"stage": "coach_quality", "metrics": {"overall_quality_score": 99}}]
        )
        is None
    )
