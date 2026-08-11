from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.nutrition.catalogue_seed_data import (
    APPROVED_FOODS,
    NUTRIENT_UNITS,
    USDA_ACCESS_DATE,
    USDA_DATA_VERSION,
    USDA_SOURCE_NAME,
    USDA_SOURCE_REFERENCE,
    composition_for,
)
from app.nutrition.enums import (
    EstimateConfidence,
    FoodMeasurementBasis,
    FoodVerificationStatus,
)
from app.nutrition.enums import FoodRole as FoodRoleEnum
from app.nutrition.models import (
    NutritionCatalogueFood,
    NutritionCatalogueFoodAlias,
    NutritionCatalogueFoodRole,
    NutritionFoodComposition,
    NutritionFoodPortion,
)
from app.nutrition.schemas import (
    CatalogueFoodResponse,
    CatalogueFoodWrite,
)

REQUIRED_PRIMARY_NUTRIENTS = frozenset(
    {"energy_kcal", "protein_g", "carbohydrate_g", "total_fat_g", "fibre_g"}
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


def scale_nutrient_value_for_grams(value_per_100g: Decimal, grams: Decimal) -> Decimal:
    return value_per_100g * grams / Decimal("100")


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
            selectinload(NutritionCatalogueFood.aliases),
            selectinload(NutritionCatalogueFood.portions),
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
    normalized_aliases = [normalize_food_alias(alias) for alias in payload.aliases]
    if any(not alias for alias in normalized_aliases):
        raise ValueError("Food aliases cannot be empty")
    if len(normalized_aliases) != len(set(normalized_aliases)):
        raise ValueError("Food aliases must be unique")
    nutrients = payload.nutrients
    if len({nutrient.nutrient_code for nutrient in nutrients}) != len(nutrients):
        raise ValueError("Nutrient codes must be unique")
    if payload.verification_status == FoodVerificationStatus.VERIFIED.value:
        missing_primary = REQUIRED_PRIMARY_NUTRIENTS - {
            nutrient.nutrient_code for nutrient in nutrients
        }
        if missing_primary:
            raise ValueError(
                "Verified food requires complete primary nutrients: "
                + ", ".join(sorted(missing_primary))
            )
    food = db.scalar(
        select(NutritionCatalogueFood)
        .where(NutritionCatalogueFood.slug == payload.slug)
        .options(
            selectinload(NutritionCatalogueFood.roles),
            selectinload(NutritionCatalogueFood.compositions),
            selectinload(NutritionCatalogueFood.aliases),
            selectinload(NutritionCatalogueFood.portions),
        )
    )
    if food is None:
        food = NutritionCatalogueFood(slug=payload.slug)
        db.add(food)
    else:
        food.roles.clear()
        food.aliases.clear()
        food.compositions.clear()
        food.portions.clear()
        db.flush()
    food.name_fa = payload.name_fa
    food.name_en = payload.name_en
    food.verification_status = FoodVerificationStatus(payload.verification_status)
    food.source_name = payload.source_name
    food.source_reference = payload.source_reference
    food.source_food_id = payload.source_food_id
    food.category = payload.category
    food.measurement_basis = payload.measurement_basis
    food.canonical_quantity = Decimal(str(payload.canonical_quantity))
    food.canonical_unit = payload.canonical_unit
    food.edible_portion = Decimal(str(payload.edible_portion))
    food.data_version = payload.data_version
    food.source_access_date = payload.source_access_date
    food.dietary_patterns = payload.dietary_patterns
    food.roles = [NutritionCatalogueFoodRole(role=role) for role in roles]
    food.aliases = [
        NutritionCatalogueFoodAlias(
            alias=alias,
            normalized_alias=normalized,
            language="fa" if any("\u0600" <= char <= "\u06ff" for char in alias) else "en",
        )
        for alias, normalized in zip(payload.aliases, normalized_aliases, strict=True)
    ]
    food.compositions = [
        NutritionFoodComposition(
            nutrient_code=nutrient.nutrient_code,
            value_per_100g=Decimal(str(nutrient.value_per_100g)),
            unit=nutrient.unit,
            unit_form=nutrient.unit_form,
            source_name=nutrient.source_name,
            source_reference=nutrient.source_reference,
            source_food_id=payload.source_food_id,
            data_version=payload.data_version,
            source_access_date=payload.source_access_date,
            confidence=EstimateConfidence(nutrient.confidence),
        )
        for nutrient in nutrients
    ]
    if len([portion for portion in payload.portions if portion.is_default]) > 1:
        raise ValueError("Only one default food portion is allowed")
    food.portions = [NutritionFoodPortion(**portion.model_dump()) for portion in payload.portions]
    db.commit()
    db.refresh(food)
    return _food_response(food)


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
        category=food.category,
        measurement_basis=food.measurement_basis,
        canonical_quantity=float(food.canonical_quantity),
        canonical_unit=food.canonical_unit,
        edible_portion=float(food.edible_portion),
        data_version=food.data_version,
        source_access_date=food.source_access_date,
        aliases=[alias.alias for alias in food.aliases],
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
        portions=[
            {
                "code": item.code,
                "quantity": item.quantity,
                "label_fa": item.label_fa,
                "label_en": item.label_en,
                "grams": item.grams,
                "is_default": item.is_default,
                "sort_order": item.sort_order,
                "source_name": item.source_name,
                "source_reference": item.source_reference,
            }
            for item in food.portions
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


def seed_base_iranian_food_catalogue(
    db: Session, *, commit: bool = True
) -> list[NutritionCatalogueFood]:
    """Upsert the approved identities and only verify source-backed compositions."""
    for legacy_slug in ("cooked-basmati-rice", "grilled-chicken-breast"):
        legacy = db.scalar(
            select(NutritionCatalogueFood).where(NutritionCatalogueFood.slug == legacy_slug)
        )
        if legacy is not None:
            legacy.verification_status = FoodVerificationStatus.RETIRED

    seeded: list[NutritionCatalogueFood] = []
    for item in APPROVED_FOODS:
        nutrients = composition_for(item.slug)
        food = db.scalar(
            select(NutritionCatalogueFood)
            .where(NutritionCatalogueFood.slug == item.slug)
            .options(
                selectinload(NutritionCatalogueFood.roles),
                selectinload(NutritionCatalogueFood.aliases),
                selectinload(NutritionCatalogueFood.compositions),
                selectinload(NutritionCatalogueFood.portions),
            )
        )
        if food is None:
            food = NutritionCatalogueFood(slug=item.slug)
            db.add(food)
        else:
            food.roles.clear()
            food.aliases.clear()
            food.compositions.clear()
            food.portions.clear()
            db.flush()
        food.name_fa = item.name_fa
        food.name_en = item.name_en
        food.category = item.category
        food.measurement_basis = FoodMeasurementBasis(item.measurement_basis)
        food.canonical_quantity = Decimal("100")
        food.canonical_unit = "g"
        food.edible_portion = Decimal("1")
        food.source_name = USDA_SOURCE_NAME if nutrients else "Fitsho approved vocabulary"
        food.source_reference = USDA_SOURCE_REFERENCE
        food.source_food_id = item.source_food_id
        food.data_version = USDA_DATA_VERSION if nutrients else "awaiting-regional-source"
        food.source_access_date = date.fromisoformat(USDA_ACCESS_DATE) if nutrients else None
        food.verification_status = (
            FoodVerificationStatus.VERIFIED if nutrients else FoodVerificationStatus.DRAFT
        )
        food.dietary_patterns = _dietary_patterns_for_slug(item.slug)
        food.roles = [NutritionCatalogueFoodRole(role=FoodRoleEnum(role)) for role in item.roles]
        food.aliases = [
            NutritionCatalogueFoodAlias(
                alias=alias,
                normalized_alias=normalize_food_alias(alias),
                language="fa" if any("\u0600" <= char <= "\u06ff" for char in alias) else "en",
            )
            for alias in dict.fromkeys(item.aliases)
        ]
        food.compositions = [
            NutritionFoodComposition(
                nutrient_code=code,
                value_per_100g=value,
                unit=NUTRIENT_UNITS[code],
                unit_form=(
                    "dietary_folate_equivalents" if code == "folate_dfe_mcg" else "nutrient_mass"
                ),
                source_name=USDA_SOURCE_NAME,
                source_reference=USDA_SOURCE_REFERENCE,
                source_food_id=item.source_food_id,
                data_version=USDA_DATA_VERSION,
                source_access_date=date.fromisoformat(USDA_ACCESS_DATE),
                confidence=EstimateConfidence.HIGH,
            )
            for code, value in nutrients.items()
        ]
        food.portions = [
            NutritionFoodPortion(
                code=portion.code,
                quantity=portion.quantity,
                label_fa=portion.label_fa,
                label_en=portion.label_en,
                grams=portion.grams,
                is_default=portion.is_default,
                sort_order=portion.sort_order,
                source_name=portion.source_name,
                source_reference=portion.source_reference,
            )
            for portion in item.portions
        ]
        seeded.append(food)
    if commit:
        db.commit()
    else:
        db.flush()
    return seeded


def normalize_food_alias(value: str) -> str:
    return " ".join(value.strip().casefold().replace("ي", "ی").replace("ك", "ک").split())


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
