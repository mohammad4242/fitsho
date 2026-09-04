from decimal import Decimal

from app.nutrition.nutrition_targets import NutrientTargets, TargetBand


def test_target_band_creation() -> None:
    band = TargetBand(
        unit="g",
        minimum=Decimal("50"),
        preferred=Decimal("75"),
        preferred_maximum=Decimal("100"),
        maximum=Decimal("120"),
    )
    assert band.unit == "g"
    assert band.minimum == Decimal("50")
    assert band.preferred == Decimal("75")
    assert band.preferred_maximum == Decimal("100")
    assert band.maximum == Decimal("120")


def test_nutrient_targets_canonical() -> None:
    targets = NutrientTargets(
        carbohydrate=TargetBand(unit="g", minimum=Decimal("100")),
        total_fat=TargetBand(unit="g", minimum=Decimal("30")),
        fibre=TargetBand(unit="g", minimum=Decimal("25")),
        free_sugar=TargetBand(unit="g", maximum=Decimal("50")),
        added_sugar=TargetBand(unit="g", maximum=Decimal("25")),
        saturated_fat=TargetBand(unit="g", maximum=Decimal("20")),
        trans_fat=TargetBand(unit="g", maximum=Decimal("2")),
        sodium=TargetBand(unit="mg", maximum=Decimal("2300")),
    )
    assert targets.carbohydrate.minimum == Decimal("100")
    assert targets.sodium.maximum == Decimal("2300")
