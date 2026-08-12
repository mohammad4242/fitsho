from uuid import UUID

from app.nutrition.enums import NutritionDietStyle
from app.nutrition.models import NutritionProgram
from app.nutrition.program_selection import ProgramSelectionContext, select_program


def _programs() -> list[NutritionProgram]:
    return [
        NutritionProgram(
            code=f"{prefix}{index:02}",
            slug=f"{prefix.lower()}{index:02}",
            diet_style=style,
        )
        for prefix, style in (
            ("ECO", NutritionDietStyle.ECONOMY),
            ("IRN", NutritionDietStyle.BALANCED_IRANIAN),
            ("GYM", NutritionDietStyle.HIGH_PROTEIN_GYM),
            ("FAST", NutritionDietStyle.QUICK_EASY),
            ("PREM", NutritionDietStyle.PREMIUM_VARIED),
        )
        for index in range(1, 6)
    ]


def test_selector_uses_goal_budget_cooking_and_variety_deterministically() -> None:
    user_id = UUID("00000000-0000-0000-0000-000000000007")
    base = ProgramSelectionContext(
        fitness_goal="maintain_weight",
        trains=False,
        exercise_type=None,
        plan_style="balanced",
        budget_style="flexible",
        cooking_skill="basic",
        maximum_cooking_time_minutes=45,
        meal_preparation_preference="mixed",
        preferred_variety="medium",
    )

    assert select_program(_programs(), base, user_id).code == "IRN03"
    assert select_program(
        _programs(), base._replace(plan_style="economical", budget_style="strict"), user_id
    ).code.startswith("ECO")
    assert select_program(
        _programs(), base._replace(plan_style="simple", maximum_cooking_time_minutes=15), user_id
    ).code.startswith("FAST")
    assert select_program(
        _programs(), base._replace(preferred_variety="high"), user_id
    ).code.startswith("PREM")
    gym = base._replace(fitness_goal="build_muscle", trains=True, exercise_type="resistance")
    assert select_program(_programs(), gym, user_id).code.startswith("GYM")
    assert (
        select_program(_programs(), gym, user_id).code
        == select_program(list(reversed(_programs())), gym, user_id).code
    )
