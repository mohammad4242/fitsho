from decimal import Decimal
from uuid import UUID

from app.nutrition.enums import NutritionDietStyle
from app.nutrition.models import NutritionProgram
from app.nutrition.nutrition_request import NormalizedNutritionRequest
from app.nutrition.program_selection import (
    ProgramSelectionContext,
    enumerate_program_candidates,
    select_program,
    select_program_candidates,
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


def test_select_program_candidates_records_trace_and_rejects_inactive() -> None:
    from decimal import Decimal

    from app.nutrition.nutrition_request import NormalizedNutritionRequest
    from app.nutrition.program_selection import select_program_candidates

    programs = _programs()
    programs[0].is_active = False  # ECO01

    req = NormalizedNutritionRequest(
        user_id="test-user",
        fitness_goal="maintain_weight",
        body_weight_kg=Decimal("70.0"),
        protein_calculation_weight_kg=Decimal("70.0"),
        tdee_kcal=Decimal("2000.0"),
        monthly_budget_irr=150_000_000,
        weekly_budget_irr=34_615_384,
        budget_style="flexible",
        trains=False,
        exercise_type=None,
        training_days_per_week=None,
        training_minutes_per_session=None,
        training_intensity=None,
        training_experience=None,
        main_meal_slots=3,
        snack_slots=1,
        dietary_pattern="omnivore",
        maximum_meal_repetition_per_week=2,
        preferred_variety="medium",
        requested_weight_change_kg_per_week=None,
        plan_style="balanced",
    )

    result = select_program_candidates(programs, req)
    assert result.programs_considered == len(programs)
    assert len(result.hard_rejections) == 1
    assert result.hard_rejections[0].program_code == "ECO01"
    assert "PROGRAM_INACTIVE" in result.hard_rejections[0].reason_codes
    assert len(result.candidates) == len(programs) - 1

    trace1 = result.decision_trace()
    result2 = select_program_candidates(list(reversed(programs)), req)
    trace2 = result2.decision_trace()

    assert trace1 == trace2
    assert trace1["policy_version"] == "nutrition-program-selection-v3"
    assert trace1["programs_considered"] == len(programs)
    assert len(trace1["hard_rejections"]) == 1
    assert len(trace1["candidates"]) == len(programs) - 1


def test_select_program_candidates_ranks_by_budget_feasibility() -> None:
    from app.nutrition.enums import NutritionBudgetTier
    from app.nutrition.program_costing import ProgramCostEstimate

    programs = _programs()
    for prog in programs:
        if prog.code.startswith("ECO"):
            prog.budget_tier_hint = NutritionBudgetTier.ECONOMY
        elif prog.code.startswith("PREM"):
            prog.budget_tier_hint = NutritionBudgetTier.VARIED
        else:
            prog.budget_tier_hint = NutritionBudgetTier.NORMAL

    # User with economy budget (90M IRR = 9M Toman)
    req = NormalizedNutritionRequest(
        user_id="u1",
        fitness_goal="lose_weight",
        body_weight_kg=Decimal("70.0"),
        protein_calculation_weight_kg=Decimal("70.0"),
        tdee_kcal=Decimal("2000.0"),
        monthly_budget_irr=90_000_000,
        weekly_budget_irr=20_769_230,
        budget_style="strict",
        trains=False,
        exercise_type=None,
        training_days_per_week=None,
        training_minutes_per_session=None,
        training_intensity=None,
        training_experience=None,
        main_meal_slots=3,
        snack_slots=1,
        dietary_pattern="omnivore",
        maximum_meal_repetition_per_week=2,
        preferred_variety="medium",
        requested_weight_change_kg_per_week=None,
        plan_style="economical",
    )

    cost_estimates = {
        prog.code: ProgramCostEstimate(
            program_code=prog.code,
            estimated_monthly_cost_irr=(
                Decimal("88000000") if prog.code.startswith("ECO") else Decimal("180000000")
            ),
            minimum_adapted_monthly_cost_irr=(
                Decimal("80000000") if prog.code.startswith("ECO") else Decimal("150000000")
            ),
            effective_budget_tier="economy" if prog.code.startswith("ECO") else "varied",
            price_coverage_complete=True,
            estimate_confidence="high",
            reason_codes=(),
        )
        for prog in programs
    }

    result = select_program_candidates(programs, req, cost_estimates=cost_estimates)

    # Top 5 candidates should be economy programs!
    top_5_codes = [c.program.code for c in result.candidates[:5]]
    assert all(code.startswith("ECO") for code in top_5_codes)

    trace = result.decision_trace(programs_constructed=5, fallback_batches_used=0)
    assert trace["programs_considered"] == 25
    assert trace["programs_hard_rejected"] >= 0
    assert trace["programs_constructed"] == 5
    assert trace["fallback_batches_used"] == 0
    assert "program_cost_estimates" in trace
    assert len(trace["program_cost_estimates"]) == 25
