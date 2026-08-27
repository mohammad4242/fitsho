from pathlib import Path

import pytest

from app.config import Settings
from app.exercises.media_storage import ExerciseMediaStorageError, publish_exercise_media

GIF_BYTES = b"GIF89a" + b"\x00" * 32


def storage_settings(tmp_path: Path) -> Settings:
    return Settings(
        app_env="test",
        cookie_secure=False,
        session_cookie_name="fitsho_session",
        media_root=tmp_path / "media",
    )


def test_identical_bytes_in_distinct_exercise_namespaces_are_not_shared(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.gif"
    source.write_bytes(GIF_BYTES)
    settings = storage_settings(tmp_path)

    first = publish_exercise_media(source, settings=settings, namespace="exercise-one")
    second = publish_exercise_media(source, settings=settings, namespace="exercise-two")

    assert first.absolute_path != second.absolute_path
    assert first.public_path == f"/media/exercises/exercise-one/{first.absolute_path.name}"
    assert second.public_path == f"/media/exercises/exercise-two/{second.absolute_path.name}"
    assert first.created is True
    assert second.created is True
    assert first.absolute_path.read_bytes() == GIF_BYTES
    assert second.absolute_path.read_bytes() == GIF_BYTES


@pytest.mark.parametrize(
    "namespace",
    ["", ".", "..", "../escape", "nested/exercise", "/absolute", "exercise\\child"],
)
def test_unsafe_exercise_namespace_is_rejected(tmp_path: Path, namespace: str) -> None:
    source = tmp_path / "source.gif"
    source.write_bytes(GIF_BYTES)

    with pytest.raises(ExerciseMediaStorageError, match="namespace"):
        publish_exercise_media(source, settings=storage_settings(tmp_path), namespace=namespace)


def test_existing_file_in_one_namespace_cannot_affect_another(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.gif"
    source.write_bytes(GIF_BYTES)
    settings = storage_settings(tmp_path)
    first = publish_exercise_media(source, settings=settings, namespace="exercise-one")
    first.absolute_path.write_bytes(b"corrupted existing file")

    second = publish_exercise_media(source, settings=settings, namespace="exercise-two")

    assert second.created is True
    assert second.absolute_path.read_bytes() == GIF_BYTES
    assert first.absolute_path.read_bytes() == b"corrupted existing file"
