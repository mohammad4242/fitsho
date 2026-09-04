"""Evidence-based nutrition goal macro strategies and energy-consistent resolution."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.nutrition.nutrition_targets import TargetBand
from app.nutrition.weight_rate_policy import (
    WeightRateResolution,
    resolve_weight_rate,
)

GOAL_STRATEGY_VERSION = "nutrition-goal-strategy-v1"
MACRO_RESOLUTION_POLICY_VERSION = "nutrition-macro-resolution-v2"


@dataclass(frozen=True)
class GoalStrategyInputs:
    fitness_goal: str
    body_weight_kg: Decimal
    protein_calculation_weight_kg: Decimal
    requested_weight_change_kg_per_week: Decimal | None
    exercise_type: str | None
    training_days_per_week: int | None
    training_minutes_per_session: int | None
    training_experience: str | None


@dataclass(frozen=True)
class GoalMacroStrategy:
    goal: str
    goal_calories: TargetBand
    protein: TargetBand
    carbohydrate: TargetBand
    total_fat: TargetBand
    fibre: TargetBand
    target_weight_rate: WeightRateResolution
    protein_distribution_g_per_meal: Decimal | None
    training_carbohydrate_priority: str
    energy_density_preference: str
    goal_reason_codes: tuple[str, ...]


def resolve_energy_consistent_macros(
    *,
    calories: Decimal,
    protein: TargetBand,
    preferred_fat_ratio: Decimal,
    fat_min_ratio: Decimal,
    fat_max_ratio: Decimal,
    carbohydrate_soft_min_g: Decimal | None = None,
    carbohydrate_soft_max_g: Decimal | None = None,
) -> tuple[TargetBand, TargetBand]:
    """Resolve energy-consistent carbohydrate and fat target bands given calories and protein."""
    protein_g = protein.preferred if protein.preferred is not None else Decimal("100")
    protein_kcal = protein_g * Decimal("4")

    # Initial fat estimate based on preferred ratio of total calories
    target_fat_kcal = calories * preferred_fat_ratio
    fat_g = (target_fat_kcal / Decimal("9")).quantize(Decimal("1"))
    fat_kcal = fat_g * Decimal("9")

    # Carb gets remainder
    remaining_kcal = calories - protein_kcal - fat_kcal
    carb_g = max(Decimal("0"), (remaining_kcal / Decimal("4")).quantize(Decimal("1")))

    # Boundary bounds for fat
    min_fat_g = max(Decimal("20"), (calories * fat_min_ratio / Decimal("9")).quantize(Decimal("1")))
    max_fat_g = (calories * fat_max_ratio / Decimal("9")).quantize(Decimal("1"))

    # Rebalance if needed to keep protein*4 + carbs*4 + fat*9 within tolerance
    calculated_total = protein_kcal + (carb_g * Decimal("4")) + (fat_g * Decimal("9"))
    discrepancy = calories - calculated_total
    if discrepancy != Decimal("0"):
        # Adjust carb by the discrepancy if feasible
        carb_adjust = (discrepancy / Decimal("4")).quantize(Decimal("1"))
        carb_g = max(Decimal("0"), carb_g + carb_adjust)

    carb_min = max(Decimal("0"), carb_g - Decimal("30"))
    carb_max = carb_g + Decimal("30")
    carbohydrate_band = TargetBand(
        unit="g",
        minimum=carb_min,
        preferred=carb_g,
        preferred_maximum=carb_g + Decimal("15"),
        maximum=carb_max,
    )

    fat_band = TargetBand(
        unit="g",
        minimum=min_fat_g,
        preferred=fat_g,
        preferred_maximum=max_fat_g,
        maximum=max_fat_g + Decimal("10"),
    )

    return carbohydrate_band, fat_band


def resolve_goal_strategy(
    inputs: GoalStrategyInputs,
    *,
    bmr: TargetBand,
    tdee: TargetBand,
    protein_calculation_weight_kg: Decimal,
    reliable_ffm_kg: Decimal | None = None,
) -> GoalMacroStrategy:
    """Resolve strategy targets for one of the 5 evidence-based coaching goals."""
    goal = inputs.fitness_goal.lower()
    tdee_val = tdee.preferred or tdee.minimum or Decimal("2000")
    bmr_val = bmr.preferred or bmr.minimum or Decimal("1400")

    rate_res = resolve_weight_rate(
        goal=goal,
        body_weight_kg=inputs.body_weight_kg,
        tdee_kcal=tdee_val,
        requested_kg_per_week=inputs.requested_weight_change_kg_per_week,
        training_experience=inputs.training_experience,
    )

    is_rt = inputs.exercise_type in ("resistance", "mixed") and (
        inputs.training_days_per_week is not None and inputs.training_days_per_week > 0
    )

    reasons: list[str] = list(rate_res.warning_codes)

    # 1. Calories
    if goal in ("lose_weight", "fat_loss"):
        # Product safety floor: do not drop below BMR in ordinary automated plan
        raw_cal = tdee_val + rate_res.calorie_delta_kcal_per_day
        goal_cal = max(bmr_val, raw_cal)
    elif goal in ("gain_weight", "build_muscle"):
        goal_cal = tdee_val + rate_res.calorie_delta_kcal_per_day
    elif goal == "body_recomposition":
        # Maintenance default
        goal_cal = tdee_val
    else:
        goal_cal = tdee_val

    # 2. Protein
    calc_weight = protein_calculation_weight_kg
    if goal == "lose_weight":
        if is_rt:
            prot_min = (calc_weight * Decimal("1.5")).quantize(Decimal("1"))
            prot_pref = (calc_weight * Decimal("1.8")).quantize(Decimal("1"))
            prot_max = (calc_weight * Decimal("2.2")).quantize(Decimal("1"))
        else:
            prot_min = (calc_weight * Decimal("1.2")).quantize(Decimal("1"))
            prot_pref = (calc_weight * Decimal("1.5")).quantize(Decimal("1"))
            prot_max = (calc_weight * Decimal("2.0")).quantize(Decimal("1"))
        pref_fat_ratio = Decimal("0.28")
        fat_min_ratio = Decimal("0.20")
        fat_max_ratio = Decimal("0.35")
        distribution = None
        carb_prio = "normal"
        density = "moderate_low"

    elif goal == "fat_loss":
        if reliable_ffm_kg is not None and is_rt:
            prot_min = (reliable_ffm_kg * Decimal("2.3")).quantize(Decimal("1"))
            prot_pref = (reliable_ffm_kg * Decimal("2.6")).quantize(Decimal("1"))
            prot_max = (reliable_ffm_kg * Decimal("3.1")).quantize(Decimal("1"))
        elif is_rt:
            prot_min = (calc_weight * Decimal("1.8")).quantize(Decimal("1"))
            prot_pref = (calc_weight * Decimal("2.2")).quantize(Decimal("1"))
            prot_max = (calc_weight * Decimal("2.6")).quantize(Decimal("1"))
        else:
            prot_min = (calc_weight * Decimal("1.6")).quantize(Decimal("1"))
            prot_pref = (calc_weight * Decimal("1.8")).quantize(Decimal("1"))
            prot_max = (calc_weight * Decimal("2.2")).quantize(Decimal("1"))
        pref_fat_ratio = Decimal("0.25")
        fat_min_ratio = Decimal("0.20")
        fat_max_ratio = Decimal("0.30")
        distribution = (calc_weight * Decimal("0.45")).quantize(Decimal("1"))
        carb_prio = "high" if is_rt else "normal"
        density = "moderate_low"

    elif goal == "gain_weight":
        if is_rt:
            prot_min = (calc_weight * Decimal("1.6")).quantize(Decimal("1"))
            prot_pref = (calc_weight * Decimal("1.8")).quantize(Decimal("1"))
            prot_max = (calc_weight * Decimal("2.2")).quantize(Decimal("1"))
        else:
            prot_min = (calc_weight * Decimal("1.2")).quantize(Decimal("1"))
            prot_pref = (calc_weight * Decimal("1.4")).quantize(Decimal("1"))
            prot_max = (calc_weight * Decimal("1.8")).quantize(Decimal("1"))
        pref_fat_ratio = Decimal("0.30")
        fat_min_ratio = Decimal("0.25")
        fat_max_ratio = Decimal("0.35")
        distribution = None
        carb_prio = "normal"
        density = "moderate_high"

    elif goal == "build_muscle":
        if not is_rt:
            reasons.append("TRAINING_STIMULUS_MISMATCH")
        prot_min = (calc_weight * Decimal("1.6")).quantize(Decimal("1"))
        prot_pref = (calc_weight * Decimal("2.0")).quantize(Decimal("1"))
        prot_max = (calc_weight * Decimal("2.4")).quantize(Decimal("1"))
        pref_fat_ratio = Decimal("0.25")
        fat_min_ratio = Decimal("0.20")
        fat_max_ratio = Decimal("0.30")
        distribution = (calc_weight * Decimal("0.40")).quantize(Decimal("1"))
        carb_prio = "high"
        density = "moderate"

    elif goal == "body_recomposition":
        if not is_rt:
            reasons.append("TRAINING_STIMULUS_MISMATCH")
        prot_min = (calc_weight * Decimal("1.8")).quantize(Decimal("1"))
        prot_pref = (calc_weight * Decimal("2.1")).quantize(Decimal("1"))
        prot_max = (calc_weight * Decimal("2.5")).quantize(Decimal("1"))
        pref_fat_ratio = Decimal("0.25")
        fat_min_ratio = Decimal("0.20")
        fat_max_ratio = Decimal("0.30")
        distribution = (calc_weight * Decimal("0.40")).quantize(Decimal("1"))
        carb_prio = "high"
        density = "moderate"

    else:
        # Default / maintenance
        prot_min = (calc_weight * Decimal("1.2")).quantize(Decimal("1"))
        prot_pref = (calc_weight * Decimal("1.5")).quantize(Decimal("1"))
        prot_max = (calc_weight * Decimal("2.0")).quantize(Decimal("1"))
        pref_fat_ratio = Decimal("0.28")
        fat_min_ratio = Decimal("0.20")
        fat_max_ratio = Decimal("0.35")
        distribution = None
        carb_prio = "normal"
        density = "moderate"

    protein_band = TargetBand(
        unit="g",
        minimum=prot_min,
        preferred=prot_pref,
        preferred_maximum=prot_pref + Decimal("15"),
        maximum=prot_max,
    )

    carbohydrate_band, fat_band = resolve_energy_consistent_macros(
        calories=goal_cal,
        protein=protein_band,
        preferred_fat_ratio=pref_fat_ratio,
        fat_min_ratio=fat_min_ratio,
        fat_max_ratio=fat_max_ratio,
    )

    # 14g fibre per 1000 kcal, minimum 25g
    fibre_g = max(
        Decimal("25"), (goal_cal * Decimal("14") / Decimal("1000")).quantize(Decimal("1"))
    )
    fibre_band = TargetBand(
        unit="g",
        minimum=Decimal("25"),
        preferred=fibre_g,
        preferred_maximum=fibre_g + Decimal("10"),
        maximum=Decimal("60"),
    )

    goal_cal_band = TargetBand(
        unit="kcal",
        minimum=goal_cal - Decimal("100"),
        preferred=goal_cal,
        preferred_maximum=goal_cal + Decimal("100"),
        maximum=goal_cal + Decimal("200"),
    )

    return GoalMacroStrategy(
        goal=goal,
        goal_calories=goal_cal_band,
        protein=protein_band,
        carbohydrate=carbohydrate_band,
        total_fat=fat_band,
        fibre=fibre_band,
        target_weight_rate=rate_res,
        protein_distribution_g_per_meal=distribution,
        training_carbohydrate_priority=carb_prio,
        energy_density_preference=density,
        goal_reason_codes=tuple(dict.fromkeys(reasons)),
    )
