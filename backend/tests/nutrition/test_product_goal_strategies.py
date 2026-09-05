from decimal import Decimal

import pytest

from app.nutrition.scientific import (
    ScientificInputs,
    StructuredExercise,
    calculate_targets,
)


def _make_exercise(exercise_type: str = "resistance") -> StructuredExercise:
    return StructuredExercise(
        exercise_type=exercise_type,  # type: ignore[arg-type]
        days_per_week=4,
        minutes_per_session=60,
        met_value=Decimal("5.0"),
        met_baseline_kcal_per_kg_hour=Decimal("1.0"),
    )


def _make_inputs(
    goal: str,
    *,
    requested_rate: Decimal | None = None,
    exercise: StructuredExercise | None = None,
    weight_kg: Decimal = Decimal("75.0"),
    height_cm: Decimal = Decimal("175.0"),
) -> ScientificInputs:
    return ScientificInputs(
        age=28,
        height_cm=height_cm,
        weight_kg=weight_kg,
        metabolic_basis="male_coefficient",
        daily_activity_level="moderate",
        fitness_goal=goal,  # type: ignore[arg-type]
        structured_exercise=exercise,
        requested_weight_change_kg_per_week=requested_rate,
        training_experience="intermediate",
    )


@pytest.mark.parametrize(
    "goal",
    [
        "lose_weight",
        "fat_loss",
        "gain_weight",
        "build_muscle",
        "body_recomposition",
    ],
)
@pytest.mark.parametrize("has_rate", [False, True])
def test_all_five_goals_authoritative_strategy_with_and_without_rate(
    goal: str, has_rate: bool
) -> None:
    rate = Decimal("0.4") if has_rate and goal != "body_recomposition" else None
    inputs = _make_inputs(goal, requested_rate=rate, exercise=_make_exercise())
    result = calculate_targets(inputs)

    assert result.goal_strategy is not None
    assert result.goal_strategy.goal == goal
    # Targets must strictly match strategy targets, not legacy targets
    assert result.goal_calories == result.goal_strategy.goal_calories
    assert result.protein == result.goal_strategy.protein
    assert result.carbohydrate == result.goal_strategy.carbohydrate
    assert result.total_fat == result.goal_strategy.total_fat
    assert result.fibre == result.goal_strategy.fibre

    # Macros must be energy-consistent with calorie target
    assert result.goal_calories.preferred is not None
    cal = result.goal_calories.preferred
    p_kcal = (result.protein.preferred or Decimal("0")) * Decimal("4")
    c_kcal = (result.carbohydrate.preferred or Decimal("0")) * Decimal("4")
    f_kcal = (result.total_fat.preferred or Decimal("0")) * Decimal("9")
    total_macro_kcal = p_kcal + c_kcal + f_kcal
    # Must be within small rounding discrepancy tolerance (<= 35 kcal)
    assert abs(cal - total_macro_kcal) <= Decimal("35")


def test_body_recomposition_null_rate_never_legacy_fallback() -> None:
    inputs = _make_inputs("body_recomposition", requested_rate=None, exercise=_make_exercise())
    result = calculate_targets(inputs)

    assert result.goal_strategy is not None
    assert result.goal_strategy.goal == "body_recomposition"
    # Calories must be maintenance (TDEE preferred)
    assert result.goal_calories.preferred == result.tdee.preferred
    # Protein must be from recomp strategy
    assert result.protein == result.goal_strategy.protein
    # Rate must be None
    assert result.goal_strategy.target_weight_rate.applied_kg_per_week is None


def test_fat_loss_with_resistance_training_high_protein_priority() -> None:
    inputs = _make_inputs(
        "fat_loss", requested_rate=Decimal("0.5"), exercise=_make_exercise("resistance")
    )
    result = calculate_targets(inputs)

    assert result.goal_strategy is not None
    assert result.goal_strategy.goal == "fat_loss"
    assert result.goal_strategy.training_carbohydrate_priority == "high"
    # Resistance training fat_loss protein multiplier is 2.2 preferred
    calc_weight = result.protein_calculation_weight_kg
    expected_protein = (calc_weight * Decimal("2.2")).quantize(Decimal("1"))
    assert result.protein.preferred == expected_protein


def test_build_muscle_only_uses_build_muscle_strategy() -> None:
    inputs = _make_inputs(
        "build_muscle", requested_rate=None, exercise=_make_exercise("resistance")
    )
    result = calculate_targets(inputs)

    assert result.goal_strategy is not None
    assert result.goal_strategy.goal == "build_muscle"
    assert result.goal_calories == result.goal_strategy.goal_calories
    assert result.protein == result.goal_strategy.protein


def test_lose_weight_only_uses_lose_weight_strategy() -> None:
    inputs = _make_inputs("lose_weight", requested_rate=None, exercise=None)
    result = calculate_targets(inputs)

    assert result.goal_strategy is not None
    assert result.goal_strategy.goal == "lose_weight"
    assert result.goal_calories == result.goal_strategy.goal_calories
    assert result.protein == result.goal_strategy.protein


def test_gain_weight_only_uses_gain_weight_strategy() -> None:
    inputs = _make_inputs("gain_weight", requested_rate=None, exercise=None)
    result = calculate_targets(inputs)

    assert result.goal_strategy is not None
    assert result.goal_strategy.goal == "gain_weight"
    assert result.goal_calories == result.goal_strategy.goal_calories
    assert result.protein == result.goal_strategy.protein
