from datetime import UTC, date, datetime
from decimal import Decimal
from types import SimpleNamespace

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

import app.nutrition.plan_service as plan_service
from app.nutrition.enums import (
    EstimateConfidence,
    FoodRole,
    FoodVerificationStatus,
    MealCategory,
    MealIngredientRole,
    NutritionDietStyle,
    NutritionProgramSlotKind,
    PriceReferenceStatus,
)
from app.nutrition.models import (
    NutritionCatalogueFood,
    NutritionCatalogueFoodRole,
    NutritionCatalogueMeal,
    NutritionCatalogueMealItem,
    NutritionFoodComposition,
    NutritionFoodPriceReference,
    NutritionPlanGeneration,
    NutritionProgram,
    NutritionProgramDay,
    NutritionProgramSlot,
    NutritionWeeklyPlan,
)
from app.nutrition.planner_engine import GenerationOutcome, NutrientComparison, PlannerResult

ORIGIN = {"Origin": "http://localhost:5173"}


def _birth_date() -> str:
    today = date.today()
    return date(today.year - 25, today.month, min(today.day, 28)).isoformat()


def _register_and_estimate(
    client: TestClient,
    email: str,
    *,
    meals: int = 2,
    snacks: int = 1,
    goal: str = "maintain_weight",
) -> None:
    assert (
        client.post(
            "/api/v1/auth/register",
            headers=ORIGIN,
            json={"email": email, "password": "long password"},
        ).status_code
        == 201
    )
    assert (
        client.post(
            "/api/v1/profile/mode", headers=ORIGIN, json={"product_mode": "nutrition"}
        ).status_code
        == 201
    )
    assert (
        client.put(
            "/api/v1/profile/shared",
            headers=ORIGIN,
            json={
                "display_name": "کاربر برنامه",
                "birth_date": _birth_date(),
                "sex": "female",
                "height_cm": 165,
                "current_weight_kg": 62.5,
                "fitness_goal": goal,
            },
        ).status_code
        == 200
    )
    assert (
        client.put(
            "/api/v1/nutrition/safety",
            headers=ORIGIN,
            json={
                "conditions": [],
                "medications": [],
                "dangerous_food_reaction_history": False,
                "pregnant": False,
                "breastfeeding": False,
                "eating_disorder_diagnosed": False,
                "eating_disorder_active_symptoms": False,
                "emergency_or_danger_symptoms": False,
                "physician_dietary_restrictions": None,
                "other_relevant_condition": None,
            },
        ).status_code
        == 200
    )
    assert (
        client.put(
            "/api/v1/nutrition/profile",
            headers=ORIGIN,
            json={
                "daily_activity_level": "moderate",
                "individual_monthly_food_budget_irr": 100_000_000,
                "budget_style": "strict",
                "meals_per_day": meals,
                "snacks_per_day": snacks,
                "preferred_plan_start_day": "saturday",
                "plan_style": "balanced",
                "cooking_skill": "basic",
                "maximum_cooking_time_minutes": 45,
                "cooking_frequency_per_week": 4,
                "meal_preparation_preference": "mixed",
                "refrigerator_access": True,
                "freezer_access": True,
                "cooking_equipment": ["stove"],
                "supplied_meals_per_week": 0,
                "supplied_meal_source": None,
                "foods_available_at_home": [],
                "favourite_foods": [],
                "disliked_foods": [],
                "never_suggest_foods": [],
                "refused_foods": [],
                "allergies": [],
                "intolerances": [],
                "dietary_pattern": "omnivore",
                "religious_cultural_exclusions": [],
                "preferred_variety": "medium",
                "maximum_meal_repetition_per_week": 2,
                "accepts_leftovers": True,
                "accepts_batch_cooking": True,
                "work_shift_context": None,
                "daily_check_in_enabled": False,
                "preferred_check_in_time": None,
            },
        ).status_code
        == 200
    )
    assert (
        client.put(
            "/api/v1/nutrition/structured-exercise", headers=ORIGIN, json={"trains": False}
        ).status_code
        == 200
    )
    assert client.post("/api/v1/nutrition/estimates", headers=ORIGIN).status_code == 201


