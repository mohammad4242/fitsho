from pathlib import Path

import pytest

from app.config import Settings
from app.private_media import PrivateMediaError, PrivateMediaResolver


def _resolver(tmp_path: Path) -> tuple[PrivateMediaResolver, Path, Path]:
    body_root = tmp_path / "body-photos"
    food_root = tmp_path / "food-photos"
    settings = Settings(
        app_env="test",
        cookie_secure=False,
        session_cookie_name="fitsho_session",
        media_root=tmp_path / "public-media",
        body_photo_storage_root=body_root,
        food_photo_storage_root=food_root,
    )
    return PrivateMediaResolver(settings), body_root, food_root


def test_resolver_reads_body_and_food_files_from_their_scopes(tmp_path: Path) -> None:
    resolver, body_root, food_root = _resolver(tmp_path)
    body_path = body_root / "ab/abcdef0123456789abcdef0123456789.jpg"
    food_path = food_root / "cd/cdef0123456789abcdef0123456789ab.jpg"
    body_path.parent.mkdir(parents=True)
    food_path.parent.mkdir(parents=True)
    body_path.write_bytes(b"body-image")
    food_path.write_bytes(b"food-image")

    assert resolver.read("body", body_path.relative_to(body_root).as_posix(), "image/jpeg") == (
        b"body-image"
    )
    assert resolver.resolve(
        "food", food_path.relative_to(food_root).as_posix(), "image/jpeg"
    ) == food_path.resolve()


@pytest.mark.parametrize(
    "key",
    [
        "/etc/passwd",
        "../outside.jpg",
        "ab/../../outside.jpg",
        "ab//file.jpg",
        "ab/./file.jpg",
        "ab/file.jpg/extra",
        "",
        "ab\\file.jpg",
        "ab/file.gif",
    ],
)
def test_resolver_rejects_unsafe_or_unsupported_keys(tmp_path: Path, key: str) -> None:
    resolver, _, _ = _resolver(tmp_path)

    with pytest.raises(PrivateMediaError) as error:
        resolver.resolve("body", key, "image/jpeg")

    assert str(error.value) == "invalid private media reference"
    if key:
        assert key not in str(error.value)


def test_resolver_rejects_unknown_scope(tmp_path: Path) -> None:
    resolver, _, _ = _resolver(tmp_path)

    with pytest.raises(PrivateMediaError, match="invalid private media reference"):
        resolver.resolve("nutrition", "ab/file.jpg", "image/jpeg")


def test_resolver_rejects_missing_directories_and_files(tmp_path: Path) -> None:
    resolver, body_root, _ = _resolver(tmp_path)
    directory = body_root / "ab/directory.jpg"
    directory.mkdir(parents=True)

    for key in ("ab/missing.jpg", "ab/directory.jpg"):
        with pytest.raises(PrivateMediaError, match="invalid private media reference"):
            resolver.resolve("body", key, "image/jpeg")


def test_resolver_rejects_mime_extension_mismatch(tmp_path: Path) -> None:
    resolver, body_root, _ = _resolver(tmp_path)
    path = body_root / "ab/abcdef0123456789abcdef0123456789.jpg"
    path.parent.mkdir(parents=True)
    path.write_bytes(b"image")

    with pytest.raises(PrivateMediaError, match="invalid private media reference"):
        resolver.resolve("body", "ab/abcdef0123456789abcdef0123456789.jpg", "image/png")


def test_resolver_rejects_symlink_escape(tmp_path: Path) -> None:
    resolver, body_root, _ = _resolver(tmp_path)
    outside = tmp_path / "outside.jpg"
    outside.write_bytes(b"outside")
    link = body_root / "ab/abcdef0123456789abcdef0123456789.jpg"
    link.parent.mkdir(parents=True)
    try:
        link.symlink_to(outside)
    except OSError:
        pytest.skip("symlinks are unavailable")

    with pytest.raises(PrivateMediaError, match="invalid private media reference"):
        resolver.resolve("body", "ab/abcdef0123456789abcdef0123456789.jpg", "image/jpeg")
