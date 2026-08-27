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
    assert row["destination_sha256"] == digest

    destination.write_bytes(b"different video")
    with pytest.raises(MediaMigrationError, match="Destination hash mismatch"):
        copy_and_verify_row(row)


def test_copy_and_verify_first_second_third_runs_allow_missing_source(
    tmp_path: Path,
) -> None:
    from app.exercises.media_migration import copy_and_verify_row

    source = tmp_path / "source.mp4"
    destination = tmp_path / "canonical" / "media.mp4"
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
    assert row["copied"] is True
    assert row["hash_verified"] is True
    assert row["destination_sha256"] == digest
    assert len(list(tmp_path.rglob("*.mp4"))) == 2

    copy_and_verify_row(row)
    assert row["copied"] is False
    assert row["hash_verified"] is True
    assert row["destination_sha256"] == digest
    assert len(list(tmp_path.rglob("*.mp4"))) == 2

    row["current_physical_path"] = str(tmp_path / "source-no-longer-mounted.mp4")
    copy_and_verify_row(row)
    assert row["copied"] is False
    assert row["hash_verified"] is True
    assert row["destination_sha256"] == digest
    assert destination.read_bytes() == b"source video"
    assert len(list(destination.parent.glob("*.mp4"))) == 1


def test_copy_and_verify_existing_destination_does_not_require_source(tmp_path: Path) -> None:
    from app.exercises.media_migration import copy_and_verify_row

    destination = tmp_path / "canonical.mp4"
    destination.write_bytes(b"canonical video")
    digest = hashlib.sha256(destination.read_bytes()).hexdigest()
    row = {
        "current_physical_path": None,
        "destination_physical_path": str(destination),
        "sha256": digest,
        "placeholder": False,
        "copied": True,
        "hash_verified": False,
    }

    copy_and_verify_row(row)

    assert row["copied"] is False
    assert row["hash_verified"] is True
    assert row["destination_sha256"] == digest
    assert destination.read_bytes() == b"canonical video"


def test_copy_and_verify_destination_mismatch_wins_when_source_is_missing(
    tmp_path: Path,
) -> None:
    from app.exercises.media_migration import MediaMigrationError, copy_and_verify_row

    destination = tmp_path / "canonical.mp4"
    destination.write_bytes(b"wrong video")
    row = {
        "current_physical_path": str(tmp_path / "source-no-longer-mounted.mp4"),
        "destination_physical_path": str(destination),
        "sha256": hashlib.sha256(b"expected video").hexdigest(),
        "placeholder": False,
        "copied": False,
        "hash_verified": False,
    }

    with pytest.raises(MediaMigrationError, match="Destination hash mismatch"):
        copy_and_verify_row(row)

    assert destination.read_bytes() == b"wrong video"


def test_copy_and_verify_non_file_destination_fails_before_missing_source(
    tmp_path: Path,
) -> None:
    from app.exercises.media_migration import MediaMigrationError, copy_and_verify_row

    destination = tmp_path / "canonical.mp4"
    destination.mkdir()
    row = {
        "current_physical_path": str(tmp_path / "source-no-longer-mounted.mp4"),
        "destination_physical_path": str(destination),
        "sha256": "a" * 64,
        "placeholder": False,
        "copied": False,
        "hash_verified": False,
    }

    with pytest.raises(MediaMigrationError, match="Destination hash mismatch"):
        copy_and_verify_row(row)

    assert destination.is_dir()
