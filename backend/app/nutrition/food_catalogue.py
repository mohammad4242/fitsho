from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.nutrition.enums import EstimateConfidence, FoodVerificationStatus, MealSlotRole
from app.nutrition.enums import FoodRole as FoodRoleEnum
from app.nutrition.models import (
    NutritionCatalogueFood,
    NutritionCatalogueFoodRole,
    NutritionCatalogueMeal,
    NutritionCatalogueMealItem,
    NutritionFoodComposition,
)
from app.nutrition.schemas import (
    CatalogueFoodResponse,
    CatalogueFoodWrite,
    CatalogueMealResponse,
    CatalogueMealWrite,
)


class FoodImportValidationError(ValueError):
    pass


class FoodRole:
    MAIN_PROTEIN = "main_protein"
    MAIN_STAPLE = "main_staple"
    SNACK = "snack"
    FLEXIBLE = "flexible"


CANONICAL_UNITS = {"g": Decimal("1"), "kg": Decimal("1000")}


@dataclass(frozen=True)
class FoodCompositionValue:
    nutrient_code: str
    value_per_100g: Decimal
    unit: str


def normalize_food_import(raw: dict[str, Any]) -> dict[str, Any]:
    try:
        quantity = Decimal(str(raw["quantity"]))
        unit = str(raw["quantity_unit"])
    except (KeyError, ArithmeticError) as error:
        raise FoodImportValidationError("Quantity and quantity unit are required") from error
    if unit not in CANONICAL_UNITS:
        raise FoodImportValidationError(f"Unsupported quantity unit: {unit}")
    if quantity <= 0:
        raise FoodImportValidationError("Quantity must be positive")
    nutrients = raw.get("nutrients", [])
    if not isinstance(nutrients, list):
        raise FoodImportValidationError("Nutrients must be a list")
    codes = [item.get("nutrient_code") for item in nutrients if isinstance(item, dict)]
    if len(codes) != len(set(codes)):
        raise FoodImportValidationError("Nutrient codes must be unique")
    return {
        **raw,
        "canonical_grams": quantity * CANONICAL_UNITS[unit],
        "nutrients": nutrients,
    }


def calculate_meal_totals(
    items: list[tuple[Decimal, list[FoodCompositionValue]]],
) -> dict[str, Decimal | None]:
    seen_codes = {value.nutrient_code for _, values in items for value in values}
    totals: dict[str, Decimal | None] = {
        code: sum(
            (
                grams * value.value_per_100g / Decimal("100")
                for grams, values in items
                for value in values
                if value.nutrient_code == code
            ),
            Decimal("0"),
        )
        for code in seen_codes
    }
    for core_code in ("energy_kcal", "protein_g", "sodium_mg"):
        totals.setdefault(core_code, None)
    return totals


def validate_meal_roles(slot_role: str, food_roles: list[str]) -> None:
    if not food_roles:
        raise ValueError("Meal requires at least one food")
    if slot_role == "main_meal" and not {
        FoodRole.MAIN_PROTEIN,
        FoodRole.MAIN_STAPLE,
    }.intersection(food_roles):
        raise ValueError("Main meal requires a main eligible food")
    if slot_role == "snack" and any(
        role in {FoodRole.MAIN_PROTEIN, FoodRole.MAIN_STAPLE} for role in food_roles
    ):
        raise ValueError("Snack can only contain snack or flexible foods")


def list_verified_foods(db: Session) -> list[CatalogueFoodResponse]:
    foods = db.scalars(
        select(NutritionCatalogueFood)
        .where(NutritionCatalogueFood.verification_status == FoodVerificationStatus.VERIFIED)
        .options(
            selectinload(NutritionCatalogueFood.roles),
            selectinload(NutritionCatalogueFood.compositions),
        )
        .order_by(NutritionCatalogueFood.name_en)
    ).all()
    return [_food_response(food) for food in foods]


