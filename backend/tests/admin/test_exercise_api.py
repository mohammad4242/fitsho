import json
from typing import cast
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from httpx import Response
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.admin.schemas import AdminExerciseMediaAssetInput
from app.auth.models import User
from app.config import Settings
from app.exercises.models import Exercise, ExerciseMediaAsset
from app.exercises.service import seed_exercises
from app.workouts.enums import WorkoutPlanStatus
from app.workouts.models import WorkoutDay, WorkoutPlan, WorkoutPlanExercise

ORIGIN = {"Origin": "http://localhost:5173"}
GIF_BYTES = b"GIF89a" + b"\x00" * 32
MP4_BYTES = b"\x00\x00\x00\x18ftypisom" + b"\x00" * 32
VALID_PROFILE = {
    "display_name": "Admin User",
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


def exercise_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "slug": "incline-push-up",
        "name_en": "Incline Push Up",
        "name_fa": "شنا سوئدی شیب‌دار",
        "body_region": "upper_body",
        "primary_muscle": "chest",
        "muscle_focus": "mid_chest",
        "secondary_muscles": ["shoulders", "triceps"],
        "equipment": ["bodyweight", "bench"],
        "difficulty": "beginner",
        "instructions_en": ["Brace your core", "Lower your chest", "Press away"],
        "instructions_fa": ["میان‌تنه را منقبض کنید", "سینه را پایین ببرید", "بدن را بالا ببرید"],
        "safety_notes_en": ["Keep the body in a straight line"],
        "safety_notes_fa": ["بدن را در یک خط مستقیم نگه دارید"],
        "is_active": True,
        "media_source_url": None,
        "media_license": None,
        "media_attribution": None,
    }
    payload.update(overrides)
    return payload


def register(client: TestClient, email: str = "admin@example.com") -> None:
    response = client.post(
        "/api/v1/auth/register",
        headers=ORIGIN,
        json={"email": email, "password": "long password"},
    )
    assert response.status_code == 201


def make_current_user_admin(client: TestClient, db: Session) -> User:
    register(client)
    user = db.scalar(select(User).where(User.email == "admin@example.com"))
    assert user is not None
    user.is_admin = True
    db.commit()
    return user


def post_exercise(
    client: TestClient,
    payload: dict[str, object],
    *,
    headers: dict[str, str] | None = None,
    media: tuple[str, bytes, str] | None = None,
    media_assets: dict[str, tuple[str, bytes, str]] | None = None,
) -> Response:
    files: dict[str, tuple[str, bytes, str]] = {}
    if media is not None:
        files["media"] = media
    files.update(media_assets or {})
    return cast(
        Response,
        client.post(
            "/api/v1/admin/exercises",
            headers=ORIGIN if headers is None else headers,
            data={"payload": json.dumps(payload)},
            files=files or None,
        ),
    )


def test_admin_media_asset_input_rejects_thumbnail_role() -> None:
    with pytest.raises(ValidationError):
        AdminExerciseMediaAssetInput.model_validate(
            {
                "presentation": "male",
                "role": "thumbnail",
                "sort_order": 0,
            }
        )


@pytest.mark.parametrize("method", ["get", "post", "delete"])
def test_admin_exercise_routes_require_authentication(
    client: TestClient,
    method: str,
) -> None:
    if method == "get":
        response = client.get("/api/v1/admin/exercises")
    elif method == "post":
        response = post_exercise(client, exercise_payload())
    else:
        response = client.delete(f"/api/v1/admin/exercises/{uuid4()}")

    assert response.status_code == 401
    assert response.json() == {"detail": "Authentication required"}


@pytest.mark.parametrize("method", ["get", "post", "delete"])
def test_admin_exercise_routes_reject_non_admin(
    client: TestClient,
    method: str,
) -> None:
    register(client, "member@example.com")

    if method == "get":
        response = client.get("/api/v1/admin/exercises")
    elif method == "post":
        response = post_exercise(client, exercise_payload())
    else:
        response = client.delete(f"/api/v1/admin/exercises/{uuid4()}")

    assert response.status_code == 403
    assert response.json() == {"detail": "Administrator access required"}


def test_admin_access_does_not_require_completed_profile(
    client: TestClient,
    db: Session,
) -> None:
    make_current_user_admin(client, db)

    response = client.get("/api/v1/admin/exercises")

    assert response.status_code == 200


