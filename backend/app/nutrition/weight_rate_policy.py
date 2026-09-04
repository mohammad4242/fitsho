"""Deterministic rate controller for weekly weight change recommendations."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

WEIGHT_RATE_POLICY_VERSION = "nutrition-weight-rate-v1"
KCAL_PER_KG_ENGINEERING_ESTIMATE = Decimal("7700")


@dataclass(frozen=True)
class WeightRateResolution:
    requested_kg_per_week: Decimal | None
    recommended_kg_per_week: Decimal | None
    applied_kg_per_week: Decimal | None
    calorie_delta_kcal_per_day: Decimal
    was_clamped: bool
    warning_codes: tuple[str, ...]


def requested_rate_delta_kcal_per_day(rate_kg_per_week: Decimal) -> Decimal:
    """Convert a requested scale-weight rate into an initial energy-control signal.

    This converts a requested scale-weight rate into an initial energy-control
    signal. It does not predict or guarantee real-world weight change.
    """
    return (rate_kg_per_week * KCAL_PER_KG_ENGINEERING_ESTIMATE / Decimal("7")).quantize(
        Decimal("1")
    )


def resolve_weight_rate(
    *,
    goal: str,
    body_weight_kg: Decimal,
    tdee_kcal: Decimal,
    requested_kg_per_week: Decimal | None,
    training_experience: str | None,
) -> WeightRateResolution:
    """Resolve recommended, requested, and applied weekly rate and energy delta."""
    normalized_goal = goal.lower()

    if normalized_goal == "body_recomposition":
        warnings: list[str] = []
        if requested_kg_per_week is not None:
            warnings.append("WEIGHT_RATE_NOT_USED_FOR_RECOMPOSITION")
        return WeightRateResolution(
            requested_kg_per_week=None,
            recommended_kg_per_week=None,
            applied_kg_per_week=None,
            calorie_delta_kcal_per_day=Decimal("0"),
            was_clamped=False,
            warning_codes=tuple(warnings),
        )

    if normalized_goal in ("maintain_weight", "improve_fitness", "strength"):
        return WeightRateResolution(
            requested_kg_per_week=requested_kg_per_week,
            recommended_kg_per_week=None,
            applied_kg_per_week=None,
            calorie_delta_kcal_per_day=Decimal("0"),
            was_clamped=False,
            warning_codes=(),
        )

    # Defaults and bounds per goal
    if normalized_goal == "lose_weight":
        recommended_rate = Decimal("0.5")
        max_rate_bw = (body_weight_kg * Decimal("0.01")).quantize(Decimal("0.1"))
        max_deficit_kcal = min(
            Decimal("1000"), (tdee_kcal * Decimal("0.25")).quantize(Decimal("1"))
        )
        is_loss = True
    elif normalized_goal == "fat_loss":
        recommended_rate = Decimal("0.5")
        max_rate_bw = min(
            Decimal("1.0"), (body_weight_kg * Decimal("0.01")).quantize(Decimal("0.1"))
        )
        max_deficit_kcal = min(Decimal("750"), (tdee_kcal * Decimal("0.20")).quantize(Decimal("1")))
        is_loss = True
    elif normalized_goal == "gain_weight":
        recommended_rate = Decimal("0.3")
        max_rate_bw = min(
            Decimal("1.0"), (body_weight_kg * Decimal("0.01")).quantize(Decimal("0.1"))
        )
        max_surplus_kcal = min(Decimal("750"), (tdee_kcal * Decimal("0.20")).quantize(Decimal("1")))
        is_loss = False
    elif normalized_goal == "build_muscle":
        is_adv = training_experience == "advanced"
        recommended_rate = Decimal("0.2") if is_adv else Decimal("0.3")
        max_rate_bw = min(
            Decimal("0.5"), (body_weight_kg * Decimal("0.005")).quantize(Decimal("0.1"))
        )
        surplus_ratio = Decimal("0.10") if is_adv else Decimal("0.15")
        max_surplus_kcal = min(Decimal("500"), (tdee_kcal * surplus_ratio).quantize(Decimal("1")))
        is_loss = False
    else:
        # Fallback
        recommended_rate = Decimal("0.5")
        max_rate_bw = Decimal("1.0")
        max_deficit_kcal = Decimal("500")
        is_loss = True

    effective_requested = (
        requested_kg_per_week if requested_kg_per_week is not None else recommended_rate
    )
    target_rate = min(effective_requested, max_rate_bw)

    theoretical_delta = requested_rate_delta_kcal_per_day(target_rate)

    warnings = []
    was_clamped = False

    if requested_kg_per_week is not None and requested_kg_per_week > recommended_rate:
        warnings.append("WEIGHT_RATE_ABOVE_RECOMMENDED")

    if is_loss:
        applied_delta = min(theoretical_delta, max_deficit_kcal)
        if effective_requested > max_rate_bw or theoretical_delta > max_deficit_kcal:
            was_clamped = True
            warnings.append("WEIGHT_RATE_CLAMPED_FOR_AUTOMATIC_SAFETY")
        applied_rate = (applied_delta * Decimal("7") / KCAL_PER_KG_ENGINEERING_ESTIMATE).quantize(
            Decimal("0.1")
        )
        calorie_delta = -applied_delta
    else:
        applied_delta = min(theoretical_delta, max_surplus_kcal)
        if effective_requested > max_rate_bw or theoretical_delta > max_surplus_kcal:
            was_clamped = True
            warnings.append("WEIGHT_RATE_CLAMPED_FOR_AUTOMATIC_SAFETY")
        applied_rate = (applied_delta * Decimal("7") / KCAL_PER_KG_ENGINEERING_ESTIMATE).quantize(
            Decimal("0.1")
        )
        calorie_delta = applied_delta

    return WeightRateResolution(
        requested_kg_per_week=requested_kg_per_week,
        recommended_kg_per_week=recommended_rate,
        applied_kg_per_week=applied_rate,
        calorie_delta_kcal_per_day=calorie_delta,
        was_clamped=was_clamped,
        warning_codes=tuple(dict.fromkeys(warnings)),
    )
