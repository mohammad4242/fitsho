from datetime import date, timedelta
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.profile.schemas import ProfileCreate, ProfileUpdate, calculate_age


def valid_payload() -> dict[str, object]:
    return {
        "display_name": "  Mohammad  ",
        "birth_date": date(2000, 5, 14),
        "sex": "male",
        "height_cm": 178,
        "current_weight_kg": "76.50",
        "fitness_goal": "build_muscle",
        "experience_level": "beginner",
        "training_days_per_week": 3,
        "physical_limitations": "   ",
    }


def test_profile_create_normalizes_text_and_decimal() -> None:
    profile = ProfileCreate.model_validate(valid_payload())

    assert profile.display_name == "Mohammad"
    assert profile.current_weight_kg == Decimal("76.50")
    assert profile.physical_limitations is None


def test_calculate_age_handles_birthday_boundary() -> None:
    today = date(2026, 7, 27)

    assert calculate_age(date(2008, 7, 27), today) == 18
    assert calculate_age(date(2008, 7, 28), today) == 17


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("height_cm", 99),
        ("height_cm", 251),
        ("current_weight_kg", "19.99"),
        ("current_weight_kg", "500.01"),
        ("current_weight_kg", "70.123"),
        ("training_days_per_week", 0),
        ("training_days_per_week", 8),
        ("sex", "unknown"),
        ("fitness_goal", "bulk"),
        ("experience_level", "expert"),
    ],
)
def test_profile_create_rejects_invalid_values(field: str, value: object) -> None:
    payload = valid_payload()
    payload[field] = value

    with pytest.raises(ValidationError):
        ProfileCreate.model_validate(payload)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("display_name", " x "),
        ("display_name", "x" * 81),
        ("physical_limitations", "x" * 1001),
    ],
)
def test_profile_create_rejects_invalid_text_lengths(field: str, value: object) -> None:
    payload = valid_payload()
    payload[field] = value

    with pytest.raises(ValidationError):
        ProfileCreate.model_validate(payload)


@pytest.mark.parametrize(
    ("birth_date", "is_valid"),
    [
        (date.today().replace(year=date.today().year - 18), True),
        (date.today().replace(year=date.today().year - 100), True),
        (date.today().replace(year=date.today().year - 18) + timedelta(days=1), False),
        (date.today().replace(year=date.today().year - 101), False),
        (date.today() + timedelta(days=1), False),
    ],
)
def test_profile_create_validates_age_range(birth_date: date, is_valid: bool) -> None:
    payload = valid_payload()
    payload["birth_date"] = birth_date

    if is_valid:
        assert ProfileCreate.model_validate(payload).birth_date == birth_date
    else:
        with pytest.raises(ValidationError):
            ProfileCreate.model_validate(payload)


def test_profile_update_rejects_empty_body_and_null_required_field() -> None:
    with pytest.raises(ValidationError, match="At least one profile field is required"):
        ProfileUpdate.model_validate({})
    with pytest.raises(ValidationError):
        ProfileUpdate.model_validate({"height_cm": None})


def test_profile_update_allows_clearing_limitations() -> None:
    update = ProfileUpdate.model_validate({"physical_limitations": None})

    assert update.model_fields_set == {"physical_limitations"}


def test_profile_update_normalizes_supplied_text() -> None:
    update = ProfileUpdate.model_validate(
        {"display_name": "  Mohammad  ", "physical_limitations": "  Knee pain  "}
    )

    assert update.display_name == "Mohammad"
    assert update.physical_limitations == "Knee pain"
