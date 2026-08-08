from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

POLICY_VERSION = "nutrition-science-v1"
FORMULA_VERSION = "mifflin-net-met-v1"

MetabolicBasis = Literal["female_coefficient", "male_coefficient"]
DailyActivity = Literal["sedentary", "light", "moderate", "very_active"]
ExerciseType = Literal["resistance", "endurance", "mixed", "other"]
FitnessGoal = Literal[
    "lose_weight",
    "gain_weight",
    "fat_loss",
    "build_muscle",
    "body_recomposition",
    "maintain_weight",
    "improve_fitness",
]
Confidence = Literal["high", "medium", "low"]

ZERO = Decimal("0")
ONE = Decimal("1")

ACTIVITY_MULTIPLIERS: dict[DailyActivity, Decimal] = {
    "sedentary": Decimal("1.20"),
    "light": Decimal("1.30"),
    "moderate": Decimal("1.40"),
    "very_active": Decimal("1.50"),
}


class GoalReselectionRequiredError(ValueError):
    pass


class TargetInfeasibleError(ValueError):
    def __init__(self, reason_codes: tuple[str, ...]) -> None:
        self.reason_codes = reason_codes
        super().__init__("Configured macro hard minimums exceed the calorie target")


@dataclass(frozen=True)
class TargetBand:
    unit: str
    minimum: Decimal | None = None
    preferred: Decimal | None = None
    preferred_maximum: Decimal | None = None
    maximum: Decimal | None = None


@dataclass(frozen=True)
class StructuredExercise:
    exercise_type: ExerciseType
    days_per_week: int
    minutes_per_session: int
    met_value: Decimal
    met_baseline_kcal_per_kg_hour: Decimal

    def __post_init__(self) -> None:
        if not 1 <= self.days_per_week <= 7:
            raise ValueError("Exercise days must be between 1 and 7")
        if not 1 <= self.minutes_per_session <= 360:
            raise ValueError("Exercise duration must be between 1 and 360 minutes")
        if self.met_value < ONE or self.met_baseline_kcal_per_kg_hour <= ZERO:
            raise ValueError("MET inputs must be positive")


@dataclass(frozen=True)
class ScientificInputs:
    age: int
    height_cm: Decimal
    weight_kg: Decimal
    metabolic_basis: MetabolicBasis | None
    daily_activity_level: DailyActivity
    fitness_goal: FitnessGoal
    structured_exercise: StructuredExercise | None

    def __post_init__(self) -> None:
        if not 18 <= self.age <= 100:
            raise ValueError("Age must be between 18 and 100")
        if self.height_cm <= ZERO or self.weight_kg <= ZERO:
            raise ValueError("Height and weight must be positive")


@dataclass(frozen=True)
class NutrientTargets:
    carbohydrate: TargetBand
    total_fat: TargetBand
    fibre: TargetBand
    free_sugar: TargetBand
    added_sugar: TargetBand
    saturated_fat: TargetBand
    trans_fat: TargetBand
    sodium: TargetBand


@dataclass(frozen=True)
class ScientificResult:
    policy_version: str
    formula_version: str
    confidence: Confidence
    confidence_reasons: tuple[str, ...]
    protein_calculation_weight_kg: Decimal
    bmr: TargetBand
    non_exercise_energy: TargetBand
    exercise_energy: TargetBand
    tdee: TargetBand
    goal_calories: TargetBand
    protein: TargetBand
    carbohydrate: TargetBand
    total_fat: TargetBand
    fibre: TargetBand
    free_sugar: TargetBand
    added_sugar: TargetBand
    saturated_fat: TargetBand
    trans_fat: TargetBand
    sodium: TargetBand


