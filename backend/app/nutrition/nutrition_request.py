"""Canonical normalized request for nutrition program selection and planning."""

from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID

from app.nutrition.enums import NutritionTargetMetric

if TYPE_CHECKING:
    from app.nutrition.models import (
        NutritionEstimate,
        NutritionProfile,
        NutritionStructuredExercise,
    )
    from app.profile.models import UserProfile


@dataclass(frozen=True)
class NormalizedNutritionRequest:
    user_id: str
    fitness_goal: str
    body_weight_kg: Decimal
    protein_calculation_weight_kg: Decimal
    tdee_kcal: Decimal
    monthly_budget_irr: int
    weekly_budget_irr: int
    budget_style: str
    trains: bool
    exercise_type: str | None
    training_days_per_week: int | None
    training_minutes_per_session: int | None
    training_intensity: str | None
    training_experience: str | None
    main_meal_slots: int
    snack_slots: int
    dietary_pattern: str
    maximum_meal_repetition_per_week: int
    preferred_variety: str
    requested_weight_change_kg_per_week: Decimal | None
    weight_rate_mode: str = "safe"
    plan_style: str | None = None
    cooking_skill: str | None = None
    maximum_cooking_time_minutes: int | None = None
    meal_preparation_preference: str | None = None


def build_normalized_nutrition_request(
    *,
    user_id: UUID,
    profile: "NutritionProfile",
    user_profile: "UserProfile",
    structured_exercise: "NutritionStructuredExercise | None",
    estimate: "NutritionEstimate",
) -> NormalizedNutritionRequest:
    """Construct a canonical normalized request from DB models."""
    raw_weight = estimate.input_snapshot.get("weight_kg", "70.0")
    try:
        body_weight_kg = Decimal(str(raw_weight))
    except Exception:
        body_weight_kg = Decimal("70.0")

    tdee_kcal = Decimal("2000.0")
    for target in estimate.targets:
        if target.metric == NutritionTargetMetric.TDEE:
            if target.preferred_value is not None:
                tdee_kcal = target.preferred_value
            elif target.preferred_maximum_value is not None:
                tdee_kcal = target.preferred_maximum_value
            break

    weekly_budget = profile.individual_monthly_food_budget_irr * 12 // 52

    return NormalizedNutritionRequest(
        user_id=str(user_id),
        fitness_goal=(
            user_profile.fitness_goal.value
            if user_profile.fitness_goal is not None
            else "maintain_weight"
        ),
        body_weight_kg=body_weight_kg,
        protein_calculation_weight_kg=body_weight_kg,
        tdee_kcal=tdee_kcal,
        monthly_budget_irr=profile.individual_monthly_food_budget_irr,
        weekly_budget_irr=weekly_budget,
        budget_style=profile.budget_style.value,
        trains=structured_exercise.trains if structured_exercise is not None else False,
        exercise_type=(
            structured_exercise.exercise_type.value
            if structured_exercise and structured_exercise.exercise_type
            else None
        ),
        training_days_per_week=structured_exercise.days_per_week if structured_exercise else None,
        training_minutes_per_session=(
            structured_exercise.minutes_per_session if structured_exercise else None
        ),
        training_intensity=(
            structured_exercise.intensity.value
            if structured_exercise and structured_exercise.intensity
            else None
        ),
        training_experience=(
            user_profile.experience_level.value
            if user_profile.experience_level is not None
            else None
        ),
        main_meal_slots=profile.effective_main_meal_slots,
        snack_slots=profile.effective_snack_slots,
        dietary_pattern=profile.dietary_pattern.value,
        maximum_meal_repetition_per_week=profile.maximum_meal_repetition_per_week,
        preferred_variety=profile.preferred_variety.value,
        requested_weight_change_kg_per_week=profile.target_weight_change_kg_per_week,
        weight_rate_mode=(
            profile.weight_rate_mode.value
            if hasattr(profile.weight_rate_mode, "value")
            else str(profile.weight_rate_mode)
        ),
        plan_style=profile.plan_style.value,
        cooking_skill=profile.cooking_skill.value,
        maximum_cooking_time_minutes=profile.maximum_cooking_time_minutes,
        meal_preparation_preference=profile.meal_preparation_preference.value,
    )
