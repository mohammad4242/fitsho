import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth.models import User
from app.exercises.enums import Equipment
from app.exercises.models import Exercise, ExerciseEquipment
from app.exercises.service import seed_exercises
from app.training_templates.engine_reference import load_template_references
from app.training_templates.models import TrainingProgramTemplate, TrainingProgramTemplateDay
from app.training_templates.service import seed_training_program_templates
from tests.training_templates.catalog_fixture import seed_real_catalog_exercises

ORIGIN = {"Origin": "http://localhost:5173"}


def _register(client: TestClient, email: str) -> None:
    response = client.post(
        "/api/v1/auth/register",
        headers=ORIGIN,
        json={"email": email, "password": "long password"},
    )
    assert response.status_code == 201, response.json()


def _seed_library(db: Session) -> None:
    seed_exercises(db)
    seed_real_catalog_exercises(db)
    seed_training_program_templates(db)


def _make_current_user_admin(client: TestClient, db: Session) -> None:
    _register(client, "admin-templates@example.com")
    user = db.scalar(select(User).where(User.email == "admin-templates@example.com"))
    assert user is not None
    user.is_admin = True
    db.commit()


def test_training_template_library_requires_admin_access(client: TestClient, db: Session) -> None:
    _seed_library(db)

    anonymous = client.get("/api/v1/admin/training-program-templates")
    assert anonymous.status_code == 401

    _register(client, "member-templates@example.com")
    member = client.get("/api/v1/admin/training-program-templates")
    assert member.status_code == 403


def test_admin_lists_complete_four_day_template_details(client: TestClient, db: Session) -> None:
    _seed_library(db)
    _make_current_user_admin(client, db)

    response = client.get("/api/v1/admin/training-program-templates?days_per_week=4")

    assert response.status_code == 200, response.text
    templates = response.json()["items"]
    assert len(templates) == 4
    classic = next(item for item in templates if item["slug"] == "t05-4-day-upper-lower-2x")
    assert classic["supported_levels"] == [
        "first_month",
        "beginner",
        "intermediate",
        "advanced",
    ]
    assert "upper_lower" in classic["focus_tags"]
    assert len(classic["programming_rationale"]) == 5
    assert classic["programming_rationale"][0]["title_fa"] == "ساختار"
    assert [day["title_fa"] for day in classic["days"]] == [
        "بالاتنه A",
        "پایین‌تنه A",
        "بالاتنه B",
        "پایین‌تنه B",
    ]
    first_slot = classic["days"][0]["slots"][0]
    assert first_slot["exercise"]["slug"] == "fedb-0577-lever-lying-chest-press"
    assert all(
        slot["exercise"] is not None
        and slot["placeholder_name_en"] is None
        and slot["placeholder_name_fa"] is None
        for day in classic["days"]
        for slot in day["slots"]
    )


def test_training_template_library_has_no_public_endpoint(client: TestClient) -> None:
    response = client.get("/api/v1/training-program-templates")

    assert response.status_code == 404


def test_admin_level_filters_return_the_same_canonical_template_id(
    client: TestClient,
    db: Session,
) -> None:
    _seed_library(db)
    _make_current_user_admin(client, db)

    beginner = client.get(
        "/api/v1/admin/training-program-templates?days_per_week=2&training_level=beginner"
    )
    intermediate = client.get(
        "/api/v1/admin/training-program-templates?days_per_week=2&training_level=intermediate"
    )

    assert beginner.status_code == 200
    assert intermediate.status_code == 200
    beginner_t01 = next(
        item for item in beginner.json()["items"] if item["slug"].startswith("t01-")
    )
    intermediate_t01 = next(
        item for item in intermediate.json()["items"] if item["slug"].startswith("t01-")
    )
    assert beginner_t01["id"] == intermediate_t01["id"]


def test_admin_creates_a_complete_multi_level_template_with_shared_content(
    client: TestClient,
    db: Session,
) -> None:
    _seed_library(db)
    _make_current_user_admin(client, db)
    payload = _template_payload_for_catalog(db)

    response = client.post(
        "/api/v1/admin/training-program-templates",
        headers=ORIGIN,
        json={
            **payload,
            "name_en": "Admin Shared Program",
            "name_fa": "برنامه مشترک ادمین",
            "supported_levels": ["first_month", "intermediate"],
        },
    )

    assert response.status_code == 201
    created = response.json()
    assert created["slug"] == "admin-shared-program"
    assert created["supported_levels"] == ["first_month", "intermediate"]
    assert len(created["days"]) == 2
    assert len(created["days"][0]["slots"]) == 5
    assert created["days"][0]["slots"][0]["exercise"]["slug"] == "fedb-0025-barbell-bench-press"
    created_references = [
        reference for reference in load_template_references(db) if reference.slug == created["slug"]
    ]
    assert len(created_references) == 1
    assert set(created_references[0].supported_levels) == {
        "first_month",
        "intermediate",
    }


