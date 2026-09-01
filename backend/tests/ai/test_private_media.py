import pytest
from pydantic import ValidationError

from app.body_analysis.providers.models import ImageInput


def test_image_input_accepts_a_stored_reference_without_inline_bytes() -> None:
    image = ImageInput(
        label="front",
        mime_type="image/jpeg",
        storage_scope="body",
        storage_key="ab/abcdef0123456789abcdef0123456789.jpg",
    )

    assert image.base64_data is None
    assert image.storage_scope == "body"
    assert image.storage_key == "ab/abcdef0123456789abcdef0123456789.jpg"


@pytest.mark.parametrize(
    "overrides",
    [
        {"base64_data": "a", "storage_scope": "body", "storage_key": "ab/file.jpg"},
        {"storage_scope": "body"},
        {"storage_key": "ab/file.jpg"},
        {},
    ],
)
def test_image_input_rejects_invalid_source_combinations(
    overrides: dict[str, object],
) -> None:
    with pytest.raises(ValidationError):
        ImageInput(label="front", mime_type="image/jpeg", **overrides)
