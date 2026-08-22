from app.workout_reviews.template_selection import build_coach_template_selection


def _selection_trace(
    *,
    reason_codes: tuple[str, ...],
    score: dict[str, int],
) -> list[dict[str, object]]:
    return [
        {
            "stage": "template_selection",
            "requested_days": 4,
            "experience_level": "intermediate",
            "templates_considered": 3,
            "hard_rejections": (),
            "candidates": (
                {
                    "slug": "four-day-chest-priority",
                    "score": score,
                    "reason_codes": reason_codes,
                },
            ),
            "selected": "four-day-chest-priority",
            "tie_break": None,
        }
    ]


def test_coach_explanation_is_derived_from_selected_trace_signals() -> None:
    summary = build_coach_template_selection(
        _selection_trace(
            reason_codes=(
                "EXPLICIT_PRIORITY_EXACT_MATCH",
                "GOAL_STRENGTH_BIAS_MATCH",
            ),
            score={
                "priority": 100,
                "body_analysis": 0,
                "goal": 25,
                "sex": 0,
                "fallback": 0,
                "total": 125,
            },
        )
    )

    assert summary is not None
    assert summary.selected_template == "four-day-chest-priority"
    assert summary.score.total == 125
    assert "۴ روزه" in summary.explanation_fa
    assert "اولویت عضلانی صریح" in summary.explanation_fa
    assert "هدف قدرت" in summary.explanation_fa
    assert "شخصی‌سازی شدند" in summary.explanation_fa
    assert "explicit muscle priority" in summary.explanation_en
    assert "Body Analysis" not in summary.explanation_en


def test_sex_prior_uses_neutral_language_and_is_not_inferred_when_disabled() -> None:
    sex_summary = build_coach_template_selection(
        _selection_trace(
            reason_codes=("SEX_PRIOR_GLUTE_MATCH",),
            score={
                "priority": 0,
                "body_analysis": 0,
                "goal": 0,
                "sex": 20,
                "fallback": 0,
                "total": 20,
            },
        )
    )
    disabled_summary = build_coach_template_selection(
        _selection_trace(
            reason_codes=(
                "EXPLICIT_PRIORITY_EXACT_MATCH",
                "SEX_PRIOR_DISABLED_BY_EXPLICIT_PRIORITY",
            ),
            score={
                "priority": 100,
                "body_analysis": 0,
                "goal": 0,
                "sex": 0,
                "fallback": 0,
                "total": 100,
            },
        )
    )

    assert sex_summary is not None
    assert "ترجیح پیش‌فرض کوچک" in sex_summary.explanation_fa
    assert "female" not in sex_summary.explanation_en.lower()
    assert "زن" not in sex_summary.explanation_fa
    assert disabled_summary is not None
    assert "ترجیح پیش‌فرض" not in disabled_summary.explanation_fa


def test_missing_or_malformed_selected_trace_has_no_coach_summary() -> None:
    assert build_coach_template_selection([]) is None
    assert (
        build_coach_template_selection(
            [
                {
                    "stage": "template_selection",
                    "requested_days": 4,
                    "experience_level": "intermediate",
                    "candidates": (),
                    "selected": None,
                }
            ]
        )
        is None
    )