def test_admin_rejects_empty_or_duplicate_supported_levels(
    client: TestClient,
    db: Session,
) -> None:
    _seed_library(db)
    _make_current_user_admin(client, db)
    exercise_id = client.get("/api/v1/admin/exercises?search=bench").json()["items"][0]["id"]
    base_payload = {
        "name_en": "Invalid Supported Levels",
        "name_fa": "سطوح پشتیبانی نامعتبر",
        "description_en": "Supported levels must be non-empty and unique.",
        "description_fa": "سطوح پشتیبانی باید غیرخالی و یکتا باشند.",
        "days_per_week": 2,
        "fitness_goal": "build_muscle",
        "focus_tags": ["full_body", "balanced"],
        "intensity_methods": ["standard"],
        "programming_rationale": _rationale_payload(),
        "source_name": "Fitsho admin library",
        "source_url": "https://fitsho.local/admin-library",
        "days": [_day_payload(day, exercise_id) for day in range(1, 3)],
    }

    for supported_levels in ([], ["beginner", "beginner"]):
        response = client.post(
            "/api/v1/admin/training-program-templates",
            headers=ORIGIN,
            json={**base_payload, "supported_levels": supported_levels},
        )

        assert response.status_code == 422
        assert response.json()["detail"][0]["loc"] == ["body", "supported_levels"]


def test_admin_update_replaces_removed_slots_and_keeps_catalog_exercise_link(
    client: TestClient,
    db: Session,
) -> None:
    _seed_library(db)
    _make_current_user_admin(client, db)
    template_response = client.get("/api/v1/admin/training-program-templates?days_per_week=4")
    template = template_response.json()["items"][0]
    print("SLUG IS:", template["slug"])
    detail_response = client.get(f"/api/v1/admin/training-program-templates/{template['id']}")
    assert detail_response.status_code == 200
    assert detail_response.json()["id"] == template["id"]
    first_slot = template["days"][0]["slots"][0]
    payload = {
        "name_en": template["name_en"],
        "name_fa": template["name_fa"],
        "description_en": template["description_en"],
        "description_fa": template["description_fa"],
        "days_per_week": template["days_per_week"],
        "supported_levels": ["beginner", "advanced"],
        "fitness_goal": template["fitness_goal"],
        "focus_tags": template["focus_tags"],
        "intensity_methods": template["intensity_methods"],
        "programming_rationale": template["programming_rationale"],
        "source_name": template["source_name"],
        "source_url": template["source_url"],
        "days": [
            {
                "title_en": day["title_en"],
                "title_fa": day["title_fa"],
                "structure_focus": day["structure_focus"],
                "direct_target_muscles": day["direct_target_muscles"],
                "slots": [
                    _slot_payload(slot, display_name_fa="پرس سینه انتخابی" if index == 0 else None)
                    for index, slot in enumerate(day["slots"][:5])
                ]
                if day["day_number"] == 1
                else [_slot_payload(slot) for slot in day["slots"][:5]],
            }
            for day in template["days"]
        ],
    }

    print("SLOTS LENGTHS:", [len(day["slots"]) for day in payload["days"]])
    print("SLOTS LENGTHS:", [len(day["slots"]) for day in payload["days"]])
    response = client.put(
        f"/api/v1/admin/training-program-templates/{template['id']}",
        headers=ORIGIN,
        json=payload,
    )

    assert response.status_code == 200, response.text
    first_day = response.json()["days"][0]
    assert len(first_day["slots"]) == len(payload["days"][0]["slots"])
    assert first_day["slots"][0]["placeholder_name_fa"] == "پرس سینه انتخابی"
    assert first_day["slots"][0]["exercise"]["id"] == first_slot["exercise"]["id"]
    assert response.json()["supported_levels"] == ["beginner", "advanced"]


