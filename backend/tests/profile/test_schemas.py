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
        "training_age_months": 24,
        "training_days_per_week": 3,
        "preferred_weekdays": [0, 2, 4],
        "priority_muscles": ["back", "glutes"],
        "training_location": "gym",
        "home_training_setup": None,
        "session_duration_minutes": 60,
        "physical_limitations": "   ",
    }


def test_profile_create_normalizes_text_and_decimal() -> None:
    profile = ProfileCreate.model_validate(valid_payload())

    assert profile.display_name == "Mohammad"
    assert profile.current_weight_kg == Decimal("76.50")
    assert profile.physical_limitations is None
    assert profile.training_age_months == 24
    assert profile.preferred_weekdays == (0, 2, 4)
    assert profile.priority_muscles == ("back", "glutes")


def test_profile_create_accepts_optional_circumference_measurements() -> None:
    profile = ProfileCreate.model_validate(
        {
            **valid_payload(),
            "shoulder_circumference_cm": "122.5",
            "waist_circumference_cm": "84.0",
            "hip_circumference_cm": "98.25",
        }
    )

    assert profile.shoulder_circumference_cm == Decimal("122.50")
    assert profile.waist_circumference_cm == Decimal("84.00")
    assert profile.hip_circumference_cm == Decimal("98.25")


def test_calculate_age_handles_birthday_boundary() -> None:
    today = date(2026, 7, 27)

    assert calculate_age(date(2008, 7, 27), today) == 18
    assert calculate_age(date(2008, 7, 28), today) == 17


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("height_cm", 119),
        ("height_cm", 231),
        ("current_weight_kg", "34.99"),
        ("current_weight_kg", "300.01"),
        ("current_weight_kg", "70.123"),
        ("shoulder_circumference_cm", "39.99"),
        ("waist_circumference_cm", "250.01"),
        ("hip_circumference_cm", "98.123"),
        ("training_days_per_week", 0),
        ("training_days_per_week", 1),
        ("training_days_per_week", 7),
        ("training_days_per_week", 8),
        ("training_age_months", -1),
        ("training_age_months", 901),
        ("preferred_weekdays", [0, 0]),
        ("preferred_weekdays", [7]),
        ("priority_muscles", ["back", "back"]),
        ("priority_muscles", ["not_a_muscle"]),
        ("sex", "unknown"),
        ("fitness_goal", "bulk"),
        ("experience_level", "expert"),
        ("training_location", "outdoors"),
        ("home_training_setup", "barbell"),
        ("session_duration_minutes", 50),
    ],
)
def test_profile_create_rejects_invalid_values(field: str, value: object) -> None:
    payload = valid_payload()
    payload[field] = value

    with pytest.raises(ValidationError):
        ProfileCreate.model_validate(payload)


def test_profile_create_accepts_six_training_days() -> None:
    payload = valid_payload()
    payload["experience_level"] = "intermediate"
    payload["training_days_per_week"] = 6

    assert ProfileCreate.model_validate(payload).training_days_per_week == 6


def test_profile_create_rejects_more_preferred_weekdays_than_training_days() -> None:
    payload = {**valid_payload(), "training_days_per_week": 2, "preferred_weekdays": [0, 2, 4]}

    with pytest.raises(ValidationError, match="Preferred weekdays"):
        ProfileCreate.model_validate(payload)


def test_profile_update_validates_preferred_weekday_count_when_supplied() -> None:
    assert ProfileUpdate.model_validate(
        {"training_days_per_week": 3, "preferred_weekdays": [0, 2, 4]}
    ).preferred_weekdays == (0, 2, 4)

    with pytest.raises(ValidationError, match="Preferred weekdays"):
        ProfileUpdate.model_validate({"training_days_per_week": 2, "preferred_weekdays": [0, 2, 4]})


def test_profile_update_accepts_and_bounds_training_age() -> None:
    assert ProfileUpdate.model_validate({"training_age_months": 36}).training_age_months == 36

    with pytest.raises(ValidationError):
        ProfileUpdate.model_validate({"training_age_months": -1})
    with pytest.raises(ValidationError):
        ProfileUpdate.model_validate({"training_age_months": 901})


@pytest.mark.parametrize(
    "goal",
    ["lose_weight", "gain_weight", "fat_loss", "build_muscle", "body_recomposition"],
)
def test_profile_create_accepts_the_five_supported_goals(goal: str) -> None:
    payload = valid_payload()
    payload["fitness_goal"] = goal

    assert ProfileCreate.model_validate(payload).fitness_goal.value == goal


def test_profile_create_accepts_the_ninety_plus_workout_duration() -> None:
    payload = valid_payload()
    payload["session_duration_minutes"] = 120

    assert ProfileCreate.model_validate(payload).session_duration_minutes == 120


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


def test_home_profile_requires_training_setup() -> None:
    payload = {**valid_payload(), "training_location": "home", "home_training_setup": None}

    with pytest.raises(ValidationError, match="Home training setup is required"):
        ProfileCreate.model_validate(payload)


def test_explicit_home_equipment_replaces_legacy_setup_and_is_canonicalized() -> None:
    payload = {
        **valid_payload(),
        "training_location": "home",
        "home_training_setup": None,
        "available_equipment": ["resistance_band", "bodyweight", "bench"],
    }

    profile = ProfileCreate.model_validate(payload)

    assert profile.available_equipment == ("bench", "bodyweight", "resistance_band")


@pytest.mark.parametrize(
    "available_equipment",
    [[], ["bodyweight", "bodyweight"], ["other"], ["unknown"]],
)
def test_profile_rejects_invalid_explicit_equipment_inventory(
    available_equipment: list[str],
) -> None:
    with pytest.raises(ValidationError):
        ProfileCreate.model_validate(
            {
                **valid_payload(),
                "training_location": "home",
                "home_training_setup": None,
                "available_equipment": available_equipment,
            }
        )


def test_gym_profile_normalizes_home_training_setup_to_none() -> None:
    payload = {
        **valid_payload(),
        "training_location": "gym",
        "home_training_setup": "dumbbells_available",
    }

    profile = ProfileCreate.model_validate(payload)

    assert profile.home_training_setup is None


def test_profile_update_normalizes_home_setup_for_gym() -> None:
    update = ProfileUpdate.model_validate(
        {
            "training_location": "gym",
            "home_training_setup": "bodyweight_only",
        }
    )

    assert update.home_training_setup is None
