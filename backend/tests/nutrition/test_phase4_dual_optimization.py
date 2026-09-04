from datetime import date, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.models import User
from app.nutrition.candidate_selection import (
    CandidateQuality,
)
from app.nutrition.enums import (
    NutritionOptimizationMode,
    NutritionPlanLifecycleStatus,
    NutritionPlanReviewStatus,
    NutritionPlanRole,
)
from app.nutrition.models import (
    NutritionEstimate,
    NutritionPlanBundle,
    NutritionPlanGeneration,
    NutritionPlanPhysicianReview,
    NutritionSafetyDecision,
    NutritionWeeklyPlan,
)
from app.nutrition.plan_comparison import (
    compare_plans,
)
from app.nutrition.plan_editing import (
    PlanEditError,
    _assert_editable,
)
from app.nutrition.plan_service import (
    active_weekly_plan,
    latest_weekly_plan,
    weekly_plan_history,
)
from app.nutrition.planner_engine import (
    GenerationOutcome,
    NutrientComparison,
    PlannedDay,
    PlannedFood,
    PlannedMeal,
    PlannerInput,
    PlannerResult,
    _warning_codes,
)
from app.nutrition.planner_policy import PLANNER_POLICY_VERSION, PLANNER_VERSION
from tests.nutrition.test_weekly_plan_api import _register_and_estimate


def _make_dummy_result(
    *,
    outcome: GenerationOutcome = GenerationOutcome.SUCCESS,
    weekly_cost_irr: int = 700_000,
    daily_calories: Decimal = Decimal("2000"),
    daily_protein: Decimal = Decimal("140"),
    budget_status: str = "within_budget",
) -> PlannerResult:
    foods = (
        PlannedFood(
            food_id="food-1",
            slug="chicken",
            name_fa="مرغ",
            name_en="Chicken",
            roles=("main",),
            grams=Decimal("100"),
            cost_irr=Decimal(weekly_cost_irr) / Decimal("7"),
            nutrients=(
                ("energy_kcal", daily_calories),
                ("protein_g", daily_protein),
            ),
            price_reference_id="ref-1",
            min_grams=Decimal("10"),
            max_grams=Decimal("500"),
            functional_role="protein",
        ),
    )
    meals = (
        PlannedMeal(
            role="main_meal",
            slot_index=0,
            template_id="template-1",
            template_category="lunch",
            foods=foods,
            cost_irr=Decimal(weekly_cost_irr) / Decimal("7"),
            nutrients=(
                ("energy_kcal", daily_calories),
                ("protein_g", daily_protein),
            ),
        ),
    )
    days = tuple(
        PlannedDay(
            day_index=i,
            meals=meals,
            cost_irr=Decimal(weekly_cost_irr) / Decimal("7"),
            nutrients=(
                ("energy_kcal", daily_calories),
                ("protein_g", daily_protein),
            ),
        )
        for i in range(7)
    )
    return PlannerResult(
        outcome=outcome,
        reason_codes=("SAFE_FEASIBLE_DRAFT_GENERATED",),
        days=days,
        weekly_cost_irr=Decimal(weekly_cost_irr),
        budget_status=budget_status,
        nutrient_comparisons={
            "goal_calories": NutrientComparison(
                preferred=daily_calories,
                minimum_or_maximum=None,
                planned=daily_calories,
                difference_from_preferred=Decimal("0"),
                difference_from_limit=None,
                status="within_target",
            ),
            "protein": NutrientComparison(
                preferred=Decimal("160"),
                minimum_or_maximum=Decimal("120"),
                planned=daily_protein,
                difference_from_preferred=daily_protein - Decimal("160"),
                difference_from_limit=daily_protein - Decimal("120"),
                status="within_target"
                if daily_protein >= Decimal("160")
                else "below_reference_target",
            ),
        },
    )


def test_budget_and_ideal_use_identical_scientific_targets():
    target = {"goal_calories": Decimal("2200"), "protein": Decimal("165")}
    budget_input = PlannerInput(
        daily_targets=target,
        micronutrient_targets={},
        micronutrient_upper_limits={},
        daily_minimums={},
        daily_maximums={},
        main_meals_per_day=3,
        snacks_per_day=1,
        weekly_budget_irr=10_000_000,
        budget_mode="strict",
        optimization_mode=NutritionOptimizationMode.BUDGET_CONSTRAINED,
    )
    ideal_input = PlannerInput(
        daily_targets=target,
        micronutrient_targets={},
        micronutrient_upper_limits={},
        daily_minimums={},
        daily_maximums={},
        main_meals_per_day=3,
        snacks_per_day=1,
        weekly_budget_irr=None,
        budget_mode=None,
        optimization_mode=NutritionOptimizationMode.IDEAL_REFERENCE,
    )

    assert budget_input.daily_targets == ideal_input.daily_targets
    assert budget_input.optimization_mode == NutritionOptimizationMode.BUDGET_CONSTRAINED
    assert ideal_input.optimization_mode == NutritionOptimizationMode.IDEAL_REFERENCE
    assert ideal_input.weekly_budget_irr is None


