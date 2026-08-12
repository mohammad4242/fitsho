"""Pure deterministic adaptation of one weekly template to profile meal buckets."""

from dataclasses import dataclass
from uuid import UUID

from app.nutrition.enums import MainMealCountBucket, MealCategory, SnackCountBucket
from app.nutrition.models import NutritionProgram
from app.nutrition.program_catalogue_seed_data import CANONICAL_MEAL_REGISTRY


@dataclass(frozen=True)
class AdaptedSlot:
    role: str
    category: MealCategory
    meal_id: UUID | None
    meal_code: str | None


@dataclass(frozen=True)
class AdaptedDay:
    day_index: int
    slots: tuple[AdaptedSlot, ...]


@dataclass(frozen=True)
class AdaptedWeek:
    program_id: UUID | None
    program_code: str
    days: tuple[AdaptedDay, ...]


def adapt_program(
    program: NutritionProgram,
    main_bucket: MainMealCountBucket,
    snack_bucket: SnackCountBucket,
    *,
    training_day_indexes: set[int] | None = None,
    include_post_workout: bool = False,
) -> AdaptedWeek:
    ordered_days = sorted(program.days, key=lambda day: day.day_number)
    main_pool = sorted(
        {
            (slot.meal.code, slot.meal.id, slot.meal.category)
            for day in ordered_days
            for slot in day.slots
            if slot.meal is not None
            and slot.meal.category in {MealCategory.LUNCH, MealCategory.DINNER}
        },
        key=lambda item: item[0],
    )
    snack_pool = sorted(
        {
            (slot.meal.code, slot.meal.id)
            for day in ordered_days
            for slot in day.slots
            if slot.meal is not None and slot.meal.category is MealCategory.SNACK
        },
        key=lambda item: item[0],
    )
    snack_count = {
        SnackCountBucket.ZERO: 0,
        SnackCountBucket.ONE: 1,
        SnackCountBucket.TWO: 2,
        SnackCountBucket.THREE_OR_MORE: 3,
    }[snack_bucket]
    adapted_days = tuple(
        _adapt_day(
            index,
            day,
            main_bucket,
            snack_count,
            main_pool,
            snack_pool,
            include_post_workout and index in (training_day_indexes or set()),
        )
        for index, day in enumerate(ordered_days)
    )
    return AdaptedWeek(program.id, program.code, adapted_days)


def _adapt_day(
    day_index: int,
    day: object,
    main_bucket: MainMealCountBucket,
    snack_count: int,
    main_pool: list[tuple[str, UUID, MealCategory]],
    snack_pool: list[tuple[str, UUID]],
    add_post_workout: bool,
) -> AdaptedDay:
    day_slots = {slot.category: slot for slot in day.slots}  # type: ignore[attr-defined]
    breakfast = _catalogue_slot("breakfast", day_slots[MealCategory.BREAKFAST])
    lunch_source = day_slots[MealCategory.LUNCH]
    lunch = (
        AdaptedSlot("free_meal", MealCategory.LUNCH, None, None)
        if lunch_source.meal is None
        else _catalogue_slot("lunch", lunch_source)
    )
    dinner = _catalogue_slot("dinner", day_slots[MealCategory.DINNER])
    if main_bucket is MainMealCountBucket.TWO:
        main_slots = [lunch, dinner]
    elif main_bucket is MainMealCountBucket.THREE:
        main_slots = [breakfast, lunch, dinner]
    else:
        current_codes = {slot.meal_code for slot in (lunch, dinner) if slot.meal_code}
        choices = [item for item in main_pool if item[0] not in current_codes] or main_pool
        extra_code, extra_id, extra_category = choices[day_index % len(choices)]
        main_slots = [
            breakfast,
            lunch,
            AdaptedSlot("extra_main", extra_category, extra_id, extra_code),
            dinner,
        ]
    planned_snack = day_slots[MealCategory.SNACK].meal
    if planned_snack is None:
        raise ValueError("Program snack slot must reference the Meal Catalogue")
    snack_choices = [(planned_snack.code, planned_snack.id)]
    additional = [item for item in snack_pool if item[0] != planned_snack.code]
    for offset in range(max(0, snack_count - 1)):
        snack_choices.append(additional[(day_index + offset) % len(additional)])
    snack_slots = [
        AdaptedSlot("snack", MealCategory.SNACK, meal_id, code)
        for code, meal_id in snack_choices[:snack_count]
    ]
    slots = [*main_slots, *snack_slots]
    if add_post_workout:
        post = CANONICAL_MEAL_REGISTRY["PW01"]
        slots.append(AdaptedSlot("post_workout", MealCategory.POST_WORKOUT, post.id, "PW01"))
    return AdaptedDay(day_index, tuple(slots))


def _catalogue_slot(role: str, slot: object) -> AdaptedSlot:
    meal = slot.meal  # type: ignore[attr-defined]
    if meal is None:
        raise ValueError(f"{role} slot must reference the Meal Catalogue")
    return AdaptedSlot(role, meal.category, meal.id, meal.code)