def test_admin_can_delete_an_exercise(client: TestClient, db: Session) -> None:
    make_current_user_admin(client, db)
    created = post_exercise(client, exercise_payload())
    assert created.status_code == 201
    exercise_id = created.json()["id"]

    response = client.delete(f"/api/v1/admin/exercises/{exercise_id}", headers=ORIGIN)

    assert response.status_code == 204
    assert db.get(Exercise, exercise_id) is None


def test_admin_delete_returns_not_found_for_missing_exercise(
    client: TestClient, db: Session
) -> None:
    make_current_user_admin(client, db)

    response = client.delete(f"/api/v1/admin/exercises/{uuid4()}", headers=ORIGIN)

    assert response.status_code == 404


@pytest.mark.parametrize("headers", [{}, {"Origin": "https://evil.example"}])
def test_delete_requires_trusted_origin(
    client: TestClient,
    db: Session,
    headers: dict[str, str],
) -> None:
    make_current_user_admin(client, db)

    response = client.delete(f"/api/v1/admin/exercises/{uuid4()}", headers=headers)

    assert response.status_code == 403
    assert response.json() == {"detail": "Untrusted request origin"}


def test_admin_deletes_an_exercise_used_in_a_workout_plan(client: TestClient, db: Session) -> None:
    admin = make_current_user_admin(client, db)
    created = post_exercise(client, exercise_payload())
    assert created.status_code == 201
    exercise = db.get(Exercise, created.json()["id"])
    assert exercise is not None
    plan = WorkoutPlan(
        user_id=admin.id,
        status=WorkoutPlanStatus.ACTIVE,
        generation_signature="a" * 64,
        profile_snapshot={},
        provider="fake",
        model_id="fake-model",
        prompt_version="v1",
        generation_policy_version="v1",
        candidate_set_hash="b" * 64,
        generation_method="ai",
    )
    day = WorkoutDay(
        workout_plan=plan,
        day_number=1,
        title_en="Upper body",
        title_fa="بالاتنه",
        estimated_duration_minutes=30,
    )
    db.add(
        WorkoutPlanExercise(
            workout_day=day,
            exercise=exercise,
            order_index=1,
            sets=3,
            reps_min=8,
            reps_max=12,
            rest_seconds=90,
            rir=2,
            estimated_minutes=8,
        )
    )
    db.commit()

    response = client.delete(f"/api/v1/admin/exercises/{exercise.id}", headers=ORIGIN)

    assert response.status_code == 204
    assert db.get(Exercise, exercise.id) is None
    assert db.get(WorkoutPlan, plan.id) is not None
    assert (
        db.scalar(select(WorkoutPlanExercise).where(WorkoutPlanExercise.exercise_id == exercise.id))
        is None
    )


def test_admin_list_includes_inactive_exercises(
    client: TestClient,
    db: Session,
) -> None:
    make_current_user_admin(client, db)
    seed_exercises(db)
    exercise = db.scalar(select(Exercise).where(Exercise.slug == "dumbbell-bench-press"))
    assert exercise is not None
    exercise.is_active = False
    db.commit()

    response = client.get("/api/v1/admin/exercises?page_size=50")

    assert response.status_code == 200
    item = next(item for item in response.json()["items"] if item["slug"] == exercise.slug)
    assert item["is_active"] is False
    assert item["created_at"]
    assert item["updated_at"]


def test_admin_list_filters_library_category_and_status(
    client: TestClient,
    db: Session,
) -> None:
    make_current_user_admin(client, db)
    seed_exercises(db)
    exercise = db.scalar(select(Exercise).where(Exercise.slug == "dumbbell-bench-press"))
    other = db.scalar(select(Exercise).where(Exercise.slug == "dumbbell-lateral-raise"))
    assert exercise is not None
    assert other is not None
    exercise.is_active = False
    exercise.needs_review = True
    other.is_active = False
    other.needs_review = True
    db.commit()

    response = client.get(
        "/api/v1/admin/exercises",
        params={
            "body_region": "upper_body",
            "primary_muscle": "chest",
            "muscle_focus": "mid_chest",
            "equipment": "dumbbell",
            "difficulty": "intermediate",
            "exercise_type": "compound",
            "is_active": "false",
            "needs_review": "true",
        },
    )

    assert response.status_code == 200
    assert [item["slug"] for item in response.json()["items"]] == ["dumbbell-bench-press"]
    assert response.json()["items"][0]["muscle_focus"] == "mid_chest"