def test_admin_deletes_template_and_owned_days(client: TestClient, db: Session) -> None:
    _seed_library(db)
    _make_current_user_admin(client, db)
    template = client.get("/api/v1/admin/training-program-templates?days_per_week=2").json()[
        "items"
    ][0]
    template_id = template["id"]

    response = client.delete(
        f"/api/v1/admin/training-program-templates/{template_id}",
        headers=ORIGIN,
    )

    assert response.status_code == 204
    assert db.get(TrainingProgramTemplate, template_id) is None
    assert (
        db.scalar(
            select(func.count())
            .select_from(TrainingProgramTemplateDay)
            .where(TrainingProgramTemplateDay.template_id == template_id)
        )
        == 0
    )


def test_admin_rejects_template_slot_with_unknown_exercise(client: TestClient, db: Session) -> None:
    _seed_library(db)
    _make_current_user_admin(client, db)
    payload = {
        "name_en": "Invalid Exercise Program",
        "name_fa": "برنامه حرکت نامعتبر",
        "description_en": "Invalid exercise test.",
        "description_fa": "آزمون حرکت نامعتبر.",
        "days_per_week": 2,
        "supported_levels": ["beginner"],
        "fitness_goal": "build_muscle",
        "focus_tags": ["full_body", "balanced"],
        "intensity_methods": ["standard"],
        "programming_rationale": _rationale_payload(),
        "source_name": "Fitsho admin library",
        "source_url": "https://fitsho.local/admin-library",
        "days": [_day_payload(day, "00000000-0000-0000-0000-000000000000") for day in range(1, 3)],
    }

    response = client.post(
        "/api/v1/admin/training-program-templates",
        headers=ORIGIN,
        json=payload,
    )

    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["body", "days"]


@pytest.mark.parametrize("mutation", ["inactive", "non_programmable", "placeholder"])
def test_admin_rejects_non_executable_template_exercises(
    client: TestClient,
    db: Session,
    mutation: str,
) -> None:
    _seed_library(db)
    _make_current_user_admin(client, db)
    exercise = db.scalar(select(Exercise).where(Exercise.slug == "fedb-0025-barbell-bench-press"))
    assert exercise is not None
    if mutation == "inactive":
        exercise.is_active = False
    elif mutation == "non_programmable":
        exercise.is_programmable = False
    else:
        exercise.source = "fitsho_training_template"
        exercise.source_id = f"test-placeholder-{exercise.id}"
        exercise.is_programmable = False
    db.commit()

    response = client.post(
        "/api/v1/admin/training-program-templates",
        headers=ORIGIN,
        json=_template_payload_for_catalog(db, str(exercise.id)),
    )

    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["body", "days"]


def test_admin_rejects_semantically_incompatible_template_exercise(
    client: TestClient,
    db: Session,
) -> None:
    _seed_library(db)
    _make_current_user_admin(client, db)
    incompatible = db.scalar(
        select(Exercise.id).where(Exercise.slug == "owner-e0c26a271aac-barbell-bent-over-row")
    )
    assert incompatible is not None
    payload = _template_payload_for_catalog(db, str(incompatible))

    response = client.post(
        "/api/v1/admin/training-program-templates",
        headers=ORIGIN,
        json=payload,
    )

    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["body", "days"]


def test_admin_accepts_compatible_template_exercises(client: TestClient, db: Session) -> None:
    _seed_library(db)
    _make_current_user_admin(client, db)

    response = client.post(
        "/api/v1/admin/training-program-templates",
        headers=ORIGIN,
        json=_template_payload_for_catalog(db),
    )

    assert response.status_code == 201


def test_admin_rejects_drop_set_on_compound_exercise(client: TestClient, db: Session) -> None:
    _seed_library(db)
    _make_current_user_admin(client, db)
    payload = _template_payload_for_catalog(db)
    payload["supported_levels"] = ["advanced"]
    payload["intensity_methods"] = ["standard", "drop_set"]
    payload["days"][0]["slots"][0]["intensity_method"] = "drop_set"

    response = client.post(
        "/api/v1/admin/training-program-templates",
        headers=ORIGIN,
        json=payload,
    )

    assert response.status_code == 422
    assert "Drop-set slots require" in response.json()["detail"][0]["msg"]


