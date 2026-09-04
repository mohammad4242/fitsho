"""Canonical shared target band and nutrient targets data structures."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class TargetBand:
    unit: str
    minimum: Decimal | None = None
    preferred: Decimal | None = None
    preferred_maximum: Decimal | None = None
    maximum: Decimal | None = None


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
