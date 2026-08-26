from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.models import User
from app.exercises.service import seed_exercises
from app.training_templates.models import TrainingProgramStructure, TrainingProgramTemplate
from app.training_templates.service import seed_training_program_templates
from tests.training_templates.catalog_fixture import seed_real_catalog_exercises

ORIGIN = {"Origin": "http://localhost:5173"}


def _register_admin(client: TestClient, db: Session, email: str) -> None:
    response = client.post(
        "/api/v1/auth/register",
        headers=ORIGIN,
        json={"email": email, "password": "long password"},
    )
    assert response.status_code == 201, response.json()
    user = db.scalar(select(User).where(User.email == email))
    assert user is not None
    user.is_admin = True
    db.commit()


def _seed_library(db: Session) -> None:
    seed_exercises(db)
    seed_real_catalog_exercises(db)
    seed_training_program_templates(db)
    structure_slugs = {
        "t01-2-day-full-body-ab": "2d-full-body-ab",
        "t02-3-day-upper-lower-full": "3d-upper-lower-full-body",
        "t03-3-day-upper-lower-upper": "3d-upper-lower-upper",
        "t04-3-day-lower-upper-lower": "3d-lower-upper-lower",
        "t05-4-day-upper-lower-2x": "4d-upper-lower-2x",
        "t06-4-day-3-upper-1-lower": "4d-3-upper-1-lower",
        "t07-4-day-3-lower-1-upper": "4d-3-lower-1-upper",
        "t08-4-day-push-pull-quads-posterior": "4d-push-pull-quads-posterior",
        "t09-5-day-ppl-upper-lower": "5d-ppl-upper-lower",
        "t10-5-day-classic-body-part": "5d-classic-body-part",
        "t11-5-day-ppl-upper-lower-priority": "5d-ppl-upper-lower",
        "t12-5-day-chest-specialization": "5d-chest-spec-body-part",
        "t13-5-day-back-specialization": "5d-back-spec-body-part",
        "t14-5-day-leg-specialization": "5d-leg-spec-body-part",
        "t15-6-day-ppl-2x": "6d-ppl-2x",
        "t16-6-day-advanced-body-part": "6d-advanced-body-part",
        "t17-6-day-balanced-specialization": "6d-ppl-specialization",
    }
    structures = {
        structure.slug: structure for structure in db.scalars(select(TrainingProgramStructure))
    }
    for template in db.scalars(select(TrainingProgramTemplate)):
        template.structure_id = structures[structure_slugs[template.slug]].id
    db.commit()


def _structure_days(days_per_week: int) -> list[dict[str, object]]:
    return [
        {
            "day_number": day_number,
            "label_en": f"Day {day_number}",
            "label_fa": f"روز {day_number}",
            "day_type": "body_part",
        }
        for day_number in range(1, days_per_week + 1)
    ]


def _structure_payload(
    *,
    days_per_week: int = 5,
    family: str | None = "split",
    split_type: str | None = "body_part",
    slug: str = "five-day-body-part-b",
) -> dict[str, object]:
    return {
        "slug": slug,
        "name_en": "5-Day Body-Part Split B",
        "name_fa": "تقسیم عضله‌ای پنج‌روزه ب",
        "days_per_week": days_per_week,
        "family": family,
        "split_type": split_type,
        "description_en": "A body-part split created by an administrator.",
        "description_fa": "تقسیم عضله‌ای ساخته‌شده توسط ادمین.",
        "days": _structure_days(days_per_week),
    }


def test_structure_catalog_returns_family_and_split_type_classification(
    client: TestClient,
    db: Session,
) -> None:
    _register_admin(client, db, "structure-classification@example.com")

    response = client.get("/api/v1/admin/training-program-structures?days_per_week=5&family=split")

    assert response.status_code == 200, response.text
    structures = response.json()["items"]
    assert {item["family"] for item in structures} == {"split"}
    assert {item["split_type"] for item in structures} == {"ppl", "body_part"}
    assert any(item["split_type"] == "ppl" for item in structures)
    assert all(item["split_type"] != "ppl" for item in structures if "Body-Part" in item["name_en"])


