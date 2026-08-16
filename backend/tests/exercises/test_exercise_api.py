from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.exercises.enums import ExerciseContentType, ExerciseLabel
from app.exercises.models import Exercise, ExerciseLabelItem
from app.exercises.service import seed_exercises

ORIGIN = {"Origin": "http://localhost:5173"}
VALID_PROFILE = {
    "display_name": "Catalog User",
    "birth_date": "2000-05-14",
    "sex": "male",
    "height_cm": 178,
    "current_weight_kg": 76.5,
    "fitness_goal": "build_muscle",
    "experience_level": "beginner",
    "training_days_per_week": 3,
    "training_location": "gym",
    "home_training_setup": None,
    "session_duration_minutes": 60,
    "physical_limitations": None,
}


def register(client: TestClient, email: str) -> UUID:
    response = client.post(
        "/api/v1/auth/register",
        headers=ORIGIN,
        json={"email": email, "password": "long password"},
    )
    assert response.status_code == 201
    return UUID(response.json()["id"])


def complete_profile(client: TestClient) -> None:
    response = client.post("/api/v1/profile", headers=ORIGIN, json=VALID_PROFILE)
    assert response.status_code == 201


def prepare_catalog(
    client: TestClient,
    db: Session,
    email: str = "catalog@example.com",
) -> None:
    register(client, email)
    complete_profile(client)
    seed_exercises(db)


@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/exercise-categories",
        "/api/v1/exercises",
        "/api/v1/exercises/dumbbell-bench-press",
    ],
)
def test_catalog_routes_require_authentication(client: TestClient, path: str) -> None:
    response = client.get(path)

    assert response.status_code == 401
    assert response.json() == {"detail": "Authentication required"}


@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/exercise-categories",
        "/api/v1/exercises",
        "/api/v1/exercises/dumbbell-bench-press",
    ],
)
def test_catalog_routes_require_completed_profile(client: TestClient, path: str) -> None:
    register(client, f"incomplete-{path.count('/')}@example.com")

    response = client.get(path)

    assert response.status_code == 403
    assert response.json() == {"detail": "Completed fitness profile required"}


def test_categories_return_ordered_bilingual_taxonomy_even_when_core_is_empty(
    client: TestClient,
    db: Session,
) -> None:
    prepare_catalog(client, db)

    response = client.get("/api/v1/exercise-categories")

    assert response.status_code == 200
    assert list(response.json()) == [
        "body_regions",
        "upper_body",
        "lower_body",
        "core",
        "muscle_focuses",
    ]
    assert [
        (item["value"], item["name_en"], item["name_fa"])
        for item in response.json()["body_regions"]
    ] == [
        ("upper_body", "Upper Body", "بالاتنه"),
        ("lower_body", "Lower Body", "پایین‌تنه"),
        ("core", "Core", "میان‌تنه"),
    ]
    assert [
        (item["value"], item["name_en"], item["name_fa"]) for item in response.json()["upper_body"]
    ] == [
        ("chest", "Chest", "سینه"),
        ("back", "Back", "پشت و زیر بغل"),
        ("shoulders", "Shoulders", "سرشانه"),
        ("biceps", "Biceps", "جلو بازو"),
        ("triceps", "Triceps", "پشت بازو"),
        ("traps", "Traps", "کول"),
        ("forearms", "Forearms", "ساعد"),
        ("neck", "Neck", "گردن"),
    ]
    assert [
        (item["value"], item["name_en"], item["name_fa"]) for item in response.json()["lower_body"]
    ] == [
        ("glutes", "Glutes", "باسن"),
        ("quadriceps", "Quadriceps", "جلو پا"),
        ("hamstrings", "Hamstrings", "پشت پا"),
        ("adductors", "Adductors", "داخل پا"),
        ("abductors", "Abductors", "بیرون پا"),
        ("legs", "Legs", "کل پا"),
        ("calves", "Calves", "ساق"),
    ]
    assert [
        (item["value"], item["name_en"], item["name_fa"]) for item in response.json()["core"]
    ] == [
        ("abs", "Abs", "شکم"),
        ("obliques", "Obliques", "پهلو"),
        ("lower_back", "Lower Back", "فیله"),
    ]
    assert [
        (item["value"], item["name_en"], item["name_fa"])
        for item in response.json()["muscle_focuses"]["chest"]
    ] == [
        ("general_chest", "General Chest", "کل سینه"),
        ("upper_chest", "Upper Chest", "بالاسینه"),
        ("mid_chest", "Mid Chest", "میان‌سینه"),
        ("lower_chest", "Lower Chest", "زیرسینه"),
    ]
    assert response.json()["muscle_focuses"]["quadriceps"] == []
    assert response.json()["muscle_focuses"]["adductors"] == []
    assert set(response.json()["muscle_focuses"]) == {
        item["value"]
        for region in ("upper_body", "lower_body", "core")
        for item in response.json()[region]
    }


