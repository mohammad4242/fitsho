from collections import Counter
from decimal import Decimal

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.nutrition.enums import (
    FoodMeasurementBasis,
    FoodVerificationStatus,
    NutritionProgramSlotKind,
)
from app.nutrition.food_catalogue import seed_base_iranian_food_catalogue
from app.nutrition.meal_catalogue import seed_meal_catalogue
from app.nutrition.models import NutritionCatalogueFood, NutritionCatalogueMeal, NutritionProgram
from app.nutrition.program_catalogue_seed_data import (
    CANONICAL_MEAL_REGISTRY,
    PROGRAM_WEEKS,
)
from app.nutrition.seed_program_catalogue import seed_program_catalogue


def _seed_dependencies(db: Session) -> None:
    seed_base_iranian_food_catalogue(db, commit=False)
    for slug, name in (
        ("creamy-peanut-butter", "کره بادام‌زمینی"),
        ("wheat-flour", "آرد گندم"),
        ("green-beans", "لوبیا سبز"),
        ("tomato-paste", "رب گوجه‌فرنگی"),
    ):
        if db.scalar(select(NutritionCatalogueFood.id).where(NutritionCatalogueFood.slug == slug)):
            continue
        db.add(
            NutritionCatalogueFood(
                slug=slug,
                name_fa=name,
                name_en=slug.replace("-", " ").title(),
                verification_status=FoodVerificationStatus.VERIFIED,
                source_name="test fixture",
                source_reference="https://fdc.nal.usda.gov/",
                category="ingredient",
                measurement_basis=FoodMeasurementBasis.AS_PURCHASED,
                canonical_quantity=Decimal("100"),
                canonical_unit="g",
                edible_portion=Decimal("1"),
                data_version="test",
                dietary_patterns=["omnivore", "vegetarian", "vegan"],
            )
        )
    db.flush()
    seed_meal_catalogue(db)


def test_seed_creates_exactly_25_programs_and_five_per_style(db: Session) -> None:
    _seed_dependencies(db)

    first = seed_program_catalogue(db)
    second = seed_program_catalogue(db)

    assert len(first) == len(second) == 25
    assert {program.code for program in first} == set(PROGRAM_WEEKS)
    assert Counter(program.diet_style.value for program in first) == {
        "economy": 5,
        "balanced_iranian": 5,
        "high_protein_gym": 5,
        "quick_easy": 5,
        "premium_varied": 5,
    }
    assert db.scalar(select(func.count()).select_from(NutritionProgram)) == 25


def test_seed_uses_only_exact_verified_canonical_meals(db: Session) -> None:
    _seed_dependencies(db)
    programs = seed_program_catalogue(db)

    referenced = {
        slot.meal.code: slot.meal.id
        for program in programs
        for day in program.days
        for slot in day.slots
        if slot.meal is not None
    }
    assert referenced == {
        code: canonical.id
        for code, canonical in CANONICAL_MEAL_REGISTRY.items()
        if code != "PW01"
        and any(code in row.split() for week in PROGRAM_WEEKS.values() for row in week)
    }
    for code, canonical in CANONICAL_MEAL_REGISTRY.items():
        row = db.scalar(select(NutritionCatalogueMeal).where(NutritionCatalogueMeal.code == code))
        assert row is not None
        assert row.id == canonical.id
        assert row.category is canonical.category
        assert row.name_fa
        assert row.verification_status is FoodVerificationStatus.VERIFIED


def test_seed_enforces_friday_gym_and_economy_rules(db: Session) -> None:
    _seed_dependencies(db)
    programs = seed_program_catalogue(db)

    for program in programs:
        friday = program.days[6]
        assert sum(slot.kind is NutritionProgramSlotKind.FREE_MEAL for slot in friday.slots) == 1
        assert next(slot for slot in friday.slots if slot.category.value == "lunch").meal is None
        if program.code.startswith("GYM"):
            breakfasts = {
                next(slot.meal.code for slot in day.slots if slot.category.value == "breakfast")
                for day in program.days
            }
            lunch_codes = [
                slot.meal.code
                for day in program.days
                for slot in day.slots
                if slot.meal is not None and slot.category.value == "lunch"
            ]
            assert breakfasts <= {"BF01", "BF02", "BF05"}
            assert lunch_codes.count("LU12") == 1
            assert "LU13" in lunch_codes
        if program.code.startswith("ECO"):
            codes = {
                slot.meal.code
                for day in program.days
                for slot in day.slots
                if slot.meal is not None
            }
            assert codes.isdisjoint({"LU03", "LU04", "LU05", "LU12", "LU13", "DN03", "DN08"})

    assert (
        db.scalar(select(NutritionCatalogueMeal).where(NutritionCatalogueMeal.code == "FREE_MEAL"))
        is None
    )


def test_seed_fails_when_canonical_meal_is_not_verified(db: Session) -> None:
    _seed_dependencies(db)
    meal = db.get(NutritionCatalogueMeal, CANONICAL_MEAL_REGISTRY["BF01"].id)
    assert meal is not None
    meal.verification_status = FoodVerificationStatus.DRAFT
    db.commit()

    with pytest.raises(ValueError, match="BF01"):
        seed_program_catalogue(db)