def _seed_foods_and_prices(db: Session) -> None:
    rows = (
        ("task6-chicken", "مرغ", (FoodRole.MAIN_PROTEIN,), "165", "31", "0", "3.6", "20"),
        ("task6-lentils", "عدس", (FoodRole.MAIN_PROTEIN,), "116", "9", "20", "0.4", "19"),
        ("task6-rice", "برنج", (FoodRole.MAIN_STAPLE,), "360", "7", "79", "0.6", "10"),
        ("task6-potato", "سیب زمینی", (FoodRole.MAIN_STAPLE,), "77", "2", "17", "0.1", "12"),
        (
            "task6-yogurt",
            "ماست",
            (FoodRole.SNACK, FoodRole.FLEXIBLE),
            "61",
            "3.5",
            "4.7",
            "3.3",
            "121",
        ),
        ("task6-oil", "روغن زیتون", (FoodRole.FLEXIBLE,), "884", "0", "0", "100", "1"),
    )
    now = datetime.now(UTC)
    foods: dict[str, NutritionCatalogueFood] = {}
    for index, (slug, name, roles, kcal, protein, carbs, fat, calcium) in enumerate(rows):
        food = NutritionCatalogueFood(
            slug=slug,
            name_fa=name,
            name_en=slug,
            verification_status=FoodVerificationStatus.VERIFIED,
            source_name="USDA FoodData Central test mapping",
            source_reference="https://fdc.nal.usda.gov/",
            source_food_id=f"fdc-{index}",
            roles=[NutritionCatalogueFoodRole(role=role) for role in roles],
            compositions=[
                NutritionFoodComposition(
                    nutrient_code=code,
                    value_per_100g=Decimal(value),
                    unit=unit,
                    unit_form="nutrient_mass",
                    source_name="USDA FoodData Central test mapping",
                    source_reference="https://fdc.nal.usda.gov/",
                    confidence=EstimateConfidence.HIGH,
                )
                for code, value, unit in (
                    ("energy_kcal", kcal, "kcal"),
                    ("protein_g", protein, "g"),
                    ("carbohydrate_g", carbs, "g"),
                    ("total_fat_g", fat, "g"),
                    ("fibre_g", "2", "g"),
                    ("calcium_mg", calcium, "mg"),
                    ("sodium_mg", "50", "mg"),
                )
            ],
        )
        db.add(food)
        db.flush()
        foods[slug] = food
        db.add(
            NutritionFoodPriceReference(
                food_id=food.id,
                canonical_unit="TOMAN_PER_KG",
                reference_price_toman=Decimal("100000"),
                sample_count=3,
                confidence=EstimateConfidence.HIGH,
                status=PriceReferenceStatus.ACCEPTED,
                calculated_at=now,
                accepted_at=now,
            )
        )
    breakfast = NutritionCatalogueMeal(
        code="TST-BF01",
        name_fa="ماست صبحانه تست",
        name_en="Test breakfast yogurt",
        category=MealCategory.BREAKFAST,
        verification_status=FoodVerificationStatus.VERIFIED,
        items=[_meal_item(foods["task6-yogurt"], "200", "100", "350", "protein")],
    )
    lunch = NutritionCatalogueMeal(
        code="TST-LU01",
        name_fa="مرغ و برنج تست",
        name_en="Test chicken and rice",
        image_path="/media/meal-catalogue/test-lunch.png",
        category=MealCategory.LUNCH,
        verification_status=FoodVerificationStatus.VERIFIED,
        items=[
            _meal_item(foods["task6-chicken"], "150", "80", "220", "protein"),
            _meal_item(foods["task6-rice"], "80", "50", "140", "carbohydrate"),
            _meal_item(foods["task6-oil"], "5", "2", "10", "fat", required=False),
        ],
    )
    dinner = NutritionCatalogueMeal(
        code="TST-DN01",
        name_fa="عدس و سیب‌زمینی تست",
        name_en="Test lentils and potato",
        category=MealCategory.DINNER,
        verification_status=FoodVerificationStatus.VERIFIED,
        items=[
            _meal_item(foods["task6-lentils"], "180", "100", "300", "protein"),
            _meal_item(foods["task6-potato"], "250", "150", "400", "carbohydrate"),
            _meal_item(foods["task6-oil"], "20", "10", "30", "fat"),
        ],
    )
    snack = NutritionCatalogueMeal(
        code="TST-SN01",
        name_fa="میان‌وعده ماست تست",
        name_en="Test yogurt snack",
        category=MealCategory.SNACK,
        verification_status=FoodVerificationStatus.VERIFIED,
        items=[_meal_item(foods["task6-yogurt"], "200", "100", "350", "protein")],
    )
    db.add_all([breakfast, lunch, dinner, snack])
    db.flush()
    db.add(
        NutritionProgram(
            code="TST-PROGRAM",
            slug="tst-program",
            name_fa="برنامه تست",
            name_en="Test program",
            description_fa="برنامه تست",
            description_en="Test program",
            diet_style=NutritionDietStyle.BALANCED_IRANIAN,
            days=[
                NutritionProgramDay(
                    day_number=day_number,
                    slots=[
                        NutritionProgramSlot(
                            category=MealCategory.BREAKFAST,
                            kind=NutritionProgramSlotKind.CATALOGUE_MEAL,
                            meal_id=breakfast.id,
                        ),
                        NutritionProgramSlot(
                            category=MealCategory.LUNCH,
                            kind=NutritionProgramSlotKind.CATALOGUE_MEAL,
                            meal_id=lunch.id,
                        ),
                        NutritionProgramSlot(
                            category=MealCategory.DINNER,
                            kind=NutritionProgramSlotKind.CATALOGUE_MEAL,
                            meal_id=dinner.id,
                        ),
                        NutritionProgramSlot(
                            category=MealCategory.SNACK,
                            kind=NutritionProgramSlotKind.CATALOGUE_MEAL,
                            meal_id=snack.id,
                        ),
                    ],
                )
                for day_number in range(1, 8)
            ],
        )
    )
    db.commit()