def nutrient_targets_for_calories(calories: Decimal) -> NutrientTargets:
    if calories <= ZERO:
        raise ValueError("Calories must be positive")
    carbohydrate_minimum = max(Decimal("130"), calories * Decimal("0.45") / Decimal("4"))
    fibre_preferred = max(Decimal("25"), calories / Decimal("1000") * Decimal("14"))
    return NutrientTargets(
        carbohydrate=TargetBand(
            unit="g",
            minimum=carbohydrate_minimum,
            maximum=calories * Decimal("0.75") / Decimal("4"),
        ),
        total_fat=TargetBand(
            unit="g",
            minimum=calories * Decimal("0.15") / Decimal("9"),
            preferred=calories * Decimal("0.20") / Decimal("9"),
            preferred_maximum=calories * Decimal("0.30") / Decimal("9"),
            maximum=calories * Decimal("0.30") / Decimal("9"),
        ),
        fibre=TargetBand(unit="g", minimum=Decimal("25"), preferred=fibre_preferred),
        free_sugar=TargetBand(
            unit="g",
            preferred=calories * Decimal("0.05") / Decimal("4"),
            maximum=calories * Decimal("0.10") / Decimal("4"),
        ),
        added_sugar=TargetBand(unit="g"),
        saturated_fat=TargetBand(
            unit="g", maximum=calories * Decimal("0.10") / Decimal("9")
        ),
        trans_fat=TargetBand(
            unit="g", maximum=calories * Decimal("0.01") / Decimal("9")
        ),
        sodium=TargetBand(unit="mg", preferred=Decimal("1500"), maximum=Decimal("2300")),
    )


def calculate_targets(inputs: ScientificInputs) -> ScientificResult:
    female_bmr = _mifflin(inputs, coefficient=Decimal("-161"))
    male_bmr = _mifflin(inputs, coefficient=Decimal("5"))
    if inputs.metabolic_basis == "female_coefficient":
        bmr = _point_band(female_bmr, "kcal/day")
    elif inputs.metabolic_basis == "male_coefficient":
        bmr = _point_band(male_bmr, "kcal/day")
    else:
        bmr = TargetBand(
            unit="kcal/day",
            minimum=min(female_bmr, male_bmr),
            preferred=(female_bmr + male_bmr) / Decimal("2"),
            maximum=max(female_bmr, male_bmr),
        )

    activity_multiplier = ACTIVITY_MULTIPLIERS[inputs.daily_activity_level]
    non_exercise = _map_band(bmr, lambda value: value * activity_multiplier)
    daily_exercise = _daily_exercise_energy(inputs.weight_kg, inputs.structured_exercise)
    exercise = _point_band(daily_exercise, "kcal/day")
    tdee = _map_band(non_exercise, lambda value: value + daily_exercise)
    goal_calories = _goal_calorie_band(inputs, bmr, tdee)
    calculation_weight = _protein_calculation_weight(inputs.height_cm, inputs.weight_kg)
    protein = TargetBand(
        unit="g/day",
        minimum=calculation_weight * Decimal("0.8"),
        preferred=calculation_weight * _preferred_protein_multiplier(inputs),
        maximum=calculation_weight * Decimal("2.2"),
    )
    assert goal_calories.preferred is not None
    nutrients = nutrient_targets_for_calories(goal_calories.preferred)
    validate_macro_energy_feasibility(goal_calories.preferred, protein, nutrients)
    confidence, reasons = _confidence(inputs)
    return ScientificResult(
        policy_version=POLICY_VERSION,
        formula_version=FORMULA_VERSION,
        confidence=confidence,
        confidence_reasons=reasons,
        protein_calculation_weight_kg=calculation_weight,
        bmr=bmr,
        non_exercise_energy=non_exercise,
        exercise_energy=exercise,
        tdee=tdee,
        goal_calories=goal_calories,
        protein=protein,
        carbohydrate=nutrients.carbohydrate,
        total_fat=nutrients.total_fat,
        fibre=nutrients.fibre,
        free_sugar=nutrients.free_sugar,
        added_sugar=nutrients.added_sugar,
        saturated_fat=nutrients.saturated_fat,
        trans_fat=nutrients.trans_fat,
        sodium=nutrients.sodium,
    )


def _mifflin(inputs: ScientificInputs, *, coefficient: Decimal) -> Decimal:
    return (
        Decimal("10") * inputs.weight_kg
        + Decimal("6.25") * inputs.height_cm
        - Decimal("5") * Decimal(inputs.age)
        + coefficient
    )


def _point_band(value: Decimal, unit: str) -> TargetBand:
    return TargetBand(unit=unit, minimum=value, preferred=value, maximum=value)


def _map_band(band: TargetBand, operation: Callable[[Decimal], Decimal]) -> TargetBand:
    def apply(value: Decimal | None) -> Decimal | None:
        if value is None:
            return None
        return operation(value)

    return TargetBand(
        unit=band.unit,
        minimum=apply(band.minimum),
        preferred=apply(band.preferred),
        preferred_maximum=apply(band.preferred_maximum),
        maximum=apply(band.maximum),
    )


