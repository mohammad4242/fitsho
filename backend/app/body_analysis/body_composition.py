from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.profile.enums import Sex


class BodyCompositionMetrics(BaseModel):
    model_config = ConfigDict(extra="forbid")

    bmi: float | None = Field(default=None, ge=0.0)
    estimated_body_fat_percent: float | None = Field(default=None, ge=0.0, le=100.0)
    body_fat_estimation_method: Literal["rfm"] | None = None
    body_fat_is_estimate: bool = True


def calculate_bmi(height_cm: float | int | None, weight_kg: float | int | None) -> float | None:
    """Calculate Body Mass Index (BMI) rounded to 1 decimal place."""
    if height_cm is None or weight_kg is None:
        return None
    if height_cm <= 0 or weight_kg <= 0:
        return None
    height_m = height_cm / 100.0
    bmi = weight_kg / (height_m**2)
    if bmi <= 5.0 or bmi >= 150.0:
        return None
    return round(bmi, 1)


def calculate_rfm_body_fat(
    sex: Sex | str | None,
    height_cm: float | int | None,
    waist_cm: float | int | None,
) -> float | None:
    """Calculate Relative Fat Mass (RFM) body fat percentage rounded to 1 decimal place.

    Formulas:
    - Male: RFM = 64 - 20 * (height_cm / waist_cm)
    - Female: RFM = 76 - 20 * (height_cm / waist_cm)
    """
    if sex is None or height_cm is None or waist_cm is None:
        return None
    if height_cm <= 0 or waist_cm <= 0:
        return None

    raw_sex = sex.value if isinstance(sex, Sex) else str(sex).lower()
    if raw_sex == Sex.MALE.value:
        base = 64.0
    elif raw_sex == Sex.FEMALE.value:
        base = 76.0
    else:
        return None

    rfm = base - 20.0 * (float(height_cm) / float(waist_cm))
    if rfm <= 2.0 or rfm >= 80.0:
        return None
    return round(rfm, 1)


def calculate_body_composition(
    *,
    sex: Sex | str | None,
    height_cm: float | int | None,
    weight_kg: float | int | None,
    waist_circumference_cm: float | int | None,
) -> BodyCompositionMetrics:
    """Compute deterministic body composition metrics from snapshot measurements."""
    bmi = calculate_bmi(height_cm, weight_kg)
    body_fat = calculate_rfm_body_fat(sex, height_cm, waist_circumference_cm)
    return BodyCompositionMetrics(
        bmi=bmi,
        estimated_body_fat_percent=body_fat,
        body_fat_estimation_method="rfm" if body_fat is not None else None,
        body_fat_is_estimate=True,
    )