def test_admin_rejects_identical_superset_pair(client: TestClient, db: Session) -> None:
    _seed_library(db)
    _make_current_user_admin(client, db)
    payload = _template_payload_for_catalog(db)
    payload["supported_levels"] = ["advanced"]
    payload["intensity_methods"] = ["standard", "superset"]
    slot = payload["days"][0]["slots"][0]
    slot["intensity_method"] = "superset"
    # Try to superset the exact same exercise twice!
    slot["superset_exercise_id"] = slot["exercise_id"]
    del payload["days"][0]["slots"][1]

    response = client.post(
        "/api/v1/admin/training-program-templates",
        headers=ORIGIN,
        json=payload,
    )

    assert response.status_code == 422
    assert "Superset exercises must be different" in response.json()["detail"][0]["msg"]


def test_admin_accepts_safe_advanced_methods(client: TestClient, db: Session) -> None:
    _seed_library(db)
    _make_current_user_admin(client, db)
    payload = _template_payload_for_catalog(db)
    payload["supported_levels"] = ["advanced"]
    payload["intensity_methods"] = ["standard", "superset", "drop_set"]
    curl_id = db.scalar(
        select(Exercise.id).where(Exercise.slug == "fedb-0229-cable-standing-inner-curl")
    )
    pushdown_id = db.scalar(
        select(Exercise.id).where(Exercise.slug == "fedb-1723-cable-triceps-pushdown")
    )
    lateral_raise_id = db.scalar(
        select(Exercise.id).where(Exercise.slug == "fedb-0178-cable-lateral-raise")
    )
    assert curl_id is not None and pushdown_id is not None and lateral_raise_id is not None
    for exercise_id in (curl_id, pushdown_id, lateral_raise_id):
        db.add(ExerciseEquipment(exercise_id=exercise_id, equipment=Equipment.CABLE))
    db.flush()
    first, second, third = payload["days"][0]["slots"][:3]
    first.update(
        exercise_id=str(curl_id),
        target_muscles=["biceps"],
        movement_pattern="elbow_flexion",
        intensity_method="superset",
        adaptation_priority="accessory",
        superset_exercise_id=str(pushdown_id),
        
        
        
    )
    payload["days"][0]["slots"].pop(1)  # Remove second slot, since it's merged into first
    
    third.update(
        exercise_id=str(lateral_raise_id),
        target_muscles=["shoulders"],
        movement_pattern="shoulder_abduction",
        intensity_method="drop_set",
        adaptation_priority="accessory",
    )

    response = client.post(
        "/api/v1/admin/training-program-templates",
        headers=ORIGIN,
        json=payload,
    )

    assert response.status_code == 201, response.json()


def test_admin_rejects_conflicting_canonical_template_tags(
    client: TestClient,
    db: Session,
) -> None:
    _seed_library(db)
    _make_current_user_admin(client, db)
    exercise_id = client.get("/api/v1/admin/exercises?search=bench").json()["items"][0]["id"]

    response = client.post(
        "/api/v1/admin/training-program-templates",
        headers=ORIGIN,
        json={
            "name_en": "Conflicting Tag Program",
            "name_fa": "برنامه با برچسب متناقض",
            "description_en": "Conflicting canonical tag test.",
            "description_fa": "آزمون برچسب‌های متناقض.",
            "days_per_week": 2,
            "supported_levels": ["beginner"],
            "fitness_goal": "build_muscle",
            "focus_tags": ["full_body", "balanced", "chest_priority"],
            "intensity_methods": ["standard"],
            "programming_rationale": _rationale_payload(),
            "source_name": "Fitsho admin library",
            "source_url": "https://fitsho.local/admin-library",
            "days": [_day_payload(day, exercise_id) for day in range(1, 3)],
        },
    )

    assert response.status_code == 422
    assert "Balanced templates cannot declare priority tags" in response.text


def test_admin_rejects_guide_from_training_template_slots(client: TestClient, db: Session) -> None:
    _seed_library(db)
    _make_current_user_admin(client, db)
    guide = db.scalar(select(Exercise).where(Exercise.slug == "dumbbell-bench-press"))
    assert guide is not None
    guide.content_type = "guide"
    db.commit()

    response = client.post(
        "/api/v1/admin/training-program-templates",
        headers=ORIGIN,
        json={
            "name_en": "Guide Slot Program",
            "name_fa": "برنامه راهنما",
            "description_en": "Guide slot must be rejected.",
            "description_fa": "جایگاه راهنما باید رد شود.",
            "days_per_week": 2,
            "supported_levels": ["beginner"],
            "fitness_goal": "build_muscle",
            "focus_tags": ["full_body", "balanced"],
            "intensity_methods": ["standard"],
            "programming_rationale": _rationale_payload(),
            "source_name": "Fitsho admin library",
            "source_url": "https://fitsho.local/admin-library",
            "days": [_day_payload(day, str(guide.id)) for day in range(1, 3)],
        },
    )

    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["body", "days"]