def _daily_exercise_energy(
    weight_kg: Decimal, exercise: StructuredExercise | None
) -> Decimal:
    if exercise is None:
        return ZERO
    net_met = max(exercise.met_value - ONE, ZERO)
    hours = Decimal(exercise.minutes_per_session) / Decimal("60")
    weekly = (
        net_met
        * exercise.met_baseline_kcal_per_kg_hour
        * weight_kg
        * hours
        * Decimal(exercise.days_per_week)
    )
    return weekly / Decimal("7")


def _goal_calorie_band(
    inputs: ScientificInputs, bmr: TargetBand, tdee: TargetBand
) -> TargetBand:
    exercise_type = (
        inputs.structured_exercise.exercise_type if inputs.structured_exercise is not None else None
    )
    if inputs.fitness_goal in {"build_muscle", "body_recomposition"} and exercise_type not in {
        "resistance",
        "mixed",
    }:
        raise GoalReselectionRequiredError
    if inputs.fitness_goal == "improve_fitness":
        raise GoalReselectionRequiredError

    if inputs.fitness_goal in {"lose_weight", "fat_loss"}:
        factors = (Decimal("0.80"), Decimal("0.85"), Decimal("0.90"))
    elif inputs.fitness_goal == "gain_weight":
        factors = (
            (Decimal("1.05"), Decimal("1.10"), Decimal("1.15"))
            if inputs.structured_exercise is not None
            else (Decimal("1.05"), Decimal("1.05"), Decimal("1.05"))
        )
    elif inputs.fitness_goal == "build_muscle":
        factors = (Decimal("1.05"), Decimal("1.05"), Decimal("1.10"))
    elif inputs.fitness_goal == "body_recomposition":
        factors = (Decimal("0.95"), Decimal("1.00"), Decimal("1.00"))
    else:
        factors = (ONE, ONE, ONE)

    assert bmr.minimum is not None and bmr.preferred is not None and bmr.maximum is not None
    assert tdee.minimum is not None and tdee.preferred is not None and tdee.maximum is not None
    return TargetBand(
        unit="kcal/day",
        minimum=max(bmr.minimum, tdee.minimum * factors[0]),
        preferred=max(bmr.preferred, tdee.preferred * factors[1]),
        maximum=max(bmr.maximum, tdee.maximum * factors[2]),
    )


def _protein_calculation_weight(height_cm: Decimal, actual_weight: Decimal) -> Decimal:
    height_metres = height_cm / Decimal("100")
    reference_weight = Decimal("25") * height_metres * height_metres
    if actual_weight <= reference_weight:
        return actual_weight
    return reference_weight + Decimal("0.33") * (actual_weight - reference_weight)


def _preferred_protein_multiplier(inputs: ScientificInputs) -> Decimal:
    exercise_type = (
        inputs.structured_exercise.exercise_type if inputs.structured_exercise is not None else None
    )
    deficit = inputs.fitness_goal in {"lose_weight", "fat_loss", "body_recomposition"}
    if exercise_type in {"resistance", "mixed"}:
        return Decimal("1.8") if deficit else Decimal("1.6")
    if exercise_type == "endurance":
        return Decimal("1.4")
    return Decimal("1.2") if deficit else Decimal("1.0")


def validate_macro_energy_feasibility(
    calories: Decimal, protein: TargetBand, nutrients: NutrientTargets
) -> None:
    assert protein.minimum is not None
    assert nutrients.carbohydrate.minimum is not None
    assert nutrients.total_fat.minimum is not None
    hard_minimum_energy = (
        protein.minimum * Decimal("4")
        + nutrients.carbohydrate.minimum * Decimal("4")
        + nutrients.total_fat.minimum * Decimal("9")
    )
    if hard_minimum_energy > calories:
        raise TargetInfeasibleError(
            (
                "PROTEIN_MINIMUM_EXCEEDS_CALORIE_BUDGET",
                "CARBOHYDRATE_MINIMUM_EXCEEDS_CALORIE_BUDGET",
                "FAT_MINIMUM_EXCEEDS_CALORIE_BUDGET",
            )
        )


def _confidence(inputs: ScientificInputs) -> tuple[Confidence, tuple[str, ...]]:
    reasons: list[str] = []
    if inputs.metabolic_basis is None:
        reasons.append("METABOLIC_BASIS_RANGE")
    if not 19 <= inputs.age <= 78:
        reasons.append("MIFFLIN_AGE_OUTSIDE_SOURCE_RANGE")
    return ("low" if reasons else "high", tuple(reasons))
