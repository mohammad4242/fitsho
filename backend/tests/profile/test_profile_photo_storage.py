from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image
from starlette.datastructures import Headers
from starlette.datastructures import UploadFile as StarletteUploadFile

from app.config import Settings
from app.profile.photo import (
    ProfilePhotoStorage,
    ProfilePhotoStorageError,
    ProfilePhotoValidationError,
    validate_and_normalize_profile_photo,
)


def _upload(
    content: bytes,
    content_type: str,
    filename: str = "profile.png",
) -> StarletteUploadFile:
    return StarletteUploadFile(
        file=BytesIO(content),
        filename=filename,
        headers=Headers({"content-type": content_type}),
    )


def _image(width: int = 256, height: int = 256, image_format: str = "PNG") -> bytes:
    output = BytesIO()
    Image.new("RGB", (width, height), color=(28, 84, 110)).save(output, format=image_format)
    return output.getvalue()


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        app_env="test",
        cookie_secure=False,
        session_cookie_name="fitsho_session",
        media_root=tmp_path / "public-media",
        profile_photo_storage_root=tmp_path / "private-profile-photos",
    )


def test_valid_square_image_is_normalized_without_private_metadata(tmp_path: Path) -> None:
    normalized = validate_and_normalize_profile_photo(
        _upload(_image(), "image/png"),
        _settings(tmp_path),
    )

    assert normalized.mime_type == "image/png"
    assert normalized.extension == ".png"
    assert normalized.width == 256
    assert normalized.height == 256
    assert normalized.content.startswith(b"\x89PNG\r\n\x1a\n")


@pytest.mark.parametrize(
    ("content", "content_type", "code"),
    [
        (_image(), "image/jpeg", "invalid_image"),
        (_image(320, 256), "image/png", "invalid_geometry"),
        (b"", "image/png", "invalid_image"),
    ],
)
def test_invalid_profile_photo_input_is_rejected(
    tmp_path: Path,
    content: bytes,
    content_type: str,
    code: str,
) -> None:
    with pytest.raises(ProfilePhotoValidationError) as error:
        validate_and_normalize_profile_photo(_upload(content, content_type), _settings(tmp_path))

    assert error.value.code == code


def test_profile_photo_byte_limit_is_enforced_before_storage(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    settings.profile_photo_max_bytes = 10

    with pytest.raises(ProfilePhotoValidationError) as error:
        validate_and_normalize_profile_photo(_upload(_image(), "image/png"), settings)

    assert error.value.code == "invalid_file_size"
    assert not settings.profile_photo_storage_root.exists()


def test_storage_writes_atomic_private_object_and_rejects_unsafe_keys(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    storage = ProfilePhotoStorage(settings)
    stored = storage.store(_image(), ".png")

    assert stored.key.startswith(f"{stored.key[:2]}/")
    assert storage.path_for(stored.key).read_bytes() == _image()
    assert storage.path_for(stored.key).is_relative_to(settings.profile_photo_storage_root)

    with pytest.raises(ProfilePhotoStorageError):
        storage.path_for("../outside.png")

    storage.delete(stored.key)
    assert not storage.path_for(stored.key).exists()
