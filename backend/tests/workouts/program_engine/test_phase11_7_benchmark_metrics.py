from types import SimpleNamespace

import tests.workouts.program_engine.phase11_benchmark as benchmark


def test_strict_whole_program_volume_fit_remains_all_or_nothing() -> None:
    assert (
        benchmark._strict_volume_fit(
            {
                "chest": {"status": "within_flexible_range"},
                "back": {"status": "constrained"},
            }
        )
        == "constrained"
    )
    assert (
        benchmark._strict_volume_fit(
            {
                "chest": {"status": "exact_target"},
                "back": {"status": "outside_acceptable_range"},
            }
        )
        == "failed"
    )


def test_muscle_level_volume_fit_counts_each_tracked_muscle() -> None:
    metric = benchmark._muscle_level_volume_fit(
        {
            "chest": {"status": "exact_target"},
            "back": {"status": "within_flexible_range"},
            "glutes": {"status": "constrained"},
            "abs": {"status": "outside_acceptable_range"},
        }
    )

    assert metric == {
        "tracked_muscles": 4,
        "within_target_or_flexible_range": 2,
        "constrained": 1,
        "outside_target": 1,
        "constrained_or_outside_target": 2,
        "percentage": 50.0,
    }


def test_aggregate_muscle_level_volume_fit_uses_successful_feasible_programs() -> None:
    records = (
        {
            "quality_audit": {
                "muscle_level_volume_fit": {
                    "tracked_muscles": 3,
                    "within_target_or_flexible_range": 2,
                    "constrained": 1,
                    "outside_target": 0,
                }
            }
        },
        {
            "quality_audit": {
                "muscle_level_volume_fit": {
                    "tracked_muscles": 1,
                    "within_target_or_flexible_range": 0,
                    "constrained": 0,
                    "outside_target": 1,
                }
            }
        },
        {"quality_audit": {}},
    )

    assert benchmark._aggregate_muscle_level_volume_fit(records) == {
        "programs": 2,
        "tracked_muscles": 4,
        "within_target_or_flexible_range": 2,
        "constrained": 1,
        "outside_target": 1,
        "constrained_or_outside_target": 2,
        "percentage": 50.0,
    }


def test_template_stats_report_recovered_template_and_attempt_depth() -> None:
    result = SimpleNamespace(
        program=SimpleNamespace(
            aggregate_metrics={"reference_template": "second-template"},
            decision_trace=(
                {
                    "stage": "template_selection",
                    "selected": "first-template",
                    "candidates": (
                        {"rank": 1, "slug": "first-template", "score": {"total": 100}},
                        {"rank": 2, "slug": "second-template", "score": {"total": 80}},
                    ),
                },
                {
                    "stage": "template_attempt",
                    "rank": 1,
                    "slug": "first-template",
                    "status": "rejected",
                    "rejection_category": "VALIDATION_FAILURE",
                    "reason_codes": ("RECOVERY_SPACING_INVALID",),
                },
                {
                    "stage": "template_attempt",
                    "rank": 2,
                    "slug": "second-template",
                    "status": "succeeded",
                    "rejection_category": None,
                    "reason_codes": ("TEMPLATE_ATTEMPT_SUCCEEDED",),
                },
            ),
        ),
        decision_trace=(),
        is_success=True,
    )

    stats = benchmark._template_stats(result)

    assert stats["selected_template"] == "first-template"
    assert stats["successful_template"] == "second-template"
    assert stats["attempt_depth"] == 2
    assert stats["successful_attempt_depth"] == 2
    assert stats["recovered_with_alternative"] is True
    assert stats["rejection_categories"] == ()
    assert stats["attempt_rejection_categories"] == ("VALIDATION_FAILURE",)


def test_template_attempt_metrics_include_zero_depth_and_exhaustion() -> None:
    metrics = benchmark._template_attempt_metrics(
        (
            {"attempted": False, "attempt_depth": 0},
            {
                "attempted": True,
                "attempt_depth": 1,
                "successful_attempt_depth": 1,
                "recovered_with_alternative": False,
                "alternatives_exhausted": False,
            },
            {
                "attempted": True,
                "attempt_depth": 3,
                "successful_attempt_depth": 3,
                "recovered_with_alternative": True,
                "alternatives_exhausted": False,
            },
            {
                "attempted": True,
                "attempt_depth": 2,
                "successful_attempt_depth": None,
                "recovered_with_alternative": False,
                "alternatives_exhausted": True,
            },
        )
    )

    assert metrics == {
        "total_template_attempts": 6,
        "attempt_depth_distribution": {"0": 1, "1": 1, "2": 1, "3": 1},
        "successful_attempt_depth_distribution": {"1": 1, "3": 1},
        "recovered_with_alternative": 1,
        "alternatives_exhausted": 1,
    }
