from io import BytesIO
from pathlib import Path
from uuid import UUID

from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.body_analysis.enums import SpecialistRole
from app.body_analysis.models import UserSpecialistRole
from app.config import Settings
from app.profile.models import UserProfilePhoto
from app.workout_reviews.repository import ensure_pending_review
from tests.nutrition.test_clinical_review_api import _login_physician, _member_plan
from tests.workout_reviews.test_api import _plan

ORIGIN = {"Origin": "http://localhost:5173"}


def _image(width: int = 256, height: int = 256, image_format: str = "PNG") -> bytes:
    output = BytesIO()
    Image.new("RGB", (width, height), color=(28, 84, 110)).save(output, format=image_format)
    return output.getvalue()


def _register(client: TestClient, email: str) -> dict[str, object]:
    response = client.post(
        "/api/v1/auth/register",
        headers=ORIGIN,
        json={"email": email, "password": "long password"},
    )
    assert response.status_code == 201, response.text
    return response.json()


def _use_private_root(test_settings: Settings) -> Path:
    root = Path(test_settings.media_root).parent / "profile-private"
    test_settings.profile_photo_storage_root = root
    return root


def test_profile_photo_requires_authentication(client: TestClient) -> None:
    assert client.get("/api/v1/profile/photo").status_code == 401
    assert client.put(
        "/api/v1/profile/photo",
        headers=ORIGIN,
        files={"file": ("profile.png", _image(), "image/png")},
    ).status_code == 401
    assert client.delete("/api/v1/profile/photo", headers=ORIGIN).status_code == 401


def test_owner_can_upload_stream_and_delete_private_profile_photo(
    client: TestClient,
    db: Session,
    test_settings: Settings,
) -> None:
    private_root = _use_private_root(test_settings)
    user = _register(client, "profile-photo-owner@example.com")

    upload = client.put(
        "/api/v1/profile/photo",
        headers=ORIGIN,
        files={"file": ("profile.png", _image(), "image/png")},
    )

    assert upload.status_code == 200, upload.text
    payload = upload.json()
    assert payload["profile_photo_url"].startswith("/api/v1/profile/photo/")
    assert payload["mime_type"] == "image/png"
    assert payload["width"] == payload["height"] == 256
    row = db.scalar(
        select(UserProfilePhoto).where(UserProfilePhoto.user_id == UUID(str(user["id"])))
    )
    assert row is not None
    stored_path = private_root / row.storage_key
    assert stored_path.is_file()
    assert stored_path.is_relative_to(private_root)
    assert not stored_path.is_relative_to(test_settings.media_root)
    current = client.get("/api/v1/auth/me")
    assert current.status_code == 200
    assert current.json()["profile_photo_url"] == payload["profile_photo_url"]

    content = client.get("/api/v1/profile/photo")
    assert content.status_code == 200
    assert content.headers["content-type"].startswith("image/png")
    assert content.headers["cache-control"] == "private, no-store"
    assert content.content.startswith(b"\x89PNG\r\n\x1a\n")

    deleted = client.delete("/api/v1/profile/photo", headers=ORIGIN)
    assert deleted.status_code == 204
    assert not stored_path.exists()
    assert client.get("/api/v1/profile/photo").status_code == 404


def test_unrelated_authenticated_user_cannot_stream_another_users_photo(
    client: TestClient,
    test_settings: Settings,
) -> None:
    _use_private_root(test_settings)
    owner = _register(client, "profile-photo-private-owner@example.com")
    upload = client.put(
        "/api/v1/profile/photo",
        headers=ORIGIN,
        files={"file": ("profile.png", _image(), "image/png")},
    )
    assert upload.status_code == 200

    client.post("/api/v1/auth/logout", headers=ORIGIN)
    _register(client, "profile-photo-private-other@example.com")
    response = client.get(f"/api/v1/profile/photo/{owner['id']}")

    assert response.status_code == 403


