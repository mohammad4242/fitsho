"""Import a curated base-food subset from the official USDA Foundation Foods download."""

from __future__ import annotations

import json
from argparse import ArgumentParser
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.config import get_settings
from app.database.session import get_engine
from app.nutrition.food_catalogue import REQUIRED_PRIMARY_NUTRIENTS, save_catalogue_food
from app.nutrition.schemas import CatalogueFoodWrite

SOURCE_NAME = "USDA FoodData Central Foundation Foods"
SOURCE_REFERENCE = "https://fdc.nal.usda.gov/download-datasets/"
DATA_VERSION = "foundation-2026-04"
SOURCE_ACCESS_DATE = date(2026, 8, 10)


@dataclass(frozen=True)
class FoundationFoodIdentity:
    fdc_id: int
    slug: str
    name_fa: str
    category: str
    role: str
    measurement_basis: str
    aliases: tuple[str, ...] = ()
    name_en: str | None = None


def _food(
    fdc_id: int,
    slug: str,
    name_fa: str,
    category: str,
    *aliases: str,
    role: str = "flexible",
    basis: str = "raw",
    name_en: str | None = None,
) -> FoundationFoodIdentity:
    return FoundationFoodIdentity(
        fdc_id=fdc_id,
        slug=slug,
        name_fa=name_fa,
        category=category,
        role=role,
        measurement_basis=basis,
        aliases=aliases,
        name_en=name_en,
    )


