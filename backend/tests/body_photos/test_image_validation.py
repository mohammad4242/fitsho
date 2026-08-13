from io import BytesIO

import pytest
from fastapi import UploadFile
from PIL import Image

from app.body_photos.image_validation import BodyPhotoValidationError, validate_and_normalize
from app.config import Settings


def _jpeg(
    size: tuple[int, int] = (1200, 2400),
    *,
    orientation: int | None = None,
) -> bytes:
    image = Image.new("RGB", size, (80, 120, 150))
    output = BytesIO()
    exif = Image.Exif()
    if orientation is not None:
        exif[274] = orientation
    image.save(output, "JPEG", quality=88, exif=exif)
    return output.getvalue()


def _upload(content: bytes, content_type: str = "image/jpeg") -> UploadFile:
    return UploadFile(filename="headless.jpg", file=BytesIO(content), headers={
        "content-type": content_type,
    })


def test_accepts_standardized_headless_photo_without_crop_evidence() -> None:
    result = validate_and_normalize(_upload(_jpeg()), Settings(app_env="test"))

    assert result.width == 1200
    assert result.height == 2400
    assert result.mime_type == "image/jpeg"
    assert not hasattr(result, "crop_top")
    assert not hasattr(result, "client_crop_confidence")


def test_accepts_exif_rotated_phone_jpeg_after_orientation_normalization() -> None:
    result = validate_and_normalize(
        _upload(_jpeg((2400, 1200), orientation=6)),
        Settings(app_env="test"),
    )

    assert (result.width, result.height) == (1200, 2400)


def test_frontend_and_backend_share_the_40_megapixel_limit() -> None:
    settings = Settings(app_env="test")
    assert settings.body_photo_max_pixels == 40_000_000


def test_file_size_error_uses_the_shared_frontend_contract() -> None:
    settings = Settings(app_env="test", body_photo_max_bytes=1024)

    with pytest.raises(BodyPhotoValidationError) as caught:
        validate_and_normalize(_upload(_jpeg()), settings)

    assert caught.value.code == "invalid_file_size"


@pytest.mark.parametrize(
    ("content", "content_type", "code"),
    [
        (b"not-an-image", "image/jpeg", "invalid_image"),
        (_jpeg(), "image/gif", "unsupported_format"),
        (_jpeg((640, 320)), "image/jpeg", "invalid_geometry"),
    ],
)
def test_returns_a_stable_actionable_basic_validation_code(
    content: bytes,
    content_type: str,
    code: str,
) -> None:
    with pytest.raises(BodyPhotoValidationError) as caught:
        validate_and_normalize(_upload(content, content_type), Settings(app_env="test"))

    assert caught.value.code == code