def save_catalogue_food(db: Session, payload: CatalogueFoodWrite) -> CatalogueFoodResponse:
    roles = [FoodRoleEnum(role) for role in payload.roles]
    if len(roles) != len(set(roles)):
        raise ValueError("Food roles must be unique")
    allowed_patterns = {"omnivore", "vegetarian", "vegan"}
    if set(payload.dietary_patterns) - allowed_patterns:
        raise ValueError("Unknown dietary pattern")
    if len(payload.dietary_patterns) != len(set(payload.dietary_patterns)):
        raise ValueError("Dietary patterns must be unique")
    nutrients = payload.nutrients
    if len({nutrient.nutrient_code for nutrient in nutrients}) != len(nutrients):
        raise ValueError("Nutrient codes must be unique")
    food = db.scalar(
        select(NutritionCatalogueFood)
        .where(NutritionCatalogueFood.slug == payload.slug)
        .options(
            selectinload(NutritionCatalogueFood.roles),
            selectinload(NutritionCatalogueFood.compositions),
        )
    )
    if food is None:
        food = NutritionCatalogueFood(slug=payload.slug)
        db.add(food)
    food.name_fa = payload.name_fa
    food.name_en = payload.name_en
    food.verification_status = FoodVerificationStatus(payload.verification_status)
    food.source_name = payload.source_name
    food.source_reference = payload.source_reference
    food.source_food_id = payload.source_food_id
    food.dietary_patterns = payload.dietary_patterns
    food.roles = [NutritionCatalogueFoodRole(role=role) for role in roles]
    food.compositions = [
        NutritionFoodComposition(
            nutrient_code=nutrient.nutrient_code,
            value_per_100g=Decimal(str(nutrient.value_per_100g)),
            unit=nutrient.unit,
            unit_form=nutrient.unit_form,
            source_name=nutrient.source_name,
            source_reference=nutrient.source_reference,
            confidence=EstimateConfidence(nutrient.confidence),
        )
        for nutrient in nutrients
    ]
    db.commit()
    db.refresh(food)
    return _food_response(food)


def save_catalogue_meal(db: Session, payload: CatalogueMealWrite) -> CatalogueMealResponse:
    foods = {
        food.id: food
        for food in db.scalars(
            select(NutritionCatalogueFood)
            .where(NutritionCatalogueFood.id.in_([item.food_id for item in payload.items]))
            .options(
                selectinload(NutritionCatalogueFood.roles),
                selectinload(NutritionCatalogueFood.compositions),
            )
        ).all()
    }
    if len(foods) != len(payload.items):
        raise ValueError("Every meal food must exist")
    role_values = [role.role.value for item in payload.items for role in foods[item.food_id].roles]
    validate_meal_roles(payload.slot_role, role_values)
    meal = NutritionCatalogueMeal(
        name_fa=payload.name_fa,
        name_en=payload.name_en,
        slot_role=MealSlotRole(payload.slot_role),
        verification_status=FoodVerificationStatus(payload.verification_status),
        items=[
            NutritionCatalogueMealItem(food_id=item.food_id, grams=Decimal(str(item.grams)))
            for item in payload.items
        ],
    )
    db.add(meal)
    db.commit()
    db.refresh(meal)
    totals = calculate_meal_totals(
        [
            (
                Decimal(str(item.grams)),
                [
                    FoodCompositionValue(value.nutrient_code, value.value_per_100g, value.unit)
                    for value in foods[item.food_id].compositions
                ],
            )
            for item in payload.items
        ]
    )
    return CatalogueMealResponse(
        id=meal.id,
        **payload.model_dump(),
        totals={
            code: float(value) if value is not None else None for code, value in totals.items()
        },
    )


def retire_catalogue_food(db: Session, slug: str) -> None:
    food = db.scalar(select(NutritionCatalogueFood).where(NutritionCatalogueFood.slug == slug))
    if food is None:
        raise ValueError("Food not found")
    food.verification_status = FoodVerificationStatus.RETIRED
    db.commit()


def _food_response(food: NutritionCatalogueFood) -> CatalogueFoodResponse:
    return CatalogueFoodResponse(
        id=food.id,
        slug=food.slug,
        name_fa=food.name_fa,
        name_en=food.name_en,
        verification_status=food.verification_status.value,
        source_name=food.source_name,
        source_reference=food.source_reference,
        source_food_id=food.source_food_id,
        dietary_patterns=food.dietary_patterns,
        roles=[role.role.value for role in food.roles],
        nutrients=[
            {
                "nutrient_code": item.nutrient_code,
                "value_per_100g": float(item.value_per_100g),
                "unit": item.unit,
                "unit_form": item.unit_form,
                "source_name": item.source_name,
                "source_reference": item.source_reference,
                "confidence": item.confidence,
            }
            for item in food.compositions
        ],
    )


