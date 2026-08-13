from uuid import UUID

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.models import User
from app.nutrition.enums import FoodVerificationStatus, MealCategory, NutritionDietStyle
from app.nutrition.models import NutritionCatalogueMeal, NutritionProgram

ORIGIN = {"Origin": "http://localhost:5173"}
PROGRAMS_PATH = "/api/v1/nutrition/admin/programs"


def _register(client: TestClient, db: Session, email: str, *, admin: bool = False) -> None:
    response = client.post(
        "/api/v1/auth/register",
        headers=ORIGIN,
        json={"email": email, "password": "long password"},
    )
    assert response.status_code == 201
    if admin:
        user = db.scalar(select(User).where(User.email == email))
        assert user is not None
        user.is_admin = True
        db.commit()


def _meal_library(db: Session) -> dict[str, UUID]:
    meals = {
        category.value: NutritionCatalogueMeal(
            code=f"TST-{category.value.upper()}",
            name_fa=f"وعده {category.value}",
            name_en=f"Verified {category.value}",
            image_path=(
                "/media/meal-catalogue/breakfast.png"
                if category is MealCategory.BREAKFAST
                else None
            ),
            category=category,
            verification_status=FoodVerificationStatus.VERIFIED,
        )
        for category in MealCategory
    }
    db.add_all(meals.values())
    db.commit()
    return {category: meal.id for category, meal in meals.items()}


def _program_payload(
    meals: dict[str, UUID],
    *,
    diet_style: str = "balanced_iranian",
    post_workout_enabled: bool = True,
) -> dict[str, object]:
    days: list[dict[str, object]] = []
    for day_number in range(1, 8):
        daily_post_workout = post_workout_enabled and day_number in {1, 3, 5}
        slots = [
            {"category": category, "meal_id": str(meals[category])}
            for category in ("breakfast", "lunch", "snack", "dinner")
        ]
        if daily_post_workout:
            slots.append({"category": "post_workout", "meal_id": str(meals["post_workout"])})
        days.append(
            {
                "day_number": day_number,
                "post_workout_enabled": daily_post_workout,
                "slots": slots,
            }
        )
    return {
        "code": f"{diet_style.upper().replace('_', '-')[:8]}-TST",
        "name_fa": "برنامه هفتگی ایرانی",
        "name_en": "Iranian weekly structure",
        "description_fa": "ساختار هفت‌روزه بدون تعیین مقدار.",
        "description_en": "Seven-day structure without portions.",
        "diet_style": diet_style,
        "post_workout_enabled": post_workout_enabled,
        "days": days,
    }


def test_admin_stores_friday_free_meal_without_catalogue_uuid(
    client: TestClient,
    db: Session,
) -> None:
    meals = _meal_library(db)
    _register(client, db, "nutrition-program-free-meal@example.com", admin=True)
    payload = _program_payload(meals, post_workout_enabled=False)
    friday = payload["days"][6]  # type: ignore[index]
    friday["slots"][1] = {"kind": "free_meal", "category": "lunch", "meal_id": None}  # type: ignore[index]

    response = client.post(PROGRAMS_PATH, headers=ORIGIN, json=payload)

    assert response.status_code == 201
    body = response.json()
    assert body["code"] == "BALANCED-TST"
    free_slot = body["days"][6]["slots"][1]
    assert free_slot == {
        "id": free_slot["id"],
        "kind": "free_meal",
        "category": "lunch",
        "meal": None,
    }
    assert (
        db.scalar(select(NutritionCatalogueMeal).where(NutritionCatalogueMeal.code == "FREE_MEAL"))
        is None
    )


def test_admin_rejects_invalid_free_meal_relationships(client: TestClient, db: Session) -> None:
    meals = _meal_library(db)
    _register(client, db, "nutrition-program-free-validation@example.com", admin=True)
    payload = _program_payload(meals, post_workout_enabled=False)
    payload["days"][6]["slots"][1] = {  # type: ignore[index]
        "kind": "free_meal",
        "category": "lunch",
        "meal_id": str(meals["lunch"]),
    }

    assert client.post(PROGRAMS_PATH, headers=ORIGIN, json=payload).status_code == 422

    payload = _program_payload(meals, post_workout_enabled=False)
    payload["days"][0]["slots"][1] = {  # type: ignore[index]
        "kind": "catalogue_meal",
        "category": "lunch",
        "meal_id": None,
    }
    assert client.post(PROGRAMS_PATH, headers=ORIGIN, json=payload).status_code == 422


def test_program_catalogue_requires_admin(client: TestClient, db: Session) -> None:
    assert client.get(PROGRAMS_PATH).status_code == 401

    _register(client, db, "nutrition-program-member@example.com")

    assert client.get(PROGRAMS_PATH).status_code == 403


