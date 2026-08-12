from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Literal
from uuid import UUID

from sqlalchemy import Select, select
from sqlalchemy.orm import Session, selectinload

from app.nutrition.enums import FoodVerificationStatus, MealCategory, NutritionDietStyle
from app.nutrition.models import (
    NutritionCatalogueMeal,
    NutritionProgram,
    NutritionProgramDay,
    NutritionProgramSlot,
)
from app.nutrition.schemas import (
    NutritionProgramDayResponse,
    NutritionProgramMealReference,
    NutritionProgramResponse,
    NutritionProgramSlotResponse,
    NutritionProgramWrite,
)

ProgramLifecycle = Literal["active", "archived", "all"]
SLOT_ORDER = {
    MealCategory.BREAKFAST: 1,
    MealCategory.LUNCH: 2,
    MealCategory.SNACK: 3,
    MealCategory.DINNER: 4,
    MealCategory.POST_WORKOUT: 5,
}


class ProgramWriteError(ValueError):
    pass


def list_programs(
    db: Session,
    *,
    diet_style: NutritionDietStyle | None = None,
    lifecycle: ProgramLifecycle = "active",
) -> list[NutritionProgram]:
    query = _program_query().order_by(NutritionProgram.name_en, NutritionProgram.id)
    if diet_style is not None:
        query = query.where(NutritionProgram.diet_style == diet_style)
    if lifecycle == "active":
        query = query.where(NutritionProgram.is_active.is_(True))
    elif lifecycle == "archived":
        query = query.where(NutritionProgram.is_active.is_(False))
    return list(db.scalars(query).unique())


def get_program(db: Session, program_id: UUID) -> NutritionProgram | None:
    return db.scalar(_program_query().where(NutritionProgram.id == program_id))


def create_program(db: Session, payload: NutritionProgramWrite) -> NutritionProgram:
    meals = _validate_meals(db, payload)
    slug = _unique_slug(db, payload.name_en)
    program = NutritionProgram(slug=slug, code=payload.code or slug.upper()[:20])
    db.add(program)
    _replace_program_content(program, payload, meals)
    db.commit()
    return _get_program_or_raise(db, program.id)


def update_program(
    db: Session,
    program_id: UUID,
    payload: NutritionProgramWrite,
) -> NutritionProgram | None:
    program = get_program(db, program_id)
    if program is None:
        return None
    meals = _validate_meals(db, payload)
    program.days.clear()
    db.flush()
    _replace_program_content(program, payload, meals)
    db.commit()
    return _get_program_or_raise(db, program.id)


def archive_program(db: Session, program_id: UUID) -> bool:
    program = db.get(NutritionProgram, program_id)
    if program is None:
        return False
    program.is_active = False
    program.archived_at = datetime.now(UTC)
    db.commit()
    return True


def restore_program(db: Session, program_id: UUID) -> NutritionProgram | None:
    program = db.get(NutritionProgram, program_id)
    if program is None:
        return None
    program.is_active = True
    program.archived_at = None
    db.commit()
    return _get_program_or_raise(db, program.id)


def program_response(program: NutritionProgram) -> NutritionProgramResponse:
    return NutritionProgramResponse(
        id=program.id,
        code=program.code,
        slug=program.slug,
        name_fa=program.name_fa,
        name_en=program.name_en,
        description_fa=program.description_fa,
        description_en=program.description_en,
        diet_style=program.diet_style,
        post_workout_enabled=program.post_workout_enabled,
        is_active=program.is_active,
        archived_at=program.archived_at,
        created_at=program.created_at,
        updated_at=program.updated_at,
        days=[
            NutritionProgramDayResponse(
                id=day.id,
                day_number=day.day_number,
                post_workout_enabled=day.post_workout_enabled,
                slots=[
                    NutritionProgramSlotResponse(
                        id=slot.id,
                        kind=slot.kind,
                        category=slot.category,
                        meal=NutritionProgramMealReference(
                            id=slot.meal.id,
                            code=slot.meal.code,
                            name_fa=slot.meal.name_fa,
                            name_en=slot.meal.name_en,
                            category=slot.meal.category,
                        )
                        if slot.meal is not None
                        else None,
                    )
                    for slot in sorted(day.slots, key=lambda item: SLOT_ORDER[item.category])
                ],
            )
            for day in sorted(program.days, key=lambda item: item.day_number)
        ],
    )


def _program_query() -> Select[tuple[NutritionProgram]]:
    return select(NutritionProgram).options(
        selectinload(NutritionProgram.days)
        .selectinload(NutritionProgramDay.slots)
        .selectinload(NutritionProgramSlot.meal)
    )


def _validate_meals(
    db: Session,
    payload: NutritionProgramWrite,
) -> dict[UUID, NutritionCatalogueMeal]:
    meal_ids = {
        slot.meal_id for day in payload.days for slot in day.slots if slot.meal_id is not None
    }
    meals = {
        meal.id: meal
        for meal in db.scalars(
            select(NutritionCatalogueMeal).where(NutritionCatalogueMeal.id.in_(meal_ids))
        )
    }
    if missing := meal_ids - meals.keys():
        raise ProgramWriteError(
            f"Selected meals do not exist: {', '.join(sorted(map(str, missing)))}"
        )
    if draft_ids := {
        meal.id
        for meal in meals.values()
        if meal.verification_status is not FoodVerificationStatus.VERIFIED
    }:
        raise ProgramWriteError(
            f"Selected meals must be verified: {', '.join(sorted(map(str, draft_ids)))}"
        )
    for day in payload.days:
        for slot in day.slots:
            if slot.meal_id is not None and meals[slot.meal_id].category is not slot.category:
                raise ProgramWriteError("Selected meal category must match its program slot")
    return meals


def _replace_program_content(
    program: NutritionProgram,
    payload: NutritionProgramWrite,
    meals: dict[UUID, NutritionCatalogueMeal],
) -> None:
    program.name_fa = payload.name_fa
    if payload.code is not None:
        program.code = payload.code
    program.name_en = payload.name_en
    program.description_fa = payload.description_fa
    program.description_en = payload.description_en
    program.diet_style = payload.diet_style
    program.post_workout_enabled = payload.post_workout_enabled
    for day_payload in sorted(payload.days, key=lambda item: item.day_number):
        day = NutritionProgramDay(
            day_number=day_payload.day_number,
            post_workout_enabled=day_payload.post_workout_enabled,
        )
        program.days.append(day)
        for slot_payload in sorted(day_payload.slots, key=lambda item: SLOT_ORDER[item.category]):
            day.slots.append(
                NutritionProgramSlot(
                    kind=slot_payload.kind,
                    category=slot_payload.category,
                    meal_id=slot_payload.meal_id,
                    meal=(
                        meals[slot_payload.meal_id] if slot_payload.meal_id is not None else None
                    ),
                )
            )


def _unique_slug(db: Session, name_en: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", name_en.lower()).strip("-") or "nutrition-program"
    base = base[:110].strip("-") or "nutrition-program"
    candidate = base
    suffix = 2
    while db.scalar(select(NutritionProgram.id).where(NutritionProgram.slug == candidate)):
        candidate = f"{base[: 120 - len(str(suffix)) - 1]}-{suffix}"
        suffix += 1
    return candidate


def _get_program_or_raise(db: Session, program_id: UUID) -> NutritionProgram:
    program = get_program(db, program_id)
    if program is None:
        raise ProgramWriteError("Nutrition program was not found after saving")
    return program