def seed_verified_iranian_foods(db: Session) -> list[CatalogueFoodResponse]:
    source = "USDA FoodData Central verified mapping"
    reference = "https://fdc.nal.usda.gov/"
    seeds: list[dict[str, Any]] = [
        {
            "slug": "cooked-basmati-rice",
            "name_fa": "برنج باسماتی پخته",
            "name_en": "Cooked basmati rice",
            "roles": ["main_staple"],
            "nutrients": [
                {"nutrient_code": "energy_kcal", "value_per_100g": 121, "unit": "kcal"},
                {"nutrient_code": "protein_g", "value_per_100g": 2.5, "unit": "g"},
                {"nutrient_code": "carbohydrate_g", "value_per_100g": 25.2, "unit": "g"},
            ],
        },
        {
            "slug": "grilled-chicken-breast",
            "name_fa": "سینه مرغ گریل‌شده",
            "name_en": "Grilled chicken breast",
            "roles": ["main_protein"],
            "nutrients": [
                {"nutrient_code": "energy_kcal", "value_per_100g": 165, "unit": "kcal"},
                {"nutrient_code": "protein_g", "value_per_100g": 31, "unit": "g"},
                {"nutrient_code": "total_fat_g", "value_per_100g": 3.6, "unit": "g"},
            ],
        },
        {
            "slug": "plain-yogurt",
            "name_fa": "ماست ساده",
            "name_en": "Plain yogurt",
            "roles": ["snack", "flexible"],
            "nutrients": [
                {"nutrient_code": "energy_kcal", "value_per_100g": 61, "unit": "kcal"},
                {"nutrient_code": "protein_g", "value_per_100g": 3.5, "unit": "g"},
                {"nutrient_code": "calcium_mg", "value_per_100g": 121, "unit": "mg"},
            ],
        },
    ]
    return [
        save_catalogue_food(
            db,
            CatalogueFoodWrite(
                **food,
                verification_status="verified",
                source_name=source,
                source_reference=reference,
                source_food_id=None,
                dietary_patterns=_dietary_patterns_for_slug(food["slug"]),
                nutrients=[
                    {
                        **nutrient,
                        "unit_form": "nutrient_mass",
                        "source_name": source,
                        "source_reference": reference,
                        "confidence": "high",
                    }
                    for nutrient in food["nutrients"]
                ],
            ),
        )
        for food in seeds
    ]


