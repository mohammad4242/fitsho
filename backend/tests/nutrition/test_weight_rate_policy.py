from decimal import Decimal

from app.nutrition.weight_rate_policy import (
    requested_rate_delta_kcal_per_day,
    resolve_weight_rate,
)


def test_requested_rate_delta_kcal_per_day() -> None:
    # 0.5 kg/week * 7700 / 7 = 550 kcal/day
    delta = requested_rate_delta_kcal_per_day(Decimal("0.5"))
    assert delta == Decimal("550")

    # 1.0 kg/week * 7700 / 7 = 1100 kcal/day
    delta_1 = requested_rate_delta_kcal_per_day(Decimal("1.0"))
    assert delta_1 == Decimal("1100")


def test_lose_weight_default_and_clamping() -> None:
    # Default 0.5 kg/week for 80kg user, TDEE 2400
    res = resolve_weight_rate(
        goal="lose_weight",
        body_weight_kg=Decimal("80"),
        tdee_kcal=Decimal("2400"),
        requested_kg_per_week=None,
        training_experience="intermediate",
    )
    assert res.recommended_kg_per_week == Decimal("0.5")
    assert res.applied_kg_per_week == Decimal("0.5")
    assert res.calorie_delta_kcal_per_day == Decimal("-550")
    assert not res.was_clamped
    assert res.warning_codes == ()

    # Extreme rate 2.0 kg/week requested -> must be clamped by 1% BW (0.8 kg)
    # and max deficit (2400 * 0.25 = 600 kcal)
    res_clamped = resolve_weight_rate(
        goal="lose_weight",
        body_weight_kg=Decimal("80"),
        tdee_kcal=Decimal("2400"),
        requested_kg_per_week=Decimal("2.0"),
        training_experience="intermediate",
    )
    assert res_clamped.was_clamped
    assert "WEIGHT_RATE_ABOVE_RECOMMENDED" in res_clamped.warning_codes
    assert "WEIGHT_RATE_CLAMPED_FOR_AUTOMATIC_SAFETY" in res_clamped.warning_codes
    # Deficit should be capped at 600 kcal/day (25% TDEE)
    assert res_clamped.calorie_delta_kcal_per_day == Decimal("-600")


def test_fat_loss_conservative_cap() -> None:
    # Fat loss max deficit is min(750, 20% TDEE)
    # TDEE 3000 -> 20% is 600 kcal. Requested 1.0 kg/wk (1100 kcal) -> clamped to 600
    res = resolve_weight_rate(
        goal="fat_loss",
        body_weight_kg=Decimal("75"),
        tdee_kcal=Decimal("3000"),
        requested_kg_per_week=Decimal("1.0"),
        training_experience="intermediate",
    )
    assert res.was_clamped
    assert res.calorie_delta_kcal_per_day == Decimal("-600")


def test_gain_weight_and_build_muscle_clamping() -> None:
    # Gain weight default recommendation is 0.3 kg/wk
    res_gw = resolve_weight_rate(
        goal="gain_weight",
        body_weight_kg=Decimal("60"),
        tdee_kcal=Decimal("2000"),
        requested_kg_per_week=None,
        training_experience=None,
    )
    assert res_gw.recommended_kg_per_week == Decimal("0.3")
    assert res_gw.calorie_delta_kcal_per_day == Decimal("330")

    # Build muscle advanced lifter: max surplus 10% TDEE
    res_adv = resolve_weight_rate(
        goal="build_muscle",
        body_weight_kg=Decimal("80"),
        tdee_kcal=Decimal("2500"),
        requested_kg_per_week=Decimal("1.5"),
        training_experience="advanced",
    )
    assert res_adv.was_clamped
    # 10% of 2500 is 250 kcal
    assert res_adv.calorie_delta_kcal_per_day == Decimal("250")


def test_body_recomposition_ignores_rate() -> None:
    res = resolve_weight_rate(
        goal="body_recomposition",
        body_weight_kg=Decimal("70"),
        tdee_kcal=Decimal("2200"),
        requested_kg_per_week=Decimal("0.5"),
        training_experience="beginner",
    )
    assert res.requested_kg_per_week is None
    assert res.recommended_kg_per_week is None
    assert res.applied_kg_per_week is None
    assert res.calorie_delta_kcal_per_day == Decimal("0")
    assert "WEIGHT_RATE_NOT_USED_FOR_RECOMPOSITION" in res.warning_codes


def test_user_override_mode() -> None:
    # Safe mode clamps 2.0 kg/week to max deficit
    res_safe = resolve_weight_rate(
        goal="lose_weight",
        body_weight_kg=Decimal("80"),
        tdee_kcal=Decimal("2400"),
        requested_kg_per_week=Decimal("2.0"),
        training_experience="intermediate",
        rate_mode="safe",
    )
    assert res_safe.was_clamped
    assert res_safe.calorie_delta_kcal_per_day == Decimal("-600")

    # User override mode respects user's 2.0 kg/week request directly
    res_override = resolve_weight_rate(
        goal="lose_weight",
        body_weight_kg=Decimal("80"),
        tdee_kcal=Decimal("2400"),
        requested_kg_per_week=Decimal("2.0"),
        training_experience="intermediate",
        rate_mode="user_override",
    )
    assert not res_override.was_clamped
    assert res_override.applied_kg_per_week == Decimal("2.0")
    assert res_override.calorie_delta_kcal_per_day == Decimal("-2200")
    assert "WEIGHT_RATE_USER_OVERRIDE_APPLIED" in res_override.warning_codes
    assert "WEIGHT_RATE_ABOVE_RECOMMENDED" in res_override.warning_codes