def _meal_item(
    food: NutritionCatalogueFood,
    reference: str,
    minimum: str,
    maximum: str,
    role: str,
    *,
    required: bool = True,
) -> NutritionCatalogueMealItem:
    return NutritionCatalogueMealItem(
        food_id=food.id,
        reference_grams=Decimal(reference),
        min_grams=Decimal(minimum),
        max_grams=Decimal(maximum),
        is_required=required,
        functional_role=MealIngredientRole(role),
    )


def test_generation_returns_visible_seven_day_draft_and_creates_review(
    client: TestClient, db: Session
) -> None:
    _register_and_estimate(client, "weekly-plan-success@example.com", meals=2, snacks=1)
    _seed_foods_and_prices(db)

    response = client.post("/api/v1/nutrition/plans", headers=ORIGIN)

    assert response.status_code == 201
    body = response.json()
    assert body["outcome"] == "success", body
    assert body["plan"]["lifecycle_status"] == "pending_physician_review"
    assert body["plan"]["is_user_visible"] is True
    assert body["plan"]["review_status"] == "pending"
    assert body["plan"]["physician_approved"] is False
    assert len(body["plan"]["days"]) == 7
    assert all(
        sum(meal["slot_role"] == "main_meal" for meal in day["meals"]) == 2
        for day in body["plan"]["days"]
    )
    assert all(
        sum(meal["slot_role"] == "snack" for meal in day["meals"]) == 1
        for day in body["plan"]["days"]
    )
    assert body["plan"]["weekly_cost_irr"] > 0
    assert body["plan"]["input_snapshot"]["main_meals_per_day"] == 2
    assert body["plan"]["price_snapshot"]["currency"] == "IRR"
    assert all(
        meal["catalogue_meal_id"] is not None and meal["catalogue_meal_category"]
        for day in body["plan"]["days"]
        for meal in day["meals"]
    )
    catalogue_meals = {
        str(meal.id): meal for meal in db.scalars(select(NutritionCatalogueMeal)).all()
    }
    for day in body["plan"]["days"]:
        for meal in day["meals"]:
            catalogue = catalogue_meals[meal["catalogue_meal_id"]]
            assert meal["name_fa"] == catalogue.name_fa
            assert meal["name_en"] == catalogue.name_en
            assert meal["meal_code"] == catalogue.code
            assert meal["image_url"] == catalogue.image_path
    revision = client.get(f"/api/v1/nutrition/plans/{body['plan']['id']}")
    assert revision.status_code == 200
    assert revision.json()["id"] == body["plan"]["id"]


def test_generation_continues_with_alignment_warning_for_muscle_goal_without_training(
    client: TestClient, db: Session
) -> None:
    _register_and_estimate(
        client,
        "weekly-plan-goal-warning@example.com",
        goal="build_muscle",
    )
    _seed_foods_and_prices(db)

    response = client.post("/api/v1/nutrition/plans", headers=ORIGIN)

    assert response.status_code == 201
    body = response.json()
    assert body["outcome"] == "success", body
    assert "TRAINING_STIMULUS_MISMATCH" in body["warning_codes"]
    assert "TARGETS_GENERATED_WITH_GOAL_COACHING_WARNING" in body["warning_codes"]
    assert "TRAINING_STIMULUS_MISMATCH" in body["plan"]["explanation_codes"]
    profile = client.get("/api/v1/profile/shared", headers=ORIGIN)
    assert profile.status_code == 200
    assert profile.json()["fitness_goal"] == "build_muscle"