def test_strict_budget_plan_validation():
    with pytest.raises(ValueError, match="weekly_budget_irr is required"):
        PlannerInput(
            daily_targets={"protein": Decimal("100")},
            micronutrient_targets={},
            micronutrient_upper_limits={},
            daily_minimums={},
            daily_maximums={},
            main_meals_per_day=3,
            snacks_per_day=1,
            weekly_budget_irr=None,
            budget_mode="strict",
            optimization_mode=NutritionOptimizationMode.BUDGET_CONSTRAINED,
        )


def test_ideal_does_not_win_because_it_costs_more():
    quality_cheaper = CandidateQuality(
        core_nutrition_max_deviation=Decimal("0.05"),
        core_nutrition_total_deviation=Decimal("0.10"),
        micronutrient_gap_penalty=Decimal("0"),
        diet_quality_penalty=Decimal("0"),
        sports_nutrition_distribution_penalty=Decimal("0"),
        budget_utilization_penalty=Decimal("0.5"),
        preference_and_feedback_penalty=Decimal("0"),
        repetition_penalty=Decimal("0"),
        warning_burden=0,
        repair_burden=0,
        substitution_burden=0,
        preferred_program_style_penalty=0,
        cost_irr=Decimal("1000000"),
        stable_program_code="PROG-A",
        stable_variant_key=("base",),
    )
    quality_expensive = CandidateQuality(
        core_nutrition_max_deviation=Decimal("0.05"),
        core_nutrition_total_deviation=Decimal("0.10"),
        micronutrient_gap_penalty=Decimal("0"),
        diet_quality_penalty=Decimal("0"),
        sports_nutrition_distribution_penalty=Decimal("0"),
        budget_utilization_penalty=Decimal("0.1"),
        preference_and_feedback_penalty=Decimal("0"),
        repetition_penalty=Decimal("0"),
        warning_burden=0,
        repair_burden=0,
        substitution_burden=0,
        preferred_program_style_penalty=0,
        cost_irr=Decimal("3000000"),
        stable_program_code="PROG-B",
        stable_variant_key=("base",),
    )

    key_cheaper = quality_cheaper.sort_key(NutritionOptimizationMode.IDEAL_REFERENCE)
    key_expensive = quality_expensive.sort_key(NutritionOptimizationMode.IDEAL_REFERENCE)

    assert key_cheaper < key_expensive, "In ideal mode, lower cost should win as late tie-breaker"


def test_preferred_protein_miss_warning_above_hard_minimum():
    inputs = PlannerInput(
        daily_targets={"protein": Decimal("165")},
        micronutrient_targets={},
        micronutrient_upper_limits={},
        daily_minimums={"protein": Decimal("130")},
        daily_maximums={},
        main_meals_per_day=3,
        snacks_per_day=1,
        weekly_budget_irr=10_000_000,
        budget_mode="strict",
    )
    daily_avg = {"protein": Decimal("145")}
    warnings = _warning_codes(
        inputs,
        daily_avg,
        budget_status="within_budget",
        data_completeness={"protein": Decimal("1.0")},
        days=(),
    )
    assert "BUDGET_PLAN_BELOW_PREFERRED_PROTEIN" in warnings


def test_budget_insufficient_exact_minimum_only_when_established():
    report_established = compare_plans(
        user_monthly_budget_irr=50_000_000,
        budget_plan_result=None,
        ideal_plan_result=_make_dummy_result(weekly_cost_irr=14_000_000),
        minimum_feasible_monthly_cost_irr=60_000_000,
    )
    assert report_established.minimum_feasible_monthly_cost_irr == 60_000_000

    report_not_established = compare_plans(
        user_monthly_budget_irr=50_000_000,
        budget_plan_result=None,
        ideal_plan_result=_make_dummy_result(weekly_cost_irr=14_000_000),
        minimum_feasible_monthly_cost_irr=None,
    )
    assert report_not_established.minimum_feasible_monthly_cost_irr is None


