from app.body_analysis.body_composition import (
    calculate_bmi,
    calculate_body_composition,
    calculate_rfm_body_fat,
)
from app.profile.enums import Sex


def test_calculate_bmi_normal() -> None:
    # 78.4 kg, 180 cm -> 78.4 / 1.8^2 = 24.1975... -> 24.2
    assert calculate_bmi(180, 78.4) == 24.2


def test_calculate_bmi_invalid_or_missing() -> None:
    assert calculate_bmi(None, 70) is None
    assert calculate_bmi(175, None) is None
    assert calculate_bmi(0, 70) is None
    assert calculate_bmi(175, 0) is None
    assert calculate_bmi(-175, 70) is None
    assert calculate_bmi(175, -70) is None
    assert calculate_bmi(200, 10) is None  # extreme low BMI <= 5.0


def test_calculate_rfm_body_fat_male() -> None:
    # Male: 64 - 20 * (180 / 80) = 64 - 45 = 19.0
    assert calculate_rfm_body_fat(Sex.MALE, 180, 80) == 19.0
    assert calculate_rfm_body_fat("male", 180, 80) == 19.0


def test_calculate_rfm_body_fat_female() -> None:
    # Female: 76 - 20 * (165 / 70) = 76 - 47.142857 = 28.857... -> 28.9
    assert calculate_rfm_body_fat(Sex.FEMALE, 165, 70) == 28.9
    assert calculate_rfm_body_fat("female", 165, 70) == 28.9


def test_calculate_rfm_body_fat_unsupported_sex() -> None:
    assert calculate_rfm_body_fat(Sex.OTHER, 180, 80) is None
    assert calculate_rfm_body_fat(Sex.PREFER_NOT_TO_SAY, 180, 80) is None
    assert calculate_rfm_body_fat("unknown", 180, 80) is None
    assert calculate_rfm_body_fat(None, 180, 80) is None


def test_calculate_rfm_body_fat_invalid_measurements() -> None:
    assert calculate_rfm_body_fat(Sex.MALE, None, 80) is None
    assert calculate_rfm_body_fat(Sex.MALE, 180, None) is None
    assert calculate_rfm_body_fat(Sex.MALE, 0, 80) is None
    assert calculate_rfm_body_fat(Sex.MALE, 180, 0) is None
    assert calculate_rfm_body_fat(Sex.MALE, -180, 80) is None
    assert calculate_rfm_body_fat(Sex.MALE, 180, -80) is None


def test_calculate_body_composition_full() -> None:
    result = calculate_body_composition(
        sex=Sex.MALE,
        height_cm=180,
        weight_kg=78.4,
        waist_circumference_cm=80.0,
    )
    assert result.bmi == 24.2
    assert result.estimated_body_fat_percent == 19.0
    assert result.body_fat_estimation_method == "rfm"
    assert result.body_fat_is_estimate is True


def test_calculate_body_composition_missing_waist() -> None:
    result = calculate_body_composition(
        sex=Sex.MALE,
        height_cm=180,
        weight_kg=78.4,
        waist_circumference_cm=None,
    )
    assert result.bmi == 24.2
    assert result.estimated_body_fat_percent is None
    assert result.body_fat_estimation_method is None
    assert result.body_fat_is_estimate is True
