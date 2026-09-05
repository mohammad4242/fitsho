from uuid import UUID

from app.nutrition.enums import (
    MainMealCountBucket,
    MealCategory,
    NutritionProgramSlotKind,
    SnackCountBucket,
)
from app.nutrition.models import (
    NutritionCatalogueMeal,
    NutritionProgram,
    NutritionProgramDay,
    NutritionProgramSlot,
)
from app.nutrition.program_adaptation import adapt_program


def _meal(code: str, category: MealCategory) -> NutritionCatalogueMeal:
    return NutritionCatalogueMeal(
        id=UUID(int=sum(ord(char) for char in code)),
        code=code,
        category=category,
        name_fa=code,
        name_en=code,
    )


def _program() -> NutritionProgram:
    breakfasts = [_meal("BF01", MealCategory.BREAKFAST), _meal("BF02", MealCategory.BREAKFAST)]
    lunches = [_meal("LU01", MealCategory.LUNCH), _meal("LU02", MealCategory.LUNCH)]
    dinners = [_meal("DN01", MealCategory.DINNER), _meal("DN02", MealCategory.DINNER)]
    snacks = [
        _meal("SN01", MealCategory.SNACK),
        _meal("SN02", MealCategory.SNACK),
        _meal("SN03", MealCategory.SNACK),
    ]
    days = []
    for index in range(7):
        lunch = NutritionProgramSlot(
            kind=NutritionProgramSlotKind.CATALOGUE_MEAL,
            category=MealCategory.LUNCH,
            meal=lunches[index % 2],
            meal_id=lunches[index % 2].id,
        )
        if index == 6:
            lunch = NutritionProgramSlot(
                kind=NutritionProgramSlotKind.FREE_MEAL,
                category=MealCategory.LUNCH,
                meal=None,
                meal_id=None,
            )
        selected = (
            breakfasts[index % 2],
            lunch,
            snacks[index % 3],
            dinners[index % 2],
        )
        slots = [
            NutritionProgramSlot(
                kind=NutritionProgramSlotKind.CATALOGUE_MEAL,
                category=meal.category,
                meal=meal,
                meal_id=meal.id,
            )
            if isinstance(meal, NutritionCatalogueMeal)
            else meal
            for meal in selected
        ]
        days.append(NutritionProgramDay(day_number=index + 1, slots=slots))
    return NutritionProgram(code="IRN01", slug="irn01", days=days)


def test_main_meal_buckets_emit_exact_shapes_without_duplicate_breakfast() -> None:
    program = _program()
    two = adapt_program(program, MainMealCountBucket.TWO, SnackCountBucket.ONE)
    three = adapt_program(program, MainMealCountBucket.THREE, SnackCountBucket.ONE)
    four = adapt_program(program, MainMealCountBucket.FOUR_OR_MORE, SnackCountBucket.ONE)

    assert all(
        [slot.role for slot in day.slots if slot.role != "snack"] == ["lunch", "dinner"]
        for day in two.days[:6]
    )
    assert [slot.role for slot in two.days[6].slots if slot.role != "snack"] == [
        "free_meal",
        "dinner",
    ]
    assert all(
        [slot.role for slot in day.slots if slot.role != "snack"]
        == ["breakfast", "lunch", "dinner"]
        for day in three.days[:6]
    )
    assert all(len([slot for slot in day.slots if slot.role != "snack"]) == 4 for day in four.days)
    assert all(sum(slot.role == "breakfast" for slot in day.slots) == 1 for day in four.days)
    approved = {"LU01", "LU02", "DN01", "DN02"}
    assert all(
        next(slot.meal_code for slot in day.slots if slot.role == "extra_main") in approved
        for day in four.days
    )


def test_snack_buckets_and_post_workout_are_independent_and_deterministic() -> None:
    program = _program()
    expected = {
        SnackCountBucket.ZERO: 0,
        SnackCountBucket.ONE: 1,
        SnackCountBucket.TWO: 2,
        SnackCountBucket.THREE_OR_MORE: 3,
    }
    for bucket, count in expected.items():
        week = adapt_program(program, MainMealCountBucket.THREE, bucket)
        assert all(sum(slot.role == "snack" for slot in day.slots) == count for day in week.days)
        assert all(
            len({slot.meal_code for slot in day.slots if slot.role == "snack"}) == count
            for day in week.days
        )

    with_post = adapt_program(
        program,
        MainMealCountBucket.THREE,
        SnackCountBucket.ONE,
        training_day_indexes={0, 2},
        include_post_workout=True,
    )
    assert [sum(slot.role == "post_workout" for slot in day.slots) for day in with_post.days] == [
        1,
        0,
        1,
        0,
        0,
        0,
        0,
    ]
    assert all(
        sum(slot.role in {"breakfast", "lunch", "free_meal", "dinner"} for slot in day.slots) == 3
        for day in with_post.days
    )
    assert adapt_program(
        program, MainMealCountBucket.FOUR_OR_MORE, SnackCountBucket.TWO
    ) == adapt_program(program, MainMealCountBucket.FOUR_OR_MORE, SnackCountBucket.TWO)


