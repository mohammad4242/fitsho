from pathlib import Path

APP_ROOT = Path(__file__).parents[1] / "app"


def test_agent_service_contains_no_fitsho_production_task_prompts() -> None:
    source = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted(APP_ROOT.rglob("*.py"))
    )
    forbidden_markers = (
        "_ANALYSIS_PROMPT",
        "_PHOTO_PREFLIGHT_PROMPT",
        "AGENT_BODY_ANALYSIS_PROMPT",
        "CODEX_WORKOUT_PROMPT",
        "CLAUDE_FOOD_PROMPT",
        "ANTIGRAVITY_BODY_PROMPT",
        "fitsho_ai_coach_recommendation",
        "fitsho_food_photo_estimate_v1",
        "fitsho_physique_assessment_v3",
        "Identify only visible foods and estimate portions.",
        "You are Fitsho AI Coach.",
    )

    assert not [marker for marker in forbidden_markers if marker in source]