def _rationale_payload() -> list[dict[str, str]]:
    return [
        {
            "title_en": f"Reason {number}",
            "title_fa": f"علت {number}",
            "detail_en": f"Program rationale {number}.",
            "detail_fa": f"منطق برنامه {number}.",
        }
        for number in range(1, 6)
    ]


def _template_payload_for_catalog(
    db: Session,
    first_exercise_id: str | None = None,
) -> dict[str, object]:
    slugs = (
        "fedb-0025-barbell-bench-press",
        "owner-e0c26a271aac-barbell-bent-over-row",
        "fedb-0765-smith-seated-shoulder-press",
        "fedb-0750-smith-chair-squat",
        "fedb-0300-dumbbell-deadlift",
    )
    exercise_ids = [
        str(db.scalar(select(Exercise.id).where(Exercise.slug == slug))) for slug in slugs
    ]
    assert all(exercise_id != "None" for exercise_id in exercise_ids)
    if first_exercise_id is not None:
        exercise_ids[0] = first_exercise_id
    days = []
    for day_number in range(1, 3):
        day = _day_payload(day_number, exercise_ids[0])
        for slot, exercise_id in zip(day["slots"], exercise_ids, strict=True):
            slot["exercise_id"] = exercise_id
        days.append(day)
    return {
        "name_en": "Focused Template Validation",
        "name_fa": "اعتبارسنجی متمرکز قالب",
        "description_en": "A focused template validation fixture.",
        "description_fa": "تست متمرکز اعتبارسنجی قالب.",
        "days_per_week": 2,
        "supported_levels": ["beginner"],
        "fitness_goal": "build_muscle",
        "focus_tags": ["full_body", "balanced"],
        "intensity_methods": ["standard"],
        "programming_rationale": _rationale_payload(),
        "source_name": "Fitsho admin library",
        "source_url": "https://fitsho.local/admin-library",
        "days": days,
    }


def _day_payload(day_number: int, exercise_id: str) -> dict[str, object]:
    slot_specs = (
        (["chest"], "horizontal_push"),
        (["back"], "horizontal_pull"),
        (["shoulders"], "vertical_push"),
        (["quadriceps"], "squat"),
        (["hamstrings", "glutes"], "hip_hinge"),
    )
    return {
        "title_en": f"Day {day_number}",
        "title_fa": f"روز {day_number}",
        "structure_focus": "full_body",
        "direct_target_muscles": [
            "chest",
            "back",
            "shoulders",
            "quadriceps",
            "hamstrings",
            "glutes",
        ],
        "slots": [
            {
                "exercise_id": exercise_id,
                "display_name_en": None,
                "display_name_fa": None,
                "target_muscles": target_muscles,
                "movement_pattern": movement_pattern,
                "intensity_method": "standard",
                "adaptation_priority": "core",
                "superset_group": None,
                "sets": 3,
                "rep_min": 8,
                "rep_max": 12,
                "target_rir": 2,
                "rest_seconds": 90,
            }
            for target_muscles, movement_pattern in slot_specs
        ],
    }


def _slot_payload(slot: dict[str, object], **overrides: object) -> dict[str, object]:
    return {
        "exercise_id": slot["exercise"]["id"],
        "display_name_en": slot["placeholder_name_en"],
        "display_name_fa": slot["placeholder_name_fa"],
        "target_muscles": slot["target_muscles"],
        "movement_pattern": slot["movement_pattern"],
        "intensity_method": slot["intensity_method"],
        "adaptation_priority": "core",
        "superset_group": slot.get("superset_group"),
        "superset_exercise_id": slot.get("superset_exercise", {}).get("id") if slot.get("superset_exercise") else None,
        "sets": slot["sets"],
        "rep_min": slot["rep_min"],
        "rep_max": slot["rep_max"],
        "target_rir": slot["target_rir"],
        "rest_seconds": slot["rest_seconds"],
        **overrides,
    }
