from datetime import date

from fastapi.testclient import TestClient

ORIGIN = {"Origin": "http://localhost:5173"}


def adult_birth_date() -> str:
    today = date.today()
    return date(today.year - 25, today.month, min(today.day, 28)).isoformat()


def register(client: TestClient, email: str) -> None:
    response = client.post(
        "/api/v1/auth/register",
        headers=ORIGIN,
        json={"email": email, "password": "long password"},
    )
    assert response.status_code == 201


def safety_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
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
    }
    payload.update(overrides)
    return payload


def nutrition_payload() -> dict[str, object]:
    return {
        "daily_activity_level": "moderate",
        "individual_monthly_food_budget_irr": 10_000_000,
        "budget_style": "strict",
        "meals_per_day": 3,
        "snacks_per_day": 1,
        "preferred_plan_start_day": "saturday",
        "plan_style": "balanced",
        "cooking_skill": "basic",
        "maximum_cooking_time_minutes": 45,
        "cooking_frequency_per_week": 4,
        "meal_preparation_preference": "mixed",
        "refrigerator_access": True,
        "freezer_access": True,
        "cooking_equipment": ["stove", "refrigerator"],
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
    }


def create_nutrition_member(
    client: TestClient,
    email: str,
    *,
    goal: str = "maintain_weight",
    safety: dict[str, object] | None = None,
) -> None:
    register(client, email)
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
                "display_name": "سارا",
                "birth_date": adult_birth_date(),
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
            json=safety or safety_payload(),
        ).status_code
        == 200
    )
    if safety is None:
        assert (
            client.put(
                "/api/v1/nutrition/profile", headers=ORIGIN, json=nutrition_payload()
            ).status_code
            == 200
        )


def test_nutrition_only_no_training_creates_an_idempotent_estimate(
    client: TestClient,
) -> None:
    create_nutrition_member(client, "estimate-no-training@example.com")
    exercise = client.put(
        "/api/v1/nutrition/structured-exercise",
        headers=ORIGIN,
        json={"trains": False},
    )

    first = client.post("/api/v1/nutrition/estimates", headers=ORIGIN)
    second = client.post("/api/v1/nutrition/estimates", headers=ORIGIN)

    assert exercise.status_code == 200
    assert exercise.json() == {
        "trains": False,
        "exercise_type": None,
        "days_per_week": None,
        "minutes_per_session": None,
        "intensity": None,
        "source": "user_reported",
    }
    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["id"] == second.json()["id"]
    assert first.json()["revision"] == 1
    assert first.json()["policy_version"] == "nutrition-science-v1"
    assert first.json()["formula_version"] == "mifflin-net-met-v1"
    assert first.json()["targets"]["exercise_energy"]["preferred"] == 0
    assert first.json()["targets"]["protein"]["minimum"] == 50
    assert first.json()["targets"]["protein"]["preferred"] == 62.5
    assert first.json()["targets"]["sodium"]["preferred"] == 1500
    assert first.json()["targets"]["sodium"]["maximum"] == 2300
    assert first.json()["micronutrients"]["potassium"]["reference_kind"] == "ai"
    assert first.json()["micronutrients"]["potassium"]["upper_limit_value"] is None

    current = client.get("/api/v1/nutrition/estimates/current")
    assert current.status_code == 200
    assert current.json()["id"] == first.json()["id"]
    assert current.json()["is_stale"] is False


def test_nutrition_only_training_requires_complete_details(client: TestClient) -> None:
    create_nutrition_member(client, "estimate-training-validation@example.com")

    incomplete = client.put(
        "/api/v1/nutrition/structured-exercise",
        headers=ORIGIN,
        json={"trains": True},
    )

    assert incomplete.status_code == 422


def test_combined_mode_reuses_training_profile_for_exercise(client: TestClient) -> None:
    register(client, "estimate-both@example.com")
    assert (
        client.post(
            "/api/v1/profile/mode", headers=ORIGIN, json={"product_mode": "both"}
        ).status_code
        == 201
    )
    profile = {
        "display_name": "محمد",
        "birth_date": adult_birth_date(),
        "sex": "male",
        "height_cm": 178,
        "current_weight_kg": 76.5,
        "fitness_goal": "build_muscle",
        "experience_level": "intermediate",
        "training_days_per_week": 4,
        "training_location": "gym",
        "home_training_setup": None,
        "training_cautions": [],
        "plan_duration_weeks": 6,
        "workout_generation_method": "fitsho_coach",
        "session_duration_minutes": 60,
        "training_intensity": "moderate",
        "physical_limitations": None,
    }
    assert client.post("/api/v1/profile", headers=ORIGIN, json=profile).status_code == 201
    assert (
        client.put("/api/v1/nutrition/safety", headers=ORIGIN, json=safety_payload()).status_code
        == 200
    )
    assert (
        client.put(
            "/api/v1/nutrition/profile", headers=ORIGIN, json=nutrition_payload()
        ).status_code
        == 200
    )

    resolved = client.get("/api/v1/nutrition/structured-exercise")
    estimate = client.post("/api/v1/nutrition/estimates", headers=ORIGIN)

    assert resolved.status_code == 200
    assert resolved.json() == {
        "trains": True,
        "exercise_type": "resistance",
        "days_per_week": 4,
        "minutes_per_session": 60,
        "intensity": "moderate",
        "source": "training_profile",
    }
    assert estimate.status_code == 201
    assert estimate.json()["targets"]["exercise_energy"]["preferred"] > 0
    assert estimate.json()["targets"]["protein"]["preferred"] > 100


def test_no_training_muscle_goal_returns_reselection_error(client: TestClient) -> None:
    create_nutrition_member(
        client,
        "estimate-invalid-goal@example.com",
        goal="build_muscle",
    )
    assert (
        client.put(
            "/api/v1/nutrition/structured-exercise",
            headers=ORIGIN,
            json={"trains": False},
        ).status_code
        == 200
    )

    response = client.post("/api/v1/nutrition/estimates", headers=ORIGIN)

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "GOAL_RESELECTION_REQUIRED"


def test_manual_medical_state_blocks_ordinary_estimate(client: TestClient) -> None:
    create_nutrition_member(
        client,
        "estimate-manual@example.com",
        safety=safety_payload(
            conditions=[{"code": "kidney_disease", "details": None}],
        ),
    )

    response = client.post("/api/v1/nutrition/estimates", headers=ORIGIN)

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "NUTRITION_ESTIMATE_BLOCKED"


def test_estimate_mutations_require_authentication_and_trusted_origin(
    client: TestClient,
) -> None:
    assert client.post("/api/v1/nutrition/estimates", headers=ORIGIN).status_code == 401
    create_nutrition_member(client, "estimate-origin@example.com")

    assert (
        client.put("/api/v1/nutrition/structured-exercise", json={"trains": False}).status_code
        == 403
    )
    assert client.post("/api/v1/nutrition/estimates").status_code == 403
