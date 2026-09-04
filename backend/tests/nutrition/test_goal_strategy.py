from decimal import Decimal

from app.nutrition.goal_strategy import (
    GoalStrategyInputs,
    resolve_energy_consistent_macros,
    resolve_goal_strategy,
)
from app.nutrition.nutrition_targets import TargetBand


def test_resolve_energy_consistent_macros() -> None:
    calories = Decimal("2000")
    protein = TargetBand(
        unit="g", minimum=Decimal("120"), preferred=Decimal("150"), maximum=Decimal("180")
    )
    # Protein 150g = 600 kcal. Remaining = 1400 kcal.
    # Fat 25% = 500 kcal = 55.5g -> ~56g (504 kcal). Remaining carb = 896 kcal = 224g.
    carb_band, fat_band = resolve_energy_consistent_macros(
        calories=calories,
        protein=protein,
        preferred_fat_ratio=Decimal("0.25"),
        fat_min_ratio=Decimal("0.20"),
        fat_max_ratio=Decimal("0.35"),
        carbohydrate_soft_min_g=None,
        carbohydrate_soft_max_g=None,
    )
    assert carb_band.preferred is not None
    assert fat_band.preferred is not None
    assert protein.preferred is not None

    total_energy = (
        (protein.preferred * Decimal("4"))
        + (carb_band.preferred * Decimal("4"))
        + (fat_band.preferred * Decimal("9"))
    )
    # Check within 15 kcal rounding tolerance
    assert abs(total_energy - calories) <= Decimal("15")


def test_lose_weight_strategy() -> None:
    bmr = TargetBand(unit="kcal", preferred=Decimal("1600"))
    tdee = TargetBand(unit="kcal", preferred=Decimal("2300"))
    inputs = GoalStrategyInputs(
        fitness_goal="lose_weight",
        body_weight_kg=Decimal("80"),
        protein_calculation_weight_kg=Decimal("75"),
        requested_weight_change_kg_per_week=Decimal("0.5"),
        exercise_type=None,
        training_days_per_week=0,
        training_minutes_per_session=0,
        training_experience=None,
    )
    strategy = resolve_goal_strategy(
        inputs,
        bmr=bmr,
        tdee=tdee,
        protein_calculation_weight_kg=Decimal("75"),
    )
    assert strategy.goal == "lose_weight"
    # Deficit should be 550 kcal, so 2300 - 550 = 1750 kcal
    assert strategy.goal_calories.preferred == Decimal("1750")
    assert strategy.protein.preferred is not None
    assert strategy.protein.preferred >= Decimal("90")  # >= 1.2 g/kg


def test_fat_loss_strategy_high_protein() -> None:
    bmr = TargetBand(unit="kcal", preferred=Decimal("1700"))
    tdee = TargetBand(unit="kcal", preferred=Decimal("2600"))
    inputs = GoalStrategyInputs(
        fitness_goal="fat_loss",
        body_weight_kg=Decimal("80"),
        protein_calculation_weight_kg=Decimal("80"),
        requested_weight_change_kg_per_week=Decimal("0.5"),
        exercise_type="resistance",
        training_days_per_week=4,
        training_minutes_per_session=60,
        training_experience="intermediate",
    )
    strategy = resolve_goal_strategy(
        inputs,
        bmr=bmr,
        tdee=tdee,
        protein_calculation_weight_kg=Decimal("80"),
    )
    assert strategy.goal == "fat_loss"
    # Fat loss with resistance should target ~2.0-2.4 g/kg -> around 160-190g protein
    assert strategy.protein.preferred is not None
    assert strategy.protein.preferred >= Decimal("160")
    assert strategy.training_carbohydrate_priority == "high"


def test_build_muscle_stimulus_mismatch_warning() -> None:
    bmr = TargetBand(unit="kcal", preferred=Decimal("1500"))
    tdee = TargetBand(unit="kcal", preferred=Decimal("2000"))
    # No resistance training
    inputs = GoalStrategyInputs(
        fitness_goal="build_muscle",
        body_weight_kg=Decimal("70"),
        protein_calculation_weight_kg=Decimal("70"),
        requested_weight_change_kg_per_week=Decimal("0.3"),
        exercise_type=None,
        training_days_per_week=0,
        training_minutes_per_session=0,
        training_experience=None,
    )
    strategy = resolve_goal_strategy(
        inputs,
        bmr=bmr,
        tdee=tdee,
        protein_calculation_weight_kg=Decimal("70"),
    )
    assert "TRAINING_STIMULUS_MISMATCH" in strategy.goal_reason_codes


def test_recomposition_strategy_maintenance() -> None:
    bmr = TargetBand(unit="kcal", preferred=Decimal("1600"))
    tdee = TargetBand(unit="kcal", preferred=Decimal("2400"))
    inputs = GoalStrategyInputs(
        fitness_goal="body_recomposition",
        body_weight_kg=Decimal("75"),
        protein_calculation_weight_kg=Decimal("75"),
        requested_weight_change_kg_per_week=None,
        exercise_type="resistance",
        training_days_per_week=4,
        training_minutes_per_session=60,
        training_experience="intermediate",
    )
    strategy = resolve_goal_strategy(
        inputs,
        bmr=bmr,
        tdee=tdee,
        protein_calculation_weight_kg=Decimal("75"),
    )
    assert strategy.goal_calories.preferred == Decimal("2400")
    assert strategy.protein.preferred is not None
    assert strategy.protein.preferred >= Decimal("135")  # ~1.8-2.2 g/kg