def test_adaptation_handles_missing_optional_slots_gracefully() -> None:
    import pytest

    from app.nutrition.program_adaptation import ProgramStructureIncompatibleError

    # Program with ONLY lunch and dinner (no breakfast, no snacks)
    lunches = [_meal("LU01", MealCategory.LUNCH)]
    dinners = [_meal("DN01", MealCategory.DINNER)]
    days = []
    for i in range(7):
        slots = [
            NutritionProgramSlot(
                kind=NutritionProgramSlotKind.CATALOGUE_MEAL,
                category=MealCategory.LUNCH,
                meal=lunches[0],
                meal_id=lunches[0].id,
            ),
            NutritionProgramSlot(
                kind=NutritionProgramSlotKind.CATALOGUE_MEAL,
                category=MealCategory.DINNER,
                meal=dinners[0],
                meal_id=dinners[0].id,
            ),
        ]
        days.append(NutritionProgramDay(day_number=i + 1, slots=slots))
    minimal_prog = NutritionProgram(code="MIN01", slug="min01", days=days)

    # 2 meals + 0 snacks should succeed perfectly
    adapted_2_0 = adapt_program(minimal_prog, MainMealCountBucket.TWO, SnackCountBucket.ZERO)
    assert len(adapted_2_0.days[0].slots) == 2
    assert [s.role for s in adapted_2_0.days[0].slots] == ["lunch", "dinner"]

    # 3 meals (needs breakfast) should raise ProgramStructureIncompatibleError
    with pytest.raises(ProgramStructureIncompatibleError, match="breakfast"):
        adapt_program(minimal_prog, MainMealCountBucket.THREE, SnackCountBucket.ZERO)

    # 1 snack requested when no snacks exist should raise ProgramStructureIncompatibleError
    with pytest.raises(ProgramStructureIncompatibleError, match="snack"):
        adapt_program(minimal_prog, MainMealCountBucket.TWO, SnackCountBucket.ONE)


def test_adaptation_cycles_single_snack_without_division_by_zero() -> None:
    # Program with exactly 1 snack for the whole week
    lunches = [_meal("LU01", MealCategory.LUNCH)]
    dinners = [_meal("DN01", MealCategory.DINNER)]
    breakfasts = [_meal("BF01", MealCategory.BREAKFAST)]
    snack = _meal("SN01", MealCategory.SNACK)
    days = []
    for i in range(7):
        slots = [
            NutritionProgramSlot(
                kind=NutritionProgramSlotKind.CATALOGUE_MEAL,
                category=MealCategory.BREAKFAST,
                meal=breakfasts[0],
                meal_id=breakfasts[0].id,
            ),
            NutritionProgramSlot(
                kind=NutritionProgramSlotKind.CATALOGUE_MEAL,
                category=MealCategory.LUNCH,
                meal=lunches[0],
                meal_id=lunches[0].id,
            ),
            NutritionProgramSlot(
                kind=NutritionProgramSlotKind.CATALOGUE_MEAL,
                category=MealCategory.DINNER,
                meal=dinners[0],
                meal_id=dinners[0].id,
            ),
            NutritionProgramSlot(
                kind=NutritionProgramSlotKind.CATALOGUE_MEAL,
                category=MealCategory.SNACK,
                meal=snack,
                meal_id=snack.id,
            ),
        ]
        days.append(NutritionProgramDay(day_number=i + 1, slots=slots))
    single_snack_prog = NutritionProgram(code="SNK01", slug="snk01", days=days)

    # Requesting 3 snacks when only 1 snack exists should cycle that snack without ZeroDivisionError
    adapted_3_snacks = adapt_program(
        single_snack_prog, MainMealCountBucket.THREE, SnackCountBucket.THREE_OR_MORE
    )
    assert len(adapted_3_snacks.days[0].slots) == 6
    snack_roles = [s for s in adapted_3_snacks.days[0].slots if s.role == "snack"]
    assert len(snack_roles) == 3
    assert all(s.meal_code == "SN01" for s in snack_roles)