def test_admin_list_filters_by_muscle_focus(client: TestClient, db: Session) -> None:
    make_current_user_admin(client, db)
    seed_exercises(db)

    response = client.get(
        "/api/v1/admin/exercises",
        params={
            "primary_muscle": "biceps",
            "muscle_focus": "brachialis_brachioradialis",
        },
    )

    assert response.status_code == 200
    assert [item["slug"] for item in response.json()["items"]] == ["hammer-curl"]


def test_admin_list_filters_labels(client: TestClient, db: Session) -> None:
    make_current_user_admin(client, db)

    created = post_exercise(
        client,
        exercise_payload(slug="cardio-step-up", labels=["cardio"]),
    )
    assert created.status_code == 201
    assert (
        post_exercise(
            client,
            exercise_payload(slug="plain-step-up", labels=[]),
        ).status_code
        == 201
    )

    response = client.get("/api/v1/admin/exercises", params={"labels": "cardio"})

    assert response.status_code == 200
    assert [item["slug"] for item in response.json()["items"]] == ["cardio-step-up"]


def test_admin_creates_exercise_and_normalized_associations(
    client: TestClient,
    db: Session,
) -> None:
    make_current_user_admin(client, db)

    response = post_exercise(client, exercise_payload())

    assert response.status_code == 201
    assert response.json()["slug"] == "incline-push-up"
    assert response.json()["muscle_focus"] == "mid_chest"
    assert response.json()["secondary_muscles"] == ["shoulders", "triceps"]
    assert response.json()["equipment"] == ["bench", "bodyweight"]
    assert response.json()["media_type"] == "placeholder"
    assert response.json()["media_path"] == "/exercises/exercise-placeholder.svg"
    exercise = db.scalar(select(Exercise).where(Exercise.slug == "incline-push-up"))
    assert exercise is not None
    assert {item.muscle.value for item in exercise.secondary_muscles} == {
        "shoulders",
        "triceps",
    }
    assert {item.equipment.value for item in exercise.equipment_items} == {
        "bodyweight",
        "bench",
    }


def test_admin_can_create_inactive_exercise(client: TestClient, db: Session) -> None:
    make_current_user_admin(client, db)

    response = post_exercise(client, exercise_payload(is_active=False))

    assert response.status_code == 201
    assert response.json()["is_active"] is False


@pytest.mark.parametrize(("is_active", "expected_status"), [(True, 200), (False, 404)])
def test_admin_created_exercise_publication_follows_active_status(
    client: TestClient,
    db: Session,
    is_active: bool,
    expected_status: int,
) -> None:
    make_current_user_admin(client, db)
    created = post_exercise(client, exercise_payload(is_active=is_active))
    assert created.status_code == 201
    assert client.post("/api/v1/profile", headers=ORIGIN, json=VALID_PROFILE).status_code == 201

    public_detail = client.get("/api/v1/exercises/incline-push-up")

    assert public_detail.status_code == expected_status
    if is_active:
        assert public_detail.json()["id"] == created.json()["id"]


def test_admin_creates_exercise_with_gif_and_safe_owner_metadata(
    client: TestClient,
    db: Session,
    test_settings: Settings,
) -> None:
    make_current_user_admin(client, db)

    response = post_exercise(
        client,
        exercise_payload(),
        media=("owner-demo.gif", GIF_BYTES, "image/gif"),
    )

    assert response.status_code == 201
    assert response.json()["media_type"] == "gif"
    assert response.json()["media_path"].startswith("/media/")
    assert response.json()["media_license"] == "Project owner supplied and authorized"
    assert response.json()["media_attribution"] == "Provided by Fitsho project owner"
    assert len(list(test_settings.media_root.glob("*.gif"))) == 1
    public_media = client.get(response.json()["media_path"])
    assert public_media.status_code == 200
    assert public_media.content == GIF_BYTES
    assert public_media.headers["content-type"] == "image/gif"


