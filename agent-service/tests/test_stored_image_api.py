from pathlib import Path

import pytest
from pydantic import ValidationError

from app.private_media import PrivateMediaError, PrivateMediaResolver
from app.schemas import StoredImageGenerationInput, StoredImageReference

BODY_KEY = "ab/abcdef0123456789abcdef0123456789.jpg"
FOOD_KEY = "cd/cd23456789abcdef0123456789abcdef.jpg"


def _stored_reference(
    *,
    label: str = "front",
    mime_type: str = "image/jpeg",
    scope: str = "body",
    key: str = BODY_KEY,
) -> dict[str, str]:
    return {
        "label": label,
        "mime_type": mime_type,
        "storage_scope": scope,
        "storage_key": key,
    }


def _generation() -> dict[str, object]:
    return {
        "agent": "antigravity",
        "model_id": "fake-model",
        "system_prompt": "Describe the image.",
        "input_payload": {},
        "response_schema": {"type": "object"},
        "schema_name": "image_answer",
        "temperature": 0,
        "max_output_tokens": 100,
        "timeout_seconds": 5,
    }


def _write(root: Path, scope: str, key: str, content: bytes = b"image") -> Path:
    path = root / scope / key
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return path


def _resolver(root: Path, **limits: int) -> PrivateMediaResolver:
    return PrivateMediaResolver(
        root,
        max_images=limits.get("max_images", 5),
        max_file_bytes=limits.get("max_file_bytes", 1024),
        max_total_bytes=limits.get("max_total_bytes", 2048),
    )


def test_stored_image_contract_is_composed_and_forbids_paths() -> None:
    reference = StoredImageReference.model_validate(_stored_reference())
    request = StoredImageGenerationInput.model_validate(
        {"generation": _generation(), "images": [reference.model_dump()]}
    )

    assert request.generation.image_labels is None
    assert request.images == (reference,)
    with pytest.raises(ValidationError):
        StoredImageReference.model_validate({**_stored_reference(), "path": "/etc/passwd"})

    with pytest.raises(ValidationError):
        StoredImageGenerationInput.model_validate(
            {
                "generation": {**_generation(), "image_labels": ["front"]},
                "images": [_stored_reference()],
            }
        )


def test_private_media_resolver_resolves_body_and_food_under_scoped_roots(tmp_path: Path) -> None:
    _write(tmp_path / "shared", "body", BODY_KEY)
    _write(tmp_path / "shared", "food", FOOD_KEY)
    resolver = _resolver(tmp_path / "shared")

    body_path = resolver.resolve("body", BODY_KEY, "image/jpeg")
    food_path = resolver.resolve("food", FOOD_KEY, "image/jpeg")

    assert body_path == (tmp_path / "shared/body" / BODY_KEY).resolve()
    assert food_path == (tmp_path / "shared/food" / FOOD_KEY).resolve()


@pytest.mark.parametrize(
    ("scope", "key", "mime_type"),
    [
        ("body", "/etc/passwd", "image/jpeg"),
        ("body", "../abcdef0123456789abcdef0123456789.jpg", "image/jpeg"),
        ("body", "ab/../abcdef0123456789abcdef0123456789.jpg", "image/jpeg"),
        ("body", "ab//abcdef0123456789abcdef0123456789.jpg", "image/jpeg"),
        ("body", "ab/c/abcdef0123456789abcdef0123456789.jpg", "image/jpeg"),
        ("body", "ab/abcdef0123456789abcdef0123456789.png", "image/jpeg"),
        ("body", "ab/abcdef0123456789abcdef0123456789.gif", "image/jpeg"),
        ("other", BODY_KEY, "image/jpeg"),
    ],
)
def test_private_media_resolver_rejects_unsafe_or_mismatched_references(
    tmp_path: Path, scope: str, key: str, mime_type: str
) -> None:
    _write(tmp_path / "shared", "body", BODY_KEY)
    resolver = _resolver(tmp_path / "shared")

    with pytest.raises(PrivateMediaError) as error:
        resolver.resolve(scope, key, mime_type)

    assert str(tmp_path) not in str(error.value)


def test_private_media_resolver_rejects_missing_directories_and_symlink_escape(
    tmp_path: Path,
) -> None:
    root = tmp_path / "shared"
    _write(root, "body", BODY_KEY)
    outside = tmp_path / "outside.jpg"
    outside.write_bytes(b"outside")
    escape = root / "body/ab/abcdef0123456789abcdef0123456780.jpg"
    escape.symlink_to(outside)
    resolver = _resolver(root)

    for key in (
        "ab/abcdef0123456789abcdef0123456781.jpg",
        "ab/abcdef0123456789abcdef0123456782.jpg",
    ):
        with pytest.raises(PrivateMediaError):
            resolver.resolve("body", key, "image/jpeg")
    with pytest.raises(PrivateMediaError):
        resolver.resolve("body", "ab/abcdef0123456789abcdef0123456780.jpg", "image/jpeg")

    directory_key = "ab/abcdef0123456789abcdef0123456783.jpg"
    (root / "body" / directory_key).mkdir()
    with pytest.raises(PrivateMediaError):
        resolver.resolve("body", directory_key, "image/jpeg")

    escaped_root = tmp_path / "escaped-root"
    _write(escaped_root, "body", BODY_KEY)
    root_with_link = tmp_path / "root-with-link"
    root_with_link.mkdir()
    (root_with_link / "body").symlink_to(escaped_root / "body", target_is_directory=True)
    with pytest.raises(PrivateMediaError):
        _resolver(root_with_link).resolve("body", BODY_KEY, "image/jpeg")


def test_private_media_resolver_enforces_per_file_and_total_size_limits(tmp_path: Path) -> None:
    root = tmp_path / "shared"
    _write(root, "body", BODY_KEY, b"12345")
    second_key = "ab/abcdef0123456789abcdef0123456788.jpg"
    _write(root, "body", second_key, b"12345")

    with pytest.raises(PrivateMediaError):
        _resolver(root, max_file_bytes=4).resolve("body", BODY_KEY, "image/jpeg")
    with pytest.raises(PrivateMediaError):
        _resolver(root, max_total_bytes=9).resolve_many(
            (
                StoredImageReference.model_validate(_stored_reference()),
                StoredImageReference.model_validate(
                    _stored_reference(key=second_key, label="side")
                ),
            )
        )


def test_private_media_resolver_enforces_image_count_limit(tmp_path: Path) -> None:
    root = tmp_path / "shared"
    _write(root, "body", BODY_KEY)
    references = tuple(
        StoredImageReference.model_validate(
            _stored_reference(key=BODY_KEY, label=f"image-{index}")
        )
        for index in range(2)
    )

    with pytest.raises(PrivateMediaError):
        _resolver(root, max_images=1).resolve_many(references)
