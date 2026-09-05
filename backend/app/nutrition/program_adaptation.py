"""Pure deterministic adaptation of one weekly template to profile meal buckets."""

from collections.abc import Sequence
from dataclasses import dataclass
from uuid import UUID

from app.nutrition.enums import MainMealCountBucket, MealCategory, SnackCountBucket
from app.nutrition.models import NutritionProgram
from app.nutrition.program_catalogue_seed_data import CANONICAL_MEAL_REGISTRY


class ProgramStructureIncompatibleError(ValueError):
    """Raised when a nutrition program has insufficient slot coverage for adaptation."""

    pass


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
    if not ordered_days:
        raise ProgramStructureIncompatibleError(
            f"Program {program.code} has no scheduled days for adaptation"
        )
    main_pool = sorted(
        {
            (slot.meal.code, slot.meal.id, slot.meal.category)
            for day in ordered_days
            for slot in getattr(day, "slots", ())
            if slot.meal is not None
            and slot.meal.category in {MealCategory.LUNCH, MealCategory.DINNER}
        },
        key=lambda item: item[0],
    )
    snack_pool = sorted(
        {
            (slot.meal.code, slot.meal.id)
            for day in ordered_days
            for slot in getattr(day, "slots", ())
            if slot.meal is not None and slot.meal.category is MealCategory.SNACK
        },
        key=lambda item: item[0],
    )
    breakfast_pool = sorted(
        {
            (slot.meal.code, slot.meal.id, slot.meal.category)
            for day in ordered_days
            for slot in getattr(day, "slots", ())
            if slot.meal is not None and slot.meal.category is MealCategory.BREAKFAST
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
            breakfast_pool,
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
    main_pool: Sequence[tuple[str, UUID, MealCategory]],
    snack_pool: Sequence[tuple[str, UUID]],
    breakfast_pool: Sequence[tuple[str, UUID, MealCategory]],
    add_post_workout: bool,
) -> AdaptedDay:
    day_slots = {slot.category: slot for slot in getattr(day, "slots", ())}

    # Lunch resolution
    lunch_source = day_slots.get(MealCategory.LUNCH)
    if lunch_source is None:
        if not main_pool:
            raise ProgramStructureIncompatibleError("Program has no lunch or main meals")
        extra_code, extra_id, extra_cat = main_pool[day_index % len(main_pool)]
        lunch = AdaptedSlot("lunch", extra_cat, extra_id, extra_code)
    elif lunch_source.meal is None:
        lunch = AdaptedSlot("free_meal", MealCategory.LUNCH, None, None)
    else:
        lunch = _catalogue_slot("lunch", lunch_source)

    # Dinner resolution
    dinner_source = day_slots.get(MealCategory.DINNER)
    if dinner_source is None:
        if not main_pool:
            raise ProgramStructureIncompatibleError("Program has no dinner or main meals")
        extra_code, extra_id, extra_cat = main_pool[(day_index + 1) % len(main_pool)]
        dinner = AdaptedSlot("dinner", extra_cat, extra_id, extra_code)
    else:
        dinner = _catalogue_slot("dinner", dinner_source)

    if main_bucket is MainMealCountBucket.TWO:
        main_slots = [lunch, dinner]
    else:
        # Breakfast resolution (only needed for 3 or 4+ meals)
        bfast_source = day_slots.get(MealCategory.BREAKFAST)
        if bfast_source is None or bfast_source.meal is None:
            if not breakfast_pool:
                raise ProgramStructureIncompatibleError("Program has no breakfast meals")
            bf_code, bf_id, bf_cat = breakfast_pool[day_index % len(breakfast_pool)]
            breakfast = AdaptedSlot("breakfast", bf_cat, bf_id, bf_code)
        else:
            breakfast = _catalogue_slot("breakfast", bfast_source)

        if main_bucket is MainMealCountBucket.THREE:
            main_slots = [breakfast, lunch, dinner]
        else:
            current_codes = {slot.meal_code for slot in (lunch, dinner) if slot.meal_code}
            choices = [item for item in main_pool if item[0] not in current_codes] or main_pool
            if not choices:
                raise ProgramStructureIncompatibleError(
                    "Program has no main meals available for extra main slot"
                )
            extra_code, extra_id, extra_category = choices[day_index % len(choices)]
            main_slots = [
                breakfast,
                lunch,
                AdaptedSlot("extra_main", extra_category, extra_id, extra_code),
                dinner,
            ]

    # Snack resolution
    if snack_count == 0:
        snack_slots: list[AdaptedSlot] = []
    else:
        snack_source = day_slots.get(MealCategory.SNACK)
        planned_snack = snack_source.meal if snack_source is not None else None
        if planned_snack is None:
            if not snack_pool:
                raise ProgramStructureIncompatibleError(
                    "Program has no snack slots for positive snack count"
                )
            planned_code, planned_id = snack_pool[day_index % len(snack_pool)]
            snack_choices = [(planned_code, planned_id)]
        else:
            snack_choices = [(planned_snack.code, planned_snack.id)]

        additional = (
            [item for item in snack_pool if item[0] != snack_choices[0][0]]
            or snack_pool
            or snack_choices
        )
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
    meal = getattr(slot, "meal", None)
    if meal is None:
        raise ProgramStructureIncompatibleError(f"{role} slot must reference the Meal Catalogue")
    return AdaptedSlot(role, meal.category, meal.id, meal.code)
