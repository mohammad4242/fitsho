from uuid import UUID

from app.nutrition.enums import NutritionDietStyle
from app.nutrition.models import NutritionProgram
from app.nutrition.program_selection import (
    ProgramSelectionContext,
    enumerate_program_candidates,
    select_program,
)


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


def _context() -> ProgramSelectionContext:
    return ProgramSelectionContext(
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


def test_selector_enumerates_all_active_programs_with_style_as_preference() -> None:
    programs = _programs()
    candidates = enumerate_program_candidates(programs, _context())

    assert len(candidates) == len(programs)
    assert [candidate.program.code for candidate in candidates[:5]] == [
        "IRN01",
        "IRN02",
        "IRN03",
        "IRN04",
        "IRN05",
    ]
    assert {candidate.program.code for candidate in candidates[5:]} == {
        program.code
        for program in programs
        if program.diet_style is not NutritionDietStyle.BALANCED_IRANIAN
    }
    assert all(candidate.preferred_style for candidate in candidates[:5])
    assert all(not candidate.preferred_style for candidate in candidates[5:])


def test_selector_excludes_only_explicitly_inactive_programs() -> None:
    programs = _programs()
    programs[-1].is_active = False

    candidates = enumerate_program_candidates(programs, _context())

    assert len(candidates) == len(programs) - 1
    assert "PREM05" not in {candidate.program.code for candidate in candidates}


def test_selector_order_is_deterministic_and_does_not_depend_on_user_id() -> None:
    programs = _programs()
    first = [
        candidate.program.code for candidate in enumerate_program_candidates(programs, _context())
    ]
    second = [
        candidate.program.code
        for candidate in enumerate_program_candidates(list(reversed(programs)), _context())
    ]

    assert first == second
    assert select_program(programs, _context(), UUID(int=1)).code == first[0]
    assert select_program(programs, _context(), UUID(int=2**128 - 1)).code == first[0]


def test_selector_style_inference_still_orders_the_preferred_group_first() -> None:
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

    assert select_program(_programs(), base, user_id).code == "IRN01"
    assert (
        select_program(
            _programs(), base._replace(plan_style="economical", budget_style="strict"), user_id
        ).code
        == "ECO01"
    )
    assert (
        select_program(
            _programs(),
            base._replace(plan_style="simple", maximum_cooking_time_minutes=15),
            user_id,
        ).code
        == "FAST01"
    )
    assert (
        select_program(_programs(), base._replace(preferred_variety="high"), user_id).code
        == "PREM01"
    )
    gym = base._replace(fitness_goal="build_muscle", trains=True, exercise_type="resistance")
    assert select_program(_programs(), gym, user_id).code == "GYM01"
    assert (
        select_program(_programs(), gym, user_id).code
        == select_program(list(reversed(_programs())), gym, user_id).code
    )