CURATED_FOUNDATION_FOODS = (
    _food(321358, "commercial-hummus", "حمص", "legumes", "هوموس", basis="as_purchased"),
    _food(321360, "grape-tomato", "گوجه گیلاسی", "vegetables", "گوجه‌فرنگی گیلاسی"),
    _food(323505, "kale", "کلم کیل", "vegetables", "کلم‌برگ"),
    _food(324653, "dill-pickles", "خیارشور", "vegetables", "خیار شور", basis="as_purchased"),
    _food(325430, "yellow-peach", "هلو", "fruit", "هلوی زرد", role="snack"),
    _food(
        325524,
        "roasted-sunflower-seeds",
        "تخمه آفتابگردان بوداده",
        "nuts_seeds",
        "تخمه آفتاب‌گردان",
        basis="as_purchased",
    ),
    _food(327357, "nectarine", "شلیل", "fruit", role="snack"),
    _food(332791, "green-olives", "زیتون سبز", "fruit", basis="as_purchased"),
    _food(746768, "dried-figs", "انجیر خشک", "fruit", role="snack", basis="as_purchased"),
    _food(746769, "romaine-lettuce", "کاهوی رومی", "vegetables"),
    _food(746773, "bartlett-pear", "گلابی", "fruit", "گلابی بارتلت", role="snack"),
    _food(
        790018,
        "wheat-flour",
        "آرد گندم سفید",
        "grains",
        "آرد سفید",
        role="main_staple",
        basis="dry",
    ),
    _food(
        790085,
        "whole-wheat-flour",
        "آرد گندم کامل",
        "grains",
        "آرد سبوس‌دار",
        role="main_staple",
        basis="dry",
    ),
    _food(
        790214,
        "white-rice-flour",
        "آرد برنج سفید",
        "grains",
        "آرد برنج",
        role="main_staple",
        basis="dry",
    ),
    _food(
        790276,
        "yellow-corn-flour",
        "آرد ذرت زرد",
        "grains",
        "آرد ذرت",
        role="main_staple",
        basis="dry",
    ),
    _food(790577, "red-onion", "پیاز قرمز", "vegetables"),
    _food(1104647, "garlic", "سیر", "vegetables", "سیر خام"),
    _food(1750340, "fuji-apple", "سیب فوجی", "fruit", role="snack"),
    _food(1999627, "oyster-mushroom", "قارچ صدفی", "vegetables"),
    _food(1999628, "shiitake-mushroom", "قارچ شیتاکه", "vegetables"),
    _food(1999629, "white-button-mushroom", "قارچ دکمه‌ای سفید", "vegetables", "قارچ سفید"),
    _food(
        1999630,
        "unsweetened-soy-milk",
        "شیر سویا بدون شکر",
        "dairy",
        "شیر سویا",
        basis="as_purchased",
    ),
    _food(
        1999631,
        "unsweetened-almond-milk",
        "شیر بادام بدون شکر",
        "dairy",
        "شیر بادام",
        basis="as_purchased",
    ),
    _food(1999632, "baby-spinach", "اسفناج بیبی", "vegetables", "برگ جوان اسفناج"),
    _food(1999634, "roma-tomato", "گوجه رُما", "vegetables", "گوجه ایتالیایی"),
    _food(
        2003587, "whole-spelt-flour", "آرد اسپلت کامل", "grains", role="main_staple", basis="dry"
    ),
    _food(
        2003588,
        "coarse-semolina",
        "سمولینای درشت",
        "grains",
        "آرد سمولینا",
        role="main_staple",
        basis="dry",
    ),
    _food(2003598, "portabella-mushroom", "قارچ پورتوبلو", "vegetables"),
    _food(
        2257046,
        "unsweetened-oat-milk",
        "شیر جو دوسر بدون شکر",
        "dairy",
        "شیر جو دوسر",
        basis="as_purchased",
    ),
    _food(2258588, "green-bell-pepper", "فلفل دلمه‌ای سبز", "vegetables", "فلفل دلمه ای سبز"),
    _food(2258589, "yellow-bell-pepper", "فلفل دلمه‌ای زرد", "vegetables", "فلفل دلمه ای زرد"),
    _food(2258590, "red-bell-pepper", "فلفل دلمه‌ای قرمز", "vegetables", "فلفل دلمه ای قرمز"),
    _food(2261420, "almond-flour", "آرد بادام", "nuts_seeds", basis="dry"),
    _food(
        2261421,
        "whole-oat-flour",
        "آرد جو دوسر کامل",
        "grains",
        "آرد اوت",
        role="main_staple",
        basis="dry",
    ),
    _food(
        2261422,
        "potato-flour",
        "آرد سیب‌زمینی",
        "starchy_vegetables",
        "آرد سیب زمینی",
        role="main_staple",
        basis="dry",
    ),
    _food(
        2262072,
        "creamy-peanut-butter",
        "کره بادام‌زمینی",
        "nuts_seeds",
        "کره بادام زمینی",
        basis="as_purchased",
    ),
    _food(2262074, "creamy-almond-butter", "کره بادام", "nuts_seeds", basis="as_purchased"),
    _food(
        2262075,
        "ground-flaxseed",
        "تخم کتان آسیاب‌شده",
        "nuts_seeds",
        "بذر کتان",
        basis="as_purchased",
    ),
    _food(2346392, "pine-nuts", "دانه کاج", "nuts_seeds", "چلغوز"),
    _food(2346395, "pecans", "گردوی پکان", "nuts_seeds"),
    _food(2346398, "pineapple", "آناناس", "fruit", role="snack"),
    _food(2346400, "green-beans", "لوبیا سبز", "vegetables"),
    _food(2512372, "quinoa-flour", "آرد کینوا", "grains", role="main_staple", basis="dry"),
    _food(2512374, "buckwheat-flour", "آرد گندم سیاه", "grains", role="main_staple", basis="dry"),
    _food(2512378, "whole-buckwheat", "گندم سیاه", "grains", role="main_staple", basis="dry"),
    _food(2512379, "whole-millet", "ارزن", "grains", role="main_staple", basis="dry"),
    _food(
        2512380,
        "brown-rice",
        "برنج قهوه‌ای",
        "grains",
        "برنج قهوه ای",
        role="main_staple",
        basis="dry",
    ),
    _food(2515374, "cashews", "بادام هندی", "nuts_seeds"),
    _food(2515375, "hazelnuts", "فندق", "nuts_seeds"),
    _food(2515379, "pistachios", "پسته", "nuts_seeds"),
    _food(2515380, "pumpkin-seeds", "تخمه کدو", "nuts_seeds"),
    _food(2515381, "raw-sunflower-seeds", "مغز تخمه آفتابگردان", "nuts_seeds", "تخمه آفتاب گردان"),
    _food(2685570, "butternut-squash", "کدو حلوایی", "starchy_vegetables", "کدو باترنات"),
    _food(2685575, "brussels-sprouts", "کلم بروکسل", "vegetables"),
    _food(2685576, "beet", "چغندر", "vegetables", "لبو خام"),
    _food(
        2685580, "tomato-paste", "رب گوجه‌فرنگی", "vegetables", "رب گوجه فرنگی", basis="as_purchased"
    ),
    _food(2710815, "apricot", "زردآلو", "fruit", "زرد الو", role="snack"),
    _food(2710820, "dry-bulgur", "بلغور گندم", "grains", "بلغور", role="main_staple", basis="dry"),
    _food(2710822, "baby-arugula", "روکولا", "vegetables", "آروگولا"),
    _food(2710823, "green-asparagus", "مارچوبه سبز", "vegetables", "مارچوبه"),
    _food(2710833, "mango", "انبه", "fruit", role="snack"),
    _food(2710837, "black-plum", "آلو سیاه", "fruit", "گوجه سبز سیاه", role="snack"),
    _food(2747665, "red-radishes", "تربچه قرمز", "vegetables", "تربچه"),
)