def test_replacing_photo_removes_only_the_previous_private_object(
    client: TestClient,
    db: Session,
    test_settings: Settings,
) -> None:
    private_root = _use_private_root(test_settings)
    _register(client, "profile-photo-replace@example.com")

    first = client.put(
        "/api/v1/profile/photo",
        headers=ORIGIN,
        files={"file": ("profile.png", _image(), "image/png")},
    )
    assert first.status_code == 200
    old_row = db.scalar(select(UserProfilePhoto))
    assert old_row is not None
    old_key = old_row.storage_key
    old_path = private_root / old_key
    assert old_path.exists()

    second = client.put(
        "/api/v1/profile/photo",
        headers=ORIGIN,
        files={"file": ("profile.jpg", _image(image_format="JPEG"), "image/jpeg")},
    )

    assert second.status_code == 200, second.text
    new_row = db.scalar(select(UserProfilePhoto))
    assert new_row is not None
    assert new_row.storage_key != old_key
    assert not old_path.exists()
    assert (private_root / new_row.storage_key).exists()
    assert second.json()["mime_type"] == "image/jpeg"
    assert second.json()["profile_photo_url"] != first.json()["profile_photo_url"]


def test_invalid_profile_photo_is_rejected_without_creating_a_row(
    client: TestClient,
    db: Session,
    test_settings: Settings,
) -> None:
    _use_private_root(test_settings)
    _register(client, "profile-photo-invalid@example.com")

    response = client.put(
        "/api/v1/profile/photo",
        headers=ORIGIN,
        files={"file": ("profile.png", _image(320, 256), "image/png")},
    )

    assert response.status_code == 422
    assert response.json() == {"detail": {"code": "invalid_geometry"}}
    assert db.scalar(select(UserProfilePhoto)) is None


def test_claimed_coach_can_view_member_profile_photo_and_pending_queue_hides_it(
    client: TestClient,
    db: Session,
    test_settings: Settings,
) -> None:
    private_root = _use_private_root(test_settings)
    owner = _register(client, "profile-photo-coach-member@example.com")
    upload = client.put(
        "/api/v1/profile/photo",
        headers=ORIGIN,
        files={"file": ("profile.png", _image(), "image/png")},
    )
    assert upload.status_code == 200

    member_id = UUID(str(owner["id"]))
    review = ensure_pending_review(db, _plan(db, member_id))
    db.commit()
    stored = db.scalar(select(UserProfilePhoto))
    assert stored is not None
    assert (private_root / stored.storage_key).exists()

    client.post("/api/v1/auth/logout", headers=ORIGIN)
    coach = _register(client, "profile-photo-coach@example.com")
    coach_id = UUID(str(coach["id"]))
    db.add(UserSpecialistRole(user_id=coach_id, role=SpecialistRole.COACH))
    db.commit()

    pending = client.get("/api/v1/coach/workout-reviews?view=pending")
    assert pending.status_code == 200
    pending_item = next(item for item in pending.json() if item["id"] == str(review.id))
    assert pending_item["member_profile_photo_url"] is None

    claimed = client.post(
        f"/api/v1/coach/workout-reviews/{review.id}/claim",
        headers=ORIGIN,
    )
    assert claimed.status_code == 200, claimed.text
    assert claimed.json()["member_profile_photo_url"].startswith(
        f"/api/v1/profile/photo/{owner['id']}"
    )

    photo = client.get(claimed.json()["member_profile_photo_url"])
    assert photo.status_code == 200
    assert photo.content.startswith(b"\x89PNG\r\n\x1a\n")


def test_claimed_physician_can_view_member_profile_photo(
    client: TestClient,
    db: Session,
    test_settings: Settings,
) -> None:
    _use_private_root(test_settings)
    member = _member_plan(client, db)
    upload = client.put(
        "/api/v1/profile/photo",
        headers=ORIGIN,
        files={"file": ("profile.png", _image(), "image/png")},
    )
    assert upload.status_code == 200, upload.text

    _login_physician(client, db, "profile-photo-physician@example.com")
    pending = client.get("/api/v1/nutrition/physician/reviews?view=pending")
    assert pending.status_code == 200
    pending_item = next(item for item in pending.json() if item["plan_id"] == member["id"])
    assert pending_item["member_profile_photo_url"] is None

    claimed = client.post(
        f"/api/v1/nutrition/physician/reviews/{pending_item['review_id']}/claim",
        headers=ORIGIN,
    )
    assert claimed.status_code == 200, claimed.text
    claimed_queue = client.get("/api/v1/nutrition/physician/reviews?view=claimed")
    assert claimed_queue.status_code == 200
    claimed_item = next(item for item in claimed_queue.json() if item["plan_id"] == member["id"])
    photo_url = claimed_item["member_profile_photo_url"]
    assert photo_url.startswith(f"/api/v1/profile/photo/{claimed_item['user_id']}")
    assert client.get(photo_url).status_code == 200