def test_structure_family_filter_separates_four_day_upper_lower_and_split(
    client: TestClient,
    db: Session,
) -> None:
    _register_admin(client, db, "structure-family-filter@example.com")

    upper_lower = client.get(
        "/api/v1/admin/training-program-structures?days_per_week=4&family=upper_lower"
    )
    split = client.get("/api/v1/admin/training-program-structures?days_per_week=4&family=split")

    assert upper_lower.status_code == 200
    assert split.status_code == 200
    assert {item["slug"] for item in upper_lower.json()["items"]} == {
        "4d-upper-lower-2x",
        "4d-3-upper-1-lower",
        "4d-3-lower-1-upper",
    }
    assert [item["slug"] for item in split.json()["items"]] == ["4d-push-pull-quads-posterior"]


def test_template_family_filter_preserves_level_filter(
    client: TestClient,
    db: Session,
) -> None:
    _seed_library(db)
    _register_admin(client, db, "template-family-filter@example.com")

    response = client.get(
        "/api/v1/admin/training-program-templates"
        "?days_per_week=5&family=split&training_level=advanced"
    )

    assert response.status_code == 200, response.text
    templates = response.json()["items"]
    assert {template["slug"] for template in templates} == {
        "t09-5-day-ppl-upper-lower",
        "t10-5-day-classic-body-part",
        "t11-5-day-ppl-upper-lower-priority",
        "t12-5-day-chest-specialization",
        "t13-5-day-back-specialization",
        "t14-5-day-leg-specialization",
    }
    assert all("advanced" in template["supported_levels"] for template in templates)


@pytest.mark.parametrize(
    ("days_per_week", "family", "split_type", "slug"),
    [
        (5, "split", "body_part", "five-day-body-part-b"),
        (6, "upper_lower", None, "six-day-upper-lower-b"),
    ],
)
def test_admin_creates_structure_and_exposes_it_under_days_and_family(
    client: TestClient,
    db: Session,
    days_per_week: int,
    family: str,
    split_type: str | None,
    slug: str,
) -> None:
    _register_admin(client, db, f"structure-create-{days_per_week}@example.com")

    created = client.post(
        "/api/v1/admin/training-program-structures",
        headers=ORIGIN,
        json=_structure_payload(
            days_per_week=days_per_week,
            family=family,
            split_type=split_type,
            slug=slug,
        ),
    )

    assert created.status_code == 201, created.text
    item = created.json()
    assert item["days_per_week"] == days_per_week
    assert item["family"] == family
    assert item["split_type"] == split_type
    assert len(item["structure_days"]) == days_per_week

    filtered = client.get(
        f"/api/v1/admin/training-program-structures?days_per_week={days_per_week}&family={family}"
    )
    assert filtered.status_code == 200
    assert slug in {entry["slug"] for entry in filtered.json()["items"]}


@pytest.mark.parametrize(
    ("days_per_week", "family", "split_type"),
    [
        (2, "split", "ppl"),
        (5, None, None),
        (5, "upper_lower", "ppl"),
        (5, "split", None),
    ],
)
def test_structure_write_rejects_invalid_family_combinations(
    client: TestClient,
    db: Session,
    days_per_week: int,
    family: str | None,
    split_type: str | None,
) -> None:
    email = (
        f"structure-invalid-{days_per_week}-{family or 'none'}-{split_type or 'none'}@example.com"
    ).lower()
    _register_admin(client, db, email)

    response = client.post(
        "/api/v1/admin/training-program-structures",
        headers=ORIGIN,
        json=_structure_payload(
            days_per_week=days_per_week,
            family=family,
            split_type=split_type,
        ),
    )

    assert response.status_code == 422, response.text


def test_admin_cannot_change_days_for_referenced_structure(
    client: TestClient,
    db: Session,
) -> None:
    _seed_library(db)
    _register_admin(client, db, "structure-safe-update@example.com")
    structure = client.get(
        "/api/v1/admin/training-program-structures?days_per_week=4&family=upper_lower"
    ).json()["items"][0]

    payload = {
        "slug": structure["slug"],
        "name_en": structure["name_en"],
        "name_fa": structure["name_fa"],
        "days_per_week": 5,
        "family": "split",
        "split_type": "body_part",
        "description_en": structure["description_en"],
        "description_fa": structure["description_fa"],
        "days": _structure_days(5),
    }

    response = client.put(
        f"/api/v1/admin/training-program-structures/{structure['id']}",
        headers=ORIGIN,
        json=payload,
    )

    assert response.status_code == 422, response.text