def test_admin_creates_exercise_with_short_video(
    client: TestClient,
    db: Session,
    test_settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    make_current_user_admin(client, db)
    monkeypatch.setattr("app.admin.media._probe_video_duration", lambda *_: 5.0)

    response = post_exercise(
        client,
        exercise_payload(),
        media=("owner-demo.mp4", MP4_BYTES, "video/mp4"),
    )

    assert response.status_code == 201
    assert response.json()["media_type"] == "video"
    assert len(list(test_settings.media_root.glob("*.mp4"))) == 1


def test_admin_creates_gendered_media_assets_and_public_detail_returns_them(
    client: TestClient,
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    make_current_user_admin(client, db)
    monkeypatch.setattr("app.admin.media._probe_video_duration", lambda *_: 5.0)
    payload = exercise_payload(
        media_assets=[
            {
                "presentation": "male",
                "role": "video",
                "media_source_url": "https://source.example/male.mp4",
                "media_license": "MIT",
                "media_attribution": "Male creator",
            },
            {
                "presentation": "female",
                "role": "video",
                "media_source_url": "https://source.example/female.mp4",
                "media_license": "MIT",
                "media_attribution": "Female creator",
            },
        ]
    )

    response = post_exercise(
        client,
        payload,
        media_assets={
            "media_male_video": ("male.mp4", MP4_BYTES, "video/mp4"),
            "media_female_video": ("female.mp4", MP4_BYTES, "video/mp4"),
        },
    )

    assert response.status_code == 201
    assert [asset["presentation"] for asset in response.json()["media_assets"]] == [
        "female",
        "male",
    ]
    assert response.json()["media_assets"][0]["media_type"] == "video"
    assert response.json()["media_assets"][0]["sort_order"] == 0
    assert client.post("/api/v1/profile", headers=ORIGIN, json=VALID_PROFILE).status_code == 201

    public_detail = client.get("/api/v1/exercises/incline-push-up")

    assert public_detail.status_code == 200
    assert [asset["presentation"] for asset in public_detail.json()["media_assets"]] == ["male"]
    assert all("id" not in asset for asset in public_detail.json()["media_assets"])

    female_detail = client.get("/api/v1/exercises/incline-push-up?presentation=female")

    assert female_detail.status_code == 200
    assert [asset["presentation"] for asset in female_detail.json()["media_assets"]] == ["female"]

    exercise = db.scalar(select(Exercise).where(Exercise.slug == "incline-push-up"))
    assert exercise is not None
    exercise.media_assets = [
        asset for asset in exercise.media_assets if asset.presentation.value != "male"
    ]
    db.flush()

    fallback_detail = client.get("/api/v1/exercises/incline-push-up")

    assert fallback_detail.status_code == 200
    assert [asset["presentation"] for asset in fallback_detail.json()["media_assets"]] == ["female"]


def test_admin_creates_multiple_media_items_for_one_gender_and_role(
    client: TestClient,
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    make_current_user_admin(client, db)
    monkeypatch.setattr("app.admin.media._probe_video_duration", lambda *_: 5.0)
    payload = exercise_payload(
        media_assets=[
            {"presentation": "male", "role": "video", "sort_order": 0, "upload_index": 0},
            {"presentation": "male", "role": "video", "sort_order": 1, "upload_index": 1},
        ]
    )

    response = client.post(
        "/api/v1/admin/exercises",
        headers=ORIGIN,
        data={"payload": json.dumps(payload)},
        files=[
            ("media_files", ("first.mp4", MP4_BYTES, "video/mp4")),
            ("media_files", ("second.mp4", MP4_BYTES + b"second", "video/mp4")),
        ],
    )

    assert response.status_code == 201
    assert [asset["sort_order"] for asset in response.json()["media_assets"]] == [0, 1]
    assert all("id" in asset for asset in response.json()["media_assets"])


def test_admin_reorders_existing_gendered_videos_without_replacing_media(
    client: TestClient,
    db: Session,
) -> None:
    make_current_user_admin(client, db)
    created = post_exercise(client, exercise_payload())
    assert created.status_code == 201
    exercise = db.get(Exercise, created.json()["id"])
    assert exercise is not None
    videos = [
        ExerciseMediaAsset(
            exercise_id=exercise.id,
            presentation="male",
            role="video",
            sort_order=sort_order,
            media_path=f"/media/male-{sort_order}.mp4",
            media_type="video",
        )
        for sort_order in range(3)
    ]
    videos.append(
        ExerciseMediaAsset(
            exercise_id=exercise.id,
            presentation="female",
            role="video",
            sort_order=0,
            media_path="/media/female-0.mp4",
            media_type="video",
        )
    )
    db.add_all(videos)
    db.commit()
    payload_assets = [
        {
            "id": str(videos[2].id),
            "presentation": "male",
            "role": "video",
            "sort_order": 0,
        },
        {
            "id": str(videos[0].id),
            "presentation": "male",
            "role": "video",
            "sort_order": 1,
        },
        {
            "id": str(videos[1].id),
            "presentation": "male",
            "role": "video",
            "sort_order": 2,
        },
        {
            "id": str(videos[3].id),
            "presentation": "female",
            "role": "video",
            "sort_order": 0,
        },
    ]

    response = client.patch(
        f"/api/v1/admin/exercises/{exercise.id}",
        headers=ORIGIN,
        data={"payload": json.dumps(exercise_payload(media_assets=payload_assets))},
    )

    assert response.status_code == 200
    db.expire_all()
    stored = list(
        db.scalars(
            select(ExerciseMediaAsset)
            .where(ExerciseMediaAsset.exercise_id == exercise.id)
            .order_by(ExerciseMediaAsset.presentation, ExerciseMediaAsset.sort_order)
        )
    )
    assert [(asset.presentation.value, asset.sort_order, asset.media_path) for asset in stored] == [
        ("female", 0, "/media/female-0.mp4"),
        ("male", 0, "/media/male-2.mp4"),
        ("male", 1, "/media/male-0.mp4"),
        ("male", 2, "/media/male-1.mp4"),
    ]
    assert {asset.id for asset in stored} == {video.id for video in videos}


def test_member_exercise_detail_returns_only_profile_gender_videos(
    client: TestClient,
    db: Session,
) -> None:
    make_current_user_admin(client, db)
    created = post_exercise(client, exercise_payload())
    assert created.status_code == 201
    exercise = db.get(Exercise, created.json()["id"])
    assert exercise is not None
    exercise.media_assets.extend(
        [
            ExerciseMediaAsset(
                presentation="female",
                role="video",
                sort_order=0,
                media_path="/media/female.mp4",
                media_type="video",
            ),
            ExerciseMediaAsset(
                presentation="male",
                role="video",
                sort_order=1,
                media_path="/media/male-second.mp4",
                media_type="video",
            ),
            ExerciseMediaAsset(
                presentation="male",
                role="video",
                sort_order=0,
                media_path="/media/male-first.mp4",
                media_type="video",
            ),
        ]
    )
    db.commit()
    assert client.post("/api/v1/profile", headers=ORIGIN, json=VALID_PROFILE).status_code == 201

    response = client.get(f"/api/v1/exercises/{exercise.slug}")

    assert response.status_code == 200
    assert [asset["media_path"] for asset in response.json()["media_assets"]] == [
        "/media/male-first.mp4",
        "/media/male-second.mp4",
    ]


def test_member_exercise_detail_falls_back_to_other_gender_video_without_matching_profile_gender(
    client: TestClient,
    db: Session,
) -> None:
    make_current_user_admin(client, db)
    created = post_exercise(client, exercise_payload())
    assert created.status_code == 201
    exercise = db.get(Exercise, created.json()["id"])
    assert exercise is not None
    exercise.media_assets.append(
        ExerciseMediaAsset(
            presentation="female",
            role="video",
            sort_order=0,
            media_path="/media/female.mp4",
            media_type="video",
        )
    )
    db.commit()
    assert client.post("/api/v1/profile", headers=ORIGIN, json=VALID_PROFILE).status_code == 201

    response = client.get(f"/api/v1/exercises/{exercise.slug}")

    assert response.status_code == 200
    assert [asset["media_path"] for asset in response.json()["media_assets"]] == [
        "/media/female.mp4"
    ]
    assert response.json()["media_presentation"] == "female"


def test_invalid_upload_returns_field_error_and_leaves_no_file(
    client: TestClient,
    db: Session,
    test_settings: Settings,
) -> None:
    make_current_user_admin(client, db)

    response = post_exercise(
        client,
        exercise_payload(),
        media=("payload.gif", b"not a gif", "image/gif"),
    )

    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["body", "media"]
    assert list(test_settings.media_root.iterdir()) == []


def test_invalid_variant_upload_removes_already_stored_legacy_media(
    client: TestClient,
    db: Session,
    test_settings: Settings,
) -> None:
    make_current_user_admin(client, db)

    response = post_exercise(
        client,
        exercise_payload(
            media_assets=[
                {
                    "presentation": "male",
                    "role": "video",
                    "media_source_url": None,
                    "media_license": None,
                    "media_attribution": None,
                }
            ]
        ),
        media=("legacy.gif", GIF_BYTES, "image/gif"),
        media_assets={"media_male_video": ("wrong.gif", GIF_BYTES, "image/gif")},
    )

    assert response.status_code == 422
    assert list(test_settings.media_root.iterdir()) == []


def test_database_failure_rolls_back_and_removes_new_media(
    client: TestClient,
    db: Session,
    test_settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    make_current_user_admin(client, db)

    def fail_create(*_: object) -> None:
        raise SQLAlchemyError("simulated failure")

    monkeypatch.setattr("app.admin.router.create_admin_exercise", fail_create)

    response = post_exercise(
        client,
        exercise_payload(),
        media=("owner-demo.gif", GIF_BYTES, "image/gif"),
    )

    assert response.status_code == 503
    assert db.scalar(select(Exercise).where(Exercise.slug == "incline-push-up")) is None
    assert list(test_settings.media_root.iterdir()) == []


def test_duplicate_slug_returns_conflict(client: TestClient, db: Session) -> None:
    make_current_user_admin(client, db)
    assert post_exercise(client, exercise_payload()).status_code == 201

    response = post_exercise(client, exercise_payload())

    assert response.status_code == 409
    assert response.json() == {"detail": "Exercise slug already exists"}


@pytest.mark.parametrize(
    ("body_region", "primary_muscle", "name_en", "name_fa", "slug"),
    [
        ("lower_body", "abductors", "Abductor Exercise", "حرکت بیرون پا", "abductor-exercise"),
        ("lower_body", "legs", "Whole Leg Exercise", "حرکت کل پا", "whole-leg-exercise"),
        ("upper_body", "back", "Back Extension", "باز کردن پشت", "back-extension"),
    ],
)
def test_admin_can_create_new_taxonomy_muscle_groups(
    client: TestClient,
    db: Session,
    body_region: str,
    primary_muscle: str,
    name_en: str,
    name_fa: str,
    slug: str,
) -> None:
    make_current_user_admin(client, db)

    response = post_exercise(
        client,
        exercise_payload(
            slug=slug,
            name_en=name_en,
            name_fa=name_fa,
            body_region=body_region,
            primary_muscle=primary_muscle,
            muscle_focus=("lower_back" if slug == "back-extension" else None),
            secondary_muscles=[],
        ),
    )

    assert response.status_code == 201
    assert response.json()["primary_muscle"] == primary_muscle
    assert response.json()["muscle_focus"] == ("lower_back" if slug == "back-extension" else None)


def test_create_rejects_browser_supplied_media_path(
    client: TestClient,
    db: Session,
) -> None:
    make_current_user_admin(client, db)

    response = post_exercise(
        client,
        exercise_payload(media_path="../../frontend/public/payload.gif"),
    )

    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["body", "media_path"]


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("body_region", "arms"),
        ("difficulty", "expert"),
        ("equipment", ["kettlebell"]),
        ("slug", "Incline Push Up"),
        ("equipment", []),
        ("instructions_en", ["One", "Two"]),
        ("instructions_fa", ["یک", "دو"]),
        ("instructions_en", ["1", "2", "3", "4", "5", "6", "7"]),
        ("instructions_fa", ["۱", "۲", "۳", "۴", "۵", "۶", "۷"]),
    ],
)
def test_create_rejects_invalid_fields(
    client: TestClient,
    db: Session,
    field: str,
    value: object,
) -> None:
    make_current_user_admin(client, db)

    response = post_exercise(client, exercise_payload(**{field: value}))

    assert response.status_code == 422
    assert field in response.json()["detail"][0]["loc"]


@pytest.mark.parametrize(
    ("body_region", "primary_muscle", "secondary_muscles"),
    [
        ("upper_body", "quadriceps", ["triceps"]),
        ("lower_body", "abs", ["glutes"]),
        ("core", "shoulders", ["abs"]),
    ],
)
def test_create_rejects_primary_muscle_outside_body_region(
    client: TestClient,
    db: Session,
    body_region: str,
    primary_muscle: str,
    secondary_muscles: list[str],
) -> None:
    make_current_user_admin(client, db)

    response = post_exercise(
        client,
        exercise_payload(
            body_region=body_region,
            primary_muscle=primary_muscle,
            secondary_muscles=secondary_muscles,
        ),
    )

    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"][-1] == "primary_muscle"


def test_create_rejects_primary_muscle_as_secondary(
    client: TestClient,
    db: Session,
) -> None:
    make_current_user_admin(client, db)

    response = post_exercise(
        client,
        exercise_payload(secondary_muscles=["chest", "triceps"]),
    )

    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"][-1] == "secondary_muscles"


def test_create_rejects_focus_outside_primary_muscle(
    client: TestClient,
    db: Session,
) -> None:
    make_current_user_admin(client, db)

    response = post_exercise(
        client,
        exercise_payload(muscle_focus="front_delt"),
    )

    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"][-1] == "muscle_focus"


def test_create_allows_cross_region_secondary_muscles(
    client: TestClient,
    db: Session,
) -> None:
    make_current_user_admin(client, db)
    created = post_exercise(client, exercise_payload())
    assert created.status_code == 201

    response = client.patch(
        f"/api/v1/admin/exercises/{created.json()['id']}",
        headers=ORIGIN,
        data={
            "payload": json.dumps(
                exercise_payload(
                    primary_muscle="back",
                    muscle_focus="general_back",
                    secondary_muscles=["biceps", "lower_back", "traps"],
                )
            )
        },
    )

    assert response.status_code == 200
    assert response.json()["secondary_muscles"] == ["biceps", "lower_back", "traps"]


@pytest.mark.parametrize("headers", [{}, {"Origin": "https://evil.example"}])
def test_create_requires_trusted_origin(
    client: TestClient,
    db: Session,
    headers: dict[str, str],
) -> None:
    make_current_user_admin(client, db)

    response = post_exercise(client, exercise_payload(), headers=headers)

    assert response.status_code == 403
    assert response.json() == {"detail": "Untrusted request origin"}


def test_admin_can_update_programming_metadata(
    client: TestClient,
    db: Session,
) -> None:
    make_current_user_admin(client, db)
    created = post_exercise(client, exercise_payload())
    assert created.status_code == 201

    response = client.patch(
        f"/api/v1/admin/exercises/{created.json()['id']}",
        headers=ORIGIN,
        data={
            "payload": json.dumps(
                exercise_payload(
                    movement_pattern="horizontal_push",
                    exercise_type="compound",
                    caution_tags=["shoulder_internal_rotation"],
                    is_programmable=True,
                    body_position="supported",
                    stability_demand="high",
                    skill_demand="moderate",
                    impact_level="low",
                    axial_loading_level="none",
                    laterality="unilateral",
                    fatigue_cost=4,
                    setup_cost=2,
                    substitution_group="horizontal_push",
                    range_of_motion_profile=["supported", "shortened"],
                )
            )
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["movement_pattern"] == "horizontal_push"
    assert body["exercise_type"] == "compound"
    assert body["caution_tags"] == ["shoulder_internal_rotation"]
    assert body["is_programmable"] is True
    assert body["body_position"] == "supported"
    assert body["stability_demand"] == "high"
    assert body["skill_demand"] == "moderate"
    assert body["impact_level"] == "low"
    assert body["axial_loading_level"] == "none"
    assert body["laterality"] == "unilateral"
    assert body["fatigue_cost"] == 4
    assert body["setup_cost"] == 2
    assert body["substitution_group"] == "horizontal_push"
    assert body["range_of_motion_profile"] == ["supported", "shortened"]
    stored = db.scalar(select(Exercise).where(Exercise.id == created.json()["id"]))
    assert stored is not None
    assert stored.movement_pattern.value == "horizontal_push"
    assert stored.body_position.value == "supported"
    assert stored.fatigue_cost == 4
    assert stored.setup_cost == 2
    assert stored.substitution_group == "horizontal_push"
    assert stored.range_of_motion_profile == ["supported", "shortened"]
    assert [item.caution_tag.value for item in stored.caution_tag_items] == [
        "shoulder_internal_rotation"
    ]

    read = client.get(f"/api/v1/admin/exercises/{created.json()['id']}")
    assert read.status_code == 200
    assert read.json()["body_position"] == "supported"
    assert read.json()["stability_demand"] == "high"
    assert read.json()["skill_demand"] == "moderate"
    assert read.json()["impact_level"] == "low"
    assert read.json()["axial_loading_level"] == "none"
    assert read.json()["fatigue_cost"] == 4
    assert read.json()["setup_cost"] == 2
    assert read.json()["laterality"] == "unilateral"
    assert read.json()["substitution_group"] == "horizontal_push"
    assert read.json()["range_of_motion_profile"] == ["supported", "shortened"]


def test_admin_can_update_name_without_safety_notes(
    client: TestClient,
    db: Session,
) -> None:
    make_current_user_admin(client, db)
    created = post_exercise(client, exercise_payload())
    assert created.status_code == 201

    response = client.patch(
        f"/api/v1/admin/exercises/{created.json()['id']}",
        headers=ORIGIN,
        data={
            "payload": json.dumps(
                exercise_payload(
                    name_en="Renamed Incline Push Up",
                    name_fa="شنا سوئدی شیب‌دار تغییرنام‌یافته",
                    safety_notes_en=[],
                    safety_notes_fa=[],
                )
            )
        },
    )

    assert response.status_code == 200
    assert response.json()["name_en"] == "Renamed Incline Push Up"
    assert response.json()["safety_notes_en"] == []
    assert response.json()["safety_notes_fa"] == []


def test_admin_can_switch_existing_item_between_exercise_and_guide_without_media_loss(
    client: TestClient,
    db: Session,
) -> None:
    from app.exercises.enums import ExerciseContentType
    from app.exercises.models import ExerciseMediaAsset

    make_current_user_admin(client, db)
    created = post_exercise(client, exercise_payload())
    assert created.status_code == 201
    exercise = db.get(Exercise, created.json()["id"])
    assert exercise is not None
    exercise.media_path = "/media/existing-guide.mp4"
    exercise.media_type = "video"
    exercise.media_assets.append(
        ExerciseMediaAsset(
            presentation="male",
            role="video",
            media_path="/media/existing-guide-male.mp4",
            media_type="video",
        )
    )
    db.commit()
    original_id = exercise.id
    original_media_path = exercise.media_path
    original_asset_count = len(exercise.media_assets)
    media_metadata = [
        {
            "id": str(exercise.media_assets[0].id),
            "presentation": "male",
            "role": "video",
            "sort_order": 0,
            "media_source_url": None,
            "media_license": None,
            "media_attribution": None,
        }
    ]

    guide_response = client.patch(
        f"/api/v1/admin/exercises/{original_id}",
        headers=ORIGIN,
        data={
            "payload": json.dumps(
                exercise_payload(content_type="guide", media_assets=media_metadata)
            )
        },
    )

    assert guide_response.status_code == 200
    assert guide_response.json()["content_type"] == "guide"
    stored = db.get(Exercise, original_id)
    assert stored is not None
    assert stored.content_type is ExerciseContentType.GUIDE
    assert stored.media_path == original_media_path
    assert len(stored.media_assets) == original_asset_count
    assert stored.equipment_items

    exercise_response = client.patch(
        f"/api/v1/admin/exercises/{original_id}",
        headers=ORIGIN,
        data={
            "payload": json.dumps(
                exercise_payload(content_type="exercise", media_assets=media_metadata)
            )
        },
    )

    assert exercise_response.status_code == 200
    assert exercise_response.json()["content_type"] == "exercise"
    assert db.get(Exercise, original_id) is not None


def test_admin_updates_a_gendered_media_asset(
    client: TestClient,
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    make_current_user_admin(client, db)
    created = post_exercise(client, exercise_payload())
    assert created.status_code == 201
    monkeypatch.setattr("app.admin.media._probe_video_duration", lambda *_: 5.0)

    response = client.patch(
        f"/api/v1/admin/exercises/{created.json()['id']}",
        headers=ORIGIN,
        data={
            "payload": json.dumps(
                exercise_payload(
                    media_assets=[
                        {
                            "presentation": "female",
                            "role": "video",
                            "media_source_url": "https://source.example/female.mp4",
                            "media_license": "MIT",
                            "media_attribution": "Female creator",
                        }
                    ]
                )
            )
        },
        files={"media_female_video": ("female.mp4", MP4_BYTES, "video/mp4")},
    )

    assert response.status_code == 200
    asset = response.json()["media_assets"][0]
    assert asset["presentation"] == "female"
    assert asset["role"] == "video"
    assert asset["media_path"].startswith("/media/")
    assert asset["media_type"] == "video"
    assert asset["media_source_url"] == "https://source.example/female.mp4"
    assert asset["media_license"] == "MIT"
    assert asset["media_attribution"] == "Female creator"


def test_admin_creates_review_exercise_with_labels_and_no_anatomy(
    client: TestClient,
    db: Session,
) -> None:
    make_current_user_admin(client, db)

    response = post_exercise(
        client,
        exercise_payload(
            body_region=None,
            primary_muscle=None,
            muscle_focus=None,
            secondary_muscles=[],
            labels=["cardio"],
            needs_review=True,
        ),
    )

    assert response.status_code == 201
    assert response.json()["body_region"] is None
    assert response.json()["primary_muscle"] is None
    assert response.json()["labels"] == ["cardio"]
