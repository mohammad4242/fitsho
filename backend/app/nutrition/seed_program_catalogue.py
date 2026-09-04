"""Validate and idempotently seed the approved Nutrition Program Catalogue."""

from uuid import NAMESPACE_URL, uuid5

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database.session import get_engine
from app.nutrition.enums import FoodVerificationStatus, MealCategory, NutritionProgramSlotKind
from app.nutrition.models import (
    NutritionCatalogueMeal,
    NutritionProgram,
    NutritionProgramDay,
    NutritionProgramSlot,
)
from app.nutrition.program_catalogue import list_programs
from app.nutrition.program_catalogue_seed_data import (
    BUDGET_TIER_HINT_BY_PROGRAM,
    CANONICAL_MEAL_REGISTRY,
    PROGRAM_WEEKS,
    STYLE_BY_PREFIX,
)

STYLE_NAMES = {
    "ECO": ("اقتصادی", "Economy"),
    "IRN": ("ایرانی متعادل", "Balanced Iranian"),
    "GYM": ("پروتئین بالا برای باشگاه", "High-Protein Gym"),
    "FAST": ("سریع و آسان", "Quick & Easy"),
    "PREM": ("متنوع ممتاز", "Premium / Varied"),
}


def seed_program_catalogue(db: Session, *, commit: bool = True) -> list[NutritionProgram]:
    meals = _validated_canonical_meals(db)
    existing = {
        program.code: program
        for program in db.scalars(
            select(NutritionProgram).where(NutritionProgram.code.in_(PROGRAM_WEEKS))
        )
    }
    for code, week in PROGRAM_WEEKS.items():
        prefix = next(item for item in STYLE_BY_PREFIX if code.startswith(item))
        program = existing.get(code)
        if program is None:
            program = NutritionProgram(
                id=uuid5(NAMESPACE_URL, f"fitsho:nutrition:program:{code}"),
                code=code,
                slug=code.lower(),
            )
            db.add(program)
        else:
            program.days.clear()
            db.flush()
        name_fa, name_en = STYLE_NAMES[prefix]
        program.name_fa = f"{name_fa} {code[-2:]}"
        program.name_en = f"{name_en} {code[-2:]}"
        program.description_fa = "الگوی هفتگی انتخاب وعده؛ مقدار مواد توسط موتور تغذیه تنظیم می‌شود."
        program.description_en = (
            "Weekly meal-selection template; ingredient amounts are adjusted "
            "by the nutrition engine."
        )
        program.diet_style = STYLE_BY_PREFIX[prefix]
        program.budget_tier_hint = BUDGET_TIER_HINT_BY_PROGRAM.get(code)
        program.post_workout_enabled = False

        program.is_active = True
        program.archived_at = None
        program.days = [_program_day(index + 1, row, meals) for index, row in enumerate(week)]
    if commit:
        db.commit()
    else:
        db.flush()
    return [
        program for program in list_programs(db, lifecycle="all") if program.code in PROGRAM_WEEKS
    ]


def _validated_canonical_meals(db: Session) -> dict[str, NutritionCatalogueMeal]:
    rows = {
        row.code: row
        for row in db.scalars(
            select(NutritionCatalogueMeal).where(
                NutritionCatalogueMeal.id.in_(item.id for item in CANONICAL_MEAL_REGISTRY.values())
            )
        )
    }
    for code, canonical in CANONICAL_MEAL_REGISTRY.items():
        row = rows.get(code)
        if (
            row is None
            or row.id != canonical.id
            or row.category is not canonical.category
            or row.verification_status is not FoodVerificationStatus.VERIFIED
        ):
            raise ValueError(f"Canonical verified Meal Catalogue record is invalid: {code}")
    return rows


def _program_day(
    day_number: int,
    encoded: str,
    meals: dict[str, NutritionCatalogueMeal],
) -> NutritionProgramDay:
    tokens = encoded.split()
    categories = (
        MealCategory.BREAKFAST,
        MealCategory.LUNCH,
        MealCategory.SNACK,
        MealCategory.DINNER,
    )
    slots: list[NutritionProgramSlot] = []
    for category, code in zip(categories, tokens, strict=True):
        if code == "FREE_MEAL":
            slots.append(
                NutritionProgramSlot(
                    kind=NutritionProgramSlotKind.FREE_MEAL,
                    category=MealCategory.LUNCH,
                    meal_id=None,
                )
            )
        else:
            canonical = CANONICAL_MEAL_REGISTRY[code]
            if canonical.category is not category:
                raise ValueError(f"Program meal category mismatch: {code}")
            slots.append(
                NutritionProgramSlot(
                    kind=NutritionProgramSlotKind.CATALOGUE_MEAL,
                    category=category,
                    meal_id=canonical.id,
                    meal=meals[code],
                )
            )
    return NutritionProgramDay(day_number=day_number, post_workout_enabled=False, slots=slots)


def main() -> None:
    settings = get_settings()
    with Session(get_engine(settings.database_url)) as db:
        seed_program_catalogue(db)


if __name__ == "__main__":
    main()