def test_list_returns_active_exercises_with_pagination_metadata(
    client: TestClient,
    db: Session,
) -> None:
    prepare_catalog(client, db)

    response = client.get("/api/v1/exercises")

    assert response.status_code == 200
    payload = response.json()
    assert payload["page"] == 1
    assert payload["page_size"] == 12
    assert payload["total"] == 17
    assert payload["total_pages"] == 2
    assert len(payload["items"]) == 12
    assert [item["name_en"] for item in payload["items"]] == sorted(
        item["name_en"] for item in payload["items"]
    )
    assert set(payload["items"][0]) == {
        "id",
        "slug",
        "name_en",
        "name_fa",
        "body_region",
        "primary_muscle",
        "muscle_focus",
        "secondary_muscles",
        "equipment",
            "difficulty",
            "labels",
        "media_path",
        "media_type",
        "content_type",
    }
    assert {item["content_type"] for item in payload["items"]} == {"exercise"}


def test_list_can_return_only_guides_for_a_selected_muscle(
    client: TestClient,
    db: Session,
) -> None:
    prepare_catalog(client, db)
    guide = db.scalar(select(Exercise).where(Exercise.slug == "dumbbell-bench-press"))
    assert guide is not None
    guide.content_type = ExerciseContentType.GUIDE
    db.commit()

    default_response = client.get(
        "/api/v1/exercises",
        params={"primary_muscle": "chest"},
    )
    guide_response = client.get(
        "/api/v1/exercises",
        params={"primary_muscle": "chest", "content_type": "guide"},
    )

    assert default_response.status_code == 200
    assert all(item["content_type"] == "exercise" for item in default_response.json()["items"])
    assert guide_response.status_code == 200
    assert [item["slug"] for item in guide_response.json()["items"]] == [
        "dumbbell-bench-press"
    ]
    assert guide_response.json()["items"][0]["content_type"] == "guide"


def test_list_filters_by_exercise_labels(client: TestClient, db: Session) -> None:
    prepare_catalog(client, db)
    exercise = db.scalar(select(Exercise).where(Exercise.slug == "dumbbell-bench-press"))
    assert exercise is not None
    exercise.labels.append(ExerciseLabelItem(label=ExerciseLabel.CARDIO))
    db.commit()

    response = client.get("/api/v1/exercises?labels=cardio")

    assert response.status_code == 200
    assert [item["slug"] for item in response.json()["items"]] == ["dumbbell-bench-press"]
    assert response.json()["items"][0]["labels"] == ["cardio"]


def test_detail_returns_complete_bilingual_exercise(
    client: TestClient,
    db: Session,
) -> None:
    prepare_catalog(client, db)
    exercise = db.scalar(select(Exercise).where(Exercise.slug == "dumbbell-bench-press"))
    assert exercise is not None
    exercise.source = "free-exercise-db"
    exercise.source_id = "0031"
    exercise.aliases_en = ["Dumbbell chest press"]
    exercise.short_description_en = "A dumbbell chest press."
    exercise.steps_en = ["Set up.", "Lower.", "Press."]
    exercise.form_cues_en = ["Brace the trunk."]
    exercise.common_mistakes_en = ["Flaring the elbows."]
    exercise.breathing_en = "Exhale while pressing."
    exercise.needs_review = True
    db.commit()

    response = client.get("/api/v1/exercises/dumbbell-bench-press")

    assert response.status_code == 200
    payload = response.json()
    assert payload["slug"] == "dumbbell-bench-press"
    assert payload["name_en"] == "Dumbbell Bench Press"
    assert payload["name_fa"] == "پرس سینه دمبل"
    assert payload["primary_muscle"] == "chest"
    assert payload["muscle_focus"] == "mid_chest"
    assert payload["secondary_muscles"] == ["shoulders", "triceps"]
    assert payload["equipment"] == ["bench", "dumbbell"]
    assert len(payload["instructions_en"]) == 3
    assert len(payload["instructions_fa"]) == 3
    assert payload["safety_notes_en"]
    assert payload["safety_notes_fa"]
    assert payload["media_type"] == "gif"
    assert payload["media_path"].endswith("/dumbbell-bench-press.gif")
    assert payload["media_source_url"] is None
    assert payload["media_license"] == "Project owner supplied and authorized"
    assert payload["media_attribution"] == "Provided by Fitsho project owner"
    assert payload["source"] == "free-exercise-db"
    assert payload["source_id"] == "0031"
    assert payload["aliases_en"] == ["Dumbbell chest press"]
    assert payload["short_description_en"] == "A dumbbell chest press."
    assert payload["steps_en"] == ["Set up.", "Lower.", "Press."]
    assert payload["form_cues_en"] == ["Brace the trunk."]
    assert payload["common_mistakes_en"] == ["Flaring the elbows."]
    assert payload["breathing_en"] == "Exhale while pressing."
    assert payload["needs_review"] is True


def test_inactive_exercises_are_hidden_from_list_and_detail(
    client: TestClient,
    db: Session,
) -> None:
    prepare_catalog(client, db)
    exercise = db.scalar(select(Exercise).where(Exercise.slug == "dumbbell-bench-press"))
    assert exercise is not None
    exercise.is_active = False
    db.commit()

    listing = client.get("/api/v1/exercises?page_size=50")
    detail = client.get("/api/v1/exercises/dumbbell-bench-press")

    assert listing.status_code == 200
    assert listing.json()["total"] == 16
    assert "dumbbell-bench-press" not in {item["slug"] for item in listing.json()["items"]}
    assert detail.status_code == 404
    assert detail.json() == {"detail": "Exercise not found"}