def test_generation_evaluates_every_program_and_persists_only_the_best_result(
    client: TestClient, db: Session, monkeypatch
) -> None:
    _register_and_estimate(client, "weekly-plan-all-candidates@example.com")
    programs = [
        NutritionProgram(
            code=f"TEST-{letter}",
            slug=f"test-{letter.casefold()}",
            name_fa=f"برنامه {letter}",
            name_en=f"Test {letter}",
            description_fa="برنامه تست",
            description_en="Test program",
            diet_style=NutritionDietStyle.BALANCED_IRANIAN,
            is_active=True,
        )
        for letter in ("A", "B", "C")
    ]
    db.add_all(programs)
    db.flush()

    monkeypatch.setattr(plan_service, "list_programs", lambda _db: programs)
    monkeypatch.setattr(plan_service, "_planner_foods", lambda _db: ((), {}, {"foods": []}))
    monkeypatch.setattr(plan_service, "_planner_meal_templates", lambda _db: ((), []))
    monkeypatch.setattr(
        plan_service,
        "adapt_program",
        lambda *_args, **_kwargs: SimpleNamespace(days=()),
    )
    calls = []
    results = (
        PlannerResult(
            outcome=GenerationOutcome.SUCCESS,
            reason_codes=("SAFE_FEASIBLE_DRAFT_GENERATED",),
            weekly_cost_irr=Decimal("100"),
            budget_status="within_budget",
            nutrient_comparisons={
                "goal_calories": NutrientComparison(
                    preferred=Decimal("2000"),
                    minimum_or_maximum=None,
                    planned=Decimal("1500"),
                    difference_from_preferred=Decimal("-500"),
                    difference_from_limit=None,
                    status="within_target",
                )
            },
        ),
        PlannerResult(
            outcome=GenerationOutcome.SUCCESS,
            reason_codes=("SAFE_FEASIBLE_DRAFT_GENERATED",),
            weekly_cost_irr=Decimal("100"),
            budget_status="within_budget",
            nutrient_comparisons={
                "goal_calories": NutrientComparison(
                    preferred=Decimal("2000"),
                    minimum_or_maximum=None,
                    planned=Decimal("2000"),
                    difference_from_preferred=Decimal("0"),
                    difference_from_limit=None,
                    status="within_target",
                )
            },
        ),
        PlannerResult(
            outcome=GenerationOutcome.INFEASIBLE,
            reason_codes=("STRICT_BUDGET_EXCEEDED",),
        ),
    )

    def fake_plan_week(inputs, foods, meal_templates, policy=plan_service.DEFAULT_POLICY, **kwargs):
        calls.append((inputs, foods, meal_templates, policy))
        return results[len(calls) - 1]

    monkeypatch.setattr(plan_service, "plan_week", fake_plan_week)

    response = client.post("/api/v1/nutrition/plans", headers=ORIGIN)

    assert response.status_code == 201
    assert response.json()["outcome"] == "success"
    assert response.json()["plan"]["input_snapshot"]["nutrition_program_code"] == "TEST-B"
    assert len(calls) == 3
    assert db.scalar(select(NutritionWeeklyPlan)) is not None
    assert len(db.scalars(select(NutritionWeeklyPlan)).all()) == 1
    generation = db.scalar(select(NutritionPlanGeneration))
    assert generation is not None
    trace = generation.diagnostic_snapshot["selection_trace"]
    assert trace["proposed_candidate_count"] == 3
    assert trace["evaluated_candidate_count"] == 3
    assert trace["successful_candidate_count"] == 2
    assert trace["first_valid_program_code"] == "TEST-A"
    assert trace["selected_program_code"] == "TEST-B"
    assert trace["selected_differs_from_first_valid"] is True


def test_generation_aggregates_all_candidate_failures_without_persisting_a_plan(
    client: TestClient, db: Session, monkeypatch
) -> None:
    _register_and_estimate(client, "weekly-plan-all-candidates-fail@example.com")
    _seed_foods_and_prices(db)
    programs = plan_service.list_programs(db)

    def fake_plan_week(inputs, foods, meal_templates, policy=plan_service.DEFAULT_POLICY, **kwargs):
        return PlannerResult(
            outcome=GenerationOutcome.INFEASIBLE,
            reason_codes=("STRICT_BUDGET_NO_FEASIBLE_REPAIR",),
        )

    monkeypatch.setattr(plan_service, "plan_week", fake_plan_week)

    response = client.post("/api/v1/nutrition/plans", headers=ORIGIN)

    assert response.status_code == 201
    assert response.json()["outcome"] == "infeasible"
    assert response.json()["plan"] is None
    assert db.scalar(select(NutritionWeeklyPlan)) is None
    generation = db.scalar(select(NutritionPlanGeneration))
    assert generation is not None
    trace = generation.diagnostic_snapshot["selection_trace"]
    assert trace["proposed_candidate_count"] == len(programs)
    assert trace["evaluated_candidate_count"] == len(programs)
    assert trace["successful_candidate_count"] == 0
    assert trace["selected_program_code"] is None
    assert trace["failure_reason_counts"] == {"STRICT_BUDGET_NO_FEASIBLE_REPAIR": len(programs)}