def test_admin_creates_seven_day_program_from_verified_category_matched_meals(
    client: TestClient,
    db: Session,
) -> None:
    meals = _meal_library(db)
    _register(client, db, "nutrition-program-admin@example.com", admin=True)

    response = client.post(PROGRAMS_PATH, headers=ORIGIN, json=_program_payload(meals))

    assert response.status_code == 201
    body = response.json()
    assert body["slug"] == "iranian-weekly-structure"
    assert body["diet_style"] == "balanced_iranian"
    assert body["is_active"] is True
    assert body["archived_at"] is None
    assert len(body["days"]) == 7
    assert [day["day_number"] for day in body["days"]] == list(range(1, 8))
    assert [slot["category"] for slot in body["days"][0]["slots"]] == [
        "breakfast",
        "lunch",
        "snack",
        "dinner",
        "post_workout",
    ]
    assert [slot["category"] for slot in body["days"][1]["slots"]] == [
        "breakfast",
        "lunch",
        "snack",
        "dinner",
    ]
    assert "fitness_goal" not in body
    assert "calories" not in body
    breakfast = body["days"][0]["slots"][0]["meal"]
    assert breakfast["code"] == "TST-BREAKFAST"
    assert breakfast["image_url"] == "/media/meal-catalogue/breakfast.png"
    assert body["days"][0]["slots"][1]["meal"]["image_url"] is None
    program = db.scalar(select(NutritionProgram).where(NutritionProgram.id == UUID(body["id"])))
    assert program is not None
    assert program.diet_style is NutritionDietStyle.BALANCED_IRANIAN


def test_admin_rejects_invalid_week_shape_draft_meals_and_category_mismatch(
    client: TestClient,
    db: Session,
) -> None:
    meals = _meal_library(db)
    _register(client, db, "nutrition-program-validation@example.com", admin=True)
    payload = _program_payload(meals)
    payload["days"] = list(payload["days"])[:6]  # type: ignore[arg-type]

    wrong_length = client.post(PROGRAMS_PATH, headers=ORIGIN, json=payload)

    assert wrong_length.status_code == 422

    payload = _program_payload(meals)
    first_day = payload["days"][0]  # type: ignore[index]
    first_day["slots"][0]["meal_id"] = str(meals["lunch"])  # type: ignore[index]

    wrong_category = client.post(PROGRAMS_PATH, headers=ORIGIN, json=payload)

    assert wrong_category.status_code == 422
    assert "match" in str(wrong_category.json()["detail"]).lower()

    draft_meal = db.get(NutritionCatalogueMeal, meals["breakfast"])
    assert draft_meal is not None
    draft_meal.verification_status = FoodVerificationStatus.DRAFT
    db.commit()

    draft_reference = client.post(
        PROGRAMS_PATH,
        headers=ORIGIN,
        json=_program_payload(meals),
    )

    assert draft_reference.status_code == 422
    assert "verified" in str(draft_reference.json()["detail"]).lower()


def test_admin_enforces_global_and_per_day_post_workout_controls(
    client: TestClient,
    db: Session,
) -> None:
    meals = _meal_library(db)
    _register(client, db, "nutrition-program-post-workout@example.com", admin=True)
    disabled_payload = _program_payload(meals, post_workout_enabled=False)
    disabled_payload["days"][0]["post_workout_enabled"] = True  # type: ignore[index]
    disabled_payload["days"][0]["slots"].append(  # type: ignore[index,union-attr]
        {"category": "post_workout", "meal_id": str(meals["post_workout"])}
    )

    globally_disabled = client.post(PROGRAMS_PATH, headers=ORIGIN, json=disabled_payload)

    assert globally_disabled.status_code == 422

    missing_slot_payload = _program_payload(meals)
    missing_slot_payload["days"][0]["slots"] = missing_slot_payload["days"][0]["slots"][:-1]  # type: ignore[index]

    missing_daily_slot = client.post(
        PROGRAMS_PATH,
        headers=ORIGIN,
        json=missing_slot_payload,
    )

    assert missing_daily_slot.status_code == 422


def test_admin_filters_updates_archives_and_restores_programs(
    client: TestClient,
    db: Session,
) -> None:
    meals = _meal_library(db)
    _register(client, db, "nutrition-program-lifecycle@example.com", admin=True)
    balanced = client.post(PROGRAMS_PATH, headers=ORIGIN, json=_program_payload(meals)).json()
    economy = client.post(
        PROGRAMS_PATH,
        headers=ORIGIN,
        json=_program_payload(meals, diet_style="economy"),
    ).json()

    filtered = client.get(f"{PROGRAMS_PATH}?diet_style=economy")

    assert filtered.status_code == 200
    assert [item["id"] for item in filtered.json()["items"]] == [economy["id"]]

    update_payload = _program_payload(meals, diet_style="quick_easy", post_workout_enabled=False)
    update_payload["name_en"] = "Quick weekly structure"
    updated = client.put(
        f"{PROGRAMS_PATH}/{balanced['id']}",
        headers=ORIGIN,
        json=update_payload,
    )

    assert updated.status_code == 200
    assert updated.json()["diet_style"] == "quick_easy"
    assert all(day["post_workout_enabled"] is False for day in updated.json()["days"])

    archived = client.delete(f"{PROGRAMS_PATH}/{economy['id']}", headers=ORIGIN)

    assert archived.status_code == 204
    assert client.get(f"{PROGRAMS_PATH}/{economy['id']}").status_code == 200
    assert client.get(PROGRAMS_PATH).json()["items"] == [updated.json()]
    archived_list = client.get(f"{PROGRAMS_PATH}?lifecycle=archived")
    assert [item["id"] for item in archived_list.json()["items"]] == [economy["id"]]

    restored = client.post(f"{PROGRAMS_PATH}/{economy['id']}/restore", headers=ORIGIN)

    assert restored.status_code == 200
    assert restored.json()["is_active"] is True
    assert restored.json()["archived_at"] is None