def test_ideal_is_never_returned_as_active_or_latest_diet(client: TestClient, db: Session):
    email = "phase4-dual@example.com"
    _register_and_estimate(client, email, meals=3, snacks=1)
    user = db.scalar(select(User).where(User.email == email))
    assert user is not None
    user_id = user.id

    safety = db.scalar(
        select(NutritionSafetyDecision)
        .where(NutritionSafetyDecision.user_id == user_id)
        .order_by(NutritionSafetyDecision.revision.desc())
    )
    assert safety is not None

    estimate = db.scalar(
        select(NutritionEstimate)
        .where(NutritionEstimate.user_id == user_id)
        .order_by(NutritionEstimate.revision.desc())
    )
    assert estimate is not None

    bundle = NutritionPlanBundle(
        user_id=user_id,
        estimate_id=estimate.id,
        comparison_snapshot={},
    )
    db.add(bundle)
    db.flush()

    # Budget generation & active weekly plan (revision 1)
    budget_gen = NutritionPlanGeneration(
        user_id=user_id,
        safety_decision_id=safety.id,
        estimate_id=estimate.id,
        bundle_id=bundle.id,
        plan_role=NutritionPlanRole.BUDGET.value,
        outcome="success",
        reason_codes=[],
        warning_codes=[],
        input_signature="sig-budget",
        input_snapshot={},
        diagnostic_snapshot={},
        planner_policy_version=PLANNER_POLICY_VERSION,
        planner_version=PLANNER_VERSION,
    )
    db.add(budget_gen)
    db.flush()

    budget_plan = NutritionWeeklyPlan(
        user_id=user_id,
        generation_id=budget_gen.id,
        estimate_id=estimate.id,
        safety_decision_id=safety.id,
        revision=1,
        lifecycle_status=NutritionPlanLifecycleStatus.ACTIVE,
        is_user_visible=True,
        start_date=date.today() - timedelta(days=2),
        planner_policy_version=PLANNER_POLICY_VERSION,
        planner_version=PLANNER_VERSION,
        scientific_policy_version="sc-v1",
        formula_version="fm-v1",
        food_data_manifest={},
        input_snapshot={},
        price_snapshot={},
        repair_snapshot=[],
        warning_codes=[],
        explanation_codes=[],
        weekly_cost_irr=10_000_000,
        weekly_budget_irr=11_000_000,
        budget_status="within_budget",
        review=NutritionPlanPhysicianReview(
            status=NutritionPlanReviewStatus.APPROVED,
            expected_plan_revision=1,
        ),
    )
    db.add(budget_plan)

    # Ideal generation & reference weekly plan (revision 2) - newer revision!
    ideal_gen = NutritionPlanGeneration(
        user_id=user_id,
        safety_decision_id=safety.id,
        estimate_id=estimate.id,
        bundle_id=bundle.id,
        plan_role=NutritionPlanRole.IDEAL_REFERENCE.value,
        outcome="success",
        reason_codes=[],
        warning_codes=[],
        input_signature="sig-ideal",
        input_snapshot={},
        diagnostic_snapshot={},
        planner_policy_version=PLANNER_POLICY_VERSION,
        planner_version=PLANNER_VERSION,
    )
    db.add(ideal_gen)
    db.flush()

    ideal_plan = NutritionWeeklyPlan(
        user_id=user_id,
        generation_id=ideal_gen.id,
        estimate_id=estimate.id,
        safety_decision_id=safety.id,
        revision=2,
        lifecycle_status=NutritionPlanLifecycleStatus.GENERATED,
        is_user_visible=True,
        start_date=date.today() - timedelta(days=1),
        planner_policy_version=PLANNER_POLICY_VERSION,
        planner_version=PLANNER_VERSION,
        scientific_policy_version="sc-v1",
        formula_version="fm-v1",
        food_data_manifest={},
        input_snapshot={},
        price_snapshot={},
        repair_snapshot=[],
        warning_codes=[],
        explanation_codes=[],
        weekly_cost_irr=20_000_000,
        weekly_budget_irr=11_000_000,
        budget_status="over_budget",
        review=None,
    )
    db.add(ideal_plan)
    db.commit()

    # Verify latest_weekly_plan returns budget_plan (revision 1), NOT ideal_plan (revision 2)
    latest = latest_weekly_plan(db, user_id)
    assert latest.id == budget_plan.id
    assert latest.revision == 1

    # Verify active_weekly_plan returns budget_plan (revision 1)
    active = active_weekly_plan(db, user_id)
    assert active.id == budget_plan.id
    assert active.revision == 1

    # Verify weekly_plan_history excludes ideal_plan
    history = weekly_plan_history(db, user_id)
    history_ids = [item.id for item in history]
    assert budget_plan.id in history_ids
    assert ideal_plan.id not in history_ids


def test_plan_editing_rejects_ideal_reference_plan():
    plan_id = uuid4()
    ideal_gen = NutritionPlanGeneration(
        user_id=uuid4(),
        safety_decision_id=uuid4(),
        plan_role=NutritionPlanRole.IDEAL_REFERENCE.value,
        outcome="success",
        reason_codes=[],
        warning_codes=[],
        input_signature="sig",
        input_snapshot={},
        diagnostic_snapshot={},
        planner_policy_version="p1",
        planner_version="v1",
    )
    ideal_plan = NutritionWeeklyPlan(
        id=plan_id,
        revision=1,
        lifecycle_status=NutritionPlanLifecycleStatus.GENERATED,
    )
    ideal_plan.generation = ideal_gen

    with pytest.raises(PlanEditError) as exc_info:
        _assert_editable(ideal_plan, plan_id)
    assert exc_info.value.code == "IDEAL_REFERENCE_PLAN_CANNOT_BE_EDITED"
