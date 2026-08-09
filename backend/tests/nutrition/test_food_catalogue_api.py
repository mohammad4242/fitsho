from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.models import User

ORIGIN = {"Origin": "http://localhost:5173"}


def _register(client: TestClient, email: str) -> None:
    response = client.post(
        "/api/v1/auth/register",
        headers=ORIGIN,
        json={"email": email, "password": "long password"},
    )
    assert response.status_code == 201


def test_authenticated_member_lists_verified_foods(client: TestClient) -> None:
    _register(client, "food-member@example.com")

    response = client.get("/api/v1/nutrition/foods")

    assert response.status_code == 200
    foods = response.json()
    assert {item["slug"] for item in foods} >= {"plain-yogurt", "chicken-breast", "lentils"}
    chicken = next(item for item in foods if item["slug"] == "chicken-breast")
    assert chicken["measurement_basis"] == "raw"
    assert set(chicken["aliases"]) >= {"سینه مرغ", "فیله مرغ"}


def test_admin_can_create_verified_food_with_provenance(client: TestClient, db: Session) -> None:
    _register(client, "food-admin@example.com")
    user = db.scalar(select(User).where(User.email == "food-admin@example.com"))
    assert user is not None
    user.is_admin = True
    db.commit()

    response = client.post(
        "/api/v1/nutrition/admin/foods",
        headers=ORIGIN,
        json={
            "slug": "admin-lentils",
            "name_fa": "عدس پخته",
            "name_en": "Cooked lentils",
            "verification_status": "verified",
            "source_name": "Verified regional composition",
            "source_reference": "https://example.test/lentils",
            "source_food_id": "regional-lentils",
            "category": "legumes",
            "measurement_basis": "dry",
            "aliases": ["عدس خشک"],
            "roles": ["main_protein", "flexible"],
            "nutrients": [
                {
                    "nutrient_code": "energy_kcal",
                    "value_per_100g": 116,
                    "unit": "kcal",
                    "unit_form": "nutrient_mass",
                    "source_name": "Verified regional composition",
                    "source_reference": "https://example.test/lentils",
                    "confidence": "high",
                },
                {
                    "nutrient_code": "protein_g",
                    "value_per_100g": 9,
                    "unit": "g",
                    "unit_form": "nutrient_mass",
                    "source_name": "Verified regional composition",
                    "source_reference": "https://example.test/lentils",
                    "confidence": "high",
                },
                {
                    "nutrient_code": "carbohydrate_g",
                    "value_per_100g": 20,
                    "unit": "g",
                    "unit_form": "nutrient_mass",
                    "source_name": "Verified regional composition",
                    "source_reference": "https://example.test/lentils",
                    "confidence": "high",
                },
                {
                    "nutrient_code": "total_fat_g",
                    "value_per_100g": 0.4,
                    "unit": "g",
                    "unit_form": "nutrient_mass",
                    "source_name": "Verified regional composition",
                    "source_reference": "https://example.test/lentils",
                    "confidence": "high",
                },
                {
                    "nutrient_code": "fibre_g",
                    "value_per_100g": 8,
                    "unit": "g",
                    "unit_form": "nutrient_mass",
                    "source_name": "Verified regional composition",
                    "source_reference": "https://example.test/lentils",
                    "confidence": "high",
                },
            ],
        },
    )

    assert response.status_code == 200
    assert response.json()["slug"] == "admin-lentils"

    retired = client.delete("/api/v1/nutrition/admin/foods/admin-lentils", headers=ORIGIN)

    assert retired.status_code == 204


def test_admin_cannot_publish_food_with_incomplete_primary_nutrients(
    client: TestClient, db: Session
) -> None:
    _register(client, "incomplete-food-admin@example.com")
    user = db.scalar(select(User).where(User.email == "incomplete-food-admin@example.com"))
    assert user is not None
    user.is_admin = True
    db.commit()

    response = client.post(
        "/api/v1/nutrition/admin/foods",
        headers=ORIGIN,
        json={
            "slug": "incomplete-food",
            "name_fa": "ماده ناقص",
            "name_en": "Incomplete food",
            "verification_status": "verified",
            "source_name": "Verified regional composition",
            "source_reference": "https://example.test/incomplete",
            "category": "test",
            "roles": ["flexible"],
            "nutrients": [
                {
                    "nutrient_code": "energy_kcal",
                    "value_per_100g": 100,
                    "unit": "kcal",
                    "source_name": "Verified regional composition",
                    "source_reference": "https://example.test/incomplete",
                    "confidence": "high",
                }
            ],
        },
    )

    assert response.status_code == 422
    assert "primary nutrients" in response.json()["detail"]
