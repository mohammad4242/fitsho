from decimal import Decimal
from importlib import import_module
from types import ModuleType

import pytest


def scientific_module() -> ModuleType:
    try:
        return import_module("app.nutrition.scientific")
    except ModuleNotFoundError:
        pytest.fail("Task 3 scientific engine is not implemented")


def make_inputs(**overrides: object) -> object:
    scientific = scientific_module()
    values: dict[str, object] = {
        "age": 30,
        "height_cm": Decimal("175"),
        "weight_kg": Decimal("70"),
        "metabolic_basis": "male_coefficient",
        "daily_activity_level": "sedentary",
        "fitness_goal": "maintain_weight",
        "structured_exercise": None,
    }
    values.update(overrides)
    return scientific.ScientificInputs(**values)


def test_mifflin_returns_a_range_when_metabolic_basis_is_skipped() -> None:
    scientific = scientific_module()

    result = scientific.calculate_targets(make_inputs(metabolic_basis=None))

    assert result.bmr.minimum == Decimal("1482.75")
    assert result.bmr.maximum == Decimal("1648.75")
    assert result.confidence == "low"
    assert "METABOLIC_BASIS_RANGE" in result.confidence_reasons


def test_net_exercise_energy_does_not_count_resting_energy_twice() -> None:
    scientific = scientific_module()
    exercise = scientific.StructuredExercise(
        exercise_type="resistance",
        days_per_week=3,
        minutes_per_session=60,
        met_value=Decimal("5"),
        met_baseline_kcal_per_kg_hour=Decimal("1"),
    )

    result = scientific.calculate_targets(make_inputs(structured_exercise=exercise))

    assert result.bmr.preferred == Decimal("1648.75")
    assert result.non_exercise_energy.preferred == Decimal("1978.5000")
    assert result.exercise_energy.preferred == Decimal("120")
    assert result.tdee.preferred == Decimal("2098.5000")


def test_older_adult_met_uses_the_older_compendium_baseline() -> None:
    scientific = scientific_module()
    exercise = scientific.StructuredExercise(
        exercise_type="resistance",
        days_per_week=3,
        minutes_per_session=60,
        met_value=Decimal("4.3"),
        met_baseline_kcal_per_kg_hour=Decimal("0.810"),
    )

    result = scientific.calculate_targets(make_inputs(age=65, structured_exercise=exercise))

    assert result.exercise_energy.preferred == Decimal("80.19")


def test_high_bmi_uses_adjusted_weight_for_protein() -> None:
    scientific = scientific_module()
    exercise = scientific.StructuredExercise(
        exercise_type="resistance",
        days_per_week=4,
        minutes_per_session=60,
        met_value=Decimal("5"),
        met_baseline_kcal_per_kg_hour=Decimal("1"),
    )

    result = scientific.calculate_targets(
        make_inputs(
            weight_kg=Decimal("100"),
            fitness_goal="fat_loss",
            structured_exercise=exercise,
        )
    )

    assert result.protein_calculation_weight_kg == Decimal("84.296875")
    assert result.protein.minimum == Decimal("67.4375000")
    assert result.protein.preferred == Decimal("151.7343750")
    assert result.protein.maximum == Decimal("185.4531250")


def test_who_targets_are_derived_from_goal_calories() -> None:
    scientific = scientific_module()

    targets = scientific.nutrient_targets_for_calories(Decimal("2000"))

    assert targets.carbohydrate.minimum == Decimal("225")
    assert targets.carbohydrate.maximum == Decimal("375")
    assert targets.total_fat.minimum == Decimal("33.33333333333333333333333333")
    assert targets.total_fat.preferred == Decimal("44.44444444444444444444444444")
    assert targets.total_fat.maximum == Decimal("66.66666666666666666666666667")
    assert targets.fibre.minimum == Decimal("25")
    assert targets.fibre.preferred == Decimal("28")
    assert targets.free_sugar.preferred == Decimal("25")
    assert targets.free_sugar.maximum == Decimal("50")
    assert targets.saturated_fat.maximum == Decimal("22.22222222222222222222222222")
    assert targets.trans_fat.maximum == Decimal("2.222222222222222222222222222")
    assert targets.sodium.preferred == Decimal("1500")
    assert targets.sodium.maximum == Decimal("2300")


def test_no_training_muscle_building_goal_gets_target_with_coaching_warning() -> None:
    scientific = scientific_module()

    result = scientific.calculate_targets(
        make_inputs(fitness_goal="build_muscle", structured_exercise=None)
    )

    assert result.goal_calories.preferred is not None
    assert "TRAINING_STIMULUS_MISMATCH" in result.training_alignment.warning_codes
    assert "TARGETS_GENERATED_WITH_GOAL_COACHING_WARNING" in result.explanation_codes


def test_improve_fitness_uses_supported_conservative_nutrition_target() -> None:
    scientific = scientific_module()

    result = scientific.calculate_targets(make_inputs(fitness_goal="improve_fitness"))

    assert result.goal_calories.preferred == result.tdee.preferred
    assert result.goal_calories.minimum == result.tdee.minimum
    assert result.goal_calories.maximum == result.tdee.maximum
    assert result.explanation_codes == ("GENERAL_FITNESS_NUTRITION_TARGET",)


def test_strength_goal_accepts_resistance_training_with_maintenance_energy() -> None:
    scientific = scientific_module()
    exercise = scientific.StructuredExercise(
        exercise_type="resistance",
        days_per_week=3,
        minutes_per_session=60,
        met_value=Decimal("5"),
        met_baseline_kcal_per_kg_hour=Decimal("1"),
    )

    result = scientific.calculate_targets(
        make_inputs(fitness_goal="strength", structured_exercise=exercise)
    )

    assert result.goal_calories.preferred == result.tdee.preferred
    assert result.training_alignment.warning_codes == ()


def test_macro_energy_conflict_is_structured_as_target_infeasible() -> None:
    scientific = scientific_module()

    with pytest.raises(scientific.TargetInfeasibleError) as error:
        scientific.validate_macro_energy_feasibility(
            Decimal("1200"),
            scientific.TargetBand(unit="g/day", minimum=Decimal("200")),
            scientific.NutrientTargets(
                carbohydrate=scientific.TargetBand(unit="g", minimum=Decimal("130")),
                total_fat=scientific.TargetBand(unit="g", minimum=Decimal("40")),
                fibre=scientific.TargetBand(unit="g"),
                free_sugar=scientific.TargetBand(unit="g"),
                added_sugar=scientific.TargetBand(unit="g"),
                saturated_fat=scientific.TargetBand(unit="g"),
                trans_fat=scientific.TargetBand(unit="g"),
                sodium=scientific.TargetBand(unit="mg"),
            ),
        )

    assert "PROTEIN_MINIMUM_EXCEEDS_CALORIE_BUDGET" in error.value.reason_codes
