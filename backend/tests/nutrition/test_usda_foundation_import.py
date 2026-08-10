from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy.orm import Session


def _nutrient(nutrient_id: int, amount: float, unit: str = "g") -> dict[str, object]:
    return {
        "nutrient": {"id": nutrient_id, "unitName": unit},
        "amount": amount,
    }


def test_foundation_record_maps_required_and_available_optional_nutrients() -> None:
    from app.nutrition.usda_foundation_import import FoundationFoodIdentity, map_foundation_food

    identity = FoundationFoodIdentity(
        fdc_id=999,
        slug="test-food",
        name_fa="ماده آزمایشی",
        category="vegetables",
        role="flexible",
        measurement_basis="raw",
        aliases=("نام دیگر",),
    )
    raw = {
        "fdcId": 999,
        "description": "Test food, raw",
        "foodNutrients": [
            _nutrient(1008, 120, "kcal"),
            _nutrient(1003, 4),
            _nutrient(1004, 2),
            _nutrient(1005, 20),
            _nutrient(1079, 3),
            _nutrient(1089, 1.5, "mg"),
        ],
    }

    payload = map_foundation_food(identity, raw)

    assert payload.verification_status == "verified"
    values = {item.nutrient_code: Decimal(str(item.value_per_100g)) for item in payload.nutrients}
    assert values["energy_kcal"] == Decimal("120")
    assert values["iron_mg"] == Decimal("1.5")
    assert "vitamin_d_mcg" not in values


def test_foundation_record_without_required_fibre_stays_draft() -> None:
    from app.nutrition.usda_foundation_import import FoundationFoodIdentity, map_foundation_food

    identity = FoundationFoodIdentity(
        fdc_id=998,
        slug="incomplete-food",
        name_fa="ماده ناقص",
        category="test",
        role="flexible",
        measurement_basis="raw",
    )
    raw = {
        "fdcId": 998,
        "description": "Incomplete food",
        "foodNutrients": [
            _nutrient(1008, 100, "kcal"),
            _nutrient(1003, 4),
            _nutrient(1004, 2),
            _nutrient(1005, 20),
        ],
    }

    payload = map_foundation_food(identity, raw)

    assert payload.verification_status == "draft"
    assert all(item.nutrient_code != "fibre_g" for item in payload.nutrients)


def test_curated_foundation_vocabulary_materially_expands_the_catalogue() -> None:
    from app.nutrition.usda_foundation_import import CURATED_FOUNDATION_FOODS

    assert len(CURATED_FOUNDATION_FOODS) >= 45
    assert len({item.fdc_id for item in CURATED_FOUNDATION_FOODS}) == len(CURATED_FOUNDATION_FOODS)
    assert len({item.slug for item in CURATED_FOUNDATION_FOODS}) == len(CURATED_FOUNDATION_FOODS)


def test_curated_import_is_idempotent(db: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    from app.nutrition import usda_foundation_import

    identity = usda_foundation_import.CURATED_FOUNDATION_FOODS[0]
    raw = {
        "fdcId": identity.fdc_id,
        "description": "Idempotent food",
        "foodNutrients": [
            _nutrient(1008, 120, "kcal"),
            _nutrient(1003, 4),
            _nutrient(1004, 2),
            _nutrient(1005, 20),
            _nutrient(1079, 3),
        ],
    }

    monkeypatch.setattr(usda_foundation_import, "CURATED_FOUNDATION_FOODS", (identity,))
    monkeypatch.setattr(
        usda_foundation_import,
        "load_foundation_records",
        lambda _: {identity.fdc_id: raw},
    )
    source = Path("not-read.json")
    usda_foundation_import.import_curated_foundation_foods(db, source)
    usda_foundation_import.import_curated_foundation_foods(db, source)
