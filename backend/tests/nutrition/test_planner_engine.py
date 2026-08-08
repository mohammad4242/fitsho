from decimal import Decimal


def _food(
    slug: str,
    roles: tuple[str, ...],
    *,
    kcal: str,
    protein: str = "0",
    carbs: str = "0",
    fat: str = "0",
    price: str = "1000",
    extra: dict[str, str] | None = None,
):
    from app.nutrition.planner_engine import PlannerFood

    nutrients = {
        "energy_kcal": Decimal(kcal),
        "protein_g": Decimal(protein),
        "carbohydrate_g": Decimal(carbs),
        "total_fat_g": Decimal(fat),
        "fibre_g": Decimal("1"),
        **{key: Decimal(value) for key, value in (extra or {}).items()},
    }
    return PlannerFood(
        food_id=slug,
        slug=slug,
        name_fa=slug,
        name_en=slug.replace("-", " ").title(),
        roles=roles,
        nutrients_per_100g=nutrients,
        price_irr_per_gram=Decimal(price),
        price_reference_id=f"price-{slug}",
    )


def _input(**changes: object):
    from app.nutrition.planner_engine import PlannerInput

    values: dict[str, object] = {
        "daily_targets": {
            "goal_calories": Decimal("2000"),
            "protein": Decimal("100"),
            "carbohydrate": Decimal("220"),
            "total_fat": Decimal("60"),
            "fibre": Decimal("25"),
        },
        "micronutrient_targets": {"calcium_mg": Decimal("1000")},
        "micronutrient_upper_limits": {"sodium_mg": Decimal("2300")},
        "daily_minimums": {
            "protein": Decimal("70"),
            "carbohydrate": Decimal("180"),
            "total_fat": Decimal("30"),
        },
        "daily_maximums": {
            "carbohydrate": Decimal("320"),
            "total_fat": Decimal("90"),
            "free_sugar": Decimal("50"),
        },
        "main_meals_per_day": 3,
        "snacks_per_day": 1,
        "weekly_budget_irr": 100_000_000,
        "budget_mode": "strict",
        "excluded_terms": (),
        "liked_terms": (),
        "disliked_terms": (),
        "dietary_pattern": "omnivore",
        "maximum_meal_repetition_per_week": 2,
    }
    values.update(changes)
    return PlannerInput(**values)  # type: ignore[arg-type]


def _catalogue():
    return (
        _food("chicken", ("main_protein",), kcal="165", protein="31", fat="3.6"),
        _food(
            "lentils",
            ("main_protein",),
            kcal="116",
            protein="9",
            carbs="20",
            extra={"calcium_mg": "19"},
        ),
        _food("rice", ("main_staple",), kcal="360", protein="7", carbs="79"),
        _food("potato", ("main_staple",), kcal="77", protein="2", carbs="17"),
        _food(
            "yogurt",
            ("snack", "flexible"),
            kcal="61",
            protein="3.5",
            carbs="4.7",
            fat="3.3",
            extra={"calcium_mg": "121"},
        ),
        _food("olive-oil", ("flexible",), kcal="884", fat="100"),
    )


def test_planner_creates_exact_user_selected_slots_for_seven_days() -> None:
    from app.nutrition.planner_engine import GenerationOutcome, plan_week

    result = plan_week(_input(main_meals_per_day=2, snacks_per_day=2), _catalogue())

    assert result.outcome is GenerationOutcome.SUCCESS
    assert len(result.days) == 7
    assert all(sum(meal.role == "main_meal" for meal in day.meals) == 2 for day in result.days)
    assert all(sum(meal.role == "snack" for meal in day.meals) == 2 for day in result.days)


def test_planner_is_deterministic_and_controls_repetition() -> None:
    from app.nutrition.planner_engine import plan_week

    first = plan_week(_input(), _catalogue())
    second = plan_week(_input(), tuple(reversed(_catalogue())))

    assert first == second
    proteins = [
        meal.foods[0].slug for day in first.days for meal in day.meals if meal.role == "main_meal"
    ]
    assert {"chicken", "lentils"} <= set(proteins)


def test_allergy_filter_is_hard_and_role_specific() -> None:
    from app.nutrition.planner_engine import plan_week

    result = plan_week(_input(excluded_terms=("chicken",)), _catalogue())

    assert all(
        food.slug != "chicken" for day in result.days for meal in day.meals for food in meal.foods
    )
    assert all(
        food.roles == ("snack", "flexible")
        for day in result.days
        for meal in day.meals
        if meal.role == "snack"
        for food in meal.foods
    )


