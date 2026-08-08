def test_task6_uses_separate_generation_and_revision_tables() -> None:
    from app.nutrition.models import (
        NutritionPlanGeneration,
        NutritionPlanPhysicianReview,
        NutritionWeeklyPlan,
        NutritionWeeklyPlanDay,
        NutritionWeeklyPlanFood,
        NutritionWeeklyPlanMeal,
        NutritionWeeklyPlanNutrient,
    )

    assert NutritionPlanGeneration.__tablename__ == "nutrition_plan_generations"
    assert NutritionWeeklyPlan.__tablename__ == "nutrition_weekly_plans"
    assert NutritionWeeklyPlanDay.__tablename__ == "nutrition_weekly_plan_days"
    assert NutritionWeeklyPlanMeal.__tablename__ == "nutrition_weekly_plan_meals"
    assert NutritionWeeklyPlanFood.__tablename__ == "nutrition_weekly_plan_foods"
    assert NutritionWeeklyPlanNutrient.__tablename__ == "nutrition_weekly_plan_nutrients"
    assert NutritionPlanPhysicianReview.__tablename__ == "nutrition_plan_physician_reviews"


def test_task6_lifecycle_and_generation_outcomes_are_not_the_same_enum() -> None:
    from app.nutrition.enums import NutritionPlanGenerationOutcome, NutritionPlanLifecycleStatus

    assert {member.value for member in NutritionPlanGenerationOutcome} == {
        "success",
        "failed",
        "safety_blocked",
        "infeasible",
        "target_infeasible",
        "live_price_unavailable",
    }
    assert "active" in {member.value for member in NutritionPlanLifecycleStatus}
    assert "active" not in {member.value for member in NutritionPlanGenerationOutcome}
    assert "pending_physician_review" in {member.value for member in NutritionPlanLifecycleStatus}
