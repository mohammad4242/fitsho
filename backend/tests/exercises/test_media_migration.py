import hashlib
from pathlib import Path

import pytest


def test_destination_path_is_deterministic_and_collision_safe() -> None:
    from app.exercises.media_migration import destination_relative_path

    path = destination_relative_path(
        slug="romanian-deadlift",
        exercise_id="12345678-1234-1234-1234-123456789abc",
        digest="a" * 64,
        extension=".mp4",
    )

    assert path.as_posix() == ("exercises/romanian-deadlift--12345678/" + f"media-{'a' * 64}.mp4")


def test_copy_and_verify_is_idempotent_and_refuses_hash_mismatch(tmp_path: Path) -> None:
    from app.exercises.media_migration import MediaMigrationError, copy_and_verify_row

    source = tmp_path / "source.mp4"
    destination = tmp_path / "destination.mp4"
    source.write_bytes(b"source video")
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    row = {
        "current_physical_path": str(source),
        "destination_physical_path": str(destination),
        "sha256": digest,
        "placeholder": False,
        "copied": False,
        "hash_verified": False,
    }

    copy_and_verify_row(row)
    copy_and_verify_row(row)

    assert destination.read_bytes() == source.read_bytes()
    assert row["copied"] is False
    assert row["hash_verified"] is True

    destination.write_bytes(b"different video")
    with pytest.raises(MediaMigrationError, match="Destination hash mismatch"):
        copy_and_verify_row(row)