def seed_base_iranian_food_catalogue(db: Session) -> list[NutritionCatalogueFood]:
    """Create the approved base-food vocabulary; composition verification is separate."""
    groups: dict[str, tuple[tuple[str, str, str], ...]] = {
        FoodRole.MAIN_PROTEIN: (
            ("chicken-breast", "سینه مرغ", "Chicken breast"),
            ("chicken-thigh-skinless", "ران مرغ بدون پوست", "Skinless chicken thigh"),
            ("beef", "گوشت گوساله", "Beef"),
            ("lamb", "گوشت گوسفند", "Lamb"),
            ("white-fish", "ماهی سفید", "White fish"),
            ("rainbow-trout", "ماهی قزل‌آلا", "Rainbow trout"),
            ("canned-tuna", "تن ماهی", "Canned tuna"),
            ("egg", "تخم‌مرغ", "Egg"),
            ("lentils", "عدس", "Lentils"),
            ("chickpeas", "نخود", "Chickpeas"),
            ("pinto-beans", "لوبیا چیتی", "Pinto beans"),
            ("red-kidney-beans", "لوبیا قرمز", "Red kidney beans"),
            ("white-beans", "لوبیا سفید", "White beans"),
            ("black-eyed-peas", "لوبیا چشم‌بلبلی", "Black-eyed peas"),
            ("split-peas", "لپه", "Split peas"),
            ("mung-beans", "ماش", "Mung beans"),
            ("soybeans", "سویا", "Soybeans"),
        ),
        FoodRole.MAIN_STAPLE: (
            ("basmati-rice", "برنج", "Basmati rice"),
            ("sangak-bread", "نان سنگک", "Sangak bread"),
            ("barbari-bread", "نان بربری", "Barbari bread"),
            ("lavash-bread", "نان لواش", "Lavash bread"),
            ("taftoon-bread", "نان تافتون", "Taftoon bread"),
            ("oats", "جو دوسر", "Oats"),
            ("barley", "جو", "Barley"),
            ("potato", "سیب‌زمینی", "Potato"),
            ("corn", "ذرت", "Corn"),
            ("pasta", "ماکارونی", "Pasta"),
        ),
        FoodRole.FLEXIBLE: (
            ("milk", "شیر", "Milk"),
            ("plain-yogurt", "ماست ساده", "Plain yogurt"),
            ("low-fat-cheese", "پنیر کم‌چرب", "Low-fat cheese"),
            ("tomato", "گوجه‌فرنگی", "Tomato"),
            ("cucumber", "خیار", "Cucumber"),
            ("onion", "پیاز", "Onion"),
            ("carrot", "هویج", "Carrot"),
            ("lettuce", "کاهو", "Lettuce"),
            ("cabbage", "کلم", "Cabbage"),
            ("spinach", "اسفناج", "Spinach"),
            ("zucchini", "کدو سبز", "Zucchini"),
            ("eggplant", "بادمجان", "Eggplant"),
            ("bell-pepper", "فلفل دلمه‌ای", "Bell pepper"),
            ("mushroom", "قارچ", "Mushroom"),
            ("celery", "کرفس", "Celery"),
            ("broccoli", "بروکلی", "Broccoli"),
            ("cauliflower", "گل‌کلم", "Cauliflower"),
            ("mixed-herbs", "سبزی خوردن", "Mixed fresh herbs"),
            ("olive-oil", "روغن زیتون", "Olive oil"),
            ("vegetable-oil", "روغن مایع", "Vegetable oil"),
            ("butter", "کره", "Butter"),
            ("walnuts", "گردو", "Walnuts"),
            ("almonds", "بادام", "Almonds"),
            ("peanuts", "بادام‌زمینی", "Peanuts"),
            ("sesame", "کنجد", "Sesame"),
            ("tahini", "ارده", "Tahini"),
        ),
        FoodRole.SNACK: (
            ("apple", "سیب", "Apple"),
            ("banana", "موز", "Banana"),
            ("orange", "پرتقال", "Orange"),
            ("tangerine", "نارنگی", "Tangerine"),
            ("kiwi", "کیوی", "Kiwi"),
            ("pomegranate", "انار", "Pomegranate"),
            ("grapes", "انگور", "Grapes"),
            ("dates", "خرما", "Dates"),
            ("raisins", "کشمش", "Raisins"),
            ("strawberries", "توت‌فرنگی", "Strawberries"),
            ("watermelon", "هندوانه", "Watermelon"),
            ("melon", "خربزه", "Melon"),
        ),
    }
    created: list[NutritionCatalogueFood] = []
    for role, foods in groups.items():
        for slug, name_fa, name_en in foods:
            food = db.scalar(
                select(NutritionCatalogueFood).where(NutritionCatalogueFood.slug == slug)
            )
            if food is None:
                food = NutritionCatalogueFood(
                    slug=slug,
                    name_fa=name_fa,
                    name_en=name_en,
                    verification_status=FoodVerificationStatus.DRAFT,
                    source_name="Fitsho approved Iranian base-food vocabulary",
                    source_reference="https://fdc.nal.usda.gov/",
                    dietary_patterns=_dietary_patterns_for_slug(slug),
                    roles=[NutritionCatalogueFoodRole(role=FoodRoleEnum(role))],
                )
                db.add(food)
                created.append(food)
    db.commit()
    return created


def _dietary_patterns_for_slug(slug: str) -> list[str]:
    omnivore_only = {
        "chicken-breast",
        "chicken-thigh-skinless",
        "beef",
        "lamb",
        "white-fish",
        "rainbow-trout",
        "canned-tuna",
        "grilled-chicken-breast",
    }
    vegetarian = {"egg", "milk", "plain-yogurt", "low-fat-cheese", "butter"}
    if slug in omnivore_only:
        return ["omnivore"]
    if slug in vegetarian:
        return ["omnivore", "vegetarian"]
    return ["omnivore", "vegetarian", "vegan"]
