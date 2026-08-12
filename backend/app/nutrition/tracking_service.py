from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterator
from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.orm import Session, selectinload

from app.nutrition.enums import (
    EstimateConfidence,
    FoodItemKind,
    MealSlotRole,
    NutritionConsumptionSource,
    NutritionDailyCheckInStatus,
    NutritionPlanLifecycleStatus,
)
from app.nutrition.models import (
    NutritionCatalogueFood,
    NutritionConsumptionEntry,
    NutritionDailyCheckIn,
    NutritionFoodItem,
    NutritionWeeklyPlan,
    NutritionWeeklyPlanDay,
    NutritionWeeklyPlanMeal,
)


class TrackingError(Exception):
    def __init__(self, code: str) -> None:
        self.code = code


def _active_plan_for_date(
    db: Session, user_id: UUID, entry_date: date
) -> NutritionWeeklyPlan | None:
    return db.scalar(
        select(NutritionWeeklyPlan)
        .where(
            NutritionWeeklyPlan.user_id == user_id,
            NutritionWeeklyPlan.lifecycle_status == NutritionPlanLifecycleStatus.ACTIVE,
            NutritionWeeklyPlan.start_date <= entry_date,
        )
        .options(
            selectinload(NutritionWeeklyPlan.days)
            .selectinload(NutritionWeeklyPlanDay.meals)
            .selectinload(NutritionWeeklyPlanMeal.foods)
        )
        .order_by(NutritionWeeklyPlan.start_date.desc(), NutritionWeeklyPlan.revision.desc())
    )


def _entry_response(entry: NutritionConsumptionEntry) -> dict[str, object]:
    return {
        "id": entry.id,
        "entry_date": entry.entry_date,
        "plan_revision_id": entry.plan_revision_id,
        "planned_meal_id": entry.planned_meal_id,
        "food_id": entry.food_id,
        "display_name": entry.display_name,
        "quantity_grams": float(entry.quantity_grams) if entry.quantity_grams else None,
        "source": entry.source.value,
        "confidence": entry.confidence.value,
        "user_confirmed": entry.user_confirmed,
        "nutrients": {key: float(str(value)) for key, value in entry.nutrients.items()},
        "warning_codes": entry.warning_codes,
        "note": entry.note,
    }


def submit_check_in(
    db: Session,
    user_id: UUID,
    entry_date: date,
    status: NutritionDailyCheckInStatus,
    note: str | None,
) -> dict[str, object]:
    existing = db.scalar(
        select(NutritionDailyCheckIn).where(
            NutritionDailyCheckIn.user_id == user_id,
            NutritionDailyCheckIn.entry_date == entry_date,
        )
    )
    plan = None
    if status in {NutritionDailyCheckInStatus.ON_PLAN, NutritionDailyCheckInStatus.MOSTLY_ON_PLAN}:
        plan = _active_plan_for_date(db, user_id, entry_date)
        if plan is None:
            raise TrackingError("ACTIVE_PLAN_REQUIRED")
        day_index = (entry_date - plan.start_date).days % 7
        day = next((row for row in plan.days if row.day_index == day_index), None)
        if day is None:
            raise TrackingError("ACTIVE_PLAN_DAY_NOT_FOUND")
        db.execute(
            delete(NutritionConsumptionEntry).where(
                NutritionConsumptionEntry.user_id == user_id,
                NutritionConsumptionEntry.entry_date == entry_date,
                NutritionConsumptionEntry.source.in_(
                    [
                        NutritionConsumptionSource.PLANNED_CONFIRMED,
                        NutritionConsumptionSource.PLANNED_ADJUSTED,
                    ]
                ),
            )
        )
        for meal in day.meals:
            db.add(
                NutritionConsumptionEntry(
                    user_id=user_id,
                    entry_date=entry_date,
                    plan_revision_id=plan.id,
                    planned_meal_id=meal.id,
                    display_name=f"{meal.slot_role.value} {meal.slot_index + 1}",
                    quantity_grams=sum((food.grams for food in meal.foods), Decimal()),
                    source=NutritionConsumptionSource.PLANNED_CONFIRMED,
                    confidence=EstimateConfidence.MEDIUM,
                    user_confirmed=True,
                    nutrients=dict(meal.nutrient_totals),
                    warning_codes=[],
                )
            )
    if existing is None:
        existing = NutritionDailyCheckIn(
            user_id=user_id,
            entry_date=entry_date,
            status=status,
            plan_revision_id=plan.id if plan else None,
            note=note,
        )
        db.add(existing)
    else:
        existing.status = status
        existing.plan_revision_id = plan.id if plan else None
        existing.note = note
    db.commit()
    return daily_summary(db, user_id, entry_date)