def test_missing_required_price_coverage_returns_structured_outcome() -> None:
    from app.nutrition.planner_engine import GenerationOutcome, plan_week

    foods = tuple(food for food in _catalogue() if food.roles != ("main_staple",))
    result = plan_week(_input(), foods)

    assert result.outcome is GenerationOutcome.LIVE_PRICE_UNAVAILABLE
    assert result.reason_codes == ("INSUFFICIENT_PRICE_COVERAGE",)
    assert result.days == ()


def test_strict_budget_is_hard_and_flexible_budget_has_a_versioned_cap() -> None:
    from app.nutrition.planner_engine import GenerationOutcome, plan_week

    strict = plan_week(_input(weekly_budget_irr=1_000), _catalogue())
    flexible = plan_week(_input(weekly_budget_irr=20_000_000, budget_mode="flexible"), _catalogue())

    assert strict.outcome is GenerationOutcome.INFEASIBLE
    assert "STRICT_BUDGET_EXCEEDED" in strict.reason_codes
    assert flexible.outcome is GenerationOutcome.SUCCESS
    assert flexible.budget_status in {"within_budget", "flexible_overage"}


def test_micronutrients_affect_selection_and_repair_is_bounded() -> None:
    from app.nutrition.planner_engine import plan_week

    result = plan_week(_input(), _catalogue())

    assert result.repair_actions
    assert len(result.repair_actions) <= 3
    assert result.nutrient_comparisons["calcium_mg"].planned > 0


def test_upper_limit_violation_never_creates_a_successful_plan() -> None:
    from app.nutrition.planner_engine import GenerationOutcome, plan_week

    salty = _food(
        "salty-chicken",
        ("main_protein",),
        kcal="165",
        protein="31",
        extra={"sodium_mg": "10000"},
    )
    foods = (salty, *_catalogue()[2:])
    result = plan_week(_input(), foods)

    assert result.outcome is GenerationOutcome.INFEASIBLE
    assert "NUTRIENT_UPPER_LIMIT_EXCEEDED" in result.reason_codes


def test_result_snapshots_are_immutable() -> None:
    from dataclasses import FrozenInstanceError

    import pytest

    from app.nutrition.planner_engine import plan_week

    result = plan_week(_input(), _catalogue())
    with pytest.raises(FrozenInstanceError):
        result.weekly_cost_irr = Decimal("0")  # type: ignore[misc]


def test_dietary_pattern_is_a_hard_candidate_filter() -> None:
    from app.nutrition.planner_engine import GenerationOutcome, PlannerFood, plan_week

    foods = tuple(
        PlannerFood(
            **{
                **food.__dict__,
                "dietary_patterns": (
                    ("omnivore",) if food.slug == "chicken" else ("omnivore", "vegan")
                ),
            }
        )
        for food in _catalogue()
    )

    result = plan_week(_input(dietary_pattern="vegan"), foods)

    assert result.outcome is GenerationOutcome.SUCCESS
    assert all(
        food.slug != "chicken" for day in result.days for meal in day.meals for food in meal.foods
    )


def test_macro_floor_failure_is_target_infeasible_after_full_validation() -> None:
    from app.nutrition.planner_engine import GenerationOutcome, plan_week

    result = plan_week(
        _input(daily_minimums={"protein": Decimal("900")}),
        _catalogue(),
    )

    assert result.outcome is GenerationOutcome.TARGET_INFEASIBLE
    assert "MACRONUTRIENT_FLOOR_NOT_MET" in result.reason_codes


def test_missing_supported_nutrient_data_is_reported_not_treated_as_zero() -> None:
    from app.nutrition.planner_engine import plan_week

    result = plan_week(_input(), _catalogue())

    comparison = result.nutrient_comparisons["free_sugar"]
    assert comparison.status == "data_incomplete"
    assert comparison.data_confidence == "low"
    assert "NUTRIENT_DATA_INCOMPLETE" in result.warning_codes


def test_micronutrient_density_influences_initial_candidate_order() -> None:
    from app.nutrition.planner_engine import plan_week

    enriched = _food(
        "calcium-lentils",
        ("main_protein",),
        kcal="116",
        protein="9",
        carbs="20",
        extra={"calcium_mg": "500"},
    )
    foods = (*_catalogue(), enriched)

    result = plan_week(_input(), foods)

    first_protein = result.days[0].meals[0].foods[0]
    assert first_protein.slug == "calcium-lentils"