def test_unknown_slug_returns_not_found(client: TestClient, db: Session) -> None:
    prepare_catalog(client, db)

    response = client.get("/api/v1/exercises/not-an-exercise")

    assert response.status_code == 404
    assert response.json() == {"detail": "Exercise not found"}


@pytest.mark.parametrize(
    ("query", "expected_total", "expected_value"),
    [
        ("body_region=lower_body", 7, ("body_region", "lower_body")),
        ("primary_muscle=biceps", 4, ("primary_muscle", "biceps")),
        ("equipment=dumbbell", 8, ("equipment", "dumbbell")),
        ("difficulty=beginner", 11, ("difficulty", "beginner")),
    ],
)
def test_list_supports_controlled_filters(
    client: TestClient,
    db: Session,
    query: str,
    expected_total: int,
    expected_value: tuple[str, str],
) -> None:
    prepare_catalog(client, db, f"filter-{expected_value[0]}@example.com")

    response = client.get(f"/api/v1/exercises?{query}&page_size=50")

    assert response.status_code == 200
    assert response.json()["total"] == expected_total
    field, value = expected_value
    if field == "equipment":
        assert all(value in item[field] for item in response.json()["items"])
    else:
        assert all(item[field] == value for item in response.json()["items"])


def test_combined_filters_use_and_semantics(client: TestClient, db: Session) -> None:
    prepare_catalog(client, db)

    response = client.get(
        "/api/v1/exercises"
        "?body_region=upper_body&primary_muscle=biceps&equipment=dumbbell&page_size=50"
    )

    assert response.status_code == 200
    assert response.json()["total"] == 2
    assert {item["slug"] for item in response.json()["items"]} == {
        "dumbbell-curl",
        "hammer-curl",
    }


def test_list_filters_by_focus_inside_selected_muscle(
    client: TestClient,
    db: Session,
) -> None:
    prepare_catalog(client, db)

    response = client.get(
        "/api/v1/exercises",
        params={
            "primary_muscle": "biceps",
            "muscle_focus": "brachialis_brachioradialis",
            "page_size": 50,
        },
    )

    assert response.status_code == 200
    assert [item["slug"] for item in response.json()["items"]] == ["hammer-curl"]


@pytest.mark.parametrize(
    "params",
    [
        {"muscle_focus": "mid_chest"},
        {"primary_muscle": "shoulders", "muscle_focus": "mid_chest"},
    ],
)
def test_list_rejects_focus_without_compatible_muscle(
    client: TestClient,
    db: Session,
    params: dict[str, str],
) -> None:
    prepare_catalog(client, db)

    response = client.get("/api/v1/exercises", params=params)

    assert response.status_code == 422


@pytest.mark.parametrize(
    ("search", "expected_slug"),
    [
        ("hammer", "hammer-curl"),
        ("پرس پا", "leg-press"),
    ],
)
def test_search_matches_english_and_persian_names(
    client: TestClient,
    db: Session,
    search: str,
    expected_slug: str,
) -> None:
    prepare_catalog(client, db, f"search-{expected_slug}@example.com")

    response = client.get("/api/v1/exercises", params={"search": search})

    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert response.json()["items"][0]["slug"] == expected_slug


def test_search_treats_sql_wildcards_as_literal_text(
    client: TestClient,
    db: Session,
) -> None:
    prepare_catalog(client, db)

    response = client.get("/api/v1/exercises", params={"search": "%"})

    assert response.status_code == 200
    assert response.json()["total"] == 0


def test_pagination_returns_stable_pages_and_empty_out_of_range_page(
    client: TestClient,
    db: Session,
) -> None:
    prepare_catalog(client, db)

    first = client.get("/api/v1/exercises?page=1&page_size=5").json()
    second = client.get("/api/v1/exercises?page=2&page_size=5").json()
    beyond = client.get("/api/v1/exercises?page=99&page_size=5").json()

    assert first["total"] == second["total"] == beyond["total"] == 17
    assert first["total_pages"] == second["total_pages"] == beyond["total_pages"] == 4
    assert len(first["items"]) == len(second["items"]) == 5
    assert {item["id"] for item in first["items"]}.isdisjoint(
        item["id"] for item in second["items"]
    )
    assert beyond["items"] == []


@pytest.mark.parametrize(
    "query",
    [
        "body_region=arms",
        "equipment=kettlebell",
        "difficulty=expert",
        "page=0",
        "page_size=0",
        "page_size=51",
        "search=",
        f"search={'a' * 101}",
    ],
)
def test_invalid_filters_return_validation_error(
    client: TestClient,
    db: Session,
    query: str,
) -> None:
    prepare_catalog(client, db, f"invalid-{abs(hash(query))}@example.com")

    response = client.get(f"/api/v1/exercises?{query}")

    assert response.status_code == 422