def add_catalogue_food(
    db: Session,
    user_id: UUID,
    entry_date: date,
    food_id: UUID,
    grams: Decimal,
    note: str | None,
) -> dict[str, object]:
    food = db.scalar(
        select(NutritionCatalogueFood)
        .where(NutritionCatalogueFood.id == food_id)
        .options(selectinload(NutritionCatalogueFood.compositions))
    )
    if food is None:
        raise TrackingError("FOOD_NOT_FOUND")
    factor = grams / Decimal("100")
    nutrients = {row.nutrient_code: str(row.value_per_100g * factor) for row in food.compositions}
    warnings = actual_intake_warnings(db, user_id, food)
    entry = NutritionConsumptionEntry(
        user_id=user_id,
        entry_date=entry_date,
        food_id=food.id,
        display_name=food.name_fa,
        quantity_grams=grams,
        source=NutritionConsumptionSource.CATALOGUE_MANUAL,
        confidence=EstimateConfidence.HIGH,
        user_confirmed=True,
        nutrients=nutrients,
        warning_codes=warnings,
        note=note,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return _entry_response(entry)


def actual_intake_warnings(
    db: Session,
    user_id: UUID,
    food: NutritionCatalogueFood,
) -> list[str]:
    exclusions = db.scalars(
        select(NutritionFoodItem).where(
            NutritionFoodItem.user_id == user_id,
            NutritionFoodItem.kind.in_(
                [FoodItemKind.ALLERGY, FoodItemKind.NEVER_SUGGEST, FoodItemKind.REFUSED]
            ),
        )
    ).all()
    searchable = f"{food.name_fa} {food.name_en} {food.slug}".casefold()
    warnings = [
        "ACTUAL_INTAKE_HARD_EXCLUSION"
        for exclusion in exclusions
        if exclusion.normalized_name.casefold() in searchable
    ]
    return list(dict.fromkeys(warnings))


def save_quick_approximation(
    db: Session,
    user_id: UUID,
    entry_date: date,
    display_name: str,
    calories: Decimal,
    protein: Decimal | None,
) -> dict[str, object]:
    nutrients = {"energy_kcal": str(calories)}
    if protein is not None:
        nutrients["protein_g"] = str(protein)
    entry = NutritionConsumptionEntry(
        user_id=user_id,
        entry_date=entry_date,
        display_name=display_name,
        source=NutritionConsumptionSource.QUICK_APPROXIMATION,
        confidence=EstimateConfidence.LOW,
        user_confirmed=True,
        nutrients=nutrients,
        warning_codes=["APPROXIMATE_INTAKE"],
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return _entry_response(entry)


def save_free_meal(
    db: Session,
    user_id: UUID,
    meal_id: UUID,
    entry_date: date,
    calories: Decimal,
    protein: Decimal,
    carbohydrate: Decimal,
    fat: Decimal,
) -> dict[str, object]:
    plan = _active_plan_for_date(db, user_id, entry_date)
    if plan is None:
        raise TrackingError("ACTIVE_PLAN_REQUIRED")
    day = next((candidate for candidate in plan.days if candidate.plan_date == entry_date), None)
    meal = (
        next((candidate for candidate in day.meals if candidate.id == meal_id), None)
        if day is not None
        else None
    )
    if meal is None or meal.slot_role is not MealSlotRole.FREE_MEAL:
        raise TrackingError("ACTIVE_FREE_MEAL_NOT_FOUND")
    entry = db.scalar(
        select(NutritionConsumptionEntry).where(
            NutritionConsumptionEntry.user_id == user_id,
            NutritionConsumptionEntry.entry_date == entry_date,
            NutritionConsumptionEntry.planned_meal_id == meal_id,
            NutritionConsumptionEntry.source == NutritionConsumptionSource.FREE_MEAL,
        )
    )
    if entry is None:
        entry = NutritionConsumptionEntry(
            user_id=user_id,
            entry_date=entry_date,
            plan_revision_id=plan.id,
            planned_meal_id=meal.id,
            display_name="وعده آزاد",
            source=NutritionConsumptionSource.FREE_MEAL,
            confidence=EstimateConfidence.LOW,
            user_confirmed=True,
            warning_codes=["USER_REPORTED_FREE_MEAL"],
        )
        db.add(entry)
    entry.nutrients = {
        "energy_kcal": str(calories),
        "protein_g": str(protein),
        "carbohydrate_g": str(carbohydrate),
        "total_fat_g": str(fat),
    }
    db.commit()
    return daily_summary(db, user_id, entry_date)


def daily_summary(db: Session, user_id: UUID, entry_date: date) -> dict[str, object]:
    check_in = db.scalar(
        select(NutritionDailyCheckIn).where(
            NutritionDailyCheckIn.user_id == user_id,
            NutritionDailyCheckIn.entry_date == entry_date,
        )
    )
    entries = db.scalars(
        select(NutritionConsumptionEntry)
        .where(
            NutritionConsumptionEntry.user_id == user_id,
            NutritionConsumptionEntry.entry_date == entry_date,
        )
        .order_by(NutritionConsumptionEntry.created_at)
    ).all()
    totals: defaultdict[str, Decimal] = defaultdict(Decimal)
    for entry in entries:
        for code, value in entry.nutrients.items():
            totals[code] += Decimal(str(value))
    return {
        "entry_date": entry_date,
        "check_in_status": check_in.status.value if check_in else "not_recorded",
        "plan_revision_id": check_in.plan_revision_id if check_in else None,
        "data_status": "sufficient" if entries else "insufficient_data",
        "actual_totals": {code: float(value) for code, value in totals.items()},
        "entries": [_entry_response(entry) for entry in entries],
    }


def history(db: Session, user_id: UUID, start: date, end: date) -> list[dict[str, object]]:
    return [daily_summary(db, user_id, current) for current in _date_range(start, end)]


def edit_entry(
    db: Session,
    user_id: UUID,
    entry_id: UUID,
    *,
    grams: Decimal | None,
    display_name: str | None,
    calories: Decimal | None,
    protein: Decimal | None,
    note: str | None,
    fields: set[str],
) -> dict[str, object]:
    entry = db.scalar(
        select(NutritionConsumptionEntry).where(
            NutritionConsumptionEntry.id == entry_id,
            NutritionConsumptionEntry.user_id == user_id,
        )
    )
    if entry is None:
        raise TrackingError("CONSUMPTION_ENTRY_NOT_FOUND")
    if entry.source in {
        NutritionConsumptionSource.PLANNED_CONFIRMED,
        NutritionConsumptionSource.PLANNED_ADJUSTED,
    }:
        raise TrackingError("USE_PLANNED_MEAL_ADJUSTMENT")
    if entry.food_id is not None:
        if grams is None:
            if "grams" in fields:
                raise TrackingError("ENTRY_GRAMS_REQUIRED")
        else:
            food = db.scalar(
                select(NutritionCatalogueFood)
                .where(NutritionCatalogueFood.id == entry.food_id)
                .options(selectinload(NutritionCatalogueFood.compositions))
            )
            if food is None:
                raise TrackingError("FOOD_NOT_FOUND")
            factor = grams / Decimal("100")
            entry.quantity_grams = grams
            entry.nutrients = {
                row.nutrient_code: str(row.value_per_100g * factor) for row in food.compositions
            }
            entry.warning_codes = actual_intake_warnings(db, user_id, food)
    elif entry.source is NutritionConsumptionSource.QUICK_APPROXIMATION:
        if display_name is not None:
            entry.display_name = display_name
        nutrients = dict(entry.nutrients)
        if calories is not None:
            nutrients["energy_kcal"] = str(calories)
        if "protein_g" in fields:
            if protein is None:
                nutrients.pop("protein_g", None)
            else:
                nutrients["protein_g"] = str(protein)
        entry.nutrients = nutrients
    if "note" in fields:
        entry.note = note
    db.commit()
    db.refresh(entry)
    return _entry_response(entry)


def recent_foods(db: Session, user_id: UUID, limit: int = 20) -> list[dict[str, object]]:
    entries = db.scalars(
        select(NutritionConsumptionEntry)
        .where(
            NutritionConsumptionEntry.user_id == user_id,
            NutritionConsumptionEntry.food_id.is_not(None),
        )
        .order_by(
            NutritionConsumptionEntry.entry_date.desc(),
            NutritionConsumptionEntry.created_at.desc(),
        )
    ).all()
    recent: list[dict[str, object]] = []
    seen: set[UUID] = set()
    for entry in entries:
        if entry.food_id is None or entry.food_id in seen:
            continue
        seen.add(entry.food_id)
        recent.append(
            {
                "food_id": entry.food_id,
                "display_name": entry.display_name,
                "last_quantity_grams": (
                    float(entry.quantity_grams) if entry.quantity_grams is not None else None
                ),
                "last_entry_date": entry.entry_date,
            }
        )
        if len(recent) >= limit:
            break
    return recent


def adjust_planned_meal(
    db: Session,
    user_id: UUID,
    meal_id: UUID,
    entry_date: date,
    status: str,
    portion_ratio: Decimal | None,
) -> dict[str, object]:
    plan = _active_plan_for_date(db, user_id, entry_date)
    if plan is None:
        raise TrackingError("ACTIVE_PLAN_REQUIRED")
    day_index = (entry_date - plan.start_date).days % 7
    day = next((candidate for candidate in plan.days if candidate.day_index == day_index), None)
    meal = (
        next(
            (candidate for candidate in day.meals if candidate.id == meal_id),
            None,
        )
        if day is not None
        else None
    )
    if meal is None:
        raise TrackingError("ACTIVE_PLAN_MEAL_NOT_FOUND")
    existing = db.scalar(
        select(NutritionConsumptionEntry).where(
            NutritionConsumptionEntry.user_id == user_id,
            NutritionConsumptionEntry.entry_date == entry_date,
            NutritionConsumptionEntry.planned_meal_id == meal_id,
        )
    )
    if status == "skipped":
        if existing is not None:
            db.delete(existing)
        db.commit()
        return daily_summary(db, user_id, entry_date)
    ratio = Decimal("1") if status == "consumed" else portion_ratio
    if ratio is None or ratio <= 0:
        raise TrackingError("PORTION_RATIO_REQUIRED")
    values = {
        "plan_revision_id": plan.id,
        "planned_meal_id": meal.id,
        "display_name": f"{meal.slot_role.value} {meal.slot_index + 1}",
        "quantity_grams": sum((food.grams for food in meal.foods), Decimal()) * ratio,
        "source": (
            NutritionConsumptionSource.PLANNED_CONFIRMED
            if status == "consumed"
            else NutritionConsumptionSource.PLANNED_ADJUSTED
        ),
        "confidence": EstimateConfidence.HIGH,
        "user_confirmed": True,
        "nutrients": {
            code: str(Decimal(str(value)) * ratio) for code, value in meal.nutrient_totals.items()
        },
        "warning_codes": [],
    }
    if existing is None:
        db.add(
            NutritionConsumptionEntry(
                user_id=user_id,
                entry_date=entry_date,
                **values,
            )
        )
    else:
        for field, value in values.items():
            setattr(existing, field, value)
    db.commit()
    return daily_summary(db, user_id, entry_date)


def _date_range(start: date, end: date) -> Iterator[date]:
    current = start
    while current <= end:
        yield current
        current = date.fromordinal(current.toordinal() + 1)


def delete_entry(db: Session, user_id: UUID, entry_id: UUID) -> None:
    entry = db.scalar(
        select(NutritionConsumptionEntry).where(
            NutritionConsumptionEntry.id == entry_id,
            NutritionConsumptionEntry.user_id == user_id,
        )
    )
    if entry is None:
        raise TrackingError("CONSUMPTION_ENTRY_NOT_FOUND")
    db.delete(entry)
    db.commit()