def test_missing_price_coverage_is_a_generation_not_a_plan(client: TestClient, db: Session) -> None:
    _register_and_estimate(client, "weekly-plan-no-price@example.com")

    response = client.post("/api/v1/nutrition/plans", headers=ORIGIN)

    assert response.status_code == 201
    assert response.json()["outcome"] == "live_price_unavailable"
    assert response.json()["reason_codes"] == ["INSUFFICIENT_PRICE_COVERAGE"]
    assert response.json()["plan"] is None
    assert db.scalar(select(NutritionPlanGeneration)) is not None
    assert db.scalar(select(NutritionWeeklyPlan)) is None


def test_latest_and_history_keep_old_snapshot_when_market_price_changes(
    client: TestClient, db: Session
) -> None:
    _register_and_estimate(client, "weekly-plan-history@example.com")
    _seed_foods_and_prices(db)
    generated = client.post("/api/v1/nutrition/plans", headers=ORIGIN)
    original_cost = generated.json()["plan"]["weekly_cost_irr"]
    references = db.scalars(select(NutritionFoodPriceReference)).all()
    for reference in references:
        reference.reference_price_toman *= 10
    db.commit()

    latest = client.get("/api/v1/nutrition/plans/latest")
    history = client.get("/api/v1/nutrition/plans/history")
    active = client.get("/api/v1/nutrition/plans/active")

    assert latest.status_code == 200
    assert latest.json()["weekly_cost_irr"] == original_cost
    assert history.status_code == 200
    assert history.json()[0]["weekly_cost_irr"] == original_cost
    assert active.status_code == 404
    assert active.json()["detail"]["code"] == "ACTIVE_NUTRITION_PLAN_NOT_FOUND"


def test_stale_reference_prices_are_not_used_as_live_prices(
    client: TestClient, db: Session
) -> None:
    _register_and_estimate(client, "weekly-plan-stale-price@example.com")
    _seed_foods_and_prices(db)
    old = datetime(2025, 1, 1, tzinfo=UTC)
    for reference in db.scalars(select(NutritionFoodPriceReference)):
        reference.accepted_at = old
    db.commit()

    response = client.post("/api/v1/nutrition/plans", headers=ORIGIN)

    assert response.status_code == 201
    assert response.json()["outcome"] == "live_price_unavailable"
    assert response.json()["reason_codes"] == ["INSUFFICIENT_PRICE_COVERAGE"]


def test_safety_block_is_persisted_without_creating_a_plan(client: TestClient, db: Session) -> None:
    assert (
        client.post(
            "/api/v1/auth/register",
            headers=ORIGIN,
            json={"email": "weekly-plan-blocked@example.com", "password": "long password"},
        ).status_code
        == 201
    )
    assert (
        client.post(
            "/api/v1/profile/mode", headers=ORIGIN, json={"product_mode": "nutrition"}
        ).status_code
        == 201
    )
    assert (
        client.put(
            "/api/v1/profile/shared",
            headers=ORIGIN,
            json={
                "display_name": "کاربر پرخطر",
                "birth_date": _birth_date(),
                "sex": "female",
                "height_cm": 165,
                "current_weight_kg": 62.5,
                "fitness_goal": "maintain_weight",
            },
        ).status_code
        == 200
    )
    assert (
        client.put(
            "/api/v1/nutrition/safety",
            headers=ORIGIN,
            json={
                "conditions": [{"code": "kidney_disease", "details": None}],
                "medications": [],
                "dangerous_food_reaction_history": False,
                "pregnant": False,
                "breastfeeding": False,
                "eating_disorder_diagnosed": False,
                "eating_disorder_active_symptoms": False,
                "emergency_or_danger_symptoms": False,
                "physician_dietary_restrictions": None,
                "other_relevant_condition": None,
            },
        ).status_code
        == 200
    )

    response = client.post("/api/v1/nutrition/plans", headers=ORIGIN)

    assert response.status_code == 201
    assert response.json()["outcome"] == "safety_blocked"
    assert response.json()["plan"] is None
    assert db.scalar(select(NutritionPlanGeneration)) is not None
    assert db.scalar(select(NutritionWeeklyPlan)) is None