NUTRIENT_SPECS: dict[str, tuple[tuple[int, ...], str, str]] = {
    "energy_kcal": ((1008, 2047, 2048), "kcal", "nutrient_mass"),
    "protein_g": ((1003,), "g", "nutrient_mass"),
    "total_fat_g": ((1004,), "g", "nutrient_mass"),
    "carbohydrate_g": ((1005,), "g", "nutrient_mass"),
    "fibre_g": ((1079,), "g", "nutrient_mass"),
    "total_sugars_g": ((2000,), "g", "nutrient_mass"),
    "saturated_fat_g": ((1258,), "g", "nutrient_mass"),
    "calcium_mg": ((1087,), "mg", "nutrient_mass"),
    "iron_mg": ((1089,), "mg", "nutrient_mass"),
    "magnesium_mg": ((1090,), "mg", "nutrient_mass"),
    "potassium_mg": ((1092,), "mg", "nutrient_mass"),
    "sodium_mg": ((1093,), "mg", "nutrient_mass"),
    "zinc_mg": ((1095,), "mg", "nutrient_mass"),
    "vitamin_c_mg": ((1162,), "mg", "nutrient_mass"),
    "vitamin_d_mcg": ((1114,), "mcg", "nutrient_mass"),
    "vitamin_b12_mcg": ((1178,), "mcg", "nutrient_mass"),
    "folate_dfe_mcg": ((1190,), "mcg", "dietary_folate_equivalents"),
}


def map_foundation_food(
    identity: FoundationFoodIdentity, raw: dict[str, Any]
) -> CatalogueFoodWrite:
    if raw.get("fdcId") != identity.fdc_id:
        raise ValueError(f"Unexpected FDC record for {identity.slug}")
    by_id = {
        item["nutrient"]["id"]: item
        for item in raw.get("foodNutrients", [])
        if isinstance(item, dict)
        and isinstance(item.get("nutrient"), dict)
        and item.get("amount") is not None
    }
    nutrients: list[dict[str, object]] = []
    for code, (candidate_ids, unit, unit_form) in NUTRIENT_SPECS.items():
        source = next((by_id[item_id] for item_id in candidate_ids if item_id in by_id), None)
        if source is None:
            continue
        nutrients.append(
            {
                "nutrient_code": code,
                "value_per_100g": source["amount"],
                "unit": unit,
                "unit_form": unit_form,
                "source_name": SOURCE_NAME,
                "source_reference": SOURCE_REFERENCE,
                "confidence": "high",
            }
        )
    codes = {str(item["nutrient_code"]) for item in nutrients}
    status = "verified" if REQUIRED_PRIMARY_NUTRIENTS <= codes else "draft"
    description = str(raw.get("description") or identity.name_en or identity.slug)
    return CatalogueFoodWrite(
        slug=identity.slug,
        name_fa=identity.name_fa,
        name_en=identity.name_en or description,
        verification_status=status,
        source_name=SOURCE_NAME,
        source_reference=SOURCE_REFERENCE,
        source_food_id=str(identity.fdc_id),
        category=identity.category,
        measurement_basis=identity.measurement_basis,
        canonical_quantity=100,
        canonical_unit="g",
        edible_portion=1,
        data_version=DATA_VERSION,
        source_access_date=SOURCE_ACCESS_DATE,
        aliases=list(dict.fromkeys((identity.name_fa, description, *identity.aliases))),
        roles=[identity.role],
        nutrients=nutrients,
    )


def load_foundation_records(source_path: Path) -> dict[int, dict[str, Any]]:
    with source_path.open(encoding="utf-8") as source_file:
        payload = json.load(source_file)
    records = payload.get("FoundationFoods")
    if not isinstance(records, list):
        raise ValueError("FoundationFoods array is required")
    return {
        int(record["fdcId"]): record
        for record in records
        if isinstance(record, dict) and isinstance(record.get("fdcId"), int)
    }


def import_curated_foundation_foods(db: Session, source_path: Path) -> list[CatalogueFoodWrite]:
    records = load_foundation_records(source_path)
    missing = [item.fdc_id for item in CURATED_FOUNDATION_FOODS if item.fdc_id not in records]
    if missing:
        raise ValueError(f"Curated FDC records are missing: {missing}")
    payloads = [
        map_foundation_food(item, records[item.fdc_id]) for item in CURATED_FOUNDATION_FOODS
    ]
    for payload in payloads:
        save_catalogue_food(db, payload)
    return payloads


def main() -> None:
    parser = ArgumentParser(description="Import curated USDA Foundation Foods into Fitsho")
    parser.add_argument("source", type=Path, help="Extracted Foundation Foods JSON file")
    args = parser.parse_args()
    with Session(get_engine(get_settings().database_url)) as db:
        payloads = import_curated_foundation_foods(db, args.source)
    verified = sum(payload.verification_status == "verified" for payload in payloads)
    draft = len(payloads) - verified
    print(f"Imported {len(payloads)} foods: {verified} verified, {draft} draft")


if __name__ == "__main__":
    main()
